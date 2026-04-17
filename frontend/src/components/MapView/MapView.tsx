import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
} from "react-leaflet";
import L from "leaflet";
import { useWebSocket } from "../../hooks/useWebSocket";

interface TelemetryPoint {
  drone_id: string;
  latitude: number;
  longitude: number;
  altitude: number;
  timestamp: string;
}

// Simple drone icon using Leaflet divIcon
const droneIcon = L.divIcon({
  html: `<div style="
    width: 28px; height: 28px;
    background: #3b82f6;
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

function MapView() {
  const [position, setPosition] = useState<[number, number] | null>(null);
  const [trail, setTrail] = useState<[number, number][]>([]);
  const [altitude, setAltitude] = useState<number | null>(null);

  // Songshan Airport — route start
  const defaultCenter: [number, number] = [25.0634, 121.5522];

  // Load historical trail on mount
  useEffect(() => {
    fetch("/api/v1/telemetry/history?drone_id=drone-001&limit=500")
      .then((res) => res.json())
      .then((body) => {
        if (body.success && body.data.length > 0) {
          const coords: [number, number][] = body.data.map(
            (p: TelemetryPoint) => [p.latitude, p.longitude]
          );
          setTrail(coords);
          setPosition(coords[coords.length - 1]);
          setAltitude(body.data[body.data.length - 1].altitude);
        }
      })
      .catch(() => {
        // Backend may not be ready yet; WebSocket will fill in shortly
      });
  }, []);

  // Real-time updates from WebSocket
  const { data: telemetry } = useWebSocket<TelemetryPoint>("telemetry");

  useEffect(() => {
    if (!telemetry) return;
    const newPos: [number, number] = [telemetry.latitude, telemetry.longitude];
    setPosition(newPos);
    setAltitude(telemetry.altitude);
    setTrail((prev) => [...prev.slice(-499), newPos]);
  }, [telemetry]);

  return (
    <div className="map-container">
      <MapContainer
        center={defaultCenter}
        zoom={14}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {trail.length > 1 && (
          <Polyline positions={trail} color="#3b82f6" opacity={0.6} weight={2} />
        )}

        {position && (
          <Marker position={position} icon={droneIcon}>
            <Popup>
              <strong>drone-001</strong>
              <br />
              Lat: {position[0].toFixed(5)}
              <br />
              Lon: {position[1].toFixed(5)}
              <br />
              Alt: {altitude?.toFixed(1)} m
            </Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}

export default MapView;
