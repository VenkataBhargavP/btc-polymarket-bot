# BTC Polymarket Bot — v4.0

> Automated split-order trading bot for **Polymarket's BTC 5-minute Up/Down** prediction markets.
> Full scenario state machine · real-time React dashboard · paper & live modes.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start — Windows](#quick-start--windows)
- [Quick Start — Linux / macOS](#quick-start--linux--macos)
- [Configuration Reference](#configuration-reference)
- [Strategy Deep-Dive](#strategy-deep-dive)
- [Dashboard](#dashboard)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [Known Issues & Status](#known-issues--status)
- [Security](#security)

---

## How It Works

Every 5 minutes Polymarket opens a new **BTC Up/Down** binary market — will BTC be _higher_ or _lower_ at the end of this 5-minute window?

This bot:

1. **Detects** the next upcoming event 30 seconds before it opens.
2. **Enters** a balanced split position — equal shares of **UP** and **DOWN** at ~$0.50 each.
3. **Monitors** price movement and activates when one side makes a decisive ≥ 30-cent move.
4. **Executes** the scenario state machine to manage the winning leg and lock in profit.
5. **Exits** via early profit target, No-Profit-Zone emergency exit, or oracle settlement.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                 │
│              React + Vite SPA  (localhost:5173)                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐  │
│  │  Price   │ │Strategy  │ │Positions  │ │System Health     │  │
│  │  Chart   │ │  State   │ │  & P&L   │ │& Trade Log       │  │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                    WS push every 250 ms
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                   FastAPI  (localhost:8000)                      │
│                                                                  │
│  ┌─────────────┐   ┌──────────────────────────────────────────┐ │
│  │MarketFinder │──▶│           StrategyEngine                 │ │
│  │polls every  │   │   S1 → S2 → S3a / S3b / S3c             │ │
│  │30 seconds   │   │   snap5() · profit_guard · circuit_breaker│ │
│  └─────────────┘   └───────────────────┬──────────────────────┘ │
│                                        │                         │
│  ┌──────────────────────┐  ┌───────────▼──────────────────────┐ │
│  │      PriceFeed       │  │         OrderManager             │ │
│  │  WS stream (live)    │  │  paper → PaperEngine ($virtual)  │ │
│  │  REST poll (paper)   │  │  live  → PolymarketClient        │ │
│  └──────────────────────┘  └──────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  SQLite (aiosqlite)  │  │   JSON structured logging        │ │
│  │  trade & event log   │  │   backend/logs/bot.log           │ │
│  └──────────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                            │
              polymarket-client SDK (async)
                            │
                    clob.polymarket.com
```

---

## Project Structure

```
btc-polymarket-bot/
│
├── backend/
│   ├── main.py                    # FastAPI app, lifespan startup/shutdown
│   ├── config.py                  # Pydantic settings — all env vars in one place
│   │
│   ├── api/
│   │   ├── routes.py              # REST endpoints (/api/*)
│   │   └── ws.py                  # WebSocket push endpoint (/ws, 250 ms)
│   │
│   ├── strategy/
│   │   ├── engine.py              # Core state machine (S1 → S2 → S3a/b/c)
│   │   ├── state.py               # EventState dataclass
│   │   ├── paper.py               # PaperEngine — virtual wallet, instant fills
│   │   └── profit_guard.py        # No-Profit-Zone (NPZ) headroom logic
│   │
│   ├── data/
│   │   ├── market_finder.py       # Discovers upcoming BTC 5-min markets
│   │   └── price_feed.py          # WS stream + watchdog + exponential backoff
│   │
│   ├── execution/
│   │   ├── order_manager.py       # Routes orders: paper vs live
│   │   └── position_tracker.py    # Fill & share tracking
│   │
│   ├── polymarket/
│   │   ├── client.py              # SDK wrapper (public + secure clients, poll fallback)
│   │   └── models.py              # MarketInfo dataclass
│   │
│   └── db/
│       └── store.py               # SQLite schema, trade logging, state persistence
│
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/            # Header · WalletPanel · PriceChart · TradeLog · …
│       ├── hooks/
│       │   ├── useWebSocket.ts    # Auto-reconnect WS with exponential backoff
│       │   └── useStrategyState.ts
│       └── types/index.ts         # BotState TypeScript interface
│
├── tests/                         # pytest suite — S1 through S3c + edge cases
├── docs/                          # Design spec, API reference, kickoff prompt
│
├── dev.ps1                        # Windows dev launcher (two PowerShell windows)
├── dev.sh                         # Linux/macOS dev launcher
├── start.ps1                      # Windows production launcher
├── start.sh                       # Linux/macOS production launcher
├── pyproject.toml                 # uv project definition
└── .env.example                   # All config keys with descriptions
```

---

## Prerequisites

| Tool | Min Version | Purpose |
|------|------------|---------|
| Python | 3.11 | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager (replaces pip/venv) |
| Node.js | 18 | Frontend build |
| npm | 9 | Frontend packages |

> **Polymarket account**: Live mode requires a MetaMask wallet funded with USDC on Polygon, connected to a Polymarket account.

---

## Quick Start — Windows

### 1. Clone & configure

```powershell
git clone https://github.com/VenkataBhargavP/btc-polymarket-bot.git
cd btc-polymarket-bot
copy .env.example .env
# Edit .env — add your credentials and set MODE
```

### 2. Development (hot-reload)

```powershell
.\dev.ps1
```

Opens two windows automatically:

| Window | URL | What's running |
|--------|-----|---------------|
| Backend | http://localhost:8000 | FastAPI + uvicorn `--reload` |
| Frontend | http://localhost:5173 | Vite dev server |

Open **http://localhost:5173** in your browser.

### 3. Production (single server)

```powershell
.\start.ps1
```

Builds the frontend into `frontend/dist/`, then FastAPI serves everything at **http://localhost:8000**.

---

## Quick Start — Linux / macOS

```bash
git clone https://github.com/VenkataBhargavP/btc-polymarket-bot.git
cd btc-polymarket-bot
cp .env.example .env
# Edit .env

./dev.sh      # development
./start.sh    # production
```

---

## Configuration Reference

All settings live in `.env`. Every key maps to a field in `backend/config.py`.

```ini
# ── Credentials (required for live mode) ──────────────────────────────────────
POLYMARKET_PRIVATE_KEY=          # MetaMask private key (hex)
POLYMARKET_WALLET_ADDRESS=       # Wallet address (0x…) — optional, SDK derives it

# ── Mode ──────────────────────────────────────────────────────────────────────
MODE=paper                       # "paper" (safe default) | "live" (real orders)
INITIAL_PAPER_BALANCE=1000.00    # Starting virtual balance for paper mode

# ── Trade sizing ──────────────────────────────────────────────────────────────
ENTRY_QUANTITY_SHARES=50         # Shares per side at entry
                                 #   50 shares × $0.50 = $25/side = $50 total
                                 #   Set to 5 for a $5 dry-run test

# ── Strategy parameters ───────────────────────────────────────────────────────
MOVE_THRESHOLD_POINTS=30         # Price move in cents to trigger activation
WINDOW_1_DURATION=30             # Seconds: Window 1 (early decisive move)
ACTIVATION_TIMER=210             # Force activation at 3m 30s if no move yet
MIN_DOMINANT_PRICE=0.55          # Minimum dominant-side price at activation (55¢)
MIN_PROFIT_BUFFER=0.50           # Min headroom $ before NPZ emergency exit
PRE_ENTRY_SECONDS=30             # Seconds before open to place entry orders
MAX_CONSECUTIVE_LOSSES=3         # Circuit breaker: halt after N losses in a row

# ── Infrastructure ────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
DB_PATH=./bot.db
```

---

## Strategy Deep-Dive

### Entry

At **T-30 seconds** before a BTC 5-min market opens, the bot places two maker limit orders simultaneously:

```
BUY  UP   — N shares @ $0.50
BUY  DOWN — N shares @ $0.50
```

Cost basis = `N × $0.50 × 2`.
Profit target = `cost_basis × 1.005` (exactly 0.5% above cost, computed after fill).

### State Machine

```
         ┌──────────┐
         │ WAITING  │  Both legs open, watching for a ≥30¢ move
         └────┬─────┘
              │ dominant side crosses ±0.30
              │ (Window 1: first 30s | Window 2: up to 210s)
              ▼
         ┌──────────┐
    ┌────│  ACTIVE  │────────────────────────────────────────┐
    │    └──────────┘                                        │
    │                                                        │
    │ dominant bounces back to entry price (S1 → S2)        │ dominant dips 10¢ below entry (S1 → S2)
    ▼                                                        ▼
  ┌──────────────────────────────┐          ┌───────────────────────────────────┐
  │ S3a — Bounce Recovery        │          │ S3b — Second Dip                  │
  │ Sell weak leg at market.     │          │ Sell weak leg at entry price.     │
  │ Hold dominant for settlement.│          │ Watch for S3c bail trigger.       │
  └──────────────────────────────┘          └─────────────────┬─────────────────┘
                                                              │ dominant recovers to entry
                                                              ▼
                                            ┌───────────────────────────────────┐
                                            │ S3c — Bail Out                    │
                                            │ Sell dominant shares via FAK.     │
                                            │ Close entire position.            │
                                            └───────────────────────────────────┘

  EARLY PROFIT EXIT  ── fires whenever total_value ≥ early_profit_target
  EMERGENCY EXIT     ── fires on NPZ (No Profit Zone) breach or <30s to expiry
  FORCE EXIT         ── manual API call → immediate emergency exit
```

### Threshold Levels (all snapped to nearest 5¢)

| Trigger | Formula | Example — dom=0.65 |
|---------|---------|-------------------|
| S1 → S2 reversal | `dominant − 0.05` | 0.60 |
| S2 → S3a bounce | `dominant` | 0.65 |
| S2 → S3b second dip | `dominant − 0.10` | 0.55 |
| S3b → S3c bail | `dominant` | 0.65 |
| Expiry win threshold | 0.99 | 0.99 |
| Expiry lose threshold | 0.01 | 0.01 |

### Circuit Breaker

After `MAX_CONSECUTIVE_LOSSES` losses the bot halts. Dashboard shows a red banner. Click **Resume** (or `POST /api/resume`) to reset the counter and restart event detection.

---

## Dashboard

Open **http://localhost:5173** (dev) or **http://localhost:8000** (prod).

| Panel | What you see |
|-------|-------------|
| **Header** | Mode badge · event countdown · Pause/Resume · PAPER/LIVE toggle · **Force Exit** (appears during active event) · WS indicator |
| **Price Chart** | Last 60 UP/DOWN price ticks |
| **Wallet Panel** | Balance · Realized P&L · Unrealized P&L |
| **Strategy State** | Phase · scenario · dominant/weak sides · prices · cost basis · profit target |
| **Positions** | Shares held/sold per side with current value |
| **Profit Meter** | Visual bar: current total value vs target vs headroom |
| **Trade Log** | Last 20 fills — action, side, shares, price, P&L impact |
| **System Health** | WS connected · tick freshness · order latency ms · loss counter |

All panels refresh every **250 ms** via WebSocket push.

---

## API Reference

Full interactive docs: **http://localhost:8000/docs**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Phase, scenario, uptime |
| `GET` | `/api/wallet` | Balance, realized/unrealized P&L |
| `GET` | `/api/positions` | UP and DOWN position detail |
| `GET` | `/api/trades` | Paginated trade history from DB |
| `GET` | `/api/events` | Recent events from DB |
| `GET` | `/api/health` | Mode, latency, uptime |
| `POST` | `/api/mode` | Switch mode — `{"mode": "paper" \| "live"}` |
| `POST` | `/api/pause` | Halt the bot |
| `POST` | `/api/resume` | Resume after halt / circuit breaker |
| `POST` | `/api/force-exit` | Immediately emergency-exit active event |
| `POST` | `/api/paper/reset` | Reset paper wallet to initial balance |
| `WS` | `/ws` | Full `BotState` JSON pushed every 250 ms |

---

## Running Tests

```powershell
# Install dependencies (creates .venv automatically)
uv sync

# Run full test suite
uv run pytest

# Run a specific scenario
uv run pytest tests/test_s3b.py -v

# Run with output
uv run pytest -s
```

Test coverage: S1, S2, S3a, S3b, S3c, early profit exit, emergency exit, circuit breaker, profit guard (NPZ), paper engine, settlement, WebSocket push, and continuous event loop.

---

## Known Issues & Status

### Network connectivity for live mode

`AsyncSecureClient.create()` calls `clob.polymarket.com/auth/api-key` at startup. If this host is unreachable the backend exits with `ConnectTimeout`.

**Diagnose:**
```powershell
Invoke-WebRequest -Uri "https://clob.polymarket.com/markets" -TimeoutSec 10
```

If this times out, a VPN pointed at a supported region is required. Polymarket restricts trading from the United States and some other jurisdictions.

### Paper mode — credentials present

With credentials in `.env` + `MODE=paper`, the bot connects to Polymarket's public REST API for market discovery and uses polling-based price updates (2-second interval) instead of WebSocket streaming. Orders are fully simulated.

### Paper mode — no credentials

Without credentials, the dashboard loads and WebSocket connects, but no BTC events are detected and the strategy stays IDLE. Useful for UI testing only.

---

## Security

- `.env` is in `.gitignore` — **never commit it**
- Treat `POLYMARKET_PRIVATE_KEY` like a bank PIN — anyone with it controls your wallet
- Always start with `MODE=paper` to validate the setup before going live
- Use `ENTRY_QUANTITY_SHARES=5` for a ~$5 live dry-run before scaling to full size
- `.env.example` contains only placeholder keys and is safe to commit

---

*Built with Python 3.11 · FastAPI · React 18 · Vite · Tailwind CSS · polymarket-client SDK*
