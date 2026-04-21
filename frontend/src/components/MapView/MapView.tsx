import React, { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
} from "react-leaflet";
import L from "leaflet";
import { useQuery } from "@tanstack/react-query";
import { useWebSocket } from "../../hooks/useWebSocket";
import { api } from "../../services/api";
import type { LandingPad } from "../../services/api";

interface DroneState {
  droneId: string;
  position: [number, number];
  trail: [number, number][];
  altitude: number;
  battery: number | null;
}

const DRONE_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7"];

function droneColor(droneId: string): string {
  const hash = [...droneId].reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return DRONE_COLORS[hash % DRONE_COLORS.length];
}

function makeDroneIcon(color: string) {
  return L.divIcon({
    html: `<div style="
      width: 28px; height: 28px;
      background: ${color};
      border: 2px solid #fff;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    ">✈</div>`,
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -16],
  });
}

const PAD_STATUS_COLORS: Record<string, string> = {
  available: "#22c55e",
  reserved: "#eab308",
  occupied: "#ef4444",
  maintenance: "#6b7280",
};

function makePadIcon(status: string) {
  const color = PAD_STATUS_COLORS[status] ?? "#6b7280";
  return L.divIcon({
    html: `<div style="
      width: 22px; height: 22px;
      background: ${color};
      border: 2px solid #fff;
      border-radius: 4px;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px;
      font-weight: bold;
      color: #fff;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    ">P</div>`,
    className: "",
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -14],
  });
}

function MapView() {
  const [drones, setDrones] = useState<Map<string, DroneState>>(new Map());
  const defaultCenter: [number, number] = [25.0634, 121.5522];

  const { lastRawMessage } = useWebSocket<unknown>("telemetry");

  useEffect(() => {
    if (!lastRawMessage) return;
    const msg = lastRawMessage as {
      type: string;
      drone_id?: string;
      data?: {
        latitude: number;
        longitude: number;
        altitude: number;
        battery_level?: number | null;
      };
    };
    if (msg.type !== "telemetry_update" || !msg.drone_id || !msg.data) return;

    const droneId = msg.drone_id;
    const d = msg.data;
    const newPos: [number, number] = [d.latitude, d.longitude];

    setDrones((prev) => {
      const updated = new Map(prev);
      const existing = updated.get(droneId);
      updated.set(droneId, {
        droneId,
        position: newPos,
        altitude: d.altitude,
        battery: d.battery_level ?? null,
        trail: existing
          ? [...existing.trail.slice(-499), newPos]
          : [newPos],
      });
      return updated;
    });
  }, [lastRawMessage]);

  const { data: pads } = useQuery<LandingPad[]>({
    queryKey: ["landing-pads-map"],
    queryFn: api.getLandingPads,
    refetchInterval: 5000,
  });

  return (
    <div className="map-container">
      <MapContainer
        center={defaultCenter}
        zoom={13}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {Array.from(drones.values()).map((drone) => {
          const color = droneColor(drone.droneId);
          return (
            <React.Fragment key={drone.droneId}>
              {drone.trail.length > 1 && (
                <Polyline
                  positions={drone.trail}
                  color={color}
                  opacity={0.6}
                  weight={2}
                />
              )}
              <Marker position={drone.position} icon={makeDroneIcon(color)}>
                <Popup>
                  <strong>{drone.droneId}</strong>
                  <br />
                  Alt: {drone.altitude?.toFixed(1)} m
                  <br />
                  Battery:{" "}
                  {drone.battery != null
                    ? `${drone.battery.toFixed(0)}%`
                    : "--"}
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {pads?.map((pad) => (
          <Marker
            key={pad.id}
            position={[pad.latitude, pad.longitude]}
            icon={makePadIcon(pad.status)}
          >
            <Popup>
              <strong>{pad.name}</strong>
              <br />
              Status: {pad.status}
              <br />
              Charger: {pad.has_charger ? "Yes" : "No"}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

export default MapView;
