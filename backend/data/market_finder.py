import asyncio
import logging
import time

from backend.config import settings
from backend.polymarket.models import MarketInfo

log = logging.getLogger(__name__)

PRE_ENTRY_SECONDS = settings.pre_entry_seconds


class MarketFinder:
    """
    Discovers upcoming BTC 5-min markets and schedules entry at T-30s.
    Pre-loads the next event when current event has < 60s remaining.
    """

    def __init__(self, client):
        self._client = client
        self._upcoming: list = []
        self._stop: bool = False

    def stop(self):
        self._stop = True

    async def run_loop(self):
        """Background loop — refreshes market list every 30s."""
        while not self._stop:
            try:
                self._upcoming = await self._client.find_btc_5min_markets()
                log.debug("MarketFinder refreshed", extra={"count": len(self._upcoming)})
            except Exception as exc:
                log.error("MarketFinder refresh failed", extra={"error": str(exc)})
            await asyncio.sleep(30)

    def get_next_market(self) -> MarketInfo | None:
        now = time.time()
        for market in self._upcoming:
            try:
                start_ts = (
                    market.state.start_date.timestamp()
                    if market.state.start_date
                    else 0
                )
            except AttributeError:
                start_ts = 0

            if start_ts > now:
                try:
                    up_token = str(market.outcomes.yes.token_id)
                    down_token = str(market.outcomes.no.token_id)
                except AttributeError:
                    continue
                return MarketInfo(
                    event_id=str(market.id),
                    condition_id=str(market.condition_id),
                    up_token_id=up_token,
                    down_token_id=down_token,
                    start_ts=start_ts,
                    seconds_until=start_ts - now,
                    slug=market.slug or "",
                )
        return None

    async def wait_and_enter(self, engine) -> None:
        """
        Continuously waits for the next market window.
        Fires entry at T-30s if balance >= $50 and bot not halted.
        Waits one full 5-min cycle (300s) before re-checking after entry.
        """
        while not self._stop:
            next_mkt = self.get_next_market()
            if next_mkt and next_mkt.seconds_until <= PRE_ENTRY_SECONDS:
                try:
                    balance = float(await self._client.get_wallet_balance())
                except Exception:
                    balance = 0.0

                bot_halted = getattr(engine, "bot_halted", False)
                if bot_halted:
                    log.warning(
                        "Circuit breaker active — skipping window",
                        extra={"event_id": next_mkt.event_id},
                    )
                elif balance >= 50.0:
                    log.info(
                        "Entering market",
                        extra={"event_id": next_mkt.event_id,
                               "balance": balance,
                               "seconds_until": round(next_mkt.seconds_until, 1)},
                    )
                    await engine.start_event_from_market(next_mkt)
                else:
                    log.warning(
                        "Insufficient balance — skipping window",
                        extra={"balance": balance, "event_id": next_mkt.event_id},
                    )
                await asyncio.sleep(300)
            else:
                await asyncio.sleep(1)
