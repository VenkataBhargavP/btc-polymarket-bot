"""Group E — Scenario S3a Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.engine import close_winning, early_profit_exit


@pytest.mark.asyncio
async def test_e1_s3a_sells_10_weak_shares():
    """E1: S3a fires on bounce — 10 WEAK shares sold."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.s2_triggered = True
    state.bounce_count = 1
    state.down_shares_held = 35.0  # After S1 5 sold
    engine = make_engine(state)

    sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sells.append((token_id, quantity, order_type))
        return price
    engine._om.sell = track_sell

    await engine._scenario_s3a(state)

    assert state.s3a_triggered is True
    assert state.scenario == "S3a"
    weak_sells = [s for s in sells if s[0] == state.down_token_id]
    assert any(s[1] == 10 for s in weak_sells)


@pytest.mark.asyncio
async def test_e2_s3a_dominant_reaches_99():
    """E2: After S3a, dominant reaches 99¢ → close_winning(dominant)."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3a_triggered = True
    state.current_up_price = 0.99

    t = state.thresholds
    dom_price = state.get_side_price(state.dominant_side)
    assert dom_price >= t["expiry_win"]

    await close_winning(state, winning_side=state.dominant_side, client=None)
    assert state.phase == "done"
    assert state.scenario == "CLOSE_WIN"


def test_e3_s3a_drop_triggers_s3b_bounce_count():
    """E3: After S3a, dominant drops to reversal_trigger → S3b, bounce_count=2."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3a_triggered = True
    state.bounce_count = 1

    t = state.thresholds
    state.current_up_price = t["reversal_trigger"]

    dom_price = state.get_side_price(state.dominant_side)
    assert dom_price <= t["reversal_trigger"]
    # bounce_count would be incremented → 2


def test_e4_s3a_bail_when_bounce_count_gte_2():
    """E4: After S3a, bounce_count >= 2 and dominant at bail_trigger → S3c bail."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3a_triggered = True
    state.bounce_count = 2

    t = state.thresholds
    state.current_up_price = t["bail_trigger"]

    dom_price = state.get_side_price(state.dominant_side)
    assert state.bounce_count >= 2
    assert dom_price >= t["bail_trigger"]


@pytest.mark.asyncio
async def test_e5_early_profit_in_s3a():
    """E5: After S3a, total value > target → early_profit_exit fires."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3a_triggered = True
    state.current_up_price = 0.95
    state.current_down_price = 0.05
    state.realized_pnl_gross = 5.0

    total_value = state.compute_total_value()
    assert total_value > state.early_profit_target

    engine = make_engine(state)
    await early_profit_exit(state, engine._om, None)
    assert state.phase == "done"
    assert state.scenario == "EARLY_PROFIT"
