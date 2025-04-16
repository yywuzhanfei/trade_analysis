from ib_insync import IB
from ib_insync.objects import Position
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def get_all_positions_with_market_value(
    ib: IB, account: str
) -> List[Tuple[Position, float]]:
    positions = ib.positions(account=account)
    result = []
    for pos in positions:
        mv = getMarketValue(ib, pos)
        result.append((pos, mv))
    return result


def getMarketValue(ib: IB, pos: Position) -> float:
    try:
        bars = ib.reqHistoricalData(
            pos.contract,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 min",
            whatToShow="MIDPOINT",
            useRTH=True,
            formatDate=1,
        )
        price = bars[-1].close if bars else None
        if price is None or price <= 0:
            logger.info(
                f"未获取到 {pos.contract.symbol} 的有效价格，使用平均成本 {pos.avgCost}"
            )
            price = pos.avgCost
        market_value = pos.position * price
        return market_value
    except Exception as e:
        logger.error(f"获取 {pos.contract.symbol} 市场价值时出错: {e}")
        return 0.0
