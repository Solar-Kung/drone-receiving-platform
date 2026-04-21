# Phase 4 — 實作計畫總覽

> 本文件是 Phase 4 的骨幹，CLI 每次 session 從此檔找到下一個 ⬜ WP 開始執行。

## 背景

Phase 1–3 已完成：telemetry pipeline、dashboard、多機 flight lifecycle、landing pad 管理。
Phase 4 目標：把模擬平台做成一個完整可 demo 的系統，加入巡檢任務、AI 報告、異常注入、控制面板。

## 關鍵設計決策（CLI 不得推翻）

1. **Mission 綁 flight**：每個 `FlightRecord` 對應一個 `Mission`。orchestrator 在建立 flight 時同步建立 mission。
2. **Waypoint 進度 = 飛行進度**：mission 的 waypoint 列表直接使用 simulator 的 route。當 drone 抵達每個 waypoint 時（segment_idx 遞增），mission progress 更新。
3. **巡檢圖片在 waypoint 抵達時產生**：使用 Pillow 產生黑底 placeholder（含 waypoint index、drone_id、timestamp），上傳 MinIO，建立 `InspectionImage` record。每個 waypoint 產生 1 張（起飛與降落 waypoint 除外）。
4. **AI 報告走 Anthropic API**：mission 完成時呼叫一次 Anthropic API，傳入 mission metadata（drone、路線、waypoint 數、異常事件）產生繁體中文巡檢報告。API key 走環境變數 `ANTHROPIC_API_KEY`，若未設定則 fallback 到範本報告。
5. **Anomaly injection 在 simulator 內部做**：每秒骰一次機率，觸發後 mutate 當下的 payload（battery drop、GPS drift、signal loss、emergency return）。
6. **Simulation control 改變 FleetSimulator 狀態**：pause / resume / speed adjustment 直接呼叫 fleet 和各 simulator 的方法，不經 Redis。

## WP 切分

每個 WP 結束時 CLI 必須：
1. 更新 `progress.md`（把 ⬜ 改 ✅）
2. Git commit（message 用英文）
3. 執行 `docker compose up -d` + `curl localhost:8000/health` 驗證 backend 正常
4. 產出簡短繁體中文完成報告（寫入 `docs/phase4_wp{N}_report.md`）

| WP | 範圍 | 估計檔案數 |
|----|------|-----------|
| WP1 | Mission System（orchestrator 建立 mission + waypoint progress + WebSocket 推送 + MissionProgress 前端元件） | 5–7 |
| WP2 | Inspection Data（Pillow 圖片產生 + MinIO 上傳 + InspectionImage 記錄 + InspectionReport 前端升級） | 4–6 |
| WP3 | AI Report（Anthropic API 整合 + mission 完成時產生報告 + 前端顯示） | 3–5 |
| WP4 | Anomaly Injection（simulator 內異常注入機制 + UI 告警強化） | 2–3 |
| WP5 | Simulation Control Panel（backend control endpoint + 前端控制頁面 + FleetSimulator pause/speed 支援） | 4–6 |

## 連續執行規則

- CLI 可以一次跑完多個 WP，不需要等 Sunny 確認
- 每個 WP 獨立 commit，context 耗盡時在 WP 邊界停，下一個 session 讀 `progress.md` 接手
- WP 之間有依賴：WP1 → WP2 → WP3 → WP4/WP5（WP4 與 WP5 可互換）
- 遇到非阻塞問題（例如某個 package 安裝慢）記錄在 WP 報告中繼續
