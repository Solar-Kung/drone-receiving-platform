#!/usr/bin/env python3
"""
udp_receiver_check.py — WP3 integration smoke-test.

Usage:
    # Terminal 1 — start this receiver (port 14550)
    python tests/udp_receiver_check.py

    # Terminal 2 — run the publisher for a few seconds
    ./build/telemetry_publisher --config configs/flight_path_example.yaml

The script listens for 10 seconds, decodes each protobuf packet, and
prints a summary.  Exit code 0 = at least one packet received and decoded.
"""

import socket
import sys
import time

# Allow running without proto_gen by falling back to raw hex dump
try:
    import importlib.util, os
    _here = os.path.dirname(__file__)
    spec = importlib.util.spec_from_file_location(
        "telemetry_pb2",
        os.path.join(_here, "..", "backend", "app", "ros_bridge", "proto_gen", "telemetry_pb2.py"),
    )
    if spec and spec.loader:
        telemetry_pb2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(telemetry_pb2)  # type: ignore
        TelemetryPacket = telemetry_pb2.TelemetryPacket
        HAS_PROTO = True
    else:
        raise ImportError("no spec")
except Exception:
    HAS_PROTO = False
    print("[warn] telemetry_pb2 not found — will print raw hex instead", file=sys.stderr)


def main() -> int:
    HOST = "0.0.0.0"
    PORT = 14550
    TIMEOUT_SEC = 10

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)
    sock.bind((HOST, PORT))
    print(f"Listening on UDP {HOST}:{PORT} for {TIMEOUT_SEC}s …")

    received = 0
    deadline = time.monotonic() + TIMEOUT_SEC

    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except TimeoutError:
            continue

        received += 1
        if HAS_PROTO:
            pkt = TelemetryPacket()
            pkt.ParseFromString(data)
            print(
                f"[{received:4d}] seq={pkt.sequence:5d}  drone={pkt.drone_id!r}"
                f"  lat={pkt.latitude:.6f}  lon={pkt.longitude:.6f}"
                f"  alt={pkt.altitude_m:.1f}m  bat={pkt.battery_percent:.1f}%"
            )
        else:
            print(f"[{received:4d}] {len(data)} bytes from {addr}: {data[:16].hex()} …")

    sock.close()
    print(f"\nReceived {received} packet(s) in {TIMEOUT_SEC}s.")
    if received == 0:
        print("FAIL — no packets received", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
