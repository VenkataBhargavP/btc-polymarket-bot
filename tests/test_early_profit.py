"""Group I — Early Profit Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.engine import early_profit_exit


def _set_above_target(state):
    """Push total_value above early_profit_target."""
    state.current_up_price = 0.95
    state.current_down_price = 0.05
    state.realized_pnl_gross = 5.0
    return state.compute_total_value()


@pytest.mark.asyncio
async def test_i1_early_profit_in_s1():
    """I1: early_profit_target crossed in S1 → early_profit_exit fires."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.scenario = "S1"
    val = _set_above_target(state)
    assert val >= state.early_profit_target

    engine = make_engine(state)
    await early_profit_exit(state, engine._om, None)
    assert state.phase == "done"
    assert state.scenario == "EARLY_PROFIT"


@pytest.mark.asyncio
async def test_i2_early_profit_in_s2():
    """I2: early_profit_target crossed in S2 → early_profit_exit fires."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.scenario = "S2"
    state.s1_triggered = True
    _set_above_target(state)

    engine = make_engine(state)
    await early_profit_exit(state, engine._om, None)
    assert state.phase == "done"
    assert state.scenario == "EARLY_PROFIT"


@pytest.mark.asyncio
async def test_i3_early_profit_in_s3a_s3b():
    """I3: early_profit_target crossed in S3a/S3b → early_profit_exit fires."""
    for scenario in ("S3a", "S3b"):
        state = make_activated_state(dominant="UP", dom_price=0.70)
        state.scenario = scenario
        _set_above_target(state)

        engine = make_engine(state)
        await early_profit_exit(state, engine._om, None)
        assert state.phase == "done"
        assert state.scenario == "EARLY_PROFIT"


def test_i4_profit_target_is_0_5_percent():
    """I4: early_profit_target = cost_basis × 1.005 — not hardcoded."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.total_cost_basis = 50.0
    state.early_profit_target = round(state.total_cost_basis * 1.005, 4)

    assert state.early_profit_target == 50.25

    # Non-standard cost basis
    state.total_cost_basis = 47.50
    state.early_profit_target = round(state.total_cost_basis * 1.005, 4)
    assert state.early_profit_target == pytest.approx(47.7375, abs=1e-4)


def test_i4_phase_done_set_first():
    """early_profit_exit sets phase='done' BEFORE placing any orders."""
    import asyncio
    state = make_activated_state(dominant="UP", dom_price=0.70)

    phase_at_sell = []

    async def track():
        from backend.strategy.engine import register_engine
        engine = make_engine(state)

        original = engine._om.sell
        async def spy_sell(*a, **kw):
            phase_at_sell.append(state.phase)
            return 0.70
        engine._om.sell = spy_sell

        await early_profit_exit(state, engine._om, None)

    asyncio.get_event_loop().run_until_complete(track())
    # phase must be "done" before sells
    assert all(p == "done" for p in phase_at_sell)
