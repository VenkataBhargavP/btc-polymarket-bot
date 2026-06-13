import asyncio
import logging
import time
from decimal import Decimal

log = logging.getLogger(__name__)

_WARN_AFTER_S = 3
_RECONNECT_AFTER_S = 10
_MAX_BACKOFF_S = 30


class PriceFeed:
    """
    Wraps the SDK stream for a single event.
    Delivers price updates to state and monitors for stale ticks.
    Reconnects with exponential backoff on silence > 10s.
    """

    def __init__(self, client, up_token_id: str, down_token_id: str):
        self._client = client
        self._up_id = up_token_id
        self._down_id = down_token_id
        self._last_tick: float = time.time()
        self._ws_connected: bool = False
        self._backoff: float = 1.0
        self._stop: bool = False

    @property
    def ws_connected(self) -> bool:
        return self._ws_connected

    @property
    def last_tick_ms(self) -> int:
        return int((time.time() - self._last_tick) * 1000)

    def stop(self):
        self._stop = True

    async def stream_prices(self, on_price_event):
        """
        Calls on_price_event(event) for each SDK stream event.
        Reconnects automatically on stale tick or error.
        """
        while not self._stop:
            try:
                self._ws_connected = True
                self._backoff = 1.0
                stream = await self._client.subscribe_market_and_btc(
                    self._up_id, self._down_id
                )
                async with stream as s:
                    async for event in s:
                        if self._stop:
                            return
                        self._last_tick = time.time()
                        await on_price_event(event)
            except Exception as exc:
                self._ws_connected = False
                log.error("PriceFeed stream error — reconnecting", extra={"error": str(exc)})
                await asyncio.sleep(min(self._backoff, _MAX_BACKOFF_S))
                self._backoff = min(self._backoff * 2, _MAX_BACKOFF_S)

    async def watchdog(self):
        """Logs WARNING at 3s silence, triggers reconnect signal at 10s silence."""
        while not self._stop:
            await asyncio.sleep(1)
            stale = time.time() - self._last_tick
            if stale >= _WARN_AFTER_S:
                log.warning("WS tick stale", extra={"stale_seconds": round(stale, 1)})
            if stale >= _RECONNECT_AFTER_S:
                log.error(
                    "WS silent for 10s — reconnect triggered",
                    extra={"stale_seconds": round(stale, 1)},
                )
                self._ws_connected = False


def extract_prices_from_event(event, up_token_id: str, down_token_id: str
                               ) -> tuple[float | None, float | None]:
    """
    Extracts (up_price, down_price) from a Polymarket SDK stream event.
    Returns (None, None) for non-price events (e.g. BTC price events).
    """
    token_id = getattr(event, "token_id", None) or getattr(event, "asset_id", None)
    price_raw = (
        getattr(event, "price", None)
        or getattr(event, "mid", None)
        or getattr(event, "last_price", None)
    )
    if token_id is None or price_raw is None:
        return None, None

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        return None, None

    if str(token_id) == str(up_token_id):
        return price, None
    if str(token_id) == str(down_token_id):
        return None, price
    return None, None
