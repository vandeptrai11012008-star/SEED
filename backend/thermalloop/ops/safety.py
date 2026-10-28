"""Independent constraint-safety layer.

This sits between the agents' committed actions and the plant. It is deliberately
simple, deterministic and *fast*: emergency reactions here never run a forecast
or call an LLM. Agents cannot change these limits or grant themselves authority
-- the limits live here, not in any agent.

It does two jobs every step:

1. **Validate/clamp** the proposed action against hard limits (actuator ranges,
   pump floors, rate-of-change limits). Out-of-range values are clamped and a
   violation is recorded.

2. **Emergency overrides** based on the latest *trusted* blackboard readings:
   over-temperature of the primary loop or a zone forces auxiliary rejection on
   and sheds GPU load; loss/suspect of a safety-critical sensor forces a
   conservative fallback (aux on, heat pump off-lift limited). These fire from
   measured state only, independent of any agent decision.

The layer reports, for every step, the list of (limit, action-taken) pairs so
the UI can show exactly why an action was changed -- structured rationale, not
a plausible-sounding story.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .actuators import BOOL_ACTUATORS, RANGES
from .engine import Action
from .state import Blackboard


@dataclass
class Limits:
    primary_supply_max_C: float = 45.0        # trip auxiliary rejection above this
    primary_supply_crit_C: float = 50.0       # shed GPU load above this
    zone_overtemp_margin_C: float = 2.0       # above setpoint -> stop heating zone
    buffer_max_C: float = 80.0
    gpu_shed_fraction: float = 0.6            # forced ceiling during emergency
    gpu_rate_limit_per_step: float = 0.25     # max |delta| per step on gpu load
    pump_rate_limit_per_step: float = 0.35    # max |delta| per step on pump speed
    critical_sensors: tuple[str, ...] = (
        "sensor_primary_supply_T", "sensor_buffer_T",
    )


@dataclass
class SafetyEvent:
    kind: str                 # clamp | override | fault
    actuator: str
    reason: str
    old: Any = None
    new: Any = None


@dataclass
class SafetyResult:
    action: Action
    events: list[SafetyEvent] = field(default_factory=list)
    emergency: bool = False

    def as_dicts(self) -> list[dict[str, Any]]:
        return [vars(e) for e in self.events]


class SafetyLayer:
    """Owns the limits. Nothing external mutates them."""

    # Effective value the plant uses when a continuous actuator is left None.
    # gpu None -> diurnal driver (treated as full demand for rate anchoring);
    # pumps None -> rated flow (1.0). Used to keep the rate limiter consistent.
    _DEFAULT_EFFECTIVE = {
        "gpu_load_fraction": 1.0,
        "primary_pump_speed": 1.0,
        "secondary_pump_speed": 1.0,
    }

    def __init__(self, limits: Limits | None = None) -> None:
        self._limits = limits or Limits()
        self._last: dict[str, float] = {}

    @property
    def limits(self) -> Limits:
        return self._limits

    def _clamp_range(self, name: str, value: float, events: list[SafetyEvent]) -> float:
        lo, hi = RANGES[name]
        if value < lo or value > hi:
            new = max(lo, min(hi, value))
            events.append(SafetyEvent("clamp", name, f"outside [{lo},{hi}]", value, new))
            return new
        return value

    def _rate_limit(self, name: str, value: float, limit: float, events: list[SafetyEvent]) -> float:
        prev = self._last.get(name)
        if prev is None:
            return value
        delta = value - prev
        if abs(delta) > limit:
            new = prev + (limit if delta > 0 else -limit)
            events.append(SafetyEvent("clamp", name, f"rate>|{limit}|/step", value, new))
            return new
        return value

    def validate(self, action: Action, board: Blackboard) -> SafetyResult:
        """Return a safe action plus the list of interventions taken."""
        events: list[SafetyEvent] = []
        L = self._limits
        # work on a copy
        a = Action(
            gpu_load_fraction=action.gpu_load_fraction,
            heat_pump_enabled=action.heat_pump_enabled,
            aux_rejection_enabled=action.aux_rejection_enabled,
            primary_pump_speed=action.primary_pump_speed,
            secondary_pump_speed=action.secondary_pump_speed,
            buffer_charge_enabled=action.buffer_charge_enabled,
            dry_cooler_available=action.dry_cooler_available,
            secondary_supply_setpoint_C=action.secondary_supply_setpoint_C,
            aux_rejection_level=action.aux_rejection_level,
            sensor_faults=dict(action.sensor_faults),
            pump_degradation=dict(action.pump_degradation),
        )

        # 1. range + rate clamps on continuous actuators
        if a.gpu_load_fraction is not None:
            a.gpu_load_fraction = self._clamp_range("gpu_load_fraction", a.gpu_load_fraction, events)
            a.gpu_load_fraction = self._rate_limit("gpu_load_fraction", a.gpu_load_fraction, L.gpu_rate_limit_per_step, events)
        if a.primary_pump_speed is not None:
            a.primary_pump_speed = self._clamp_range("primary_pump_speed", a.primary_pump_speed, events)
            a.primary_pump_speed = self._rate_limit("primary_pump_speed", a.primary_pump_speed, L.pump_rate_limit_per_step, events)
        if a.secondary_pump_speed is not None:
            a.secondary_pump_speed = self._clamp_range("secondary_pump_speed", a.secondary_pump_speed, events)
            a.secondary_pump_speed = self._rate_limit("secondary_pump_speed", a.secondary_pump_speed, L.pump_rate_limit_per_step, events)
        if a.secondary_supply_setpoint_C is not None:
            a.secondary_supply_setpoint_C = self._clamp_range(
                "secondary_supply_setpoint_C", a.secondary_supply_setpoint_C, events)
        if a.aux_rejection_level is not None:
            a.aux_rejection_level = self._clamp_range(
                "aux_rejection_level", a.aux_rejection_level, events)

        # 2. emergency overrides from trusted measured state only
        emergency = False
        primary_sig = board.signal("sensor_primary_supply_T")
        primary_trusted = primary_sig is not None and primary_sig.quality == "ok"
        primary_C = float(primary_sig.value) if primary_trusted else None

        # 2a. critical sensor loss/suspect -> conservative fallback
        for sid in L.critical_sensors:
            q = board.quality(sid)
            if q in ("missing", "stale", "suspect"):
                events.append(SafetyEvent("fault", sid, f"critical sensor quality={q}"))
                a.aux_rejection_enabled = True          # reject rather than risk overheat
                # Never stop primary while a safety sensor is untrusted. Treat a
                # None command as "plant default = full flow" (1.0) explicitly,
                # so a legitimate commanded 0.0 is not silently confused with None.
                current_primary = 1.0 if a.primary_pump_speed is None else a.primary_pump_speed
                a.primary_pump_speed = max(current_primary, 0.8)
                emergency = True

        # 2b. over-temperature protection (only when we trust the reading)
        if primary_C is not None:
            if primary_C >= L.primary_supply_max_C:
                if a.aux_rejection_enabled is not True:
                    events.append(SafetyEvent("override", "aux_rejection_enabled",
                        f"primary {primary_C:.1f}C >= {L.primary_supply_max_C}C", a.aux_rejection_enabled, True))
                a.aux_rejection_enabled = True
                emergency = True
            if primary_C >= L.primary_supply_crit_C:
                ceiling = L.gpu_shed_fraction
                cur = a.gpu_load_fraction if a.gpu_load_fraction is not None else 1.0
                if cur > ceiling:
                    events.append(SafetyEvent("override", "gpu_load_fraction",
                        f"primary {primary_C:.1f}C >= crit {L.primary_supply_crit_C}C: shed", cur, ceiling))
                    a.gpu_load_fraction = ceiling

        # 2c. buffer over-temperature -> stop charging
        buffer_sig = board.signal("sensor_buffer_T")
        if buffer_sig is not None and buffer_sig.quality == "ok":
            if float(buffer_sig.value) >= L.buffer_max_C:
                if a.buffer_charge_enabled is not False:
                    events.append(SafetyEvent("override", "buffer_charge_enabled",
                        f"buffer {buffer_sig.value:.1f}C >= {L.buffer_max_C}C", a.buffer_charge_enabled, False))
                a.buffer_charge_enabled = False

        # Remember the EFFECTIVE setpoint applied this step for the next step's
        # rate limiter. When a field is None the plant uses its default, so we
        # anchor to that default rather than leaving a stale value behind. This
        # keeps the limiter consistent across modes A/B/C (A always sets fields;
        # B/C may leave them None) and prevents a gap from creating a stale
        # anchor that wrongly throttles or permits the next move.
        self._last["gpu_load_fraction"] = (
            a.gpu_load_fraction if a.gpu_load_fraction is not None
            else self._DEFAULT_EFFECTIVE["gpu_load_fraction"])
        self._last["primary_pump_speed"] = (
            a.primary_pump_speed if a.primary_pump_speed is not None
            else self._DEFAULT_EFFECTIVE["primary_pump_speed"])
        self._last["secondary_pump_speed"] = (
            a.secondary_pump_speed if a.secondary_pump_speed is not None
            else self._DEFAULT_EFFECTIVE["secondary_pump_speed"])

        return SafetyResult(action=a, events=events, emergency=emergency)
