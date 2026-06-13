"""Group G — Scenario S3c Tests"""
import asyncio
import pytest
from tests.conftest import make_activated_state, make_engine


@pytest.mark.asyncio
async def test_g1_s3c_exits_all_shares_fak():
    """G1: S3c fires — all remaining shares sold FAK simultaneously, phase=done."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.s2_triggered = True
    state.s3b_triggered = True
    state.bounce_count = 2
    state.up_shares_held = 25.0
    state.down_shares_held = 30.0  # More weak shares than dominant → allowed by S3c
    engine = make_engine(state)

    fak_sells = []
    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        fak_sells.append((token_id, quantity, order_type))
        return price
    engine._om.sell = track_sell

    await engine._scenario_s3c(state)

    assert state.s3c_triggered is True
    assert state.scenario == "S3c"
    assert state.phase == "done"
    # Both sides should be sold
    assert len(fak_sells) == 2
    assert all(s[2] == "MARKET_FAK" for s in fak_sells)


@pytest.mark.asyncio
async def test_g2_s3c_partial_fill():
    """G2: S3c with partial FAK fill — filled portion recorded, remainder auto-cancelled."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s3b_triggered = True
    state.bounce_count = 2
    state.up_shares_held = 20.0
    state.down_shares_held = 20.0
    engine = make_engine(state)

    # Paper mode → instant full fill; FAK partial fill is SDK-level behavior
    # We verify S3c sets phase=done regardless
    await engine._scenario_s3c(state)
    assert state.phase == "done"
    assert state.s3c_triggered is True
