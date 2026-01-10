import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from ib_insync.objects import AccountValue

from src.client import connect_ib
from src.constants import ACCOUNT, NOTION_ACCOUNT_SUMMARY_PAGE, NOTION_HEADERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACCOUNT_SUMMARY_PAGE = os.getenv(
    "NOTION_ACCOUNT_SUMMARY_PAGE", NOTION_ACCOUNT_SUMMARY_PAGE
)
ACCOUNT_SUMMARY_HEADING = "account summary"


def _plain_text(rich_text: List[Dict[str, object]]) -> str:
    parts = []
    for item in rich_text:
        text = item.get("plain_text")
        if text is None:
            text = item.get("text", {}).get("content", "")
        parts.append(text)
    return "".join(parts)


def fetch_page_blocks(page_id: str) -> List[Dict[str, object]]:
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    params: Dict[str, object] = {"page_size": 100}
    blocks: List[Dict[str, object]] = []

    while True:
        resp = requests.get(url, headers=NOTION_HEADERS, params=params)
        if not resp.ok:
            logger.error(
                "Error fetching page blocks: %s %s", resp.status_code, resp.text
            )
            break
        data = resp.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        params["start_cursor"] = data.get("next_cursor")
    return blocks


def find_code_block_after_heading(
    blocks: List[Dict[str, object]], heading_text: str
) -> Optional[str]:
    needle = heading_text.strip().lower()
    seen_heading = False
    for block in blocks:
        block_type = block.get("type")
        if block_type == "heading_2":
            heading = _plain_text(block.get("heading_2", {}).get("rich_text", []))
            seen_heading = heading.strip().lower() == needle
            continue
        if seen_heading and block_type == "code":
            return block.get("id")
    return None


def format_value(value: str) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def index_account_values(values: List[AccountValue]) -> Dict[str, List[AccountValue]]:
    index: Dict[str, List[AccountValue]] = {}
    for v in values:
        if v.account and v.account != ACCOUNT:
            continue
        index.setdefault(v.tag, []).append(v)
    return index


def pick_value(
    index: Dict[str, List[AccountValue]],
    tags: List[str],
    preferred_currency: str = "BASE",
) -> Optional[AccountValue]:
    for tag in tags:
        entries = index.get(tag)
        if not entries:
            continue
        for entry in entries:
            if entry.currency == preferred_currency:
                return entry
        return entries[0]
    return None


def format_account_summary(values: List[AccountValue]) -> str:
    by_tag = index_account_values(values)
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        f"Account: {ACCOUNT}",
        f"Updated: {timestamp}",
        "",
    ]
    fields = [
        (["NetLiquidation"], "NetLiquidation"),
        (["AvailableFunds"], "AvailableFunds"),
        (["BuyingPower"], "BuyingPower"),
        (["EquityWithLoanValue"], "EquityWithLoanValue"),
        (["InitMarginReq"], "InitMarginReq"),
        (["MaintMarginReq"], "MaintMarginReq"),
        (["ExcessLiquidity"], "ExcessLiquidity"),
        (
            ["TotalCashBalance", "TotalCashValue", "CashBalance", "SettledCash"],
            "CashBalance",
        ),
    ]
    for tags, label in fields:
        entry = pick_value(by_tag, tags)
        if entry and entry.value not in (None, ""):
            value = format_value(entry.value)
            currency = f" {entry.currency}" if entry.currency else ""
            lines.append(f"{label}: {value}{currency}")
        else:
            lines.append(f"{label}: N/A")
    return "\n".join(lines)


def update_code_block(block_id: str, content: str) -> bool:
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    payload = {
        "code": {
            "rich_text": [{"type": "text", "text": {"content": content}}],
            "language": "plain text",
        }
    }
    resp = requests.patch(url, headers=NOTION_HEADERS, json=payload)
    if resp.ok:
        return True
    logger.error("Error updating code block: %s %s", resp.status_code, resp.text)
    return False


def sync_account_summary(ib) -> bool:
    values = ib.accountSummary() + ib.accountValues(account=ACCOUNT)
    blocks = fetch_page_blocks(ACCOUNT_SUMMARY_PAGE)
    block_id = find_code_block_after_heading(blocks, ACCOUNT_SUMMARY_HEADING)
    if not block_id:
        logger.error(
            "Cannot find code block under heading '%s' on page %s.",
            ACCOUNT_SUMMARY_HEADING,
            ACCOUNT_SUMMARY_PAGE,
        )
        return False

    content = format_account_summary(values)
    if update_code_block(block_id, content):
        logger.info("Updated account summary code block.")
        return True
    return False


def main() -> None:
    ib = connect_ib()
    if not ib:
        logger.error("Failed to connect to Interactive Brokers.")
        return
    try:
        sync_account_summary(ib)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
