"""Infrastructure agent -- owns the primary pump speed.

Goal: hold the rack coolant loop near a target temperature using the least
pumping energy. A PI controller adjusts flow from the measured temperature,
with a bounded adaptive gain and a protective full-flow override near limits.
"""
from __future__ import annotations

from ..control import AdaptiveGain, PIController
from .base import Agent, AgentOutput, Commit


class InfrastructureAgent(Agent):
    name = "infrastructure"
    owns = ("primary_pump_speed",)

    FULL_FLOW_AT_C = 39.0
    MIN_TRIM_SPEED = 0.7
    SETPOINT_MARGIN_C = 3.0

    def __init__(self, forecaster=None):
        super().__init__(forecaster)
        # Higher pump speed lowers supply temperature (reverse-acting loop).
        self.pi = PIController(kp=0.05, ki=0.0008, out_min=self.MIN_TRIM_SPEED,
                               out_max=1.0, direction=-1.0)
        self.adapt = AdaptiveGain(gain=0.05, lo=0.02, hi=0.12)

    def reset(self):
        super().reset()
        self.pi.reset()
        self.adapt = AdaptiveGain(gain=0.05, lo=0.02, hi=0.12)

    def act(self, board, t_s):
        out = AgentOutput()
        sig = board.signal("sensor_primary_supply_T")
        if sig is None or sig.quality != "ok":
            self.pi.reset()
            out.commits.append(Commit("primary_pump_speed", 1.0,
                "primary temp untrusted: full flow 1.00 (safety first)"))
            return out

        primary_C = float(sig.value)
        band = float(board.read("target::primary_supply_band_C", 40.0) or 40.0)
        setpoint_C = min(self.FULL_FLOW_AT_C, band - self.SETPOINT_MARGIN_C)

        if primary_C >= self.FULL_FLOW_AT_C:
            self.pi.last_output = 1.0
            out.commits.append(Commit("primary_pump_speed", 1.0,
                f"primary {primary_C:.1f}C >= {self.FULL_FLOW_AT_C}C: full flow (safety bias)"))
            return out

        error = setpoint_C - primary_C
        self.pi.kp = self.adapt.observe(error)
        speed = self.pi.update(setpoint_C, primary_C, dt_s=600.0)
        reason = (f"PI hold ~{setpoint_C:.0f}C (now {primary_C:.1f}C, err {error:+.1f}) "
                  f"-> flow {speed:.2f} [kp={self.pi.kp:.3f}]")

        # Forecast-assisted safety check before significant trimming in mode C.
        if self.forecaster is not None and speed < 0.85:
            probe = self.forecaster({"primary_pump_speed": speed}, horizon=4)
            self.compute_cost += probe.get("steps", 0)
            if probe.get("peak_primary_supply_C", 0.0) >= band:
                speed = max(speed, 0.9)
                self.pi.last_output = speed
                reason = f"forecast overheat at low flow: hold {speed:.2f}"

        out.commits.append(Commit("primary_pump_speed", round(speed, 3), reason))
        return out
