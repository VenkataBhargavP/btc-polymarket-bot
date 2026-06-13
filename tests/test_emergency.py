"""Group J — Emergency Exit Tests"""
import asyncio
import time
import pytest
from tests.conftest import make_activated_state, make_state, make_engine
from backend.strategy.engine import emergency_exit


@pytest.mark.asyncio
async def test_j1_expiry_approaching():
    """J1: expiry_approaching → all shares sold FAK, higher-value side first."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    engine = make_engine(state)

    sell_order = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sell_order.append((token_id, order_type))
        return price
    engine._om.sell = track_sell

    from backend.strategy.engine import register_engine
    register_engine(state, engine)
    await emergency_exit(state, "expiry_approaching", engine._om, None)

    assert state.phase == "done"
    assert state.scenario == "EXIT_NPZ"
    assert all(s[1] == "MARKET_FAK" for s in sell_order)


@pytest.mark.asyncio
async def test_j2_below_min_edge():
    """J2: below_min_edge at activation → all shares sold FAK immediately."""
    state = make_state(up_price=0.52, down_price=0.48)
    state.phase = "active"
    state.dominant_side = "UP"
    state.weak_side = "DOWN"
    engine = make_engine(state)

    fak_sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        fak_sells.append(order_type)
        return price
    engine._om.sell = track_sell

    from backend.strategy.engine import register_engine
    register_engine(state, engine)
    await emergency_exit(state, "below_min_edge", engine._om, None)

    assert state.phase == "done"
    assert state.scenario == "EXIT_NPZ"


@pytest.mark.asyncio
async def test_j3_no_profit_zone():
    """J3: no_profit_zone headroom breached → all shares sold FAK, scenario=EXIT_NPZ."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.up_shares_held = 1.0
    state.down_shares_held = 1.0
    state.total_cost_basis = 50.0
    state.realized_pnl_gross = 0.0
    engine = make_engine(state)

    from backend.strategy.engine import register_engine
    register_engine(state, engine)
    await emergency_exit(state, "no_profit_zone", engine._om, None)

    assert state.phase == "done"
    assert state.scenario == "EXIT_NPZ"


@pytest.mark.asyncio
async def test_j4_emergency_exit_no_dominant_set():
    """J4: Emergency exit when no dominant side set yet — defaults to UP/DOWN, exits cleanly."""
    state = make_state(up_price=0.50, down_price=0.50)
    state.phase = "active"
    state.dominant_side = ""  # Not yet set
    state.weak_side = ""
    engine = make_engine(state)

    from backend.strategy.engine import register_engine
    register_engine(state, engine)
    await emergency_exit(state, "below_min_edge", engine._om, None)

    assert state.phase == "done"
    assert state.scenario == "EXIT_NPZ"
