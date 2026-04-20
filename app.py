import base64
import os
import random
import re
import secrets
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from curator import curate_data
from database import (
    cache_search_results,
    create_user,
    delete_product,
    get_active_ip_block,
    get_all_products,
    get_cached_search_results,
    get_latest_active_reset_code,
    get_user_search_recommendations,
    get_user_by_email,
    get_user_by_username,
    insert_products,
    record_user_search,
    create_review,
    get_reviews_by_product_id,
    mark_password_reset_code_used,
    record_ip_violation,
    store_password_reset_code,
    update_user_password,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-prodexa")
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
app.config["RATELIMIT_HEADERS_ENABLED"] = True

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEARCH_QUERY_REGEX = re.compile(r"^[a-zA-Z0-9\s\-_,.+()]{2,80}$")

ABUSE_BLOCK_SECONDS = int(os.environ.get("ABUSE_BLOCK_SECONDS", "1800"))
ABUSE_MAX_VIOLATIONS = int(os.environ.get("ABUSE_MAX_VIOLATIONS", "8"))
ABUSE_VIOLATION_WINDOW_SECONDS = int(os.environ.get("ABUSE_VIOLATION_WINDOW_SECONDS", "900"))
ABUSE_TRACKER = {}


def normalize_search_query(query):
    return " ".join((query or "").strip().lower().split())


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address() or "unknown"


limiter = Limiter(
    key_func=get_client_ip,
    app=app,
    default_limits=["400 per day", "120 per hour"],
)


def prune_abuse_tracker(now):
    stale_ips = []
    for ip, data in ABUSE_TRACKER.items():
        if data.get("blocked_until", 0) < now - ABUSE_VIOLATION_WINDOW_SECONDS and data.get("violations", 0) <= 0:
            stale_ips.append(ip)
    for ip in stale_ips:
        ABUSE_TRACKER.pop(ip, None)


def register_violation(ip):
    now = time.time()
    prune_abuse_tracker(now)

    record = ABUSE_TRACKER.setdefault(ip, {"violations": 0, "last_violation": 0, "blocked_until": 0})
    if now - record["last_violation"] > ABUSE_VIOLATION_WINDOW_SECONDS:
        record["violations"] = 0

    record["violations"] += 1
    record["last_violation"] = now

    if record["violations"] >= ABUSE_MAX_VIOLATIONS:
        record["blocked_until"] = now + ABUSE_BLOCK_SECONDS

    # Persist violations so blocks survive process restarts.
    try:
        persisted = record_ip_violation(
            ip,
            max_violations=ABUSE_MAX_VIOLATIONS,
            window_seconds=ABUSE_VIOLATION_WINDOW_SECONDS,
            block_seconds=ABUSE_BLOCK_SECONDS,
            reason="automated abuse detected",
        )
    except Exception:
        persisted = None
    if persisted and persisted.get("blocked_until"):
        persisted_blocked_until = persisted["blocked_until"].timestamp()
        if persisted_blocked_until > record.get("blocked_until", 0):
            record["blocked_until"] = persisted_blocked_until


def get_persistent_blocked_until(ip):
    try:
        active_block = get_active_ip_block(ip)
    except Exception:
        return 0
    if not active_block:
        return 0
    blocked_until = active_block.get("blocked_until")
    if not blocked_until:
        return 0
    return blocked_until.timestamp()


def issue_form_token(form_name):
    token = secrets.token_urlsafe(24)
    session[f"{form_name}_form_token"] = token
    session[f"{form_name}_form_issued_at"] = time.time()
    return token


def validate_form_token(form_name, submitted_token, min_age_seconds=1, max_age_seconds=1800):
    expected_token = session.pop(f"{form_name}_form_token", "")
    issued_at = session.pop(f"{form_name}_form_issued_at", 0)

    if not expected_token or not submitted_token:
        return False

    if not secrets.compare_digest(str(expected_token), str(submitted_token)):
        return False

    now = time.time()
    age = now - float(issued_at or 0)
    if age < min_age_seconds or age > max_age_seconds:
        return False

    return True


def has_honeypot_content():
    return bool(request.form.get("website", "").strip())


@app.before_request
def enforce_temporary_ip_blocks():
    if request.endpoint == "static":
        return None

    ip = get_client_ip()
    now = time.time()
    memory_blocked_until = ABUSE_TRACKER.get(ip, {}).get("blocked_until", 0)
    persistent_blocked_until = get_persistent_blocked_until(ip)
    effective_blocked_until = max(memory_blocked_until, persistent_blocked_until)

    if effective_blocked_until > now:
        retry_after = int(effective_blocked_until - now)
        message = {"error": "We've received too many requests from your device. Please wait a moment and try again."}
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            response = jsonify(message)
            response.status_code = 429
            response.headers["Retry-After"] = str(max(retry_after, 1))
            return response
        return render_template("index.html", search_form_token=issue_form_token("search"), blocked_error=message["error"]), 429


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(exc):
    ip = get_client_ip()
    register_violation(ip)
    retry_after = int(getattr(exc, "retry_after", 60) or 60)
    message = "You're moving a bit too fast. Please wait a moment and try again."
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        response = jsonify({"error": message})
        response.status_code = 429
        response.headers["Retry-After"] = str(max(retry_after, 1))
        return response
    flash(message, "error")
    if request.endpoint == "register":
        return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt()), 429
    if request.endpoint == "forgot_password":
        return render_template(
            "forgot_password.html",
            captcha_prompt=get_captcha_prompt(),
            forgot_form_token=issue_form_token("forgot_password"),
        ), 429
    if request.endpoint == "login":
        return render_template("login.html", captcha_prompt=get_captcha_prompt()), 429
    return render_template("index.html", search_form_token=issue_form_token("search")), 429


# -----------------------------------
# Authentication & Security
# -----------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "Unauthorized"}), 401
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def password_is_valid(password):
    return (
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
        and re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    )


def generate_captcha():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    answer = "".join(random.choice(chars) for _ in range(5))

    width, height = 250, 90
    svg = f'<svg width="180" height="65" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="captcha" class="captcha-img cursor-pointer" title="Click to refresh">'
    svg += """
    <defs>
        <linearGradient id="bgGradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#f8fbff"/>
            <stop offset="45%" stop-color="#edf4fb"/>
            <stop offset="100%" stop-color="#fef8ef"/>
        </linearGradient>
        <filter id="warp" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.012 0.06" numOctaves="2" seed="7" result="noise"/>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="6" xChannelSelector="R" yChannelSelector="G"/>
        </filter>
        <filter id="softBlur" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="0.45"/>
        </filter>
        <filter id="grain" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.95" numOctaves="1" seed="12"/>
            <feColorMatrix type="saturate" values="0"/>
            <feComponentTransfer>
                <feFuncA type="table" tableValues="0 0.06"/>
            </feComponentTransfer>
        </filter>
    </defs>
    """
    svg += f'<rect width="{width}" height="{height}" rx="12" fill="url(#bgGradient)"/>'

    # Fine grain and random dots introduce texture variation.
    svg += f'<rect width="{width}" height="{height}" filter="url(#grain)"/>'
    for _ in range(85):
        cx, cy = random.randint(0, width), random.randint(0, height)
        r = random.randint(1, 2)
        opacity = random.uniform(0.15, 0.5)
        color = random.choice(["#7c8ea5", "#5f738c", "#8b9db3"])
        svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{opacity:.2f}"/>'

    # Interference lines and curves crossing text regions.
    for _ in range(9):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        sw = random.randint(1, 3)
        opacity = random.uniform(0.28, 0.62)
        svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#5a6f88" stroke-width="{sw}" stroke-linecap="round" opacity="{opacity:.2f}"/>'

    for _ in range(4):
        y_start = random.randint(18, height - 18)
        qx = random.randint(70, width - 70)
        qy = random.randint(0, height)
        y_end = random.randint(18, height - 18)
        path_d = f"M 0 {y_start} Q {qx} {qy}, {width} {y_end}"
        svg += f'<path d="{path_d}" stroke="#4a627f" stroke-width="2" fill="none" opacity="0.62" filter="url(#softBlur)"/>'

    x = 26
    for char in answer:
        y = random.randint(56, 72)
        angle = random.randint(-34, 34)
        font_size = random.randint(36, 44)
        dx = random.randint(-2, 2)
        dy = random.randint(-2, 2)
        fill = random.choice(["#0f172a", "#15263b", "#1e293b", "#22344a"])

        # Draw slight shadow and warped foreground glyph for OCR resistance.
        svg += f'<text x="0" y="0" font-family="Verdana, Tahoma, sans-serif" font-size="{font_size}" font-weight="800" fill="#f8fafc" opacity="0.48" transform="translate({x + 2 + dx}, {y + 1 + dy}) rotate({angle})">{char}</text>'
        svg += f'<text x="0" y="0" font-family="Verdana, Tahoma, sans-serif" font-size="{font_size}" font-weight="800" fill="{fill}" transform="translate({x + dx}, {y + dy}) rotate({angle})" filter="url(#warp)">{char}</text>'
        x += random.randint(38, 44)

    # Extra partial strokes over characters.
    for _ in range(5):
        sx = random.randint(0, width)
        sy = random.randint(18, height - 10)
        ex = min(width, sx + random.randint(26, 72))
        ey = max(8, min(height - 8, sy + random.randint(-12, 12)))
        svg += f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="#3b4f66" stroke-width="2" opacity="0.35"/>'

    svg += f'<rect x="1.5" y="1.5" width="{width - 3}" height="{height - 3}" rx="10" fill="none" stroke="#d5e2ef" stroke-width="1.5"/>'
    svg += "</svg>"

    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    data_uri = f"data:image/svg+xml;base64,{b64_svg}"

    session["captcha_answer"] = answer
    session.pop("captcha_prompt", None)  # Clean up old session bloat
    return data_uri


def get_captcha_prompt():
    return generate_captcha()


def validate_captcha(answer):
    expected = str(session.get("captcha_answer", "")).strip()
    valid = bool(expected) and str(answer).strip().upper() == expected
    session.pop("captcha_answer", None)  # Clear the answer so it can't be reused
    return valid


def is_mail_suppressed():
    return os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() in {"1", "true", "yes", "on"}


def send_password_reset_email(to_email, reset_code, username):
    if is_mail_suppressed():
        print(f"Password reset code for {to_email}: {reset_code}")
        return True

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM", smtp_user or "no-reply@prodexa.local")
    use_ssl = os.environ.get("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    if not smtp_host:
        return False

    message = EmailMessage()
    message["Subject"] = "Prodexa password reset verification code"
    message["From"] = mail_from
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                f"Hi {username},",
                "",
                "Use the verification code below to reset your Prodexa password.",
                "",
                f"Code: {reset_code}",
                "",
                "This code expires in 10 minutes.",
                "If you did not request this, you can ignore this email.",
            ]
        )
    )

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(message)
        return True
    except Exception as exc:
        print(f"Password reset email error: {exc}")
        return False


def issue_password_reset(email):
    user = get_user_by_email(email)
    if not user:
        return True

    reset_code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    stored = store_password_reset_code(
        user["id"],
        generate_password_hash(reset_code),
        expires_at,
    )
    if not stored:
        return False

    session["password_reset_email"] = email
    if is_mail_suppressed():
        session["debug_reset_code"] = reset_code
    return send_password_reset_email(email, reset_code, user["username"])


# -----------------------------------
# API Routes
# -----------------------------------
@app.route("/refresh-captcha")
def refresh_captcha_route():
    prompt = generate_captcha()
    return jsonify({"captcha_prompt": prompt})


# -----------------------------------
# Auth Routes
# -----------------------------------
@app.route("/register", methods=["GET", "POST"])
@limiter.limit("6 per hour;20 per day", methods=["POST"])
def register():
    username = ""
    email = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()

        if has_honeypot_content():
            register_violation(get_client_ip())
            flash("Invalid registration request.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        if not validate_form_token("register", request.form.get("form_token", ""), min_age_seconds=1, max_age_seconds=1800):
            register_violation(get_client_ip())
            flash("Registration form expired or invalid. Please try again.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        password = request.form.get("password", "")
        captcha = request.form.get("captcha", "")

        if not validate_captcha(captcha):
            register_violation(get_client_ip())
            flash("The security code was incorrect. Please try again.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        if len(username) < 3 or not re.match(r"^[a-zA-Z0-9_]+$", username):
            flash("Username must be at least 3 characters and contain only letters, numbers, or underscores.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        if not password_is_valid(password):
            flash("Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 400

        try:
            existing_user = get_user_by_username(username)
            existing_email = get_user_by_email(email)
        except Exception:
            flash("We're experiencing technical difficulties right now. Please try again later.", "error")
            return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email), 503

        if existing_user:
            flash("Username already exists.", "error")
        elif existing_email:
            flash("Email already exists.", "error")
        else:
            hashed_pw = generate_password_hash(password)
            if create_user(username, email, hashed_pw):
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            flash("An error occurred during registration.", "error")
    return render_template("register.html", register_form_token=issue_form_token("register"), captcha_prompt=get_captcha_prompt(), username=username, email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        captcha = request.form.get("captcha", "")

        if not validate_captcha(captcha):
            register_violation(get_client_ip())
            flash("The security code was incorrect. Please try again.", "error")
            return render_template("login.html", captcha_prompt=get_captcha_prompt(), username=username), 400

        try:
            user = get_user_by_username(username)
        except Exception:
            flash("We're experiencing technical difficulties right now. Please try again later.", "error")
            return render_template("login.html", captcha_prompt=get_captcha_prompt(), username=username), 503
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
        return render_template("login.html", captcha_prompt=get_captcha_prompt(), username=username), 401
    return render_template("login.html", captcha_prompt=get_captcha_prompt(), username=username)


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("8 per hour;25 per day", methods=["POST"])
def forgot_password():
    email = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if has_honeypot_content():
            register_violation(get_client_ip())
            flash("Invalid reset request.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            ), 400

        if not validate_form_token("forgot_password", request.form.get("form_token", ""), min_age_seconds=1, max_age_seconds=1800):
            register_violation(get_client_ip())
            flash("Request expired or invalid. Please try again.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            ), 400

        captcha = request.form.get("captcha", "")

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            )

        if not validate_captcha(captcha):
            register_violation(get_client_ip())
            flash("The security code was incorrect. Please try again.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            )

        try:
            issued = issue_password_reset(email)
        except Exception:
            flash("We could not process your request at this time. Please try again later.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            ), 503

        if not issued:
            flash("We could not send the verification email. Please try again later.", "error")
            return render_template(
                "forgot_password.html",
                captcha_prompt=get_captcha_prompt(),
                forgot_form_token=issue_form_token("forgot_password"),
                email=email
            ), 503

        flash("If that email exists, a verification code has been sent.", "success")
        return redirect(url_for("reset_password"))

    return render_template(
        "forgot_password.html",
        captcha_prompt=get_captcha_prompt(),
        forgot_form_token=issue_form_token("forgot_password"),
        email=email
    )


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    preset_email = session.get("password_reset_email", "")
    verification_code = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        verification_code = request.form.get("verification_code", "").strip()
        password = request.form.get("password", "")

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code)

        if not re.fullmatch(r"\d{6}", verification_code):
            flash("Please enter the 6-digit verification code from your email.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code)

        if not password_is_valid(password):
            flash("Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code)

        try:
            user = get_user_by_email(email)
            reset_request = user and get_latest_active_reset_code(user["id"])
        except Exception:
            flash("We could not process your request at this time. Please try again later.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code), 503

        if not user or not reset_request or not check_password_hash(reset_request["code_hash"], verification_code):
            flash("Invalid or expired verification code.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code)

        updated = update_user_password(user["id"], generate_password_hash(password))
        used = mark_password_reset_code_used(reset_request["id"])

        if not updated or not used:
            flash("We could not update your password right now. Please try again later.", "error")
            return render_template("reset_password.html", preset_email=email, verification_code=verification_code), 503

        session.pop("password_reset_email", None)
        session.pop("debug_reset_code", None)
        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", preset_email=preset_email, verification_code=verification_code)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# -----------------------------------
# Home Page
# -----------------------------------
@app.route("/")
def home():
    user_recommendations = []
    static_recommendations = [
        "Samsung mobile under 15000",
        "iPhone 15 128GB",
        "Gaming laptop RTX 4060",
        "Bluetooth earbuds under 3000",
    ]

    user_id = session.get("user_id")
    if user_id:
        try:
            db_recs = get_user_search_recommendations(user_id, limit=8)
            static_normalized = {normalize_search_query(q) for q in static_recommendations}
            for rec in db_recs:
                if normalize_search_query(rec) not in static_normalized:
                    user_recommendations.append(rec)
        except Exception:
            user_recommendations = []

    return render_template(
        "index.html",
        search_form_token=issue_form_token("search"),
        user_recommendations=user_recommendations[:4],  # Show up to 4 unique recommendations
    )


# -----------------------------------
# Dashboard Page
# -----------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    products = get_all_products(user_id=session["user_id"])

    total_products = len(products)

    total_brands = len(set(p.get("brand", "") for p in products if p.get("brand")))

    avg_price = 0
    if products:
        avg_price = int(sum(p.get("price", 0) for p in products if p.get("price")) / len(products))

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_brands=total_brands,
        avg_price=avg_price,
        products=products,
    )


# -----------------------------------
# Analytics API
# -----------------------------------
@app.route("/api/analytics")
@login_required
def analytics():
    products = get_all_products(user_id=session["user_id"])

    history = {}
    brands = {}

    for p in products:
        name = p.get("product_name")
        price = p.get("price")
        brand = p.get("brand", "Unknown")
        date_val = p.get("curated_at")

        if not name or price is None:
            continue

        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(date_val)[:16]

        if name not in history:
            history[name] = {"dates": [], "prices": []}

        history[name]["dates"].append(date_str)
        history[name]["prices"].append(price)

        if brand not in brands:
            brands[brand] = []
        brands[brand].append(price)

    for name in history:
        history[name]["dates"].reverse()
        history[name]["prices"].reverse()

    brand_avg = {b: round(sum(prices) / len(prices), 2) for b, prices in brands.items() if prices}

    return jsonify({"history": history, "brands": brand_avg})


# -----------------------------------
# Saved Products Page
# -----------------------------------
@app.route("/saved")
@login_required
def saved():
    products = get_all_products(user_id=session["user_id"])
    return render_template("saved_dynamic.html", products=products)


# -----------------------------------
# Product Details Page
# -----------------------------------
@app.route("/product/<int:product_id>")
@login_required
def product_details(product_id):
    products = get_all_products(user_id=session["user_id"])

    selected_product = None

    for product in products:
        if product["id"] == product_id:
            selected_product = product
            break

    if not selected_product:
        flash("Product not found or you do not have access to it.", "error")
        return redirect(url_for("saved"))

    reviews = get_reviews_by_product_id(product_id)

    return render_template(
        "productdetails_dynamic.html",
        product=selected_product,
        reviews=reviews,
        review_form_token=issue_form_token(f"review_{product_id}")
    )

# -----------------------------------
# Search Route
# -----------------------------------
@app.route("/search", methods=["POST"])
@limiter.limit("24 per hour;120 per day", methods=["POST"])
def search():
    if has_honeypot_content():
        register_violation(get_client_ip())
        return render_template(
            "results_dynamic.html",
            products=[],
            query="",
            scrape_errors=["Your request was blocked. Please try again later."],
        ), 400

    if not validate_form_token("search", request.form.get("form_token", ""), min_age_seconds=1, max_age_seconds=900):
        register_violation(get_client_ip())
        return render_template(
            "results_dynamic.html",
            products=[],
            query="",
            scrape_errors=["Your search session expired. Please try searching again from the home page."],
        ), 400

    query = request.form.get("product", "").strip()
    if not SEARCH_QUERY_REGEX.fullmatch(query):
        register_violation(get_client_ip())
        return render_template(
            "results_dynamic.html",
            products=[],
            query=query,
            recommendations=[],
            scrape_errors=["Please enter a valid product name to search (2 to 80 characters)."],
        ), 400

    normalized_query = normalize_search_query(query)
    user_id = session.get("user_id")
    recommendations = []
    if user_id:
        try:
            recommendations = get_user_search_recommendations(user_id, query_prefix=normalized_query, limit=6)
        except Exception:
            recommendations = []

    try:
        cached_products = get_cached_search_results(normalized_query)
    except Exception:
        cached_products = []

    if cached_products:
        if user_id:
            try:
                record_user_search(
                    user_id=user_id,
                    raw_query=query,
                    normalized_query=normalized_query,
                    result_count=len(cached_products),
                    used_cache=True,
                )
            except Exception:
                pass

        return render_template(
            "results_dynamic.html",
            products=cached_products,
            query=query,
            recommendations=recommendations,
            cache_used=True,
            scrape_errors=[],
        )

    try:
        from scraper import scrape_all_sites
    except Exception as exc:
        return render_template(
            "results_dynamic.html",
            products=[],
            query=query,
            recommendations=recommendations,
            cache_used=False,
            scrape_errors=["Search service is temporarily unavailable. Please try again later."],
        )

    df = scrape_all_sites(query)
    scrape_errors = df.attrs.get("scrape_errors", [])
    df = curate_data(df)
    products = df.to_dict(orient="records")

    if products:
        try:
            cache_search_results(normalized_query, products, created_by_user_id=user_id)
        except Exception:
            pass

    if user_id:
        try:
            record_user_search(
                user_id=user_id,
                raw_query=query,
                normalized_query=normalized_query,
                result_count=len(products),
                used_cache=False,
            )
        except Exception:
            pass

    return render_template(
        "results_dynamic.html",
        products=products,
        query=query,
        recommendations=recommendations,
        cache_used=False,
        scrape_errors=scrape_errors,
    )


# -----------------------------------
# Review Submission
# -----------------------------------
@app.route("/product/<int:product_id>/review", methods=["POST"])
@login_required
def submit_review(product_id):
    if not validate_form_token(f"review_{product_id}", request.form.get("form_token")):
        flash("Review form expired or invalid. Please try again.", "error")
        return redirect(url_for("product_details", product_id=product_id))

    rating = request.form.get("rating")
    comment = request.form.get("comment", "").strip()

    if not rating or not rating.isdigit() or not 1 <= int(rating) <= 5:
        flash("Please select a rating between 1 and 5.", "error")
        return redirect(url_for("product_details", product_id=product_id))

    if len(comment) > 2000:
        flash("Review comment cannot exceed 2000 characters.", "error")
        return redirect(url_for("product_details", product_id=product_id))

    user_id = session["user_id"]

    products = get_all_products(user_id=user_id)
    if not any(p['id'] == product_id for p in products):
        flash("You can only review products you have saved.", "error")
        return redirect(url_for("saved"))

    if create_review(user_id, product_id, int(rating), comment):
        flash("Your review has been submitted!", "success")
    else:
        flash("There was an error submitting your review. You may have already reviewed this product.", "error")

    return redirect(url_for("product_details", product_id=product_id))

# -----------------------------------
# Delete Saved Product
# -----------------------------------
@app.route("/delete/<int:product_id>", methods=["GET", "POST"])
@login_required
def remove_product(product_id):
    delete_product(product_id, user_id=session["user_id"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    return redirect(url_for("saved"))


# -----------------------------------
# Save Product (AJAX)
# -----------------------------------
@app.route("/save", methods=["POST"])
@login_required
def save_product():
    data = request.json
    if data:
        insert_products(pd.DataFrame([data]), user_id=session["user_id"])
        return jsonify({"success": True})
    return jsonify({"error": "No data provided"}), 400


# -----------------------------------
# Run App
# -----------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
