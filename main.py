from src.client import connect_ib
from src.position import get_all_positions_with_market_value, get_all_positions_margin_usage
from src.constants import ACCOUNT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    ib = connect_ib()
    positions_with_mv = get_all_positions_with_market_value(ib, ACCOUNT)
    for pos, mv in positions_with_mv:
        logger.info(f"合约: {pos.contract.symbol}, 市场价值: {mv:.2f}")

    data = get_all_positions_margin_usage(ib, ACCOUNT)
    for item in data:
        print(item)
    ib.disconnect()

if __name__ == "__main__":
    main()