"""Group O — Paper Mode Tests"""
import pytest
from backend.strategy.paper import PaperEngine
from backend.execution.order_manager import OrderManager
from backend.config import settings


def test_o1_paper_fills_instant_at_requested_price():
    """O1: Paper mode fills are instant at mid-price — no API calls."""
    paper = PaperEngine(1000.0)
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)

    import asyncio

    async def run():
        up = await om.buy("up-token", 50, 0.50, "LIMIT")
        down = await om.buy("down-token", 50, 0.50, "LIMIT")
        assert up == 0.50
        assert down == 0.50

        sell = await om.sell("up-token", 5, 0.30, "EXPIRING_LIMIT")
        assert sell == 0.30

    asyncio.get_event_loop().run_until_complete(run())


def test_o2_paper_wallet_reset():
    """O2: Paper wallet reset → balance returns to INITIAL_PAPER_BALANCE, positions cleared."""
    paper = PaperEngine(1000.0)
    paper.buy("UP", 50, 0.50)
    paper.sell("UP", 5, 0.70)

    assert paper.balance != 1000.0
    assert paper.positions.get("UP", 0) > 0

    paper.reset()

    assert paper.balance == 1000.0
    assert paper.positions == {}
    assert paper.trade_log == []


def test_o3_paper_position_tracking():
    """O3: Paper engine correctly tracks buy and sell positions."""
    paper = PaperEngine(500.0)

    paper.buy("UP", 50, 0.50)
    assert paper.positions["UP"] == 50.0
    assert paper.balance == pytest.approx(500.0 - 25.0, abs=0.01)

    paper.sell("UP", 5, 0.70)
    assert paper.positions["UP"] == 45.0
    assert paper.balance == pytest.approx(500.0 - 25.0 + 5 * 0.70, abs=0.01)


def test_o4_paper_mode_is_default():
    """O4: MODE defaults to 'paper' — never live by default."""
    # config.py has mode: str = "paper" as default
    # .env.example has MODE=paper
    # This verifies the contract
    from backend.config import Settings
    default = Settings(polymarket_private_key="dummy")
    assert default.mode == "paper"


def test_o5_paper_buy_sell_pnl():
    """O5: Paper engine correctly computes balance after trades."""
    paper = PaperEngine(1000.0)

    # Buy 50 UP + 50 DOWN at $0.50 = $50.00 total
    paper.buy("UP", 50, 0.50)
    paper.buy("DOWN", 50, 0.50)
    assert paper.balance == pytest.approx(1000.0 - 50.0, abs=0.01)

    # Sell 5 DOWN at $0.30 = $1.50 proceeds
    paper.sell("DOWN", 5, 0.30)
    assert paper.balance == pytest.approx(950.0 + 1.50, abs=0.01)
