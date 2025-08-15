import logging
import os
import time
import socket
import requests
import subprocess
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException, ElementClickInterceptedException
from selenium_stealth import stealth

# ----------------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------
# GLOBALS
# ----------------------------------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in environment variables.")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID must be set in environment variables.")

PAYMENT_GATEWAYS = [
    "paypal", "stripe", "braintree", "square", "magento", "avs", "convergepay",
    "paysimple", "oceanpayments", "eprocessing", "hipay", "worldpay", "cybersource",
    "payjunction", "authorize.net", "2checkout", "adyen", "checkout.com", "payflow",
    "payeezy", "usaepay", "creo", "squareup", "authnet", "ebizcharge", "cpay",
    "moneris", "recurly", "cardknox", "chargify", "paytrace", "hostedpayments",
    "securepay", "eway", "blackbaud", "lawpay", "clover", "cardconnect", "bluepay",
    "fluidpay", "rocketgateway", "rocketgate", "shopify", "woocommerce",
    "bigcommerce", "opencart", "prestashop", "razorpay"
]
FRONTEND_FRAMEWORKS = ["react", "angular", "vue", "svelte"]
BACKEND_FRAMEWORKS = [
    "wordpress", "laravel", "django", "node.js", "express", "ruby on rails",
    "flask", "php", "asp.net", "spring"
]
DESIGN_LIBRARIES = ["bootstrap", "tailwind", "bulma", "foundation", "materialize"]

# ----------------------------------------------------------------------------------
# CHROMEDRIVER SETUP (OPTIONAL AUTO-INSTALL)
# ----------------------------------------------------------------------------------

def setup_chrome_driver():
    try:
        logger.info("Setting up ChromeDriver automatically...")
        subprocess.run(['apt-get', 'update'], check=True)
        subprocess.run(['apt-get', 'install', '-y', 'wget', 'unzip'], check=True)
        logger.info("ChromeDriver setup assumed managed by Selenium Manager.")
    except Exception as e:
        logger.error(f"Error setting up ChromeDriver: {e}")
        raise

# ----------------------------------------------------------------------------------
# CREATE A NEW DRIVER FOR EACH PAGE
# ----------------------------------------------------------------------------------

def create_local_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(), options=chrome_options)

    stealth(
        driver,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/110.0.5481.105 Safari/537.36"
        ),
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    driver.set_page_load_timeout(20)
    return driver

def click_google_consent_if_needed(driver, wait_seconds=2):
    time.sleep(wait_seconds)
    possible_selectors = [
        "button#L2AGLb",
        "button#W0wltc",
        "div[role='none'] button:nth-of-type(2)",
    ]
    for sel in possible_selectors:
        try:
            btn = driver.find_element("css selector", sel)
            btn.click()
            logger.info(f"Clicked Google consent button: {sel}")
            time.sleep(1.5)
            return
        except (NoSuchElementException, ElementClickInterceptedException):
            pass

# ----------------------------------------------------------------------------------
# GOOGLE SEARCH WITH PAGINATION
# ----------------------------------------------------------------------------------

def google_search(query: str, limit: int = 10, offset: int = 0):
    all_links = []
    seen = set()

    pages_needed = (limit // 100) + (1 if limit % 100 != 0 else 0)
    max_pages = min(pages_needed, 10)

    logger.info(f"[google_search] Query='{query}', limit={limit}, offset={offset}")
    logger.info(f"Starting multi-page scrape: need {limit} results, up to {max_pages} pages")

    for page_index in range(max_pages):
        start_val = offset + (page_index * 100)
        driver = create_local_driver()
        try:
            url = (
                f"https://www.google.com/search?q={query}"
                f"&num=100"
                f"&start={start_val}"
                f"&hl=en&gl=us"
            )
            logger.info(f"Navigating to: {url}")
            driver.get(url)

            click_google_consent_if_needed(driver)

            time.sleep(2)

            a_elements = driver.find_elements("css selector", "div.yuRUbf > a")
            if not a_elements:
                logger.info(f"No results found on page_index={page_index} => stopping.")
                break

            page_links = []
            for a_tag in a_elements:
                href = a_tag.get_attribute("href")
                if href and href.startswith("http"):
                    page_links.append(href)

            for link in page_links:
                if link not in seen:
                    seen.add(link)
                    all_links.append(link)
                if len(all_links) >= limit:
                    break

            logger.info(f"Found {len(page_links)} links on this page. Accumulated so far: {len(all_links)}")

            if len(all_links) >= limit:
                break

        except WebDriverException as e:
            logger.error(f"Error scraping Google on page {page_index}: {e}")
            break
        finally:
            driver.quit()

        time.sleep(3)

    return all_links[:limit]

# ----------------------------------------------------------------------------------
# DETECT TECH STACK
# ----------------------------------------------------------------------------------

def detect_tech_stack(html_text: str):
    txt_lower = html_text.lower()

    front_found = []
    for fw in FRONTEND_FRAMEWORKS:
        if fw in txt_lower:
            front_found.append(fw)

    back_found = []
    for bw in BACKEND_FRAMEWORKS:
        if bw in txt_lower:
            back_found.append(bw)

    design_found = []
    for ds in DESIGN_LIBRARIES:
        if ds in txt_lower:
            design_found.append(ds)

    return {
        "front_end": ", ".join(set(front_found)) if front_found else "None",
        "back_end": ", ".join(set(back_found)) if back_found else "None",
        "design": ", ".join(set(design_found)) if design_found else "None",
    }

# ----------------------------------------------------------------------------------
# SITE DETAILS CHECK
# ----------------------------------------------------------------------------------

def check_site_details(url: str):
    details = {
        "url": url,
        "dns": "N/A",
        "ssl": "N/A",
        "status_code": 0,
        "cloudflare": "NO",
        "captcha": "NO",
        "gateways": "",
        "graphql": "NO",
        "language": "N/A",
        "front_end": "None",
        "back_end": "None",
        "design": "None",
    }

    domain = extract_domain(url)
    if domain:
        try:
            socket.gethostbyname(domain)
            details["dns"] = "resolvable"
        except:
            details["dns"] = "unresolvable"

    try:
        resp = requests.get(url, timeout=10, verify=True)
        details["ssl"] = "valid"
        details["status_code"] = resp.status_code
        txt_lower = resp.text.lower()

        if any("cloudflare" in k.lower() for k in resp.headers.keys()) or \
           any("cloudflare" in v.lower() for v in resp.headers.values()):
            details["cloudflare"] = "✅ YES"
        else:
            details["cloudflare"] = "🔥 NO"

        if "captcha" in txt_lower or "recaptcha" in txt_lower:
            details["captcha"] = "✅ YES"
        else:
            details["captcha"] = "🔥 NO"

        if "graphql" in txt_lower:
            details["graphql"] = "YES"
        else:
            details["graphql"] = "NO"

        lang = extract_language(resp.text)
        if lang:
            details["language"] = lang

        found_gw = []
        for gw in PAYMENT_GATEWAYS:
            if gw.lower() in txt_lower:
                found_gw.append(gw)
        details["gateways"] = ", ".join(set(found_gw)) if found_gw else "None"

        stack = detect_tech_stack(resp.text)
        details["front_end"] = stack["front_end"]
        details["back_end"] = stack["back_end"]
        details["design"] = stack["design"]

    except requests.exceptions.SSLError:
        details["ssl"] = "invalid"
        try:
            resp = requests.get(url, timeout=10, verify=False)
            details["status_code"] = resp.status_code
            txt_lower = resp.text.lower()

            if any("cloudflare" in k.lower() for k in resp.headers.keys()) or \
               any("cloudflare" in v.lower() for v in resp.headers.values()):
                details["cloudflare"] = "✅ YES"
            else:
                details["cloudflare"] = "🔥 NO"

            if "captcha" in txt_lower or "recaptcha" in txt_lower:
                details["captcha"] = "✅ YES"
            else:
                details["captcha"] = "🔥 NO"

            if "graphql" in txt_lower:
                details["graphql"] = "YES"
            else:
                details["graphql"] = "NO"

            lang = extract_language(resp.text)
            if lang:
                details["language"] = lang

            found_gw = []
            for gw in PAYMENT_GATEWAYS:
                if gw.lower() in txt_lower:
                    found_gw.append(gw)
            details["gateways"] = ", ".join(set(found_gw)) if found_gw else "None"

            stack = detect_tech_stack(resp.text)
            details["front_end"] = stack["front_end"]
            details["back_end"] = stack["back_end"]
            details["design"] = stack["design"]
        except:
            pass

    except Exception as e:
        logger.error(f"Error checking {url}: {e}")

    return details

def extract_domain(url: str):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return None

def extract_language(html: str):
    import re
    match = re.search(r"<html[^>]*\slang=['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

# ----------------------------------------------------------------------------------
# ASYNC WRAPPERS FOR CONCURRENCY
# ----------------------------------------------------------------------------------

executor = ThreadPoolExecutor(max_workers=5)

async def async_google_search(query: str, limit: int, offset: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        executor, google_search, query, limit, offset
    )

async def async_check_site_details(url: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        executor, check_site_details, url
    )

# ----------------------------------------------------------------------------------
# BOT COMMAND HANDLERS
# ----------------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Type /cmds to see how to use this bot."
    )

async def cmd_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Commands:\n"
        "/dork <query> <count>\n"
        "Example:\n"
        '/dork intext:"shoes"+"powered by shopify"+"2025" 100\n'
        "This will dork 100 sites for that query.\n\n"
        "For Admins Only:\n"
        "/bord <message>\n"
        "Broadcast the message to all registered users.\n"
    )
    await update.message.reply_text(text)

async def cmd_dork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    just_args = raw_text[len("/dork"):].strip()
    if not just_args or " " not in just_args:
        await update.message.reply_text("Usage: /dork <query> <count>")
        return

    query_part, count_str = just_args.rsplit(" ", 1)
    query_part = query_part.strip()
    count_str = count_str.strip()

    if not count_str.isdigit():
        await update.message.reply_text("Please provide a valid integer for <count>.")
        return

    limit = int(count_str)
    if limit < 1:
        limit = 1
    elif limit > 300:
        limit = 300

    await update.message.reply_text(
        f"Searching for up to {limit} results for:\n{query_part}\nPlease wait..."
    )

    try:
        results = await async_google_search(query_part, limit, 0)
    except Exception as e:
        logger.error(f"Error scraping Google: {e}")
        await update.message.reply_text(f"Error scraping Google: {e}")
        return

    if not results:
        await update.message.reply_text("No results found or something went wrong (possible Google block?).")
        return

    details_list = []
    for url in results:
        d = await async_check_site_details(url)
        details_list.append(d)

    timestamp = int(time.time())
    filename = f"results_{timestamp}.txt"

    lines = []
    for d in details_list:
        lines.append(
            f"URL: {d['url']}\n"
            f"DNS: {d['dns']}\n"
            f"SSL: {d['ssl']}\n"
            f"Status: {d['status_code']}\n"
            f"Cloudflare: {d['cloudflare']}\n"
            f"Captcha: {d['captcha']}\n"
            f"Gateways: {d['gateways']}\n"
            f"GraphQL: {d['graphql']}\n"
            f"Language: {d['language']}\n"
            f"Front-end: {d['front_end']}\n"
            f"Back-end: {d['back_end']}\n"
            f"Design: {d['design']}\n"
            "\n"
            "⚡ PARAEL DORKER ⚡\n"
            "🌩️ BOT:@Parael1101 🌩️\n"
            "----------------------------------------\n"
        )

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)

    try:
        with open(filename, "rb") as file_data:
            doc = InputFile(file_data, filename=filename)
            await update.message.reply_document(
                document=doc,
                caption="Here are your results."
            )
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        await update.message.reply_text(f"Error sending file: {e}")

    try:
        os.remove(filename)
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {e}")

async def cmd_bord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use /bord.")
        return

    text = update.message.text.strip()
    parts = text.split(" ", maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /bord <message>")
        return

    message_to_broadcast = parts[1].strip()

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"[Broadcast]\n{message_to_broadcast}"
        )
        await update.message.reply_text("Broadcast sent to admin.")
    except Exception as e:
        logger.error(f"Could not send broadcast: {e}")
        await update.message.reply_text(f"Error sending broadcast: {e}")

# ----------------------------------------------------------------------------------
# FALLBACK HANDLER (non-command text)
# ----------------------------------------------------------------------------------

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

# ----------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------

def main():
    setup_chrome_driver()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cmds", cmd_cmds))
    app.add_handler(CommandHandler("dork", cmd_dork))
    app.add_handler(CommandHandler("bord", cmd_bord))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler))

    logger.info("Bot is starting. Press Ctrl+C to stop.")
    app.run_polling()
    logger.info("Bot has stopped.")

# ----------------------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
