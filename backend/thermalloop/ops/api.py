"""FastAPI router for the autonomous operations layer.

Exposes a small session API so the ops UI can create a live run, step it
(pause/resume/step/speed are the caller's cadence over ``tick``), inspect the
event timeline, read agent decisions, run the three-mode comparison, and list
stored experiments. Sessions are in-memory; comparisons and experiments persist
to SQLite via :class:`ExperimentStore`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import MODEL_VERSION
from .actuators import OWNERSHIP, RANGES
from .agents import ALL_AGENTS
from .evaluation import compare_modes
from .experiments import ExperimentStore
from .runtime import OpsRuntime
from .safety import Limits
from .scenarios import SCENARIO_LABELS

router = APIRouter(prefix="/api/ops", tags=["ops"])

_SESSIONS: dict[str, OpsRuntime] = {}
_STORE = ExperimentStore(Path(__file__).resolve().parents[3] / "results" / "experiments.sqlite")


class CreateSession(BaseModel):
    mode: str = Field("C", pattern="^[ABC]$")
    scenario: str = "none"
    seed: int = 0
    timestep_s: int = 600
    start_hour: float = 0.0
    drivers: dict[str, Any] | None = None


class TickRequest(BaseModel):
    steps: int = Field(1, ge=1, le=500)


class CompareRequest(BaseModel):
    scenario: str = "none"
    seed: int = 0
    n_steps: int = Field(48, ge=1, le=2000)
    timestep_s: int = 600
    start_hour: float = 0.0
    drivers: dict[str, Any] | None = None
    persist: bool = True


def _report_dict(report: Any) -> dict[str, Any]:
    rec = report.record
    return {
        "index": report.index, "t_s": report.t_s, "hour": rec.hour,
        "scenario_label": report.scenario_label,
        "metrics": {
            "gpu_load_fraction": rec.gpu_load_fraction,
            "primary_supply_C": rec.primary_supply_C,
            "secondary_supply_C": rec.secondary_supply_C,
            "buffer_temp_C": rec.buffer_temp_C,
            "soil_temp_C": rec.soil_temp_C,
            "delivered_total_W": rec.delivered_total_W,
            "unmet_demand_W": rec.unmet_demand_W,
            "pump_power_W": rec.pump_power_W,
            "heat_pump_elec_W": rec.heat_pump_elec_W,
            "primary_unrejected_W": rec.primary_unrejected_W,
            "zone_temperature_C": rec.zone_temperature_C,
        },
        "decisions": report.decisions,
        "safety_events": report.safety_events,
        "faults": report.faults,
        "proposals": report.proposals,
    }


@router.get("/meta")
def meta() -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "modes": {"A": "Rule-based baseline", "B": "Agents (no forecast)",
                  "C": "Agents + forecast & validation"},
        "scenarios": SCENARIO_LABELS,
        "agents": [{"name": cls.name, "owns": list(cls.owns)} for cls in ALL_AGENTS],
        "ownership": OWNERSHIP,
        "actuator_ranges": {k: list(v) for k, v in RANGES.items()},
        "coordinator": {
            "regimes": ["protect", "recover", "conserve"],
            "note": ("Supervisory layer: picks a global regime from measured "
                     "state and publishes per-agent targets. Owns no actuator."),
        },
        "real_device_enabled": False,
    }


@router.post("/session")
def create_session(req: CreateSession) -> dict[str, Any]:
    try:
        rt = OpsRuntime(mode=req.mode, scenario=req.scenario, seed=req.seed,
                        timestep_s=req.timestep_s, start_hour=req.start_hour,
                        drivers=req.drivers)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    sid = f"ops_{uuid.uuid4().hex[:10]}"
    _SESSIONS[sid] = rt
    return {"session_id": sid, "mode": req.mode, "scenario": req.scenario,
            "seed": req.seed, "model_version": MODEL_VERSION}


@router.post("/session/{session_id}/tick")
def tick(session_id: str, req: TickRequest) -> dict[str, Any]:
    rt = _SESSIONS.get(session_id)
    if rt is None:
        raise HTTPException(404, "unknown session")
    reports = [rt.tick() for _ in range(req.steps)]
    return {"reports": [_report_dict(r) for r in reports],
            "coordinator_cost_branch_steps": rt.coordinator_compute_cost,
            "total_steps": rt.index}


@router.get("/session/{session_id}/events")
def events(session_id: str, since_seq: int = -1, limit: int = 200) -> dict[str, Any]:
    rt = _SESSIONS.get(session_id)
    if rt is None:
        raise HTTPException(404, "unknown session")
    evs = rt.bus.events(since_seq=since_seq)[-limit:]
    return {"events": [e.as_dict() for e in evs], "latest_seq": rt.bus._seq - 1}


@router.get("/session/{session_id}/state")
def session_state(session_id: str) -> dict[str, Any]:
    rt = _SESSIONS.get(session_id)
    if rt is None:
        raise HTTPException(404, "unknown session")
    return {"blackboard": rt.board.snapshot(), "total_steps": rt.index,
            "mode": rt.mode, "scenario": rt.scenario_name}


@router.delete("/session/{session_id}")
def delete_session(session_id: str) -> dict[str, bool]:
    return {"deleted": _SESSIONS.pop(session_id, None) is not None}


@router.post("/compare")
def compare(req: CompareRequest) -> dict[str, Any]:
    try:
        cmp = compare_modes(scenario=req.scenario, seed=req.seed, n_steps=req.n_steps,
                            timestep_s=req.timestep_s, start_hour=req.start_hour,
                            drivers=req.drivers)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = cmp.as_dict()
    if req.persist:
        cmp_id = f"cmp_{uuid.uuid4().hex[:10]}"
        _STORE.save_comparison(cmp_id, scenario=req.scenario, seed=req.seed,
                               model_version=MODEL_VERSION, result=result)
        result["cmp_id"] = cmp_id
    return result


@router.get("/comparisons")
def list_comparisons(limit: int = 50) -> dict[str, Any]:
    return {"comparisons": _STORE.list_comparisons(limit)}


@router.get("/experiments")
def list_experiments(limit: int = 50) -> dict[str, Any]:
    return {"experiments": _STORE.list_experiments(limit)}
