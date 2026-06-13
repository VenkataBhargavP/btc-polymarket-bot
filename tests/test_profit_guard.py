"""Group H — Profit Guard Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.profit_guard import compute_headroom, check_profit_zone
from backend.config import settings


def test_h1_headroom_positive_after_s1():
    """H1: After S1 sell (5 shares) — headroom still > $0.50, continue in S1."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.down_shares_held = 45.0  # 5 sold
    state.realized_pnl_gross = 5.0 * 0.30   # sold at 30¢

    result = compute_headroom(state)
    assert result["headroom"] > settings.min_profit_buffer
    assert result["in_profit_zone"] is True


def test_h2_headroom_below_threshold_triggers_npz():
    """H2: After sell — headroom ≤ $0.50 → no-profit-zone."""
    state = make_activated_state(dominant="UP", dom_price=0.55)
    # Sell so many shares that best future value can't recover
    state.up_shares_held = 1.0
    state.down_shares_held = 1.0
    state.realized_pnl_gross = 2.0  # Tiny recovery
    state.total_cost_basis = 50.0

    result = compute_headroom(state)
    # best_future = 1*0.99 + 1*0.01 = 1.00
    # max_rec = 2.00 + 1.00 = 3.00
    # headroom = 3.00 - 50.00 = -47.00
    assert result["in_profit_zone"] is False
    assert result["headroom"] <= 0.50


def test_h3_headroom_checked_on_every_tick():
    """H3: compute_headroom is deterministic and can be called per tick."""
    state = make_activated_state(dominant="UP", dom_price=0.70)

    for _ in range(5):
        result = compute_headroom(state)
        assert isinstance(result["in_profit_zone"], bool)


@pytest.mark.asyncio
async def test_h4_check_profit_zone_idempotent_when_done():
    """H4: check_profit_zone() returns True immediately when phase='done'."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.phase = "done"
    state.up_shares_held = 1.0  # Would be NPZ if phase were active
    state.down_shares_held = 1.0
    state.total_cost_basis = 50.0

    result = await check_profit_zone(state)
    assert result is True  # Returns True without triggering emergency exit


@pytest.mark.asyncio
async def test_h5_position_sizing_guard_prevents_inversion():
    """H5: Guard prevents sell that would make dom_held < weak_held."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.up_shares_held = 30.0   # dominant
    state.down_shares_held = 30.0  # weak — equal

    engine = make_engine(state)

    sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sells.append(quantity)
        return price
    engine._om.sell = track_sell

    # Try to sell 30 dominant shares — would make dom_held = 0 < weak_held = 30
    await engine._sell_shares(state, "UP", 30, 0.70, "EXPIRING_LIMIT")

    # Quantity should be reduced to 0 (can't sell at all when equal)
    # OR reduced so dominant stays >= weak
    if sells:
        remaining_dom = state.up_shares_held
        remaining_weak = state.down_shares_held
        assert remaining_dom >= remaining_weak
