# huashan.py（無 Selenium 版本）
import re
import time
from urllib.parse import urljoin

import requests as req
from bs4 import BeautifulSoup as bs
from requests.utils import requote_uri
from requests.exceptions import ReadTimeout, RequestException
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = req.Session()
session.verify = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})


def safe_get(url, retries=3, timeout=30):
    """
    對單一 URL 做帶重試機制的 GET 請求。
    若多次失敗，回傳 None，不中斷主程式。
    """
    for i in range(retries):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except ReadTimeout:
            print(f"[華山] 讀取超時，第 {i + 1} 次重試：{url}")
            time.sleep(2)
        except RequestException as e:
            print(f"[華山] 請求失敗，第 {i + 1} 次重試：{url}，錯誤：{e}")
            break
    print(f"[華山] 多次嘗試後仍無法取得內容，跳過此頁：{url}")
    return None


def fetch_huashan_exhibitions():
    base_url = "https://www.huashan1914.com"
    list_url = "https://www.huashan1914.com/w/huashan1914/exhibition"
    museum_name = "華山1914文創園區"

    results = []

    # 1) 先抓列表頁，找出所有展覽詳細頁連結
    print("[華山] 取得展覽列表頁...")
    list_resp = safe_get(list_url, timeout=30)
    if list_resp is None:
        print("[華山] 無法取得列表頁，直接返回空陣列")
        return results

    soup = bs(list_resp.text, "html.parser")

    detail_urls = set()
    for a in soup.select("a[href]"):
        href = a["href"]
        # 觀察華山展覽網址類型，多為 /w/huashan1914/exhibition_xxx 之類
        if "exhibition_" in href:
            full = urljoin(base_url, href)
            detail_urls.add(full)

    if not detail_urls:
        print("[華山] 在列表頁中沒有找到任何展覽連結")
        return results

    print(f"[華山] 在列表頁中找到 {len(detail_urls)} 個展覽連結")

    # 2) 逐一進入詳細頁解析
    for ex_link in sorted(detail_urls):
        try:
            resp = safe_get(ex_link, timeout=30)
            if resp is None:
                continue

            html = bs(resp.text, "html.parser")

            # 展覽名稱
            title = ""
            ex_title = html.find("div", class_="article-title page")
            if ex_title:
                title = ex_title.get_text(strip=True)

            # 展覽日期
            ex_date = ""
            dates = [d.get_text(strip=True) for d in html.find_all("div", class_="card-date")]
            if dates:
                ex_date = " - ".join(dates[:2])

            # 展覽時間
            ex_time = ""
            node = html.find("div", class_="card-time")
            if node:
                raw = node.get_text(" ", strip=True)
                if re.match(r"^\d", raw):
                    ex_time = raw

            # 展覽圖片
            ex_img = ""
            first_img = html.select_one("span[rel] img")
            if first_img and first_img.get("src"):
                ex_img = requote_uri(urljoin(base_url, first_img["src"]))

            # 展覽地點
            ex_place = ""
            place = html.find("a", class_="openMap")
            if place:
                ex_place = place.get_text(strip=True)

            results.append({
                "museum": museum_name,
                "title": title,
                "date": ex_date,
                "topic": "",
                "url": ex_link,
                "image_url": ex_img,
                "location": ex_place,
                "time": ex_time,
                "category": "",
                "extra": "",
            })

        except Exception as e:
            print("[華山] 解析單一展覽時發生錯誤，已跳過此筆。錯誤內容：", repr(e))
            continue

    return results