import requests
import json
import pandas as pd
import os

API_KEY = ""  # 請替換成你的 Google Places API Key
BASE_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.types",
    "places.websiteUri",
    "places.internationalPhoneNumber",
    "places.rating",
    "places.regularOpeningHours.weekdayDescriptions"
])

HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": FIELD_MASK,
}

# 建立 Downloads 目錄（與檔案同層）
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
print("CSV 將輸出到：", DOWNLOADS_DIR)

KEYWORDS = [
    "台北市 博物館", "台北市 美術館",
    "museum in Taipei City", "art museum Taipei",
    "新北市 博物館", "新北市 美術館",
    "museum in New Taipei City", "art museum New Taipei",
]

EXTRA_QUERIES = [
    "華山1914文化創意產業園區",
    "松山文創園區",
]

KEEP_PARK_IDS = {
    "ChIJbSTgI2WpQjQRcVwWB2cnyfE",
    "ChIJO0vOI7-rQjQR3Pl9_4cPK8g",
}

MUSEUM_TYPES = {"museum", "art_gallery"}

def search_text_all_pages(text_query):
    all_places = []
    page_token = None

    while True:
        body = {
            "textQuery": text_query,
            "languageCode": "zh-TW",
            "pageSize": 20,
        }
        if page_token:
            body["pageToken"] = page_token

        resp = requests.post(BASE_URL, headers=HEADERS, json=body)
        print(f"[searchText] {text_query} -> {resp.status_code}")
        data = resp.json()

        if "error" in data:
            print("API 錯誤：", data["error"].get("message"))
            break

        places = data.get("places", [])
        all_places.extend(places)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_places

def is_museum_like(place):
    types = set(place.get("types", []) or [])
    return bool(types & MUSEUM_TYPES)

def extract_row(place):
    pid = place.get("id")
    name = place.get("displayName", {}).get("text")
    addr = place.get("formattedAddress")
    loc = place.get("location", {}) or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    website = place.get("websiteUri")
    phone = place.get("internationalPhoneNumber")
    rating = place.get("rating")
    opening_list = place.get("regularOpeningHours", {}).get("weekdayDescriptions", [])

    opening_str = "|".join(opening_list) if opening_list else None

    return {
        "place_id": pid,
        "館名": name,
        "地址": addr,
        "緯度": lat,
        "經度": lng,
        "網站": website,
        "電話": phone,
        "評分": rating,
        "營業時間": opening_str,
    }

def main():
    all_places_by_id = {}

    # 1. 雙北博物館、美術館
    for kw in KEYWORDS:
        places = search_text_all_pages(kw)
        for p in places:
            pid = p.get("id")
            if pid:
                all_places_by_id[pid] = p

    # 2. 補抓華山、松菸
    for q in EXTRA_QUERIES:
        places = search_text_all_pages(q)
        for p in places:
            pid = p.get("id")
            if pid:
                all_places_by_id[pid] = p

    print("抓到(去重後) place 數量：", len(all_places_by_id))

    selected_places = []
    for p in all_places_by_id.values():
        if is_museum_like(p) or p.get("id") in KEEP_PARK_IDS:
            selected_places.append(p)

    print("保留 place 數量：", len(selected_places))

    rows = [extract_row(p) for p in selected_places]
    df = pd.DataFrame(rows)

    output_path = os.path.join(DOWNLOADS_DIR, "taipei_museums_info.csv")
    df.to_csv(output_path, encoding="utf-8-sig", index=False)

    print("已輸出：", output_path)

if __name__ == "__main__":
    main()
