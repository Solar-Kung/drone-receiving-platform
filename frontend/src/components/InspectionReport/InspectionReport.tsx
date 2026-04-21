import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Mission } from "../../services/api";
import { useWebSocket } from "../../hooks/useWebSocket";

interface MissionCardProps {
  mission: Mission;
}

function MissionCard({ mission }: MissionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const { data: images, refetch } = useQuery({
    queryKey: ["mission-images", mission.id],
    queryFn: () => api.getMissionImages(mission.id),
    enabled: expanded,
    staleTime: 30_000,
  });

  const statusColor = (status: string) => {
    switch (status) {
      case "completed": return "active";
      case "in_progress":
      case "data_uploading": return "warning";
      case "failed": return "error";
      default: return "";
    }
  };

  return (
    <div className="card" style={{ marginBottom: "12px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 style={{ margin: 0 }}>{mission.name}</h3>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {images != null && images.length > 0 && (
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              {images.length} image{images.length !== 1 ? "s" : ""} captured
            </span>
          )}
          <span className={`status-badge ${statusColor(mission.status)}`}>
            {mission.status}
          </span>
        </div>
      </div>

      {/* Description */}
      {mission.description && (
        <p style={{ color: "var(--text-secondary)", marginBottom: "8px", fontSize: "0.875rem" }}>
          {mission.description}
        </p>
      )}

      {/* Timestamps */}
      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
        {mission.started_at && (
          <span>Started: {new Date(mission.started_at).toLocaleString()} </span>
        )}
        {mission.completed_at && (
          <span>| Completed: {new Date(mission.completed_at).toLocaleString()}</span>
        )}
      </div>

      {/* Toggle images */}
      <button
        onClick={() => { setExpanded((v) => !v); if (!expanded) refetch(); }}
        style={{
          background: "var(--border-color, #334155)",
          border: "none",
          color: "var(--text-primary, #f8fafc)",
          padding: "4px 10px",
          borderRadius: "4px",
          cursor: "pointer",
          fontSize: "0.8rem",
          marginBottom: expanded ? "12px" : "0",
        }}
      >
        {expanded ? "Hide Images" : "View Images"}
      </button>

      {/* Image grid */}
      {expanded && (
        <div>
          {images == null ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>Loading...</p>
          ) : images.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>No images yet.</p>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "4px" }}>
              {images.map((img) => (
                <a
                  key={img.id}
                  href={img.url ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={img.filename}
                >
                  <img
                    src={img.url ?? ""}
                    alt={img.filename}
                    style={{
                      width: "150px",
                      height: "112px",
                      objectFit: "cover",
                      borderRadius: "4px",
                      border: "1px solid var(--border-color, #334155)",
                    }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI report (WP3 fills this in) */}
      {mission.report_text && (
        <div style={{ marginTop: "12px" }}>
          <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: "6px" }}>
            Inspection Report
          </div>
          <pre style={{
            whiteSpace: "pre-wrap",
            fontSize: "0.8rem",
            color: "var(--text-secondary)",
            background: "var(--bg-secondary, #0f172a)",
            padding: "10px",
            borderRadius: "4px",
            margin: 0,
          }}>
            {mission.report_text}
          </pre>
        </div>
      )}
    </div>
  );
}

function InspectionReport() {
  const queryClient = useQueryClient();
  const { lastRawMessage } = useWebSocket<unknown>("telemetry");

  const { data: missions, isLoading } = useQuery({
    queryKey: ["missions"],
    queryFn: () => api.getMissions(),
    refetchInterval: 10_000,
  });

  // Invalidate image queries when a new image arrives via WebSocket
  useEffect(() => {
    if (!lastRawMessage) return;
    const msg = lastRawMessage as { type: string; data?: { mission_id?: string } };
    if (msg.type === "inspection_image" && msg.data?.mission_id) {
      queryClient.invalidateQueries({ queryKey: ["mission-images", msg.data.mission_id] });
    }
    // Invalidate mission list when report is ready
    if (msg.type === "mission_report") {
      queryClient.invalidateQueries({ queryKey: ["missions"] });
    }
  }, [lastRawMessage, queryClient]);

  return (
    <div>
      <h2 style={{ marginBottom: "16px" }}>Inspection Reports</h2>

      {isLoading ? (
        <div className="card">Loading missions...</div>
      ) : missions && missions.length > 0 ? (
        missions.map((mission: Mission) => (
          <MissionCard key={mission.id} mission={mission} />
        ))
      ) : (
        <div className="card">
          <p style={{ color: "var(--text-secondary)" }}>
            No inspection missions found.
          </p>
        </div>
      )}
    </div>
  );
}

export default InspectionReport;
