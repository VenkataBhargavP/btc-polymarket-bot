import logging
import time

from backend.config import settings

log = logging.getLogger(__name__)


class PaperEngine:
    """
    Mirrors StrategyEngine exactly for paper trading.
    Fills are instant at the requested price — no API calls.
    Wallet is in-memory; persists to DB for session continuity.
    Switchable to live via MODE env var with zero code changes.
    """

    def __init__(self, initial_balance: float | None = None):
        self.balance = initial_balance or settings.initial_paper_balance
        self.positions: dict[str, float] = {}   # side ("UP"/"DOWN") → shares
        self.trade_log: list = []
        self._initial_balance = self.balance

    def buy(self, side: str, quantity: float, price: float) -> float:
        cost = quantity * price
        self.balance -= cost
        self.positions[side] = self.positions.get(side, 0.0) + quantity
        self.trade_log.append({
            "ts": time.time(),
            "action": "BUY",
            "side": side,
            "shares": quantity,
            "price": price,
            "total_value": cost,
        })
        log.debug(
            "Paper BUY",
            extra={"side": side, "shares": quantity, "price": price,
                   "balance": round(self.balance, 4)},
        )
        return price   # Instant fill at requested price

    def sell(self, side: str, quantity: float, price: float) -> float:
        proceeds = quantity * price
        self.balance += proceeds
        self.positions[side] = max(0.0, self.positions.get(side, 0.0) - quantity)
        self.trade_log.append({
            "ts": time.time(),
            "action": "SELL",
            "side": side,
            "shares": quantity,
            "price": price,
            "total_value": proceeds,
        })
        log.debug(
            "Paper SELL",
            extra={"side": side, "shares": quantity, "price": price,
                   "balance": round(self.balance, 4)},
        )
        return price   # Instant fill

    def reset(self, balance: float | None = None) -> None:
        self.balance = balance if balance is not None else self._initial_balance
        self.positions = {}
        self.trade_log = []
        log.info("Paper wallet reset", extra={"balance": self.balance})

    def get_position(self, side: str) -> float:
        return self.positions.get(side, 0.0)

    def wallet_summary(self) -> dict:
        return {
            "balance": round(self.balance, 4),
            "positions": dict(self.positions),
            "trade_count": len(self.trade_log),
        }
