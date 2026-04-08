import { useWebSocket } from "../../hooks/useWebSocket";
import type { TelemetryData } from "../../services/api";

function TelemetryPanel() {
  const { data: telemetry, connected } = useWebSocket<TelemetryData>("telemetry");

  return (
    <div>
      <h2 style={{ marginBottom: "16px" }}>
        Real-time Telemetry{" "}
        <span className={`status-badge ${connected ? "active" : "error"}`}>
          {connected ? "Connected" : "Disconnected"}
        </span>
      </h2>

      {telemetry ? (
        <div className="dashboard-grid">
          <div className="card">
            <div className="card-header">Drone ID</div>
            <div className="card-value">{telemetry.drone_id}</div>
          </div>
          <div className="card">
            <div className="card-header">Position</div>
            <div className="card-value" style={{ fontSize: "1rem" }}>
              {telemetry.latitude?.toFixed(6)}, {telemetry.longitude?.toFixed(6)}
            </div>
          </div>
          <div className="card">
            <div className="card-header">Altitude</div>
            <div className="card-value">{telemetry.altitude?.toFixed(1)} m</div>
          </div>
          <div className="card">
            <div className="card-header">Speed</div>
            <div className="card-value">{telemetry.speed?.toFixed(1)} m/s</div>
          </div>
          <div className="card">
            <div className="card-header">Heading</div>
            <div className="card-value">{telemetry.heading?.toFixed(0)}°</div>
          </div>
          <div className="card">
            <div className="card-header">Battery</div>
            <div
              className="card-value"
              style={{
                color:
                  telemetry.battery_level > 50
                    ? "var(--accent-green)"
                    : telemetry.battery_level > 20
                    ? "var(--accent-yellow)"
                    : "var(--accent-red)",
              }}
            >
              {telemetry.battery_level?.toFixed(0)}%
            </div>
          </div>
          <div className="card">
            <div className="card-header">Signal Strength</div>
            <div className="card-value">
              {telemetry.signal_strength?.toFixed(0)}%
            </div>
          </div>
          <div className="card">
            <div className="card-header">Last Update</div>
            <div className="card-value" style={{ fontSize: "0.875rem" }}>
              {telemetry.timestamp}
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <p style={{ color: "var(--text-secondary)" }}>
            Waiting for telemetry data...
          </p>
        </div>
      )}
    </div>
  );
}

export default TelemetryPanel;
