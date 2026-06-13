from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Tick:
    """Single price update from the WebSocket stream."""
    event_id: str
    token_id: str
    side: str           # "UP" | "DOWN" | "BTC"
    price: Decimal
    timestamp: float
    source: str = ""    # "polymarket" | "binance"


@dataclass
class Fill:
    """Confirmed order fill."""
    order_id: str
    token_id: str
    side: str           # "BUY" | "SELL"
    shares: float
    price: float
    timestamp: float
    scenario: str = ""


@dataclass
class OrderResult:
    """Result of a place_order call."""
    order_id: str | None
    ok: bool
    error: str = ""
    price: float = 0.0
    size: float = 0.0


@dataclass
class MarketInfo:
    """Resolved BTC 5-min market ready for trading."""
    event_id: str
    condition_id: str
    up_token_id: str
    down_token_id: str
    start_ts: float
    seconds_until: float
    slug: str = ""
