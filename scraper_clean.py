import os
import re
import urllib.parse
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

load_dotenv()

# Try to get BRAVE_PATH from environment, fallback to common locations
BRAVE_PATH = os.environ.get("BRAVE_PATH")
if not BRAVE_PATH:
    common_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            BRAVE_PATH = path
            break

DEFAULT_TIMEOUT_MS = int(os.environ.get("SCRAPER_TIMEOUT_MS", "30000"))

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
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run `pip install playwright` and "
            "`python -m playwright install chromium` for local setup."
        )
    return sync_playwright()


def fetch_page_html(url, wait_for=None):
    with get_driver() as playwright:
        launch_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if BRAVE_PATH:
            launch_options["executable_path"] = BRAVE_PATH

        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            if wait_for:
                page.wait_for_selector(wait_for, timeout=DEFAULT_TIMEOUT_MS)
            else:
                page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)
            return page.content()
        finally:
            context.close()
            browser.close()


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
    match = re.search(r"(\d[\d,]*)", normalized)
    return match.group(1) if match else "N/A"


def looks_like_price_text(text):
    if not text:
        return False
    normalized = " ".join(str(text).split())
    return bool(re.search(r"(?:₹|Rs\.?)\s*\d[\d,]*|\b\d{3,}(?:,\d{2,3})*\b", normalized))


def normalize_price(price):
    extracted = extract_price_from_text(price)
    return extracted if extracted != "N/A" else "N/A"


def extract_amazon_price(card):
    offscreen = safe_text(card.select_one("span.a-price span.a-offscreen"))
    whole = safe_text(card.select_one("span.a-price-whole"))
    if offscreen:
        return normalize_price(offscreen)

    if whole:
        whole_digits = normalize_price(whole)
        if whole_digits == "N/A":
            return "N/A"
        return whole_digits

    return "N/A"


def extract_amazon_description(card):
    description_candidates = []

    feature_selectors = [
        "div.a-row.a-size-base.a-color-secondary",
        "div.a-row.a-size-small",
        "div.a-row.a-spacing-small span.a-size-base",
        "div.a-section.a-spacing-small span.a-size-base",
    ]

    ignore_phrases = {
        "sponsored",
        "limited time deal",
        "prime",
        "amazon's choice",
        "overall pick",
        "best seller",
    }

    for selector in feature_selectors:
        for node in card.select(selector):
            text = safe_text(node)
            lowered = text.lower()
            if not text or lowered in ignore_phrases:
                continue
            if "ratings" in lowered or "rating" in lowered or "review" in lowered:
                continue
            if looks_like_price_text(text):
                continue
            if len(text) < 8:
                continue
            if text not in description_candidates:
                description_candidates.append(text)
        if description_candidates:
            break

    if description_candidates:
        return " | ".join(description_candidates[:3])

    bullet_points = [
        safe_text(node)
        for node in card.select("ul.a-unordered-list li span")
        if safe_text(node) and not looks_like_price_text(safe_text(node))
    ]
    if bullet_points:
        return " | ".join(bullet_points[:3])

    rating = safe_text(card.select_one("span.a-icon-alt"))
    reviews = safe_text(card.select_one("span.a-size-base.s-underline-text"))
    meta_parts = []
    if rating:
        meta_parts.append(f"Rating: {rating}")
    if reviews:
        meta_parts.append(f"Reviews: {reviews}")
    return " | ".join(meta_parts) if meta_parts else "Amazon Product"


def scrape_flipkart(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.flipkart.com/search?q={search_query}"
    soup = BeautifulSoup(fetch_page_html(search_url, wait_for="a[href*='/p/']"), "lxml")

    cards = (
        soup.select("div[data-id]")
        or soup.select("div._1AtVbE")
        or soup.select("div._75nlfW")
    )
    product_map = {}

    for card in cards:
        title_link = card.select_one("a[href*='/p/']")
        href = safe_attr(title_link, "href")
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
            or card.select_one("div._1_WHN1")
        )

        price = "N/A"
        if price_tag:
            price = normalize_price(price_tag.get_text())
        else:
            for text in card.stripped_strings:
                if looks_like_price_text(text):
                    price = normalize_price(text)
                    break

        image_tag = card.select_one("img")
        image = safe_attr(image_tag, "src") or safe_attr(image_tag, "data-src")
        if image.startswith("data:image") and safe_attr(image_tag, "data-src"):
            image = safe_attr(image_tag, "data-src")

        desc_list = card.select("ul li")
        if desc_list:
            description = " | ".join([safe_text(li) for li in desc_list])
        else:
            ignore_lower = {
                "add to compare",
                "bestseller",
                "sponsored",
                "assured",
                "flipkart assured",
                "free delivery",
            }
            description = " | ".join(
                s
                for s in card.stripped_strings
                if s.lower() not in ignore_lower and s != name and s != price and len(s) > 1 and not looks_like_price_text(s)
            )
        if not description:
            description = "Flipkart Product"

        if base_link not in product_map:
            product_map[base_link] = {
                "name": name,
                "price": price,
                "description": description,
                "image": image,
                "link": link,
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

    for item in product_map.values():
        products.append(
            build_product(
                "Flipkart",
                search_url,
                item["name"],
                item["price"],
                item["description"],
                item["image"],
                item["link"],
            )
        )

    return products


def scrape_amazon(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.amazon.in/s?k={search_query}"
    soup = BeautifulSoup(
        fetch_page_html(search_url, wait_for="div[data-component-type='s-search-result']"),
        "lxml",
    )
    cards = soup.select("div[data-component-type='s-search-result']")

    for card in cards:
        title_link = card.select_one("h2 a")
        name_tag = card.select_one("h2 span")
        image_tag = card.select_one("img.s-image")

        link = urljoin("https://www.amazon.in", safe_attr(title_link, "href"))
        name = safe_text(name_tag)
        price = extract_amazon_price(card)
        image = safe_attr(image_tag, "src")
        description = extract_amazon_description(card)

        if not link or not name or price == "N/A":
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
