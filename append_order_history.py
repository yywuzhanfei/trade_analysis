from ib_insync import *
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from src.client import connect_ib
from src.constants import ACCOUNT
import logging
import requests
from src.constants import NOTION_TOKEN, NOTION_DB, NOTION_HEADERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_existing_notion_order_ids():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB}/query"
    order_ids = set()

    payload = {}
    while True:
        resp = requests.post(url, headers=NOTION_HEADERS, json=payload).json()
        for page in resp["results"]:
            title = page["properties"]["trade_id"]["title"]
            if title:
                order_ids.add(title[0]["text"]["content"])
        if not resp.get("has_more"):
            break
        payload["start_cursor"] = resp["next_cursor"]

    return order_ids

def push_trade_to_notion(record):
    payload = {
        "parent": {"database_id": NOTION_DB},
        "properties": {
            "trade_id": {
                "title": [
                    {"text": {"content": str(record["order_id"])}}
                ]
            },
            "date": {
                "date": {"start": record["time"]}
            },
            "symbol": {
                "rich_text": [
                    {"text": {"content": record["symbol"]}}
                ]
            },
            "side": {
                "select": {"name": record["action"]}
            },
            "quantity": {
                "number": float(record["quantity"])
            },
            "price": {
                "number": float(record["price"])
            },
            "commission": {
                "number": float(record["commission"] or 0)
            },
        },
    }

    requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json=payload,
    )


# --- 初始化连接 ---
ib = connect_ib()

# --- 获取新成交记录 ---
new_records = []
trades = ib.trades()
for trade in trades:
    if trade.contract.secType != "STK":
        continue
    for fill in trade.fills:
        order_id = fill.execution.execId
        print(fill)
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

# --- 同步到 Notion ---
if new_records:
    notion_existing_ids = fetch_existing_notion_order_ids()

    uploaded = 0
    for record in new_records:
        if str(record["order_id"]) not in notion_existing_ids:
            push_trade_to_notion(record)
            uploaded += 1

    logger.info(f"Uploaded {uploaded} new trades to Notion.")
else:
    logger.info("No new trades to upload to Notion.")

ib.disconnect()
