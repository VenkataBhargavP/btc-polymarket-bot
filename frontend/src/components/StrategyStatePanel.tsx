import React from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
}

function windowBadge(window: number) {
  if (window === 1) return { label: "WINDOW 1", color: "bg-green-700 text-green-100" };
  if (window === 2) return { label: "WINDOW 2", color: "bg-amber-700 text-amber-100" };
  if (window === 3) return { label: "TIMER 210s", color: "bg-blue-700 text-blue-100" };
  return { label: "—", color: "bg-gray-700 text-gray-300" };
}

function phaseBadge(phase: string) {
  switch (phase) {
    case "waiting":
      return "bg-yellow-800 text-yellow-200";
    case "active":
      return "bg-green-800 text-green-200";
    case "closing":
      return "bg-blue-800 text-blue-200";
    case "done":
      return "bg-gray-700 text-gray-400";
    default:
      return "bg-gray-800 text-gray-400";
  }
}

export function StrategyStatePanel({ state }: Props) {
  const badge = windowBadge(state.activation_window);

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="text-xs text-gray-400 uppercase tracking-wider">Strategy State</div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs font-bold px-2 py-1 rounded ${phaseBadge(state.phase)}`}>
          {state.phase.toUpperCase()}
        </span>
        {state.scenario && (
          <span className="text-xs font-bold px-2 py-1 rounded bg-purple-800 text-purple-100">
            {state.scenario}
          </span>
        )}
        {state.activation_window > 0 && (
          <span className={`text-xs font-bold px-2 py-1 rounded ${badge.color}`}>
            {badge.label} — {state.elapsed_seconds.toFixed(0)}s
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-400">Dominant: </span>
          <span className="text-green-400 font-bold">{state.dominant_side || "—"}</span>
        </div>
        <div>
          <span className="text-gray-400">Weak: </span>
          <span className="text-red-400 font-bold">{state.weak_side || "—"}</span>
        </div>
        <div>
          <span className="text-gray-400">UP Price: </span>
          <span className="text-white">{(state.up_price * 100).toFixed(1)}¢</span>
        </div>
        <div>
          <span className="text-gray-400">DOWN Price: </span>
          <span className="text-white">{(state.down_price * 100).toFixed(1)}¢</span>
        </div>
        <div>
          <span className="text-gray-400">Cost Basis: </span>
          <span className="text-white">${state.total_cost_basis.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-gray-400">Target: </span>
          <span className="text-amber-400">${state.early_profit_target.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}
