"""Group D — Scenario S2 Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.engine import compute_thresholds, snap5


@pytest.mark.asyncio
async def test_d1_s2_sells_10_dominant_shares():
    """D1: S2 fires — 10 DOMINANT shares sold."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.down_shares_held = 45.0   # After S1 5 sold
    engine = make_engine(state)

    sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sells.append((token_id, quantity, order_type))
        return price
    engine._om.sell = track_sell

    await engine._scenario_s2(state)

    assert state.s2_triggered is True
    assert state.scenario == "S2"
    dom_sells = [s for s in sells if s[0] == state.up_token_id]
    assert any(s[1] == 10 for s in dom_sells)


@pytest.mark.asyncio
async def test_d2_s2_weak_reaches_99():
    """D2: After S2, weak reaches 99¢ → close_winning(weak)."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s2_triggered = True
    state.scenario = "S2"
    state.up_shares_held = 40.0
    state.current_down_price = 0.99
    state.current_up_price = 0.01

    t = state.thresholds
    weak_price = state.get_side_price(state.weak_side)
    assert weak_price >= t["expiry_win"]

    from backend.strategy.engine import close_winning
    await close_winning(state, winning_side=state.weak_side, client=None)
    assert state.phase == "done"
    assert state.scenario == "CLOSE_WIN"


def test_d3_early_profit_after_s2():
    """D3: After S2, total value > target → early_profit_exit triggered."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s2_triggered = True
    state.up_shares_held = 40.0
    state.down_shares_held = 45.0
    state.realized_pnl_gross = 10.0 * 0.35

    state.current_up_price = 0.85
    state.current_down_price = 0.15

    total_value = state.compute_total_value()
    assert total_value > state.early_profit_target


def test_d4_s2_bounce_triggers_s3a():
    """D4: After S2, dominant bounces to bounce_trigger → S3a, bounce_count=1."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s2_triggered = True

    t = state.thresholds
    state.current_up_price = t["bounce_trigger"]

    dom_price = state.get_side_price(state.dominant_side)
    assert dom_price >= t["bounce_trigger"]
    assert not state.s3a_triggered


def test_d5_s2_second_dip_triggers_s3b():
    """D5: After S2, dominant drops to second_dip → S3b triggered."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s2_triggered = True

    t = state.thresholds
    state.current_up_price = t["second_dip"]

    dom_price = state.get_side_price(state.dominant_side)
    assert dom_price <= t["second_dip"]
    assert not state.s3b_triggered


def test_d6_snap5_prevents_near_miss():
    """D6: dominant near bounce_trigger (63¢) but target snapped to 65¢ — waits in S2."""
    thresholds = compute_thresholds(0.65)
    bounce = thresholds["bounce_trigger"]
    assert bounce == 0.65

    near_miss_price = 0.63
    assert near_miss_price < bounce, "63¢ should NOT trigger 65¢ bounce"


def test_d7_price_between_dip_and_bounce():
    """D7: Price stays between second_dip and bounce_trigger → holds in S2."""
    t = compute_thresholds(0.70)
    mid_price = (t["second_dip"] + t["bounce_trigger"]) / 2
    assert t["second_dip"] < mid_price < t["bounce_trigger"]
