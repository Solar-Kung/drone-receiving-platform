# Phase 4 · WP2 — Inspection Data（Pillow 圖片產生 + MinIO 上傳）

## 目標

Drone 抵達每個中繼 waypoint 時，產生一張 placeholder 巡檢圖片（Pillow 黑底 + 文字），上傳 MinIO，建立 `InspectionImage` 記錄，前端能瀏覽縮圖與 presigned URL。

## 前置閱讀

- `docs/phase4_wp1_instructions.md` — WP1 mission 系統是本 WP 基礎
- `docs/phase4_plan.md` — 關鍵設計決策 3
- `backend/app/services/minio_client.py` — 既有上傳函式
- `backend/app/models/mission.py` — `InspectionImage` 既有欄位
- `backend/app/api/data.py` — 既有 `GET /api/v1/data/missions/{id}/images` endpoint

## 需求

### 後端

1. **新增 Pillow dependency**
   在 `backend/requirements.txt` 加 `Pillow==10.4.0`。Dockerfile 不需要動（pip install 會處理）。

2. **新建 `backend/app/services/inspection_image_generator.py`**
   一個簡單的 service：
   ```python
   async def generate_and_upload(
       mission_id: uuid.UUID,
       drone_id: str,
       waypoint_idx: int,
       total_waypoints: int,
       latitude: float,
       longitude: float,
   ) -> InspectionImage:
       """產生 placeholder 圖片，上傳 MinIO，建立 DB 記錄。"""
   ```
   - 圖片規格：800x600、黑底（`#0a0a0a`）、白色等寬字
   - 文字內容（分行顯示，居中）：
     - `INSPECTION CAPTURE`
     - `Drone: {drone_id}`
     - `Waypoint: {waypoint_idx}/{total_waypoints}`
     - `Location: {lat:.5f}, {lon:.5f}`
     - `Time: {iso_timestamp}`
   - 編碼為 JPEG bytes（quality=85）
   - 呼叫 `upload_file()` 上傳到 `inspection-images` bucket（既有 client 就是寫入這個 bucket）
   - `object_key` 格式：`missions/{mission_id}/waypoint_{waypoint_idx:02d}_{timestamp}.jpg`
   - 建立 `InspectionImage` DB record
   - 回傳該 record

3. **Orchestrator 呼叫 image generator**
   在 WP1 新增的「waypoint 變化時 broadcast」邏輯中，當偵測到 waypoint 變化：
   - 起飛 waypoint（`segment_idx == 0`）與降落 waypoint（`segment_idx >= total_segments - 1`）**不產生圖片**
   - 中繼 waypoint 呼叫 `generate_and_upload()`（用 `asyncio.create_task` 非阻塞）
   - 成功後 broadcast `/ws/telemetry`：
     ```json
     {
       "type": "inspection_image",
       "drone_id": "drone-001",
       "data": {
         "mission_id": "<uuid>",
         "image_id": "<uuid>",
         "filename": "...",
         "waypoint_idx": 3
       }
     }
     ```

4. **確認 `GET /api/v1/data/missions/{id}/images` 回傳 presigned URL**
   既有 endpoint 已經有 `url` 欄位填 presigned URL，確認它仍能正常運作。

### 前端

5. **升級 `InspectionReport.tsx`**
   目前只列 mission 清單，擴展為：
   - 保留 mission 清單的既有樣式
   - 每張 mission card 新增「View Images」摺疊區塊
   - 點擊後 fetch `/api/v1/data/missions/{id}/images`，顯示縮圖 grid（每張 150x112）
   - 點擊縮圖開新分頁顯示大圖（使用 presigned URL）
   - 圖片數量顯示在 mission card header（例如 `"3 images captured"`）

6. **新增 WebSocket 即時通知**
   在 `InspectionReport.tsx` 訂閱 `/ws/telemetry`，收到 `type === "inspection_image"` 時讓對應 mission 的圖片查詢自動 refetch（用 TanStack Query 的 `queryClient.invalidateQueries`）。

## 驗收

```bash
docker compose up -d
sleep 60  # 等 drone 飛到第二個 waypoint

# 應該看到圖片
curl -s localhost:8000/api/v1/data/missions | jq '.[0].id' | xargs -I {} curl -s localhost:8000/api/v1/data/missions/{}/images | jq 'length'
# 預期 >= 1

# 前端
# 瀏覽 http://localhost:3000/inspections
# - 每個 mission card 顯示圖片數量
# - 點擊「View Images」展開縮圖 grid
# - 點縮圖開啟大圖
```

## 約束

- 不要用 `subprocess` 或外部工具產生圖片（純 Pillow）
- 不要阻塞 orchestrator 的 position callback（用 `asyncio.create_task`）
- MinIO 上傳失敗不要讓 flight 崩潰（log error 繼續）
- 不要改動 `data.py` 既有的 image API schema（只新增 frontend 消費邏輯）
- 不要在這個 WP 動 AI 報告（WP3）

## 完成後

1. 更新 `progress.md`：Phase 4 · 4B 所有項目標 ✅（除了 AI 報告那一項留給 WP3）
2. `git add -A && git commit -m "feat(phase4-wp2): inspection image generation with pillow + minio upload"`
3. 產出 `docs/phase4_wp2_report.md`（繁體中文，200 字內）
4. 繼續 WP3（見 `docs/phase4_wp3_instructions.md`）
