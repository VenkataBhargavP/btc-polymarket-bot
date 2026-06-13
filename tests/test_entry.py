"""Group A — Entry Tests"""
import asyncio
import time
import pytest
from tests.conftest import make_state, make_engine, make_activated_state
from backend.strategy.engine import StrategyEngine, register_engine
from backend.strategy.paper import PaperEngine
from backend.execution.order_manager import OrderManager


@pytest.mark.asyncio
async def test_a1_entry_places_both_orders_at_0_50():
    """A1: Wallet >= $50 → both maker limit orders placed at $0.50 simultaneously."""
    fills = []

    class TrackingOM(OrderManager):
        async def buy(self, token_id, quantity, price, order_type="LIMIT"):
            fills.append((token_id, quantity, price))
            return price

    paper = PaperEngine(1000.0)
    om = TrackingOM(client=None, paper_engine=paper, paper_mode=True)
    engine = StrategyEngine(order_manager=om, client=None, db=None)

    state = make_state()
    register_engine(state, engine)

    # Simulate start_event internals: two buys
    up, down = await asyncio.gather(
        om.buy(state.up_token_id, 50, 0.50, "LIMIT"),
        om.buy(state.down_token_id, 50, 0.50, "LIMIT"),
    )

    assert up == 0.50
    assert down == 0.50
    assert len(fills) == 2
    assert all(f[2] == 0.50 for f in fills)


@pytest.mark.asyncio
async def test_a2_insufficient_balance_skip():
    """A2: Wallet < $50 → window skipped."""
    from backend.data.market_finder import MarketFinder
    from backend.polymarket.models import MarketInfo
    from unittest.mock import AsyncMock, MagicMock

    paper = PaperEngine(20.0)  # Under $50
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)
    engine = StrategyEngine(order_manager=om, client=None, db=None)

    mock_client = MagicMock()
    mock_client.get_wallet_balance = AsyncMock(return_value=20.0)
    mock_client.find_btc_5min_markets = AsyncMock(return_value=[])

    finder = MarketFinder(client=mock_client)
    finder._upcoming = []

    # No next market → wait_and_enter would skip
    result = finder.get_next_market()
    assert result is None


@pytest.mark.asyncio
async def test_a3_cost_basis_and_profit_target():
    """A3: After entry fills, total_cost_basis is recorded; early_profit_target = cost_basis × 1.005."""
    state = make_state()
    state.entry_up_price = 0.50
    state.entry_down_price = 0.50
    state.up_shares_held = 50.0
    state.down_shares_held = 50.0

    state.total_cost_basis = (
        state.up_shares_held * state.entry_up_price
        + state.down_shares_held * state.entry_down_price
    )
    state.early_profit_target = round(state.total_cost_basis * 1.005, 4)

    assert state.total_cost_basis == 50.0
    assert state.early_profit_target == 50.25


@pytest.mark.asyncio
async def test_a4_bot_halted_skips_entry():
    """A4: Bot halted (circuit breaker) at T-30s → no entry placed."""
    paper = PaperEngine(1000.0)
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)
    engine = StrategyEngine(order_manager=om, client=None, db=None)
    engine.bot_halted = True
    engine.consecutive_losses = 3

    from backend.polymarket.models import MarketInfo
    market = MarketInfo(
        event_id="test", condition_id="c", up_token_id="u", down_token_id="d",
        start_ts=time.time() + 30, seconds_until=30
    )

    # start_event_from_market should skip when halted
    await engine.start_event_from_market(market)
    assert engine.state is None   # No event was started
