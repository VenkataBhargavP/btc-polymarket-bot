"""Shared pytest fixtures for all test groups. All tests run in paper mode."""
import asyncio
import time
import pytest

from backend.strategy.state import EventState
from backend.strategy.paper import PaperEngine
from backend.execution.order_manager import OrderManager
from backend.strategy.engine import StrategyEngine, snap5, compute_thresholds


def make_state(
    *,
    up_price: float = 0.50,
    down_price: float = 0.50,
    mode: str = "paper",
    start_offset: float = 0.0,
) -> EventState:
    state = EventState(
        event_id="test-event-1",
        market_condition_id="cond-1",
        up_token_id="up-token-1",
        down_token_id="down-token-1",
        start_time=time.time() - start_offset,
        mode=mode,
    )
    state.current_up_price = up_price
    state.current_down_price = down_price
    state.entry_up_price = 0.50
    state.entry_down_price = 0.50
    state.up_shares_held = 50.0
    state.down_shares_held = 50.0
    state.total_cost_basis = 50.0
    state.early_profit_target = round(50.0 * 1.005, 4)
    return state


def make_activated_state(dominant: str = "UP", dom_price: float = 0.70) -> EventState:
    state = make_state()
    state.phase = "active"
    state.activation_window = 1

    if dominant == "UP":
        state.current_up_price = dom_price
        state.current_down_price = round(1.0 - dom_price, 4)
        state.dominant_side = "UP"
        state.weak_side = "DOWN"
    else:
        state.current_down_price = dom_price
        state.current_up_price = round(1.0 - dom_price, 4)
        state.dominant_side = "DOWN"
        state.weak_side = "UP"

    state.dominant_price = dom_price
    state.weak_price = round(1.0 - dom_price, 4)
    state.activation_up_price = state.current_up_price
    state.activation_down_price = state.current_down_price
    state.thresholds = compute_thresholds(dom_price)
    return state


def make_paper_om() -> OrderManager:
    paper = PaperEngine(initial_balance=1000.0)
    return OrderManager(client=None, paper_engine=paper, paper_mode=True)


def make_engine(state: EventState | None = None) -> StrategyEngine:
    paper = PaperEngine(initial_balance=1000.0)
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)
    engine = StrategyEngine(order_manager=om, client=None, db=None, paper_engine=paper)
    if state:
        from backend.strategy.engine import register_engine
        register_engine(state, engine)
    return engine
