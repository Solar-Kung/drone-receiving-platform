import { useEffect, useState } from "react";
import { useWebSocket } from "../../hooks/useWebSocket";

interface MissionProgressMsg {
  mission_id: string;
  current_waypoint: number;
  total_waypoints: number;
  progress: number;
}

interface DroneProgress {
  droneId: string;
  missionId: string;
  currentWaypoint: number;
  totalWaypoints: number;
  progress: number;
}

function MissionProgress() {
  const [progress, setProgress] = useState<Map<string, DroneProgress>>(new Map());
  const { lastRawMessage } = useWebSocket<unknown>("telemetry");

  useEffect(() => {
    if (!lastRawMessage) return;
    const msg = lastRawMessage as {
      type: string;
      drone_id?: string;
      data?: MissionProgressMsg;
    };
    if (msg.type !== "mission_progress" || !msg.drone_id || !msg.data) return;

    const { drone_id, data } = msg;
    setProgress((prev) => {
      const updated = new Map(prev);
      updated.set(drone_id, {
        droneId: drone_id,
        missionId: data.mission_id,
        currentWaypoint: data.current_waypoint,
        totalWaypoints: data.total_waypoints,
        progress: data.progress,
      });
      return updated;
    });
  }, [lastRawMessage]);

  if (progress.size === 0) {
    return (
      <p style={{ color: "var(--text-secondary)" }}>
        Waiting for mission data...
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
      {Array.from(progress.values()).map((p) => (
        <div key={p.droneId}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: "6px",
              fontSize: "0.875rem",
            }}
          >
            <span style={{ fontWeight: 600 }}>{p.droneId}</span>
            <span style={{ color: "var(--text-secondary)" }}>
              {p.currentWaypoint}/{p.totalWaypoints} &mdash;{" "}
              {p.progress.toFixed(0)}%
            </span>
          </div>
          <div
            style={{
              height: "8px",
              background: "var(--border-color, #334155)",
              borderRadius: "4px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${Math.min(p.progress, 100)}%`,
                background: "linear-gradient(to right, #3b82f6, #22c55e)",
                borderRadius: "4px",
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default MissionProgress;
