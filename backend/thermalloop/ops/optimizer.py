"""MPC-lite optimiser: look ahead over candidates and pick the best plan.

This is the step that makes the controller *smart* rather than merely reactive.
Given the live engine, it forks it once per candidate action plan, rolls each
forward over a short horizon, scores the predicted trajectory with an explicit,
auditable objective, and returns the best-scoring plan plus the full scoreboard.

The objective is public and weighted (no hidden tuning):

    cost =  w_violation * (steps predicted over the safety band)
          + w_unmet     * predicted unmet-heat kWh
          + w_energy    * predicted pump+heat-pump kWh
          - w_recover   * predicted useful delivered-heat kWh
          + w_switch    * how far the plan moves the GPU load from "as-is"

Lower cost is better. Safety dominates (large weight), then meeting heat demand,
then energy, then heat recovery, with a small penalty for throttling compute so
the optimiser does not shed load gratuitously. Everything is deterministic:
same seed + same state => same chosen plan, so runs stay reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .engine import Action, SteppedEngine


@dataclass
class Objective:
    primary_band_C: float = 44.0
    w_violation: float = 1000.0     # per predicted over-band step (safety first)
    w_unmet_kWh: float = 20.0
    w_energy_kWh: float = 1.0
    w_recover_kWh: float = 2.0      # reward (subtracted)
    w_switch: float = 5.0           # mild penalty for moving load off its current value


@dataclass
class CandidateScore:
    label: str
    candidate: dict[str, Any]
    cost: float
    peak_primary_C: float
    violation_steps: int
    delivered_kWh: float
    pump_kWh: float
    unmet_kWh: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "candidate": self.candidate,
            "cost": round(self.cost, 3),
            "peak_primary_C": round(self.peak_primary_C, 2),
            "violation_steps": self.violation_steps,
            "delivered_kWh": round(self.delivered_kWh, 3),
            "pump_kWh": round(self.pump_kWh, 3),
            "unmet_kWh": round(self.unmet_kWh, 3),
        }


@dataclass
class OptimizerResult:
    best: CandidateScore
    scoreboard: list[CandidateScore] = field(default_factory=list)
    branch_steps: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "best": self.best.as_dict(),
            "scoreboard": [c.as_dict() for c in self.scoreboard],
            "branch_steps": self.branch_steps,
        }


def _roll(engine: SteppedEngine, candidate: dict[str, Any], horizon: int,
          obj: Objective) -> tuple[int, float, float, float, float]:
    branch = engine.fork()
    action = Action(
        gpu_load_fraction=candidate.get("gpu_load_fraction"),
        heat_pump_enabled=candidate.get("heat_pump_enabled"),
        aux_rejection_enabled=candidate.get("aux_rejection_enabled"),
        primary_pump_speed=candidate.get("primary_pump_speed"),
        secondary_pump_speed=candidate.get("secondary_pump_speed"),
        buffer_charge_enabled=candidate.get("buffer_charge_enabled"),
        secondary_supply_setpoint_C=candidate.get("secondary_supply_setpoint_C"),
        aux_rejection_level=candidate.get("aux_rejection_level"),
    )
    dt = branch.get_state().dt_s
    peak = -1e9
    violations = 0
    delivered_J = pump_J = unmet_J = 0.0
    for _ in range(max(1, horizon)):
        _, rec = branch.step(action, dt)
        peak = max(peak, rec.primary_supply_C)
        if rec.primary_supply_C >= obj.primary_band_C:
            violations += 1
        delivered_J += rec.delivered_total_W * dt
        pump_J += (rec.pump_power_W + rec.heat_pump_elec_W) * dt
        unmet_J += rec.unmet_demand_W * dt
    return violations, peak, delivered_J / 3.6e6, pump_J / 3.6e6, unmet_J / 3.6e6


class MPCOptimizer:
    """Evaluate a candidate set and return the lowest-cost plan."""

    def __init__(self, objective: Objective | None = None, horizon: int = 6) -> None:
        self.obj = objective or Objective()
        self.horizon = horizon

    def optimise(
        self,
        engine: SteppedEngine,
        candidates: dict[str, dict[str, Any]],
        current_load: float,
    ) -> OptimizerResult:
        obj = self.obj
        scores: list[CandidateScore] = []
        branch_steps = 0
        for label, cand in candidates.items():
            viol, peak, delivered, pump, unmet = _roll(engine, cand, self.horizon, obj)
            branch_steps += self.horizon
            load = cand.get("gpu_load_fraction", current_load)
            switch = abs(float(load) - current_load) if load is not None else 0.0
            cost = (obj.w_violation * viol
                    + obj.w_unmet_kWh * unmet
                    + obj.w_energy_kWh * pump
                    - obj.w_recover_kWh * delivered
                    + obj.w_switch * switch)
            scores.append(CandidateScore(
                label=label, candidate=cand, cost=cost, peak_primary_C=peak,
                violation_steps=viol, delivered_kWh=delivered, pump_kWh=pump,
                unmet_kWh=unmet))
        scores.sort(key=lambda c: c.cost)
        return OptimizerResult(best=scores[0], scoreboard=scores, branch_steps=branch_steps)


def default_candidates(
    current_load: float,
    current_setpoint_C: float = 55.0,
) -> dict[str, dict[str, Any]]:
    """Bounded coordinate-descent sweep over load and secondary setpoint.

    A full Cartesian grid would be expensive. Sweep each control axis around
    the current operating point, retaining full auxiliary rejection for safety.
    """
    loads = sorted({round(max(0.3, min(1.0, current_load + d)), 3)
                    for d in (-0.15, 0.0, 0.1)})
    setpoints = sorted({round(max(45.0, min(62.0, current_setpoint_C + d)), 1)
                        for d in (-5.0, 0.0, 5.0)})
    grid: dict[str, dict[str, Any]] = {}
    for load in loads:
        grid[f"L{load}"] = {
            "gpu_load_fraction": load, "aux_rejection_level": 1.0,
            "secondary_supply_setpoint_C": current_setpoint_C,
        }
    for sp in setpoints:
        grid[f"S{sp:.0f}"] = {
            "gpu_load_fraction": current_load, "aux_rejection_level": 1.0,
            "secondary_supply_setpoint_C": sp,
        }
    return grid
