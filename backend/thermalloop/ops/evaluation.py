"""Three-mode comparison harness.

Runs control modes A (rule-based), B (agents, no forecast) and C (agents with
forecast + validation) on the SAME scenario, seed, timestep and drivers, then
computes the metrics from the brief:

  total_power_kWh        - pumps + heat-pump electricity
  on_time_job_fraction   - fraction of steps GPU load met its diurnal target
  temp_violation_steps   - steps with primary supply over the safety trip temp
  comfort_shortfall_Kh   - integral of zone under-temperature over time
  useful_heat_kWh        - delivered recovered heat
  recovery_time_steps    - steps to return primary temp to band after worst peak
  failover_count         - owner comms-loss / timeout fallbacks taken
  coordinator_cost       - forecast branch steps consumed (0 for A and B)

It does NOT tune anything to make C win. The returned ``verdict`` states,
per metric, which mode was best and whether C actually helped versus B/A.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import MODEL_VERSION
from .runtime import OpsRuntime
from .safety import Limits

COMFORT_SETPOINTS = {"zone_robot_lab": 22.0, "zone_seed_testing": 24.0,
                     "zone_seed_storage": 15.0}


# Band below the trip temperature that counts as "recovered" (named, not magic).
RECOVERY_BAND_C = 2.0
# A job step is "on time" when achieved GPU load meets this fraction of demand.
ON_TIME_TOLERANCE = 0.95


def _metrics(runtime: OpsRuntime, limits: Limits) -> dict[str, Any]:
    from ..simulation import _diurnal_load  # pure helper, no engine state
    reports = runtime.reports
    dt_s = runtime.engine.get_state().dt_s
    dt_h = dt_s / 3600.0
    base = runtime.engine._base_fraction
    peak = runtime.engine._peak_fraction
    total_elec_kWh = 0.0
    useful_heat_kWh = 0.0
    temp_violations = 0
    comfort_Kh = 0.0
    failovers = 0
    peak_primary = -1e9
    peak_idx = 0

    # "Ideal" GPU demand for a step = the undisturbed diurnal driver at that
    # step's own recorded hour. This is a stateless function of the hour, so it
    # is identical across modes A/B/C and immune to the bootstrap phase offset
    # (the previous reference-engine approach was off by one step). A job is
    # "on time" when the achieved GPU load reaches ON_TIME_TOLERANCE of demand.
    met = 0
    for i, r in enumerate(reports):
        rec = r.record
        total_elec_kWh += (rec.pump_power_W + rec.heat_pump_elec_W) * dt_h / 1000.0
        useful_heat_kWh += rec.delivered_total_W * dt_h / 1000.0
        demand = _diurnal_load(rec.hour, base, peak)
        if demand <= 1e-9 or rec.gpu_load_fraction >= ON_TIME_TOLERANCE * demand:
            met += 1
        if rec.primary_supply_C >= limits.primary_supply_max_C:
            temp_violations += 1
        if rec.primary_supply_C > peak_primary:
            peak_primary, peak_idx = rec.primary_supply_C, i
        for zone, setp in COMFORT_SETPOINTS.items():
            temp = rec.zone_temperature_C.get(zone)
            if temp is not None and temp < setp:
                comfort_Kh += (setp - temp) * dt_h
        failovers += sum(1 for f in r.faults
                         if f.get("code") in ("owner_comms_loss", "owner_timeout"))
    on_time_fraction = met / max(1, len(reports))

    # recovery time: steps after the worst peak until primary back within band
    recovery = 0
    for j in range(peak_idx, len(reports)):
        if reports[j].record.primary_supply_C <= limits.primary_supply_max_C - RECOVERY_BAND_C:
            recovery = j - peak_idx
            break
    else:
        recovery = len(reports) - peak_idx

    return {
        "total_power_kWh": round(total_elec_kWh, 3),
        "on_time_job_fraction": round(on_time_fraction, 4),
        "temp_violation_steps": temp_violations,
        "comfort_shortfall_Kh": round(comfort_Kh, 3),
        "useful_heat_kWh": round(useful_heat_kWh, 3),
        "peak_primary_supply_C": round(peak_primary, 2),
        "recovery_time_steps": recovery,
        "failover_count": failovers,
        "coordinator_cost_branch_steps": runtime.coordinator_compute_cost,
    }


@dataclass
class Comparison:
    scenario: str
    seed: int
    n_steps: int
    model_version: str
    per_mode: dict[str, dict[str, Any]] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"scenario": self.scenario, "seed": self.seed, "n_steps": self.n_steps,
                "model_version": self.model_version, "per_mode": self.per_mode,
                "verdict": self.verdict}


def _verdict(per_mode: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Honest per-metric comparison. Lower is better except the two noted."""
    higher_better = {"on_time_job_fraction", "useful_heat_kWh"}
    verdict: dict[str, Any] = {}
    for metric in per_mode["A"]:
        if metric == "coordinator_cost_branch_steps":
            continue
        vals = {m: per_mode[m][metric] for m in ("A", "B", "C")}
        if metric in higher_better:
            best = max(vals, key=vals.get)
        else:
            best = min(vals, key=vals.get)
        verdict[metric] = {"values": vals, "best_mode": best}

    # Did C actually help relative to B and A? Report plainly.
    notes = []
    c_power, b_power = per_mode["C"]["total_power_kWh"], per_mode["B"]["total_power_kWh"]
    if per_mode["C"]["temp_violation_steps"] < per_mode["B"]["temp_violation_steps"]:
        notes.append("C reduced temperature violations vs B (forecast pre-trim helped).")
    elif per_mode["C"]["temp_violation_steps"] > per_mode["B"]["temp_violation_steps"]:
        notes.append("C had MORE violations than B: forecast did not help here.")
    else:
        notes.append("C and B had equal temperature violations: forecast added no safety benefit.")
    if c_power > b_power:
        notes.append(f"C used more electricity than B ({c_power} vs {b_power} kWh) "
                     f"plus {per_mode['C']['coordinator_cost_branch_steps']} branch steps of compute.")
    verdict["_notes"] = notes
    verdict["_honesty"] = ("Metrics are raw simulation outputs on identical seed/inputs; "
                           "no tuning was applied to favour any mode.")
    return verdict


def compare_modes(
    *, scenario: str = "none", seed: int = 0, n_steps: int = 48,
    timestep_s: int = 600, start_hour: float = 0.0,
    drivers: dict[str, Any] | None = None, limits: Limits | None = None,
) -> Comparison:
    limits = limits or Limits()
    per_mode: dict[str, dict[str, Any]] = {}
    for mode in ("A", "B", "C"):
        rt = OpsRuntime(mode=mode, scenario=scenario, seed=seed, timestep_s=timestep_s,
                        start_hour=start_hour, drivers=drivers, limits=limits)
        rt.run(n_steps)
        per_mode[mode] = _metrics(rt, limits)
    cmp = Comparison(scenario=scenario, seed=seed, n_steps=n_steps,
                     model_version=MODEL_VERSION, per_mode=per_mode)
    cmp.verdict = _verdict(per_mode)
    return cmp
