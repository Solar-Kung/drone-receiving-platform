# Phase 4 · WP5 完成報告

## 改動摘要

### 後端
- `fleet_simulator.py`：新增 `paused` 屬性與三個方法：`pause()`（設所有 simulator 的 `paused=True`）、`resume()`（恢復）、`set_speed(multiplier)`（同步更新所有 simulator 的 `speed_multiplier`）。
- `telemetry_simulator.py`：新增 `paused` 屬性；迴圈每 step 開頭檢查 `if self.paused`，成立時 sleep 0.5 秒後 continue，不推進 elapsed_seconds 也不送 POST。
- 新建 `api/simulation.py`：`GET /api/v1/simulation/status`（回傳 `paused`、`speed`、per-drone 狀態）與 `POST /api/v1/simulation/control`（action: `pause` / `resume` / `set_speed`）。
- `main.py`：lifespan 中將 fleet 掛至 `app.state.fleet`，供 simulation router 存取；新增 `simulation` router 至 `/api/v1/simulation`。

### 前端
- 新建 `SimulationControl.tsx`：呼叫 status API（每 2 秒 refetch）、顯示運行狀態指示燈、Pause/Resume 按鈕、1× / 2× / 5× 速度選擇器、per-drone 狀態表格。
- `App.tsx`：新增 `SimulationPage` 元件、`/simulation` 路由、側邊欄 "Simulation" NavLink。
- `api.ts`：新增 `SimulationStatus` 型別、`getSimulationStatus()`、`simulationControl()` 函式。

## 驗證結果
- `GET /api/v1/simulation/status` → `{"paused":false,"speed":1.0,"drones":[...]}`
- `POST /api/v1/simulation/control {"action":"pause"}` → drones 全部切換 paused=true
- `POST /api/v1/simulation/control {"action":"set_speed","speed":2.0}` → speed 更新至 2.0
- `POST /api/v1/simulation/control {"action":"resume"}` → 恢復運行
- 前端 `http://localhost:3000/simulation` 頁面可正常載入、操作
