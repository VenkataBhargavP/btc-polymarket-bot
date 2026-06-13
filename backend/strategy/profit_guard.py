from backend.config import settings

MIN_PROFIT_BUFFER = settings.min_profit_buffer


def compute_headroom(state) -> dict:
    """
    Best-case future value assumes:
      - dominant_held shares all win at $0.99
      - weak_held shares all lose at $0.01

    If this best case still can't return MIN_PROFIT_BUFFER above cost basis,
    the position is in the no-profit zone and must be exited immediately.

    Called after every sell_shares() and on every price tick.
    """
    dom = state.dominant_side
    weak = state.weak_side

    dom_held = state.up_shares_held if dom == "UP" else state.down_shares_held
    weak_held = state.up_shares_held if weak == "UP" else state.down_shares_held

    best_future = (dom_held * 0.99) + (weak_held * 0.01)
    max_rec = state.realized_pnl_gross + best_future
    headroom = max_rec - state.total_cost_basis
    in_zone = headroom > MIN_PROFIT_BUFFER

    return {
        "realized": round(state.realized_pnl_gross, 4),
        "best_future": round(best_future, 4),
        "max_recoverable": round(max_rec, 4),
        "cost_basis": round(state.total_cost_basis, 4),
        "headroom": round(headroom, 4),
        "in_profit_zone": in_zone,
    }


async def check_profit_zone(state) -> bool:
    """Idempotent — safe to call multiple times per tick."""
    if state.phase == "done":
        return True   # Already exiting — never re-trigger
    result = compute_headroom(state)
    state.profit_guard = result
    if not result["in_profit_zone"]:
        from backend.strategy.engine import emergency_exit
        await emergency_exit(state, reason="no_profit_zone")
        return False
    return True
