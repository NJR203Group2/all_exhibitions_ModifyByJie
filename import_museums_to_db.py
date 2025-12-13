import csv
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Downloads",
    "taipei_museums_info.csv"
)

conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3307,
    user="test",
    password="123456",
    database="exhibition_db",
    ssl_disabled=True,
    use_pure=True,
)

cursor = conn.cursor()

sql = """
INSERT INTO museums
(place_id, name, address, latitude, longitude,
 website, phone, rating, opening_hours)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    address = VALUES(address),
    latitude = VALUES(latitude),
    longitude = VALUES(longitude),
    website = VALUES(website),
    phone = VALUES(phone),
    rating = VALUES(rating),
    opening_hours = VALUES(opening_hours)
"""

rows = []

with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append((
            r["place_id"],
            r["館名"],
            r["地址"],
            r["緯度"] or None,
            r["經度"] or None,
            r["網站"],
            r["電話"],
            r["評分"] or None,
            r["營業時間"],
        ))

print(f"準備寫入 museums：{len(rows)} 筆")

cursor.executemany(sql, rows)
conn.commit()

cursor.close()
conn.close()

print("museums 資料表寫入完成")
