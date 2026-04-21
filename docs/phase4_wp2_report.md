# Phase 4 · WP2 完成報告

## 改動摘要

### 後端
- `requirements.txt`：新增 `Pillow==10.4.0`，強制重建 Docker image 安裝（使用 `--no-cache`）。
- 新建 `services/inspection_image_generator.py`：`generate_and_upload()` 以 Pillow 產生 800×600 黑底 JPEG，文字含 drone_id、waypoint index、座標、時間戳，上傳至 MinIO `inspection-images` bucket，建立 `InspectionImage` DB record 並回傳。字型優先使用 DejaVu Mono，失敗時降級至 Pillow 內建字型。
- `orchestrator.py`：新增 `_generate_inspection_image()` 方法，在 waypoint 變化且非起飛/降落 waypoint 時以 `asyncio.create_task` 非阻塞呼叫 image generator；圖片產生後 broadcast `inspection_image` 事件到 `/ws/telemetry`。
- `docker-compose.yml`：移除 redis port 對外映射（修復 port 6379 衝突，backend 現已正常啟動）。

### 前端
- `services/api.ts`：新增 `InspectionImageData` 型別與 `getMissionImages()` 函式；`Mission` 介面新增 `report_text`、`report_generated_at`（為 WP3 預備）。
- 重寫 `InspectionReport.tsx`：拆分出 `MissionCard` 元件，加入「View Images」摺疊區塊、縮圖 grid（點擊開新分頁大圖）、`inspection_image` WebSocket invalidation、AI 報告欄位佔位（WP3 填入）。

## 驗證結果
- `GET /api/v1/data/missions/{id}/images` 回傳 >= 1 張圖片（含 presigned URL）
- Backend log 可見 `INSERT INTO inspection_images` 於每個中繼 waypoint 觸發
- MinIO presigned URL 格式正確（內網 `minio:9000`，docker 網路內可存取）
