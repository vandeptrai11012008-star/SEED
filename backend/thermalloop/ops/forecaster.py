"""Forecasting model used by mode-C agents (separate from the operational one).

A forecaster takes a candidate action dict and a horizon, forks the *current*
operational engine state, and rolls it forward applying the candidate action
every step. It returns summary metrics of that branch -- peak primary supply
temperature, delivered heat, pump energy -- which agents use as evidence.

Key honesty point: the branch uses the engine's own driver assumptions, NOT
the real disturbance the world will impose. So when a scenario like
``forecast_mismatch`` makes reality diverge from the driver, the forecast can
be *wrong*, and the evaluation will show whether mode C still helped. Nothing
here manufactures a confidence number.
"""
from __future__ import annotations

from typing import Any, Callable

from .engine import Action, SteppedEngine


def make_forecaster(
    engine: SteppedEngine,
    drivers: dict[str, Any] | None,
    start_hour: float,
    timestep_s: int,
) -> Callable[..., dict[str, Any]]:
    """Return a ``forecaster(candidate: dict, horizon: int) -> metrics``.

    The returned closure forks the live engine at call time, so it always
    forecasts from the plant's current state.
    """

    def forecaster(candidate: dict[str, Any] | None = None, horizon: int = 6) -> dict[str, Any]:
        candidate = candidate or {}
        branch: SteppedEngine = engine.fork()
        action = Action(
            gpu_load_fraction=candidate.get("gpu_load_fraction"),
            heat_pump_enabled=candidate.get("heat_pump_enabled"),
            aux_rejection_enabled=candidate.get("aux_rejection_enabled"),
            primary_pump_speed=candidate.get("primary_pump_speed"),
            secondary_pump_speed=candidate.get("secondary_pump_speed"),
            buffer_charge_enabled=candidate.get("buffer_charge_enabled"),
            secondary_supply_setpoint_C=candidate.get("secondary_supply_setpoint_C"),
            aux_rejection_level=candidate.get("aux_rejection_level"),
        )
        dt = branch.get_state().dt_s
        peak_primary = -1e9
        delivered_J = 0.0
        pump_J = 0.0
        unmet_J = 0.0
        for _ in range(max(1, horizon)):
            _, rec = branch.step(action, dt)
            peak_primary = max(peak_primary, rec.primary_supply_C)
            delivered_J += rec.delivered_total_W * dt
            pump_J += rec.pump_power_W * dt
            unmet_J += rec.unmet_demand_W * dt
        return {
            "steps": max(1, horizon),
            "peak_primary_supply_C": round(peak_primary, 3),
            "delivered_kWh": round(delivered_J / 3.6e6, 4),
            "pump_kWh": round(pump_J / 3.6e6, 4),
            "unmet_kWh": round(unmet_J / 3.6e6, 4),
        }

    return forecaster
