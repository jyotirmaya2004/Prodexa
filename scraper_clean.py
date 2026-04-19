import logging
import os
import queue
import re
import tempfile
import threading
import time
import urllib.parse
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None
    Options = None
    EdgeOptions = None
    By = None
    WebDriverWait = None
    EC = None

logger = logging.getLogger(__name__)

load_dotenv()

SELENIUM_WORK_DIR = os.path.join(os.getcwd(), ".selenium")
os.makedirs(SELENIUM_WORK_DIR, exist_ok=True)
os.environ.setdefault("SE_CACHE_PATH", os.path.join(SELENIUM_WORK_DIR, "cache"))
os.makedirs(os.environ["SE_CACHE_PATH"], exist_ok=True)

CHROME_PATH = os.environ.get("CHROME_PATH")
EDGE_PATH = os.environ.get("EDGE_PATH")
BRAVE_PATH = os.environ.get("BRAVE_PATH")
if not BRAVE_PATH:
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for path in brave_paths:
        if os.path.exists(path):
            BRAVE_PATH = path
            break

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("SCRAPER_TIMEOUT_SECONDS", "30"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("SCRAPER_REQUEST_TIMEOUT_SECONDS", "20"))

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

GARBAGE_PHRASES = {
    "add to compare",
    "compare",
    "wishlist",
    "share",
    "sponsored",
    "assured",
    "flipkart assured",
    "free delivery",
    "bank offer",
    "partner offer",
    "save extra",
    "limited time deal",
    "prime",
    "amazon's choice",
    "overall pick",
    "best seller",
    "currently unavailable",
    "top discount",
    "bestseller",
    "daily saver",
    "deal of the day",
    "free shipping",
    "out of stock",
    "rating",
    "reviews",
}


DRIVER_INIT_TIMEOUT_SECONDS = int(os.environ.get("DRIVER_INIT_TIMEOUT_SECONDS", "30"))


def _launch_browser(browser_name, browser_path, options_obj, result_queue):
    """Target function for the driver-init thread. Puts the driver or an
    exception into *result_queue* so the caller can apply a wall-clock timeout."""
    try:
        if browser_name == "edge":
            driver = webdriver.Edge(options=options_obj)
        else:
            driver = webdriver.Chrome(options=options_obj)
        result_queue.put(("ok", driver))
    except Exception as exc:
        result_queue.put(("err", exc))


def get_driver():
    """Create and return a Selenium WebDriver instance.

    Driver initialisation is performed in a background thread so that a
    hung ChromeDriver process cannot block the calling thread (and therefore
    the Flask worker) indefinitely.  If the browser fails to start within
    DRIVER_INIT_TIMEOUT_SECONDS the thread is abandoned and a RuntimeError
    is raised so the caller can degrade gracefully.
    """
    if webdriver is None or Options is None:
        raise RuntimeError(
            "Selenium is not installed. Run `pip install selenium` for local setup."
        )

    browser_candidates = []
    if CHROME_PATH:
        browser_candidates.append(("chrome", CHROME_PATH))
    if EDGE_PATH and EdgeOptions is not None:
        browser_candidates.append(("edge", EDGE_PATH))
    if BRAVE_PATH:
        browser_candidates.append(("chrome", BRAVE_PATH))
    if not browser_candidates:
        browser_candidates = [("chrome", None)]

    last_error = None
    for browser_name, browser_path in browser_candidates:
        if browser_name == "edge":
            options = EdgeOptions()
            options.use_chromium = True
        else:
            options = Options()

        if browser_path:
            options.binary_location = browser_path

        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        profile_dir = tempfile.mkdtemp(prefix="selenium-profile-", dir=SELENIUM_WORK_DIR)
        options.add_argument(f"--user-data-dir={profile_dir}")

        result_queue = queue.Queue()
        t = threading.Thread(
            target=_launch_browser,
            args=(browser_name, browser_path, options, result_queue),
            daemon=True,
        )
        logger.info("Starting %s browser (timeout=%ds)…", browser_name, DRIVER_INIT_TIMEOUT_SECONDS)
        t.start()

        try:
            status, value = result_queue.get(timeout=DRIVER_INIT_TIMEOUT_SECONDS)
        except queue.Empty:
            last_error = RuntimeError(
                f"Browser init timed out after {DRIVER_INIT_TIMEOUT_SECONDS}s "
                f"(browser={browser_name}, path={browser_path!r})"
            )
            logger.warning("get_driver: %s", last_error)
            continue

        if status == "ok":
            driver = value
            driver.set_page_load_timeout(DEFAULT_TIMEOUT_SECONDS)
            logger.info("Browser started successfully (%s).", browser_name)
            return driver
        else:
            last_error = value
            logger.warning("get_driver: browser=%s error: %s", browser_name, last_error)

    raise RuntimeError(f"Unable to start Selenium browser: {last_error}")


def fetch_page_html(url, wait_css=None):
    """Fetch a page using Selenium and return its HTML source.

    Raises RuntimeError (propagated from get_driver) if the browser cannot
    be started, so callers can catch it and degrade gracefully.
    """
    logger.info("fetch_page_html: loading %s", url)
    driver = get_driver()  # may raise RuntimeError — intentional
    try:
        driver.get(url)
        if wait_css and WebDriverWait is not None and EC is not None and By is not None:
            try:
                WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
                )
            except Exception:
                pass  # Ignore timeout and parse whatever is loaded

        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        time.sleep(1)
        return driver.page_source
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def fetch_static_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


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
    match = re.search(r"(?:₹|Rs\.?)\s*([0-9][0-9,]{2,})", normalized)
    if not match:
        match = re.search(r"\b([1-9][0-9,]{3,})\b", normalized)
    return match.group(1) if match else "N/A"


def looks_like_price_text(text):
    if not text:
        return False
    normalized = " ".join(str(text).split())
    return bool(re.search(r"(?:₹|Rs\.?)\s*[1-9][0-9,]{2,}|\b[1-9][0-9,]{3,}\b", normalized))


def normalize_price(price):
    extracted = extract_price_from_text(price)
    if extracted == "N/A":
        return "N/A"

    digits_only = extracted.replace(",", "")
    try:
        numeric_value = int(digits_only)
    except ValueError:
        return "N/A"

    if numeric_value < 100:
        return "N/A"

    return extracted


def clean_candidate_text(text):
    normalized = " ".join(str(text).split()).strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered in GARBAGE_PHRASES:
        return ""
    if looks_like_price_text(normalized):
        return ""
    return normalized


def extract_strings(node):
    if not node:
        return []

    cleaned = []
    seen = set()
    for value in node.stripped_strings:
        text = clean_candidate_text(value)
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
    return cleaned


def pick_product_name(link_tag, fallback_href=""):
    candidates = [
        safe_attr(link_tag, "title"),
        safe_attr(link_tag, "aria-label"),
        safe_text(link_tag),
    ]

    image_tag = link_tag.find("img")
    if image_tag:
        candidates.append(safe_attr(image_tag, "alt"))

    parent = link_tag.parent
    if parent:
        candidates.extend(extract_strings(parent)[:5])

    for candidate in candidates:
        text = clean_candidate_text(candidate)
        if not text or len(text) < 6:
            continue
        return text

    path_parts = [part for part in fallback_href.split("/") if part]
    slug = path_parts[0] if path_parts else ""
    return slug.replace("-", " ").title().strip() or "N/A"


def extract_price_from_node(node):
    if not node:
        return "N/A"

    for text in node.stripped_strings:
        if "₹" not in text and "Rs" not in text:
            continue
        normalized_price = normalize_price(text)
        if normalized_price != "N/A":
            return normalized_price
    return "N/A"


def extract_amazon_price(card):
    offscreen = safe_text(card.select_one("span.a-price span.a-offscreen"))
    whole = safe_text(card.select_one("span.a-price-whole"))
    if offscreen:
        return normalize_price(offscreen)

    if whole:
        whole_digits = normalize_price(whole)
        if whole_digits != "N/A":
            return whole_digits

    fallback = safe_text(card.select_one("span.a-color-price"))
    return normalize_price(fallback) if fallback else "N/A"


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
    try:
        html = fetch_page_html(search_url)
    except Exception as exc:
        logger.error("scrape_flipkart: browser unavailable — %s", exc)
        return products
    soup = BeautifulSoup(html, "lxml")

    links = soup.select("a[href*='/p/']")
    seen = set()

    for link_tag in links:
        href = safe_attr(link_tag, "href")
        if not href or "/p/" not in href:
            continue

        full_link = urljoin("https://www.flipkart.com", href)
        base = full_link.split("?")[0]
        if base in seen:
            continue
        seen.add(base)

        container = (
            link_tag.find_parent(attrs={"data-id": True})
            or link_tag.find_parent("article")
            or link_tag.find_parent("li")
            or link_tag.parent
        )
        if not container:
            continue

        # ✅ Extract specific name tags to prevent noisy text dumps
        name_tag = (
            container.select_one("div.KzDlHZ")
            or container.select_one("div._4rR01T")
            or container.select_one("a.s1Q9rs")
            or container.select_one("a.IRpwTa")
            or container.select_one("a.WKTcLC")
        )
        name = safe_text(name_tag) if name_tag else pick_product_name(link_tag, fallback_href=href)

        price = extract_price_from_node(container)
        if price == "N/A":
            continue

        img = container.find("img")
        image = safe_attr(img, "src") or safe_attr(img, "data-src")

        # ✅ Target product bullet lists specifically to prevent garbage specs
        specs = container.select("ul li")
        if specs:
            valid_specs = [safe_text(li) for li in specs if safe_text(li) and len(safe_text(li)) > 3]
            description = " | ".join(valid_specs[:4]) if valid_specs else "Flipkart Product"
        else:
            texts = [text for text in extract_strings(container) if text != name and len(text) > 5]
            description = " | ".join(texts[:4]) if texts else "Flipkart Product"

        products.append(
            build_product(
                "Flipkart",
                search_url,
                name,
                price,
                description,
                image,
                full_link,
            )
        )

    return products


def scrape_amazon(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.amazon.in/s?k={search_query}"

    # ✅ USE SELENIUM (IMPORTANT)
    try:
        html = fetch_page_html(search_url, wait_css="div[data-component-type='s-search-result']")
    except Exception as exc:
        logger.error("scrape_amazon: browser unavailable — %s", exc)
        return products
    soup = BeautifulSoup(html, "lxml")

    cards = soup.select("div[data-component-type='s-search-result']") or soup.select("div.s-result-item[data-asin]")

    for card in cards:
        # Amazon often renders multiple h2 tags (brand + product title). Target
        # the actual product title anchor first to avoid picking brand-only text.
        link_tag = (
            card.select_one("a.s-link-style.a-text-normal")
            or card.select_one("a.a-link-normal.s-no-outline")
            or card.select_one("h2 a")
            or card.select_one("a.a-link-normal.s-underline-text")
        )
        if not link_tag:
            continue

        href = safe_attr(link_tag, "href")
        if not href:
            continue

        link = urljoin("https://www.amazon.in", href)

        # ✅ PRODUCT NAME
        title_h2 = link_tag.select_one("h2") or card.select_one("a.s-link-style.a-text-normal h2")
        name = ""

        if title_h2:
            # Prefer aria-label when present, else use the h2>span text content.
            name = safe_attr(title_h2, "aria-label")
            if not name:
                title_span = title_h2.select_one("span")
                name = safe_text(title_span) or safe_text(title_h2)

        if not name:
            name_tag = (
                link_tag.select_one("span")
                or card.select_one("span.a-size-medium.a-color-base.a-text-normal")
                or card.select_one("span.a-size-base-plus.a-color-base.a-text-normal")
                or card.select_one("span.a-text-normal")
            )
            name = safe_text(name_tag)

        if not name or len(name) < 5:
            continue

        # ✅ PRICE (STRICT)
        price = extract_amazon_price(card)
        if price == "N/A":
            continue

        # ✅ IMAGE
        img_tag = card.select_one("img.s-image")
        image = safe_attr(img_tag, "src")

        # ✅ DESCRIPTION
        description = extract_amazon_description(card)

        products.append(
            build_product(
                "Amazon",
                search_url,
                name,
                price,
                description,
                image,
                link
            )
        )

    return products

def scrape_meesho(query):
    products = []
    search_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.meesho.com/search?q={search_query}"

    # ✅ Selenium required
    try:
        html = fetch_page_html(search_url)
    except Exception as exc:
        logger.error("scrape_meesho: browser unavailable — %s", exc)
        return products
    soup = BeautifulSoup(html, "lxml")

    # Meesho product cards (generic div scan)
    cards = soup.find_all("a", href=True)

    seen = set()

    for tag in cards:
        href = tag.get("href")

        # ✅ only product links
        if not href or "/product/" not in href:
            continue

        link = urljoin("https://www.meesho.com", href)
        base = link.split("?")[0]

        if base in seen:
            continue
        seen.add(base)

        parent = tag.find_parent()

        if not parent:
            continue

        texts = [t.strip() for t in parent.stripped_strings]

        # 🔥 CLEAN TEXT
        ignore_words = [
            "wishlist", "view similar", "free delivery",
            "trusted", "meesho", "rating", "reviews"
        ]

        texts = [
            t for t in texts
            if not any(w in t.lower() for w in ignore_words)
            and len(t) > 5
        ]

        if not texts:
            continue

        # ✅ PRICE
        price = "N/A"
        for t in texts:
            if re.search(r"₹\s*[1-9][0-9,]{2,}", t):
                price = re.search(r"[0-9,]+", t).group()
                break

        if price == "N/A":
            continue

        # ✅ NAME
        name = next((t for t in texts if len(t) > 15 and "₹" not in t), texts[0])

        if len(name.split()) < 2:
            continue

        # ✅ IMAGE
        img_tag = parent.find("img")
        image = img_tag.get("src") if img_tag else ""

        # ✅ DESCRIPTION
        description = " | ".join(texts[1:4]) if len(texts) > 1 else "Meesho Product"

        products.append({
            "Source": "Meesho",
            "Product Name": name,
            "Price": price,
            "Description": description,
            "Image": image,
            "Link": link
        })

    return products


def scrape_myntra(query):
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
