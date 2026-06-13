import { useEffect, useRef, useCallback } from "react";

const WS_WARN_MS = 3000;
const WS_RECONNECT_MS = 10000;
const MAX_BACKOFF_MS = 30000;

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: string) => void;
  onStatusChange?: (connected: boolean) => void;
}

export function useWebSocket({ url, onMessage, onStatusChange }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef<number>(1000);
  const lastTickRef = useRef<number>(Date.now());
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warnTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (warnTimerRef.current) clearInterval(warnTimerRef.current);
  }, []);

  const connect = useCallback(() => {
    clearTimers();

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      backoffRef.current = 1000;
      onStatusChange?.(true);

      warnTimerRef.current = setInterval(() => {
        const stale = Date.now() - lastTickRef.current;
        if (stale >= WS_RECONNECT_MS) {
          ws.close();
        }
      }, 1000);
    };

    ws.onmessage = (evt) => {
      lastTickRef.current = Date.now();
      onMessage(evt.data);
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      clearTimers();
      reconnectTimerRef.current = setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
        connect();
      }, backoffRef.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url, onMessage, onStatusChange, clearTimers]);

  useEffect(() => {
    connect();
    return () => {
      clearTimers();
      wsRef.current?.close();
    };
  }, [connect, clearTimers]);
}
