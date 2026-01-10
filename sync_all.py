import logging

from append_order_history import sync_order_history
from src.client import connect_ib
from sync_account_summary_to_notion import sync_account_summary
from sync_positions_to_notion import sync_positions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    ib = connect_ib()
    if not ib:
        logger.error("Failed to connect to Interactive Brokers.")
        return
    try:
        for name, func in (
            ("account summary", sync_account_summary),
            ("positions", sync_positions),
            ("order history", sync_order_history),
        ):
            try:
                logger.info("Syncing %s...", name)
                func(ib)
            except Exception as e:
                logger.error("Failed syncing %s: %s", name, e)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
