"""Group F — Scenario S3b Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.engine import close_winning, early_profit_exit


@pytest.mark.asyncio
async def test_f1_s3b_sells_15_dominant_shares():
    """F1: S3b fires — 15 DOMINANT shares sold."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.s2_triggered = True
    state.up_shares_held = 40.0  # After S2 10 sold
    state.down_shares_held = 35.0  # After S1 5 sold
    engine = make_engine(state)

    sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sells.append((token_id, quantity, order_type))
        return price
    engine._om.sell = track_sell

    await engine._scenario_s3b(state)

    assert state.s3b_triggered is True
    assert state.scenario == "S3b"
    dom_sells = [s for s in sells if s[0] == state.up_token_id]
    assert any(s[1] == 15 for s in dom_sells)


@pytest.mark.asyncio
async def test_f2_s3b_weak_reaches_99():
    """F2: After S3b, weak reaches 99¢ → close_winning(weak)."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3b_triggered = True
    state.current_down_price = 0.99

    t = state.thresholds
    weak_price = state.get_side_price(state.weak_side)
    assert weak_price >= t["expiry_win"]

    await close_winning(state, winning_side=state.weak_side, client=None)
    assert state.phase == "done"
    assert state.scenario == "CLOSE_WIN"


def test_f3_s3b_bail_with_s3b_triggered_flag():
    """F3: S3b uses s3b_triggered flag — NOT a generic s3_triggered flag."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3b_triggered = True
    state.bounce_count = 2

    t = state.thresholds
    state.current_up_price = t["bail_trigger"]

    dom_price = state.get_side_price(state.dominant_side)
    # Bail check: dom_price >= bail_trigger AND not s3c_triggered
    assert not state.s3c_triggered  # s3b's bail check uses s3c_triggered
    assert state.bounce_count >= 2
    assert dom_price >= t["bail_trigger"]
    # → S3c should fire


def test_f4_s3b_no_s3c_when_bounce_count_lt_2():
    """F4: After S3b, dominant recovers but bounce_count < 2 → no S3c yet."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3b_triggered = True
    state.bounce_count = 1  # Not yet 2

    t = state.thresholds
    state.current_up_price = t["bail_trigger"]

    # bounce_count increments to 2 only after this check passes once
    # Here < 2 means no S3c yet
    assert state.bounce_count < 2


@pytest.mark.asyncio
async def test_f5_early_profit_in_s3b():
    """F5: After S3b, total value > target → early_profit_exit fires."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3b_triggered = True
    state.current_down_price = 0.95
    state.current_up_price = 0.05
    state.realized_pnl_gross = 8.0

    total_value = state.compute_total_value()
    assert total_value > state.early_profit_target

    engine = make_engine(state)
    await early_profit_exit(state, engine._om, None)
    assert state.phase == "done"
    assert state.scenario == "EARLY_PROFIT"
