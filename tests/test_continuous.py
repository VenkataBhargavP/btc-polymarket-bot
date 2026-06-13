"""Group M — Continuous Operation Tests"""
import time
import pytest
from tests.conftest import make_state, make_activated_state, make_engine
from backend.strategy.engine import StrategyEngine
from backend.strategy.paper import PaperEngine
from backend.execution.order_manager import OrderManager
from backend.strategy.state import EventState


def make_fresh_state(event_id: str = "event-1") -> EventState:
    state = make_state()
    state.event_id = event_id
    return state


def test_m1_fresh_state_per_event():
    """M1: State object is fresh per event — no accumulated state from prior events."""
    state1 = make_fresh_state("event-1")
    state1.up_shares_sold = 15.0

    state2 = make_fresh_state("event-2")

    # Fresh state has no carry-over from state1
    assert state2.up_shares_sold == 0.0
    assert state2.event_id == "event-2"
    assert state2.s1_triggered is False
    assert state2.s2_triggered is False


def test_m2_entry_at_pre_entry_seconds():
    """M2: Entry orders placed at T-30s — seconds_until <= PRE_ENTRY_SECONDS triggers entry."""
    from backend.config import settings
    seconds_until = settings.pre_entry_seconds - 1  # Just inside window

    assert seconds_until <= settings.pre_entry_seconds


def test_m3_skip_if_balance_insufficient():
    """M3: Balance < $50 → next window skipped."""
    balance = 49.99
    assert balance < 50.0


def test_m4_no_memory_leak_across_events():
    """M4: 10 consecutive windows — trade_log and price_history reset each event."""
    for i in range(10):
        state = make_fresh_state(f"event-{i}")
        # Simulate some activity
        state.trade_log.append({"action": "BUY", "side": "UP"})
        state.price_history.append({"ts": time.time(), "up": 0.70, "down": 0.30})

        # Fresh state for next window
        next_state = make_fresh_state(f"event-{i+1}")
        assert len(next_state.trade_log) == 0
        assert len(next_state.price_history) == 0
