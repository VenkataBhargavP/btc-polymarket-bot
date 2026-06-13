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
                                        #   | "EARLY_PROFIT" | "EXIT_NPZ" | "CLOSE_WIN"
    activation_window: int = 0          # 1, 2, or 3

    # Position tracking
    up_shares_held: float = 50.0
    down_shares_held: float = 50.0
    up_shares_sold: float = 0.0
    down_shares_sold: float = 0.0

    # Prices
    current_up_price: float = 0.50
    current_down_price: float = 0.50
    activation_up_price: float = 0.0
    activation_down_price: float = 0.0
    entry_up_price: float = 0.50
    entry_down_price: float = 0.50
    btc_spot_price: float = 0.0

    # Side identification (set at activation)
    dominant_side: str = ""             # "UP" | "DOWN"
    weak_side: str = ""
    dominant_price: float = 0.0
    weak_price: float = 0.0
    thresholds: dict = field(default_factory=dict)

    # Scenario flags — three separate flags to avoid blocking S3b→S3c
    s1_triggered: bool = False
    s2_triggered: bool = False
    s3a_triggered: bool = False
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

    # Circuit breaker (carried across events — loaded from DB at startup)
    consecutive_losses: int = 0
    bot_halted: bool = False

    # Concurrency
    activation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Order tracking
    open_order_ids: list = field(default_factory=list)
    orders: list = field(default_factory=list)
    trade_log: list = field(default_factory=list)
    price_history: list = field(default_factory=list)   # Last 60 ticks

    def get_shares_held(self, side: str) -> float:
        return self.up_shares_held if side == "UP" else self.down_shares_held

    def get_side_price(self, side: str) -> float:
        return self.current_up_price if side == "UP" else self.current_down_price

    def get_token_id(self, side: str) -> str:
        return self.up_token_id if side == "UP" else self.down_token_id

    def compute_total_value(self) -> float:
        return (
            self.realized_pnl_gross
            + self.up_shares_held * self.current_up_price
            + self.down_shares_held * self.current_down_price
        )

    def add_price_tick(self, up_price: float, down_price: float):
        import time
        self.price_history.append({
            "ts": time.time(),
            "up": up_price,
            "down": down_price,
        })
        if len(self.price_history) > 60:
            self.price_history.pop(0)
