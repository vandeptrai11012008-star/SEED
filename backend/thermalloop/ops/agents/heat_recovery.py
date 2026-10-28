"""Heat Recovery agent -- owns secondary pump speed and buffer charging.

Goal: maximise useful heat delivered to the zones and store surplus in the
buffer for later, without overfilling it. It runs the secondary pump to meet
current demand and charges the buffer when there is surplus recovered heat and
the buffer has headroom. It honours comfort requests (full flow) relayed by the
arbiter.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Commit


class HeatRecoveryAgent(Agent):
    name = "heat_recovery"
    owns = ("secondary_pump_speed", "buffer_charge_enabled",
            "secondary_supply_setpoint_C")

    def act(self, board, t_s):
        out = AgentOutput()
        unmet = float(board.read("unmet_demand_W", 0.0) or 0.0)
        liquid = float(board.read("liquid_captured_W", 0.0) or 0.0)
        delivered = float(board.read("delivered_total_W", 0.0) or 0.0)
        buffer_C = board.read("buffer_temp_C")

        # Track the coordinator's secondary supply target (heat quality knob).
        sec_sp = board.read("target::secondary_supply_C")
        if sec_sp is not None:
            regime = board.read("target::regime", "?")
            out.commits.append(Commit(
                "secondary_supply_setpoint_C", round(float(sec_sp), 2),
                f"track coordinator {regime} target {float(sec_sp):.0f}C"))

        # Secondary flow: full when demand is unmet, else proportional-ish.
        if unmet > 2_000.0:
            speed, reason = 1.0, f"unmet demand {unmet/1000:.0f}kW: full secondary flow"
        elif delivered > 1_000.0:
            speed, reason = 0.8, f"serving {delivered/1000:.0f}kW demand: flow 0.80"
        else:
            speed, reason = 0.5, "low demand: trim secondary flow 0.50"
        out.commits.append(Commit("secondary_pump_speed", round(speed, 3), reason))

        # Buffer charging: enable when there is recovery surplus and headroom.
        surplus = liquid - delivered
        headroom = buffer_C is None or float(buffer_C) < 70.0
        charge = surplus > 30_000.0 and headroom
        creason = (f"surplus {surplus/1000:.0f}kW and buffer<70C: charge ON"
                   if charge else
                   ("buffer near full: charge OFF" if not headroom
                    else "insufficient surplus: charge OFF"))
        out.commits.append(Commit("buffer_charge_enabled", charge, creason))
        return out
