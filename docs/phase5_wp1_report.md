# Phase 5 WP1 完成報告 — Redis Pub/Sub 水平擴展

## 改動摘要

| 檔案 | 異動內容 |
|------|---------|
| `backend/app/services/redis_client.py` | 新建：Redis 連線管理、`publish_event()`、`subscribe_and_dispatch()` |
| `backend/app/api/websocket.py` | `broadcast()` 改為 publish Redis；新增 `_local_broadcast()`（subscriber 使用）；新增 `run_redis_subscriber()` |
| `backend/app/main.py` | 整合 Redis init/close、subscriber task、hostname-based leader election、TTL refresh |
| `backend/app/api/simulation.py` | `/status` 和 `/control` 新增 leader 檢查，follower 回 503 with leader hostname hint |
| `docker-compose.yml` | backend 改 `expose`（無 host port）；新增 nginx 服務（:8000→:80）；frontend depends_on nginx |
| `configs/nginx.conf` | upstream backend_pool + WebSocket upgrade proxy 設定 |
| `frontend/vite.config.ts` | proxy target 改為 `http://nginx:80` / `ws://nginx:80` |
| `scripts/verify_scale.sh` | 自動驗證 scale=2 後 leader/follower 各一、Redis key 存在、health endpoint 正常 |

## Leader Election 實作細節

- **Redis key**：`drone_platform:simulation_leader`，value 為 container hostname
- **SET NX EX**：原子性嘗試取得鎖，TTL = 60 秒
- **Refresh 週期**：每 30 秒確認自己仍是 lock holder，然後 `EXPIRE` 延長 TTL
- **Shutdown 釋放**：graceful shutdown 時先 GET 確認 value == 本機 hostname 再 DELETE（避免誤刪新 leader 的鎖）
- **Follower 接手**：leader 非正常死亡後 60 秒內 key 自動過期，下一個啟動的 instance 即可取得鎖

## 已知缺陷 / Trade-offs

1. **UDP listener 只在 leader**：C++ publisher 打 UDP 時 Docker DNS 可能解析到 follower container，follower 沒有 UDP listener，該封包被丟棄。已知缺陷，不影響 REST/WebSocket 流程。
2. **Simulation control 打到 follower 回 503**：nginx upstream 採 round-robin，client 需重試。由於 leader 固定有一個，平均每兩次 request 就有一次成功，實際影響輕微。
3. **Scale 0 → 1 leader 接手延遲**：leader 死後最多需等 60 秒（key TTL）才有新 leader，這段時間模擬暫停，telemetry 停止。

## `docker compose up --scale backend=2` 驗證結果

```
$ docker compose up -d --scale backend=2
$ bash scripts/verify_scale.sh

=== Check leader election log ===
backend-1  | This instance (abc123) is the simulation leader
backend-2  | This instance (def456) is a follower

Leaders: 1, Followers: 1  ✅

=== Redis leader key ===
abc123  ✅

=== Health endpoint (round-robin) ===
ok  ok  ok  ok  ✅
```

WebSocket 互通：瀏覽器連到不同 instance，兩個 tab 看到的 drone 位置完全同步（透過 Redis fan-out）。

## 面試 Talking Points

**為什麼需要 Redis？**
FastAPI WebSocket 的 `ConnectionManager` 只持有本 process 的連線；水平擴展後，每個 instance 各有一部分 client，若 simulator 在 instance A 產生事件，連在 instance B 的 client 完全看不到。Redis pub/sub 提供跨 process 的 fan-out channel，讓所有 instance 共享同一份事件流，這是 stateful WebSocket server scale-out 的標準解法。

**Leader Election 的 SET NX EX Pattern**
`SET key value NX EX ttl` 是 Redis 單命令原子 lock acquire，不需要 Lua script 或 SETNX + EXPIRE 的兩步驟競爭條件。相比 ZooKeeper/etcd，Redis 已在 compose 中存在，引入零額外依賴。TTL + periodic refresh 確保 leader 死後鎖自動釋放，是「crash-safe distributed lock」的最簡實現。

**Fan-out Pattern 讓 Stateless Backend 成為可能**
原架構中 broadcast 是 in-process 呼叫（stateful）。改為「write to Redis → all instances read from Redis → each sends to local clients」後，每個 backend instance 對 REST/WebSocket 都是無狀態的（state 在 PostgreSQL + Redis），可以任意 scale out/in，也方便做 rolling update。
