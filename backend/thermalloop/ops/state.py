"""Shared blackboard with timestamped values and data-quality flags.

Agents never read the engine directly; they read this blackboard. Each signal
carries the simulation time it was written and a quality flag so an agent can
tell a fresh reading from a stale one, a dropout, or a value it should not
trust. This is what lets the safety and fault logic react to sensor loss
without pretending the data is good.

Quality values:
  ok       - fresh, trusted
  stale    - older than ``stale_after_s`` (not refreshed recently)
  suspect  - present but flagged (e.g. drifting/stuck sensor)
  missing  - no value (dropout / NaN)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class Signal:
    key: str
    value: Any
    t_s: float
    quality: str = "ok"

    def age_s(self, now_s: float) -> float:
        return max(0.0, now_s - self.t_s)


class Blackboard:
    def __init__(self, stale_after_s: float = 1800.0) -> None:
        self._signals: dict[str, Signal] = {}
        self.stale_after_s = stale_after_s
        self.now_s = 0.0

    def set_time(self, t_s: float) -> None:
        self.now_s = t_s

    def write(self, key: str, value: Any, *, t_s: float, quality: str = "ok") -> None:
        if isinstance(value, float) and math.isnan(value):
            quality = "missing"
        self._signals[key] = Signal(key=key, value=value, t_s=t_s, quality=quality)

    def read(self, key: str, default: Any = None) -> Any:
        sig = self._signals.get(key)
        if sig is None:
            return default
        return sig.value

    def signal(self, key: str) -> Signal | None:
        sig = self._signals.get(key)
        if sig is None:
            return None
        # promote fresh->stale lazily based on current time
        if sig.quality == "ok" and sig.age_s(self.now_s) > self.stale_after_s:
            return Signal(sig.key, sig.value, sig.t_s, "stale")
        return sig

    def quality(self, key: str) -> str:
        sig = self.signal(key)
        return "missing" if sig is None else sig.quality

    def is_trustworthy(self, key: str) -> bool:
        return self.quality(key) == "ok"

    def ingest_record(self, record: Any, t_s: float) -> None:
        """Publish the useful fields of a StepRecord to the blackboard.

        Sensor readings keep the quality flag the engine attached (so injected
        sensor faults propagate); derived aggregates are written as ``ok``.
        """
        for sid, reading in record.sensor_states.items():
            q = str(reading.get("quality", "ok"))
            self.write(sid, reading.get("value"), t_s=t_s, quality=q)
        for key in ("it_power_W", "liquid_captured_W", "hx_transfer_W",
                    "heat_pump_thermal_W", "heat_pump_elec_W", "pump_power_W",
                    "delivered_total_W", "unmet_demand_W", "primary_unrejected_W",
                    "aux_rejected_W", "buffer_temp_C", "soil_temp_C",
                    "primary_mass_flow_kg_s", "secondary_mass_flow_kg_s",
                    "gpu_load_fraction", "ambient_C", "energy_residual_W",
                    "primary_supply_C", "secondary_supply_C"):
            self.write(key, getattr(record, key), t_s=t_s, quality="ok")
        for zone_id, temp in record.zone_temperature_C.items():
            self.write(f"zone_temp_C::{zone_id}", temp, t_s=t_s, quality="ok")
        for zone_id, unmet in record.zone_unmet_W.items():
            self.write(f"zone_unmet_W::{zone_id}", unmet, t_s=t_s, quality="ok")

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            k: {"value": s.value, "t_s": s.t_s, "quality": self.quality(k),
                "age_s": s.age_s(self.now_s)}
            for k, s in self._signals.items()
        }
