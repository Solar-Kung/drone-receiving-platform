# Drone Telemetry Receiving Platform — Implementation Plan

> 無人機巡檢監控接收站 — 分階段實作規劃
>
> 本文件供 Claude Code 參考，涵蓋 API 設計、系統架構、每個 Phase 的具體實作步驟與驗收標準。

---

## Project Overview

一個 **drone inspection monitoring receiving station**，接收無人機遙測資料（經緯度、高度），提供即時飛行軌跡視覺化與監控。所有無人機資料為 AI 模擬產生，無真實物理無人機。

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python), async SQLAlchemy |
| Frontend | React + Vite + TypeScript |
| Database | TimescaleDB (time-series PostgreSQL) |
| Cache / Pub-Sub | Redis |
| Object Storage | MinIO (S3-compatible) |
| Infrastructure | Docker Compose |

### Current Codebase Status

- 7 data models 已定義（`Drone`, `FlightRecord`, `TelemetryData`, `LandingPad`, `LandingSchedule`, `Mission`, `InspectionImage`）
- 15+ REST endpoints 已 scaffold
- 3 WebSocket channels 已建立（`telemetry`, `flights`, `landings`）
- Frontend dashboard 卡片全部顯示 `--`，無即時資料
- Mock mode 僅隨機產生台北座標，無連續飛行軌跡
- `recharts` 已是前端 dependency，但圖表尚未實作

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Simulation Layer                       │
│                                                         │
│  ┌──────────────────┐    ┌────────────────────────┐     │
│  │ Route Definitions │───►│ Telemetry Simulator    │     │
│  │ (waypoint paths)  │    │ (1 Hz GPS generation)  │     │
│  └──────────────────┘    └──────────┬─────────────┘     │
└─────────────────────────────────────┼───────────────────┘
                                      │ POST /api/v1/telemetry
                                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                        │
│                                                         │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │ Telemetry API │──│ WebSocket Srv  │──│ Telemetry   │ │
│  │ POST/GET      │  │ /ws/telemetry  │  │ Service     │ │
│  └──────┬───────┘  └───────┬────────┘  │ validate +  │ │
│         │                  │           │ broadcast   │ │
│         │                  │           └─────────────┘ │
└─────────┼──────────────────┼────────────────────────────┘
          │                  │
          ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│   TimescaleDB    │  │     Redis        │
│   (hypertable)   │  │   (pub/sub)      │
└──────────────────┘  └──────────────────┘
          │                  │
          │    REST          │    WebSocket
          ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                Frontend (React + Vite)                    │
│                                                         │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │  Live Map     │  │ Altitude Chart │  │  Dashboard  │ │
│  │  (Leaflet)    │  │ (Recharts)     │  │  Stats      │ │
│  └──────────────┘  └────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Simulator 透過 REST API 推資料**：simulator 不直接寫 DB 或呼叫 WebSocket，而是 POST 到自己的後端。未來換成真實 drone 推資料時，後端不需要改動。
2. **WebSocket 統一 envelope 格式**：所有 WebSocket 訊息使用 `{ "type": "...", "drone_id": "...", "data": {...} }` 格式，前端根據 `type` 分流處理。
3. **TimescaleDB hypertable**：telemetry 資料天生是 time-series，用 hypertable 以 `timestamp` 分區，時間範圍查詢效率高。
4. **Phase 1 不引入 flight_id 概念**：flight 代表一段完整起降過程，要管理 lifecycle 複雜度會跳很多。先用 `drone_id` 區分資料，Phase 3 再加 flight 概念。

---

## API Design (MVP)

### Phase 1 Endpoints

| Method | Endpoint | Description | Request / Response |
|--------|----------|-------------|-------------------|
| `POST` | `/api/v1/telemetry` | 接收一筆遙測資料 | See below |
| `GET` | `/api/v1/telemetry/latest` | 取得最新一筆 | `?drone_id=drone-001` |
| `GET` | `/api/v1/telemetry/history` | 取得歷史軌跡 | `?drone_id=drone-001&limit=100` |
| `WS` | `/ws/telemetry` | 即時推送 | Envelope format |

### POST /api/v1/telemetry

**Request Body:**

```json
{
  "drone_id": "drone-001",
  "latitude": 25.033,
  "longitude": 121.565,
  "altitude": 120.5,
  "timestamp": "2026-04-14T10:30:00Z"
}
```

**Response:** `201 Created`

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "drone_id": "drone-001",
    "latitude": 25.033,
    "longitude": 121.565,
    "altitude": 120.5,
    "timestamp": "2026-04-14T10:30:00Z"
  }
}
```

**Handler Logic:**
1. Validate input (Pydantic schema)
2. Write to TimescaleDB
3. Broadcast via WebSocket: `manager.broadcast("telemetry", payload)`
4. Return 201

### GET /api/v1/telemetry/latest

**Query Params:** `drone_id` (required)

**Response:**

```json
{
  "success": true,
  "data": {
    "drone_id": "drone-001",
    "latitude": 25.033,
    "longitude": 121.565,
    "altitude": 120.5,
    "timestamp": "2026-04-14T10:30:00Z"
  }
}
```

**Usage:** 前端開頁面時呼叫，初始化地圖位置。

### GET /api/v1/telemetry/history

**Query Params:** `drone_id` (required), `limit` (optional, default 100, max 1000)

**Response:**

```json
{
  "success": true,
  "data": [
    { "latitude": 25.033, "longitude": 121.565, "altitude": 120.5, "timestamp": "..." },
    { "latitude": 25.034, "longitude": 121.566, "altitude": 121.0, "timestamp": "..." }
  ],
  "meta": {
    "count": 100,
    "drone_id": "drone-001"
  }
}
```

**Note:** 按 `timestamp` 升序排列。前端用此 API 畫飛行軌跡 Polyline。

### WebSocket Envelope Format

所有 `/ws/telemetry` 訊息統一使用此格式：

```json
{
  "type": "telemetry_update",
  "drone_id": "drone-001",
  "data": {
    "latitude": 25.033,
    "longitude": 121.565,
    "altitude": 120.5,
    "timestamp": "2026-04-14T10:30:00Z"
  }
}
```

Phase 2 擴展後會增加 `type: "alert"` 類型：

```json
{
  "type": "alert",
  "drone_id": "drone-001",
  "level": "warning",
  "message": "Battery low: 18%"
}
```

### Phase 2 Additional Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/stats/summary` | Dashboard 聚合統計 |

**GET /api/v1/stats/summary Response:**

```json
{
  "success": true,
  "data": {
    "active_drones": 1,
    "total_telemetry_points": 3842,
    "latest_altitude": 120.5,
    "active_since": "2026-04-14T08:00:00Z"
  }
}
```

### Phase 3 Additional Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/flights` | 建立 flight record |
| `PATCH` | `/api/v1/flights/{id}/status` | 更新 flight 狀態 |
| `GET` | `/api/v1/flights/active` | 取得進行中的 flights |
| `POST` | `/api/v1/landings/pads` | 建立 landing pad |
| `POST` | `/api/v1/landings/reserve` | 預約 landing pad |
| `POST` | `/api/v1/landings/release` | 釋放 landing pad |

### Phase 4 Additional Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/simulation/control` | 模擬控制 (start/pause/speed) |
| `GET` | `/api/v1/simulation/status` | 取得模擬狀態 |
| `POST` | `/api/v1/data/missions` | 建立巡檢任務 |
| `POST` | `/api/v1/data/missions/{id}/images` | 上傳巡檢圖片 |

---

## Phase 1 — Single Drone Telemetry Pipeline

**Goal:** 一架無人機，資料從模擬器流到前端，地圖上有東西在動。

**Deliverables:** 即時地圖 + 飛行軌跡 + 高度圖表

### 1A. Data Model (Slim TelemetryData)

**File:** `backend/app/models/telemetry.py`

保留 `TelemetryData` 的核心欄位，其他設為 nullable：

```python
class TelemetryData(Base):
    __tablename__ = "telemetry_data"

    id = Column(UUID, primary_key=True, default=uuid4)
    drone_id = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Phase 2 fields — nullable for now
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    signal_strength = Column(Float, nullable=True)
```

**TimescaleDB Setup:**

```sql
SELECT create_hypertable('telemetry_data', 'timestamp');
```

確認在 `main.py` 的 `lifespan` 中執行 hypertable 建立（如果尚未設定）。

**Acceptance Criteria:**
- [ ] Model 定義完成，migration 可執行
- [ ] TimescaleDB hypertable 正確建立
- [ ] 可透過 SQLAlchemy 寫入和查詢

### 1B. REST Endpoints + WebSocket Broadcast

**Files:**
- `backend/app/api/telemetry.py` — 新建 router
- `backend/app/api/websocket.py` — 修改現有 broadcast 邏輯

**Implementation Details:**

```python
# backend/app/api/telemetry.py

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

@router.post("/", status_code=201)
async def receive_telemetry(data: TelemetryCreate, db: AsyncSession = Depends(get_db)):
    # 1. Write to TimescaleDB
    telemetry = TelemetryData(**data.dict())
    db.add(telemetry)
    await db.commit()

    # 2. Broadcast via WebSocket
    await manager.broadcast("telemetry", {
        "type": "telemetry_update",
        "drone_id": data.drone_id,
        "data": {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "altitude": data.altitude,
            "timestamp": data.timestamp.isoformat()
        }
    })

    return {"success": True, "data": telemetry}

@router.get("/latest")
async def get_latest(drone_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TelemetryData)
        .where(TelemetryData.drone_id == drone_id)
        .order_by(TelemetryData.timestamp.desc())
        .limit(1)
    )
    return {"success": True, "data": result.scalar_one_or_none()}

@router.get("/history")
async def get_history(drone_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TelemetryData)
        .where(TelemetryData.drone_id == drone_id)
        .order_by(TelemetryData.timestamp.asc())
        .limit(min(limit, 1000))
    )
    rows = result.scalars().all()
    return {"success": True, "data": rows, "meta": {"count": len(rows), "drone_id": drone_id}}
```

**Pydantic Schemas:**

```python
# backend/app/schemas/telemetry.py

class TelemetryCreate(BaseModel):
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime

class TelemetryResponse(BaseModel):
    id: UUID
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime
```

**Acceptance Criteria:**
- [ ] `POST /api/v1/telemetry` 寫入 DB 並回傳 201
- [ ] `GET /api/v1/telemetry/latest?drone_id=drone-001` 回傳最新一筆
- [ ] `GET /api/v1/telemetry/history?drone_id=drone-001&limit=50` 回傳升序資料
- [ ] POST 後 WebSocket client 收到即時推送
- [ ] 用 Swagger UI (`localhost:8000/docs`) 手動測試通過

### 1C. Telemetry Simulator

**File:** `backend/app/simulation/telemetry_simulator.py`

**Route Definition — 台北基隆河路線:**

```python
# Predefined waypoints: 松山機場 → 基隆河沿岸 → 大直 → 圓山
TAIPEI_ROUTE = [
    {"lat": 25.0634, "lon": 121.5522, "alt": 0},      # 松山機場（起飛點）
    {"lat": 25.0634, "lon": 121.5522, "alt": 80},      # 爬升
    {"lat": 25.0670, "lon": 121.5450, "alt": 120},     # 基隆河上空
    {"lat": 25.0720, "lon": 121.5380, "alt": 120},     # 沿河飛行
    {"lat": 25.0780, "lon": 121.5310, "alt": 120},     # 大直橋附近
    {"lat": 25.0830, "lon": 121.5250, "alt": 120},     # 圓山附近
    {"lat": 25.0800, "lon": 121.5200, "alt": 100},     # 開始下降
    {"lat": 25.0750, "lon": 121.5150, "alt": 60},      # 下降中
    {"lat": 25.0700, "lon": 121.5250, "alt": 30},      # 返回
    {"lat": 25.0634, "lon": 121.5522, "alt": 0},       # 回到起點降落
]
```

**Simulator Core Logic:**

```python
class TelemetrySimulator:
    def __init__(self, drone_id: str, route: list, base_url: str, speed_multiplier: float = 1.0):
        self.drone_id = drone_id
        self.route = route
        self.base_url = base_url
        self.speed_multiplier = speed_multiplier  # 預留給 Phase 4 控制面板
        self.running = False

    async def start(self):
        self.running = True
        async with httpx.AsyncClient() as client:
            while self.running:
                for i in range(len(self.route) - 1):
                    start = self.route[i]
                    end = self.route[i + 1]
                    # 根據兩點距離決定插值步數（約每秒移動一步）
                    steps = max(int(self._distance(start, end) / 0.0003), 5)
                    for step in range(steps):
                        if not self.running:
                            return
                        t = step / steps
                        point = self._interpolate(start, end, t)
                        await client.post(f"{self.base_url}/api/v1/telemetry", json={
                            "drone_id": self.drone_id,
                            "latitude": point["lat"],
                            "longitude": point["lon"],
                            "altitude": point["alt"],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        await asyncio.sleep(1.0 / self.speed_multiplier)

    def _interpolate(self, start, end, t):
        return {
            "lat": start["lat"] + (end["lat"] - start["lat"]) * t,
            "lon": start["lon"] + (end["lon"] - start["lon"]) * t,
            "alt": start["alt"] + (end["alt"] - start["alt"]) * t,
        }

    def _distance(self, a, b):
        return ((a["lat"] - b["lat"])**2 + (a["lon"] - b["lon"])**2) ** 0.5

    async def stop(self):
        self.running = False
```

**Integration with FastAPI lifespan:**

```python
# backend/app/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(...)
    await ensure_buckets()

    simulator = TelemetrySimulator(
        drone_id="drone-001",
        route=TAIPEI_ROUTE,
        base_url="http://localhost:8000",
        speed_multiplier=1.0
    )
    task = asyncio.create_task(simulator.start())

    yield

    # Shutdown
    await simulator.stop()
    task.cancel()
```

**Acceptance Criteria:**
- [ ] `docker compose up` 後 simulator 自動啟動
- [ ] 每秒在 backend log 中看到 POST 請求
- [ ] 無人機沿預定義路線移動（非隨機跳躍）
- [ ] 飛完一圈後自動重新開始

### 1D. Frontend — Live Map + Flight Trail

**File:** `frontend/src/components/MapView.tsx`

**Implementation:**

```tsx
// Key logic (pseudocode for reference)

const MapView = () => {
  const [trail, setTrail] = useState<[number, number][]>([]);
  const [position, setPosition] = useState<[number, number] | null>(null);
  const ws = useWebSocket("/ws/telemetry");

  // 1. 初始化：載入歷史軌跡
  useEffect(() => {
    fetch("/api/v1/telemetry/history?drone_id=drone-001&limit=200")
      .then(res => res.json())
      .then(data => {
        const coords = data.data.map(p => [p.latitude, p.longitude]);
        setTrail(coords);
        if (coords.length > 0) setPosition(coords[coords.length - 1]);
      });
  }, []);

  // 2. WebSocket：即時更新
  useEffect(() => {
    if (ws.lastMessage) {
      const msg = JSON.parse(ws.lastMessage);
      if (msg.type === "telemetry_update") {
        const newPos: [number, number] = [msg.data.latitude, msg.data.longitude];
        setPosition(newPos);
        setTrail(prev => [...prev.slice(-500), newPos]); // 保留最近 500 點
      }
    }
  }, [ws.lastMessage]);

  return (
    <MapContainer center={[25.0634, 121.5522]} zoom={14}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {position && <Marker position={position} icon={droneIcon}>
        <Popup>Altitude: {altitude}m</Popup>
      </Marker>}
      {trail.length > 1 && <Polyline positions={trail} color="blue" opacity={0.6} />}
    </MapContainer>
  );
};
```

**Acceptance Criteria:**
- [ ] 打開瀏覽器看到無人機 marker 在地圖上移動
- [ ] marker 後面有連續的藍色軌跡線
- [ ] 重新整理頁面後，歷史軌跡立即顯示
- [ ] Popup 顯示目前高度

### 1E. Frontend — Altitude Chart

**File:** `frontend/src/components/AltitudeChart.tsx`

**Implementation:**

```tsx
// Uses recharts (already a dependency)
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

const AltitudeChart = () => {
  const [data, setData] = useState<{time: string, altitude: number}[]>([]);
  const ws = useWebSocket("/ws/telemetry");

  useEffect(() => {
    if (ws.lastMessage) {
      const msg = JSON.parse(ws.lastMessage);
      if (msg.type === "telemetry_update") {
        setData(prev => [
          ...prev.slice(-60),  // 保留最近 60 秒
          {
            time: new Date(msg.data.timestamp).toLocaleTimeString(),
            altitude: msg.data.altitude
          }
        ]);
      }
    }
  }, [ws.lastMessage]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <XAxis dataKey="time" />
        <YAxis domain={[0, 150]} label={{ value: 'm', position: 'insideLeft' }} />
        <Tooltip />
        <Line type="monotone" dataKey="altitude" stroke="#3b82f6" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
};
```

**Acceptance Criteria:**
- [ ] 高度圖表即時滾動更新
- [ ] 能看到起飛爬升、巡航、下降的曲線
- [ ] X 軸顯示時間，Y 軸顯示高度 (m)

### Phase 1 Integration Test

完成所有子步驟後的端到端驗證：

1. `docker compose up -d`
2. 等待 5 秒，打開 `http://localhost:3000`
3. 確認：地圖上有無人機在沿基隆河移動
4. 確認：軌跡線連續（非跳躍）
5. 確認：高度圖表即時更新
6. 打開 `http://localhost:8000/docs`，GET `/api/v1/telemetry/history?drone_id=drone-001` 回傳資料
7. 開兩個瀏覽器 tab，兩邊地圖同步更新

---

## Phase 2 — Dashboard + Richer Telemetry

**Goal:** Dashboard 卡片顯示 live 數字，遙測資料擴展到 battery/speed/heading，告警系統。

**Depends on:** Phase 1 完成

### 2A. Stats Endpoint

**File:** `backend/app/api/stats.py`

新建 `GET /api/v1/stats/summary`，後端做聚合查詢：

```python
@router.get("/api/v1/stats/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    thirty_sec_ago = now - timedelta(seconds=30)

    # Active drones: distinct drone_id with telemetry in last 30s
    active = await db.execute(
        select(func.count(distinct(TelemetryData.drone_id)))
        .where(TelemetryData.timestamp > thirty_sec_ago)
    )

    # Total points
    total = await db.execute(select(func.count(TelemetryData.id)))

    # Latest altitude
    latest = await db.execute(
        select(TelemetryData.altitude)
        .order_by(TelemetryData.timestamp.desc())
        .limit(1)
    )

    return {
        "success": True,
        "data": {
            "active_drones": active.scalar(),
            "total_telemetry_points": total.scalar(),
            "latest_altitude": latest.scalar(),
            "active_since": now.isoformat()
        }
    }
```

**Acceptance Criteria:**
- [ ] Endpoint 回傳正確聚合數字
- [ ] Active drones 在 simulator 運行時 >= 1

### 2B. Dashboard UI

**File:** `frontend/src/components/Dashboard.tsx`

將四張 `--` 卡片改為用 TanStack Query 呼叫 stats API：

```tsx
const { data } = useQuery({
  queryKey: ['stats'],
  queryFn: () => api.get('/stats/summary'),
  refetchInterval: 5000  // 每 5 秒 refetch
});
```

**Acceptance Criteria:**
- [ ] Dashboard 卡片顯示 live 數字
- [ ] 數字每 5 秒自動更新

### 2C. Extended Telemetry Fields

**Changes:**
- 更新 `TelemetryCreate` schema 加入 optional `battery`, `speed`, `heading` 欄位
- 更新 POST handler 處理新欄位
- 更新 simulator 產生額外資料：
  - `battery`: 從 100% 線性遞減，每秒 -0.05%
  - `speed`: 根據相鄰 waypoint 距離計算，巡航 ~10 m/s
  - `heading`: 根據移動方向計算（atan2）
- 更新 WebSocket envelope 加入三個欄位

**Acceptance Criteria:**
- [ ] POST 可接收 battery/speed/heading
- [ ] Simulator 產生合理的 battery drain 曲線
- [ ] WebSocket 訊息包含擴展欄位

### 2D. Multi-Chart Panel

**File:** `frontend/src/components/TelemetryCharts.tsx`

擴展 AltitudeChart 為多圖表 panel：

- Tab 式或堆疊式顯示三條線：altitude, battery, speed
- 共用 X 軸（時間）
- Battery 用紅色（< 20% 時閃爍）
- Speed 用綠色

**Acceptance Criteria:**
- [ ] 三個圖表即時更新
- [ ] Battery < 20% 時有視覺警示

### 2E. Alert System

**Backend:** 在 POST telemetry handler 中加入 alert 邏輯：

```python
if data.battery_level is not None:
    if data.battery_level < 10:
        await manager.broadcast("telemetry", {
            "type": "alert",
            "drone_id": data.drone_id,
            "level": "critical",
            "message": f"Battery critical: {data.battery_level:.0f}%"
        })
    elif data.battery_level < 20:
        await manager.broadcast("telemetry", {
            "type": "alert",
            "drone_id": data.drone_id,
            "level": "warning",
            "message": f"Battery low: {data.battery_level:.0f}%"
        })
```

**Frontend:** 新建 `AlertPanel` 元件，toast 或 badge 顯示告警。

**Acceptance Criteria:**
- [ ] Battery < 20% 時前端出現 warning toast
- [ ] Battery < 10% 時出現 critical alert
- [ ] 現有的 `FlightTracker` battery alert 邏輯正確整合

---

## Phase 3 — Multi-Drone + Flight Lifecycle

**Goal:** 3-5 架無人機同時飛，完整的起降生命週期，landing pad 管理。

**Depends on:** Phase 2 完成

### 3A. Fleet Simulator

**File:** `backend/app/simulation/fleet_simulator.py`

重構 Phase 1 的 `TelemetrySimulator` 為 `FleetSimulator`：

```python
class FleetSimulator:
    def __init__(self, base_url: str, speed_multiplier: float = 1.0):
        self.drones: dict[str, DroneSimulator] = {}
        self.base_url = base_url
        self.speed_multiplier = speed_multiplier

    async def start(self):
        # 定義多條路線
        routes = {
            "drone-001": TAIPEI_RIVER_ROUTE,      # 基隆河巡檢
            "drone-002": SOLAR_FARM_ROUTE,         # 太陽能板場
            "drone-003": BRIDGE_INSPECTION_ROUTE,  # 橋樑檢查
        }

        # Stagger 起飛時間
        for i, (drone_id, route) in enumerate(routes.items()):
            await asyncio.sleep(30 * i)  # 每架間隔 30 秒
            sim = DroneSimulator(drone_id, route, self.base_url, self.speed_multiplier)
            self.drones[drone_id] = sim
            asyncio.create_task(sim.start())
```

**Route Definitions:**

```python
# 路線 1: 基隆河沿岸（同 Phase 1）
TAIPEI_RIVER_ROUTE = [...]

# 路線 2: 太陽能板場巡檢（中和）
SOLAR_FARM_ROUTE = [
    {"lat": 24.9980, "lon": 121.4950, "alt": 0},
    {"lat": 24.9980, "lon": 121.4950, "alt": 60},
    # 網格式飛行：來回掃描
    {"lat": 24.9990, "lon": 121.4950, "alt": 60},
    {"lat": 24.9990, "lon": 121.4970, "alt": 60},
    {"lat": 25.0000, "lon": 121.4970, "alt": 60},
    {"lat": 25.0000, "lon": 121.4950, "alt": 60},
    # ... 更多網格線
    {"lat": 24.9980, "lon": 121.4950, "alt": 0},
]

# 路線 3: 橋樑檢查（新北大橋）
BRIDGE_INSPECTION_ROUTE = [
    {"lat": 25.0570, "lon": 121.4650, "alt": 0},
    {"lat": 25.0570, "lon": 121.4650, "alt": 40},
    # 沿橋低空飛行
    {"lat": 25.0580, "lon": 121.4680, "alt": 30},
    {"lat": 25.0590, "lon": 121.4710, "alt": 25},
    {"lat": 25.0600, "lon": 121.4740, "alt": 30},
    {"lat": 25.0570, "lon": 121.4650, "alt": 0},
]
```

**Also:** 在 startup 時自動建立 drone records 到 DB（用現有 `Drone` model）。

**Acceptance Criteria:**
- [ ] 3 架無人機同時在不同路線飛行
- [ ] 起飛時間間隔 30 秒
- [ ] 每架有獨立的 battery drain 曲線

### 3B. Flight Orchestrator

**File:** `backend/app/simulation/orchestrator.py`

驅動每架 drone 的完整生命週期：

```python
class FlightOrchestrator:
    """
    Flight status lifecycle:
    scheduled → in_flight → approaching → landing → landed → completed

    Trigger conditions:
    - scheduled → in_flight: 起飛時間到達
    - in_flight → approaching: 距離目標 < 500m
    - approaching → landing: LandingManager 分配 pad 成功
    - landing → landed: 高度 = 0 且座標對齊 pad
    - landed → completed: 等待 30 秒（模擬充電）後釋放 pad
    """

    async def run_flight(self, drone_id: str, route: list):
        # 1. Create flight record → scheduled
        flight = await self.create_flight(drone_id, status="scheduled")

        # 2. Start telemetry → in_flight
        await self.update_status(flight.id, "in_flight")
        # Simulator starts generating telemetry...

        # 3. Monitor position, when near destination → approaching
        # (triggered by distance check in telemetry handler)

        # 4. Reserve pad → landing
        pad = await self.landing_manager.assign_pad(drone_id)
        if pad is None:
            # Enter holding pattern (circle until pad available)
            await self.hold(drone_id)

        # 5. Altitude = 0 → landed
        await self.update_status(flight.id, "landed")

        # 6. Wait 30s (charging) → completed, release pad
        await asyncio.sleep(30)
        await self.landing_manager.release_pad(pad.id)
        await self.update_status(flight.id, "completed")
```

**Internal Event Bus (Redis pub/sub):**

```python
# Flight status change → triggers downstream actions
await redis.publish("flight_events", json.dumps({
    "event": "status_changed",
    "flight_id": flight.id,
    "drone_id": drone_id,
    "old_status": "in_flight",
    "new_status": "approaching"
}))
```

**Acceptance Criteria:**
- [ ] Flight records 自動建立並更新狀態
- [ ] 狀態轉換自動觸發（非手動 API call）
- [ ] 前端透過 `/ws/flights` 收到狀態變更通知
- [ ] Holding pattern 在無可用 pad 時正確執行

### 3C. Landing Pad Management

用現有的 `LandingPad` model 和 `LandingManager` service。

**Startup:** 建立 2-3 個 landing pad：

```python
LANDING_PADS = [
    {"name": "松山機場 Pad A", "lat": 25.0634, "lon": 121.5522, "status": "available"},
    {"name": "圓山 Pad B", "lat": 25.0720, "lon": 121.5200, "status": "available"},
    {"name": "大直 Pad C", "lat": 25.0780, "lon": 121.5310, "status": "available"},
]
```

**Pad Lifecycle:** `available → reserved → occupied → available`

**Acceptance Criteria:**
- [ ] Pad 自動被 orchestrator reserve/release
- [ ] 同時兩架 drone approaching 時不會分配同一個 pad
- [ ] Pad 狀態變更透過 `/ws/landings` 即時推送

### 3D. Multi-Drone Map

**File:** `frontend/src/components/MapView.tsx`

修改支援多 marker：

```tsx
// 維護每架 drone 的狀態
const [drones, setDrones] = useState<Map<string, DroneState>>(new Map());

// WebSocket 根據 drone_id 更新對應的 marker 和 trail
if (msg.type === "telemetry_update") {
    setDrones(prev => {
        const updated = new Map(prev);
        const drone = updated.get(msg.drone_id) || { trail: [], position: null };
        drone.position = [msg.data.latitude, msg.data.longitude];
        drone.trail = [...drone.trail.slice(-500), drone.position];
        updated.set(msg.drone_id, drone);
        return updated;
    });
}
```

每架 drone 用不同顏色 marker（根據 drone_id 分配）。

**Acceptance Criteria:**
- [ ] 地圖上同時顯示 3+ 架無人機
- [ ] 每架有獨立的軌跡線和顏色
- [ ] 點擊 marker 顯示該 drone 的資訊

### 3E. Landing Pad UI

在地圖上加 landing pad marker：

- 方形 icon，顏色反映狀態（綠 = available, 黃 = reserved, 紅 = occupied）
- 點擊顯示 pad 資訊（名稱、座標、佔用 drone）
- 整合現有 `LandingControl` 元件

**Acceptance Criteria:**
- [ ] 地圖上顯示 landing pad markers
- [ ] Pad 狀態變更時 marker 顏色即時更新
- [ ] 可看到 drone 降落到 pad 的過程

---

## Phase 4 — Mission, Inspection + Simulation Control

**Goal:** 完整巡檢任務流程、AI 報告、模擬控制面板。

**Depends on:** Phase 3 完成

### 4A. Mission System

**用現有的 `Mission` model。** Orchestrator 在 flight 開始時自動建立 mission，設定 waypoint 列表。

**Mission lifecycle:** `created → in_progress → data_uploading → completed / failed`

**Key Logic:**
- 每到達一個 waypoint，更新 mission 進度
- 透過 WebSocket 推送進度更新：`"Waypoint 5/12 — 42%"`
- Flight 完成時自動 complete mission

**Frontend:** 新建 `MissionProgress` 元件，顯示進度條和 waypoint 列表。

**Acceptance Criteria:**
- [ ] Mission 隨 flight 自動建立
- [ ] 進度即時更新（WebSocket）
- [ ] 前端顯示進度條

### 4B. Inspection Data + AI Reports

**在每個 waypoint 產生模擬巡檢資料：**
- 使用範本圖片 + overlay 文字（或 placeholder 圖片），上傳到 MinIO
- 用範本引擎產生巡檢報告文字，例如：
  - `"Panel A3 — 裂縫偵測, severity: moderate"`
  - `"Bridge section B2 — 鏽蝕, severity: low"`
- 前端 `InspectionReport` 元件顯示圖片 + 報告

**Optional AI Enhancement:** 用 Anthropic API 產生更豐富的報告文字。

**Acceptance Criteria:**
- [ ] 每個 waypoint 產生一張圖片並存入 MinIO
- [ ] 巡檢報告文字自動產生
- [ ] 前端可瀏覽圖片和報告

### 4C. Anomaly Injection

**在 simulator 中隨機注入異常事件：**

```python
ANOMALY_TYPES = {
    "battery_drop": {
        "probability": 0.002,  # 每秒 0.2% 機率
        "effect": lambda state: {**state, "battery": state["battery"] - 15}
    },
    "gps_drift": {
        "probability": 0.001,
        "effect": lambda state: {
            **state,
            "lat": state["lat"] + random.gauss(0, 0.0005),
            "lon": state["lon"] + random.gauss(0, 0.0005)
        }
    },
    "signal_loss": {
        "probability": 0.0005,
        "duration": 5,  # 停止 telemetry 5 秒
    },
    "emergency_return": {
        "probability": 0.0003,
        "effect": "abort_mission_and_return_to_base"
    }
}
```

**Acceptance Criteria:**
- [ ] 偶爾出現 battery 突降，觸發 alert
- [ ] GPS drift 在地圖上可見（軌跡抖動）
- [ ] Signal loss 期間地圖 marker 停止更新
- [ ] Emergency return 改變 flight status 並返航

### 4D. Simulation Control Panel

**Frontend:** 新頁面或 sidebar panel。

**Features:**
- Start / Pause / Stop 模擬
- 速度調整：1x / 2x / 5x（改變 simulator 的 `speed_multiplier`）
- 手動新增/移除 drone
- 場景 preset 選擇：
  - 「例行太陽能板巡檢」
  - 「緊急橋樑檢查」
  - 「多機河岸巡邏」

**Backend:** `POST /api/v1/simulation/control`

```json
{
  "action": "set_speed",
  "value": 2.0
}
```

**Important:** Phase 1 的 simulator 已預留 `speed_multiplier` 參數，此處只需加入 API 和 UI。

**Acceptance Criteria:**
- [ ] 可從 UI 暫停/恢復模擬
- [ ] 速度調整即時生效
- [ ] 可選擇不同場景 preset

---

## File Structure (Target)

```
backend/app/
├── main.py                     # FastAPI app + lifespan
├── config.py                   # Settings
├── database.py                 # Async SQLAlchemy
├── models/
│   ├── telemetry.py            # TelemetryData (Phase 1)
│   ├── drone.py                # Drone (Phase 3)
│   ├── flight.py               # FlightRecord (Phase 3)
│   ├── landing.py              # LandingPad, LandingSchedule (Phase 3)
│   └── mission.py              # Mission, InspectionImage (Phase 4)
├── schemas/
│   ├── telemetry.py            # Pydantic schemas (Phase 1)
│   ├── stats.py                # Stats response (Phase 2)
│   └── simulation.py           # Simulation control (Phase 4)
├── api/
│   ├── telemetry.py            # Telemetry CRUD (Phase 1)
│   ├── websocket.py            # WebSocket manager (Phase 1, existing)
│   ├── stats.py                # Stats endpoint (Phase 2)
│   ├── flights.py              # Flight CRUD (Phase 3, existing)
│   ├── landings.py             # Landing CRUD (Phase 3, existing)
│   ├── data.py                 # Mission/Image CRUD (Phase 4, existing)
│   └── simulation.py           # Simulation control (Phase 4)
├── services/
│   ├── flight_tracker.py       # Flight tracking (existing)
│   ├── landing_manager.py      # Landing pad mgmt (existing)
│   ├── data_collector.py       # Mission/image mgmt (existing)
│   └── minio_client.py         # Object storage (existing)
├── simulation/                 # NEW — all simulation code
│   ├── telemetry_simulator.py  # Single drone sim (Phase 1)
│   ├── fleet_simulator.py      # Multi-drone sim (Phase 3)
│   ├── orchestrator.py         # Flight lifecycle (Phase 3)
│   ├── routes.py               # Predefined waypoint routes (Phase 1)
│   └── anomalies.py            # Anomaly injection (Phase 4)
└── ros_bridge/                 # Existing, not touched until later

frontend/src/
├── App.tsx
├── components/
│   ├── MapView.tsx             # Live map (Phase 1, modify existing)
│   ├── AltitudeChart.tsx       # Altitude chart (Phase 1, new)
│   ├── TelemetryCharts.tsx     # Multi-chart panel (Phase 2, new)
│   ├── Dashboard.tsx           # Stats cards (Phase 2, modify existing)
│   ├── AlertPanel.tsx          # Alert toasts (Phase 2, new)
│   ├── TelemetryPanel.tsx      # Existing
│   ├── LandingControl.tsx      # Existing, modify Phase 3
│   ├── InspectionReport.tsx    # Existing, modify Phase 4
│   ├── MissionProgress.tsx     # Mission progress bar (Phase 4, new)
│   └── SimulationControl.tsx   # Control panel (Phase 4, new)
├── hooks/
│   └── useWebSocket.ts         # Existing, auto-reconnect
└── services/
    └── api.ts                  # Existing, add new query wrappers
```

---

## Estimated Timeline

| Phase | Scope | Duration (solo dev, 2-3 hr/day) |
|-------|-------|---------------------------------|
| Phase 1 | Single drone E2E pipeline | 1-2 weeks |
| Phase 2 | Dashboard + extended telemetry | 1 week |
| Phase 3 | Multi-drone + flight lifecycle | 2-3 weeks |
| Phase 4 | Mission + inspection + control | 2-3 weeks |

**Milestone checkpoints:**
- Phase 1 完成 → 可以 demo「即時無人機追蹤」
- Phase 2 完成 → 完整的監控 dashboard
- Phase 3 完成 → 可展示系統設計能力（多 drone、狀態機、resource management）
- Phase 4 完成 → 完整的模擬平台

---

## References

- **UAV-telemetry** (`kevinbdx35/UAV-telemetry`) — API 設計參考
- **DroneEngineeringEcosystemDEE** (`dronsEETAC/DroneEngineeringEcosystemDEE`) — 事件驅動架構參考
- **mavsdk_drone_show** (`alireza787b/mavsdk_drone_show`) — FastAPI + React + SITL 整合參考
