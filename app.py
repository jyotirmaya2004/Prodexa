import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from scraper import scrape_all_sites
from curator import curate_data
import pandas as pd
from database import (
    create_products_table,
    insert_products,
    get_all_products,
    delete_product,
    create_user,
    get_user_by_username
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-prodexa")

# Create table when app starts
create_products_table()


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


# -----------------------------------
# Auth Routes
# -----------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if get_user_by_username(username):
            flash("Username already exists.", "error")
        else:
            hashed_pw = generate_password_hash(password)
            if create_user(username, hashed_pw):
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            else:
                flash("An error occurred during registration.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")
    return render_template("login.html")

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

    total_brands = len(
        set(
            p.get("brand", "")
            for p in products
            if p.get("brand")
        )
    )

    avg_price = 0
    if products:
        avg_price = int(
            sum(
                p.get("price", 0)
                for p in products
                if p.get("price")
            ) / len(products)
        )

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_brands=total_brands,
        avg_price=avg_price,
        products=products
    )


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

    return render_template(
        "productdetails_dynamic.html",
        product=selected_product
    )


# -----------------------------------
# Search Route
# -----------------------------------
@app.route("/search", methods=["POST"])
def search():
    query = request.form["product"]

    # 1. Scrape all sites
    df = scrape_all_sites(query)
    scrape_errors = df.attrs.get("scrape_errors", [])

    # 2. Curate data
    df = curate_data(df)

    # 3. Save to database (Disabled auto-save so users can save manually via UI)

    # 4. Convert to template format
    products = df.to_dict(orient="records")

    return render_template(
        "results_dynamic.html",
        products=products,
        query=query,
        scrape_errors=scrape_errors
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
    app.run(debug=True)
