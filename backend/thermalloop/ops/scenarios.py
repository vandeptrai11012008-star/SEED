"""Runtime scenario and fault injectors.

A scenario is a function of the current step index that returns a partial
:class:`~thermalloop.ops.engine.Action` describing an *external disturbance*
(what the world does to the plant), plus optional runtime events (agent comms
loss). These are injected after the agents act, so the agents must cope with
them rather than being told in advance.

Covered (all mandatory in the brief):
  ai_load_spike        - sudden jump in GPU demand
  pump_degradation     - primary pump loses capacity over time
  sensor_drift         - a sensor reads increasingly wrong but present
  sensor_loss          - a sensor drops out entirely
  server_failure       - a block of racks trips (load drop)
  heating_demand_change- outdoor temperature step (more/less heat needed)
  forecast_mismatch    - driver differs from what mode-C branches assume
  agent_comms_loss     - a named agent goes silent for a window
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .engine import Action


@dataclass
class Disturbance:
    """What the scenario imposes at a given step."""
    action: Action = field(default_factory=Action)
    offline_agents: tuple[str, ...] = ()
    label: str = ""


Scenario = Callable[[int], Disturbance]


def none_scenario() -> Scenario:
    def f(step: int) -> Disturbance:
        return Disturbance()
    return f


def ai_load_spike(start: int = 10, end: int = 22, level: float = 1.0) -> Scenario:
    def f(step: int) -> Disturbance:
        if start <= step < end:
            return Disturbance(Action(gpu_load_fraction=level),
                               label=f"AI load spike -> {level:.0%}")
        return Disturbance()
    return f


def pump_degradation(start: int = 8, floor: float = 0.45, ramp: int = 10) -> Scenario:
    def f(step: int) -> Disturbance:
        if step < start:
            return Disturbance()
        frac = max(floor, 1.0 - (step - start) / max(ramp, 1) * (1.0 - floor))
        return Disturbance(Action(pump_degradation={"primary": frac}),
                           label=f"primary pump degraded to {frac:.0%}")
    return f


def sensor_drift(sensor: str = "sensor_primary_supply_T",
                 start: int = 6, rate_C: float = 1.0) -> Scenario:
    def f(step: int) -> Disturbance:
        if step < start:
            return Disturbance()
        offset = (step - start + 1) * rate_C
        return Disturbance(Action(sensor_faults={sensor: {"mode": "offset", "offset_C": offset}}),
                           label=f"{sensor} drifting +{offset:.1f}C")
    return f


def sensor_loss(sensor: str = "sensor_primary_supply_T", start: int = 12, end: int = 24) -> Scenario:
    def f(step: int) -> Disturbance:
        if start <= step < end:
            return Disturbance(Action(sensor_faults={sensor: {"mode": "dropout"}}),
                               label=f"{sensor} dropout")
        return Disturbance()
    return f


def server_failure(start: int = 14, end: int = 30, surviving_load: float = 0.5) -> Scenario:
    def f(step: int) -> Disturbance:
        if start <= step < end:
            return Disturbance(Action(gpu_load_fraction=surviving_load),
                               label=f"server block failure -> load capped {surviving_load:.0%}")
        return Disturbance()
    return f


def heating_demand_change(start: int = 6, ambient_hint: str = "colder") -> Scenario:
    # Modelled as a cold snap that raises zone/greenhouse demand. The engine
    # ambient is driver-level; here we approximate by forcing extra GPU heat is
    # NOT appropriate, so we instead flag demand via sensor-free label and rely
    # on the mode harness to set a colder ambient_mean_C driver. This injector
    # therefore only annotates the timeline.
    def f(step: int) -> Disturbance:
        if step >= start:
            return Disturbance(label=f"heating demand change ({ambient_hint})")
        return Disturbance()
    return f


def forecast_mismatch(start: int = 8, actual: float = 0.95) -> Scenario:
    """World runs hotter than mode-C branches expect (branches use the driver).

    The forecaster assumes the diurnal driver; here the real load is forced
    higher, so mode C's pre-trims are based on a wrong assumption. This is the
    honest test of whether the forecast actually helps.
    """
    def f(step: int) -> Disturbance:
        if step >= start:
            return Disturbance(Action(gpu_load_fraction=actual),
                               label=f"forecast mismatch: real load {actual:.0%}")
        return Disturbance()
    return f


def agent_comms_loss(agent: str = "infrastructure", start: int = 10, end: int = 20) -> Scenario:
    def f(step: int) -> Disturbance:
        if start <= step < end:
            return Disturbance(offline_agents=(agent,),
                               label=f"{agent} comms loss")
        return Disturbance()
    return f


def cooling_derate(start: int = 8, end: int = 30, available: float = 0.25,
                   load: float = 1.0) -> Scenario:
    """Heat-wave: dry cooler loses most capacity while load is maxed.

    This is the scenario where foresight actually matters: with rejection
    crippled and load high, a reactive controller lets the loop climb into the
    safety band, while a forecaster can pre-trim load. It is also the honest
    stress test -- if mode C still cannot help here, the comparison will say so.
    """
    def f(step: int) -> Disturbance:
        if start <= step < end:
            return Disturbance(
                Action(dry_cooler_available=available, gpu_load_fraction=load),
                label=f"cooling derate to {available:.0%}, load {load:.0%}")
        return Disturbance()
    return f


SCENARIOS: dict[str, Scenario] = {
    "none": none_scenario(),
    "ai_load_spike": ai_load_spike(),
    "pump_degradation": pump_degradation(),
    "sensor_drift": sensor_drift(),
    "sensor_loss": sensor_loss(),
    "server_failure": server_failure(),
    "heating_demand_change": heating_demand_change(),
    "forecast_mismatch": forecast_mismatch(),
    "agent_comms_loss": agent_comms_loss(),
    "cooling_derate": cooling_derate(),
}

SCENARIO_LABELS = {
    "none": "No disturbance",
    "ai_load_spike": "AI workload spike",
    "pump_degradation": "Primary pump degradation",
    "sensor_drift": "Sensor drift",
    "sensor_loss": "Sensor loss / dropout",
    "server_failure": "Server block failure",
    "heating_demand_change": "Heating demand change",
    "forecast_mismatch": "Forecast mismatch",
    "agent_comms_loss": "Agent comms loss",
    "cooling_derate": "Cooling derate (heat wave)",
}
