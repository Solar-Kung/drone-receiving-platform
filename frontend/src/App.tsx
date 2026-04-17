import { Routes, Route, NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import MapView from "./components/MapView/MapView";
import AltitudeChart from "./components/AltitudeChart/AltitudeChart";
import TelemetryPanel from "./components/TelemetryPanel/TelemetryPanel";
import LandingControl from "./components/LandingControl/LandingControl";
import InspectionReport from "./components/InspectionReport/InspectionReport";
import TelemetryCharts from "./components/TelemetryCharts/TelemetryCharts";
import AlertPanel from "./components/AlertPanel/AlertPanel";
import { api } from "./services/api";

function App() {
  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>Drone Receiving Platform</h1>
        <span className="status-badge active">System Online</span>
      </header>

      <nav className="app-sidebar">
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/telemetry">Telemetry</NavLink>
        <NavLink to="/landings">Landing Control</NavLink>
        <NavLink to="/inspections">Inspections</NavLink>
      </nav>

      <main className="app-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/telemetry" element={<TelemetryPanel />} />
          <Route path="/landings" element={<LandingControl />} />
          <Route path="/inspections" element={<InspectionReport />} />
        </Routes>
      </main>
      <AlertPanel />
    </div>
  );
}

function Dashboard() {
  const { data: statsRes } = useQuery({
    queryKey: ["stats"],
    queryFn: api.getStats,
    refetchInterval: 5000,
  });

  const { data: pads } = useQuery({
    queryKey: ["landingPads"],
    queryFn: api.getLandingPads,
    refetchInterval: 5000,
  });

  const { data: missions } = useQuery({
    queryKey: ["missions"],
    queryFn: () => api.getMissions(),
    refetchInterval: 5000,
  });

  const stats = statsRes?.data;
  const activeDrones = stats?.active_drones ?? "--";
  const availablePads =
    pads != null
      ? pads.filter((p) => p.status === "available").length
      : "--";
  const todayMissions =
    missions != null
      ? missions.filter((m) => {
          const today = new Date().toDateString();
          return new Date(m.created_at).toDateString() === today;
        }).length
      : "--";

  return (
    <div>
      <div className="dashboard-grid">
        <div className="card">
          <div className="card-header">Active Drones</div>
          <div className="card-value">{activeDrones}</div>
        </div>
        <div className="card">
          <div className="card-header">Active Flights</div>
          <div className="card-value">{activeDrones}</div>
        </div>
        <div className="card">
          <div className="card-header">Available Pads</div>
          <div className="card-value">{availablePads}</div>
        </div>
        <div className="card">
          <div className="card-header">Today's Missions</div>
          <div className="card-value">{todayMissions}</div>
        </div>
      </div>
      <div className="card">
        <div className="card-header">Live Map</div>
        <MapView />
      </div>
      <div className="card">
        <div className="card-header">Altitude Profile</div>
        <AltitudeChart />
      </div>
      <div className="card">
        <div className="card-header">Telemetry Charts</div>
        <TelemetryCharts />
      </div>
    </div>
  );
}

export default App;
