# C++ Telemetry Publisher — 專案規格

## 專案定位

在現有 drone-receiving-platform 中新增一個獨立的 C++ 子專案 `cpp_telemetry_publisher/`，扮演「L2 空中端」的角色：
讀取飛行路徑設定 → 生成 telemetry → 透過 UDP 推送給 Backend。

這個專案**不取代**現有的 Python simulator，而是**並存**的另一種資料來源，展示：
1. Modern C++ production 寫法
2. L2 協議（UDP binary packet）的真實樣貌
3. 跨語言整合（C++ publisher → Python backend adapter）

---

## 架構定位

```
[C++ Telemetry Publisher]        ← 新增，本次任務
         │
         │  UDP:14550 (MAVLink-like binary packet)
         ▼
[Python Backend UDP Listener]    ← 新增，本次任務
         │
         │  內部事件匯流排
         ▼
[WebSocket Broadcaster]          ← 既有
         │
         ▼
[Frontend]                       ← 既有
```

與現有的 Python simulator 對比：

| 來源 | 協議 | 模擬的層 |
|------|------|---------|
| Python Simulator (既有) | HTTP POST | 簡化的 L2 |
| **C++ Publisher (新)** | **UDP binary** | **真實 L2** |

兩者同時可運作，Backend 都能收。

---

## 技術棧

| 類別 | 技術 | 原因 |
|------|------|------|
| 語言 | C++17 | 平衡語法現代性與 Shield AI 實際採用版本 |
| 建置 | CMake 3.16+ | 業界標準 |
| 套件管理 | vcpkg | 跨平台、微軟維護、好上手 |
| Logging | spdlog | header-only、業界常用 |
| Config 解析 | yaml-cpp | YAML 讀取 |
| 命令列參數 | CLI11 | header-only、API 乾淨 |
| Serialization | Protocol Buffers (protobuf) | 業界標準 binary 格式 |
| 單元測試 | GoogleTest | 業界標準 |
| Containerization | Docker | 與現有 compose stack 整合 |

---

## 目錄結構

```
drone-receiving-platform/
├── cpp_telemetry_publisher/          ← 新增子專案
│   ├── CMakeLists.txt
│   ├── vcpkg.json                    ← 宣告依賴
│   ├── Dockerfile
│   ├── README.md
│   ├── configs/
│   │   └── flight_path_example.yaml  ← 飛行路徑範例
│   ├── proto/
│   │   └── telemetry.proto           ← protobuf schema
│   ├── include/
│   │   └── telemetry_publisher/
│   │       ├── udp_socket.h
│   │       ├── trajectory.h
│   │       ├── telemetry_generator.h
│   │       ├── publisher.h
│   │       └── config.h
│   ├── src/
│   │   ├── main.cpp
│   │   ├── udp_socket.cpp
│   │   ├── trajectory.cpp
│   │   ├── telemetry_generator.cpp
│   │   ├── publisher.cpp
│   │   └── config.cpp
│   └── tests/
│       ├── test_trajectory.cpp
│       ├── test_udp_socket.cpp
│       └── test_telemetry_generator.cpp
│
├── backend/
│   └── app/
│       ├── ros_bridge/
│       │   └── udp_listener.py       ← 新增：接收 C++ publisher 的 UDP 封包
│       └── ...
└── docker-compose.yml                 ← 新增 service: cpp_publisher
```

---

## Modern C++ 展示清單（CLI 必須涵蓋）

每個類別必須至少用到一次，面試時能指著 code 講：

### RAII（Resource Acquisition Is Initialization）
- `UdpSocket` class：constructor 開 socket，destructor 自動 close
- 禁止 copy（`= delete`），允許 move

### Smart Pointers
- `std::unique_ptr` 管理所有 owned resource
- **禁止**出現 raw `new` / `delete`（除了 placement new 場景，本專案不需要）

### Move Semantics
- `UdpSocket` 必須實作 move constructor 和 move assignment
- 回傳大物件時用 move 而不是 copy

### Threading
- 至少 2 個 thread：
  - `generator_thread`：定時生成 telemetry
  - `publisher_thread`：從 queue 拿資料發 UDP
- `std::atomic<bool> running_` 控制停止
- `std::mutex` + `std::condition_variable` 實作 producer-consumer queue
- Ctrl-C (SIGINT) handler：設 `running_ = false`，主 thread join 所有 worker

### STL Containers & Algorithms
- `std::vector<Waypoint>` 存路徑
- `std::queue` 當 publishing buffer
- `std::chrono` 做精準 timing
- range-based for loop

### Modern Features
- `std::optional<Waypoint>` 表示「可能到終點」
- `constexpr` 常數（發送頻率、buffer 大小）
- Lambda expression 傳給 thread
- Structured bindings（如果用 map iteration）
- `auto` + type deduction（適度使用，明顯型別才寫死）

### Error Handling
- 用 `std::expected`（C++23）— 若 vcpkg/compiler 不支援，改用 `tl::expected` 或 `std::variant` 或簡單 return code + log
- Socket error 不 throw exception，回傳 error code

---

## Protobuf Schema (`proto/telemetry.proto`)

```protobuf
syntax = "proto3";

package drone_platform.telemetry;

message TelemetryPacket {
  string drone_id = 1;
  int64 timestamp_ms = 2;  // Unix epoch milliseconds

  // Position
  double latitude = 3;
  double longitude = 4;
  double altitude_m = 5;

  // Motion
  double speed_mps = 6;
  double heading_deg = 7;

  // Status
  double battery_percent = 8;
  double signal_strength = 9;

  // Sequence number (for detecting packet loss)
  uint32 sequence = 10;
}
```

---

## 飛行路徑設定範例 (`configs/flight_path_example.yaml`)

```yaml
publisher:
  drone_id: "cpp-drone-001"
  target_host: "127.0.0.1"  # Backend UDP listener
  target_port: 14550
  publish_rate_hz: 10
  log_level: "info"

trajectory:
  # Linear interpolation between waypoints
  waypoints:
    - { lat: 25.0330, lon: 121.5654, alt: 0.0,   hold_sec: 2.0 }  # Taipei 101 起飛
    - { lat: 25.0340, lon: 121.5670, alt: 50.0,  hold_sec: 1.0 }
    - { lat: 25.0360, lon: 121.5690, alt: 100.0, hold_sec: 5.0 }  # 巡航
    - { lat: 25.0340, lon: 121.5670, alt: 50.0,  hold_sec: 1.0 }
    - { lat: 25.0330, lon: 121.5654, alt: 0.0,   hold_sec: 0.0 }  # 返航
  speed_mps: 10.0

simulation:
  battery_drain_per_second: 0.05  # % per second
  signal_base: 95.0
  signal_noise: 5.0
  loop: true  # 跑完重新來過
```

---

## 核心類別介面

### `Config` — 解析 YAML
```cpp
struct Waypoint {
    double lat, lon, alt;
    double hold_sec;
};

struct PublisherConfig {
    std::string drone_id;
    std::string target_host;
    uint16_t target_port;
    int publish_rate_hz;
    std::string log_level;
};

struct TrajectoryConfig {
    std::vector<Waypoint> waypoints;
    double speed_mps;
};

struct SimulationConfig {
    double battery_drain_per_second;
    double signal_base;
    double signal_noise;
    bool loop;
};

struct Config {
    PublisherConfig publisher;
    TrajectoryConfig trajectory;
    SimulationConfig simulation;

    static std::optional<Config> load_from_file(const std::string& path);
};
```

### `UdpSocket` — RAII socket wrapper
```cpp
class UdpSocket {
public:
    UdpSocket(const std::string& host, uint16_t port);
    ~UdpSocket();

    UdpSocket(const UdpSocket&) = delete;
    UdpSocket& operator=(const UdpSocket&) = delete;

    UdpSocket(UdpSocket&& other) noexcept;
    UdpSocket& operator=(UdpSocket&& other) noexcept;

    // 回傳 bytes sent；失敗回 -1 並 log
    ssize_t send(const std::vector<uint8_t>& data);

    bool is_open() const;

private:
    int fd_ = -1;
    sockaddr_in target_{};
};
```

### `Trajectory` — 生成位置
```cpp
class Trajectory {
public:
    explicit Trajectory(TrajectoryConfig config);

    // 根據當前時間推進軌跡，回傳當前位置
    // 若已走完且 loop=false，回傳 nullopt
    std::optional<Position> advance(std::chrono::milliseconds delta);

    void reset();

private:
    TrajectoryConfig config_;
    size_t current_segment_ = 0;
    double segment_progress_ = 0.0;  // 0.0 ~ 1.0
    // ...
};
```

### `TelemetryGenerator` — 把位置包成完整 telemetry
```cpp
class TelemetryGenerator {
public:
    TelemetryGenerator(std::string drone_id, SimulationConfig sim_config);

    TelemetryPacket generate(const Position& pos, std::chrono::milliseconds elapsed);

private:
    std::string drone_id_;
    SimulationConfig sim_config_;
    uint32_t sequence_ = 0;
    std::mt19937 rng_;  // For signal noise
};
```

### `Publisher` — 整合起來
```cpp
class Publisher {
public:
    Publisher(Config config);
    ~Publisher();

    void start();
    void stop();  // Set atomic flag, join threads
    void wait();  // Block until stopped

private:
    void generator_loop();
    void publisher_loop();

    Config config_;
    std::atomic<bool> running_{false};

    // Producer-consumer queue
    std::queue<TelemetryPacket> queue_;
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
    static constexpr size_t kMaxQueueSize = 100;

    std::thread generator_thread_;
    std::thread publisher_thread_;

    std::unique_ptr<UdpSocket> socket_;
    std::unique_ptr<Trajectory> trajectory_;
    std::unique_ptr<TelemetryGenerator> generator_;
};
```

### `main.cpp` — 命令列進入點
```cpp
// 使用 CLI11 解析：
//   --config <path>     必填
//   --verbose           可選，覆蓋 log level
//
// 註冊 SIGINT handler → publisher.stop()
// publisher.start(); publisher.wait();
```

---

## Backend Python 端對接

### `backend/app/ros_bridge/udp_listener.py`

- 非同步 UDP server（用 `asyncio.DatagramProtocol`）
- 綁定 `0.0.0.0:14550`
- 收到封包 → protobuf decode → 轉成既有 `TelemetryMessage` dataclass → 呼叫 `flight_tracker.handle_telemetry(msg)`
- 與 `telemetry_sub.py` 並存，共用相同下游 handler
- 在 `main.py` lifespan 啟動時 `asyncio.create_task` 起來

Python protobuf 需要 `protoc --python_out=...` 生成 `telemetry_pb2.py`，放在 `backend/app/ros_bridge/proto_gen/`。建置步驟寫在 Dockerfile。

---

## Docker 整合

### `cpp_telemetry_publisher/Dockerfile`

```dockerfile
# Multi-stage build
FROM ubuntu:22.04 AS builder
# Install cmake, g++, git, curl, zip, unzip, tar, pkg-config
# Clone vcpkg, bootstrap, install dependencies via vcpkg.json
# Build release
# Run tests

FROM ubuntu:22.04 AS runtime
# Copy binary
# Copy default config
ENTRYPOINT ["/app/telemetry_publisher"]
CMD ["--config", "/app/configs/flight_path_example.yaml"]
```

### `docker-compose.yml` 新增 service

```yaml
cpp_publisher:
  build:
    context: ./cpp_telemetry_publisher
  depends_on:
    - backend
  environment:
    - TARGET_HOST=backend
    - TARGET_PORT=14550
  networks:
    - drone-net
  # Default 不啟動，手動 `docker compose up cpp_publisher` 啟動
  profiles: ["simulator"]
```

並在 `docker-compose.yml` 的 `backend` service 開放 UDP port：
```yaml
backend:
  ports:
    - "8000:8000"
    - "14550:14550/udp"
```

---

## 測試要求

### 單元測試（GoogleTest）

- `test_trajectory.cpp`：
  - 空 waypoints 回傳 nullopt
  - 單點 waypoint 永遠回傳該點
  - 兩點之間內插正確（檢查中點位置）
  - Loop 模式到尾端會重新開始
- `test_udp_socket.cpp`：
  - Construct 成功開 socket（用 127.0.0.1 + random high port）
  - Move constructor 後原物件失效
  - Destructor 會關閉 fd
- `test_telemetry_generator.cpp`：
  - Sequence 號遞增
  - Battery 隨時間下降
  - Timestamp 接近當前時間

### 整合測試

一個 bash script `tests/integration_test.sh`：
1. 啟動 mock UDP server（Python 一行起）
2. 執行 publisher 5 秒
3. 驗證 server 收到 ≥ 40 封包（10Hz × 5s，允許 20% loss）
4. 驗證第一個封包的 drone_id 正確

---

## 實作順序（給 CLI 的 WP 切分）

### WP1：專案骨架 + Hello World
- CMakeLists.txt + vcpkg.json
- 空 main.cpp 印 "Telemetry Publisher v0.1"
- Dockerfile build 成功
- **驗收**：`docker build` 成功、容器跑起來印 log

### WP2：Config + Trajectory
- `Config::load_from_file` 解析 YAML
- `Trajectory` 類別 + 單元測試
- main.cpp 改成讀 config 印出所有 waypoint
- **驗收**：`./publisher --config configs/flight_path_example.yaml` 正確印出；trajectory 測試通過

### WP3：UDP Socket + Protobuf
- 編譯 telemetry.proto
- `UdpSocket` 類別 + 單元測試
- main.cpp 改成：每秒發一個 protobuf packet 到 127.0.0.1:14550
- 寫一個 Python 小 script (`tests/udp_receiver_check.py`) 驗證收到且能 decode
- **驗收**：Python script 收得到、decode 成功

### WP4：Publisher 整合 + Threading
- `Publisher` 類別：generator thread + publisher thread + queue
- SIGINT handler
- spdlog 整合
- **驗收**：跑起來看到 10Hz 穩定發送；Ctrl-C 優雅關閉（log 顯示 "Stopping..." 和 "Joined threads"）

### WP5：Backend UDP Listener
- `udp_listener.py` + lifespan 啟動
- protobuf python 產生
- WebSocket 收得到 cpp-drone-001 的資料
- **驗收**：`docker compose up` 後，前端地圖看到 cpp-drone-001 移動

### WP6：文件 + 清理
- README.md（build、run、架構圖、設計決策）
- 所有 TODO 清掉
- `.clang-format` + 全專案格式化
- **驗收**：README 有 build 步驟、架構圖、設計決策；`clang-format --dry-run` 無 diff

---

## 品質標準

- **零 warning** 編譯（`-Wall -Wextra -Wpedantic`）
- 通過 `clang-tidy` 基本檢查（`modernize-*`, `performance-*`, `bugprone-*`）
- 所有 public class 有 brief comment（不需要 full Doxygen）
- `main.cpp` 簡潔（< 50 行），複雜邏輯都在類別裡
- 沒有全域變數（SIGINT handler 的 publisher pointer 可例外，但要包在 anonymous namespace）

---

## 面試 talking points（做完後你能講的故事）

1. **為什麼用 UDP 不用 TCP/HTTP？**
   封包容錯、遙測頻率高、即使丟 1-2% 也不影響 operator 判斷

2. **Producer-consumer 為什麼要？**
   Generator 和 network I/O 解耦；generator 不會被 socket 阻塞

3. **RAII 在哪？**
   UdpSocket destructor 保證 fd 不洩漏，即使 exception 也是

4. **為什麼選 protobuf？**
   schema 演進、跨語言（C++ publisher + Python backend）、比 JSON 小 5-10x

5. **如果真實飛機斷線怎麼辦？**
   目前是 best-effort；生產環境會加 sequence gap detection、heartbeat、重連邏輯

6. **如何擴展到多機？**
   Publisher 接受 multiple drone_id config → 每個 drone 獨立 trajectory + generator thread；或多個 publisher process 各自負責一台

---

## progress.md 更新

在專案根目錄 `progress.md` 新增章節：

```markdown
## Phase X: C++ Telemetry Publisher

- ⬜ WP1: Project skeleton + Hello World
- ⬜ WP2: Config + Trajectory
- ⬜ WP3: UDP Socket + Protobuf
- ⬜ WP4: Publisher integration + Threading
- ⬜ WP5: Backend UDP Listener integration
- ⬜ WP6: Documentation + cleanup
```

每完成一個 WP，標 ✅ 並 commit。

---

## 給 CLI 的執行提示

- 讀取 `docs/platform_status_and_plan.md` 和 `CLAUDE.md` 先建立專案上下文
- WP 之間不需要停下來等 Sunny 確認，連續執行到 WP6 結束
- 每個 WP 完成時：commit + 更新 progress.md
- Context 耗盡：commit 當前 WP → 更新 progress.md → 停止，讓下一個 session 接手
- 遇到 vcpkg 下載超時等環境問題：寫在 WP 報告中，跳過該步驟繼續下一個 WP
- 所有程式碼、commit message、code comment 用**英文**；WP 完成報告用**繁體中文**
- 不要改動現有 Python simulator（`telemetry_sub.py` mock mode）；新舊共存
