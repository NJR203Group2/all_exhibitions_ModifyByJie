import csv
import traceback
import os
import mysql.connector
from datetime import datetime

print("app.py 開始執行")

# 先確認目前工作目錄
print("當前工作目錄:", os.getcwd())

# 建立 Downloads 目錄（與 app.py 同層）
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
print("CSV 將輸出到：", DOWNLOADS_DIR)

# 匯入模組
try:
    print("開始匯入模組...")
    from songshan import fetch_songshan_exhibitions
    from npm_museum import fetch_npm_exhibitions
    from moca import fetch_moca_exhibitions
    from huashan import fetch_huashan_exhibitions
    from fubon import fetch_fubon_exhibitions
    from tfam import fetch_tfam_exhibitions
    from ntnu import fetch_ntnu_exhibitions
    print("模組匯入成功")
except Exception as e:
    print("匯入模組時發生錯誤：")
    traceback.print_exc()
    input("按 Enter 結束")
    raise

# CSV 欄位
FIELDNAMES = [
    "館別",
    "展覽名稱",
    "展覽日期",
    "start_date",
    "end_date",
    "is_permanent",
    "展覽主題",
    "展覽連結",
    "展覽圖片",
    "展覽地點",
    "展覽時間",
]


def normalize(ex):
    """將各館爬回來的欄位統一成同一組 key。"""
    return {
        "館別": ex.get("museum", ""),
        "展覽名稱": ex.get("title", ""),
        "展覽日期": ex.get("date", ""),
        "start_date": ex.get("start_date", ""),
        "end_date": ex.get("end_date", ""),
        "is_permanent": ex.get("is_permanent", ""),
        "展覽主題": ex.get("topic", ""),
        "展覽連結": ex.get("url", ""),
        "展覽圖片": ex.get("image_url", ""),
        "展覽地點": ex.get("location", ""),
        "展覽時間": ex.get("time", ""),
    }


def collect_all_exhibitions():
    """呼叫各館爬蟲，收集所有展覽資訊。"""
    all_exhibitions = []

    print("抓取 松山文創園區...")
    all_exhibitions.extend(fetch_songshan_exhibitions())
    print(f"松山累積筆數：{len(all_exhibitions)}")

    print("抓取 國立故宮博物院...")
    all_exhibitions.extend(fetch_npm_exhibitions())
    print(f"故宮累積筆數：{len(all_exhibitions)}")

    print("抓取 當代藝術館...")
    all_exhibitions.extend(fetch_moca_exhibitions())
    print(f"當代累積筆數：{len(all_exhibitions)}")

    print("抓取 華山1914文創園區...")
    all_exhibitions.extend(fetch_huashan_exhibitions())
    print(f"華山累積筆數：{len(all_exhibitions)}")

    print("抓取 富邦美術館...")
    all_exhibitions.extend(fetch_fubon_exhibitions())
    print(f"富邦累積筆數：{len(all_exhibitions)}")

    print("抓取 臺北市立美術館...")
    all_exhibitions.extend(fetch_tfam_exhibitions())
    print(f"北美館累積筆數：{len(all_exhibitions)}")

    print("抓取 師大美術館...")
    all_exhibitions.extend(fetch_ntnu_exhibitions())
    print(f"師大累積筆數：{len(all_exhibitions)}")

    return all_exhibitions


def save_to_csv(base_filename, exhibitions):
    """將全部展覽寫入 CSV 到 Downloads 資料夾，加入時間戳記。"""

    # 產生時間戳記：202512072215（YYYYMMDDHHMM）
    timestamp = datetime.now().strftime("%Y%m%d%H%M")

    # 組合檔名 all_museums_exhibitions_YYYYMMDDHHMM.csv
    filename = f"{base_filename}_{timestamp}.csv"

    filepath = os.path.join(DOWNLOADS_DIR, filename)
    print(f"準備寫入 CSV：{filepath}（共 {len(exhibitions)} 筆）")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for ex in exhibitions:
            writer.writerow(normalize(ex))

    print("CSV 寫入完成")


def save_to_db(exhibitions):
    """
    將展覽資料寫入 GCP VM 上的 MariaDB：
      host=127.0.0.1, port=3307, user=test, password=123456, database=exhibition_db
    目標資料表：exhibitions_20251204
    （此資料表需事先新增 batch_id 與 created_at 欄位）
    """
    print("準備寫入 MariaDB exhibitions_20251204...")

    # 建立批次 ID 與 created_at 時間字串
    batch_id = datetime.now().strftime("%Y%m%d%H%M")       # 例如：202512072215
    created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=3307,
        user="test",
        password="123456",
        database="exhibition_db",
    )
    cursor = conn.cursor()

    sql = """
        INSERT INTO exhibitions_20251204
        (museum, title, date, start_date, end_date, is_permanent,
         topic, url, image_url, location, time,
         batch_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s)
    """

    count = 0
    for ex in exhibitions:
        n = normalize(ex)
        cursor.execute(
            sql,
            (
                n["館別"],
                n["展覽名稱"],
                n["展覽日期"],
                n["start_date"],
                n["end_date"],
                n["is_permanent"],
                n["展覽主題"],
                n["展覽連結"],
                n["展覽圖片"],
                n["展覽地點"],
                n["展覽時間"],
                batch_id,
                created_at_str,
            ),
        )
        count += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"MariaDB 寫入完成，共寫入 {count} 筆資料，batch_id = {batch_id}")


def main():
    print("進入 main()")
    try:
        exhibitions = collect_all_exhibitions()
        print(f"全部抓完，共 {len(exhibitions)} 筆")

        # 1) 寫入 CSV 到 Downloads
        save_to_csv("all_museums_exhibitions", exhibitions)

        # 2) 寫入 GCP VM 上的 MariaDB
        save_to_db(exhibitions)

        print("程式執行完畢")
    except Exception as e:
        print("main() 執行過程中發生錯誤：")
        traceback.print_exc()
        input("按 Enter 結束")
        raise


if __name__ == "__main__":
    print(f"👉 __name__ = {__name__}")
    main()
