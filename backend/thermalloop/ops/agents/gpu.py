"""GPU agent -- protects the racks; does NOT own the load setpoint.

It watches rack-side temperatures (approximated here by the primary supply
temperature, which is the rack coolant feed) and, if they climb toward the
limit, sends a *request* to the Workload agent to shed load. Single-writer:
the GPU agent cannot set the load itself; it can only ask.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Request


class GPUAgent(Agent):
    name = "gpu"
    owns = ()

    def act(self, board, t_s):
        out = AgentOutput()
        sig = board.signal("sensor_primary_supply_T")
        if sig is None or sig.quality != "ok":
            out.requests.append(Request(
                "gpu_load_fraction", target=0.7, priority=5,
                rationale="rack coolant temp unavailable: request conservative 0.70 load"))
            return out
        coolant_C = float(sig.value)
        # Only escalate a shed request as the coolant feed genuinely nears the
        # 45C trip; below 44C the thermal margin is fine for full compute.
        if coolant_C >= 44.5:
            out.requests.append(Request(
                "gpu_load_fraction", target=0.6, priority=9,
                rationale=f"coolant {coolant_C:.1f}C>=44.5C near trip: shed to 0.60"))
        elif coolant_C >= 44.0:
            out.requests.append(Request(
                "gpu_load_fraction", target=0.8, priority=6,
                rationale=f"coolant {coolant_C:.1f}C>=44C: cap load 0.80"))
        return out
