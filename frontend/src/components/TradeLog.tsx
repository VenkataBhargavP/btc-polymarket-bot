import React from "react";
import { BotState, TradeEntry, TradeAction } from "../types";

interface Props {
  state: BotState;
}

function actionColor(action: TradeAction): string {
  switch (action) {
    case "BUY":
      return "text-blue-400";
    case "SELL":
      return "text-amber-400";
    case "EARLY_PROFIT":
      return "text-yellow-400";
    case "CLOSE_WIN":
      return "text-green-400";
    case "EXIT_NPZ":
      return "text-red-400";
    default:
      return "text-gray-400";
  }
}

function rowBg(action: TradeAction): string {
  switch (action) {
    case "EARLY_PROFIT":
      return "bg-yellow-900/20";
    case "EXIT_NPZ":
      return "bg-red-900/20";
    case "CLOSE_WIN":
      return "bg-green-900/20";
    default:
      return "";
  }
}

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

export function TradeLog({ state }: Props) {
  const trades = [...state.trade_log].reverse().slice(0, 20);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">
        Trade Log (last 20)
      </div>
      {trades.length === 0 ? (
        <div className="text-gray-500 text-xs">No trades yet</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400">
                <th className="text-left pb-1">Time</th>
                <th className="text-left pb-1">Action</th>
                <th className="text-left pb-1">Side</th>
                <th className="text-right pb-1">Shares</th>
                <th className="text-right pb-1">Price</th>
                <th className="text-right pb-1">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t: TradeEntry, i) => (
                <tr key={i} className={`border-t border-gray-700 ${rowBg(t.action)}`}>
                  <td className="py-0.5 text-gray-400">{fmtTime(t.ts)}</td>
                  <td className={`py-0.5 font-bold ${actionColor(t.action)}`}>{t.action}</td>
                  <td className="py-0.5 text-gray-300">{t.side}</td>
                  <td className="py-0.5 text-right text-white">{t.shares}</td>
                  <td className="py-0.5 text-right text-white">
                    {(t.price * 100).toFixed(1)}¢
                  </td>
                  <td
                    className={`py-0.5 text-right ${
                      (t.pnl_impact ?? 0) > 0
                        ? "text-green-400"
                        : (t.pnl_impact ?? 0) < 0
                        ? "text-red-400"
                        : "text-gray-400"
                    }`}
                  >
                    {t.pnl_impact !== undefined
                      ? `${t.pnl_impact >= 0 ? "+" : ""}$${t.pnl_impact.toFixed(2)}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
