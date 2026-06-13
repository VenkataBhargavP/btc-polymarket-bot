# BTC Polymarket Bot v4.0

A production-ready auto-trading bot for Polymarket's BTC 5-minute Up/Down prediction markets.

## Quick Start

### Paper Mode (default — safe, no real orders)

```bash
# Copy environment template
cp .env.example .env

# Start everything (builds frontend first)
./start.sh
```

Open http://localhost:8000

### Development (hot reload)

```bash
./dev.sh
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### Live Mode

1. Edit `.env`: set `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_WALLET_ADDRESS`, `MODE=live`
2. Run `./start.sh`

## Architecture

```
btc-polymarket-bot/
├── backend/
│   ├── main.py              # FastAPI + lifespan startup
│   ├── config.py            # pydantic-settings (reads .env)
│   ├── polymarket/client.py # polymarket-client SDK wrapper
│   ├── strategy/engine.py   # Full scenario state machine (S1→S2→S3a/S3b→S3c)
│   ├── strategy/state.py    # EventState dataclass
│   ├── strategy/profit_guard.py  # Headroom calculator
│   ├── strategy/paper.py    # Paper wallet (mirrors live exactly)
│   ├── execution/order_manager.py  # Buy/sell dispatcher
│   ├── data/market_finder.py  # BTC 5-min market discovery
│   ├── db/store.py          # SQLite persistence
│   └── api/routes.py + ws.py  # REST + WebSocket push (250ms)
└── frontend/src/            # React 18 + TypeScript + Tailwind
```

## Strategy

1. **Entry**: Place 50 shares UP + 50 shares DOWN at $0.50 (maker limits, zero fee)
2. **Activation**: At 30pt price move or T=210s — identify dominant side
3. **S1**: Sell 5 weak shares (expiring limit, 10s TTL)
4. **S2**: If dominant reverses — sell 10 dominant shares
5. **S3a/S3b/S3c**: Handle bounces; bail to FAK on excessive churn
6. **Exit**: Early profit (0.5% of cost basis), close winning (99¢ oracle), or emergency FAK

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POLYMARKET_PRIVATE_KEY` | — | MetaMask private key (live only) |
| `MODE` | `paper` | `paper` or `live` |
| `INITIAL_PAPER_BALANCE` | `1000.00` | Paper wallet starting balance |
| `MOVE_THRESHOLD_POINTS` | `30` | Cents of move to trigger activation |
| `MIN_DOMINANT_PRICE` | `0.55` | Min edge at activation |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Circuit breaker threshold |

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Mode, phase, scenario |
| `GET` | `/api/wallet` | Balance, P&L |
| `GET` | `/api/positions` | Open positions |
| `GET` | `/api/trades` | Trade history |
| `POST` | `/api/mode` | Hot-swap paper/live |
| `POST` | `/api/pause` | Pause bot |
| `POST` | `/api/resume` | Resume after circuit breaker |
| `POST` | `/api/paper/reset` | Reset paper wallet |
| `WS` | `/ws` | Full state JSON every 250ms |

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All tests run in paper mode — no real orders placed.

## Safety

- **Circuit breaker**: Halts after 3 consecutive losses. Resume via `POST /api/resume`.
- **Emergency exit**: Triggered if headroom ≤ $0.50 or <30s to expiry
- **Position guard**: Dominant side always holds ≥ weak side shares
- **Paper default**: `MODE=paper` — never accidentally goes live
