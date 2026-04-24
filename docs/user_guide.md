# Drone Receiving Platform — User Guide

> 本文件反映 **2026-04-24** 當下的實際能力，以 codebase 稽核為依據。
> 未來新增功能請更新本文件。

---

## 1. 這個平台是什麼

**無人機巡檢監控接收站**（drone-receiving-platform）是一套模擬驅動的無人機遙測收集與即時展示系統。所有飛行資料皆為 AI 模擬產生，沒有實體無人機。

**一句話資料流：** 內建 FleetSimulator 每秒透過 REST API 推送模擬遙測 → 寫入 TimescaleDB + 廣播到 Redis pub/sub → 每個 backend instance 從 Redis 訂閱後推送到連線中的 WebSocket 用戶端 → React 前端即時更新地圖、圖表、任務進度。

**誰該讀這份文件：**
- **開發者 / 接手者** — 第 3、4、8 節：如何跑起來、架構決策、開發工作流
- **API 整合方** — 第 5 節：所有 endpoint、request / response schema、curl 範例
- **Demo 觀眾** — 第 6 節：前端頁面各自看到什麼

---

## 2. Status at a Glance

| 項目 | 狀態 | 備註 |
|------|------|------|
| Docker Compose 啟動 | ✅ Fully implemented | nginx + backend + frontend + timescaledb + redis + minio |
| REST — POST /api/v1/telemetry | ✅ Fully implemented | 寫 DB + Redis broadcast + battery alert |
| REST — GET /api/v1/telemetry/latest | ✅ Fully implemented | |
| REST — GET /api/v1/telemetry/history | ✅ Fully implemented | |
| REST — GET/POST /api/v1/flights/drones | ✅ Fully implemented | |
| REST — GET /api/v1/flights | ✅ Fully implemented | 可過濾 status / drone_id |
| REST — GET /api/v1/flights/{id} | ✅ Fully implemented | |
| REST — GET /api/v1/flights/{id}/telemetry | 🟡 Partial | 永遠回傳 `[]`（stub，未接 telemetry 表） |
| REST — Landing Pads (GET/POST/PATCH) | ✅ Fully implemented | |
| REST — Landing Schedules (GET/POST) | ✅ Fully implemented | |
| REST — Missions (GET/POST/PATCH) | ✅ Fully implemented | |
| REST — Image Upload & List | ✅ Fully implemented | 上傳到 MinIO，回傳 presigned URL |
| REST — GET /api/v1/stats/summary | ✅ Fully implemented | |
| REST — GET /api/v1/simulation/status | ✅ Fully implemented | follower 回 503 |
| REST — POST /api/v1/simulation/control | ✅ Fully implemented | follower 回 503 |
| WebSocket /ws/telemetry | ✅ Fully implemented | Redis pub/sub fan-out |
| WebSocket /ws/flights | ✅ Fully implemented | Redis pub/sub fan-out |
| WebSocket /ws/landings | ✅ Fully implemented | Redis pub/sub fan-out |
| Fleet Simulator（3 架模擬無人機） | ✅ Fully implemented | drone-001/002/003，三條台北路線 |
| Flight 自動生命週期 | ✅ Fully implemented | scheduled→in_flight→approaching→landing→landed |
| Mission 自動生命週期 | ✅ Fully implemented | created→in_progress→data_uploading→completed |
| Anomaly Injection | ✅ Fully implemented | battery_drop / gps_drift / signal_loss / emergency_return |
| Inspection Image Generation | ✅ Fully implemented | Pillow 合成圖上傳 MinIO |
| AI Inspection Report | ✅ Fully implemented | Anthropic API；無 API key 時用 fallback 範本 |
| Battery Alert（<20% / <10%） | ✅ Fully implemented | `api/telemetry.py:49-63`，走 /ws/telemetry |
| TimescaleDB hypertable | ✅ Fully implemented | `ensure_hypertable()` 每次啟動確認 |
| Redis Pub/Sub + Leader Election | ✅ Fully implemented | Phase 5 WP1 |
| Nginx Load Balancer | ✅ Fully implemented | `docker compose --scale backend=N` |
| UDP Listener（C++ publisher） | ✅ Fully implemented | port 14550 protobuf，leader only |
| Frontend — Dashboard 卡片 | ✅ Fully implemented | 接 API，非 hardcoded |
| Frontend — Live Map（多 marker） | ✅ Fully implemented | Leaflet，500 點軌跡，5 色 |
| Frontend — Telemetry Panel | ✅ Fully implemented | 8 個即時數字卡片 |
| Frontend — Telemetry Charts | ✅ Fully implemented | altitude / battery / speed 三條 recharts |
| Frontend — Landing Control | ✅ Fully implemented | landing pad 狀態格子 |
| Frontend — Inspection Report | ✅ Fully implemented | 任務列表、圖片 gallery、AI 報告 |
| Frontend — Alert Panel（Toast） | ✅ Fully implemented | 10s auto-expire，固定右下角 |
| Frontend — Mission Progress | ✅ Fully implemented | per-drone 進度條，WebSocket 驅動 |
| Frontend — Simulation Control | ✅ Fully implemented | pause/resume/speed，per-drone 狀態表 |
| ROS 2 Bridge（Telemetry Subscriber） | 🟡 Partial | 類別存在，mock mode 有實作，但 main.py 未啟動 |
| ROS 2 Bridge（Image Subscriber） | 🟡 Partial | 類別存在，無 ROS 2 時只 sleep，main.py 未啟動 |
| ROS 2 Bridge（Mission Subscriber） | 🟡 Partial | 類別存在，無 ROS 2 時只 sleep，main.py 未啟動 |
| Authentication / Authorization | ⬜ Not yet implemented | 所有 endpoint 開放 |

---

## 3. Quick Start

### 3.1 啟動所有服務

```bash
# 複製環境設定（首次）
cp configs/.env.example configs/.env

# 啟動所有服務（background）
docker compose up -d

# 等待 DB migration 與 simulator 初始化（約 15 秒）
sleep 15
```

### 3.2 驗證各服務健康

```bash
# Backend health check
curl -s http://localhost:8000/health
# 預期：{"status":"ok","service":"drone-receiving-platform"}

# 確認 simulator 有在送資料（log 每秒應有 POST 200）
docker compose logs backend --tail=10 | grep "POST /api/v1/telemetry"

# 確認 TimescaleDB hypertable 已建立
docker compose exec timescaledb psql -U drone_admin -d drone_station \
  -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"
# 預期：telemetry_data

# 確認 Redis leader election
docker compose exec redis redis-cli GET drone_platform:simulation_leader
# 預期：容器 hostname（非空）
```

### 3.3 看到第一筆 mock telemetry

```bash
# 查詢 drone-001 最新一筆
curl -s "http://localhost:8000/api/v1/telemetry/latest?drone_id=drone-001" | python3 -m json.tool
```

預期回傳包含 `latitude`、`longitude`、`altitude` 的 JSON。若 simulator 剛啟動，可等 5 秒後重試。

### 3.4 Access Points

| 服務 | URL | 說明 |
|------|-----|------|
| 前端 Dashboard | http://localhost:3000 | React 主介面 |
| Swagger UI | http://localhost:8000/docs | 互動式 API 文件 |
| MinIO Console | http://localhost:9001 | 物件儲存管理（帳號：minio_admin / minio_secret） |

---

## 4. 系統架構

### 4.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose Network (drone-net)                          │
│                                                              │
│  ┌──────────┐     ┌──────────────────────────────────────┐  │
│  │ frontend │────►│  nginx :80 (load balancer)           │  │
│  │  :3000   │     └──────────────┬───────────────────────┘  │
│  └──────────┘                    │ round-robin               │
│                         ┌────────▼────────┐                  │
│                         │  backend pool   │                  │
│                         │  (N instances)  │                  │
│                         └──┬──────────┬──┘                  │
│                            │          │                      │
│             ┌──────────────▼─┐  ┌─────▼──────────────┐     │
│             │  timescaledb   │  │  redis :6379        │     │
│             │  :5432         │  │  pub/sub + lock     │     │
│             └────────────────┘  └─────────────────────┘     │
│                                                              │
│             ┌──────────────────────────────────────┐        │
│             │  minio :9000/:9001                   │        │
│             │  inspection-images / flight-logs     │        │
│             └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘

External:
  C++ telemetry publisher ──UDP 14550──► backend (leader only)
```

### 4.2 實際資料流

```
FleetSimulator (backend leader)
  │  1 Hz per drone
  ▼
POST /api/v1/telemetry
  │
  ├─► TelemetryData (TimescaleDB)
  │
  └─► manager.broadcast("telemetry", ...)
         │
         ▼  publish to Redis  ws:telemetry
      Redis
         │
         ▼  subscribe_and_dispatch (every backend instance)
      _local_broadcast
         │
         ▼
      WebSocket /ws/telemetry ──► Browser (React)
         │
         ├─► MapView: 更新 drone marker 位置 + 軌跡
         ├─► TelemetryPanel: 更新 8 個數字卡片
         ├─► TelemetryCharts: 更新三條圖表
         ├─► AlertPanel: 檢查 type="alert" → 顯示 toast
         ├─► MissionProgress: 檢查 type="mission_progress" → 更新進度條
         └─► InspectionReport: 檢查 type="inspection_image" / "mission_report"
```

FlightOrchestrator 在 leader instance 內以 callback 形式收到每個 position update，驅動 flight status 狀態機，並呼叫 `manager.broadcast("flights", ...)` 推送到 /ws/flights。

LandingManager 在 pad assign / release 時呼叫 `manager.broadcast("landings", ...)` 推送到 /ws/landings。

### 4.3 重要設計決策

**Simulator 走 REST，不直接寫 DB**
FleetSimulator 透過 `httpx.AsyncClient` POST 到 `/api/v1/telemetry`，和真實無人機使用同一條 API 路徑。這讓模擬與真實資料流可以直接互換。

**WebSocket envelope 格式**
所有 WebSocket 訊息使用統一 envelope：
```json
{
  "type": "telemetry_update",
  "drone_id": "drone-001",
  "data": { ... }
}
```
前端用 `type` 欄位路由處理邏輯。

**Redis Pub/Sub Fan-out（Phase 5）**
每個 `manager.broadcast()` 呼叫 publish 到 Redis。每個 backend instance 各自訂閱 Redis 並呼叫 `_local_broadcast()` 發給本地 WebSocket 連線，實現水平擴展。

**Leader Election**
啟動時以 `Redis SET NX EX 60` 搶 `drone_platform:simulation_leader` 鎖。取得鎖的 instance 啟動 FleetSimulator + FlightOrchestrator + UDP listener；其他 instance 只服務 REST/WebSocket。Leader 每 30 秒 refresh TTL。

---

## 5. 使用指南 — Backend

### 5.1 REST API

所有 endpoint 的互動式文件在 **http://localhost:8000/docs**（Swagger UI）。

#### Telemetry（`/api/v1/telemetry`）

**POST /api/v1/telemetry** — 接收遙測並廣播
```bash
curl -s -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "drone-001",
    "latitude": 25.0330,
    "longitude": 121.5654,
    "altitude": 100.0,
    "timestamp": "2026-04-24T12:00:00Z",
    "battery_level": 85.0,
    "speed": 10.5,
    "heading": 270.0,
    "signal_strength": 95.0
  }'
```
Response HTTP 201：`{"success": true, "data": {...}}`

Battery alert 邏輯（`api/telemetry.py:49-63`）：
- `battery_level < 20` → 廣播 `type="alert", level="warning"`
- `battery_level < 10` → 廣播 `type="alert", level="critical"`

**GET /api/v1/telemetry/latest?drone_id=drone-001**
```bash
curl -s "http://localhost:8000/api/v1/telemetry/latest?drone_id=drone-001"
```
Response：`{"success": true, "data": {id, drone_id, latitude, longitude, altitude, timestamp, battery_level?, speed?, heading?, signal_strength?}}`

**GET /api/v1/telemetry/history?drone_id=drone-001&limit=100**
```bash
curl -s "http://localhost:8000/api/v1/telemetry/history?drone_id=drone-001&limit=50"
```
Response：`{"success": true, "data": [...], "meta": {"count": N, "drone_id": "..."}}`
`limit` 最大 1000；資料以 `timestamp` 升序排列。

---

#### Drones & Flights（`/api/v1/flights`）

**GET /api/v1/flights/drones** — 列出所有活躍無人機
```bash
curl -s http://localhost:8000/api/v1/flights/drones
```
Response：`[{id, name, model, serial_number, is_active, created_at}, ...]`

**POST /api/v1/flights/drones** — 手動建立無人機記錄
```bash
curl -s -X POST http://localhost:8000/api/v1/flights/drones \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Drone", "model": "DJI M300", "serial_number": "SN-TEST-001"}'
```

**GET /api/v1/flights/drones/{drone_id}** — 單機查詢（UUID）

**GET /api/v1/flights/** — 列出所有 flight records
```bash
# 過濾進行中的飛行
curl -s "http://localhost:8000/api/v1/flights/?status=in_flight"
```
可用 query params：`status`（scheduled/in_flight/approaching/landing/landed/completed/aborted）、`drone_id`（UUID）

**GET /api/v1/flights/{flight_id}** — 單筆 flight record

**GET /api/v1/flights/{flight_id}/telemetry** 🟡 — 永遠回傳 `[]`（stub，`api/flights.py:125`）

---

#### Stats（`/api/v1/stats`）

**GET /api/v1/stats/summary**
```bash
curl -s http://localhost:8000/api/v1/stats/summary | python3 -m json.tool
```
Response：
```json
{
  "success": true,
  "data": {
    "active_drones": 3,
    "total_telemetry_points": 12345,
    "latest_altitude": 120.5,
    "uptime_since": "2026-04-24T10:00:00Z"
  }
}
```
`active_drones`：過去 30 秒內有遙測資料的 drone 數量。

---

#### Landing Pads（`/api/v1/landings`）

**GET /api/v1/landings/pads** — 列出所有 landing pad
```bash
curl -s "http://localhost:8000/api/v1/landings/pads?status=available"
```
可用 `status` filter：available / occupied / reserved / maintenance

**POST /api/v1/landings/pads** — 建立 landing pad
```bash
curl -s -X POST http://localhost:8000/api/v1/landings/pads \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Pad", "latitude": 25.04, "longitude": 121.55, "has_charger": true}'
```

**PATCH /api/v1/landings/pads/{pad_id}/status** — 手動更新 pad 狀態
```bash
curl -s -X PATCH http://localhost:8000/api/v1/landings/pads/{pad_id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "maintenance"}'
```

**POST /api/v1/landings/schedules** — 手動建立降落排程
**GET /api/v1/landings/schedules** — 列出降落排程（可用 `pad_id` filter）

注意：正常運作時，orchestrator 會自動呼叫 `landing_manager.assign_pad()` 和 `complete_landing()`，不需要手動操作。

---

#### Missions & Images（`/api/v1/data`）

**GET /api/v1/data/missions** — 列出所有任務
```bash
curl -s "http://localhost:8000/api/v1/data/missions?status=in_progress"
```
可用 `status` filter：created / in_progress / data_uploading / completed / failed；可用 `drone_id` filter

**GET /api/v1/data/missions/{mission_id}** — 單筆任務（含 `report_text` 欄位）

**POST /api/v1/data/missions** — 手動建立任務（正常由 orchestrator 自動建立）

**PATCH /api/v1/data/missions/{mission_id}/status** — 手動更新任務狀態

**POST /api/v1/data/missions/{mission_id}/images** — 上傳巡檢圖片（multipart）
```bash
curl -s -X POST http://localhost:8000/api/v1/data/missions/{mission_id}/images \
  -F "file=@/path/to/image.jpg" \
  -F "captured_at=2026-04-24T12:00:00Z"
```
圖片上傳到 MinIO `inspection-images` bucket，key 格式：`missions/{mission_id}/{filename}`

**GET /api/v1/data/missions/{mission_id}/images** — 列出任務圖片（附 presigned URL，有效期 1 小時）

---

#### Simulation Control（`/api/v1/simulation`）

> 這兩個 endpoint 只在 **leader instance** 有效。Follower 回 HTTP 503 `{"error": "not_leader", "leader_hostname": "..."}` — 重試即可，nginx round-robin 最終會打到 leader。

**GET /api/v1/simulation/status**
```bash
curl -s http://localhost:8000/api/v1/simulation/status
```
Response：`{"paused": false, "speed": 1.0, "drones": [{drone_id, running, paused, stopped}, ...]}`

**POST /api/v1/simulation/control**
```bash
# 暫停
curl -s -X POST http://localhost:8000/api/v1/simulation/control \
  -H "Content-Type: application/json" -d '{"action": "pause"}'

# 恢復
curl -s -X POST http://localhost:8000/api/v1/simulation/control \
  -H "Content-Type: application/json" -d '{"action": "resume"}'

# 加速 2 倍
curl -s -X POST http://localhost:8000/api/v1/simulation/control \
  -H "Content-Type: application/json" -d '{"action": "set_speed", "speed": 2.0}'
```
`speed` 範圍 0.1–10.0。

---

### 5.2 WebSocket

#### 連接方式

| Channel | URL | 用途 |
|---------|-----|------|
| telemetry | `ws://localhost:8000/ws/telemetry` | 遙測、alert、任務進度、報告 |
| flights | `ws://localhost:8000/ws/flights` | flight status 變更 |
| landings | `ws://localhost:8000/ws/landings` | landing pad 狀態變更 |

#### 測試（wscat）

```bash
# 安裝 wscat（若未安裝）
npm install -g wscat

# 訂閱 telemetry channel
wscat -c ws://localhost:8000/ws/telemetry

# 連上後發 ping（server 回 pong）
{"type": "ping"}
```

#### 訊息格式

所有訊息都是 JSON。`type` 欄位決定訊息種類：

**telemetry_update**（1 Hz per drone）
```json
{
  "type": "telemetry_update",
  "drone_id": "drone-001",
  "data": {
    "drone_id": "drone-001",
    "latitude": 25.0634,
    "longitude": 121.5200,
    "altitude": 120.5,
    "timestamp": "2026-04-24T12:00:00Z",
    "battery_level": 85.0,
    "speed": 10.5,
    "heading": 270.0,
    "signal_strength": 95.0
  }
}
```

**alert**（battery < 20%）
```json
{
  "type": "alert",
  "drone_id": "drone-001",
  "level": "warning",
  "message": "Battery low: 18%"
}
```
`level` 可為 `"warning"`（<20%）或 `"critical"`（<10%）。

**flight_status_change**（on /ws/flights）
```json
{
  "type": "flight_status_change",
  "data": {
    "flight_id": "uuid",
    "status": "in_flight",
    "timestamp": "2026-04-24T12:00:00Z"
  }
}
```

**pad_assigned / landing_completed / pad_released**（on /ws/landings）
```json
{
  "type": "pad_assigned",
  "data": {
    "flight_id": "uuid",
    "pad_id": "uuid",
    "pad_name": "Songshan Pad A",
    "scheduled_time": "2026-04-24T12:05:00Z"
  }
}
```

**mission_progress**（on /ws/telemetry）
```json
{
  "type": "mission_progress",
  "drone_id": "drone-001",
  "data": {
    "mission_id": "uuid",
    "current_waypoint": 5,
    "total_waypoints": 12,
    "progress": 41.7
  }
}
```

**inspection_image**（on /ws/telemetry，每個 waypoint 觸發）
```json
{
  "type": "inspection_image",
  "drone_id": "drone-001",
  "data": {
    "mission_id": "uuid",
    "image_id": "uuid",
    "filename": "drone-001_wp3.jpg",
    "waypoint_idx": 3
  }
}
```

**mission_report**（on /ws/telemetry，任務完成後觸發）
```json
{
  "type": "mission_report",
  "drone_id": "drone-001",
  "data": {
    "mission_id": "uuid",
    "report_text": "本次巡檢..."
  }
}
```

#### Ping / Pong

所有三個 channel 的 WebSocket handler 都支援 ping/pong。Client 送 `{"type": "ping"}`，server 回 `{"type": "pong"}`。前端 `useWebSocket.ts` 每 30 秒自動發一次 ping（`hooks/useWebSocket.ts:62-66`）。

#### 重連機制

前端 `useWebSocket.ts:47-51`：連線斷開後 3 秒自動重連。

---

### 5.3 ROS 2 Bridge

三個 ROS 2 subscriber 類別存在於 `backend/app/ros_bridge/` 但**目前 `main.py` lifespan 不啟動任何一個**。它們屬於預留框架，尚未整合進運行時：

| 類別 | 檔案 | 無 ROS 2 時的 fallback |
|------|------|------------------------|
| `TelemetrySubscriber` | `telemetry_sub.py` | `_run_mock_mode()` 已實作（每秒隨機座標），但因類別未被啟動，mock mode 也不會執行 |
| `ImageSubscriber` | `image_sub.py` | standby mode：無限 `sleep(5)` 迴圈 |
| `MissionSubscriber` | `mission_sub.py` | standby mode：無限 `sleep(5)` 迴圈 |

目前的實際遙測來源是 **FleetSimulator** 透過 REST API，不是 ROS 2 bridge。

**UDP Listener**（`ros_bridge/udp_listener.py`）是例外：它**已在 main.py 中啟動**（leader instance），接收來自 C++ telemetry publisher 的 protobuf 封包（port 14550）。

---

## 6. 使用指南 — Frontend

打開瀏覽器 http://localhost:3000，左側 sidebar 有五個頁面。

### 6.1 頁面總覽

| Sidebar 選項 | Route | 主要元件 |
|--------------|-------|---------|
| Dashboard | `/` | 統計卡片 + MapView + AlertPanel + TelemetryCharts + MissionProgress |
| Telemetry | `/telemetry` | TelemetryPanel（即時數字）+ AltitudeChart |
| Landings | `/landings` | LandingControl（pad 狀態格子） |
| Inspections | `/inspections` | InspectionReport（任務列表 + 圖片 gallery + AI 報告） |
| Simulation | `/simulation` | SimulationControl（暫停/速度控制） |

### 6.2 Dashboard

Dashboard 頂部有四個統計卡片，**透過 React Query 每 5 秒重新呼叫 API**（`App.tsx:47-70`）：
- **Active Drones** — 來自 `GET /api/v1/stats/summary`，顯示過去 30 秒有遙測的 drone 數
- **Active Flights** — 來自 `GET /api/v1/flights/` client-side 過濾排除 completed/aborted
- **Landing Pads** — 來自 `GET /api/v1/landings/pads`，顯示 available pad 數量
- **Active Missions** — 來自 `GET /api/v1/data/missions` client-side 過濾 in_progress 數量

卡片資料載入中時顯示 `--`；這不是 hardcoded，而是 API 回傳前的 loading state。

MapView 嵌入 Dashboard 右側，即時顯示所有無人機位置。AlertPanel 以 toast 形式固定在右下角。TelemetryCharts（三條圖表）和 MissionProgress（進度條）也在 Dashboard 底部顯示。

### 6.3 Telemetry Panel

TelemetryPanel 接 `/ws/telemetry` WebSocket，顯示**最新一筆**遙測資料的 8 個欄位：
- 連線狀態 badge（Connected / Disconnected）
- Drone ID、Position（lat/lon 6位小數）、Altitude（公尺）
- Speed（m/s）、Heading（度）、Signal Strength（%）
- Battery（%，顏色：>50% 綠、20-50% 黃、<20% 紅）
- Last Update（timestamp）

注意：TelemetryPanel 顯示的是最後一筆收到的任何 drone 資料，不會區分多架 drone。

AltitudeChart 顯示最近 60 筆高度資料，X 軸為時間，Y 軸為公尺。

### 6.4 Live Map

MapView 在 Dashboard 頁面。使用 Leaflet，以台北為中心。

- **多架無人機**：每架 drone 一個彩色 marker（5 種顏色，by drone_id hash）
- **軌跡線**：每架保留最近 500 個位置點的 polyline
- **點擊 drone marker**：彈出 popup 顯示 drone ID、altitude、battery
- **Landing Pad markers**：方形圖示，顏色對應狀態（綠=available、黃=reserved、紅=occupied、灰=maintenance）
- **點擊 pad marker**：顯示 pad 名稱、狀態、充電設備

地圖資料透過 `/ws/telemetry` WebSocket 即時更新；landing pad 資料每 5 秒透過 REST API 重新抓取（`MapView.tsx:116-120`）。

### 6.5 Landing Control

Landings 頁面顯示所有 landing pad 的狀態格子，每 5 秒 polling `GET /api/v1/landings/pads`。每格顯示：pad 名稱、狀態 badge、座標、是否有充電設備、最大承重。

Landing pad 的 assign/release 由 orchestrator 自動處理，不需要手動操作。

### 6.6 Inspection Reports

Inspections 頁面列出所有任務（每 10 秒 polling），可展開每個任務卡片查看：
- 任務名稱、狀態 badge、waypoint 圖片數量
- 任務描述、開始 / 完成時間
- **展開後**：顯示所有巡檢圖片縮圖（帶 MinIO presigned URL，有效 1 小時）
- **AI 報告**：任務完成後由 orchestrator 觸發生成，顯示在圖片下方

當新圖片或報告透過 WebSocket 到達時，React Query cache 自動更新，頁面即時反映最新內容。

---

## 7. 資料模型

### TelemetryData（`models/telemetry.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key（與 timestamp 複合 PK） |
| timestamp | DateTime+tz | primary key，TimescaleDB hypertable partition column |
| drone_id | String(255) | 無 FK 約束，可為任意字串（e.g. "drone-001"） |
| latitude | Float | 緯度，NOT NULL |
| longitude | Float | 經度，NOT NULL |
| altitude | Float | 高度（公尺），NOT NULL |
| speed | Float? | 速度（m/s），nullable |
| heading | Float? | 航向（度），nullable |
| battery_level | Float? | 電量（%），nullable |
| signal_strength | Float? | 訊號強度（%），nullable |

`telemetry_data` 在啟動時由 `ensure_hypertable()` 轉為 TimescaleDB hypertable，以 `timestamp` 分區。

### Drone（`models/drone.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| name | String(100) | 名稱 |
| model | String(100) | 機型 |
| serial_number | String(100) | unique |
| max_flight_time | Float? | 最大飛行時間（分鐘） |
| is_active | Boolean | 預設 True |
| created_at / updated_at | DateTime+tz | |

### FlightRecord（`models/flight.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| drone_id | UUID | FK → drones.id |
| status | FlightStatus | scheduled/in_flight/approaching/landing/landed/completed/aborted |
| takeoff_time | DateTime+tz? | nullable |
| landing_time | DateTime+tz? | nullable |
| created_at | DateTime+tz | |

### LandingPad（`models/landing.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| name | String(50) | unique |
| latitude / longitude | Float | |
| altitude | Float | 預設 0.0 |
| status | PadStatus | available/occupied/reserved/maintenance |
| has_charger | Boolean | |
| max_drone_weight | Float? | nullable |

### LandingSchedule（`models/landing.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| flight_id | UUID | FK → flight_records.id |
| pad_id | UUID | FK → landing_pads.id |
| scheduled_time | DateTime+tz | |
| actual_time | DateTime+tz? | landing 完成時填入 |
| priority | Integer | 預設 0 |

### Mission（`models/mission.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| drone_id | UUID | FK → drones.id |
| flight_id | UUID | FK → flight_records.id |
| name | String(200) | |
| description | Text? | |
| status | MissionStatus | created/in_progress/data_uploading/completed/failed |
| area_of_interest | Text? | |
| started_at / completed_at | DateTime+tz? | nullable |
| report_text | Text? | AI 報告文字，nullable |
| report_generated_at | DateTime+tz? | nullable |

### InspectionImage（`models/mission.py`）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | primary key |
| mission_id | UUID | FK → missions.id |
| filename | String(255) | |
| object_key | String(500) | MinIO object key（`missions/{id}/{filename}`） |
| content_type | String(100) | 預設 image/jpeg |
| captured_at | DateTime+tz? | nullable |
| uploaded_at | DateTime+tz | server default |

---

## 8. 開發工作流

### 8.1 Backend 改 code（live reload）

`docker-compose.yml` 將 `./backend/app` 掛載為 container 內的 `/app`（volume mount）。uvicorn 以 `--reload` 模式運行，修改任何 Python 檔案後自動重載，**不需要重建 image**。

```bash
# 修改後確認 backend 已重載
docker compose logs backend --tail=5
```

### 8.2 Frontend 改 code

```bash
# 在 container 外開發（推薦，有 HMR）
cd frontend
npm install
npm run dev   # dev server on :5173，proxy 到 nginx:80

# 或修改後重建 container
docker compose build frontend && docker compose up -d frontend
```

### 8.3 資料庫 schema 變更

目前使用 `Base.metadata.create_all()`（無 migration 工具）。新增 model 欄位後，**已存在的 table 不會自動 ALTER**，需要：
1. 手動寫 `ALTER TABLE` SQL（參考 `services/timescale.py:ensure_mission_columns()` 的寫法）
2. 或在開發環境中 `docker compose down -v` 重建 volumes（**資料會清空**）

### 8.4 如何加一個新 endpoint

1. 在對應的 `backend/app/api/*.py` 中新增 route function（參考 `api/telemetry.py` 的結構）
2. Pydantic schema 放在同檔案或 `backend/app/schemas/` 下
3. 若需要 WebSocket broadcast，呼叫 `await manager.broadcast(channel, data)`（框架會自動走 Redis pub/sub）
4. Router 已在 `main.py` 中註冊，不需要額外掛載

---

## 9. 已知限制 / Not Yet Implemented

- **Authentication / Authorization** — 所有 endpoint 完全開放，無任何身份驗證
- **GET /api/v1/flights/{id}/telemetry** — stub，永遠回傳 `[]`；需要將 TelemetryData 與 flight_id 關聯才能實作
- **ROS 2 Bridge 整合** — TelemetrySubscriber / ImageSubscriber / MissionSubscriber 三個類別存在但未在 main.py 啟動；實際 ROS 2 訊息接收未驗證
- **TelemetrySubscriber mock mode** — `_run_mock_mode()` 有實作但因類別未被啟動而無效；目前的模擬由 FleetSimulator 負責
- **Pad release after landing** — orchestrator 只有 battery 耗盡才呼叫 `release_pad()`；正常 landed→completed 轉換不釋放 pad
- **Flight completed 轉換** — `FlightStatus.COMPLETED` 只在 battery 耗盡時觸發；正常飛行結束後 drone 停在 `landed` 狀態
- **FlightTracker.check_battery_alerts()** — `services/flight_tracker.py:82-93` 定義但無呼叫者（dead code）；battery alert 的實際執行點在 `api/telemetry.py:49-63`
- **TelemetryPanel 多 drone 區分** — 只顯示最新一筆，無法切換查看特定 drone
- **Simulation Control follower 重試** — 前端 SimulationControl 目前不處理 503；若打到 follower，需要使用者手動重試
- **UDP Listener leader-only** — C++ publisher 的 UDP 封包有機會打到 follower（Docker DNS round-robin），follower 無 UDP listener 會靜默丟棄
- **手動新增/移除 drone** — Simulation Control UI 無此功能
- **場景 preset** — Simulation Control UI 無此功能

---

## 10. Roadmap 指引

詳細的 Phase 1-5 實作規劃、API spec、驗收條件請參閱：
- `docs/implementation_plan.md` — 主要實作計畫
- `progress.md` — 各 WP 完成狀態勾選表

本文件只描述當前已實作的功能；尚未完成的項目見第 9 節。

---

## 11. FAQ / Troubleshooting

**Q: ROS 2 沒裝會怎樣？**

A: 完全不影響。ROS 2 bridge 類別在 `import rclpy` 失敗時進入 fallback 模式（`image_sub.py`、`mission_sub.py` sleep；`telemetry_sub.py` 有 mock mode 但類別本身未被啟動）。系統的遙測來源是 FleetSimulator，不依賴 ROS 2。

**Q: 前端連到 backend 但看不到無人機？**

A: 檢查 simulator 是否在跑：
```bash
docker compose logs backend --tail=20 | grep "POST /api/v1/telemetry"
```
若無輸出，查看 leader election 是否成功：
```bash
docker compose exec redis redis-cli GET drone_platform:simulation_leader
```
若 Redis key 不存在，leader 未啟動，重啟 backend：
```bash
docker compose restart backend
```

**Q: Dashboard 卡片顯示 `--`？**

A: `--` 是 React Query 載入中的 loading state，不是 hardcoded。如果 5 秒後仍未更新，開啟 browser DevTools → Network，確認 `/api/v1/stats/summary` 回 200 且有資料。

**Q: WebSocket 斷線會自動重連嗎？**

A: 會。`hooks/useWebSocket.ts:47-51` 在 `onclose` 事件後等 3 秒重連。重連期間 TelemetryPanel 顯示 "Disconnected" badge。

**Q: MinIO bucket 沒自動建立怎麼辦？**

A: `ensure_buckets()` 在每次 backend 啟動時執行，若 bucket 不存在則建立 `inspection-images` 和 `flight-logs`。若出現 bucket 相關錯誤，確認 MinIO 服務健康：
```bash
docker compose ps minio
curl -s http://localhost:9001  # MinIO console 應可訪問
```
重啟 backend 會觸發 `ensure_buckets()` 重試：
```bash
docker compose restart backend
```

**Q: 前端打 API 是直接到 backend 還是透過 nginx？**

A: 透過 nginx（port 8000）。`vite.config.ts` proxy 指向 `http://nginx:80`；nginx 再 round-robin 到 backend pool。這讓 `docker compose --scale backend=2` 可正常運作。

**Q: simulation/status 回 503？**

A: 你的請求打到了 follower instance。follower 回 `{"error": "not_leader", "leader_hostname": "..."}` 是正常設計。直接再試一次，nginx 會把下一次請求輪到 leader。
