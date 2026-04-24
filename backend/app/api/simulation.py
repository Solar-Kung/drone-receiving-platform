"""
Simulation Control API — pause/resume/speed for the in-process FleetSimulator.

Note: These endpoints are only served by the leader instance. Followers return 503
so the client can retry (nginx round-robin will eventually reach the leader).
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal

from app.services.redis_client import get_redis

router = APIRouter()

SIMULATION_LEADER_KEY = "drone_platform:simulation_leader"


async def _require_leader(request: Request):
    """Raise 503 with leader hint if this instance is not the simulation leader."""
    if not getattr(request.app.state, "is_leader", False):
        try:
            leader = await get_redis().get(SIMULATION_LEADER_KEY)
        except Exception:
            leader = None
        raise HTTPException(
            status_code=503,
            detail={"error": "not_leader", "leader_hostname": leader},
        )


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "set_speed"]
    speed: float = Field(default=1.0, ge=0.1, le=10.0)


@router.get("/status")
async def simulation_status(request: Request):
    await _require_leader(request)
    fleet = request.app.state.fleet
    drones = [
        {
            "drone_id": drone_id,
            "running": sim.running,
            "paused": sim.paused,
            "stopped": sim.is_stopped,
        }
        for drone_id, sim in fleet.simulators.items()
    ]
    return {
        "paused": fleet.paused,
        "speed": fleet.speed_multiplier,
        "drones": drones,
    }


@router.post("/control")
async def simulation_control(body: ControlRequest, request: Request):
    await _require_leader(request)
    fleet = request.app.state.fleet

    if body.action == "pause":
        fleet.pause()
    elif body.action == "resume":
        fleet.resume()
    elif body.action == "set_speed":
        fleet.set_speed(body.speed)

    return {"ok": True, "action": body.action, "speed": fleet.speed_multiplier, "paused": fleet.paused}
