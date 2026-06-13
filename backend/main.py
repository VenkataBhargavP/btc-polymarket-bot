import asyncio
import logging
import logging.handlers
import os
import signal
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket

from pythonjsonlogger import jsonlogger

from backend.config import settings
from backend.db.store import (
    init_db,
    get_bot_state_value,
    set_bot_state_value,
)
from backend.strategy.paper import PaperEngine
from backend.strategy.engine import StrategyEngine
from backend.execution.order_manager import OrderManager
from backend.data.market_finder import MarketFinder
from backend.api import routes as api_routes
from backend.api import ws as api_ws


# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging():
    os.makedirs("backend/logs", exist_ok=True)

    formatter = jsonlogger.JsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp"},
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        "backend/logs/bot.log", when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


log = logging.getLogger(__name__)


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    log.info("Bot starting", extra={"mode": settings.mode})

    # DB
    db = await init_db()

    # Paper engine
    paper = PaperEngine(initial_balance=settings.initial_paper_balance)

    # Polymarket client
    # Live: full auth + trading approvals.
    # Paper with credentials: read-only (market discovery + price feed, no
    #   on-chain trading approvals).  Without credentials: stays None (UI only).
    client = None
    if settings.mode == "live":
        from backend.polymarket.client import PolymarketClient
        client = PolymarketClient()
        await client.connect()
        log.info("Polymarket client connected (live)")
    elif settings.polymarket_private_key and settings.polymarket_wallet_address:
        from backend.polymarket.client import PolymarketClient
        client = PolymarketClient()
        await client.connect_readonly()
        log.info("Polymarket client connected (paper/readonly)")

    # Order manager
    om = OrderManager(
        client=client,
        paper_engine=paper,
        paper_mode=(settings.mode == "paper"),
    )

    # Strategy engine
    engine = StrategyEngine(order_manager=om, client=client, db=db, paper_engine=paper)

    # Restore circuit breaker state from DB
    consecutive_losses = await get_bot_state_value(db, "consecutive_losses", 0)
    bot_halted = await get_bot_state_value(db, "bot_halted", False)
    engine.load_circuit_breaker(consecutive_losses, bot_halted)
    log.info(
        "Circuit breaker restored",
        extra={"consecutive_losses": consecutive_losses, "bot_halted": bot_halted},
    )

    # Market finder — in paper mode, pass paper_engine so balance is checked
    # against the virtual wallet, not the real on-chain wallet.
    market_finder = None
    if client:
        market_finder = MarketFinder(
            client=client,
            paper_engine=paper if settings.mode == "paper" else None,
        )

    # Inject into API modules
    api_routes.inject(engine, paper, db)
    api_ws.inject(engine, paper)

    # Health check at startup
    if settings.mode == "live":
        if not settings.polymarket_private_key:
            log.error("POLYMARKET_PRIVATE_KEY is not set — cannot trade live")
            sys.exit(1)
        try:
            balance = float(await client.get_wallet_balance())
            if balance <= 0:
                log.error("Wallet balance is 0 — check credentials")
        except Exception as exc:
            log.error("Startup health check failed", extra={"error": str(exc)})

    # Background tasks
    tasks = []
    if market_finder:
        tasks.append(asyncio.create_task(market_finder.run_loop()))
        tasks.append(asyncio.create_task(market_finder.wait_and_enter(engine)))
    else:
        log.info("No Polymarket credentials in .env — market finder disabled (UI-only mode)")

    # Graceful shutdown handler
    def _shutdown(*_):
        log.warning("SIGTERM received — finishing current event")
        for t in tasks:
            t.cancel()

    signal.signal(signal.SIGTERM, _shutdown)

    app.state.engine = engine
    app.state.paper = paper
    app.state.db = db

    yield

    # Cleanup
    for t in tasks:
        t.cancel()
    if client:
        await client.close()
    await db.close()
    log.info("Bot shutdown complete")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="BTC Polymarket Bot", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_routes.router)


@app.websocket("/ws")
async def ws_handler(websocket: WebSocket):
    await api_ws.websocket_endpoint(websocket)


# Serve built frontend if it exists
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        log_config=None,
    )
