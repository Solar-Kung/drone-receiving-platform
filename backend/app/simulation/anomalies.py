"""
Anomaly Injection — per-simulator probabilistic fault injection.

Each TelemetrySimulator holds one AnomalyState instance.
Call maybe_trigger_anomaly() once per second (before payload assembly),
then apply_anomaly() to mutate the outgoing payload.
"""

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnomalyType(str, Enum):
    BATTERY_DROP = "battery_drop"       # immediate -15% battery
    GPS_DRIFT = "gps_drift"             # position offset ±0.0005 deg
    SIGNAL_LOSS = "signal_loss"         # signal_strength=0, suppress POST for 5s
    EMERGENCY_RETURN = "emergency_return"  # flag early return to orchestrator


# Mean time between events ≈ 1/prob seconds per anomaly type
ANOMALY_PROBABILITIES: dict[AnomalyType, float] = {
    AnomalyType.BATTERY_DROP: 0.002,       # ~8 min average interval
    AnomalyType.GPS_DRIFT: 0.001,          # ~16 min
    AnomalyType.SIGNAL_LOSS: 0.0005,       # ~33 min
    AnomalyType.EMERGENCY_RETURN: 0.0003,  # ~55 min
}

# How long each anomaly stays "active" (seconds)
ANOMALY_DURATIONS: dict[AnomalyType, float] = {
    AnomalyType.BATTERY_DROP: 1.0,         # single-tick
    AnomalyType.GPS_DRIFT: 5.0,
    AnomalyType.SIGNAL_LOSS: 5.0,
    AnomalyType.EMERGENCY_RETURN: 1.0,     # single-tick flag
}


@dataclass
class AnomalyState:
    active: Optional[AnomalyType] = None
    started_at: Optional[float] = None   # monotonic time
    metadata: dict = field(default_factory=dict)

    def is_active(self) -> bool:
        if self.active is None:
            return False
        elapsed = time.monotonic() - (self.started_at or 0)
        if elapsed >= ANOMALY_DURATIONS.get(self.active, 1.0):
            self.active = None
            self.started_at = None
            self.metadata = {}
            return False
        return True

    def clear(self) -> None:
        self.active = None
        self.started_at = None
        self.metadata = {}


def maybe_trigger_anomaly(state: AnomalyState) -> AnomalyState:
    """
    Roll once per second. If no anomaly is active, randomly trigger one.
    Modifies state in-place and returns it.
    """
    if state.is_active():
        return state  # existing anomaly still running

    for anomaly_type, prob in ANOMALY_PROBABILITIES.items():
        if random.random() < prob:
            state.active = anomaly_type
            state.started_at = time.monotonic()
            state.metadata = {}
            break

    return state


def apply_anomaly(payload: dict, state: AnomalyState) -> dict:
    """
    Return a (possibly modified) copy of payload based on current anomaly.
    Does NOT mutate the input dict.
    suppress_post is communicated via payload["_suppress_post"] = True.
    """
    if not state.is_active():
        return payload

    result = dict(payload)

    if state.active == AnomalyType.BATTERY_DROP:
        result["battery_level"] = max(0.0, payload.get("battery_level", 100.0) - 15.0)

    elif state.active == AnomalyType.GPS_DRIFT:
        result["latitude"] = payload["latitude"] + random.gauss(0, 0.0005)
        result["longitude"] = payload["longitude"] + random.gauss(0, 0.0005)

    elif state.active == AnomalyType.SIGNAL_LOSS:
        result["signal_strength"] = 0.0
        result["_suppress_post"] = True   # simulator will skip the HTTP POST

    elif state.active == AnomalyType.EMERGENCY_RETURN:
        result["_emergency_return"] = True

    return result
