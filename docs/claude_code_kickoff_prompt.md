You are building a production-ready Polymarket BTC 5-minute split-order auto-trading bot.

A complete implementation specification is attached as `polymarket_btc_bot_implementation.md`. Read it fully before writing a single line of code. Every decision — architecture, order types, scenario logic, thresholds, exit paths — is already made in that document. Do not invent alternatives.

---

## YOUR TASK

Build the entire project exactly as specified. Follow the build order in Section 21 without deviation.

---

## CRITICAL RULES — READ BEFORE STARTING

### 1. SDK — use the NEW unified SDK only
- Package: `polymarket-client` (NOT `py-clob-client`)
- Auth: `AsyncSecureClient.create(private_key=..., wallet=...)` — 2 keys only
- Orders: `place_limit_order()` and `place_market_order(order_type="FAK")`
- Streams: `client.subscribe([MarketSpec(...), CryptoPricesSpec(...)])`
- Never import from `py_clob_client` anywhere in the codebase

### 2. Order types — strictly enforced
| Context | Order type | Method |
|---|---|---|
| Entry (both sides) | Maker LIMIT @ $0.50 | `place_limit_order(side="BUY", price="0.50", size="50")` |
| Scenario sells (S1/S2/S3a/S3b) | Expiring LIMIT (10s TTL) | `place_limit_order(..., expiration=now+10)` |
| Emergency exit / S3c bail | Market FAK | `place_market_order(order_type="FAK")` |
| Settlement (dominant @ 99¢) | No order | Cancel open orders, let oracle settle |

### 3. Profit target — dynamic, never hardcoded
```python
state.early_profit_target = state.total_cost_basis * 1.005
```
Computed after entry fills. Never use a fixed dollar value.

### 4. Scenario flags — three separate flags, not one
```python
s3a_triggered: bool = False
s3b_triggered: bool = False
s3c_triggered: bool = False
```
S3b's bail check must use `not state.s3c_triggered` — never `not state.s3_triggered`.

### 5. All price thresholds snap to nearest 5¢
```python
def snap5(price: float) -> float:
    return round(round(price / 0.05) * 0.05, 4)
```
Every value in `compute_thresholds()` must be wrapped with `snap5()`.

### 6. Position sizing guard — enforce on every sell
After every `sell_shares()` call:
- `quantity = min(quantity, shares_held)`
- After sell: `dominant_held >= weak_held` must remain true
- If sell would invert this, reduce `quantity` to the maximum that preserves it

### 7. phase = "done" is always set FIRST in exit functions
```python
async def early_profit_exit(state):
    state.phase = "done"   # FIRST line — prevents re-entry
    ...

async def emergency_exit(state, reason):
    state.phase = "done"   # FIRST line
    ...
```

### 8. check_profit_zone() is idempotent
```python
async def check_profit_zone(state) -> bool:
    if state.phase == "done":
        return True   # Already exiting — never re-trigger
    ...
```

### 9. Paper mode default
`MODE=paper` in `.env.example`. Never default to live. Paper mode fills are instant at the requested price — no API calls, same state machine.

### 10. No file may be stubbed or abbreviated
Every file in Section 4 (Project Structure) must be complete and production-ready. No `# TODO`, no `pass`, no placeholder functions.

---

## BUILD ORDER (Section 21)

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

After each backend file: confirm it imports cleanly with no errors before proceeding.
After step 15: confirm `npm run build` passes with zero TypeScript errors.

---

## VERIFICATION CHECKLIST

Before declaring the build complete, verify every item:

**Backend**
- [ ] `polymarket-client` is the only Polymarket import — no `py_clob_client` anywhere
- [ ] `AsyncSecureClient.create(private_key=..., wallet=...)` used for auth
- [ ] `setup_trading_approvals()` called once at startup
- [ ] Entry orders: both `place_limit_order(side="BUY", price="0.50", size="50")` via `asyncio.gather`
- [ ] `state.early_profit_target = state.total_cost_basis * 1.005` set after fills
- [ ] `s3a_triggered`, `s3b_triggered`, `s3c_triggered` are three separate bool fields
- [ ] S3b bail check: `not state.s3c_triggered` (not `s3_triggered`)
- [ ] `snap5()` applied to every value in `compute_thresholds()`
- [ ] `sell_shares()` has both quantity cap and dominant>=weak guard
- [ ] `phase = "done"` is the first line in `early_profit_exit()` and `emergency_exit()`
- [ ] `check_profit_zone()` returns `True` immediately when `phase == "done"`
- [ ] `close_winning()` cancels orders only — no sell orders placed
- [ ] Circuit breaker: `consecutive_losses` counter; halt on 3rd loss; resume via `POST /api/resume`
- [ ] Expiry watchdog: `emergency_exit(reason="expiry_approaching")` when < 30s remaining and not done
- [ ] WS watchdog: WARNING at 3s, reconnect at 10s with exponential backoff
- [ ] All state mutations behind `asyncio.Lock`
- [ ] Order retry: 3 attempts with 500ms exponential backoff
- [ ] `pre_entry_seconds=30` — entry placed 30s before window open
- [ ] Balance check ≥ $50 before entry; skip window if insufficient
- [ ] `bot_state` table persists `consecutive_losses` and `bot_halted` across restarts
- [ ] FastAPI WebSocket pushes full state JSON every 250ms
- [ ] All REST endpoints in Section 13 implemented

**Frontend**
- [ ] All 9 components in Section 14 implemented
- [ ] Profit meter animates from cost_basis to early_profit_target
- [ ] "NO PROFIT ZONE — EXITING" red full-width flash banner
- [ ] "EARLY PROFIT — EXITING" gold full-width flash banner
- [ ] "CIRCUIT BREAKER — BOT HALTED" persistent red banner when `bot_halted=true`
- [ ] Countdown turns red + pulses at < 30s
- [ ] Trade log colors: BUY=blue, SELL=amber, EARLY_PROFIT=gold, CLOSE_WIN=green, EXIT_NPZ=red
- [ ] PAPER/LIVE mode toggle calls `POST /api/mode`
- [ ] Paper wallet reset button (paper mode only)
- [ ] `npm run build` passes with zero TypeScript errors

**Tests**
- [ ] All 15 test groups (A through O) from Section 19 have corresponding pytest test functions
- [ ] Every test runs in paper mode — no real orders in test suite
- [ ] Circuit breaker tests K1–K5 all pass
- [ ] Position sizing guard tests H4–H5 all pass

---

## FILES TO CREATE (complete list)

```
btc-polymarket-bot/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── polymarket/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── models.py
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── state.py
│   │   ├── profit_guard.py
│   │   └── paper.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py
│   │   └── position_tracker.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── price_feed.py
│   │   └── market_finder.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── store.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── ws.py
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
├── tests/
│   ├── __init__.py
│   ├── test_entry.py          # Group A
│   ├── test_activation.py     # Group B
│   ├── test_s1.py             # Group C
│   ├── test_s2.py             # Group D
│   ├── test_s3a.py            # Group E
│   ├── test_s3b.py            # Group F
│   ├── test_s3c.py            # Group G
│   ├── test_profit_guard.py   # Group H
│   ├── test_early_profit.py   # Group I
│   ├── test_emergency.py      # Group J
│   ├── test_circuit_breaker.py # Group K
│   ├── test_settlement.py     # Group L
│   ├── test_continuous.py     # Group M
│   ├── test_websocket.py      # Group N
│   └── test_paper.py          # Group O
├── .env.example
├── requirements.txt
├── start.sh
├── dev.sh
└── README.md
```

---

Now begin. Start with step 1: `backend/config.py` and `.env.example`.
