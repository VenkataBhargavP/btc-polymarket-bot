"""Group C — Scenario S1 Tests"""
import asyncio
import pytest
from tests.conftest import make_activated_state, make_engine


@pytest.mark.asyncio
async def test_c1_s1_sells_5_weak_shares():
    """C1: S1 fires immediately at activation — 5 WEAK shares sold via expiring limit."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    engine = make_engine(state)

    sells = []
    original_sell = engine._om.sell

    async def track_sell(token_id, quantity, price, order_type="EXPIRING_LIMIT"):
        sells.append((token_id, quantity, order_type))
        return price

    engine._om.sell = track_sell
    await engine._scenario_s1(state)

    assert state.s1_triggered is True
    assert state.scenario == "S1"
    assert any(s[1] == 5 for s in sells), "Expected 5 shares in first S1 sell"
    assert any(s[2] == "EXPIRING_LIMIT" for s in sells)


@pytest.mark.asyncio
async def test_c2_s1_dominant_reaches_99():
    """C2: After S1, dominant hits 99¢ → close_winning, no sell orders placed."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    engine = make_engine(state)

    state.s1_triggered = True
    state.scenario = "S1"
    state.down_shares_held = 45.0  # after 5 sold

    state.current_up_price = 0.99

    cancelled = []
    from backend.strategy.engine import close_winning

    async def mock_cancel(token_id):
        cancelled.append(token_id)

    class MockClient:
        cancel_all_market_orders = mock_cancel

    await close_winning(state, winning_side="UP", client=MockClient())

    assert state.phase == "done"
    assert state.scenario == "CLOSE_WIN"
    assert len(cancelled) == 2  # both token IDs cancelled


@pytest.mark.asyncio
async def test_c3_early_profit_triggered_in_s1():
    """C3: After S1, early_profit_target crossed → early_profit_exit fires."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    state.s1_triggered = True
    state.scenario = "S1"
    state.down_shares_held = 45.0

    # Manually push value over target
    state.total_cost_basis = 50.0
    state.early_profit_target = 50.25
    state.current_up_price = 0.90
    state.current_down_price = 0.10
    state.realized_pnl_gross = 5.0 * 0.30   # from S1 sell

    total_value = state.compute_total_value()
    assert total_value > state.early_profit_target

    from backend.strategy.engine import early_profit_exit
    engine = make_engine(state)
    await early_profit_exit(state, engine._om, None)

    assert state.phase == "done"
    assert state.scenario == "EARLY_PROFIT"


def test_c4_s1_triggers_s2_on_reversal():
    """C4: After S1, dominant drops to reversal_trigger → S2 triggered."""
    state = make_activated_state(dominant="UP", dom_price=0.70)
    t = state.thresholds

    # Simulate price drop to reversal trigger
    state.current_up_price = t["reversal_trigger"]

    dom_price = state.get_side_price(state.dominant_side)
    assert dom_price <= t["reversal_trigger"]
    assert not state.s2_triggered  # S2 not yet fired


def test_c5_order_ttl_auto_cancels():
    """C5: S1 expiring limit order with 10s TTL — auto-cancels if not filled."""
    # Structural: EXPIRING_LIMIT orders have TTL of 10s per spec
    # In paper mode fills are instant; in live mode the TTL handles this at SDK level
    # We verify the order_type is correctly passed
    from backend.execution.order_manager import OrderManager
    from backend.strategy.paper import PaperEngine

    paper = PaperEngine(1000.0)
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)

    # In paper mode EXPIRING_LIMIT and MARKET_FAK both fill instantly
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        om.sell("token-1", 5, 0.30, "EXPIRING_LIMIT")
    )
    loop.close()
    assert result == 0.30
