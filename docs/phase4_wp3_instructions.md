# Phase 4 · WP3 — AI Report（Anthropic API 整合）

## 目標

Mission 完成時呼叫 Anthropic API，傳入任務 metadata 產生繁體中文巡檢報告。報告存進 DB，前端在 mission card 顯示。API key 未設定時 fallback 到範本報告。

## 前置閱讀

- `docs/phase4_wp2_instructions.md` — WP2 巡檢圖片結構
- `docs/phase4_plan.md` — 關鍵設計決策 4
- `backend/app/models/mission.py` — 擴展 Mission model
- [Anthropic API docs](https://docs.claude.com/en/api/messages) — 使用 `claude-sonnet-4-6`（SDK 選用 `anthropic` PyPI package）

## 需求

### 後端

1. **新增 dependencies**
   `backend/requirements.txt` 加：
   ```
   anthropic>=0.34.0
   ```

2. **擴展 `Mission` model**
   在 `backend/app/models/mission.py` 的 `Mission` class 新增欄位：
   ```python
   report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
   report_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
   ```
   這是新欄位、沒 migration framework，直接讓 `Base.metadata.create_all` 處理（若既有 DB 沒這欄位，CLI 可以 drop `missions` table 重建，因為 missions 是 runtime 產生，不需保留）。在報告中註明這個決定。

3. **環境變數**
   在 `backend/app/config.py` 新增：
   ```python
   anthropic_api_key: str = ""
   anthropic_model: str = "claude-sonnet-4-6"
   ```
   `configs/.env.example` 也加對應條目（`ANTHROPIC_API_KEY=`、`ANTHROPIC_MODEL=claude-sonnet-4-6`），註明「留空則 fallback 到範本報告」。

4. **新建 `backend/app/services/ai_report_generator.py`**
   ```python
   async def generate_report(mission_id: uuid.UUID) -> str:
       """
       查詢 mission + drone + 圖片數量 + flight 資料，
       呼叫 Anthropic API 產生繁體中文巡檢報告。
       若 API key 為空或呼叫失敗，fallback 到範本報告。
       回傳報告文字。
       """
   ```
   - 查詢 DB 組 prompt context：mission name、drone 型號、圖片數量、起訖時間、路線概述
   - System prompt 要求：繁體中文、約 200–300 字、包含「巡檢任務總結」、「發現事項」、「建議」三段
   - 使用 `anthropic.AsyncAnthropic` client，`max_tokens=600`
   - API 失敗 log warning 後 fallback
   - Fallback 範本：一段固定格式文字，用 mission metadata 填入（例如：「本次巡檢由 {drone_name} 執行... 共捕獲 {N} 張影像... 未發現異常」）

5. **Orchestrator 完成時觸發報告產生**
   在 mission 狀態轉為 `COMPLETED` 之後（WP1 邏輯），`asyncio.create_task` 呼叫 `generate_report()`：
   - 產生完成後寫回 mission 的 `report_text` 與 `report_generated_at`
   - Broadcast `/ws/telemetry`：
     ```json
     {
       "type": "mission_report",
       "drone_id": "drone-001",
       "data": {
         "mission_id": "<uuid>",
         "report_text": "..."
       }
     }
     ```
   - 不阻塞主 transition 流程

6. **擴展 `MissionResponse` schema**
   在 `backend/app/api/data.py` 的 `MissionResponse` 新增：
   ```python
   report_text: Optional[str] = None
   report_generated_at: Optional[datetime] = None
   ```
   讓前端能透過既有 `GET /missions` 拿到報告。

### 前端

7. **升級 `InspectionReport.tsx`**
   - 每個 mission card 在「View Images」區塊下方新增「Inspection Report」區塊
   - 若 `mission.report_text` 存在，用 `<pre style="white-space: pre-wrap">` 顯示（保留換行）
   - 若不存在，顯示 `Report pending...`
   - WebSocket 收到 `type === "mission_report"` 時 invalidate missions query 觸發 refetch

## 驗收

```bash
# 不設 API key 的情況
docker compose up -d
# 等一個 mission 完整跑完（約 3–5 分鐘看電池歸零）
# mission 應該有 fallback 範本報告
curl -s localhost:8000/api/v1/data/missions | jq '.[0].report_text'
# 預期是範本文字

# 設 API key 後
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> configs/.env
docker compose restart backend
# 等下一個 mission 完成
curl -s localhost:8000/api/v1/data/missions | jq '.[-1].report_text'
# 預期是 Claude 產生的繁體中文報告

# 前端
# 瀏覽 http://localhost:3000/inspections
# - 完成的 mission card 顯示「Inspection Report」區塊
# - 報告文字完整顯示
```

## 約束

- 不要在啟動時呼叫 API（只在 mission 完成時觸發）
- 不要把 API key log 出來
- Anthropic client 用 async 版本（`AsyncAnthropic`），不要用同步 client 阻塞 event loop
- 不要引入額外的 LLM abstraction layer（直接用 `anthropic` SDK 即可）
- Fallback 範本要合理，不能留 `TODO` 或 placeholder
- 不要在這個 WP 動 anomaly injection（WP4）或 control panel（WP5）

## 完成後

1. 更新 `progress.md`：Phase 4 · 4B 所有項目全部標 ✅（含 AI 報告那一項）
2. `git add -A && git commit -m "feat(phase4-wp3): anthropic api integration for inspection reports"`
3. 產出 `docs/phase4_wp3_report.md`（繁體中文，200 字內，說明 fallback 行為與如何設定 API key）
4. 繼續 WP4（見 `docs/phase4_wp4_instructions.md`）
