import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
from ib_insync.objects import Position

from src.client import connect_ib
from src.constants import ACCOUNT, NOTION_HEADERS, NOTION_POSITIONS_DB
from src.position import getMarketValue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NOTION_POSITIONS_DB = os.getenv("NOTION_POSITIONS_DB", NOTION_POSITIONS_DB)


def make_position_id(pos: Position) -> str:
    contract = pos.contract
    parts = [contract.secType, contract.symbol]
    if contract.lastTradeDateOrContractMonth:
        parts.append(contract.lastTradeDateOrContractMonth)
    if contract.strike:
        parts.append(str(contract.strike))
    if contract.right:
        parts.append(contract.right)
    if contract.currency:
        parts.append(contract.currency)
    return "-".join(parts)


def fetch_existing_notion_position_pages() -> Dict[str, str]:
    url = f"https://api.notion.com/v1/databases/{NOTION_POSITIONS_DB}/query"
    payload: Dict[str, str] = {}
    results: Dict[str, str] = {}

    try:
        while True:
            resp = requests.post(url, headers=NOTION_HEADERS, json=payload).json()
            for page in resp.get("results", []):
                title = page["properties"].get("position_id", {}).get("title", [])
                if title:
                    results[title[0]["text"]["content"]] = page["id"]
            if not resp.get("has_more"):
                break
            payload["start_cursor"] = resp.get("next_cursor")
    except Exception as e:
        logger.error(f"Error fetching Notion position pages: {e}")

    return results


def build_properties(record: Dict[str, object]) -> Dict[str, object]:
    props: Dict[str, Optional[Dict[str, object]]] = {
        "position_id": {"title": [{"text": {"content": record["position_id"]}}]},
        "symbol": {"rich_text": [{"text": {"content": record["symbol"]}}]},
        "sec_type": {"select": {"name": record["sec_type"]}},
        "quantity": {"number": record["quantity"]},
        "avg_cost": {"number": record["avg_cost"]},
        "market_value": {"number": record["market_value"]},
        "updated_at": {"date": {"start": record["updated_at"]}},
    }
    return {k: v for k, v in props.items() if v is not None}


def upsert_position_to_notion(record: Dict[str, object], page_id: Optional[str]) -> bool:
    properties = build_properties(record)
    if page_id:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"properties": properties}
        method = requests.patch
    else:
        url = "https://api.notion.com/v1/pages"
        payload = {"parent": {"database_id": NOTION_POSITIONS_DB}, "properties": properties}
        method = requests.post

    try:
        response = method(url, headers=NOTION_HEADERS, json=payload)
        if response.ok:
            return True
        logger.error(
            "Error upserting position to Notion: %s %s",
            response.status_code,
            response.text,
        )
    except Exception as e:
        logger.error(f"Error upserting position to Notion: {e}")
    return False


def serialize_position(ib, pos: Position) -> Dict[str, object]:
    market_value = getMarketValue(ib, pos)
    return {
        "position_id": make_position_id(pos),
        "symbol": pos.contract.symbol,
        "sec_type": pos.contract.secType,
        "quantity": float(pos.position),
        "avg_cost": float(pos.avgCost),
        "market_value": float(market_value),
        "currency": pos.contract.currency or "",
        "expiry": pos.contract.lastTradeDateOrContractMonth or "",
        "strike": float(pos.contract.strike) if pos.contract.strike else 0,
        "right": pos.contract.right or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def sync_positions(ib) -> Dict[str, int]:
    positions = ib.positions(account=ACCOUNT)
    existing_pages = fetch_existing_notion_position_pages()
    uploaded = 0
    updated = 0

    for pos in positions:
        record = serialize_position(ib, pos)
        page_id = existing_pages.get(record["position_id"])
        if upsert_position_to_notion(record, page_id):
            if page_id:
                updated += 1
            else:
                uploaded += 1

    logger.info(f"Synced positions to Notion. Created: {uploaded}, Updated: {updated}")
    return {"created": uploaded, "updated": updated}


def main() -> None:
    ib = connect_ib()
    if not ib:
        logger.error("Failed to connect to Interactive Brokers.")
        return
    try:
        sync_positions(ib)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
