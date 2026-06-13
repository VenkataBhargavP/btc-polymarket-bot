import asyncio
import logging
import time

log = logging.getLogger(__name__)

_ORDER_LATENCY_MS: list[float] = []


class OrderManager:
    """
    Unified buy/sell dispatcher with paper mode and live mode.
    Paper mode: instant fill at requested price, no API calls.
    Live mode: retry 3 times with 500ms exponential backoff.
    """

    def __init__(self, client=None, paper_engine=None, paper_mode: bool = True):
        self._client = client
        self._paper = paper_engine
        self._paper_mode = paper_mode
        self._open_orders: dict[str, str] = {}   # order_id → side

    @property
    def paper_mode(self) -> bool:
        return self._paper_mode

    def set_mode(self, paper: bool) -> None:
        self._paper_mode = paper

    def get_avg_latency_ms(self) -> float:
        if not _ORDER_LATENCY_MS:
            return 0.0
        recent = _ORDER_LATENCY_MS[-20:]
        return round(sum(recent) / len(recent), 1)

    async def buy(
        self,
        token_id: str,
        quantity: float,
        price: float,
        order_type: str = "LIMIT",
    ) -> float | None:
        if self._paper_mode:
            if self._paper:
                side = "UP" if "up" in token_id.lower() else "DOWN"
                self._paper.buy(side, quantity, price)
            return price   # Instant fill in paper mode

        t0 = time.time()
        for attempt in range(3):
            try:
                order_id = await self._client.place_limit_buy(
                    token_id=token_id,
                    price=str(price),
                    size=str(int(quantity)),
                )
                if order_id:
                    self._open_orders[order_id] = "BUY"
                    _ORDER_LATENCY_MS.append((time.time() - t0) * 1000)
                    if len(_ORDER_LATENCY_MS) > 100:
                        _ORDER_LATENCY_MS.pop(0)
                    return price
                log.warning(
                    "Buy order returned None",
                    extra={"attempt": attempt + 1, "token_id": token_id},
                )
            except Exception as exc:
                log.error(
                    "Buy order error",
                    extra={"attempt": attempt + 1, "error": str(exc), "token_id": token_id},
                )
            await asyncio.sleep(0.5 * (2 ** attempt))

        log.error("Buy failed after 3 attempts", extra={"token_id": token_id})
        return None

    async def sell(
        self,
        token_id: str,
        quantity: float,
        price: float,
        order_type: str = "EXPIRING_LIMIT",
    ) -> float | None:
        if self._paper_mode:
            if self._paper:
                side = "UP" if "up" in token_id.lower() else "DOWN"
                self._paper.sell(side, quantity, price)
            return price

        t0 = time.time()
        order_id: str | None = None

        for attempt in range(3):
            try:
                if order_type == "MARKET_FAK":
                    order_id = await self._client.place_market_sell_fak(
                        token_id=token_id,
                        shares=str(int(quantity)),
                    )
                else:
                    order_id = await self._client.place_limit_sell(
                        token_id=token_id,
                        price=str(price),
                        size=str(int(quantity)),
                        expiration_seconds=10,
                    )

                if order_id:
                    self._open_orders[order_id] = "SELL"
                    _ORDER_LATENCY_MS.append((time.time() - t0) * 1000)
                    if len(_ORDER_LATENCY_MS) > 100:
                        _ORDER_LATENCY_MS.pop(0)
                    return price
                log.warning(
                    "Sell order returned None",
                    extra={"attempt": attempt + 1, "order_type": order_type},
                )
            except Exception as exc:
                log.error(
                    "Sell order error",
                    extra={"attempt": attempt + 1, "error": str(exc),
                           "order_type": order_type},
                )
            await asyncio.sleep(0.5 * (2 ** attempt))

        log.error(
            "Sell failed after 3 attempts",
            extra={"token_id": token_id, "order_type": order_type},
        )
        return None

    async def cancel_all(self, token_id: str) -> None:
        if self._paper_mode:
            return
        if self._client:
            await self._client.cancel_all_market_orders(token_id)
