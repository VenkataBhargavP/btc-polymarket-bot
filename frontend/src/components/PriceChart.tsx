import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { BotState } from "../types";

interface Props {
  state: BotState;
}

export function PriceChart({ state }: Props) {
  const data = state.price_history.map((tick) => ({
    t: new Date(tick.ts * 1000).toLocaleTimeString(),
    UP: Number(tick.up.toFixed(4)),
    DOWN: Number(tick.down.toFixed(4)),
  }));

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-64">
      <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">
        Price Chart — Last 60 Ticks
      </div>
      {data.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          Waiting for price data…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="90%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="upGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="downGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="t" tick={{ fontSize: 10, fill: "#9ca3af" }} />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}¢`}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              width={40}
            />
            <Tooltip
              contentStyle={{ background: "#1f2937", border: "1px solid #374151" }}
              labelStyle={{ color: "#9ca3af" }}
              formatter={(v: number) => [`${(v * 100).toFixed(1)}¢`]}
            />
            <Area
              type="monotone"
              dataKey="UP"
              stroke="#22c55e"
              strokeWidth={2}
              fill="url(#upGrad)"
              dot={false}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="DOWN"
              stroke="#ef4444"
              strokeWidth={2}
              fill="url(#downGrad)"
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
