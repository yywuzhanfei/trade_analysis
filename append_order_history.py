from ib_insync import *
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from src.client import connect_ib
from src.constants import ACCOUNT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 配置 ---
CSV_FILE = "ib_trade_log.csv"
SHEET_NAME = "IB order history"
GOOGLE_CREDENTIALS_FILE = "ib-goog-sheet-credentials.json"

# --- 初始化连接 ---
ib = connect_ib()

# --- 加载已记录 orderId 集合 ---
existing_order_ids = set()
if os.path.exists(CSV_FILE):
    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_order_ids.add(int(row["order_id"]))

# --- 获取新成交记录 ---
new_records = []
trades = ib.trades()
print(trades)
for trade in trades:
    for fill in trade.fills:
        order_id = fill.execution.orderId
        if order_id not in existing_order_ids:
            record = {
                "symbol": trade.contract.symbol,
                "action": trade.order.action,
                "quantity": fill.execution.shares,
                "price": fill.execution.price,
                "time": fill.execution.time.strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": order_id,
                "commission": (
                    fill.commissionReport.commission if fill.commissionReport else ""
                ),
            }
            new_records.append(record)

# --- 追加写入 CSV ---
if new_records:
    write_header = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_records[0].keys())
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)
    print(f"Appended {len(new_records)} new trades to CSV.")
else:
    print("No new trades to append.")

# --- 上传到 Google Sheets ---
if new_records:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_CREDENTIALS_FILE, scope
    )
    client = gspread.authorize(creds)

    try:
        sheet = client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        print("Google Sheet not found.")
        sheet = client.create(SHEET_NAME).sheet1

    # 确保表头存在
    if sheet.row_count == 0:
        sheet.append_row(list(new_records[0].keys()))

    # 添加新记录
    for record in new_records:
        sheet.append_row(list(record.values()))
    print(f"Uploaded {len(new_records)} new trades to Google Sheets.")
else:
    print("No new trades to upload to Google Sheets.")

ib.disconnect()
