# C++ Telemetry Publisher

A standalone C++17 drone telemetry simulator that acts as the **L2 air side** of the drone-receiving-platform.  It reads a flight-path YAML config, generates realistic telemetry at a configurable rate, and streams serialised Protocol Buffer packets over UDP to the Python backend.

## Architecture

```
┌─────────────────────────────────┐
│   C++ Telemetry Publisher       │
│                                 │
│  Trajectory (linear interp.)    │
│       │                         │
│       ▼  10 Hz                  │
│  TelemetryGenerator             │
│  (battery drain, signal noise)  │
│       │                         │
│       ▼  producer queue         │
│  Publisher (2 threads)          │
│       │                         │
│       ▼  UDP/protobuf           │
└───────┼─────────────────────────┘
        │  :14550
        ▼
┌─────────────────────────────────┐
│  Python Backend  (FastAPI)      │
│  ros_bridge/udp_listener.py     │
│       │                         │
│       ▼                         │
│  flight_tracker.handle_telemetry│
│       │                         │
│       ▼                         │
│  WebSocket /ws/telemetry  ──►  Frontend map
└─────────────────────────────────┘
```

Compared to the existing Python simulator (HTTP POST):

| Source              | Protocol     | Simulated layer |
|---------------------|-------------|-----------------|
| Python simulator    | HTTP POST   | Simplified L2   |
| **C++ publisher**   | UDP binary  | Real L2         |

Both sources feed the same `handle_telemetry` handler — the backend is source-agnostic.

## Build

### Prerequisites

- CMake ≥ 3.16
- g++ ≥ 11 (or clang ≥ 14)
- [vcpkg](https://vcpkg.io) — set `VCPKG_ROOT` or pass `-DCMAKE_TOOLCHAIN_FILE`

```bash
cd cpp_telemetry_publisher

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake

cmake --build build --parallel
```

### Docker (recommended)

```bash
# Build the image (vcpkg downloads ~5 min on first run; cached afterwards)
docker build -t telemetry_publisher cpp_telemetry_publisher/

# Run standalone (targets host machine backend)
docker run --rm telemetry_publisher \
  --config /app/configs/flight_path_example.yaml

# Run as part of the full stack
docker compose --profile simulator up cpp_publisher
```

## Run

```bash
./build/telemetry_publisher --config configs/flight_path_example.yaml
./build/telemetry_publisher --config configs/flight_path_example.yaml --verbose
./build/telemetry_publisher --version
```

`Ctrl-C` triggers SIGINT → `Publisher::stop()` → threads join cleanly (log shows *"Joined threads"*).

## Tests

```bash
cd build && ctest --output-on-failure
```

Three test suites:

| Suite | Cases | What it covers |
|-------|-------|---------------|
| `test_trajectory` | 8 | empty/single waypoint, midpoint interp, altitude lerp, loop restart, no-loop nullopt, hold_sec hover |
| `test_udp_socket` | 5 | open socket, send reaches receiver, move ctor, move assign, RAII destructor |
| `test_telemetry_generator` | 7 | sequence increment, battery drain, battery clamp, timestamp epoch, drone_id, position fields, signal bounds |

### Python smoke test (WP3 integration)

```bash
# Terminal 1 — listen
python tests/udp_receiver_check.py

# Terminal 2 — publish
./build/telemetry_publisher --config configs/flight_path_example.yaml
```

## Design Decisions

### Why UDP?

Drone telemetry is loss-tolerant: missing one position update (100 ms at 10 Hz) does not affect situational awareness.  UDP avoids TCP's head-of-line blocking and connection overhead — critical when bandwidth is constrained or latency must be minimal.

### Why Protocol Buffers?

- **Schema evolution**: fields can be added without breaking old receivers.
- **Cross-language**: the same `.proto` generates both C++ sender and Python receiver code.
- **Compact**: ~5–10× smaller than JSON for the same payload, saving radio bandwidth on real drones.

### Producer-consumer queue

`generator_thread` and `publisher_thread` are decoupled by a bounded `std::queue` (capacity 100).  This ensures that a momentary network stall never delays telemetry generation, and that a fast generator cannot exhaust memory.

### RAII everywhere

`UdpSocket` owns its file descriptor.  The constructor opens it; the destructor closes it — no explicit cleanup needed even if an exception propagates.  `std::unique_ptr` is used for all owned sub-objects in `Publisher`; there are zero raw `new`/`delete` calls.

### Thread safety

- `running_` is `std::atomic<bool>` — no lock needed for the stop flag.
- The queue is protected by `std::mutex` + `std::condition_variable`; the consumer blocks efficiently instead of spinning.
- SIGINT sets `running_ = false` via a pointer in an anonymous namespace (not a true global).

## File Structure

```
cpp_telemetry_publisher/
├── CMakeLists.txt          — C++17, vcpkg, three GTest suites
├── vcpkg.json              — spdlog, yaml-cpp, cli11, protobuf, gtest
├── Dockerfile              — multi-stage build (builder + runtime)
├── .clang-format           — Google style, 4-space indent, 100-col limit
├── configs/
│   └── flight_path_example.yaml
├── proto/
│   └── telemetry.proto     — TelemetryPacket protobuf schema
├── include/telemetry_publisher/
│   ├── config.h            — Config, Waypoint, structs
│   ├── trajectory.h        — Trajectory, Position
│   ├── telemetry_generator.h
│   ├── udp_socket.h        — RAII UDP socket
│   └── publisher.h         — Publisher (threading + queue)
├── src/
│   ├── main.cpp            — CLI11 entry point (< 50 lines of logic)
│   ├── config.cpp
│   ├── trajectory.cpp
│   ├── telemetry_generator.cpp
│   ├── udp_socket.cpp
│   └── publisher.cpp
└── tests/
    ├── test_trajectory.cpp
    ├── test_udp_socket.cpp
    ├── test_telemetry_generator.cpp
    └── udp_receiver_check.py   — Python UDP smoke test
```
