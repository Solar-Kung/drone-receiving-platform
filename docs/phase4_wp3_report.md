# Phase 4 · WP3 完成報告

## 改動摘要

### 後端
- `requirements.txt`：新增 `anthropic>=0.34.0`（實際安裝版本 0.96.0）。
- `config.py`：新增 `anthropic_api_key`（預設空字串）與 `anthropic_model`（預設 `claude-sonnet-4-6`）。
- `models/mission.py`：新增 `report_text: Text | None` 與 `report_generated_at: DateTime | None` 欄位。
- `services/timescale.py`：新增 `ensure_mission_columns()`，以 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 冪等地新增兩個欄位，解決 DB 已存在時 ORM 欄位不符的問題。
- `main.py`：啟動時呼叫 `ensure_mission_columns()`。
- 新建 `services/ai_report_generator.py`：`generate_report()` 查詢 mission + 圖片數量組 prompt，呼叫 `AsyncAnthropic` 產生繁體中文報告（三段：巡檢任務總結、發現事項、建議）；API key 未設或呼叫失敗時 fallback 到范本報告。`save_report()` 寫回 DB。
- `orchestrator.py`：`_complete_mission()` 完成後以 `asyncio.create_task` 非阻塞呼叫 `_generate_and_broadcast_report()`，產出後 broadcast `mission_report` 事件。
- `api/data.py`：`MissionResponse` 新增 `report_text`、`report_generated_at` 欄位。

### 前端
- `InspectionReport.tsx`（WP2 已完成）：report 區塊讀取 `mission.report_text`，有內容時顯示，無時顯示 `Report pending...`；WebSocket `mission_report` 事件觸發 `invalidateQueries`。

## Fallback 行為與 API Key 設定
- **未設定 API Key**：`generate_report()` 直接回傳固定格式範本報告，內含任務名稱、時長、圖片數量，無需外部網路請求。
- **設定 API Key**：在 `configs/.env` 加入 `ANTHROPIC_API_KEY=sk-ant-xxx` 後 `docker compose restart backend` 即生效，下次 mission 完成時自動呼叫 Claude 產生報告。
- **API 失敗**：log warning 後同樣 fallback 到範本報告，不阻斷 flight lifecycle。

## 驗證結果
- `ALTER TABLE missions ADD COLUMN IF NOT EXISTS report_text TEXT` 執行正常（log 可見）
- `GET /api/v1/data/missions` 回傳含 `report_text: null` 欄位
- `GET /health` 正常
