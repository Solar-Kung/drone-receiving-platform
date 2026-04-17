import axios from "axios";

const client = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// --- Types ---

export interface TelemetryData {
  drone_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number | null;
  heading: number | null;
  battery_level: number | null;
  signal_strength: number | null;
}

export interface StatsSummary {
  active_drones: number;
  total_telemetry_points: number;
  latest_altitude: number | null;
  uptime_since: string;
}

export interface Drone {
  id: string;
  name: string;
  model: string;
  serial_number: string;
  is_active: boolean;
  created_at: string;
}

export interface FlightRecord {
  id: string;
  drone_id: string;
  status: string;
  takeoff_time: string | null;
  landing_time: string | null;
  created_at: string;
}

export interface LandingPad {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  altitude: number;
  status: string;
  has_charger: boolean;
  max_drone_weight: number | null;
  created_at: string;
}

export interface Mission {
  id: string;
  drone_id: string;
  flight_id: string;
  name: string;
  description: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// --- API Functions ---

export const api = {
  // Drones
  getDrones: async (): Promise<Drone[]> => {
    const { data } = await client.get("/flights/drones");
    return data;
  },

  // Flights
  getFlights: async (params?: {
    status?: string;
    drone_id?: string;
  }): Promise<FlightRecord[]> => {
    const { data } = await client.get("/flights", { params });
    return data;
  },

  // Landing Pads
  getLandingPads: async (): Promise<LandingPad[]> => {
    const { data } = await client.get("/landings/pads");
    return data;
  },

  // Missions
  getMissions: async (params?: {
    status?: string;
    drone_id?: string;
  }): Promise<Mission[]> => {
    const { data } = await client.get("/data/missions", { params });
    return data;
  },

  // Stats
  getStats: async (): Promise<{ success: boolean; data: StatsSummary }> => {
    const { data } = await client.get("/stats/summary");
    return data;
  },
};
