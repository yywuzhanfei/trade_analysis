from src.client import connect_ib
from src.constants import NOTION_DB, NOTION_HEADERS
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def fetch_existing_notion_order_ids():
    """Fetch existing order IDs from Notion."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DB}/query"
    order_ids = set()
    payload = {}

    try:
        while True:
            resp = requests.post(url, headers=NOTION_HEADERS, json=payload).json()
            for page in resp.get("results", []):
                title = page["properties"].get("trade_id", {}).get("title", [])
                if title:
                    order_ids.add(title[0]["text"]["content"])
            if not resp.get("has_more"):
                break
            payload["start_cursor"] = resp.get("next_cursor")
    except Exception as e:
        logger.error(f"Error fetching Notion order IDs: {e}")

    return order_ids

def push_trade_to_notion(record):
    """Push a single trade record to Notion."""
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DB},
        "properties": {
            "trade_id": {"title": [{"text": {"content": str(record["order_id"])}}]},
            "date": {"date": {"start": record["time"]}},
            "symbol": {"rich_text": [{"text": {"content": record["symbol"]}}]},
            "side": {"select": {"name": record["action"]}},
            "quantity": {"number": float(record["quantity"])},
            "price": {"number": float(record["price"])},
            "commission": {"number": float(record.get("commission", 0))},
        },
    }

    try:
        response = requests.post(url, headers=NOTION_HEADERS, json=payload)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error pushing trade to Notion: {e}")


def fetch_new_ib_trades(ib):
    """Fetch new trades from Interactive Brokers and aggregate fills."""
    aggregated_records = {}
    try:
        trades = ib.trades()
        for trade in trades:
            if trade.contract.secType != "STK":
                continue
            for fill in trade.fills:
                key = (trade.contract.symbol, trade.order.action)  # Aggregate by symbol and action
                if key not in aggregated_records:
                    aggregated_records[key] = {
                        "symbol": trade.contract.symbol,
                        "action": trade.order.action,
                        "quantity": 0,
                        "price": 0,
                        "time": fill.execution.time.strftime("%Y-%m-%d %H:%M:%S"),
                        "order_id": fill.execution.execId,  # Use the first fill's order_id
                        "commission": 0,
                    }
                # Update aggregated values
                aggregated_records[key]["quantity"] += fill.execution.shares
                aggregated_records[key]["price"] += fill.execution.price * fill.execution.shares
                aggregated_records[key]["commission"] += fill.commissionReport.commission if fill.commissionReport else 0

        # Calculate average price for each aggregated record
        for record in aggregated_records.values():
            record["price"] /= record["quantity"]

    except Exception as e:
        logger.error(f"Error fetching IB trades: {e}")

    return list(aggregated_records.values())

def main():
    """Main function to synchronize trades."""
    # Initialize IB connection
    ib = connect_ib()
    if not ib:
        logger.error("Failed to connect to Interactive Brokers.")
        return

    # Fetch new trades
    new_records = fetch_new_ib_trades(ib)

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

if __name__ == "__main__":
    main()
