import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useWebSocket } from "../../hooks/useWebSocket";

interface TelemetryPoint {
  altitude: number;
  battery_level: number | null;
  speed: number | null;
  timestamp: string;
}

interface ChartPoint {
  time: string;
  altitude: number;
  battery: number | null;
  speed: number | null;
}

function MiniChart({
  data,
  dataKey,
  color,
  unit,
  label,
  warnBelow,
}: {
  data: ChartPoint[];
  dataKey: keyof ChartPoint;
  color: string;
  unit: string;
  label: string;
  warnBelow?: number;
}) {
  const latest = data.length > 0 ? (data[data.length - 1][dataKey] as number | null) : null;
  const isWarning = warnBelow != null && latest != null && latest < warnBelow;
  const lineColor = isWarning ? "#ef4444" : color;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 2 }}>
        {label}
        {latest != null && (
          <span
            style={{
              marginLeft: 8,
              color: isWarning ? "#ef4444" : "#e2e8f0",
              fontWeight: isWarning ? 700 : 400,
            }}
          >
            {typeof latest === "number" ? latest.toFixed(1) : "--"} {unit}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={130}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis unit={unit} tick={{ fontSize: 10 }} width={42} />
          <Tooltip formatter={(v: number) => [`${v} ${unit}`, label]} />
          <Line
            type="monotone"
            dataKey={dataKey as string}
            stroke={lineColor}
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function TelemetryCharts() {
  const [data, setData] = useState<ChartPoint[]>([]);
  const { data: telemetry } = useWebSocket<TelemetryPoint>("telemetry");

  useEffect(() => {
    if (!telemetry) return;
    setData((prev) => [
      ...prev.slice(-59),
      {
        time: new Date(telemetry.timestamp).toLocaleTimeString(),
        altitude: Math.round(telemetry.altitude * 10) / 10,
        battery: telemetry.battery_level != null ? Math.round(telemetry.battery_level * 10) / 10 : null,
        speed: telemetry.speed != null ? Math.round(telemetry.speed * 10) / 10 : null,
      },
    ]);
  }, [telemetry]);

  return (
    <div>
      <MiniChart data={data} dataKey="altitude" color="#3b82f6" unit="m" label="Altitude" />
      <MiniChart data={data} dataKey="battery" color="#22c55e" unit="%" label="Battery" warnBelow={20} />
      <MiniChart data={data} dataKey="speed" color="#a855f7" unit="m/s" label="Speed" />
    </div>
  );
}

export default TelemetryCharts;
