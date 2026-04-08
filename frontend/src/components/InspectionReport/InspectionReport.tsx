import { useQuery } from "@tanstack/react-query";
import { api, type Mission } from "../../services/api";

function InspectionReport() {
  const { data: missions, isLoading } = useQuery({
    queryKey: ["missions"],
    queryFn: () => api.getMissions(),
    refetchInterval: 10000,
  });

  const statusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "active";
      case "in_progress":
      case "data_uploading":
        return "warning";
      case "failed":
        return "error";
      default:
        return "";
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: "16px" }}>Inspection Reports</h2>

      {isLoading ? (
        <div className="card">Loading missions...</div>
      ) : (
        <div>
          {missions && missions.length > 0 ? (
            missions.map((mission: Mission) => (
              <div className="card" key={mission.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <h3>{mission.name}</h3>
                  <span
                    className={`status-badge ${statusColor(mission.status)}`}
                  >
                    {mission.status}
                  </span>
                </div>
                {mission.description && (
                  <p
                    style={{
                      color: "var(--text-secondary)",
                      marginBottom: "8px",
                    }}
                  >
                    {mission.description}
                  </p>
                )}
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  {mission.started_at && (
                    <span>Started: {new Date(mission.started_at).toLocaleString()} </span>
                  )}
                  {mission.completed_at && (
                    <span>
                      | Completed:{" "}
                      {new Date(mission.completed_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="card">
              <p style={{ color: "var(--text-secondary)" }}>
                No inspection missions found. Create missions via the API.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default InspectionReport;
