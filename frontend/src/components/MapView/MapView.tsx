import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { TelemetryData } from "../../services/api";

function MapView() {
  const { data: telemetry } = useWebSocket<TelemetryData>("telemetry");

  // Default center: Taipei
  const center: [number, number] = [25.033, 121.5654];

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={14}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {telemetry && (
          <Marker position={[telemetry.latitude, telemetry.longitude]}>
            <Popup>
              <div>
                <strong>Drone: {telemetry.drone_id}</strong>
                <br />
                Alt: {telemetry.altitude?.toFixed(1)}m | Speed:{" "}
                {telemetry.speed?.toFixed(1)}m/s
                <br />
                Battery: {telemetry.battery_level?.toFixed(0)}%
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}

export default MapView;
