"""Research agent -- proposes experiments; never writes an actuator.

It periodically forms a hypothesis ("would raising the secondary setpoint
deliver more useful heat without overheating?"), and -- only when it has a
forecaster (mode C) -- runs candidate branches off the current snapshot on the
SAME inputs, compares them against constraints, and emits a proposal carrying
the *measured* branch metrics as evidence. It does not auto-apply anything and
attaches no fabricated confidence number: the evidence is the raw branch
outcome plus whether constraints held.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Proposal


class ResearchAgent(Agent):
    name = "research"
    owns = ()

    def __init__(self, forecaster=None, period_steps: int = 12):
        super().__init__(forecaster)
        self.period_steps = period_steps
        self._step = 0

    def reset(self):
        super().reset()
        self._step = 0

    def act(self, board, t_s):
        out = AgentOutput()
        self._step += 1
        if self.forecaster is None or self._step % self.period_steps != 0:
            return out

        baseline = self.forecaster({}, horizon=8)
        candidate = self.forecaster({"gpu_load_fraction": 0.9}, horizon=8)
        self.compute_cost += baseline.get("steps", 0) + candidate.get("steps", 0)

        peak = candidate.get("peak_primary_supply_C", 0.0)
        constraints_ok = peak < 45.0
        delta_heat = (candidate.get("delivered_kWh", 0.0)
                      - baseline.get("delivered_kWh", 0.0))
        out.proposals.append(Proposal(
            topic="experiment",
            detail={"hypothesis": "raise GPU load to 0.90 for more recoverable heat",
                    "constraints_ok": constraints_ok},
            rationale=("branch at load 0.90 keeps primary peak "
                       f"{peak:.1f}C and changes delivered heat by "
                       f"{delta_heat:+.2f} kWh over the horizon "
                       "(measured branch outcome, not auto-applied)"),
            evidence={"baseline": baseline, "candidate": candidate,
                      "delta_delivered_kWh": round(delta_heat, 3),
                      "constraints_ok": constraints_ok}))
        return out
