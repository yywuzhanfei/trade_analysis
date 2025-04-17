from ib_insync import IB, MarketOrder, Position
from ib_insync.objects import Position
from typing import List, Tuple
import logging
from src.constants import ACCOUNT

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
    pos.contract.exchange = "SMART"
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
        return market_value if pos.contract.secType == "STK" else market_value * 100
    except Exception as e:
        logger.error(f"获取 {pos.contract.symbol} 市场价值时出错: {e}")
        return 0.0

def get_position_margin_usage(ib: IB, pos: Position, account: str) -> dict:
    # 补全合约信息
    if not pos.contract.exchange:
        ib.qualifyContracts(pos.contract)
    
    quantity = int(pos.position)  # 持仓张数
    operation = 'BUY' if quantity > 0 else 'SELL'
    if quantity < 0:
        quantity = -quantity  # 期权合约的持仓量是负数
    # 期权合约的持仓量是负数，买入时需要取绝对值

    order = MarketOrder(operation, quantity, whatIf=True)
    order.account = account  # ← 必填，否则 Error 435

    orderStates = ib.whatIfOrder(pos.contract, order)
    if not orderStates:
        return None

    init  = float(orderStates.initMarginChange)
    maint = float(orderStates.maintMarginChange)

    return {
        'symbol': pos.contract.symbol,
        'expiry': pos.contract.lastTradeDateOrContractMonth,
        'strike': pos.contract.strike,
        'right': pos.contract.right,
        'position': pos.position,
        'total_init':  init,
        'total_maint': maint,
    }




def get_all_positions_margin_usage(ib: IB, account: str) -> List[dict]:
    result = []

    for pos in ib.positions(account):
        result.append(get_position_margin_usage(ib, pos, account))

    return result