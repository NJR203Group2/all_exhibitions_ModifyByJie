# tfam.py（無 Selenium 版本）
import re
from urllib.parse import urljoin

import requests as req
from bs4 import BeautifulSoup as bs
import urllib3
from requests.exceptions import RequestException, ReadTimeout

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = req.Session()
session.verify = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})


def safe_get(url, retries=3, timeout=20, tag="[北美館]"):
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except ReadTimeout:
            print(f"{tag} 讀取超時，第 {i + 1} 次重試：{url}")
        except RequestException as e:
            print(f"{tag} 請求失敗，第 {i + 1} 次重試：{url}，錯誤：{e}")
            break
    print(f"{tag} 多次嘗試後仍無法取得內容，跳過：{url}")
    return None


def fetch_tfam_exhibitions():
    BASE = "https://www.tfam.museum/"
    HOME = "https://www.tfam.museum/index.aspx?ddlLang=zh-tw"
    EXH = "https://www.tfam.museum/Exhibition/Exhibition.aspx?ddlLang=zh-tw"

    # 抓館名
    museum_name = "臺北市立美術館"
    r_home = safe_get(HOME, tag="[北美館 HOME]")
    if r_home is not None:
        html_home = bs(r_home.text, "html.parser")
        tfam = html_home.find("div", class_="footer-info-container")
        if tfam:
            tfam_text = tfam.get_text(" ", strip=True)
            m = re.search(r"臺北市立美術館", tfam_text)
            if m:
                museum_name = m.group()

    results = []

    # 1) 取得展覽列表頁
    print("[北美館] 取得展覽列表頁...")
    r_exh = safe_get(EXH, tag="[北美館 EXH]")
    if r_exh is None:
        print("[北美館] 無法取得列表頁，返回空陣列")
        return results

    soup_list = bs(r_exh.text, "html.parser")

    # 2) 從列表頁找出所有詳細頁連結
    detail_urls = set()
    for a in soup_list.select("a[href]"):
        href = a["href"]
        if "Exhibition_Special.aspx" in href and "id=" in href:
            full = urljoin(BASE, href)
            detail_urls.add(full)

    if not detail_urls:
        print("[北美館] 列表頁中沒有找到任何 Exhibition_Special.aspx 連結")
        return results

    print(f"[北美館] 在列表頁中找到 {len(detail_urls)} 個展覽連結")

    # 3) 逐一進入詳細頁解析
    for ex_link in sorted(detail_urls):
        try:
            r_detail = safe_get(ex_link, tag="[北美館 詳細頁]")
            if r_detail is None:
                continue

            html = bs(r_detail.text, "html.parser")

            # 標題
            title = ""
            node_title = html.find("span", id="CPContent_lbExName")
            if node_title:
                title = node_title.get_text(strip=True)
            else:
                # 退而求其次抓 <title> 裡的內容
                if html.title and html.title.string:
                    title = html.title.string.strip()

            # 日期（官方通常會把起迄日都放這裡）
            ex_date = ""
            node_date = html.find("span", id="CPContent_lbDate")
            if node_date:
                ex_date = node_date.get_text(" ", strip=True)

            # 地點：比較保守的做法，用關鍵字「地點」去抓
            ex_place = ""
            for p in html.find_all(["p", "span", "div"]):
                txt = p.get_text(" ", strip=True)
                if "地點" in txt:
                    # 嘗試切掉「地點：」前綴
                    if "：" in txt:
                        ex_place = txt.split("：", 1)[1].strip()
                    elif ":" in txt:
                        ex_place = txt.split(":", 1)[1].strip()
                    else:
                        ex_place = txt.strip()
                    if ex_place:
                        break

            # 圖片：先嘗試找特定 id，再退而求其次找第一張較大的圖片
            ex_img = ""
            img = html.find("img", id="CPContent_imgEx")
            if not img:
                # 再試試其他 img
                candidates = html.find_all("img")
                if candidates:
                    img = candidates[0]
            if img and img.get("src"):
                ex_img = urljoin(BASE, img["src"])

            # 時間：北美館原本列表頁是把日期+時間混在一起
            # 如果需要更精確時間，可以再補強解析邏輯
            ex_time = ex_date

            if any([title, ex_date, ex_place, ex_img, ex_link]):
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
            print("[北美館] 解析單一展覽時發生錯誤，已跳過此筆。錯誤內容：", repr(e))
            continue

    return results