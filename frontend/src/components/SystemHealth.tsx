import React from "react";
import { BotState } from "../types";

interface Props {
  state: BotState;
  wsConnected: boolean;
}

function fmtExpiry(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function SystemHealth({ state, wsConnected }: Props) {
  const tickColor =
    state.health.last_tick_ms < 3000 ? "text-green-400" : "text-red-400";

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-2">
      <div className="text-xs text-gray-400 uppercase tracking-wider">System Health</div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div>
          <span className="text-gray-400">WS: </span>
          <span className={wsConnected ? "text-green-400" : "text-red-400"}>
            {wsConnected ? "● connected" : "● disconnected"}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Tick: </span>
          <span className={tickColor}>{state.health.last_tick_ms}ms</span>
        </div>
        <div>
          <span className="text-gray-400">Order latency: </span>
          <span className="text-white">{state.health.order_latency_ms}ms</span>
        </div>
        <div>
          <span className="text-gray-400">Losses: </span>
          <span className={state.consecutive_losses >= 2 ? "text-red-400" : "text-white"}>
            {state.consecutive_losses}/{3}
          </span>
        </div>
        {state.event_id && (
          <>
            <div className="col-span-2 truncate">
              <span className="text-gray-400">Event: </span>
              <span className="text-gray-300 text-xs">{state.event_id}</span>
            </div>
            <div>
              <span className="text-gray-400">Expires: </span>
              <span
                className={
                  state.event_expires_in < 30
                    ? "text-red-400 font-bold animate-pulse"
                    : "text-white"
                }
              >
                {fmtExpiry(state.event_expires_in)}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
