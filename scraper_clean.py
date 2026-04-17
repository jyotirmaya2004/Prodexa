import time
import urllib.parse
from urllib.parse import urljoin
import os
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except ImportError:
    webdriver = None
    Options = None

load_dotenv()

# Try to get BRAVE_PATH from environment, fallback to common locations
BRAVE_PATH = os.environ.get("BRAVE_PATH")
if not BRAVE_PATH:
    # Common Brave browser installation paths
    common_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            BRAVE_PATH = path
            break

PRODUCT_COLUMNS = [
    "Source",
    "Source URL",
    "Search URL",
    "Product Name",
    "Price",
    "Description",
    "Image",
    "Link",
]


def get_driver():
    if webdriver is None or Options is None:
        raise RuntimeError("Selenium is not installed in this deployment.")

    options = Options()
    if BRAVE_PATH:
        options.binary_location = BRAVE_PATH
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def build_product(source, search_url, name, price, description, image, link):
    return {
        "Source": source,
        "Source URL": link or search_url,
        "Search URL": search_url,
        "Product Name": name or "N/A",
        "Price": price or "N/A",
        "Description": description or "N/A",
        "Image": image or "N/A",
        "Link": link or search_url,
    }


def safe_text(tag):
    if not tag:
        return ""
    return tag.get_text(" ", strip=True)


def safe_attr(tag, attr_name):
    if not tag:
        return ""
    return tag.get(attr_name, "").strip()


def extract_price_from_text(text):
    if not text:
        return "N/A"

    normalized = " ".join(str(text).split())
    digits = "".join(ch for ch in normalized if ch.isdigit() or ch == ",")
    return digits if digits else "N/A"


def scrape_flipkart(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.flipkart.com/search?q={search_query}"
    driver = get_driver()

    try:
        driver.get(search_url)
        time.sleep(4)

        soup = BeautifulSoup(driver.page_source, "lxml")

        cards = soup.find_all("a", href=True)

        product_map = {}

        for card in cards:
            href = card.get("href")
            if not href or "/p/" not in href:
                continue

            link = urljoin("https://www.flipkart.com", href)
            base_link = link.split("?")[0]

            name_tag = (
                card.select_one("div.KzDlHZ")
                or card.select_one("a.WKTcLC")
                or card.select_one("div._4rR01T")
                or card.select_one("span.B_NuCI")
            )
            if name_tag:
                name = safe_text(name_tag)
            else:
                path_parts = [part for part in href.split("/") if part]
                slug = path_parts[0] if path_parts else ""
                name = slug.replace("-", " ").title().strip()

            price_tag = (
                card.select_one("div.Nx9bqj")
                or card.select_one("div._30jeq3")
            )

            price = "N/A"
            if price_tag:
                price = extract_price_from_text(price_tag.get_text())
            else:
                for text in card.stripped_strings:
                    if "\u20b9" in text or "₹" in text:
                        price = extract_price_from_text(text)
                        break

            image_tag = card.select_one("img")
            image = safe_attr(image_tag, "src") or safe_attr(image_tag, "data-src")
            if image.startswith("data:image") and safe_attr(image_tag, "data-src"):
                image = safe_attr(image_tag, "data-src")

            desc_list = card.select("ul li")
            if desc_list:
                description = " | ".join([safe_text(li) for li in desc_list])
            else:
                ignore_lower = {"add to compare", "bestseller", "sponsored", "assured", "flipkart assured", "free delivery"}
                description = " | ".join(
                    s for s in card.stripped_strings
                    if s.lower() not in ignore_lower and s != name and s != price and len(s) > 1 and "₹" not in s
                )
            if not description:
                description = "Flipkart Product"

            if base_link not in product_map:
                product_map[base_link] = {
                    "name": name,
                    "price": price,
                    "description": description,
                    "image": image,
                    "link": link
                }
            else:
                existing = product_map[base_link]
                if name_tag:
                    existing["name"] = name
                if price != "N/A":
                    existing["price"] = price
                if image and not image.startswith("data:image"):
                    existing["image"] = image
                if description != "Flipkart Product" and len(description) > len(existing["description"]):
                    existing["description"] = description

        for base_link, item in product_map.items():
            products.append(
                build_product("Flipkart", search_url, item["name"], item["price"], item["description"], item["image"], item["link"])
            )
    finally:
        driver.quit()

    return products


def scrape_amazon(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.amazon.in/s?k={search_query}"
    driver = get_driver()

    try:
        driver.get(search_url)
        time.sleep(4)

        soup = BeautifulSoup(driver.page_source, "lxml")
        cards = soup.select("div[data-component-type='s-search-result']")

        for card in cards:
            title_link = card.select_one("h2 a")
            name_tag = card.select_one("h2 span")
            price_tag = (
                card.select_one("span.a-price-whole")
                or card.select_one("span.a-offscreen")
            )
            image_tag = card.select_one("img.s-image")

            link = urljoin("https://www.amazon.in", safe_attr(title_link, "href"))
            name = safe_text(name_tag)
            price = safe_text(price_tag)
            image = safe_attr(image_tag, "src")

            rating_tag = card.select_one("span.a-icon-alt")
            rating = safe_text(rating_tag)

            review_tag = card.select_one("span.a-size-base.s-underline-text")
            reviews = safe_text(review_tag)

            desc_parts = []
            if rating:
                desc_parts.append(f"Rating: {rating}")
            if reviews:
                desc_parts.append(f"Reviews: {reviews}")

            description = " | ".join(desc_parts) if desc_parts else "Amazon Product"

            if not link or not name:
                continue

            products.append(
                build_product(
                    "Amazon",
                    search_url,
                    name,
                    price,
                    description,
                    image,
                    link,
                )
            )
    finally:
        driver.quit()

    return products


def scrape_myntra(query):
    return []


def scrape_meesho(query):
    return []


def scrape_all_sites(query):
    all_products = []
    errors = []

    scrapers = [
        ("Flipkart", scrape_flipkart),
        ("Amazon", scrape_amazon),
        ("Myntra", scrape_myntra),
        ("Meesho", scrape_meesho),
    ]

    for source_name, scraper_fn in scrapers:
        try:
            all_products.extend(scraper_fn(query))
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")

    df = pd.DataFrame(all_products, columns=PRODUCT_COLUMNS)
    df.attrs["scrape_errors"] = errors
    return df
