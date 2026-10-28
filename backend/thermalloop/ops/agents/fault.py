"""Fault agent -- detects abnormal conditions and raises faults.

It owns no actuator. It cross-checks the blackboard for: untrusted safety
sensors, an energy residual that has drifted (model/measurement mismatch), a
primary loop that is losing its ability to reject heat (pump degradation
signature), and persistent large unmet demand. Each detection is emitted as a
``fault`` the runtime turns into a bus event, and -- for the dangerous ones --
a high-priority request to shed load or increase rejection. It does not invent
root causes it cannot see; it reports the observable signature.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Request


class FaultAgent(Agent):
    name = "fault"
    owns = ()

    def __init__(self, forecaster=None):
        super().__init__(forecaster)
        self._flow_history: list[float] = []

    def reset(self):
        super().reset()
        self._flow_history = []

    def act(self, board, t_s):
        out = AgentOutput()

        # 1. safety sensor integrity
        for sid in ("sensor_primary_supply_T", "sensor_buffer_T"):
            q = board.quality(sid)
            if q != "ok":
                out.faults.append({"code": "sensor_integrity", "signal": sid,
                                   "quality": q, "t_s": t_s})

        # 2. energy residual drift (operational vs. expected balance)
        residual = board.read("energy_residual_W")
        if residual is not None and abs(float(residual)) > 50_000.0:
            out.faults.append({"code": "energy_residual_drift",
                               "residual_W": round(float(residual), 1), "t_s": t_s})

        # 3. pump degradation signature: flow falling while load steady/high
        flow = board.read("primary_mass_flow_kg_s")
        load = board.read("gpu_load_fraction", 0.0)
        if flow is not None:
            self._flow_history.append(float(flow))
            if len(self._flow_history) > 6:
                self._flow_history.pop(0)
            if len(self._flow_history) == 6:
                early = sum(self._flow_history[:3]) / 3
                late = sum(self._flow_history[3:]) / 3
                if early > 1e-6 and late < early * 0.7 and float(load) > 0.5:
                    out.faults.append({"code": "primary_flow_degradation",
                                       "from_kg_s": round(early, 2),
                                       "to_kg_s": round(late, 2), "t_s": t_s})
                    out.requests.append(Request(
                        "aux_rejection_enabled", target=True, priority=8,
                        rationale="primary flow degraded ~30%: request aux rejection ON"))

        # 4. persistent large unmet demand
        unmet = board.read("unmet_demand_W", 0.0)
        if unmet is not None and float(unmet) > 50_000.0:
            out.faults.append({"code": "large_unmet_demand",
                               "unmet_W": round(float(unmet), 1), "t_s": t_s})
        return out
