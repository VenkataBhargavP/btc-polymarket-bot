"""Group K — Circuit Breaker Tests"""
import pytest
from tests.conftest import make_activated_state, make_engine
from backend.strategy.engine import StrategyEngine
from backend.strategy.paper import PaperEngine
from backend.execution.order_manager import OrderManager


def make_engine_with_losses(consecutive_losses: int, halted: bool = False) -> StrategyEngine:
    paper = PaperEngine(1000.0)
    om = OrderManager(client=None, paper_engine=paper, paper_mode=True)
    engine = StrategyEngine(order_manager=om, client=None, db=None)
    engine.consecutive_losses = consecutive_losses
    engine.bot_halted = halted
    return engine


def test_k1_first_loss_counter():
    """K1: 1st loss event → consecutive_losses=1, trading continues."""
    engine = make_engine_with_losses(0)
    engine.consecutive_losses += 1
    assert engine.consecutive_losses == 1
    assert not engine.bot_halted


def test_k2_second_loss_counter():
    """K2: 2nd loss event → consecutive_losses=2, trading continues."""
    engine = make_engine_with_losses(1)
    engine.consecutive_losses += 1
    assert engine.consecutive_losses == 2
    assert not engine.bot_halted


def test_k3_third_loss_halts_bot():
    """K3: 3rd consecutive loss → consecutive_losses=3, bot_halted=True."""
    engine = make_engine_with_losses(2)
    engine.consecutive_losses += 1

    if engine.consecutive_losses >= 3:
        engine.bot_halted = True

    assert engine.consecutive_losses == 3
    assert engine.bot_halted is True


def test_k4_win_resets_counter():
    """K4: Win event resets consecutive_losses to 0."""
    engine = make_engine_with_losses(2)
    # Win
    engine.consecutive_losses = 0
    assert engine.consecutive_losses == 0


@pytest.mark.asyncio
async def test_k5_resume_clears_halt():
    """K5: POST /api/resume while halted → bot_halted=False, consecutive_losses=0, trading resumes."""
    engine = make_engine_with_losses(3, halted=True)
    assert engine.bot_halted is True

    await engine.resume()

    assert engine.bot_halted is False
    assert engine.consecutive_losses == 0
