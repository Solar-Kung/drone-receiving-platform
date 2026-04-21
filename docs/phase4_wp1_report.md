# Phase 4 · WP1 完成報告

## 改動摘要

### 後端（orchestrator.py）
- `start()` 在建立 FlightRecord 後，獨立地為每架 drone 建立 `Mission`（名稱含 drone 型號與時間戳），mission 建立失敗不影響 flight 建立。
- `_transition()` 新增 mission 狀態同步：`SCHEDULED→IN_FLIGHT` 時 mission `CREATED→IN_PROGRESS`（設 started_at）；`LANDING→LANDED` 時 mission `IN_PROGRESS→DATA_UPLOADING`；battery 耗盡觸發 `_complete_mission()` 設 `COMPLETED`（設 completed_at）。
- 新增 `_last_segment_idx` 追蹤：每次 waypoint 變化（segment_idx 不同於上次）時 broadcast `mission_progress` 到 `/ws/telemetry`，內含 mission_id、current_waypoint、total_waypoints、progress（百分比）。進度推送在 fast-path 之前執行，確保每個 waypoint 皆捕獲。
- 新增 `docker-compose.yml`：移除 redis 對外 port（解決 port 6379 衝突）。

### 前端
- 新建 `MissionProgress.tsx`：訂閱 `/ws/telemetry`，過濾 `mission_progress` 訊息，以 `Map<drone_id, DroneProgress>` 維護狀態，顯示每架 drone 的進度條與 `N/M — X%` 文字。
- `App.tsx`：在 Live Map 與 Altitude Profile 之間新增 Mission Progress 卡片。

## 驗證結果
- `curl localhost:8000/api/v1/data/missions | jq 'length'` → 3（三架 drone 各一個 mission）
- Mission status 確認為 `in_progress`（drone 起飛後）
- Backend log 可見 `UPDATE missions SET status=...in_progress` 及 `started_at` 更新
- `GET /health` 回傳正常
