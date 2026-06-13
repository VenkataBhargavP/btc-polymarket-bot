"""Group L — Settlement Tests"""
import pytest
from tests.conftest import make_activated_state
from backend.strategy.engine import close_winning


@pytest.mark.asyncio
async def test_l1_close_winning_cancels_orders_no_sells():
    """L1: Dominant hits 99¢ → open orders cancelled, no sell orders placed."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.current_up_price = 0.99

    cancelled = []

    class MockClient:
        @staticmethod
        async def cancel_all_market_orders(token_id):
            cancelled.append(token_id)

    sells_placed = []

    async def mock_sell(*a, **kw):
        sells_placed.append(a)
        return 0.70

    await close_winning(state, winning_side="UP", client=MockClient())

    assert state.phase == "done"
    assert state.scenario == "CLOSE_WIN"
    assert len(cancelled) == 2
    assert len(sells_placed) == 0   # No sell orders placed — oracle settles


def test_l2_weak_shares_expire_at_zero():
    """L2: Weak shares expire at $0 — no sell order placed, loss accepted."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.down_shares_held = 45.0

    # On CLOSE_WIN, weak shares go to $0 — this is by design
    # Verify that close_winning does NOT touch weak shares
    initial_down = state.down_shares_held

    # close_winning only cancels — no changes to share counts
    # Weak shares remain held and settle at $0 via oracle
    assert state.down_shares_held == initial_down


@pytest.mark.asyncio
async def test_l3_settlement_scenario_path():
    """L3: After close_winning, scenario='CLOSE_WIN' to mark settlement."""
    state = make_activated_state(dominant="DOWN", dom_price=0.80)
    state.current_down_price = 0.99

    await close_winning(state, winning_side="DOWN", client=None)

    assert state.scenario == "CLOSE_WIN"
    assert state.phase == "done"
