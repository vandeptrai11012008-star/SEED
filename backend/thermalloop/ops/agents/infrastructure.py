"""Infrastructure agent -- owns the primary pump speed.

Goal: hold the rack coolant loop at a target temperature using the least
pumping energy. It now runs a PI controller instead of coarse thresholds:
more flow when the loop runs above the coordinator's primary band, less flow
when it runs cool -- settling smoothly instead of chattering. An adaptive gain
nudges responsiveness based on tracking performance ("measure -> adjust").
"""
from __future__ import annotations

from ..control import AdaptiveGain, PIController
from .base import Agent, AgentOutput, Commit


class InfrastructureAgent(Agent):
    name = "infrastructure"
    owns = ("primary_pump_speed",)

    # Flow is biased HIGH for safety: the pump only trims below full flow when
    # the loop is comfortably cool, and ramps straight back to full as it warms.
    # Cooling safety always beats pump-energy saving -- a cut that risks an
    # overheat is never worth the few watts saved.
    TRIM_BELOW_C = 34.0      # only consider trimming when cooler than this
    FULL_FLOW_AT_C = 39.0    # at/above this, command full flow
    MIN_TRIM_SPEED = 0.7     # never trim below this (keeps real cooling margin)

    def __init__(self, forecaster=None):
        super().__init__(forecaster)
        self.adapt = AdaptiveGain(gain=0.05, lo=0.02, hi=0.12)

    def reset(self):
        super().reset()
        self.adapt = AdaptiveGain(gain=0.05, lo=0.02, hi=0.12)

    def act(self, board, t_s):
        out = AgentOutput()
        sig = board.signal("sensor_primary_supply_T")
        if sig is None or sig.quality != "ok":
            out.commits.append(Commit("primary_pump_speed", 1.0,
                "primary temp untrusted: full flow 1.00 (safety first)"))
            return out

        primary_C = float(sig.value)
        if primary_C >= self.FULL_FLOW_AT_C:
            speed, reason = 1.0, f"primary {primary_C:.1f}C warm: full flow"
        elif primary_C <= self.TRIM_BELOW_C:
            # Smoothly trim toward MIN_TRIM_SPEED the cooler we are, to save pump
            # energy -- but never below the safety floor.
            margin = (self.TRIM_BELOW_C - primary_C) / 10.0
            speed = max(self.MIN_TRIM_SPEED, 1.0 - margin)
            reason = f"primary {primary_C:.1f}C cool: trim flow {speed:.2f} to save pump"
        else:
            # Linear ramp between trim and full-flow thresholds.
            frac = (primary_C - self.TRIM_BELOW_C) / (self.FULL_FLOW_AT_C - self.TRIM_BELOW_C)
            speed = max(self.MIN_TRIM_SPEED, self.MIN_TRIM_SPEED + frac * (1.0 - self.MIN_TRIM_SPEED))
            reason = f"primary {primary_C:.1f}C mid-band: flow {speed:.2f}"

        out.commits.append(Commit("primary_pump_speed", round(speed, 3), reason))
        return out
