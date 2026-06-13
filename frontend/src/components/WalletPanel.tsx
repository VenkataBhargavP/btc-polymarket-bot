import React from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
}

function fmt(n: number, decimals = 2) {
  return n.toFixed(decimals);
}

export function WalletPanel({ state }: Props) {
  const pnlColor =
    state.realized_pnl > 0
      ? "text-green-400"
      : state.realized_pnl < 0
      ? "text-red-400"
      : "text-gray-300";

  return (
    <div className="bg-gray-800 rounded-lg p-4 grid grid-cols-3 gap-4">
      <div>
        <div className="text-xs text-gray-400 uppercase tracking-wider">Balance</div>
        <div className="text-xl font-bold text-white">${fmt(state.wallet_balance)}</div>
      </div>
      <div>
        <div className="text-xs text-gray-400 uppercase tracking-wider">Realized P&L</div>
        <div className={`text-xl font-bold ${pnlColor}`}>
          {state.realized_pnl >= 0 ? "+" : ""}${fmt(state.realized_pnl)}
        </div>
      </div>
      <div>
        <div className="text-xs text-gray-400 uppercase tracking-wider">Unrealized P&L</div>
        <div
          className={`text-xl font-bold ${
            state.unrealized_pnl > 0
              ? "text-green-400"
              : state.unrealized_pnl < 0
              ? "text-red-400"
              : "text-gray-300"
          }`}
        >
          {state.unrealized_pnl >= 0 ? "+" : ""}${fmt(state.unrealized_pnl)}
        </div>
      </div>
    </div>
  );
}
