# Phase 4 · WP4 完成報告

## 改動摘要

### 後端
- 新建 `simulation/anomalies.py`：定義四種 `AnomalyType`（`BATTERY_DROP`、`GPS_DRIFT`、`SIGNAL_LOSS`、`EMERGENCY_RETURN`）、`AnomalyState` dataclass、`maybe_trigger_anomaly()`（每秒機率觸發）、`apply_anomaly()`（mutate payload 並回傳）。
- `telemetry_simulator.py` 完整改寫：每架 simulator 持有獨立 `AnomalyState`；每 tick 依序執行 anomaly injection → alert broadcast；`_suppress_post` 讓 SIGNAL_LOSS 略過 HTTP POST；`_emergency_return` 標記傳入 position callback dict。
- `orchestrator.py` 更新：fast-path 在 `emergency_return=True` 時不提早離開，確保 APPROACHING 轉換即時觸發；`_transition()` 新增 `emergency_return` 參數，`IN_FLIGHT → APPROACHING` 條件改為 `segment_idx >= 80% OR emergency_return`。

## 四種異常觸發頻率（理論平均值）

| 異常類型 | 每秒機率 | 平均觸發間隔 |
|----------|----------|-------------|
| BATTERY_DROP | 0.002 | 約 8 分鐘 |
| GPS_DRIFT | 0.001 | 約 16 分鐘 |
| SIGNAL_LOSS | 0.0005 | 約 33 分鐘 |
| EMERGENCY_RETURN | 0.0003 | 約 55 分鐘 |

## 驗證結果
- Backend 重啟後 `GET /health` 正常
- Log 可見各 simulator 的 anomaly 觸發訊息
- WebSocket `alert` 事件（`level: critical/warning`）在異常觸發時即時推送
