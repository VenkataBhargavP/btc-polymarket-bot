export type Phase = "idle" | "waiting" | "active" | "closing" | "done";
export type Scenario =
  | ""
  | "S1"
  | "S2"
  | "S3a"
  | "S3b"
  | "S3c"
  | "EARLY_PROFIT"
  | "EXIT_NPZ"
  | "CLOSE_WIN";
export type Side = "UP" | "DOWN" | "";
export type TradeAction =
  | "BUY"
  | "SELL"
  | "EARLY_PROFIT"
  | "EXIT_NPZ"
  | "CLOSE_WIN"
  | "CLOSE";

export interface ProfitGuard {
  realized: number;
  best_future: number;
  max_recoverable: number;
  cost_basis: number;
  headroom: number;
  in_profit_zone: boolean;
}

export interface TradeEntry {
  ts: number;
  action: TradeAction;
  side: Side;
  shares: number;
  price: number;
  pnl_impact?: number;
  scenario: Scenario;
}

export interface PriceTick {
  ts: number;
  up: number;
  down: number;
}

export interface HealthInfo {
  ws_connected: boolean;
  last_tick_ms: number;
  order_latency_ms: number;
}

export interface BotState {
  ts: number;
  mode: "paper" | "live";
  phase: Phase;
  scenario: Scenario;
  activation_window: number;
  elapsed_seconds: number;
  event_id: string;
  event_expires_in: number;

  up_price: number;
  down_price: number;
  dominant_side: Side;
  weak_side: Side;

  up_shares_held: number;
  down_shares_held: number;
  up_shares_sold: number;
  down_shares_sold: number;

  realized_pnl: number;
  unrealized_pnl: number;
  realized_pnl_gross: number;
  total_cost_basis: number;
  early_profit_target: number;
  current_total_value: number;
  profit_to_target: number;
  wallet_balance: number;

  consecutive_losses: number;
  bot_halted: boolean;

  profit_guard: ProfitGuard;
  trade_log: TradeEntry[];
  price_history: PriceTick[];
  health: HealthInfo;
}

export interface Position {
  side: Side;
  token_id: string;
  shares_held: number;
  shares_sold: number;
  current_price: number;
  entry_price: number;
  unrealized_pnl: number;
}
