import logging

log = logging.getLogger(__name__)


class PositionTracker:
    """
    Real-time share counting for a single event.
    Updated by OrderManager after each confirmed fill.
    Source of truth for dominant/weak share counts.
    """

    def __init__(self):
        self._positions: dict[str, float] = {"UP": 0.0, "DOWN": 0.0}
        self._cost_basis: dict[str, float] = {"UP": 0.0, "DOWN": 0.0}
        self._fills: list[dict] = []

    def record_buy(self, side: str, shares: float, price: float) -> None:
        self._positions[side] = self._positions.get(side, 0.0) + shares
        self._cost_basis[side] = self._cost_basis.get(side, 0.0) + shares * price
        self._fills.append({
            "action": "BUY", "side": side,
            "shares": shares, "price": price,
        })
        log.debug(
            "Position buy recorded",
            extra={"side": side, "shares": shares, "total": self._positions[side]},
        )

    def record_sell(self, side: str, shares: float, price: float) -> None:
        current = self._positions.get(side, 0.0)
        sold = min(shares, current)
        self._positions[side] = current - sold
        self._fills.append({
            "action": "SELL", "side": side,
            "shares": sold, "price": price,
        })
        log.debug(
            "Position sell recorded",
            extra={"side": side, "shares": sold, "remaining": self._positions[side]},
        )

    def get_shares(self, side: str) -> float:
        return self._positions.get(side, 0.0)

    def get_all_positions(self) -> dict:
        return {
            "UP": {
                "shares": self._positions.get("UP", 0.0),
                "cost_basis": round(self._cost_basis.get("UP", 0.0), 4),
            },
            "DOWN": {
                "shares": self._positions.get("DOWN", 0.0),
                "cost_basis": round(self._cost_basis.get("DOWN", 0.0), 4),
            },
        }

    def reset(self) -> None:
        self._positions = {"UP": 0.0, "DOWN": 0.0}
        self._cost_basis = {"UP": 0.0, "DOWN": 0.0}
        self._fills = []
