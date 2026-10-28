"""Power & Cooling agent -- owns heat-pump enable and continuous aux rejection.

Goal: reject only the heat that cannot be used, and only as much as needed. It
now modulates auxiliary rejection *continuously* (0..1) proportional to how far
the primary loop sits above the coordinator's band and how much surplus heat is
piling up -- so it rejects gently when slightly warm and hard when hot, instead
of slamming the dry cooler fully on/off. The heat pump stays on while there is
useful heat demand to upgrade.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Commit


class PowerCoolingAgent(Agent):
    name = "power_cooling"
    owns = ("heat_pump_enabled", "aux_rejection_enabled", "aux_rejection_level")

    def act(self, board, t_s):
        out = AgentOutput()
        unrejected = float(board.read("primary_unrejected_W", 0.0) or 0.0)
        delivered = float(board.read("delivered_total_W", 0.0) or 0.0)
        unmet = float(board.read("unmet_demand_W", 0.0) or 0.0)
        primary_sig = board.signal("sensor_primary_supply_T")
        primary_C = (float(primary_sig.value)
                     if primary_sig and primary_sig.quality == "ok" else None)
        band = float(board.read("target::primary_supply_band_C", 40.0) or 40.0)

        # Continuous rejection level: driven by BOTH the surplus heat and the
        # temperature margin to the band. Either signal alone can call for it,
        # and both ramp to FULL well before the loop reaches the band, so
        # rejection leads the temperature rise rather than lagging it.
        level_from_surplus = min(1.0, max(0.0, (unrejected - 5_000.0) / 25_000.0))
        level_from_temp = 0.0
        if primary_C is not None:
            # full rejection by the time we are 2C under the band, not at it
            level_from_temp = min(1.0, max(0.0, (primary_C - (band - 8.0)) / 6.0))
        level = max(level_from_surplus, level_from_temp)
        level = round(level, 3)

        out.commits.append(Commit("aux_rejection_level", level,
            f"reject {level:.0%} (surplus {unrejected/1000:.0f}kW, "
            f"primary {primary_C:.1f}C vs band {band:.0f}C)"
            if primary_C is not None else
            f"reject {level:.0%} (surplus {unrejected/1000:.0f}kW, primary untrusted)"))
        # Keep the boolean consistent for any consumer that reads it.
        out.commits.append(Commit("aux_rejection_enabled", level > 1e-6,
            f"aux {'ON' if level > 1e-6 else 'OFF'} (level {level:.0%})"))

        # Heat pump: on when there is useful demand (delivered or unmet heat).
        hp_on = (delivered + unmet) > 5_000.0
        hp_reason = (f"heat demand {(delivered+unmet)/1000:.0f}kW>5kW: heat pump ON"
                     if hp_on else "negligible heat demand: heat pump OFF")
        out.commits.append(Commit("heat_pump_enabled", hp_on, hp_reason))
        return out
