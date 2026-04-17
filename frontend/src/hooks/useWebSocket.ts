import { useEffect, useRef, useState, useCallback } from "react";

interface WebSocketState<T> {
  data: T | null;
  connected: boolean;
  error: string | null;
  /** Full parsed envelope — use this when you need message.type (e.g. "alert"). */
  lastRawMessage: unknown | null;
}

export function useWebSocket<T>(channel: string): WebSocketState<T> {
  const [state, setState] = useState<WebSocketState<T>>({
    data: null,
    connected: false,
    error: null,
    lastRawMessage: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${channel}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setState((prev) => ({ ...prev, connected: true, error: null }));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "pong") return;
        setState((prev) => ({
          ...prev,
          lastRawMessage: message,
          // Only update `data` for messages that carry a data payload
          ...(message.data != null ? { data: message.data as T } : {}),
        }));
      } catch {
        // Ignore parse errors for non-JSON messages
      }
    };

    ws.onclose = () => {
      setState((prev) => ({ ...prev, connected: false }));
      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setState((prev) => ({ ...prev, error: "WebSocket connection error" }));
    };
  }, [channel]);

  useEffect(() => {
    connect();

    // Heartbeat ping every 30s
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}
