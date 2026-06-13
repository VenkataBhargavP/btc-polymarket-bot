import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/api")

# Injected at startup by main.py
_engine = None
_paper_engine = None
_db = None
_start_time = time.time()


def inject(engine, paper_engine, db):
    global _engine, _paper_engine, _db
    _engine = engine
    _paper_engine = paper_engine
    _db = db


# ── Request models ────────────────────────────────────────────────────────────

class ModeRequest(BaseModel):
    mode: str   # "paper" | "live"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status():
    state = _engine.state if _engine else None
    return {
        "mode": settings.mode,
        "phase": state.phase if state else "idle",
        "scenario": state.scenario if state else "",
        "bot_halted": _engine.bot_halted if _engine else False,
        "consecutive_losses": _engine.consecutive_losses if _engine else 0,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "event_id": state.event_id if state else "",
    }


@router.get("/wallet")
async def get_wallet():
    state = _engine.state if _engine else None
    if settings.mode == "paper" and _paper_engine:
        balance = _paper_engine.balance
    elif _engine and not _engine.bot_halted:
        try:
            from decimal import Decimal
            balance = float(await _engine._client.get_wallet_balance())
        except Exception:
            balance = 0.0
    else:
        balance = 0.0

    return {
        "mode": settings.mode,
        "balance": round(balance, 4),
        "realized_pnl": round(state.realized_pnl, 4) if state else 0.0,
        "unrealized_pnl": round(state.unrealized_pnl, 4) if state else 0.0,
        "total_cost_basis": round(state.total_cost_basis, 4) if state else 0.0,
        "early_profit_target": round(state.early_profit_target, 4) if state else 0.0,
    }


@router.get("/positions")
async def get_positions():
    state = _engine.state if _engine else None
    if not state:
        return {"positions": []}
    return {
        "positions": [
            {
                "side": "UP",
                "token_id": state.up_token_id,
                "shares_held": state.up_shares_held,
                "shares_sold": state.up_shares_sold,
                "current_price": state.current_up_price,
                "entry_price": state.entry_up_price,
                "unrealized_pnl": round(
                    state.up_shares_held * (state.current_up_price - state.entry_up_price), 4
                ),
            },
            {
                "side": "DOWN",
                "token_id": state.down_token_id,
                "shares_held": state.down_shares_held,
                "shares_sold": state.down_shares_sold,
                "current_price": state.current_down_price,
                "entry_price": state.entry_down_price,
                "unrealized_pnl": round(
                    state.down_shares_held * (state.current_down_price - state.entry_down_price), 4
                ),
            },
        ]
    }


@router.get("/trades")
async def get_trades(limit: int = 50, offset: int = 0):
    if not _db:
        return {"trades": []}
    from backend.db.store import get_paginated_trades
    trades = await get_paginated_trades(_db, limit=limit, offset=offset)
    return {"trades": trades, "limit": limit, "offset": offset}


@router.get("/events")
async def get_events(limit: int = 20):
    if not _db:
        return {"events": []}
    from backend.db.store import get_recent_events
    events = await get_recent_events(_db, limit=limit)
    return {"events": events}


@router.post("/mode")
async def set_mode(req: ModeRequest):
    if req.mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'live'")

    import backend.config as cfg
    cfg.settings.mode = req.mode

    if _engine and _engine._om:
        _engine._om.set_mode(paper=(req.mode == "paper"))

    return {"mode": req.mode, "message": "Mode switched. Takes effect on next event."}


@router.post("/pause")
async def pause_bot():
    if _engine:
        _engine.bot_halted = True
    return {"paused": True}


@router.post("/resume")
async def resume_bot():
    if not _engine:
        return {"resumed": False, "reason": "engine not initialized"}
    await _engine.resume()
    return {"resumed": True, "consecutive_losses": _engine.consecutive_losses,
            "bot_halted": _engine.bot_halted}


@router.get("/health")
async def get_health():
    from backend.execution.order_manager import _ORDER_LATENCY_MS
    om = _engine._om if _engine else None
    avg_latency = om.get_avg_latency_ms() if om else 0.0

    return {
        "status": "ok",
        "mode": settings.mode,
        "bot_halted": _engine.bot_halted if _engine else False,
        "order_latency_ms": avg_latency,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.post("/paper/reset")
async def reset_paper():
    if settings.mode != "paper":
        raise HTTPException(status_code=400, detail="Only available in paper mode")
    if _paper_engine:
        _paper_engine.reset()
    return {"reset": True, "balance": _paper_engine.balance if _paper_engine else 0}


@router.post("/force-exit")
async def force_exit():
    """Immediately emergency-exit any active event. Use for dry-run testing."""
    if not _engine or not _engine.state:
        return {"exited": False, "reason": "No active event"}
    state = _engine.state
    if state.phase == "done":
        return {"exited": False, "reason": "Event already done"}
    from backend.strategy.engine import emergency_exit
    await emergency_exit(state, "force_exit", _engine._om, _engine._client)
    return {
        "exited": True,
        "realized_pnl": round(state.realized_pnl, 4),
        "event_id": state.event_id,
    }
