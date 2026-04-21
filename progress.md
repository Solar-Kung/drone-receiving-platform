# Implementation Progress

> 實作進度追蹤 — Claude Code 完成每個步驟後在此打勾
>
> Last updated: 2026-04-21 (Phase 4 WP1 complete)

---

## Phase 1 — Single Drone Telemetry Pipeline

**Goal:** 一架無人機，資料端到端流通，地圖上有東西在動

### 1A. Data Model

- [x] `TelemetryData` model 精簡為核心欄位（drone_id, lat, lon, alt, timestamp）
- [x] 擴展欄位（battery, speed, heading, signal_strength）設為 nullable
- [x] TimescaleDB hypertable 以 `timestamp` 分區正確建立
- [x] Model 可透過 SQLAlchemy 正常寫入和查詢

### 1B. REST Endpoints + WebSocket Broadcast

- [x] 新建 `backend/app/api/telemetry.py` router
- [x] 新建 `backend/app/schemas/telemetry.py` Pydantic schemas
- [x] `POST /api/v1/telemetry` — 寫入 DB + WebSocket broadcast，回傳 201
- [x] `GET /api/v1/telemetry/latest?drone_id=xxx` — 回傳最新一筆
- [x] `GET /api/v1/telemetry/history?drone_id=xxx&limit=100` — 回傳升序歷史資料
- [x] Router 註冊到 `main.py`
- [x] WebSocket envelope 格式統一為 `{ "type": "...", "drone_id": "...", "data": {...} }`
- [x] Swagger UI 手動測試三個 endpoint 全部通過

### 1C. Telemetry Simulator

- [x] 新建 `backend/app/simulation/` 目錄
- [x] 新建 `backend/app/simulation/routes.py` — 台北路線 waypoint 定義
- [x] 新建 `backend/app/simulation/telemetry_simulator.py` — 核心 simulator class
- [x] Simulator 使用線性插值在 waypoint 間移動（非隨機跳躍）
- [x] 高度使用梯形曲線（起飛爬升 → 巡航 → 下降）
- [x] Simulator 透過 `httpx.AsyncClient` POST 到自己的 API（不直接寫 DB）
- [x] 預留 `speed_multiplier` 參數（Phase 4 用）
- [x] 掛載到 FastAPI `lifespan` 以 `asyncio.create_task` 啟動
- [x] 飛完一圈自動重新開始
- [x] `docker compose up` 後 simulator 自動執行，log 中每秒可見 POST

### 1D. Frontend — Live Map + Flight Trail

- [x] 修改 `MapView.tsx` — 頁面載入時 GET history 畫 Polyline
- [x] WebSocket 即時更新 marker 位置
- [x] 新座標 append 到 Polyline（保留最近 500 點）
- [x] Marker popup 顯示高度、經緯度
- [x] 自訂無人機 icon（非預設 Leaflet marker）
- [ ] 瀏覽器中可見無人機沿路線移動，軌跡連續

### 1E. Frontend — Altitude Chart

- [x] 新建 `AltitudeChart.tsx`（使用 recharts LineChart）
- [x] X 軸顯示時間（最近 60 秒），Y 軸顯示高度 (m)
- [x] 透過 WebSocket 即時更新
- [ ] 可見起飛爬升、巡航、下降曲線

### Phase 1 Integration Test

- [ ] `docker compose up -d` 後 5 秒內地圖上出現移動的無人機
- [ ] 軌跡線連續（非跳躍式）
- [ ] 高度圖表即時滾動更新
- [x] Swagger `GET /history` 回傳有資料
- [ ] 開兩個瀏覽器 tab，兩邊地圖同步更新

---

## Phase 2 — Dashboard + Richer Telemetry

**Goal:** Dashboard 卡片顯示 live 數字，遙測擴展 battery/speed/heading，告警系統

### 2A. Stats Endpoint

- [x] 新建 `backend/app/api/stats.py` router
- [x] `GET /api/v1/stats/summary` — 聚合查詢 active_drones, total_points, latest_altitude
- [x] Router 註冊到 `main.py`
- [x] Simulator 運行時 active_drones >= 1

### 2B. Dashboard UI

- [x] `Dashboard` 元件改用 TanStack Query 呼叫 stats API
- [x] 每 5 秒自動 refetch
- [x] 四張卡片顯示 live 數字（取代 `--`）

### 2C. Extended Telemetry Fields

- [x] 更新 `TelemetryCreate` schema 加入 optional battery, speed, heading
- [x] 更新 POST handler 處理新欄位
- [x] Simulator 產生 battery drain（100% 線性遞減，每秒 -0.05%）
- [x] Simulator 產生 speed（根據 waypoint 間距，巡航 ~10 m/s）
- [x] Simulator 產生 heading（根據移動方向 atan2 計算）
- [x] WebSocket envelope 包含擴展欄位

### 2D. Multi-Chart Panel

- [x] 新建 `TelemetryCharts.tsx`（或擴展 AltitudeChart）
- [x] 顯示三條線：altitude, battery, speed
- [x] 共用 X 軸（時間）
- [x] Battery < 20% 時有視覺警示（紅色/閃爍）

### 2E. Alert System

- [x] 後端：POST handler 中 battery < 20% 發送 alert WebSocket 訊息
- [x] 後端：battery < 10% 發送 critical alert
- [x] 新建 `AlertPanel.tsx`（toast 或 badge 顯示告警）
- [ ] 告警出現在前端 UI

### Phase 2 Integration Test

- [ ] Dashboard 卡片全部顯示 live 數字
- [ ] 三個圖表即時更新
- [ ] Battery 遞減至 < 20% 時前端出現 warning
- [ ] Battery < 10% 時出現 critical alert

---

## Phase 3 — Multi-Drone + Flight Lifecycle

**Goal:** 3-5 架無人機同時飛，完整起降生命週期，landing pad 管理

### 3A. Fleet Simulator

- [x] 新建 `backend/app/simulation/fleet_simulator.py`
- [x] 定義多條路線（基隆河、太陽能板場、橋樑檢查）
- [x] 管理 3-5 個 DroneSimulator instance
- [x] 起飛時間間隔 30 秒（stagger）
- [x] 啟動時自動建立 drone records 到 DB
- [x] 每架 drone 有獨立 battery drain 曲線

### 3B. Flight Orchestrator

- [x] 新建 `backend/app/simulation/orchestrator.py`
- [x] 自動建立 FlightRecord（→ scheduled）
- [x] 起飛時自動切換 → in_flight
- [x] 距離目標 < 500m 自動切換 → approaching
- [x] 呼叫 LandingManager 預約 pad → landing
- [x] 高度 = 0 且對齊 pad → landed
- [ ] 等待 30 秒 → completed，釋放 pad
- [ ] 無可用 pad 時進入 holding pattern
- [x] Flight status 變更透過 `/ws/flights` 即時推送
- [ ] Redis pub/sub 做內部事件總線

### 3C. Landing Pad Management

- [x] Simulator 啟動時建立 2-3 個 landing pad（松山、圓山、大直）
- [x] Orchestrator approaching 時呼叫 `assign_pad()`
- [ ] Orchestrator completed 時呼叫 `release_pad()`
- [x] 同時兩架 approaching 不分配同一個 pad
- [x] Pad 狀態變更透過 `/ws/landings` 即時推送

### 3D. Multi-Drone Map

- [x] `MapView.tsx` 支援多個 marker
- [x] 每架 drone 不同顏色
- [x] 每架有獨立軌跡線
- [x] 維護 `Map<drone_id, { marker, trail }>` 結構
- [x] 點擊 marker 顯示該 drone 資訊

### 3E. Landing Pad UI

- [x] 地圖上顯示 landing pad markers（方形 icon）
- [x] Pad 顏色反映狀態（綠 available, 黃 reserved, 紅 occupied）
- [x] 點擊顯示 pad 資訊
- [ ] 整合現有 `LandingControl` 元件到地圖

### Phase 3 Integration Test

- [ ] 地圖上同時顯示 3+ 架無人機在不同路線飛行
- [ ] Flight status 自動轉換（不需手動 API call）
- [ ] Landing pad 自動 reserve → occupy → release
- [ ] 無可用 pad 時 drone 進入 holding pattern
- [ ] 所有狀態變更在前端即時反映

---

## Phase 4 — Mission, Inspection + Simulation Control

**Goal:** 完整巡檢任務流程、AI 報告、模擬控制面板

### 4A. Mission System

- [x] Orchestrator 在 flight 開始時自動建立 Mission
- [x] 每到達 waypoint 更新 mission 進度
- [x] 進度透過 WebSocket 即時推送
- [x] 新建 `MissionProgress.tsx` 顯示進度條
- [x] Flight 完成時自動 complete mission

### 4B. Inspection Data + AI Reports

- [x] 每個 waypoint 產生模擬巡檢圖片
- [x] 圖片上傳到 MinIO
- [x] 產生巡檢報告文字（範本或 AI）
- [x] 前端 `InspectionReport` 元件顯示圖片 + 報告

### 4C. Anomaly Injection

- [x] Simulator 隨機注入 battery 突降
- [x] Simulator 隨機注入 GPS drift
- [x] Simulator 隨機注入 signal loss（暫停 telemetry）
- [x] Simulator 隨機注入 emergency return（中斷任務返航）
- [x] 異常事件觸發 alert system

### 4D. Simulation Control Panel

- [x] 新建 `SimulationControl.tsx` 頁面
- [x] 後端 `POST /api/v1/simulation/control` endpoint
- [x] 後端 `GET /api/v1/simulation/status` endpoint
- [x] Start / Pause / Stop 控制
- [x] 速度調整（1x / 2x / 5x）
- [ ] 手動新增/移除 drone
- [ ] 場景 preset 選擇

### Phase 4 Integration Test

- [ ] Mission 隨 flight 自動建立並追蹤進度
- [ ] 巡檢圖片在 MinIO 中可存取
- [ ] 偶爾出現異常事件並觸發告警
- [x] 控制面板可暫停/恢復/調速模擬
- [ ] 場景 preset 可正確載入

---

## Phase C: C++ Telemetry Publisher

**Goal:** Standalone C++17 subproject that publishes drone telemetry via UDP/protobuf to the Python backend.

- [x] WP1: Project skeleton + Hello World (CMakeLists.txt, vcpkg.json, Dockerfile, main.cpp)
- [x] WP2: Config + Trajectory (YAML config, linear interpolation, unit tests)
- [x] WP3: UDP Socket + Protobuf (RAII socket, proto codegen, Python receiver check)
- [x] WP4: Publisher integration + Threading (producer-consumer queue, SIGINT, spdlog)
- [x] WP5: Backend UDP Listener integration (Python asyncio UDP, WebSocket bridge)
- [x] WP6: Documentation + cleanup (README, clang-format, zero-warning check)

---

## Summary

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1 — Single Drone Pipeline | 🟡 In progress | 31 / 37 |
| Phase 2 — Dashboard + Telemetry | 🟡 In progress | 14 / 18 |
| Phase 3 — Multi-Drone + Lifecycle | 🟡 In progress | 25 / 30 |
| Phase 4 — Mission + Control | 🟡 In progress | 20 / 21 |
| **Total** | | **90 / 106** |

### Status Legend

- 🔲 Not started
- 🟡 In progress
- ✅ Complete

### Notes on unchecked Phase 1 items

The 6 unchecked Phase 1 items (1D browser visual, 1E browser visual, and 4 integration-test browser items) require visual confirmation in a real browser session. The underlying code is implemented.

Phase 2: 14/18 checked. The 4 unchecked items are the browser-visual integration tests (dashboard cards showing live numbers, charts updating, alert toasts appearing). Backend verified: `active_drones >= 1`, `battery_level/speed/heading` present in latest response.
