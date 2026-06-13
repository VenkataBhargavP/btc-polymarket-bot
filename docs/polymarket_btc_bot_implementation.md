# Polymarket BTC 5-Minute Split-Order Trading Bot
## Complete Implementation Specification — v4.0

> **Status:** Ready for Claude Code handoff  
> **Last updated:** June 2026  
> **Target:** Personal use, paper-trade first, live-trade when validated

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack Decision](#2-tech-stack-decision)
3. [Hosting Options](#3-hosting-options)
4. [Project Structure](#4-project-structure)
5. [Environment Configuration](#5-environment-configuration)
6. [Authentication & API Client](#6-authentication--api-client)
7. [Strategy: Core Concepts](#7-strategy-core-concepts)
8. [Strategy: State Machine](#8-strategy-state-machine)
9. [Strategy: Scenario Engine](#9-strategy-scenario-engine)
10. [Strategy: Profit Guard](#10-strategy-profit-guard)
11. [Execution Layer](#11-execution-layer)
12. [Paper Trade Mode](#12-paper-trade-mode)
13. [FastAPI Backend](#13-fastapi-backend)
14. [Frontend Dashboard](#14-frontend-dashboard)
15. [Database Schema](#15-database-schema)
16. [Logging](#16-logging)
17. [Production Readiness](#17-production-readiness)
18. [Startup Scripts](#18-startup-scripts)
19. [Test Cases](#19-test-cases)
20. [Gap Resolutions & Prompt Patches](#20-gap-resolutions--prompt-patches)
21. [Build Order](#21-build-order)
22. [Requirements](#22-requirements)

---

## 1. Project Overview

A production-ready auto-trading bot for Polymarket's BTC 5-minute Up/Down prediction markets. The bot enters every window with a symmetric 50:50 split position (50 shares UP + 50 shares DOWN) using maker limit orders at $0.50 each, then manages position sizing dynamically as the market moves — trimming the losing side and locking spread on reversals — until a 0.5% profit target is reached or the window settles.

**Core principles:**
- Maker-only entry (zero fees, $0.50 both sides)
- Dynamic position sizing — winning side always holds more shares than losing side
- All scenario triggers snap to nearest 5-cent level (50¢, 55¢, 60¢, 65¢…)
- 0.5% profit target on actual cost basis — never hardcoded
- 3-loss circuit breaker with manual retrigger
- Paper mode mirrors live mode exactly — same state machine, same logic

---

## 2. Tech Stack Decision

### What Changed from v3 and Why

| Component | v3 (old prompt) | v4 (this spec) | Reason |
|---|---|---|---|
| Polymarket SDK | `py-clob-client` (legacy) | `polymarket-client` (unified beta) | New SDK has async, typed models, built-in WebSocket streams, FAK/FOK native support |
| Auth credentials | 4 keys (API key + secret + passphrase + private key) | 2 keys (private key + wallet address) | New SDK's `AsyncSecureClient` handles all signing internally |
| Order types | Manual CLOB construction | `place_limit_order()` / `place_market_order(order_type="FAK")` | Native SDK methods — no manual signing |
| Price stream | Manual WebSocket to `wss://ws-subscriptions-clob.polymarket.com` | `client.subscribe([MarketSpec(...), CryptoPricesSpec(...)])` | SDK merges both Polymarket and Binance BTC feed in one async iterator |

### Stack (final)

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Async framework | asyncio (native) | — |
| Polymarket SDK | `polymarket-client` | `0.1.0b7` |
| Web framework | FastAPI + Uvicorn | `>=0.111.0` / `>=0.29.0` |
| WebSocket push | FastAPI WebSocket | built-in |
| Database | SQLite via `aiosqlite` | `>=0.20.0` |
| Config | `pydantic-settings` | `>=2.3.0` |
| Frontend | React 18 + TypeScript + Vite | `^18.3.1` / `^5.4.5` |
| Charting | Recharts | `^2.12.7` |
| Styling | Tailwind CSS | `^3.4.3` |
| Logging | `python-json-logger` | `>=2.0.7` |

### Hardware Note — Friend's Laptop (8GB RAM, basic GPU)
This stack runs comfortably on 8GB RAM. The bot backend uses < 200MB RAM at runtime. The React frontend build requires ~500MB temporarily. No GPU usage — all computation is CPU-bound async I/O.

---

## 3. Hosting Options

### Recommended Path
**Local first → AWS Free Tier for 24/7**

#### Option A — Local (Primary, Development + Paper Trading)
Run directly on the laptop. Zero cost, zero latency to your terminal, easiest debugging.

```bash
# Start both backend and frontend
./dev.sh
```

Limitation: laptop must stay on and connected. Acceptable for paper trading and initial live testing.

#### Option B — AWS Free Tier (Primary for 24/7 Live Trading)
- **Instance:** `t2.micro` (1 vCPU, 1GB RAM) — free for 12 months
- **OS:** Ubuntu 22.04 LTS
- **What fits:** Backend only. Serve the React build as static files via Uvicorn.
- **Cost after 12 months:** ~$8.50/month (t2.micro on-demand). Consider switching to Oracle Cloud at that point.
- **Setup:** Standard EC2, open port 8000, use `systemd` service for auto-restart.

```bash
# On EC2 after SSH
sudo apt update && sudo apt install python3.11 python3-pip nodejs npm -y
git clone <your-repo>
cd btc-polymarket-bot
pip install -r requirements.txt
./start.sh
```

**Important:** Store `.env` secrets in AWS Secrets Manager or EC2 Systems Manager Parameter Store — never in the repo.

#### Option C — Oracle Cloud Free Tier (Best Long-Term Free)
- **Always free:** 2× AMD Compute VMs (1 OCPU, 1GB RAM each) — no 12-month expiry
- Better than AWS for permanent free hosting
- Same setup process as AWS EC2
- URL: cloud.oracle.com → Always Free resources

#### Option D — Railway.app
- Free tier: 500 hours/month (enough for ~20 days continuous)
- One-click deploy from GitHub
- Good for demos, not reliable for 24/7 trading
- Falls short once free hours exhaust mid-month

#### Option E — Fly.io
- Free: 3 shared VMs (256MB RAM each) — always free
- Memory is tight at 256MB; backend alone may need 512MB
- Viable with careful memory profiling; not recommended as first choice

#### Option F — Render.com
- **Do not use for this bot.** Free tier spins down after 15 minutes of inactivity. A trading bot must never have cold starts.

### Decision Matrix

| Option | Cost | Always-on | Setup effort | Recommended for |
|---|---|---|---|---|
| Local laptop | Free | Manual | None | Dev + paper trade |
| AWS Free Tier | Free (12mo) | Yes | Low | Live trading, first year |
| Oracle Cloud | Free forever | Yes | Medium | Live trading, long term |
| Railway | Free (limited) | No | Very low | Demos only |
| Fly.io | Free | Yes | Medium | Alternative to Oracle |
| Render | Free | No | Low | Not suitable |

---

## 4. Project Structure

```
btc-polymarket-bot/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # pydantic-settings config
│   ├── polymarket/
│   │   ├── __init__.py
│   │   ├── client.py              # AsyncSecureClient + AsyncPublicClient wrappers
│   │   └── models.py              # Internal models (Tick, Fill, OrderResult)
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── engine.py              # Full scenario state machine
│   │   ├── state.py               # EventState dataclass
│   │   ├── profit_guard.py        # compute_headroom() + check_profit_zone()
│   │   └── paper.py              # PaperEngine — mirrors real engine
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py       # place/cancel/status wrappers
│   │   └── position_tracker.py   # Real-time share counting
│   ├── data/
│   │   ├── __init__.py
│   │   ├── price_feed.py          # Unified WebSocket stream (Polymarket + Binance)
│   │   └── market_finder.py       # BTC 5-min market discovery + pre-load
│   ├── db/
│   │   ├── __init__.py
│   │   └── store.py               # aiosqlite schema + async helpers
│   └── api/
│       ├── __init__.py
│       ├── routes.py              # REST endpoints
│       └── ws.py                  # WebSocket push (250ms)
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── WalletPanel.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   ├── PositionTable.tsx
│   │   │   ├── StrategyStatePanel.tsx
│   │   │   ├── ProfitMeter.tsx
│   │   │   ├── TradeLog.tsx
│   │   │   ├── SystemHealth.tsx
│   │   │   └── ModeToggle.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useStrategyState.ts
│   │   └── types/
│   │       └── index.ts
│   ├── package.json
│   └── vite.config.ts
├── .env.example
├── requirements.txt
├── start.sh
├── dev.sh
└── README.md
```

---

## 5. Environment Configuration

### `.env.example`

```env
# ── Polymarket credentials (2 keys only — new SDK) ────────────────────────────
POLYMARKET_PRIVATE_KEY=              # MetaMask private key (0x...)
POLYMARKET_WALLET_ADDRESS=           # MetaMask wallet address (0x...) — optional, SDK derives it

# ── Mode ──────────────────────────────────────────────────────────────────────
MODE=paper                           # "paper" | "live"
INITIAL_PAPER_BALANCE=1000.00

# ── Strategy parameters (tune without code changes) ───────────────────────────
MOVE_THRESHOLD_POINTS=30             # Price move in cents to trigger activation
WINDOW_1_DURATION=30                 # Seconds for Window 1
ACTIVATION_TIMER=210                 # Forced activation at 3m30s
MIN_DOMINANT_PRICE=0.55              # Minimum edge at activation (55¢)
MIN_PROFIT_BUFFER=0.50               # Minimum headroom before emergency exit ($)
PRE_ENTRY_SECONDS=30                 # Seconds before window open to place entry orders
MAX_CONSECUTIVE_LOSSES=3             # Circuit breaker threshold

# ── Infrastructure ────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
DB_PATH=./bot.db
```

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    polymarket_private_key: str
    polymarket_wallet_address: str | None = None

    mode: str = "paper"
    initial_paper_balance: float = 1000.0

    move_threshold_points: int = 30
    window_1_duration: int = 30
    activation_timer: int = 210
    min_dominant_price: float = 0.55
    min_profit_buffer: float = 0.50
    pre_entry_seconds: int = 30
    max_consecutive_losses: int = 3

    log_level: str = "INFO"
    db_path: str = "./bot.db"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 6. Authentication & API Client

### Why 2 Keys Only

The new `polymarket-client` SDK (`AsyncSecureClient`) derives all necessary CLOB credentials from the MetaMask private key. The old API key / secret / passphrase pattern was for `py-clob-client`'s manual L2 signing — no longer needed.

### `polymarket/client.py`

```python
import os
from decimal import Decimal
from polymarket import AsyncPublicClient, AsyncSecureClient
from polymarket.streams import MarketSpec, CryptoPricesSpec, UserSpec
from backend.config import settings


class PolymarketClient:
    """
    Thin wrapper around AsyncSecureClient and AsyncPublicClient.
    Owns the client lifecycle — must be used as async context manager
    or explicitly closed with await client.close().
    """

    def __init__(self):
        self._public: AsyncPublicClient | None = None
        self._secure: AsyncSecureClient | None = None

    async def connect(self):
        self._public = AsyncPublicClient()
        self._secure = await AsyncSecureClient.create(
            private_key=settings.polymarket_private_key,
            wallet=settings.polymarket_wallet_address,
        )
        await self._secure.setup_trading_approvals()

    async def close(self):
        if self._secure:
            await self._secure.close()
        if self._public:
            await self._public.close()

    # ── Market discovery ──────────────────────────────────────────────────────

    async def find_btc_5min_markets(self) -> list:
        """Return all open BTC 5-minute Up/Down markets, sorted by start_date."""
        results = []
        markets = self._public.list_markets(closed=False, page_size=50)
        async for page in markets:
            for market in page.items:
                slug = market.slug or ""
                if "btc" in slug.lower() and "updown" in slug.lower().replace("-", ""):
                    results.append(market)
        return sorted(results, key=lambda m: m.state.start_date or 0)

    async def get_order_book(self, token_id: str):
        return await self._public.get_order_book(token_id=token_id)

    async def get_midpoint(self, token_id: str) -> Decimal:
        return await self._public.get_midpoint(token_id=token_id)

    # ── Order placement ───────────────────────────────────────────────────────

    async def place_limit_buy(self, token_id: str, price: str, size: str) -> str | None:
        """Place maker limit BUY order. Returns order_id or None on failure."""
        response = await self._secure.place_limit_order(
            token_id=token_id,
            side="BUY",
            price=price,
            size=size,
        )
        return response.order_id if response.ok else None

    async def place_limit_sell(self, token_id: str, price: str, size: str,
                                expiration_seconds: int = 10) -> str | None:
        """Place maker limit SELL with short expiration (FAK behaviour)."""
        import time
        response = await self._secure.place_limit_order(
            token_id=token_id,
            side="SELL",
            price=price,
            size=size,
            expiration=int(time.time()) + expiration_seconds,
        )
        return response.order_id if response.ok else None

    async def place_market_sell_fak(self, token_id: str, shares: str) -> str | None:
        """Fill-and-Kill market sell — for emergency exits and S3c bail."""
        response = await self._secure.place_market_order(
            token_id=token_id,
            side="SELL",
            shares=shares,
            order_type="FAK",
        )
        return response.order_id if response.ok else None

    async def cancel_order(self, order_id: str) -> bool:
        response = await self._secure.cancel_order(order_id=order_id)
        return bool(response.canceled)

    async def cancel_all_market_orders(self, token_id: str):
        await self._secure.cancel_market_orders(token_id=token_id)

    async def get_wallet_balance(self) -> Decimal:
        values = await self._secure.get_portfolio_values(market=[])
        return values[0].value if values else Decimal("0")

    # ── Realtime stream ───────────────────────────────────────────────────────

    async def subscribe_market_and_btc(self, up_token_id: str, down_token_id: str):
        """
        Returns a merged async stream of:
          - MarketPriceChangeEvent / MarketBestBidAskEvent for UP and DOWN tokens
          - CryptoPricesBinanceEvent for BTC/USDT spot (reference price)
        """
        stream = await self._secure.subscribe([
            MarketSpec(token_ids=[up_token_id, down_token_id]),
            CryptoPricesSpec(topic="prices.crypto.binance", symbols=["btcusdt"]),
            UserSpec(),
        ])
        return stream
```

---

## 7. Strategy: Core Concepts

### Entry

Every 5 minutes Polymarket opens a new "Bitcoin Up or Down" market. Before each window opens, the bot places **two maker limit orders simultaneously**:
- 50 shares UP @ $0.50
- 50 shares DOWN @ $0.50

Total deployed: **$50.00** (cost basis). Both orders fill at window open when the market begins at 50¢/50¢. Zero fees (maker orders).

### Profit Target

**0.5% of actual cost basis** — computed after fill, not hardcoded:

```python
state.early_profit_target = state.total_cost_basis * 1.005
# e.g. cost_basis = $50.00 → target = $50.25
```

### 5-Factor Price Snapping

All trigger levels snap to the nearest 5-cent multiple:

```python
def snap5(price: float) -> float:
    """Round to nearest 5-cent level: 0.50, 0.55, 0.60, 0.65..."""
    return round(round(price / 0.05) * 0.05, 4)
```

Examples:
- Activation at 63¢ → `snap5(0.63)` = 0.65 (bounce trigger), 0.60 (reversal trigger)
- Activation at 70¢ → reversal at 0.65, bounce at 0.70, second_dip at 0.60

### Activation Windows

| Window | When | Trigger | UI Badge |
|---|---|---|---|
| Window 1 | T=0–30s | 30pt move from 50¢ | Green — "WINDOW 1 — Ns" |
| Window 2 | T=30s–210s | 30pt move from 50¢ | Amber — "WINDOW 2 — Ns" |
| Window 3 | T=210s | Forced — any price | Blue — "TIMER — 210s" |

### Dominant vs Weak Side

At activation, whichever side is above 50¢ is **dominant**. The other is **weak**.

```python
state.dominant_side = "UP" if up_price >= down_price else "DOWN"
state.weak_side     = "DOWN" if state.dominant_side == "UP" else "UP"
```

### Position Sizing Rule

**Winning side must always hold more shares than losing side.** On every sell, the bot trims the currently losing side by more than it trims the winning side. The imbalance is what creates the profit potential at settlement.

Guard enforced on every `sell_shares()` call:
```python
assert quantity <= shares_held, "Cannot sell more than held"
after_dominant = dominant_held - (quantity if side == dom else 0)
after_weak     = weak_held     - (quantity if side == weak else 0)
assert after_dominant >= after_weak, "Sell would invert position balance"
```

### Order Types by Context

| Action | Order type | Reason |
|---|---|---|
| Entry (buy both sides) | Maker LIMIT @ $0.50 | Zero fees; fills at window open |
| Scenario sells (S1, S2, S3a, S3b) | Expiring LIMIT (10s TTL) | Maker if fills; auto-cancels if not — no stuck orders |
| Emergency exit, S3c bail | Market FAK | Must execute immediately regardless of spread |
| Settlement (dominant at 99¢) | No order — let settle | Oracle pays $1/share; weak side expires at $0 |

---

## 8. Strategy: State Machine

### `strategy/state.py`

```python
import asyncio
from dataclasses import dataclass, field


@dataclass
class EventState:
    # Identity
    event_id: str
    market_condition_id: str
    up_token_id: str
    down_token_id: str
    start_time: float
    mode: str                           # "paper" | "live"

    # Phase
    phase: str = "waiting"              # "waiting" | "active" | "closing" | "done"
    scenario: str = ""                  # "" | "S1" | "S2" | "S3a" | "S3b" | "S3c"
                                        #   | "EARLY_PROFIT" | "EXIT_NPZ"
    activation_window: int = 0          # 1, 2, or 3

    # Position tracking
    up_shares_held: float = 50.0
    down_shares_held: float = 50.0
    up_shares_sold: float = 0.0
    down_shares_sold: float = 0.0

    # Prices
    current_up_price: float = 0.0
    current_down_price: float = 0.0
    activation_up_price: float = 0.0
    activation_down_price: float = 0.0
    entry_up_price: float = 0.0
    entry_down_price: float = 0.0

    # Side identification (set at activation)
    dominant_side: str = ""             # "UP" | "DOWN"
    weak_side: str = ""
    dominant_price: float = 0.0
    weak_price: float = 0.0
    thresholds: dict = field(default_factory=dict)

    # Scenario flags — one per scenario to avoid blocking S3b→S3c
    s1_triggered: bool = False
    s2_triggered: bool = False
    s3a_triggered: bool = False         # CHANGED from v3: split into 3 flags
    s3b_triggered: bool = False
    s3c_triggered: bool = False
    s3_direction: str = ""
    bounce_count: int = 0

    # P&L
    total_cost_basis: float = 0.0
    early_profit_target: float = 0.0   # Set dynamically = cost_basis * 1.005
    realized_pnl_gross: float = 0.0    # Sum of all sell proceeds
    realized_pnl: float = 0.0          # realized_pnl_gross - total_cost_basis
    unrealized_pnl: float = 0.0
    profit_guard: dict = field(default_factory=dict)

    # Circuit breaker
    consecutive_losses: int = 0
    bot_halted: bool = False

    # Concurrency
    activation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Logs
    open_order_ids: list = field(default_factory=list)
    orders: list = field(default_factory=list)
    trade_log: list = field(default_factory=list)
    price_history: list = field(default_factory=list)   # Last 60 ticks
```

---

## 9. Strategy: Scenario Engine

### `strategy/engine.py` — Full pseudocode specification

#### Constants

```python
MOVE_THRESHOLD_POINTS = settings.move_threshold_points  # 30
WINDOW_1_DURATION     = settings.window_1_duration      # 30
ACTIVATION_TIMER      = settings.activation_timer       # 210
MIN_DOMINANT_PRICE    = settings.min_dominant_price     # 0.55
MIN_PROFIT_BUFFER     = settings.min_profit_buffer      # 0.50
PRE_ENTRY_SECONDS     = settings.pre_entry_seconds      # 30
MAX_LOSSES            = settings.max_consecutive_losses # 3
```

#### Helper: 5-factor snap

```python
def snap5(price: float) -> float:
    return round(round(price / 0.05) * 0.05, 4)
```

#### Helper: compute_thresholds

```python
def compute_thresholds(dominant_price: float) -> dict:
    """
    All levels derived from activation dominant price and snapped to 5¢.

    dominant=0.80 → reversal=0.75, bounce=0.80, second_dip=0.70, bail=0.80
    dominant=0.65 → reversal=0.60, bounce=0.65, second_dip=0.55, bail=0.65
    dominant=0.55 → reversal=0.50, bounce=0.55, second_dip=0.45, bail=0.55
    """
    weak = round(1.0 - dominant_price, 4)
    return {
        "dominant_initial":  snap5(dominant_price),
        "weak_initial_sell": snap5(weak),
        "reversal_trigger":  snap5(dominant_price - 0.05),  # S1 → S2
        "bounce_trigger":    snap5(dominant_price),          # S2 → S3a
        "second_dip":        snap5(dominant_price - 0.10),  # S2 → S3b
        "bail_trigger":      snap5(dominant_price),          # S3b → S3c
        "expiry_win":        0.99,
        "expiry_lose":       0.01,
    }
```

#### Event loop: start_event()

```python
async def start_event(state: EventState):
    # 1. Place MAKER limit orders on both sides simultaneously
    await asyncio.gather(
        buy_shares(state, side="UP",   quantity=50, price=0.50, order_type="LIMIT"),
        buy_shares(state, side="DOWN", quantity=50, price=0.50, order_type="LIMIT"),
    )

    # 2. Record actual cost basis from fill prices
    state.total_cost_basis = (
        state.up_shares_held   * state.entry_up_price +
        state.down_shares_held * state.entry_down_price
    )

    # 3. Compute dynamic profit target — strictly 0.5% of cost basis
    state.early_profit_target = round(state.total_cost_basis * 1.005, 4)

    state.phase = "waiting"

    # 4. Launch price monitor and time trigger concurrently
    await asyncio.gather(
        price_monitor(state),
        time_trigger(state),
    )
```

#### price_monitor()

```python
async def price_monitor(state: EventState):
    async with await client.subscribe_market_and_btc(
        state.up_token_id, state.down_token_id
    ) as stream:
        async for event in stream:
            if state.phase == "done":
                return

            update_prices_from_event(state, event)
            elapsed = time.time() - state.start_time

            if state.phase == "waiting":
                move = abs(state.current_up_price - 0.50)
                if move >= (MOVE_THRESHOLD_POINTS / 100):
                    window = 1 if elapsed <= WINDOW_1_DURATION else 2
                    state.activation_window = window
                    await activate(state)

            elif state.phase == "active":
                total_value = compute_total_value(state)
                if total_value >= state.early_profit_target:
                    await early_profit_exit(state)
                    return
                if not await check_profit_zone(state):
                    return
```

#### time_trigger()

```python
async def time_trigger(state: EventState):
    await asyncio.sleep(ACTIVATION_TIMER)
    if state.phase == "waiting":
        state.activation_window = 3
        await activate(state)
```

#### activate()

```python
async def activate(state: EventState):
    async with state.activation_lock:
        if state.phase != "waiting":
            return   # Already activated — lock prevents double-fire

        state.activation_up_price   = state.current_up_price
        state.activation_down_price = state.current_down_price
        state.phase = "active"

    up   = state.activation_up_price
    down = state.activation_down_price
    dominant_price = max(up, down)

    if dominant_price < MIN_DOMINANT_PRICE:
        await emergency_exit(state, reason="below_min_edge")
        return

    state.dominant_side  = "UP"   if up >= down else "DOWN"
    state.weak_side      = "DOWN" if up >= down else "UP"
    state.dominant_price = dominant_price
    state.weak_price     = round(1.0 - dominant_price, 4)
    state.thresholds     = compute_thresholds(dominant_price)

    await scenario_s1(state)
```

#### Scenario S1

```python
async def scenario_s1(state: EventState):
    """
    Sell 5 WEAK shares at current weak price.
    Then watch for: expiry win OR reversal trigger.
    """
    t    = state.thresholds
    weak = state.weak_side
    dom  = state.dominant_side

    # Sell 5 weak shares (losing side) — expiring limit (10s TTL = FAK behaviour)
    await sell_shares(state, side=weak, quantity=5,
                      price=get_side_price(state, weak), order_type="EXPIRING_LIMIT")
    state.s1_triggered = True
    state.scenario     = "S1"
    if not await check_profit_zone(state): return

    async for tick in price_stream(state):
        update_prices(state, tick)

        if compute_total_value(state) >= state.early_profit_target:
            await early_profit_exit(state); return

        # Dominant reached 99¢ — let it settle
        if get_side_price(state, dom) >= t["expiry_win"]:
            await close_winning(state, winning_side=dom); return

        # Dominant dropped to reversal level — go to S2
        if get_side_price(state, dom) <= t["reversal_trigger"] and not state.s2_triggered:
            await scenario_s2(state); return

        if not await check_profit_zone(state): return
```

#### Scenario S2

```python
async def scenario_s2(state: EventState):
    """
    Dominant dropped after S1. Sell 10 DOMINANT shares.
    Now weak side is expected winner.
    """
    t    = state.thresholds
    dom  = state.dominant_side
    weak = state.weak_side

    # Sell 10 dominant shares (now the losing side)
    await sell_shares(state, side=dom, quantity=10,
                      price=get_side_price(state, dom), order_type="EXPIRING_LIMIT")
    state.s2_triggered = True
    state.scenario     = "S2"
    if not await check_profit_zone(state): return

    async for tick in price_stream(state):
        update_prices(state, tick)

        if compute_total_value(state) >= state.early_profit_target:
            await early_profit_exit(state); return

        # Weak side reached 99¢ — let it settle
        if get_side_price(state, weak) >= t["expiry_win"]:
            await close_winning(state, winning_side=weak); return

        # Dominant bounced back to activation level → S3a
        if get_side_price(state, dom) >= t["bounce_trigger"] and not state.s3a_triggered:
            state.bounce_count += 1
            await scenario_s3a(state); return

        # Dominant dropped further to second_dip → S3b
        if get_side_price(state, dom) <= t["second_dip"] and not state.s3b_triggered:
            await scenario_s3b(state); return

        if not await check_profit_zone(state): return
```

#### Scenario S3a

```python
async def scenario_s3a(state: EventState):
    """
    After S1+S2, dominant bounced. Sell 10 more WEAK shares.
    Dominant is again expected winner.
    """
    t    = state.thresholds
    dom  = state.dominant_side
    weak = state.weak_side

    await sell_shares(state, side=weak, quantity=10,
                      price=get_side_price(state, weak), order_type="EXPIRING_LIMIT")
    state.s3a_triggered = True
    state.s3_direction  = "dominant_recovering"
    state.scenario      = "S3a"
    if not await check_profit_zone(state): return

    async for tick in price_stream(state):
        update_prices(state, tick)

        if compute_total_value(state) >= state.early_profit_target:
            await early_profit_exit(state); return

        if get_side_price(state, dom) >= t["expiry_win"]:
            await close_winning(state, winning_side=dom); return

        # Dominant dropped again → S3b
        if get_side_price(state, dom) <= t["reversal_trigger"] and not state.s3b_triggered:
            state.bounce_count += 1
            await scenario_s3b(state); return

        # Bounce count >= 2 and dominant recovered → bail to S3c
        if state.bounce_count >= 2 and get_side_price(state, dom) >= t["bail_trigger"]:
            await scenario_s3c(state); return

        if not await check_profit_zone(state): return
```

#### Scenario S3b

```python
async def scenario_s3b(state: EventState):
    """
    After S1+S2, dominant dropped again. Sell 15 more DOMINANT shares.
    Weak side is now expected winner.
    """
    t    = state.thresholds
    dom  = state.dominant_side
    weak = state.weak_side

    await sell_shares(state, side=dom, quantity=15,
                      price=get_side_price(state, dom), order_type="EXPIRING_LIMIT")
    state.s3b_triggered = True                  # FIXED: own flag, not s3_triggered
    state.s3_direction  = "weak_recovering"
    state.scenario      = "S3b"
    if not await check_profit_zone(state): return

    async for tick in price_stream(state):
        update_prices(state, tick)

        if compute_total_value(state) >= state.early_profit_target:
            await early_profit_exit(state); return

        if get_side_price(state, weak) >= t["expiry_win"]:
            await close_winning(state, winning_side=weak); return

        # Dominant recovered → bail to S3c (uses s3b_triggered, not s3_triggered)
        if get_side_price(state, dom) >= t["bail_trigger"] and not state.s3c_triggered:
            state.bounce_count += 1
            if state.bounce_count >= 2:
                await scenario_s3c(state); return

        if not await check_profit_zone(state): return
```

#### Scenario S3c — Bail

```python
async def scenario_s3c(state: EventState):
    """
    Back-and-forth exhausted. No profitable resolution identified.
    Exit ALL remaining shares immediately at market (FAK).
    Accept small loss. Move to next event.
    """
    dom  = state.dominant_side
    weak = state.weak_side

    await asyncio.gather(
        sell_shares(state, side=dom,  quantity=get_shares_held(state, dom),
                    price=get_side_price(state, dom),  order_type="MARKET_FAK"),
        sell_shares(state, side=weak, quantity=get_shares_held(state, weak),
                    price=get_side_price(state, weak), order_type="MARKET_FAK"),
    )
    state.s3c_triggered = True
    state.scenario      = "S3c"
    state.phase         = "done"
```

#### Early Profit Exit

```python
async def early_profit_exit(state: EventState):
    """
    Total value crossed early_profit_target (cost_basis × 1.005).
    Sell both sides simultaneously — this is a profit grab.
    """
    state.phase = "done"   # Set first — prevents any further scenario logic

    await asyncio.gather(
        sell_shares(state, side="UP",   quantity=state.up_shares_held,
                    price=state.current_up_price,   order_type="EXPIRING_LIMIT"),
        sell_shares(state, side="DOWN", quantity=state.down_shares_held,
                    price=state.current_down_price, order_type="EXPIRING_LIMIT"),
    )
    state.scenario = "EARLY_PROFIT"
```

#### Close Winning (Settlement)

```python
async def close_winning(state: EventState, winning_side: str):
    """
    Dominant hit 99¢. Do NOT place sell orders.
    Cancel any open orders on both sides and let oracle settle:
      - Winning shares → $1.00 each (oracle payout)
      - Weak shares    → $0.00 each (expire worthless — acceptable)
    Sequential cancel to protect winning side first.
    """
    state.phase = "done"   # Set first

    # Cancel any resting limit orders to prevent stale fills
    await client.cancel_all_market_orders(state.up_token_id)
    await client.cancel_all_market_orders(state.down_token_id)

    state.scenario = "CLOSE_WIN"
    # No sell orders placed — oracle settlement handles payout
```

#### Emergency Exit

```python
async def emergency_exit(state: EventState, reason: str):
    """
    Triggered when:
      - Headroom <= MIN_PROFIT_BUFFER (no-profit-zone)
      - Dominant price < MIN_DOMINANT_PRICE at activation
      - Expiry < 30s and phase != "done"
    Sells all remaining shares at market (FAK).
    Higher-value side sold first to protect most value.
    """
    state.phase = "done"   # Set first

    dom   = state.dominant_side or "UP"
    weak  = state.weak_side     or "DOWN"
    dom_q = get_shares_held(state, dom)
    wq    = get_shares_held(state, weak)
    dom_v = dom_q * get_side_price(state, dom)
    wv    = wq    * get_side_price(state, weak)

    if dom_v >= wv:
        await sell_shares(state, side=dom,  quantity=dom_q, order_type="MARKET_FAK")
        await sell_shares(state, side=weak, quantity=wq,    order_type="MARKET_FAK")
    else:
        await sell_shares(state, side=weak, quantity=wq,    order_type="MARKET_FAK")
        await sell_shares(state, side=dom,  quantity=dom_q, order_type="MARKET_FAK")

    state.scenario = "EXIT_NPZ"
```

#### sell_shares() — Position accounting

```python
async def sell_shares(state: EventState, side: str, quantity: float,
                       price: float, order_type: str):
    """
    Places sell order and updates state on confirmed fill.
    Guards: quantity <= held AND winning_held > losing_held after sell.
    """
    dom  = state.dominant_side or side
    weak = state.weak_side     or ("DOWN" if side == "UP" else "UP")

    # Guard 1: cannot sell more than held
    held = get_shares_held(state, side)
    quantity = min(quantity, held)
    if quantity <= 0:
        return

    # Guard 2: winning side must hold more shares than losing after sell
    after_dom  = state.up_shares_held   if dom == "UP"  else state.down_shares_held
    after_weak = state.up_shares_held   if weak == "UP" else state.down_shares_held
    if side == dom:
        after_dom  -= quantity
    else:
        after_weak -= quantity

    if after_dom < after_weak:
        # Reduce quantity to maintain imbalance
        quantity = held - (get_shares_held(state, dom if side != dom else weak))
        if quantity <= 0:
            return

    # Place order via execution layer
    fill_price = await order_manager.sell(
        token_id=get_token_id(state, side),
        quantity=quantity,
        price=price,
        order_type=order_type,
    )

    if fill_price is not None:
        # Update state
        state.realized_pnl_gross += quantity * fill_price
        state.realized_pnl        = state.realized_pnl_gross - state.total_cost_basis
        if side == "UP":
            state.up_shares_held -= quantity
            state.up_shares_sold += quantity
        else:
            state.down_shares_held -= quantity
            state.down_shares_sold += quantity

        state.trade_log.append({
            "ts": time.time(), "action": "SELL", "side": side,
            "shares": quantity, "price": fill_price,
            "pnl_impact": quantity * (fill_price - 0.50),
            "scenario": state.scenario,
        })
```

---

## 10. Strategy: Profit Guard

### `strategy/profit_guard.py`

```python
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
    dom       = state.dominant_side
    weak      = state.weak_side
    dom_held  = state.up_shares_held   if dom  == "UP" else state.down_shares_held
    weak_held = state.up_shares_held   if weak == "UP" else state.down_shares_held

    best_future    = (dom_held * 0.99) + (weak_held * 0.01)
    max_rec        = state.realized_pnl_gross + best_future
    headroom       = max_rec - state.total_cost_basis
    in_zone        = headroom > MIN_PROFIT_BUFFER

    return {
        "realized":        round(state.realized_pnl_gross, 4),
        "best_future":     round(best_future, 4),
        "max_recoverable": round(max_rec, 4),
        "cost_basis":      round(state.total_cost_basis, 4),
        "headroom":        round(headroom, 4),
        "in_profit_zone":  in_zone,
    }


async def check_profit_zone(state) -> bool:
    """Idempotent — safe to call multiple times per tick."""
    if state.phase == "done":
        return True   # Already exiting, don't re-trigger
    result = compute_headroom(state)
    state.profit_guard = result
    if not result["in_profit_zone"]:
        from backend.strategy.engine import emergency_exit
        await emergency_exit(state, reason="no_profit_zone")
        return False
    return True
```

---

## 11. Execution Layer

### `execution/order_manager.py`

```python
class OrderManager:
    def __init__(self, client: PolymarketClient, paper_mode: bool = True):
        self._client = client
        self._paper  = paper_mode
        self._open_orders: dict[str, str] = {}   # order_id → side

    async def buy(self, token_id: str, quantity: float,
                   price: float, order_type: str = "LIMIT") -> float | None:
        if self._paper:
            return price   # Instant fill at requested price in paper mode

        for attempt in range(3):
            order_id = await self._client.place_limit_buy(
                token_id=token_id,
                price=str(price),
                size=str(int(quantity)),
            )
            if order_id:
                self._open_orders[order_id] = "BUY"
                return price
            await asyncio.sleep(0.5 * (2 ** attempt))   # Exponential backoff

        return None   # 3 attempts failed

    async def sell(self, token_id: str, quantity: float,
                    price: float, order_type: str = "EXPIRING_LIMIT") -> float | None:
        if self._paper:
            return price

        if order_type == "MARKET_FAK":
            order_id = await self._client.place_market_sell_fak(
                token_id=token_id,
                shares=str(int(quantity)),
            )
        else:
            # Expiring limit (10s TTL) — FAK behaviour without taker fee
            order_id = await self._client.place_limit_sell(
                token_id=token_id,
                price=str(price),
                size=str(int(quantity)),
                expiration_seconds=10,
            )

        if order_id:
            self._open_orders[order_id] = "SELL"
            return price
        return None
```

### `data/market_finder.py`

```python
class MarketFinder:
    """
    Discovers upcoming BTC 5-min markets and schedules entry at T-30s.
    Pre-loads the next event when current event has < 60s remaining.
    """

    def __init__(self, client: PolymarketClient):
        self._client   = client
        self._upcoming: list = []

    async def run_loop(self):
        while True:
            self._upcoming = await self._client.find_btc_5min_markets()
            await asyncio.sleep(30)   # Poll every 30s

    def get_next_market(self) -> dict | None:
        now = time.time()
        for market in self._upcoming:
            start_ts = market.state.start_date.timestamp() if market.state.start_date else 0
            if start_ts > now:
                up_token   = market.outcomes.yes.token_id
                down_token = market.outcomes.no.token_id
                return {
                    "event_id":    str(market.id),
                    "condition_id": str(market.condition_id),
                    "up_token_id":  str(up_token),
                    "down_token_id": str(down_token),
                    "start_ts":     start_ts,
                    "seconds_until": start_ts - now,
                }
        return None

    async def wait_and_enter(self, engine) -> None:
        """Wait until T-30s, verify balance, then fire entry orders."""
        while True:
            next_mkt = self.get_next_market()
            if next_mkt and next_mkt["seconds_until"] <= PRE_ENTRY_SECONDS:
                balance = await self._client.get_wallet_balance()
                if float(balance) >= 50.0:
                    await engine.start_event_from_market(next_mkt)
                else:
                    log.warning("Insufficient balance — skipping window",
                                extra={"balance": float(balance)})
                await asyncio.sleep(300)   # Wait a full 5-min cycle before next
            else:
                await asyncio.sleep(1)
```

---

## 12. Paper Trade Mode

### `strategy/paper.py`

```python
class PaperEngine:
    """
    Mirrors StrategyEngine exactly.
    Fills are instant at current mid-price — no real API calls.
    Wallet is in-memory; persists to DB for session continuity.
    Switchable to live via MODE env var with zero code changes.
    """

    def __init__(self, initial_balance: float = 1000.0):
        self.balance    = initial_balance
        self.positions  = {}   # token_id → shares
        self.trade_log  = []

    def buy(self, side: str, quantity: float, price: float) -> float:
        cost = quantity * price
        self.balance -= cost
        self.positions[side] = self.positions.get(side, 0) + quantity
        return price   # Instant fill

    def sell(self, side: str, quantity: float, price: float) -> float:
        proceeds = quantity * price
        self.balance += proceeds
        self.positions[side] = max(0, self.positions.get(side, 0) - quantity)
        return price

    def reset(self, balance: float = 1000.0):
        self.balance   = balance
        self.positions = {}
        self.trade_log = []
```

---

## 13. FastAPI Backend

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Mode, phase, scenario, wallet, uptime |
| `GET` | `/api/wallet` | USDC balance, unrealized P&L, realized P&L |
| `GET` | `/api/positions` | Open positions with entry, current price, P&L |
| `GET` | `/api/trades` | Paginated trade history from SQLite |
| `GET` | `/api/events` | Recent events with outcome and scenario path |
| `POST` | `/api/mode` | `{ "mode": "paper" \| "live" }` hot-swap |
| `POST` | `/api/pause` | Finish current event, halt next |
| `POST` | `/api/resume` | Resume after pause or circuit breaker |
| `GET` | `/api/health` | WS status, last tick age ms, order latency ms |

### WebSocket Payload (pushed every 250ms)

```json
{
  "ts": 1718000000000,
  "mode": "paper",
  "phase": "active",
  "scenario": "S1",
  "activation_window": 1,
  "elapsed_seconds": 12.4,
  "event_id": "...",
  "event_expires_in": 142,
  "up_price": 0.81,
  "down_price": 0.19,
  "dominant_side": "UP",
  "weak_side": "DOWN",
  "up_shares_held": 50,
  "down_shares_held": 45,
  "up_shares_sold": 0,
  "down_shares_sold": 5,
  "realized_pnl": 1.00,
  "unrealized_pnl": 15.50,
  "realized_pnl_gross": 1.00,
  "total_cost_basis": 50.00,
  "early_profit_target": 50.25,
  "current_total_value": 50.31,
  "profit_to_target": 0.19,
  "wallet_balance": 985.00,
  "consecutive_losses": 0,
  "bot_halted": false,
  "profit_guard": {
    "headroom": 1.45,
    "max_recoverable": 51.45,
    "cost_basis": 50.00,
    "in_profit_zone": true
  },
  "trade_log": [],
  "price_history": [],
  "health": {
    "ws_connected": true,
    "last_tick_ms": 48,
    "order_latency_ms": 210
  }
}
```

---

## 14. Frontend Dashboard

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: BTC Bot [PAPER] ─── 04:23 ──────── [Pause] [WS ●]     │
├──────────────────────┬──────────────────────────────────────────┤
│                      │ Wallet: Balance | Realized | Unrealized  │
│                      ├──────────────────────────────────────────┤
│  Price Chart         │ Strategy State Panel                     │
│  (UP green,          │  Phase: ACTIVE | Scenario: S1            │
│   DOWN red)          │  Window: WINDOW 1 — 12s                  │
│  Recharts AreaChart  │  Position Table: UP/DOWN shares + P&L    │
│  Last 60 ticks       │  Sell Ladder: completed sells            │
│  Auto-scroll         ├──────────────────────────────────────────┤
│                      │ Profit Meter                             │
│                      │  $50.00 ────███░░░░ $50.25              │
│                      │  Headroom: ██ $1.45 (green)             │
├──────────────────────┴──────────────────────────────────────────┤
│ Trade Log (last 20)  │ System Health                            │
│ ts | action | side   │ WS: connected | Tick: 48ms              │
│ | shares | price | $ │ Market: [event_id] | expires: 2:22      │
│                      │ [PAPER / LIVE toggle] [Reset paper]     │
└──────────────────────┴──────────────────────────────────────────┘
```

### Component Behaviors

**Header:** Countdown turns red + pulses when < 30s. Mode badge: amber=PAPER, red-pulse=LIVE.

**Profit Meter:** Progress bar animates from cost_basis toward early_profit_target. Turns gold and pulses on crossing target. Headroom sub-bar: green > $2.00, amber $0.50–$2.00, red ≤ $0.50 (flashes + "NO PROFIT ZONE" banner).

**Trade Log colors:** BUY=blue, SELL=amber, EARLY_PROFIT=gold, CLOSE_WIN=green, EXIT_NPZ=red, S3c=grey.

**Toast notifications:** 3s top-right toast on every scenario change.

**Emergency banners:**
- "NO PROFIT ZONE — EXITING" — red full-width flash
- "EARLY PROFIT — EXITING" — gold full-width flash
- "CIRCUIT BREAKER — 3 LOSSES — BOT HALTED" — red persistent banner until manual resume

**Circuit breaker UI:** When `bot_halted = true`, disable all controls except `POST /api/resume`. Show persistent red banner.

---

## 15. Database Schema

```sql
CREATE TABLE events (
  id                  TEXT PRIMARY KEY,
  condition_id        TEXT,
  start_ts            INTEGER,
  end_ts              INTEGER,
  mode                TEXT,
  activation_window   INTEGER,
  activation_up_price REAL,
  activation_down_price REAL,
  dominant_side       TEXT,
  outcome             TEXT,          -- "EARLY_PROFIT"|"CLOSE_WIN"|"EXIT_NPZ"|"S3c"
  scenario_path       TEXT,          -- e.g. "S1→S2→S3b→EXIT_NPZ"
  realized_pnl        REAL,
  cost_basis          REAL,
  early_profit_target REAL,
  trade_count         INTEGER,
  consecutive_losses  INTEGER        -- snapshot at event close
);

CREATE TABLE trades (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id    TEXT,
  ts          INTEGER,
  action      TEXT,                  -- "BUY"|"SELL"|"CLOSE"|"EARLY_PROFIT"|"EXIT_NPZ"
  side        TEXT,                  -- "UP"|"DOWN"
  shares      REAL,
  price       REAL,
  total_value REAL,
  order_id    TEXT,
  mode        TEXT,
  scenario    TEXT
);

CREATE TABLE price_ticks (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT,
  ts       INTEGER,
  up_price REAL,
  down_price REAL
);

CREATE TABLE bot_state (
  key   TEXT PRIMARY KEY,
  value TEXT                         -- JSON — persists consecutive_losses, halted flag
);
```

---

## 16. Logging

Use `python-json-logger`. Every entry includes:

```json
{
  "timestamp": "2026-06-13T10:30:00Z",
  "level": "INFO",
  "module": "engine",
  "event_id": "btc-updown-5m-1718000000",
  "scenario": "S1",
  "action": "SELL",
  "side": "DOWN",
  "shares": 5,
  "price": 0.35,
  "elapsed_seconds": 14.2,
  "activation_window": 1,
  "latency_ms": 210,
  "headroom": 1.45
}
```

| Level | When |
|---|---|
| `DEBUG` | Every price tick |
| `INFO` | Order placed, scenario change, phase change, activation |
| `WARNING` | WS reconnect, order retry, near-expiry forced exit, no-profit-zone, early profit, circuit breaker triggered |
| `ERROR` | Order failure after 3 retries, auth failure, market not found |

Output: stdout (container-compatible) + `backend/logs/bot.log` (daily rotation, 7-day retention).

---

## 17. Production Readiness

- All state mutation behind `asyncio.Lock` — no race conditions
- No blocking I/O anywhere in async path
- Order deduplication: never re-place an already-open order_id
- WS watchdog: WARNING at 3s no-tick, reconnect with exponential backoff (1s, 2s, 4s, max 30s) at 10s no-tick
- Startup health checks: API keys present, wallet balance > 0, at least one upcoming market found — fail fast with clear error message
- Polymarket `RateLimitError`: automatic exponential backoff (caught via SDK exception class)
- Graceful shutdown on `SIGTERM`: finish current event close orders, then exit
- `check_profit_zone()` is idempotent — safe to call multiple times per tick
- `early_profit_exit()` and `emergency_exit()` both set `phase="done"` as first action
- Expiry watchdog: if `seconds_remaining < 30` and `phase != "done"` → call `emergency_exit(reason="expiry_approaching")`
- Circuit breaker: `consecutive_losses` counter; on 3rd loss set `bot_halted=True`, log WARNING, persist to `bot_state` table, notify (stub — wire up later); resume only on `POST /api/resume`
- Settlement confirmation: after `close_winning()`, poll wallet balance until it reflects oracle payout before starting next event

---

## 18. Startup Scripts

### `start.sh` (production)

```bash
#!/bin/bash
set -e
pip install -r requirements.txt --quiet
cd frontend && npm install --silent && npm run build && cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 &
echo "Bot running → http://localhost:8000"
```

### `dev.sh` (hot reload)

```bash
#!/bin/bash
trap 'kill %1 %2' EXIT

uvicorn backend.main:app --reload --port 8000 &
cd frontend && npm run dev -- --port 5173 &

wait
```

---

## 19. Test Cases

All test cases must be covered. Paper mode must be used for all tests before going live.

### Group A — Entry Tests

| ID | Test | Expected |
|---|---|---|
| A1 | Wallet balance ≥ $50 → entry at T-30s | Both maker limit orders placed at $0.50 simultaneously |
| A2 | Wallet balance < $50 at T-30s | Window skipped; log WARNING; next window attempted |
| A3 | Entry fills verified after window opens | `total_cost_basis` recorded; `early_profit_target = cost_basis × 1.005` set |
| A4 | Bot halted (circuit breaker) at T-30s | No entry placed; halt banner shown |

### Group B — Activation Tests

| ID | Test | Expected |
|---|---|---|
| B1 | 30pt UP move in T=0–30s | Window 1 activation; dominant=UP |
| B2 | 30pt DOWN move in T=0–30s | Window 1 activation; dominant=DOWN |
| B3 | 30pt move in T=31–209s | Window 2 activation |
| B4 | No 30pt move; T=210s reached | Window 3 forced activation |
| B5 | Activation price < 55¢ (dominant) | `emergency_exit(reason="below_min_edge")` fired |
| B6 | Race: price_monitor and time_trigger fire simultaneously | Lock ensures only one activation fires |

### Group C — Scenario S1 Tests

| ID | Test | Expected |
|---|---|---|
| C1 | S1 fires immediately at activation | 5 WEAK shares sold via expiring limit at current weak price |
| C2 | After S1, dominant continues rising to 99¢ | `close_winning()` → cancel open orders, let settle |
| C3 | After S1, early_profit_target crossed | `early_profit_exit()` — both sides sold simultaneously |
| C4 | After S1, dominant drops to reversal_trigger (snap5 level) | S2 triggered |
| C5 | After S1, sell order doesn't fill in 10s | Order auto-cancels (TTL); state unchanged; monitoring continues |

### Group D — Scenario S2 Tests

| ID | Test | Expected |
|---|---|---|
| D1 | S2 fires on reversal — 10 DOMINANT shares sold | Position: dom_held reduced by 10 |
| D2 | After S2, weak reaches 99¢ | `close_winning(winning_side=weak)` |
| D3 | After S2, early_profit_target crossed | `early_profit_exit()` |
| D4 | After S2, dominant bounces to bounce_trigger | S3a triggered; `bounce_count = 1` |
| D5 | After S2, dominant drops to second_dip | S3b triggered |
| D6 | After S2, dominant near bounce_trigger (63¢) but not crossing (target snapped to 65¢) | Bot waits in S2; S3a not triggered until 65¢ crossed |
| D7 | After S2, price stays between second_dip and bounce_trigger | Bot holds in S2; no further sells |

### Group E — Scenario S3a Tests

| ID | Test | Expected |
|---|---|---|
| E1 | S3a fires on bounce — 10 WEAK shares sold | weak_held reduced by 10 |
| E2 | After S3a, dominant reaches 99¢ | `close_winning(dominant)` |
| E3 | After S3a, dominant drops to reversal_trigger again | S3b triggered; `bounce_count = 2` |
| E4 | After S3a, `bounce_count >= 2` and dominant at bail_trigger | S3c bail triggered |
| E5 | After S3a, early_profit_target crossed | `early_profit_exit()` |

### Group F — Scenario S3b Tests

| ID | Test | Expected |
|---|---|---|
| F1 | S3b fires — 15 DOMINANT shares sold | dom_held reduced by 15 |
| F2 | After S3b, weak reaches 99¢ | `close_winning(weak)` |
| F3 | After S3b, dominant recovers to bail_trigger; bounce_count ≥ 2 | S3c triggered (uses `s3b_triggered` flag — FIXED) |
| F4 | After S3b, dominant recovers to bail_trigger; bounce_count < 2 | No S3c yet; bounce_count incremented; continue watching |
| F5 | After S3b, early_profit_target crossed | `early_profit_exit()` |

### Group G — Scenario S3c Tests

| ID | Test | Expected |
|---|---|---|
| G1 | S3c fires — all remaining shares sold FAK simultaneously | `phase = "done"`; both sides exited; loss recorded |
| G2 | S3c sell partially fills (FAK) | Filled portion recorded; remainder auto-cancelled |

### Group H — Profit Guard Tests

| ID | Test | Expected |
|---|---|---|
| H1 | After S1 sell — headroom still > $0.50 | Continue in S1 |
| H2 | After any sell — headroom ≤ $0.50 | `emergency_exit(reason="no_profit_zone")` |
| H3 | headroom check on every price tick in active phase | No-profit-zone detected mid-scenario |
| H4 | `check_profit_zone()` called when `phase="done"` | Returns True immediately — no re-trigger |
| H5 | Position after multiple sells has dom_held < weak_held | Position sizing guard prevents sell; quantity reduced |

### Group I — Early Profit Tests

| ID | Test | Expected |
|---|---|---|
| I1 | `current_total_value >= early_profit_target` in S1 | `early_profit_exit()` fires |
| I2 | `current_total_value >= early_profit_target` in S2 | `early_profit_exit()` fires |
| I3 | `current_total_value >= early_profit_target` in S3a/S3b | `early_profit_exit()` fires |
| I4 | early_profit_target is 0.5% of actual cost basis | Target = $50.25 when cost_basis = $50.00 |

### Group J — Emergency Exit Tests

| ID | Test | Expected |
|---|---|---|
| J1 | `expiry_approaching` (< 30s, not done) | All shares sold FAK; higher-value side first |
| J2 | `below_min_edge` at activation | All shares sold FAK immediately |
| J3 | `no_profit_zone` headroom breached | All shares sold FAK; scenario = "EXIT_NPZ" |
| J4 | Emergency exit when no dominant side set yet | Defaults to UP/DOWN; exits cleanly |

### Group K — Circuit Breaker Tests

| ID | Test | Expected |
|---|---|---|
| K1 | 1st loss event | `consecutive_losses = 1`; trading continues |
| K2 | 2nd loss event | `consecutive_losses = 2`; trading continues |
| K3 | 3rd consecutive loss event | `consecutive_losses = 3`; `bot_halted = True`; notification stub called; no new entries |
| K4 | Win event resets counter | `consecutive_losses = 0` |
| K5 | `POST /api/resume` received while halted | `bot_halted = False`; `consecutive_losses = 0`; trading resumes |

### Group L — Settlement Tests

| ID | Test | Expected |
|---|---|---|
| L1 | Dominant hits 99¢ — close_winning() | Open orders cancelled; both sides held to oracle settlement |
| L2 | Weak shares expire at $0 | No sell order placed; loss on weak shares accepted |
| L3 | Settlement confirmed in wallet | Balance updated; next event entry allowed |

### Group M — Continuous Operation Tests

| ID | Test | Expected |
|---|---|---|
| M1 | Event ends at `phase="done"` | `market_finder` immediately queues next event |
| M2 | Next event starts in < 30s | Entry orders placed correctly at T-30s of next window |
| M3 | Previous settlement not confirmed; balance < $50 | Next window skipped; log WARNING |
| M4 | 10 consecutive windows — no memory leak | State object is fresh per event; no accumulated state |

### Group N — WebSocket & Connection Tests

| ID | Test | Expected |
|---|---|---|
| N1 | No price tick for 3s | WARNING logged; UI shows "stale" tick indicator |
| N2 | No price tick for 10s | Reconnect with exponential backoff; bot resumes |
| N3 | WS reconnect during active scenario | State preserved; scenario resumes from last known price |
| N4 | Multiple reconnects in one event | Max 30s backoff; ERROR logged after repeated failures |

### Group O — Paper Mode Tests

| ID | Test | Expected |
|---|---|---|
| O1 | All scenarios A–N run in paper mode | Identical logic; fills instant at mid-price; no real orders |
| O2 | Paper wallet reset | Balance returns to `INITIAL_PAPER_BALANCE`; positions cleared |
| O3 | Switch paper → live via `POST /api/mode` | Next event uses live orders; current event finishes in paper |

---

## 20. Gap Resolutions & Prompt Patches

These are the 12 gaps identified during review of v3 and the exact code-level fixes applied in this v4 specification.

### G1 — Entry Order Type (Critical → Closed)
**Problem:** `buy_shares()` called without specifying order type; could default to taker/market.  
**Fix:** All entry buys use `order_type="LIMIT"` at exactly `price=0.50`. Explicit in `start_event()`.

### G2 — Partial Fill on Entry (Critical → Closed — Non-issue)
**Problem:** Partial fill would create unbalanced position.  
**Resolution:** Non-issue by design. Maker limit orders at $0.50 on both sides fill at window open when the market initializes at exactly 50¢/50¢. Symmetric fill is guaranteed by market structure.

### G3 — Bounce Trigger Near-Miss (High → Closed)
**Problem:** `bounce_trigger` required exact cross of activation price; near-misses left bot frozen in S2.  
**Fix:** All thresholds computed via `snap5()` — rounded to nearest 5¢. Example: activation at 63¢ → bounce_trigger snaps to 65¢, reversal_trigger snaps to 60¢. No near-miss possible.

### G4 — Sell Order Type (High → Closed)
**Problem:** Sell orders untyped — risk of stuck orders at expiry.  
**Fix:**  
- Scenario sells (S1, S2, S3a, S3b): `EXPIRING_LIMIT` with 10s TTL (maker if fills, auto-cancels if not)  
- Emergency exits and S3c: `MARKET_FAK` (must execute immediately)  
- Settlement (99¢): no sell orders — let oracle settle

### G5 — Reversal Crossback Threshold (Medium → Closed)
**Problem:** 55¢ crossback rule was specific to 60¢ activation; behavior at other activation prices unclear.  
**Fix:** Q1 confirmed: crossback trigger = `dominant_price - 0.05` snapped to 5¢. At 70¢ activation → crossback at 65¢. Universal 5-factor snap makes this consistent at any activation price.

### G6 — Pre-Event Entry Timing (Medium → Closed)
**Problem:** No timing defined for when to place entry orders.  
**Fix:** Entry orders placed at **T-30 seconds** before window open. Pre-condition: previous settlement confirmed and balance ≥ $50. Configurable via `PRE_ENTRY_SECONDS` env var.

### G7 — S3b → S3c Bail Path Blocked (High → Closed)
**Problem:** Single `s3_triggered` flag was already `True` when entering S3b, blocking S3c bail check.  
**Fix:** Three dedicated flags: `s3a_triggered`, `s3b_triggered`, `s3c_triggered`. S3b's bail check uses `not state.s3c_triggered` — always works correctly.

### G8 — `await_fill_or_market()` Undefined (Critical → Closed — Simplified)
**Problem:** Function was called in `close_winning()` but never defined.  
**Fix:** `close_winning()` does not place any sell orders. It cancels open orders and sets `phase="done"`. Oracle handles payout: winning shares → $1, weak shares → $0 (accepted loss).

### G9 — Oversell Guard (Medium → Closed)
**Problem:** Nothing prevented selling more shares than held.  
**Fix:** `sell_shares()` enforces: (1) `quantity = min(quantity, held)`, (2) after-sell `dominant_held >= weak_held`. Quantity reduced automatically if needed to maintain position imbalance.

### G10 — Continuous Operation (Medium → Closed)
**Problem:** No event handoff logic defined.  
**Fix:** `market_finder.wait_and_enter()` runs continuously. After each event closes, it waits for settlement confirmation and balance check, then enters the next window at T-30s.

### G11 — Hardcoded Profit Target (Medium → Closed)
**Problem:** `EARLY_PROFIT_TARGET = $50.50` was hardcoded; incorrect if fills varied.  
**Fix:** `state.early_profit_target = state.total_cost_basis * 1.005` — computed from actual fill prices after entry. Strictly 0.5% — not a fixed dollar amount. Removed from `.env`.

### G12 — Window 3 No-Move Behaviour (Medium → Closed)
**Problem:** Forced activation at T=210s with price at 50¢ would always immediately emergency-exit.  
**Fix:** This is correct behaviour. If no move in 3.5 minutes, activation fires → dominant < MIN_DOMINANT_PRICE → `emergency_exit(reason="below_min_edge")` → shares sold at market → settlement. System auto-continues to next window.

---

## 21. Build Order

Build strictly in this sequence. After each backend file: verify clean import. After frontend: verify `npm run build` passes with zero TypeScript errors.

```
1.  backend/config.py + .env.example
2.  backend/db/store.py
3.  backend/polymarket/models.py + client.py
4.  backend/data/price_feed.py + market_finder.py
5.  backend/strategy/state.py
6.  backend/strategy/profit_guard.py
7.  backend/strategy/engine.py
8.  backend/strategy/paper.py
9.  backend/execution/order_manager.py + position_tracker.py
10. backend/api/routes.py + ws.py
11. backend/main.py
12. frontend/src/types/index.ts
13. frontend/src/hooks/useWebSocket.ts + useStrategyState.ts
14. frontend/src/components/ (all — Header last)
15. frontend/src/App.tsx + main.ts
16. start.sh + dev.sh + README.md
```

Do not abbreviate or stub any file. Every file must be complete and production-ready.

---

## 22. Requirements

### `requirements.txt`

```
polymarket-client>=0.1.0b7
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
websockets>=12.0
aiohttp>=3.9.0
aiosqlite>=0.20.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
python-json-logger>=2.0.7
```

### `frontend/package.json` (dependencies)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.7",
    "lucide-react": "^0.383.0"
  },
  "devDependencies": {
    "typescript": "^5.4.5",
    "vite": "^5.2.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.3",
    "autoprefixer": "latest",
    "postcss": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest"
  }
}
```

---

*End of specification. Paste into Claude Code and run `./dev.sh` to begin.*
