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
  timestamp: string;
}

interface ChartPoint {
  time: string;
  altitude: number;
}

function AltitudeChart() {
  const [data, setData] = useState<ChartPoint[]>([]);
  const { data: telemetry } = useWebSocket<TelemetryPoint>("telemetry");

  useEffect(() => {
    if (!telemetry) return;
    setData((prev) => [
      ...prev.slice(-59),
      {
        time: new Date(telemetry.timestamp).toLocaleTimeString(),
        altitude: Math.round(telemetry.altitude * 10) / 10,
      },
    ]);
  }, [telemetry]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <XAxis
          dataKey="time"
          tick={{ fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[0, "auto"]}
          unit="m"
          tick={{ fontSize: 11 }}
          width={45}
        />
        <Tooltip formatter={(v: number) => [`${v} m`, "Altitude"]} />
        <Line
          type="monotone"
          dataKey="altitude"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default AltitudeChart;
