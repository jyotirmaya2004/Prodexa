import os
import random
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from curator import curate_data
from database import (
    create_user,
    delete_product,
    get_all_products,
    get_latest_active_reset_code,
    get_user_by_email,
    get_user_by_username,
    insert_products,
    mark_password_reset_code_used,
    store_password_reset_code,
    update_user_password,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-prodexa")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    left = random.randint(1, 9)
    right = random.randint(1, 9)
    session["captcha_answer"] = str(left + right)
    session["captcha_prompt"] = f"{left} + {right}"


def get_captcha_prompt():
    if "captcha_prompt" not in session or "captcha_answer" not in session:
        generate_captcha()
    return session["captcha_prompt"]


def validate_captcha(answer):
    expected = str(session.get("captcha_answer", "")).strip()
    valid = expected and str(answer).strip() == expected
    generate_captcha()
    return valid


def is_mail_suppressed():
    return os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() in {"1", "true", "yes", "on"}


def send_password_reset_email(to_email, reset_code):
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
    return send_password_reset_email(email, reset_code)


# -----------------------------------
# Auth Routes
# -----------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(username) < 3 or not re.match(r"^[a-zA-Z0-9_]+$", username):
            flash("Username must be at least 3 characters and contain only letters, numbers, or underscores.", "error")
            return render_template("register.html")

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        if not password_is_valid(password):
            flash("Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.", "error")
            return render_template("register.html")

        try:
            existing_user = get_user_by_username(username)
            existing_email = get_user_by_email(email)
        except Exception:
            flash("Database connection failed during registration. Please verify your database settings.", "error")
            return render_template("register.html"), 503

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
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        try:
            user = get_user_by_username(username)
        except Exception:
            flash("Database connection failed during login. Please verify your database settings.", "error")
            return render_template("login.html"), 503
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    captcha_prompt = get_captcha_prompt()

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        captcha = request.form.get("captcha", "")

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("forgot_password.html", captcha_prompt=get_captcha_prompt())

        if not validate_captcha(captcha):
            flash("CAPTCHA validation failed. Please try again.", "error")
            return render_template("forgot_password.html", captcha_prompt=get_captcha_prompt())

        try:
            issued = issue_password_reset(email)
        except Exception:
            flash("Database connection failed while creating a reset request. Please try again.", "error")
            return render_template("forgot_password.html", captcha_prompt=get_captcha_prompt()), 503

        if not issued:
            flash("We could not send the verification email. Please check your SMTP settings and try again.", "error")
            return render_template("forgot_password.html", captcha_prompt=get_captcha_prompt()), 503

        flash("If that email exists, a verification code has been sent.", "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html", captcha_prompt=captcha_prompt)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    preset_email = session.get("password_reset_email", "")

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        verification_code = request.form["verification_code"].strip()
        password = request.form["password"]

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("reset_password.html", preset_email=email)

        if not re.fullmatch(r"\d{6}", verification_code):
            flash("Please enter the 6-digit verification code from your email.", "error")
            return render_template("reset_password.html", preset_email=email)

        if not password_is_valid(password):
            flash("Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.", "error")
            return render_template("reset_password.html", preset_email=email)

        try:
            user = get_user_by_email(email)
            reset_request = user and get_latest_active_reset_code(user["id"])
        except Exception:
            flash("Database connection failed during password reset. Please try again.", "error")
            return render_template("reset_password.html", preset_email=email), 503

        if not user or not reset_request or not check_password_hash(reset_request["code_hash"], verification_code):
            flash("Invalid or expired verification code.", "error")
            return render_template("reset_password.html", preset_email=email)

        updated = update_user_password(user["id"], generate_password_hash(password))
        used = mark_password_reset_code_used(reset_request["id"])

        if not updated or not used:
            flash("We could not update your password. Please try again.", "error")
            return render_template("reset_password.html", preset_email=email), 503

        session.pop("password_reset_email", None)
        session.pop("debug_reset_code", None)
        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", preset_email=preset_email)


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
    return render_template("index.html")


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

    return render_template("productdetails_dynamic.html", product=selected_product)


# -----------------------------------
# Search Route
# -----------------------------------
@app.route("/search", methods=["POST"])
def search():
    query = request.form["product"]

    try:
        from scraper import scrape_all_sites
    except Exception as exc:
        return render_template(
            "results_dynamic.html",
            products=[],
            query=query,
            scrape_errors=[f"Scraper unavailable: {exc}"],
        )

    df = scrape_all_sites(query)
    scrape_errors = df.attrs.get("scrape_errors", [])
    df = curate_data(df)
    products = df.to_dict(orient="records")

    return render_template(
        "results_dynamic.html",
        products=products,
        query=query,
        scrape_errors=scrape_errors,
    )


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
