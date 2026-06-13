import React from "react";
import { useStrategyState } from "./hooks/useStrategyState";
import { Header } from "./components/Header";
import { WalletPanel } from "./components/WalletPanel";
import { PriceChart } from "./components/PriceChart";
import { PositionTable } from "./components/PositionTable";
import { StrategyStatePanel } from "./components/StrategyStatePanel";
import { ProfitMeter } from "./components/ProfitMeter";
import { TradeLog } from "./components/TradeLog";
import { SystemHealth } from "./components/SystemHealth";

export default function App() {
  const { state, wsConnected, toast } = useStrategyState();

  const showNPZBanner =
    state.profit_guard?.in_profit_zone === false && state.phase !== "idle";
  const showEarlyProfitBanner = state.scenario === "EARLY_PROFIT";
  const showCircuitBreaker = state.bot_halted;

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <Header state={state} wsConnected={wsConnected} />

      {/* Emergency banners */}
      {showCircuitBreaker && (
        <div className="w-full bg-red-700 text-white text-center py-2 font-bold text-sm animate-pulse">
          ⛔ CIRCUIT BREAKER — {state.consecutive_losses} LOSSES — BOT HALTED — Click Resume to continue
        </div>
      )}
      {showNPZBanner && (
        <div className="w-full bg-red-600 text-white text-center py-2 font-bold text-sm animate-pulse">
          🚨 NO PROFIT ZONE — EXITING
        </div>
      )}
      {showEarlyProfitBanner && (
        <div className="w-full bg-yellow-500 text-black text-center py-2 font-bold text-sm animate-pulse">
          ★ EARLY PROFIT — EXITING
        </div>
      )}

      {/* Toast notifications */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-gray-800 border border-gray-600 text-white px-4 py-2 rounded shadow-lg text-sm animate-fade-in">
          {toast}
        </div>
      )}

      {/* Main grid */}
      <div className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left column */}
        <div className="space-y-4">
          <PriceChart state={state} />
          <TradeLog state={state} />
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <WalletPanel state={state} />
          <StrategyStatePanel state={state} />
          <PositionTable state={state} />
          <ProfitMeter state={state} />
          <SystemHealth state={state} wsConnected={wsConnected} />
        </div>
      </div>
    </div>
  );
}
