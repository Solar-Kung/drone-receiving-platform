import { Routes, Route, NavLink } from "react-router-dom";
import MapView from "./components/MapView/MapView";
import AltitudeChart from "./components/AltitudeChart/AltitudeChart";
import TelemetryPanel from "./components/TelemetryPanel/TelemetryPanel";
import LandingControl from "./components/LandingControl/LandingControl";
import InspectionReport from "./components/InspectionReport/InspectionReport";

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
    </div>
  );
}

function Dashboard() {
  return (
    <div>
      <div className="dashboard-grid">
        <div className="card">
          <div className="card-header">Active Drones</div>
          <div className="card-value">--</div>
        </div>
        <div className="card">
          <div className="card-header">Active Flights</div>
          <div className="card-value">--</div>
        </div>
        <div className="card">
          <div className="card-header">Available Pads</div>
          <div className="card-value">--</div>
        </div>
        <div className="card">
          <div className="card-header">Today's Missions</div>
          <div className="card-value">--</div>
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
    </div>
  );
}

export default App;
