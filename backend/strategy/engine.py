import asyncio
import logging
import time

from backend.config import settings
from backend.strategy.state import EventState
from backend.strategy.profit_guard import check_profit_zone
from backend.polymarket.models import MarketInfo

log = logging.getLogger(__name__)

MOVE_THRESHOLD_POINTS = settings.move_threshold_points   # 30
WINDOW_1_DURATION = settings.window_1_duration           # 30
ACTIVATION_TIMER = settings.activation_timer             # 210
MIN_DOMINANT_PRICE = settings.min_dominant_price         # 0.55
MIN_PROFIT_BUFFER = settings.min_profit_buffer           # 0.50
PRE_ENTRY_SECONDS = settings.pre_entry_seconds           # 30
MAX_LOSSES = settings.max_consecutive_losses             # 3


def snap5(price: float) -> float:
    """Round to nearest 5-cent level: 0.50, 0.55, 0.60, 0.65..."""
    return round(round(price / 0.05) * 0.05, 4)


def compute_thresholds(dominant_price: float) -> dict:
    """
    All levels derived from activation dominant price and snapped to 5¢.
    dominant=0.80 → reversal=0.75, bounce=0.80, second_dip=0.70, bail=0.80
    dominant=0.65 → reversal=0.60, bounce=0.65, second_dip=0.55, bail=0.65
    dominant=0.55 → reversal=0.50, bounce=0.55, second_dip=0.45, bail=0.55
    """
    weak = round(1.0 - dominant_price, 4)
    return {
        "dominant_initial": snap5(dominant_price),
        "weak_initial_sell": snap5(weak),
        "reversal_trigger": snap5(dominant_price - 0.05),   # S1 → S2
        "bounce_trigger": snap5(dominant_price),             # S2 → S3a
        "second_dip": snap5(dominant_price - 0.10),          # S2 → S3b
        "bail_trigger": snap5(dominant_price),               # S3b → S3c
        "expiry_win": 0.99,
        "expiry_lose": 0.01,
    }


class StrategyEngine:
    """
    Full scenario state machine for a single BTC 5-min event.
    Wires together order_manager, price_feed, and db.
    """

    def __init__(self, order_manager, client, db, paper_engine=None):
        self._om = order_manager
        self._client = client
        self._db = db
        self._paper = paper_engine
        self._state: EventState | None = None

        # Circuit breaker state — loaded from DB at startup
        self.consecutive_losses: int = 0
        self.bot_halted: bool = False

    @property
    def state(self) -> EventState | None:
        return self._state

    def load_circuit_breaker(self, consecutive_losses: int, bot_halted: bool):
        self.consecutive_losses = consecutive_losses
        self.bot_halted = bot_halted

    async def start_event_from_market(self, market: MarketInfo) -> None:
        if self.bot_halted:
            log.warning("Bot halted — skipping event", extra={"event_id": market.event_id})
            return

        state = EventState(
            event_id=market.event_id,
            market_condition_id=market.condition_id,
            up_token_id=market.up_token_id,
            down_token_id=market.down_token_id,
            start_time=market.start_ts,
            mode=settings.mode,
            consecutive_losses=self.consecutive_losses,
            bot_halted=self.bot_halted,
        )
        self._state = state
        register_engine(state, self)
        await self._run_event(state)

    async def _run_event(self, state: EventState) -> None:
        try:
            await self._start_event(state)
        except Exception as exc:
            log.error("Event run error", extra={"error": str(exc), "event_id": state.event_id})
            if state.phase != "done":
                await emergency_exit(state, "exception", self._om, self._client)
        finally:
            await self._close_event(state)

    async def _start_event(self, state: EventState) -> None:
        # 1. Place both MAKER limit orders simultaneously
        qty = settings.entry_quantity_shares
        up_price, down_price = await asyncio.gather(
            self._om.buy(
                token_id=state.up_token_id,
                quantity=qty,
                price=0.50,
                order_type="LIMIT",
            ),
            self._om.buy(
                token_id=state.down_token_id,
                quantity=qty,
                price=0.50,
                order_type="LIMIT",
            ),
        )

        state.entry_up_price = up_price or 0.50
        state.entry_down_price = down_price or 0.50
        state.current_up_price = state.entry_up_price
        state.current_down_price = state.entry_down_price

        # 2. Record actual cost basis
        state.total_cost_basis = (
            state.up_shares_held * state.entry_up_price
            + state.down_shares_held * state.entry_down_price
        )

        # 3. Compute dynamic profit target — strictly 0.5% of cost basis
        state.early_profit_target = round(state.total_cost_basis * 1.005, 4)

        state.phase = "waiting"

        log.info(
            "Event started",
            extra={
                "event_id": state.event_id,
                "cost_basis": state.total_cost_basis,
                "profit_target": state.early_profit_target,
            },
        )

        state.trade_log.append({
            "ts": time.time(), "action": "BUY", "side": "UP",
            "shares": 50, "price": state.entry_up_price,
            "pnl_impact": 0, "scenario": "",
        })
        state.trade_log.append({
            "ts": time.time(), "action": "BUY", "side": "DOWN",
            "shares": 50, "price": state.entry_down_price,
            "pnl_impact": 0, "scenario": "",
        })

        # 4. Run price monitor and timer concurrently
        await asyncio.gather(
            self._price_monitor(state),
            self._time_trigger(state),
            self._expiry_watchdog(state),
        )

    async def _price_monitor(self, state: EventState) -> None:
        from backend.data.price_feed import extract_prices_from_event

        async def on_event(event):
            if state.phase == "done":
                return

            up_p, down_p = extract_prices_from_event(
                event, state.up_token_id, state.down_token_id
            )
            if up_p is not None:
                state.current_up_price = up_p
            if down_p is not None:
                state.current_down_price = down_p

            if up_p is not None or down_p is not None:
                state.add_price_tick(state.current_up_price, state.current_down_price)

            elapsed = time.time() - state.start_time

            if state.phase == "waiting":
                move = abs(state.current_up_price - 0.50)
                if move >= (MOVE_THRESHOLD_POINTS / 100):
                    window = 1 if elapsed <= WINDOW_1_DURATION else 2
                    state.activation_window = window
                    await self._activate(state)

            elif state.phase == "active":
                total_value = state.compute_total_value()
                if total_value >= state.early_profit_target:
                    await early_profit_exit(state, self._om, self._client)
                    return
                if not await check_profit_zone(state):
                    return

        from backend.data.price_feed import PriceFeed
        feed = PriceFeed(self._client, state.up_token_id, state.down_token_id)
        await asyncio.gather(
            feed.stream_prices(on_event),
            feed.watchdog(),
        )

    async def _time_trigger(self, state: EventState) -> None:
        await asyncio.sleep(ACTIVATION_TIMER)
        if state.phase == "waiting":
            state.activation_window = 3
            await self._activate(state)

    async def _expiry_watchdog(self, state: EventState) -> None:
        """Emergency exit if < 30s remaining and phase is not done."""
        event_duration = 300  # 5-minute window
        while state.phase != "done":
            await asyncio.sleep(1)
            elapsed = time.time() - state.start_time
            remaining = event_duration - elapsed
            if remaining < 30 and state.phase != "done":
                log.warning(
                    "Expiry approaching",
                    extra={"remaining_s": round(remaining, 1), "event_id": state.event_id},
                )
                await emergency_exit(state, "expiry_approaching", self._om, self._client)
                return

    async def _activate(self, state: EventState) -> None:
        async with state.activation_lock:
            if state.phase != "waiting":
                return   # Already activated — lock prevents double-fire

            state.activation_up_price = state.current_up_price
            state.activation_down_price = state.current_down_price
            state.phase = "active"

        up = state.activation_up_price
        down = state.activation_down_price
        dominant_price = max(up, down)

        log.info(
            "Activated",
            extra={
                "window": state.activation_window,
                "up": up,
                "down": down,
                "dominant_price": dominant_price,
                "event_id": state.event_id,
            },
        )

        if dominant_price < MIN_DOMINANT_PRICE:
            await emergency_exit(state, "below_min_edge", self._om, self._client)
            return

        state.dominant_side = "UP" if up >= down else "DOWN"
        state.weak_side = "DOWN" if up >= down else "UP"
        state.dominant_price = dominant_price
        state.weak_price = round(1.0 - dominant_price, 4)
        state.thresholds = compute_thresholds(dominant_price)

        await self._scenario_s1(state)

    async def _scenario_s1(self, state: EventState) -> None:
        """Sell 5 WEAK shares at current weak price. Watch for expiry win or reversal."""
        t = state.thresholds
        weak = state.weak_side
        dom = state.dominant_side

        await self._sell_shares(
            state, side=weak, quantity=5,
            price=state.get_side_price(weak), order_type="EXPIRING_LIMIT",
        )
        state.s1_triggered = True
        state.scenario = "S1"

        log.info("S1 triggered", extra={"event_id": state.event_id, "weak": weak})

        if not await check_profit_zone(state):
            return

        while state.phase == "active":
            await asyncio.sleep(0.25)

            total_value = state.compute_total_value()
            if total_value >= state.early_profit_target:
                await early_profit_exit(state, self._om, self._client)
                return

            dom_price = state.get_side_price(dom)
            if dom_price >= t["expiry_win"]:
                await close_winning(state, winning_side=dom, client=self._client)
                return

            if dom_price <= t["reversal_trigger"] and not state.s2_triggered:
                await self._scenario_s2(state)
                return

            if not await check_profit_zone(state):
                return

    async def _scenario_s2(self, state: EventState) -> None:
        """Dominant dropped after S1. Sell 10 DOMINANT shares."""
        t = state.thresholds
        dom = state.dominant_side
        weak = state.weak_side

        await self._sell_shares(
            state, side=dom, quantity=10,
            price=state.get_side_price(dom), order_type="EXPIRING_LIMIT",
        )
        state.s2_triggered = True
        state.scenario = "S2"

        log.info("S2 triggered", extra={"event_id": state.event_id, "dom": dom})

        if not await check_profit_zone(state):
            return

        while state.phase == "active":
            await asyncio.sleep(0.25)

            total_value = state.compute_total_value()
            if total_value >= state.early_profit_target:
                await early_profit_exit(state, self._om, self._client)
                return

            weak_price = state.get_side_price(weak)
            if weak_price >= t["expiry_win"]:
                await close_winning(state, winning_side=weak, client=self._client)
                return

            dom_price = state.get_side_price(dom)
            if dom_price >= t["bounce_trigger"] and not state.s3a_triggered:
                state.bounce_count += 1
                await self._scenario_s3a(state)
                return

            if dom_price <= t["second_dip"] and not state.s3b_triggered:
                await self._scenario_s3b(state)
                return

            if not await check_profit_zone(state):
                return

    async def _scenario_s3a(self, state: EventState) -> None:
        """After S1+S2, dominant bounced. Sell 10 more WEAK shares."""
        t = state.thresholds
        dom = state.dominant_side
        weak = state.weak_side

        await self._sell_shares(
            state, side=weak, quantity=10,
            price=state.get_side_price(weak), order_type="EXPIRING_LIMIT",
        )
        state.s3a_triggered = True
        state.s3_direction = "dominant_recovering"
        state.scenario = "S3a"

        log.info("S3a triggered", extra={"event_id": state.event_id, "bounce_count": state.bounce_count})

        if not await check_profit_zone(state):
            return

        while state.phase == "active":
            await asyncio.sleep(0.25)

            total_value = state.compute_total_value()
            if total_value >= state.early_profit_target:
                await early_profit_exit(state, self._om, self._client)
                return

            dom_price = state.get_side_price(dom)
            if dom_price >= t["expiry_win"]:
                await close_winning(state, winning_side=dom, client=self._client)
                return

            if dom_price <= t["reversal_trigger"] and not state.s3b_triggered:
                state.bounce_count += 1
                await self._scenario_s3b(state)
                return

            if state.bounce_count >= 2 and dom_price >= t["bail_trigger"]:
                await self._scenario_s3c(state)
                return

            if not await check_profit_zone(state):
                return

    async def _scenario_s3b(self, state: EventState) -> None:
        """After S1+S2, dominant dropped again. Sell 15 DOMINANT shares."""
        t = state.thresholds
        dom = state.dominant_side
        weak = state.weak_side

        await self._sell_shares(
            state, side=dom, quantity=15,
            price=state.get_side_price(dom), order_type="EXPIRING_LIMIT",
        )
        state.s3b_triggered = True   # Own flag — never s3_triggered
        state.s3_direction = "weak_recovering"
        state.scenario = "S3b"

        log.info("S3b triggered", extra={"event_id": state.event_id})

        if not await check_profit_zone(state):
            return

        while state.phase == "active":
            await asyncio.sleep(0.25)

            total_value = state.compute_total_value()
            if total_value >= state.early_profit_target:
                await early_profit_exit(state, self._om, self._client)
                return

            weak_price = state.get_side_price(weak)
            if weak_price >= t["expiry_win"]:
                await close_winning(state, winning_side=weak, client=self._client)
                return

            dom_price = state.get_side_price(dom)
            # S3b bail check uses not s3c_triggered — never not s3_triggered
            if dom_price >= t["bail_trigger"] and not state.s3c_triggered:
                state.bounce_count += 1
                if state.bounce_count >= 2:
                    await self._scenario_s3c(state)
                    return

            if not await check_profit_zone(state):
                return

    async def _scenario_s3c(self, state: EventState) -> None:
        """Back-and-forth exhausted. Exit ALL remaining shares at market (FAK)."""
        dom = state.dominant_side
        weak = state.weak_side

        await asyncio.gather(
            self._sell_shares(
                state, side=dom,
                quantity=state.get_shares_held(dom),
                price=state.get_side_price(dom),
                order_type="MARKET_FAK",
            ),
            self._sell_shares(
                state, side=weak,
                quantity=state.get_shares_held(weak),
                price=state.get_side_price(weak),
                order_type="MARKET_FAK",
            ),
        )
        state.s3c_triggered = True
        state.scenario = "S3c"
        state.phase = "done"

        log.warning("S3c bail — exiting all", extra={"event_id": state.event_id})

    async def _sell_shares(
        self,
        state: EventState,
        side: str,
        quantity: float,
        price: float,
        order_type: str,
    ) -> None:
        """Places sell order and updates state. Guards: quantity cap + dominant>=weak."""
        dom = state.dominant_side or side
        weak = state.weak_side or ("DOWN" if side == "UP" else "UP")

        # Guard 1: cannot sell more than held
        held = state.get_shares_held(side)
        quantity = min(quantity, held)
        if quantity <= 0:
            return

        # Guard 2: winning side must hold more shares than losing after sell
        after_dom = state.up_shares_held if dom == "UP" else state.down_shares_held
        after_weak = state.up_shares_held if weak == "UP" else state.down_shares_held
        if side == dom:
            after_dom -= quantity
        else:
            after_weak -= quantity

        if after_dom < after_weak:
            other_held = state.get_shares_held(dom if side != dom else weak)
            quantity = held - other_held
            if quantity <= 0:
                return

        fill_price = await self._om.sell(
            token_id=state.get_token_id(side),
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

        if fill_price is not None:
            state.realized_pnl_gross += quantity * fill_price
            state.realized_pnl = state.realized_pnl_gross - state.total_cost_basis
            if side == "UP":
                state.up_shares_held -= quantity
                state.up_shares_sold += quantity
            else:
                state.down_shares_held -= quantity
                state.down_shares_sold += quantity

            state.trade_log.append({
                "ts": time.time(),
                "action": "SELL",
                "side": side,
                "shares": quantity,
                "price": fill_price,
                "pnl_impact": quantity * (fill_price - 0.50),
                "scenario": state.scenario,
            })

            log.info(
                "Sell filled",
                extra={
                    "side": side, "shares": quantity, "price": fill_price,
                    "scenario": state.scenario, "event_id": state.event_id,
                },
            )

    async def _close_event(self, state: EventState) -> None:
        """Persist event to DB and update circuit breaker."""
        from backend.db.store import save_event, save_trade, set_bot_state_value

        is_win = state.scenario in ("CLOSE_WIN", "EARLY_PROFIT") or state.realized_pnl > 0

        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        if self.consecutive_losses >= MAX_LOSSES:
            self.bot_halted = True
            log.warning(
                "Circuit breaker triggered",
                extra={"consecutive_losses": self.consecutive_losses},
            )

        state.consecutive_losses = self.consecutive_losses
        state.bot_halted = self.bot_halted

        if self._db:
            await save_event(self._db, state)
            for trade in state.trade_log:
                await save_trade(self._db, state.event_id, {**trade, "mode": state.mode})
            await set_bot_state_value(
                self._db, "consecutive_losses", self.consecutive_losses
            )
            await set_bot_state_value(self._db, "bot_halted", self.bot_halted)

        log.info(
            "Event closed",
            extra={
                "event_id": state.event_id,
                "scenario": state.scenario,
                "realized_pnl": state.realized_pnl,
                "consecutive_losses": self.consecutive_losses,
                "bot_halted": self.bot_halted,
            },
        )

    async def resume(self) -> None:
        """Resume after circuit breaker halt."""
        self.bot_halted = False
        self.consecutive_losses = 0
        if self._db:
            from backend.db.store import set_bot_state_value
            await set_bot_state_value(self._db, "bot_halted", False)
            await set_bot_state_value(self._db, "consecutive_losses", 0)
        log.info("Bot resumed after circuit breaker")


# ── Module-level functions (used by profit_guard and paper engine) ────────────

async def early_profit_exit(state: EventState, order_manager=None, client=None) -> None:
    """Total value crossed early_profit_target. Sell both sides simultaneously."""
    state.phase = "done"   # FIRST — prevents re-entry

    if order_manager is None:
        return

    dom = state.dominant_side or "UP"
    weak = state.weak_side or "DOWN"

    engine = _get_engine_for_state(state)
    if engine:
        await asyncio.gather(
            engine._sell_shares(
                state, side="UP",
                quantity=state.up_shares_held,
                price=state.current_up_price,
                order_type="EXPIRING_LIMIT",
            ),
            engine._sell_shares(
                state, side="DOWN",
                quantity=state.down_shares_held,
                price=state.current_down_price,
                order_type="EXPIRING_LIMIT",
            ),
        )

    state.scenario = "EARLY_PROFIT"
    log.warning("Early profit exit", extra={"event_id": state.event_id,
                                            "total_value": state.compute_total_value()})


async def close_winning(state: EventState, winning_side: str, client=None) -> None:
    """
    Dominant hit 99¢. Cancel open orders and let oracle settle.
    No sell orders placed — oracle pays $1/share.
    """
    state.phase = "done"   # FIRST

    if client:
        await client.cancel_all_market_orders(state.up_token_id)
        await client.cancel_all_market_orders(state.down_token_id)

    state.scenario = "CLOSE_WIN"
    log.info(
        "Close winning — oracle settlement",
        extra={"winning_side": winning_side, "event_id": state.event_id},
    )


async def emergency_exit(state: EventState, reason: str,
                          order_manager=None, client=None) -> None:
    """
    Triggered when: headroom <= MIN_PROFIT_BUFFER, dominant < MIN_DOMINANT_PRICE,
    or expiry < 30s. Sells all shares at market (FAK). Higher-value side first.
    """
    state.phase = "done"   # FIRST

    dom = state.dominant_side or "UP"
    weak = state.weak_side or "DOWN"
    dom_q = state.get_shares_held(dom)
    wq = state.get_shares_held(weak)
    dom_v = dom_q * state.get_side_price(dom)
    wv = wq * state.get_side_price(weak)

    if order_manager is None:
        state.scenario = "EXIT_NPZ"
        return

    engine = _get_engine_for_state(state)
    if engine:
        if dom_v >= wv:
            await engine._sell_shares(state, side=dom, quantity=dom_q, price=state.get_side_price(dom), order_type="MARKET_FAK")
            await engine._sell_shares(state, side=weak, quantity=wq, price=state.get_side_price(weak), order_type="MARKET_FAK")
        else:
            await engine._sell_shares(state, side=weak, quantity=wq, price=state.get_side_price(weak), order_type="MARKET_FAK")
            await engine._sell_shares(state, side=dom, quantity=dom_q, price=state.get_side_price(dom), order_type="MARKET_FAK")

    state.scenario = "EXIT_NPZ"
    log.warning(
        "Emergency exit",
        extra={"reason": reason, "event_id": state.event_id,
               "dom_q": dom_q, "wq": wq},
    )


# Registry so module-level functions can reach back into the engine
_engine_registry: dict = {}


def register_engine(state: EventState, engine: "StrategyEngine") -> None:
    _engine_registry[state.event_id] = engine


def _get_engine_for_state(state: EventState) -> "StrategyEngine | None":
    return _engine_registry.get(state.event_id)
