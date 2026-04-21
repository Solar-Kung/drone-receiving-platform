# Phase 4 · WP4 — Anomaly Injection

## 目標

Simulator 隨機注入異常事件（battery drop、GPS drift、signal loss、emergency return），透過既有 alert system 通知前端。不改變 flight lifecycle 核心邏輯，只 mutate 當下 payload。

## 前置閱讀

- `docs/phase4_plan.md` — 關鍵設計決策 5
- `backend/app/simulation/telemetry_simulator.py` — 現在的 payload 生成邏輯
- `backend/app/api/telemetry.py` — 既有的 battery alert broadcast
- `frontend/src/components/AlertPanel/AlertPanel.tsx` — 既有告警 UI

## 需求

### 後端

1. **新建 `backend/app/simulation/anomalies.py`**
   ```python
   class AnomalyType(str, Enum):
       BATTERY_DROP = "battery_drop"       # 突然掉 15%
       GPS_DRIFT = "gps_drift"             # 位置偏移 ±0.0005 度
       SIGNAL_LOSS = "signal_loss"         # signal strength 歸零，持續 5 秒
       EMERGENCY_RETURN = "emergency_return"  # 標記需要提前返航

   @dataclass
   class AnomalyState:
       active: Optional[AnomalyType] = None
       started_at: Optional[float] = None  # monotonic time
       metadata: dict = field(default_factory=dict)

   ANOMALY_PROBABILITIES = {
       AnomalyType.BATTERY_DROP: 0.002,      # 每秒 0.2%
       AnomalyType.GPS_DRIFT: 0.001,
       AnomalyType.SIGNAL_LOSS: 0.0005,
       AnomalyType.EMERGENCY_RETURN: 0.0003,
   }

   def maybe_trigger_anomaly(state: AnomalyState) -> AnomalyState:
       """每秒呼叫一次，根據機率骰出異常。已有 active 異常時不觸發新的。"""

   def apply_anomaly(payload: dict, state: AnomalyState) -> dict:
       """根據當前 anomaly state 修改 payload。回傳新 dict，不 mutate 輸入。"""
   ```

2. **TelemetrySimulator 整合**
   在 `telemetry_simulator.py`：
   - 每個 `TelemetrySimulator` 持有一個 `AnomalyState`
   - 每次內迴圈（每秒一次）：
     1. 呼叫 `maybe_trigger_anomaly`
     2. 呼叫 `apply_anomaly` 修改 payload
     3. 若剛觸發新異常，broadcast alert（透過新的 POST endpoint 或直接在 simulator 內呼叫 manager — **直接呼叫 `manager.broadcast`** 是可以的，因為 simulator 在同一個 process 內；不需要走 REST）
   - `SIGNAL_LOSS` 持續 5 秒：`signal_strength = 0`，同時**不送 POST**（模擬真實斷線）
   - `EMERGENCY_RETURN` 觸發時：記錄到 anomaly state metadata，在 orchestrator 的 fast-path 檢查會讀到這個 state

3. **Orchestrator 處理 emergency return**
   Orchestrator 透過 position callback 已經拿得到 simulator，新增一個方法讓 simulator 把 anomaly state 傳過來（或直接把 anomaly state 放進 `point` dict 一併傳）：
   - Callback 內若收到 `anomaly.type == EMERGENCY_RETURN`，強制把 flight 狀態推到 `APPROACHING`（跳過正常的 80% segment 判斷），觸發 pad assignment
   - 若無 pad，維持 `IN_FLIGHT` 不額外處理（既有 landing-without-pad fallback 已處理）

4. **Alert broadcast**
   異常觸發時透過 `manager.broadcast("telemetry", ...)`：
   ```json
   {
     "type": "alert",
     "drone_id": "drone-001",
     "level": "warning",  // GPS_DRIFT、SIGNAL_LOSS
     "message": "GPS drift detected"
   }
   ```
   ```json
   {
     "type": "alert",
     "drone_id": "drone-001",
     "level": "critical",  // BATTERY_DROP、EMERGENCY_RETURN
     "message": "Battery dropped 15% — unexpected discharge"
   }
   ```

### 前端

5. **AlertPanel 不需改動**
   既有 alert UI 已支援 warning / critical 兩種 level，WP2/WP3 沒動它，WP4 也不動。

6. **地圖上標記異常 drone（可選加強）**
   在 `MapView.tsx` 若最近 10 秒內該 drone 有 alert，marker 加紅色脈衝光暈（CSS animation）。用 `Map<drone_id, last_alert_time>` 追蹤。此項若時間不夠可跳過，記錄在報告中。

## 驗收

```bash
docker compose up -d
# 等 5–10 分鐘讓異常有機會觸發
docker compose logs backend | grep -i anomaly
# 預期看到異常觸發 log

# 前端
# - 右下角告警 toast 偶爾出現
# - 地圖上 drone 位置偶爾「抖動」（GPS drift 效果）
# - 某架 drone 在巡航中段忽然朝 pad 方向飛（emergency return）
```

## 約束

- 異常機率不要調太高（預設值平均約 10–20 分鐘會觸發一次）
- `SIGNAL_LOSS` 期間 simulator **不送 POST**（不是送 0 座標）
- 不要讓 anomaly 疊加（active 期間不觸發新的）
- 不要動 flight lifecycle 的狀態機邏輯（只新增 emergency return fast-path）
- 不要在這個 WP 做 simulation control panel（WP5）

## 完成後

1. 更新 `progress.md`：Phase 4 · 4C 所有項目標 ✅
2. `git add -A && git commit -m "feat(phase4-wp4): anomaly injection with battery drop, gps drift, signal loss, emergency return"`
3. 產出 `docs/phase4_wp4_report.md`（繁體中文，200 字內，列出四種異常實際觸發頻率）
4. 繼續 WP5（見 `docs/phase4_wp5_instructions.md`）
