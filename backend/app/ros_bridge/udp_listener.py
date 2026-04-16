"""
UDP Listener — receives protobuf TelemetryPacket from the C++ publisher.

Binds to 0.0.0.0:14550 using asyncio.DatagramProtocol.
Each packet is decoded, converted to a TelemetryMessage, and forwarded
to flight_tracker.handle_telemetry — the same handler used by the ROS 2
bridge.  Both sources are therefore interchangeable from the backend's
perspective.

telemetry_pb2.py is generated on first startup from
ros_bridge/proto_gen/telemetry.proto using grpcio-tools.
"""

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from app.ros_bridge.telemetry_sub import TelemetryMessage

logger = logging.getLogger(__name__)

_PROTO_DIR = os.path.join(os.path.dirname(__file__), "proto_gen")
_PB2_PATH  = os.path.join(_PROTO_DIR, "telemetry_pb2.py")
_PROTO_FILE = os.path.join(_PROTO_DIR, "telemetry.proto")

UDP_HOST = "0.0.0.0"
UDP_PORT = 14550


# ── protobuf generation ────────────────────────────────────────────────────────

def _ensure_pb2() -> None:
    """Generate telemetry_pb2.py from the .proto file if it doesn't exist."""
    if os.path.exists(_PB2_PATH):
        return
    logger.info("Generating telemetry_pb2.py from %s", _PROTO_FILE)
    result = subprocess.run(
        [
            sys.executable, "-m", "grpc_tools.protoc",
            f"-I{_PROTO_DIR}",
            f"--python_out={_PROTO_DIR}",
            _PROTO_FILE,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"protoc failed:\n{result.stderr}"
        )
    logger.info("telemetry_pb2.py generated successfully")


def _load_pb2():
    """Import and return the generated telemetry_pb2 module."""
    _ensure_pb2()
    import importlib.util
    spec = importlib.util.spec_from_file_location("telemetry_pb2", _PB2_PATH)
    mod  = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    return mod


# ── asyncio DatagramProtocol ───────────────────────────────────────────────────

class _TelemetryProtocol(asyncio.DatagramProtocol):
    """asyncio UDP server that decodes protobuf and dispatches to flight_tracker."""

    def __init__(self, telemetry_packet_cls, handle_fn) -> None:
        self._TelemetryPacket = telemetry_packet_cls
        self._handle = handle_fn
        self._packets_received = 0

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        logger.info("UDP listener ready on %s:%d", UDP_HOST, UDP_PORT)

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            pkt = self._TelemetryPacket()
            pkt.ParseFromString(data)
        except Exception as exc:
            logger.warning("Failed to decode UDP packet from %s: %s", addr, exc)
            return

        self._packets_received += 1
        if self._packets_received % 100 == 0:
            logger.debug(
                "UDP: %d packets received; last from drone=%s seq=%d",
                self._packets_received, pkt.drone_id, pkt.sequence,
            )

        # Convert to the shared TelemetryMessage dataclass
        msg = TelemetryMessage(
            drone_id         = pkt.drone_id,
            flight_id        = "udp-flight-001",      # placeholder until WP5B
            timestamp        = datetime.now(timezone.utc).isoformat(),
            latitude         = pkt.latitude,
            longitude        = pkt.longitude,
            altitude         = pkt.altitude_m,
            speed            = pkt.speed_mps,
            heading          = pkt.heading_deg,
            battery_level    = pkt.battery_percent,
            signal_strength  = pkt.signal_strength,
        )

        asyncio.ensure_future(self._handle(msg))

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP listener error: %s", exc)


# ── public API ─────────────────────────────────────────────────────────────────

async def start_udp_listener(handle_telemetry_fn) -> None:
    """
    Start the asyncio UDP listener.  Call once from the FastAPI lifespan.

    Args:
        handle_telemetry_fn: coroutine ``async (TelemetryMessage) -> None``
                             (typically flight_tracker.handle_telemetry)
    """
    try:
        pb2 = _load_pb2()
    except Exception as exc:
        logger.error("UDP listener disabled — could not load protobuf: %s", exc)
        return

    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _TelemetryProtocol(pb2.TelemetryPacket, handle_telemetry_fn),
        local_addr=(UDP_HOST, UDP_PORT),
    )
    logger.info("UDP/protobuf telemetry listener started on port %d", UDP_PORT)
    # transport is kept alive by the event loop; no explicit cleanup needed
    # for a server that runs until process exit.
    _ = transport  # suppress linter warning
