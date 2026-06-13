import json
import time
import aiosqlite
from backend.config import settings

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id                    TEXT PRIMARY KEY,
    condition_id          TEXT,
    start_ts              INTEGER,
    end_ts                INTEGER,
    mode                  TEXT,
    activation_window     INTEGER,
    activation_up_price   REAL,
    activation_down_price REAL,
    dominant_side         TEXT,
    outcome               TEXT,
    scenario_path         TEXT,
    realized_pnl          REAL,
    cost_basis            REAL,
    early_profit_target   REAL,
    trade_count           INTEGER,
    consecutive_losses    INTEGER
);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT,
    ts          INTEGER,
    action      TEXT,
    side        TEXT,
    shares      REAL,
    price       REAL,
    total_value REAL,
    order_id    TEXT,
    mode        TEXT,
    scenario    TEXT
);

CREATE TABLE IF NOT EXISTS price_ticks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT,
    ts         INTEGER,
    up_price   REAL,
    down_price REAL
);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    await db.executescript(_DDL)
    await db.commit()
    return db


async def save_event(db: aiosqlite.Connection, state) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO events
            (id, condition_id, start_ts, end_ts, mode, activation_window,
             activation_up_price, activation_down_price, dominant_side,
             outcome, scenario_path, realized_pnl, cost_basis,
             early_profit_target, trade_count, consecutive_losses)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            state.event_id,
            state.market_condition_id,
            int(state.start_time),
            int(time.time()),
            state.mode,
            state.activation_window,
            state.activation_up_price,
            state.activation_down_price,
            state.dominant_side,
            state.scenario,
            _build_scenario_path(state),
            state.realized_pnl,
            state.total_cost_basis,
            state.early_profit_target,
            len(state.trade_log),
            state.consecutive_losses,
        ),
    )
    await db.commit()


async def save_trade(db: aiosqlite.Connection, event_id: str, trade: dict) -> None:
    await db.execute(
        """
        INSERT INTO trades
            (event_id, ts, action, side, shares, price, total_value, order_id, mode, scenario)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            event_id,
            int(trade.get("ts", time.time())),
            trade.get("action", ""),
            trade.get("side", ""),
            trade.get("shares", 0),
            trade.get("price", 0),
            trade.get("shares", 0) * trade.get("price", 0),
            trade.get("order_id", ""),
            trade.get("mode", "paper"),
            trade.get("scenario", ""),
        ),
    )
    await db.commit()


async def save_tick(db: aiosqlite.Connection, event_id: str,
                    up_price: float, down_price: float) -> None:
    await db.execute(
        "INSERT INTO price_ticks (event_id, ts, up_price, down_price) VALUES (?,?,?,?)",
        (event_id, int(time.time() * 1000), up_price, down_price),
    )
    await db.commit()


async def get_bot_state_value(db: aiosqlite.Connection, key: str, default=None):
    async with db.execute("SELECT value FROM bot_state WHERE key=?", (key,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return default
    return json.loads(row["value"])


async def set_bot_state_value(db: aiosqlite.Connection, key: str, value) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?,?)",
        (key, json.dumps(value)),
    )
    await db.commit()


async def get_trades_for_event(db: aiosqlite.Connection, event_id: str) -> list:
    async with db.execute(
        "SELECT * FROM trades WHERE event_id=? ORDER BY ts ASC", (event_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_recent_events(db: aiosqlite.Connection, limit: int = 20) -> list:
    async with db.execute(
        "SELECT * FROM events ORDER BY start_ts DESC LIMIT ?", (limit,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_paginated_trades(db: aiosqlite.Connection,
                                limit: int = 50, offset: int = 0) -> list:
    async with db.execute(
        "SELECT * FROM trades ORDER BY ts DESC LIMIT ? OFFSET ?", (limit, offset)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


def _build_scenario_path(state) -> str:
    parts = []
    if state.s1_triggered:
        parts.append("S1")
    if state.s2_triggered:
        parts.append("S2")
    if state.s3a_triggered:
        parts.append("S3a")
    if state.s3b_triggered:
        parts.append("S3b")
    if state.s3c_triggered:
        parts.append("S3c")
    if state.scenario in ("EARLY_PROFIT", "EXIT_NPZ", "CLOSE_WIN"):
        parts.append(state.scenario)
    return "→".join(parts) if parts else state.scenario
