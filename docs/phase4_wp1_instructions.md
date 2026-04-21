# Phase 4 · WP1 — Mission System

## 目標

每個 flight 綁一個 mission。Drone 抵達每個 waypoint 時 mission progress 遞增，透過 WebSocket 推送到前端進度條。Mission 隨 flight 生命週期開始與結束。

## 前置閱讀

- `docs/implementation_plan.md` — Phase 4A 段落
- `docs/phase4_plan.md` — 關鍵設計決策 1、2
- `backend/app/simulation/orchestrator.py` — 理解現有的 flight lifecycle 與 position callback 機制
- `backend/app/simulation/telemetry_simulator.py` — 理解 `segment_idx` 如何傳遞
- `backend/app/models/mission.py` — 既有 Mission model
- `backend/app/api/data.py` — 既有 mission CRUD endpoints

## 需求

### 後端

1. **Orchestrator 建立 mission**
   在 `FlightOrchestrator.start()` 建立 `FlightRecord` 之後，為每架 drone 同步建立一個 `Mission`：
   - `drone_id` / `flight_id` 用剛建立的
   - `name`: 根據 route 命名（例如 `"Taipei River Patrol — 2026-04-21 14:30"`），可以用 `DRONE_SPECS` 的 `name` 欄位
   - `description`: 簡短描述任務類型
   - `status`: `CREATED`
   - 記錄 `mission_id` 到 orchestrator 的 in-memory dict `self._mission_ids: dict[str, uuid.UUID]`

2. **Mission 狀態隨 flight 狀態轉換**
   修改 `_transition` 方法，在以下時機更新 mission：
   - flight `scheduled → in_flight`：mission `CREATED → IN_PROGRESS`，設定 `started_at`
   - flight `landing → landed`：mission `IN_PROGRESS → DATA_UPLOADING`（模擬上傳中）
   - flight `* → completed`：mission `DATA_UPLOADING → COMPLETED`，設定 `completed_at`
   - 使用既有的 `async_session` pattern，不要引入新的 service

3. **Waypoint 進度追蹤**
   新增 position callback 邏輯：每次 `segment_idx` 變化時（相對於上一次 callback），計算 `progress = segment_idx / total_segments * 100`，broadcast 到 `/ws/telemetry` channel：
   ```json
   {
     "type": "mission_progress",
     "drone_id": "drone-001",
     "data": {
       "mission_id": "<uuid>",
       "current_waypoint": 3,
       "total_waypoints": 10,
       "progress": 30.0
     }
   }
   ```
   - 只在 waypoint 變化時 broadcast（減少訊息量），不要每秒都送
   - 用 orchestrator in-memory dict `self._last_segment_idx: dict[str, int]` 追蹤

4. **處理 state collection 初始化**
   `seed_data()` 建立的 drone 如果 DB 已經有舊 flight/mission，不要影響新 session 的 in-memory state。新 session 啟動時永遠建立新的 flight + mission。

### 前端

5. **新建 `MissionProgress.tsx`**
   放在 `frontend/src/components/MissionProgress/MissionProgress.tsx`：
   - 訂閱 `/ws/telemetry`，過濾 `type === "mission_progress"` 的訊息
   - 維護 `Map<drone_id, { current_waypoint, total_waypoints, progress }>`
   - 顯示每架 drone 一行進度條（drone_id + 進度條 + `5/10 — 50%` 文字）
   - 進度條用 CSS linear-gradient，配色與現有 dashboard 一致（blue → green）
   - 沒有資料時顯示 `Waiting for mission data...`

6. **掛載進 Dashboard**
   在 `App.tsx` 的 `Dashboard` 元件，`Live Map` 與 `Altitude Profile` 卡片之間新增一張卡片 `Mission Progress`，內容放 `<MissionProgress />`。

7. **更新 `InspectionReport.tsx`**
   既有頁面已經列 missions，確認顯示的 mission 狀態會隨 orchestrator 推進更新（透過既有的 TanStack Query `refetchInterval: 10000`）。

## 驗收

```bash
# Backend
docker compose up -d
sleep 15

# 應該看到 3 個 missions 被建立
curl -s localhost:8000/api/v1/data/missions | jq 'length'  # 預期 >= 3

# WebSocket 應該收到 mission_progress 訊息
# 用瀏覽器 dev console 連 ws://localhost:3000/ws/telemetry 測試

# 前端
# 瀏覽 http://localhost:3000
# - Dashboard 新增的 "Mission Progress" 卡片顯示 3 個進度條
# - 進度條隨 drone 移動而推進
# - /inspections 頁面的 mission status 會從 created → in_progress → completed 變化
```

## 約束

- 不要改動 flight lifecycle 本身（Phase 3 已穩定）
- 不要新增 Redis pub/sub（直接用現有的 WebSocket manager）
- 不要動 `InspectionImage` 模型（WP2 會處理）
- 不要在這個 WP 引入 Anthropic API（WP3 會處理）
- mission 建立失敗時 log error 但不要讓 flight 建立失敗（rollback 獨立處理）

## 完成後

1. 更新 `progress.md`：Phase 4 · 4A 所有項目標 ✅
2. `git add -A && git commit -m "feat(phase4-wp1): mission system with waypoint progress tracking"`
3. 產出 `docs/phase4_wp1_report.md`（繁體中文，200 字內，描述改動與驗證結果）
4. 繼續 WP2（見 `docs/phase4_wp2_instructions.md`）
