import re
import time
import random
from urllib.parse import urljoin

import requests as req
from bs4 import BeautifulSoup as bs
from requests.utils import requote_uri
from requests.exceptions import ReadTimeout, RequestException
import urllib3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = req.Session()
session.verify = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
})

def safe_get(url, timeout=(10, 60), retries=3, backoff=2.0):
    """
    timeout=(connect_timeout, read_timeout)
    retries: 失敗重試次數
    """
    last_err = None
    for i in range(retries):
        try:
            # 小抖動，避免連打太快
            time.sleep(0.2 + random.random() * 0.4)
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (ReadTimeout, RequestException) as e:
            last_err = e
            wait = (backoff ** i) + random.random()
            print(f"[Huashan] request failed ({i+1}/{retries}) -> {url}\n  {repr(e)}\n  wait {wait:.1f}s")
            time.sleep(wait)
    return None


def get_driver(headless=True):
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print("⚠️ 無法啟動 Selenium driver，略過華山：", repr(e))
        return None


def parse_huashan_date(raw: str):
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    def parse_token(token: str):
        cleaned = re.sub(r"[^0-9\.]", "", token)
        m = re.match(r"^(\d{4})(\d{2})\.(\d{1,2})$", cleaned)
        if not m:
            return None
        y, mm, dd = m.groups()
        return f"{y}-{int(mm):02d}-{int(dd):02d}"

    norm = s.replace("－", "-")
    parts = re.split(r"\s*-\s*", norm, maxsplit=1)

    if len(parts) == 2:
        left, right = parts
        start = parse_token(left)
        end = parse_token(right)

        if start and end:
            return start, end, 0
        if start and not end:
            return start, None, 1
        if start:
            return start, None, 0
        return None, None, 0

    start = parse_token(norm)
    if start:
        return start, None, 1

    return None, None, 0


def fetch_huashan_exhibitions():
    base_url = "https://www.huashan1914.com"
    exh = "https://www.huashan1914.com/w/huashan1914"
    museum_name = "華山1914文化創意產業園區"

    driver = get_driver(headless=True)
    if driver is None:
        return []

    results = []
    try:
        driver.get(exh)
        wait = WebDriverWait(driver, 20)
        container = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".swiper-slide.swiper-slide-active")
            )
        )
        items = container.find_elements(By.XPATH, "./div")

        for it in items:
            ex_link = ""
            try:
                img = it.find_element(By.XPATH, "./img")
                onclick = img.get_attribute("onclick") or ""
                m = re.search(r"'(/[^']+)'", onclick)
                if m:
                    ex_link = urljoin(base_url, m.group(1))
            except Exception:
                pass

            if not ex_link.startswith(("http://", "https://")):
                continue

            # ✅ 用 safe_get + 拉長 read timeout + 失敗跳過單筆
            resp = safe_get(ex_link, timeout=(10, 60), retries=3)
            if resp is None:
                print(f"[Huashan] skip (timeout): {ex_link}")
                continue

            html = bs(resp.text, "html.parser")

            title = ""
            ex_title = html.find("div", class_="article-title page")
            if ex_title:
                title = ex_title.get_text(strip=True)

            ex_date = ""
            dates = [d.get_text(strip=True) for d in html.find_all("div", class_="card-date")]
            if dates:
                ex_date = " - ".join(dates[:2])

            start_date, end_date, is_permanent = parse_huashan_date(ex_date)

            ex_time = ""
            node = html.find("div", class_="card-time")
            if node:
                raw = node.get_text(" ", strip=True)
                if re.match(r"^\d", raw):
                    ex_time = raw

            ex_img = ""
            first_img = html.select_one("span[rel] img")
            if first_img and first_img.get("src"):
                ex_img = requote_uri(urljoin(base_url, first_img["src"]))

            ex_place = ""
            place = html.find("a", class_="openMap")
            if place:
                ex_place = place.get_text(strip=True)

            results.append({
                "museum": museum_name,
                "title": title,
                "date": ex_date,
                "start_date": start_date,
                "end_date": end_date,
                "is_permanent": is_permanent,
                "topic": "",
                "url": ex_link,
                "image_url": ex_img,
                "location": ex_place,
                "time": ex_time,
                "category": "",
                "extra": "",
            })

    finally:
        driver.quit()

    return results


# ✅ 重要：不要在 import 時執行爬蟲
if __name__ == "__main__":
    print(fetch_huashan_exhibitions())
