import { useQuery } from "@tanstack/react-query";
import { api, type LandingPad } from "../../services/api";

function LandingControl() {
  const { data: pads, isLoading } = useQuery({
    queryKey: ["landing-pads"],
    queryFn: () => api.getLandingPads(),
    refetchInterval: 5000,
  });

  const statusColor = (status: string) => {
    switch (status) {
      case "available":
        return "active";
      case "occupied":
        return "warning";
      case "reserved":
        return "warning";
      case "maintenance":
        return "error";
      default:
        return "";
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: "16px" }}>Landing Pad Control</h2>

      {isLoading ? (
        <div className="card">Loading landing pads...</div>
      ) : (
        <div className="dashboard-grid">
          {pads && pads.length > 0 ? (
            pads.map((pad: LandingPad) => (
              <div className="card" key={pad.id}>
                <div className="card-header">{pad.name}</div>
                <div style={{ marginBottom: "8px" }}>
                  <span className={`status-badge ${statusColor(pad.status)}`}>
                    {pad.status}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  <p>
                    Position: {pad.latitude.toFixed(6)},{" "}
                    {pad.longitude.toFixed(6)}
                  </p>
                  <p>Charger: {pad.has_charger ? "Yes" : "No"}</p>
                  {pad.max_drone_weight && (
                    <p>Max Weight: {pad.max_drone_weight} kg</p>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="card">
              <p style={{ color: "var(--text-secondary)" }}>
                No landing pads configured. Add pads via the API.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LandingControl;
