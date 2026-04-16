# Multi-stage build for C++ Telemetry Publisher
# Stage 1: build + test
# Stage 2: minimal runtime image

# ── Builder ────────────────────────────────────────────────────────────────────
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    git \
    curl \
    zip \
    unzip \
    tar \
    pkg-config \
    ninja-build \
    autoconf \
    automake \
    libtool \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bootstrap vcpkg (shallow clone for speed)
RUN git clone --depth=1 https://github.com/microsoft/vcpkg /vcpkg \
    && /vcpkg/bootstrap-vcpkg.sh -disableMetrics

ENV VCPKG_ROOT=/vcpkg
# Disable telemetry
ENV VCPKG_DISABLE_METRICS=1

WORKDIR /src

# ── Dependency layer (cached while vcpkg.json + CMakeLists.txt unchanged) ──────
COPY vcpkg.json CMakeLists.txt ./
# Create stub source files so CMake configure succeeds without the real sources.
# Real source is COPY-ed below after the slow dependency install is cached.
RUN mkdir -p src include/telemetry_publisher tests proto \
    proto_gen

# Configure: vcpkg reads vcpkg.json and builds all dependencies
RUN cmake -S . -B /build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE=/vcpkg/scripts/buildsystems/vcpkg.cmake \
    2>&1 | tail -20

# ── Source layer ───────────────────────────────────────────────────────────────
COPY proto/   ./proto/
COPY include/ ./include/
COPY src/     ./src/
COPY tests/   ./tests/
COPY configs/ ./configs/

# Build everything (proto codegen runs here too)
RUN cmake --build /build --parallel "$(nproc)"

# Run unit tests
RUN cd /build && ctest --output-on-failure

# ── Runtime ────────────────────────────────────────────────────────────────────
FROM ubuntu:22.04 AS runtime

# libstdc++ is needed for the dynamic binary; libprotobuf is linked in
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/telemetry_publisher /app/telemetry_publisher
COPY --from=builder /src/configs               /app/configs

# TARGET_HOST and TARGET_PORT can be overridden at runtime to point at backend
ENTRYPOINT ["/app/telemetry_publisher"]
CMD ["--config", "/app/configs/flight_path_example.yaml"]
