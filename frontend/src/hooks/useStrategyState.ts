import { useState, useCallback, useRef, useEffect } from "react";
import { BotState } from "../types";
import { useWebSocket } from "./useWebSocket";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.host}/ws`
    : "ws://localhost:8000/ws";

const DEFAULT_STATE: BotState = {
  ts: 0,
  mode: "paper",
  phase: "idle",
  scenario: "",
  activation_window: 0,
  elapsed_seconds: 0,
  event_id: "",
  event_expires_in: 0,
  up_price: 0.5,
  down_price: 0.5,
  dominant_side: "",
  weak_side: "",
  up_shares_held: 0,
  down_shares_held: 0,
  up_shares_sold: 0,
  down_shares_sold: 0,
  realized_pnl: 0,
  unrealized_pnl: 0,
  realized_pnl_gross: 0,
  total_cost_basis: 0,
  early_profit_target: 0,
  current_total_value: 0,
  profit_to_target: 0,
  wallet_balance: 0,
  consecutive_losses: 0,
  bot_halted: false,
  profit_guard: {
    realized: 0,
    best_future: 0,
    max_recoverable: 0,
    cost_basis: 0,
    headroom: 0,
    in_profit_zone: true,
  },
  trade_log: [],
  price_history: [],
  health: { ws_connected: false, last_tick_ms: 0, order_latency_ms: 0 },
};

export function useStrategyState() {
  const [state, setState] = useState<BotState>(DEFAULT_STATE);
  const [wsConnected, setWsConnected] = useState(false);
  const prevScenarioRef = useRef<string>("");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);

  const onMessage = useCallback(
    (data: string) => {
      try {
        const parsed: BotState = JSON.parse(data);
        setState(parsed);

        if (parsed.scenario && parsed.scenario !== prevScenarioRef.current) {
          prevScenarioRef.current = parsed.scenario;
          showToast(`Scenario: ${parsed.scenario}`);
        }
      } catch {
        // ignore malformed frames
      }
    },
    [showToast]
  );

  useWebSocket({ url: WS_URL, onMessage, onStatusChange: setWsConnected });

  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
  }, []);

  return { state, wsConnected, toast };
}
