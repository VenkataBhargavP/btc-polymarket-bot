import React from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
}

export function ProfitMeter({ state }: Props) {
  const { total_cost_basis, early_profit_target, current_total_value, profit_guard } = state;

  const range = early_profit_target - total_cost_basis;
  const progress = range > 0
    ? Math.min(1, Math.max(0, (current_total_value - total_cost_basis) / range))
    : 0;

  const crossedTarget = current_total_value >= early_profit_target && early_profit_target > 0;

  const headroom = profit_guard?.headroom ?? 0;
  const headroomColor =
    headroom > 2.0
      ? "bg-green-500"
      : headroom > 0.5
      ? "bg-amber-500"
      : "bg-red-500 animate-pulse";

  const headroomTextColor =
    headroom > 2.0 ? "text-green-400" : headroom > 0.5 ? "text-amber-400" : "text-red-400";

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="text-xs text-gray-400 uppercase tracking-wider">Profit Meter</div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-400">
          <span>${total_cost_basis.toFixed(2)}</span>
          <span>${early_profit_target.toFixed(2)}</span>
        </div>
        <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              crossedTarget
                ? "bg-yellow-400 animate-pulse"
                : "bg-blue-500"
            }`}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        <div className="text-center text-xs text-gray-300">
          Current: ${current_total_value.toFixed(2)}
          {crossedTarget && (
            <span className="ml-2 text-yellow-400 font-bold animate-pulse">★ TARGET HIT</span>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <div className="text-xs text-gray-400">
          Headroom: <span className={headroomTextColor}>${headroom.toFixed(2)}</span>
        </div>
        <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${headroomColor}`}
            style={{
              width: `${Math.min(100, Math.max(0, (headroom / 3) * 100))}%`,
            }}
          />
        </div>
        {headroom <= 0.5 && total_cost_basis > 0 && (
          <div className="text-xs text-red-400 font-bold animate-pulse">
            ⚠ NO PROFIT ZONE
          </div>
        )}
      </div>
    </div>
  );
}
