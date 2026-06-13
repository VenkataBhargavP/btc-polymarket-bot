import React, { useState } from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
  onModeChange?: (mode: "paper" | "live") => void;
}

export function ModeToggle({ state, onModeChange }: Props) {
  const [pending, setPending] = useState(false);

  async function toggle() {
    const nextMode = state.mode === "paper" ? "live" : "paper";
    setPending(true);
    try {
      await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: nextMode }),
      });
      onModeChange?.(nextMode);
    } finally {
      setPending(false);
    }
  }

  async function resetPaper() {
    await fetch("/api/paper/reset", { method: "POST" });
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={toggle}
        disabled={pending}
        className={`px-3 py-1 rounded text-xs font-bold transition-colors ${
          state.mode === "paper"
            ? "bg-amber-600 hover:bg-amber-500 text-white"
            : "bg-red-700 hover:bg-red-600 text-white animate-pulse"
        }`}
      >
        {pending ? "…" : state.mode === "paper" ? "PAPER" : "LIVE"}
      </button>
      {state.mode === "paper" && (
        <button
          onClick={resetPaper}
          className="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-300"
        >
          Reset Wallet
        </button>
      )}
    </div>
  );
}
