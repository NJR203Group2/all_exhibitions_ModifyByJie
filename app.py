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
    """呼叫各館爬蟲，收集所有展覽資訊（單館失敗不影響整體）。"""
    all_exhibitions = []

    def run(museum_name, fn):
        try:
            print(f"抓取 {museum_name}...")
            data = fn() or []
            all_exhibitions.extend(data)
            print(f"{museum_name} 完成，本次 {len(data)} 筆，累積 {len(all_exhibitions)} 筆")
        except Exception:
            print(f"{museum_name} 抓取失敗，跳過，繼續下一館")
            traceback.print_exc()

    run("松山文創園區", fetch_songshan_exhibitions)
    run("國立故宮博物院", fetch_npm_exhibitions)
    run("當代藝術館", fetch_moca_exhibitions)
    run("華山1914文創園區", fetch_huashan_exhibitions)
    run("富邦美術館", fetch_fubon_exhibitions)
    run("臺北市立美術館", fetch_tfam_exhibitions)
    run("師大美術館", fetch_ntnu_exhibitions)

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
    print("準備寫入 MariaDB exhibitions_20251204...")

    batch_id = datetime.now().strftime("%Y%m%d%H%M")
    created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 讓你確定程式真的有進入 DB 區塊
    print(f"[DB] batch_id={batch_id}, rows={len(exhibitions)}")

    try:
        print("[DB] connect() -> 127.0.0.1:3307 ...")
        conn = mysql.connector.connect(
            host="127.0.0.1",
            port=3307,
            user="test",
            password="123456",
            database="exhibition_db",
            connection_timeout=5,          # 超重要：避免卡住
            ssl_disabled=True,   # 關鍵
            use_pure=True,       # 關鍵
            autocommit=False,
        )
        print("[DB] connect OK")

        cursor = conn.cursor()

        # 確認真的連到你要的 DB
        cursor.execute("SELECT DATABASE(), USER(), VERSION();")
        db_name, user_name, ver = cursor.fetchone()
        print(f"[DB] DATABASE()={db_name} USER()={user_name} VERSION()={ver}")

        sql = """
            INSERT INTO exhibitions_20251204
            (museum, title, date, start_date, end_date, is_permanent,
             topic, url, image_url, location, time,
             batch_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # 用 executemany，一次送，速度快、也比較不容易看起來卡住
        rows = []
        for ex in exhibitions:
            n = normalize(ex)
            rows.append((
                n["館別"] or None,
                n["展覽名稱"] or None,
                n["展覽日期"] or None,
                n["start_date"] or None,
                n["end_date"] or None,
                str(n["is_permanent"]) if n["is_permanent"] != "" else None,
                n["展覽主題"] or None,
                n["展覽連結"] or None,
                n["展覽圖片"] or None,
                n["展覽地點"] or None,
                n["展覽時間"] or None,
                batch_id,
                created_at_str,
            ))

        print("[DB] executemany() ...")
        cursor.executemany(sql, rows)
        print(f"[DB] executemany OK, rowcount(last batch)={cursor.rowcount}")

        print("[DB] commit() ...")
        conn.commit()
        print("[DB] commit OK")

        cursor.close()
        conn.close()

        print(f"MariaDB 寫入完成，共寫入 {len(rows)} 筆資料，batch_id = {batch_id}")

    except Exception:
        print("[DB] 寫入失敗，traceback：")
        traceback.print_exc()
        raise


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
    print(f"__name__ = {__name__}")
    main()
