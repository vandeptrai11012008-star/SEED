"""Building agent -- occupant comfort; owns no actuator.

It tracks zone temperatures against their setpoints and, when a zone is cold,
requests more heat delivery (effectively asking HeatRecovery to keep the
secondary pump running and buffer discharging). It raises a comfort concern as
a proposal with the measured shortfall so the UI can show it. It does not
fabricate a comfort "score"; it reports the temperature gap in kelvin.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Proposal, Request

COMFORT_ZONES = ("zone_robot_lab", "zone_seed_testing", "zone_seed_storage")


class BuildingAgent(Agent):
    name = "building"
    owns = ()

    def act(self, board, t_s):
        out = AgentOutput()
        worst_gap = 0.0
        worst_zone = None
        for zone in COMFORT_ZONES:
            temp = board.read(f"zone_temp_C::{zone}")
            unmet = board.read(f"zone_unmet_W::{zone}", 0.0)
            if temp is None:
                continue
            setpoint = {"zone_robot_lab": 22.0, "zone_seed_testing": 24.0,
                        "zone_seed_storage": 15.0}[zone]
            gap = setpoint - float(temp)
            if gap > worst_gap:
                worst_gap, worst_zone = gap, zone
            if gap > 0.5 or float(unmet) > 1000.0:
                out.proposals.append(Proposal(
                    topic="comfort",
                    detail={"zone": zone, "temp_C": round(float(temp), 2),
                            "setpoint_C": setpoint, "gap_K": round(gap, 2),
                            "unmet_W": round(float(unmet), 1)},
                    rationale=f"{zone} is {gap:.2f}K below setpoint"))
        if worst_zone is not None and worst_gap > 0.5:
            out.requests.append(Request(
                "secondary_pump_speed", target=1.0, priority=7,
                rationale=f"comfort shortfall {worst_gap:.2f}K in {worst_zone}: "
                          "request full secondary flow"))
        return out
