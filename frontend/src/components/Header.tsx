import React, { useState } from "react";
import { BotState } from "../types";
import { ModeToggle } from "./ModeToggle";

interface Props {
  state: BotState;
  wsConnected: boolean;
}

function fmtCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function Header({ state, wsConnected }: Props) {
  const [pausing, setPausing] = useState(false);
  const nearExpiry = state.event_expires_in < 30 && state.event_expires_in > 0;

  async function pause() {
    setPausing(true);
    try {
      await fetch("/api/pause", { method: "POST" });
    } finally {
      setPausing(false);
    }
  }

  async function resume() {
    await fetch("/api/resume", { method: "POST" });
  }

  return (
    <header className="bg-gray-900 border-b border-gray-700 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-white font-bold text-lg">BTC Bot</h1>
        <span
          className={`text-xs px-2 py-0.5 rounded font-bold ${
            state.mode === "paper"
              ? "bg-amber-700 text-amber-100"
              : "bg-red-700 text-red-100 animate-pulse"
          }`}
        >
          {state.mode.toUpperCase()}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {state.event_expires_in > 0 && (
          <span
            className={`font-mono text-sm font-bold ${
              nearExpiry ? "text-red-400 animate-pulse" : "text-gray-300"
            }`}
          >
            {fmtCountdown(state.event_expires_in)}
          </span>
        )}

        <button
          onClick={state.bot_halted ? resume : pause}
          disabled={pausing}
          className={`text-xs px-3 py-1 rounded transition-colors ${
            state.bot_halted
              ? "bg-green-700 hover:bg-green-600 text-white"
              : "bg-gray-700 hover:bg-gray-600 text-gray-200"
          }`}
        >
          {pausing ? "…" : state.bot_halted ? "Resume" : "Pause"}
        </button>

        <ModeToggle state={state} />

        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected ? "bg-green-500" : "bg-red-500 animate-pulse"
            }`}
          />
          <span className="text-xs text-gray-400">WS</span>
        </div>
      </div>
    </header>
  );
}
