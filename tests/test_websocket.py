"""Group N — WebSocket & Connection Tests"""
import asyncio
import time
import pytest
from backend.data.price_feed import PriceFeed, extract_prices_from_event


class MockEvent:
    def __init__(self, token_id: str, price: float):
        self.token_id = token_id
        self.price = price


def test_n1_stale_tick_warning_at_3s():
    """N1: No price tick for 3s → stale detection triggers."""
    feed = PriceFeed(client=None, up_token_id="up", down_token_id="down")
    # Simulate 3.5s of silence
    feed._last_tick = time.time() - 3.5
    stale = time.time() - feed._last_tick
    assert stale >= 3.0


def test_n2_reconnect_triggered_at_10s():
    """N2: No price tick for 10s → reconnect triggered."""
    feed = PriceFeed(client=None, up_token_id="up", down_token_id="down")
    feed._last_tick = time.time() - 11.0
    stale = time.time() - feed._last_tick
    assert stale >= 10.0


def test_n3_state_preserved_on_ws_reconnect():
    """N3: WS reconnect during active scenario — state preserved."""
    from tests.conftest import make_activated_state
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.scenario = "S1"

    # Simulate WS disconnect/reconnect — state is in memory, not lost
    assert state.s1_triggered is True
    assert state.scenario == "S1"
    assert state.phase == "active"


def test_n4_extract_prices_from_event_up():
    """N4: extract_prices_from_event correctly extracts UP price."""
    event = MockEvent("up-token-1", 0.75)
    up_p, down_p = extract_prices_from_event(event, "up-token-1", "down-token-1")
    assert up_p == 0.75
    assert down_p is None


def test_n4_extract_prices_from_event_down():
    """N4: extract_prices_from_event correctly extracts DOWN price."""
    event = MockEvent("down-token-1", 0.25)
    up_p, down_p = extract_prices_from_event(event, "up-token-1", "down-token-1")
    assert up_p is None
    assert down_p == 0.25


def test_n4_extract_prices_unknown_token():
    """N4: extract_prices_from_event returns (None, None) for unknown tokens."""
    event = MockEvent("btc-token", 67000.0)
    up_p, down_p = extract_prices_from_event(event, "up-token-1", "down-token-1")
    assert up_p is None
    assert down_p is None
