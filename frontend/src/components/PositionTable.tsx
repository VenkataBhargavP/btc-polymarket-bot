import React from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
}

function fmt(n: number, d = 2) {
  return n.toFixed(d);
}

export function PositionTable({ state }: Props) {
  const rows = [
    {
      side: "UP",
      held: state.up_shares_held,
      sold: state.up_shares_sold,
      price: state.up_price,
      isDominant: state.dominant_side === "UP",
    },
    {
      side: "DOWN",
      held: state.down_shares_held,
      sold: state.down_shares_sold,
      price: state.down_price,
      isDominant: state.dominant_side === "DOWN",
    },
  ];

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">Positions</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-xs">
            <th className="text-left pb-1">Side</th>
            <th className="text-right pb-1">Held</th>
            <th className="text-right pb-1">Sold</th>
            <th className="text-right pb-1">Price</th>
            <th className="text-right pb-1">Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.side} className="border-t border-gray-700">
              <td className="py-1 font-medium">
                <span
                  className={
                    r.isDominant
                      ? "text-green-400"
                      : r.side === state.weak_side
                      ? "text-red-400"
                      : "text-gray-300"
                  }
                >
                  {r.side}
                  {r.isDominant && (
                    <span className="ml-1 text-xs text-green-500">DOM</span>
                  )}
                </span>
              </td>
              <td className="py-1 text-right text-white">{r.held}</td>
              <td className="py-1 text-right text-gray-400">{r.sold}</td>
              <td className="py-1 text-right text-white">{fmt(r.price * 100, 1)}¢</td>
              <td className="py-1 text-right text-white">
                ${fmt(r.held * r.price)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
