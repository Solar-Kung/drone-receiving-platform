import { useEffect, useState } from "react";
import { useWebSocket } from "../../hooks/useWebSocket";

interface Alert {
  id: number;
  drone_id: string;
  level: "warning" | "critical";
  message: string;
  expiresAt: number;
}

interface RawMessage {
  type: string;
  drone_id?: string;
  level?: string;
  message?: string;
}

let _nextId = 0;

function AlertPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const { lastRawMessage } = useWebSocket<unknown>("telemetry");

  // Receive alert messages
  useEffect(() => {
    if (!lastRawMessage) return;
    const msg = lastRawMessage as RawMessage;
    if (msg.type !== "alert") return;

    const level = msg.level === "critical" ? "critical" : "warning";
    const newAlert: Alert = {
      id: _nextId++,
      drone_id: msg.drone_id ?? "unknown",
      level,
      message: msg.message ?? "Alert",
      expiresAt: Date.now() + 10_000,
    };
    setAlerts((prev) => [newAlert, ...prev].slice(0, 10));
  }, [lastRawMessage]);

  // Auto-expire alerts
  useEffect(() => {
    if (alerts.length === 0) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setAlerts((prev) => prev.filter((a) => a.expiresAt > now));
    }, 1000);
    return () => clearInterval(timer);
  }, [alerts.length]);

  if (alerts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxWidth: 320,
      }}
    >
      {alerts.map((alert) => (
        <div
          key={alert.id}
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: alert.level === "critical" ? "#1e0a0a" : "#1e1500",
            border: `2px solid ${alert.level === "critical" ? "#ef4444" : "#eab308"}`,
            color: "#f8fafc",
            fontSize: 13,
            boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
            animation: alert.level === "critical" ? "pulse-border 1s infinite" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <span
              style={{
                background: alert.level === "critical" ? "#ef4444" : "#eab308",
                color: "#fff",
                fontSize: 10,
                fontWeight: 700,
                padding: "1px 6px",
                borderRadius: 4,
                textTransform: "uppercase",
              }}
            >
              {alert.level}
            </span>
            <span style={{ color: "#94a3b8", fontSize: 11 }}>{alert.drone_id}</span>
          </div>
          <div>{alert.message}</div>
        </div>
      ))}
      <style>{`
        @keyframes pulse-border {
          0%, 100% { border-color: #ef4444; }
          50% { border-color: #fca5a5; }
        }
      `}</style>
    </div>
  );
}

export default AlertPanel;
