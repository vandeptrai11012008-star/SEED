"""Workload agent -- owns the GPU load setpoint.

Goal: run as much compute as possible (serve jobs on time) without pushing the
cooling loop into trouble. It observes primary-loop supply temperature and the
current diurnal driver, and sets the GPU load fraction. In mode C it uses the
forecaster to check whether a higher load would overheat the loop a few steps
ahead, and backs off pre-emptively instead of waiting for the safety trip.
"""
from __future__ import annotations

from .base import Agent, AgentOutput, Commit, Proposal


class WorkloadAgent(Agent):
    name = "workload"
    owns = ("gpu_load_fraction",)

    def act(self, board, t_s):
        out = AgentOutput()
        driver = board.read("gpu_load_fraction", 0.55)
        target = float(driver)

        primary_sig = board.signal("sensor_primary_supply_T")
        primary_trusted = primary_sig is not None and primary_sig.quality == "ok"
        primary_C = float(primary_sig.value) if primary_trusted else None
        reason = f"follow diurnal driver target={target:.2f}"

        # Honour the coordinator's global load ceiling (top-down objective).
        ceiling = board.read("target::gpu_load_ceiling")
        if ceiling is not None and target > float(ceiling):
            target = float(ceiling)
            regime = board.read("target::regime", "?")
            reason = f"coordinator {regime} regime: hold load ceiling {target:.2f}"

        # Reactive back-off (modes B and C): trim proportionally only as the
        # loop nears the 45C trip, so we use the available thermal margin for
        # real work instead of shedding early. Full load up to 43C, linearly
        # down to a 0.55 floor at the 45C trip.
        if primary_C is not None and primary_C > 43.0:
            shed = max(0.55, 1.0 - 0.45 * (primary_C - 43.0) / 2.0)
            if shed < target:
                target = shed
                reason = f"primary {primary_C:.1f}C nearing 45C trip: trim load to {target:.2f}"
        elif not primary_trusted:
            target = min(target, 0.75)
            reason = "primary temp untrusted: conservative load 0.75"

        # Validated (mode C only): forecast where the CURRENT plan is heading and
        # pre-trim BEFORE the loop is hot. This is the only behavioural
        # difference from mode B, so it is also where C either earns or wastes
        # its compute cost.
        evidence = None
        if self.forecaster is not None and primary_trusted:
            probe = self.forecaster({"gpu_load_fraction": target}, horizon=6)
            self.compute_cost += probe.get("steps", 0)
            peak = probe.get("peak_primary_supply_C", 0.0)
            evidence = {"probe_peak_primary_C": peak, "probe_action_load": round(target, 3)}
            # If the operational-model forecast says the current plan heads
            # toward the 45C trip, pre-trim before the loop is hot. This helps
            # only when the forecasting model reflects reality; under an
            # UNMODELLED fault (e.g. a failing dry cooler the forecaster does
            # not know about) the forecast stays benign and C behaves like B --
            # which the comparison honestly reports rather than hides.
            if peak >= 43.0 and target > 0.6:
                forecast_target = max(0.6, 0.85 - 0.15 * (peak - 43.0))
                if forecast_target < target:
                    reason = (f"forecast peak {peak:.1f}C nearing 45C trip "
                              f"(now {primary_C:.1f}C): pre-trim load to {forecast_target:.2f}")
                    target = forecast_target

        out.commits.append(Commit("gpu_load_fraction", round(target, 4), reason))
        out.proposals.append(Proposal(
            topic="workload_plan",
            detail={"gpu_load_fraction": round(target, 4)},
            rationale=reason, evidence=evidence))
        return out
