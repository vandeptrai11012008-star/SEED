"""Actuator registry and single-writer ownership table.

Each actuator has exactly one owner agent that may *write* it. Any other agent
must send a ``request`` event; the owner (or the arbiter on its behalf) decides.
This module just holds the ownership table and converts a committed set of
actuator values into an :class:`~thermalloop.ops.engine.Action`.

Real-device adapters are intentionally absent: the only "device" is the
simulation. A ``real_device_enabled`` flag exists and defaults to ``False`` to
make explicit that nothing here touches hardware.
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import Action

# actuator id -> owning agent name. Single writer each.
OWNERSHIP: dict[str, str] = {
    "gpu_load_fraction": "workload",
    "primary_pump_speed": "infrastructure",
    "secondary_pump_speed": "heat_recovery",
    "buffer_charge_enabled": "heat_recovery",
    "secondary_supply_setpoint_C": "heat_recovery",
    "heat_pump_enabled": "power_cooling",
    "aux_rejection_enabled": "power_cooling",
    "aux_rejection_level": "power_cooling",
}

# physical / allowed range per actuator (used by the safety clamp too).
RANGES: dict[str, tuple[float, float]] = {
    "gpu_load_fraction": (0.0, 1.0),
    "primary_pump_speed": (0.2, 1.0),     # never fully stop primary while IT hot
    "secondary_pump_speed": (0.0, 1.0),
    "secondary_supply_setpoint_C": (35.0, 70.0),
    "aux_rejection_level": (0.0, 1.0),
}

BOOL_ACTUATORS = {"buffer_charge_enabled", "heat_pump_enabled", "aux_rejection_enabled"}


@dataclass
class OwnershipError(Exception):
    actuator: str
    claimed_by: str
    owner: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (f"agent {self.claimed_by!r} may not write actuator "
                f"{self.actuator!r}; owner is {self.owner!r}")


class ActuatorRegistry:
    def __init__(self, real_device_enabled: bool = False) -> None:
        self.real_device_enabled = real_device_enabled
        self.values: dict[str, float | bool] = {}

    def owner(self, actuator: str) -> str:
        return OWNERSHIP[actuator]

    def assert_writer(self, actuator: str, agent: str) -> None:
        owner = OWNERSHIP.get(actuator)
        if owner is None:
            raise KeyError(f"unknown actuator {actuator!r}")
        if owner != agent:
            raise OwnershipError(actuator=actuator, claimed_by=agent, owner=owner)

    def commit(self, actuator: str, value: float | bool, agent: str) -> None:
        """Record a committed value after verifying single-writer ownership."""
        self.assert_writer(actuator, agent)
        self.values[actuator] = value

    def to_action(self) -> Action:
        v = self.values
        return Action(
            gpu_load_fraction=v.get("gpu_load_fraction"),
            heat_pump_enabled=v.get("heat_pump_enabled"),
            aux_rejection_enabled=v.get("aux_rejection_enabled"),
            primary_pump_speed=v.get("primary_pump_speed"),
            secondary_pump_speed=v.get("secondary_pump_speed"),
            buffer_charge_enabled=v.get("buffer_charge_enabled"),
            secondary_supply_setpoint_C=v.get("secondary_supply_setpoint_C"),
            aux_rejection_level=v.get("aux_rejection_level"),
        )
