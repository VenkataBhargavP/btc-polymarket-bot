import asyncio
import json
import logging
import time
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

_PUSH_INTERVAL_S = 0.25   # 250ms

# Injected at startup
_engine = None
_paper_engine = None


def inject(engine, paper_engine):
    global _engine, _paper_engine
    _engine = engine
    _paper_engine = paper_engine


def _build_payload() -> dict:
    """Build the full state JSON pushed to the frontend every 250ms."""
    now_ms = int(time.time() * 1000)
    state = _engine.state if _engine else None

    if not state:
        return {
            "ts": now_ms,
            "mode": "paper",
            "phase": "idle",
            "scenario": "",
            "activation_window": 0,
            "elapsed_seconds": 0,
            "event_id": "",
            "event_expires_in": 0,
            "up_price": 0.5,
            "down_price": 0.5,
            "dominant_side": "",
            "weak_side": "",
            "up_shares_held": 0,
            "down_shares_held": 0,
            "up_shares_sold": 0,
            "down_shares_sold": 0,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "realized_pnl_gross": 0,
            "total_cost_basis": 0,
            "early_profit_target": 0,
            "current_total_value": 0,
            "profit_to_target": 0,
            "wallet_balance": _paper_engine.balance if _paper_engine else 0,
            "consecutive_losses": _engine.consecutive_losses if _engine else 0,
            "bot_halted": _engine.bot_halted if _engine else False,
            "profit_guard": {},
            "trade_log": [],
            "price_history": [],
            "health": {"ws_connected": False, "last_tick_ms": 0, "order_latency_ms": 0},
        }

    elapsed = time.time() - state.start_time
    event_duration = 300
    expires_in = max(0, event_duration - elapsed)
    total_value = state.compute_total_value()
    profit_to_target = max(0, state.early_profit_target - total_value)

    if state.mode == "paper" and _paper_engine:
        wallet_balance = _paper_engine.balance
    else:
        wallet_balance = 0.0

    unrealized = (
        state.up_shares_held * state.current_up_price
        + state.down_shares_held * state.current_down_price
        - (
            state.up_shares_held * state.entry_up_price
            + state.down_shares_held * state.entry_down_price
        )
    )
    state.unrealized_pnl = round(unrealized, 4)

    om = _engine._om if _engine else None
    order_latency = om.get_avg_latency_ms() if om else 0.0

    return {
        "ts": now_ms,
        "mode": state.mode,
        "phase": state.phase,
        "scenario": state.scenario,
        "activation_window": state.activation_window,
        "elapsed_seconds": round(elapsed, 1),
        "event_id": state.event_id,
        "event_expires_in": round(expires_in, 1),
        "up_price": state.current_up_price,
        "down_price": state.current_down_price,
        "dominant_side": state.dominant_side,
        "weak_side": state.weak_side,
        "up_shares_held": state.up_shares_held,
        "down_shares_held": state.down_shares_held,
        "up_shares_sold": state.up_shares_sold,
        "down_shares_sold": state.down_shares_sold,
        "realized_pnl": round(state.realized_pnl, 4),
        "unrealized_pnl": round(state.unrealized_pnl, 4),
        "realized_pnl_gross": round(state.realized_pnl_gross, 4),
        "total_cost_basis": round(state.total_cost_basis, 4),
        "early_profit_target": round(state.early_profit_target, 4),
        "current_total_value": round(total_value, 4),
        "profit_to_target": round(profit_to_target, 4),
        "wallet_balance": round(wallet_balance, 4),
        "consecutive_losses": state.consecutive_losses,
        "bot_halted": state.bot_halted,
        "profit_guard": state.profit_guard,
        "trade_log": state.trade_log[-20:],
        "price_history": state.price_history[-60:],
        "health": {
            "ws_connected": True,
            "last_tick_ms": 0,
            "order_latency_ms": order_latency,
        },
    }


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("WebSocket client connected", extra={"client": str(websocket.client)})
    try:
        while True:
            try:
                payload = _build_payload()
                await websocket.send_text(json.dumps(payload))
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                log.error("WebSocket push error", extra={"error": str(exc)})
            await asyncio.sleep(_PUSH_INTERVAL_S)
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
    except Exception as exc:
        log.error("WebSocket fatal error", extra={"error": str(exc)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
