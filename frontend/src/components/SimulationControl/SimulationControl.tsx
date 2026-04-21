import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../services/api";

const SPEED_OPTIONS = [
  { label: "1×", value: 1.0 },
  { label: "2×", value: 2.0 },
  { label: "5×", value: 5.0 },
];

export default function SimulationControl() {
  const queryClient = useQueryClient();
  const [pendingSpeed, setPendingSpeed] = useState<number | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ["simulationStatus"],
    queryFn: api.getSimulationStatus,
    refetchInterval: 2000,
  });

  const controlMutation = useMutation({
    mutationFn: ({
      action,
      speed,
    }: {
      action: "pause" | "resume" | "set_speed";
      speed?: number;
    }) => api.simulationControl(action, speed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulationStatus"] });
      setPendingSpeed(null);
    },
  });

  const handlePauseResume = () => {
    if (!status) return;
    controlMutation.mutate({ action: status.paused ? "resume" : "pause" });
  };

  const handleSpeed = (speed: number) => {
    setPendingSpeed(speed);
    controlMutation.mutate({ action: "set_speed", speed });
  };

  if (isLoading) {
    return <div style={{ padding: "16px", color: "#888" }}>Loading simulation status…</div>;
  }

  if (!status) {
    return <div style={{ padding: "16px", color: "#f87171" }}>Simulation unavailable</div>;
  }

  const currentSpeed = pendingSpeed ?? status.speed;
  const isBusy = controlMutation.isPending;

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Status + controls row */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-block",
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: status.paused ? "#f59e0b" : "#22c55e",
            }}
          />
          <span style={{ fontWeight: 600, color: status.paused ? "#f59e0b" : "#22c55e" }}>
            {status.paused ? "Paused" : "Running"}
          </span>
        </div>

        <button
          onClick={handlePauseResume}
          disabled={isBusy}
          style={{
            padding: "6px 20px",
            borderRadius: "6px",
            border: "none",
            cursor: isBusy ? "not-allowed" : "pointer",
            background: status.paused ? "#22c55e" : "#f59e0b",
            color: "#fff",
            fontWeight: 600,
            fontSize: "14px",
            opacity: isBusy ? 0.6 : 1,
          }}
        >
          {status.paused ? "▶ Resume" : "⏸ Pause"}
        </button>

        {/* Speed selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#aaa", fontSize: "13px" }}>Speed:</span>
          {SPEED_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleSpeed(opt.value)}
              disabled={isBusy}
              style={{
                padding: "4px 14px",
                borderRadius: "6px",
                border: `2px solid ${currentSpeed === opt.value ? "#3b82f6" : "#444"}`,
                background: currentSpeed === opt.value ? "#1e3a5f" : "transparent",
                color: currentSpeed === opt.value ? "#93c5fd" : "#aaa",
                fontWeight: currentSpeed === opt.value ? 700 : 400,
                cursor: isBusy ? "not-allowed" : "pointer",
                fontSize: "13px",
                opacity: isBusy ? 0.6 : 1,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Per-drone status table */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ color: "#888", textAlign: "left" }}>
            <th style={{ padding: "4px 12px 8px 0" }}>Drone</th>
            <th style={{ padding: "4px 12px 8px 0" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {status.drones.map((d) => {
            let label = "Stopped";
            let color = "#6b7280";
            if (d.running && d.paused) { label = "Paused"; color = "#f59e0b"; }
            else if (d.running) { label = "Running"; color = "#22c55e"; }
            else if (d.stopped) { label = "Completed"; color = "#8b5cf6"; }
            return (
              <tr key={d.drone_id}>
                <td style={{ padding: "4px 12px 4px 0", color: "#e5e7eb" }}>{d.drone_id}</td>
                <td style={{ padding: "4px 0", color }}>
                  <span
                    style={{
                      display: "inline-block",
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: color,
                      marginRight: "6px",
                    }}
                  />
                  {label}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
