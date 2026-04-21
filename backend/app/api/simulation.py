"""
Simulation Control API — pause/resume/speed for the in-process FleetSimulator.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal

router = APIRouter()


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "set_speed"]
    speed: float = Field(default=1.0, ge=0.1, le=10.0)


@router.get("/status")
async def simulation_status(request: Request):
    fleet = getattr(request.app.state, "fleet", None)
    if fleet is None:
        raise HTTPException(status_code=503, detail="Fleet not initialised")
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
    fleet = getattr(request.app.state, "fleet", None)
    if fleet is None:
        raise HTTPException(status_code=503, detail="Fleet not initialised")

    if body.action == "pause":
        fleet.pause()
    elif body.action == "resume":
        fleet.resume()
    elif body.action == "set_speed":
        fleet.set_speed(body.speed)

    return {"ok": True, "action": body.action, "speed": fleet.speed_multiplier, "paused": fleet.paused}
