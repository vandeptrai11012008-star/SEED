"""Arbitration layer.

The arbiter resolves who gets to move each actuator this step. The public rules
are:

1. **Single writer.** Only the owning agent may *commit* an actuator value. A
   commit from a non-owner is rejected (and logged) -- this is enforced again
   by :class:`ActuatorRegistry`, but the arbiter refuses it first.
2. **Requests are advisory.** Non-owners send requests. For each actuator the
   arbiter picks the highest-priority request and, if it is stricter/safer than
   the owner's own commit, overrides the owner with it. "Safer" is defined per
   actuator (e.g. a lower GPU load, more rejection).
3. **Response deadline.** If an owner did not respond this step (comms loss /
   timeout), the arbiter applies a conservative fallback for that actuator and
   records a fault. Emergency safety still runs afterwards regardless.

The arbiter returns the resolved values plus a per-actuator decision record so
the UI can show the exact rule that fired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .actuators import BOOL_ACTUATORS, OWNERSHIP
from .agents.base import AgentOutput

# Conservative fallback used when an owner times out / loses comms.
FALLBACK: dict[str, Any] = {
    "gpu_load_fraction": 0.55,          # drop to base load
    "primary_pump_speed": 0.9,          # keep plenty of coolant flow
    "secondary_pump_speed": 0.8,
    "buffer_charge_enabled": False,     # don't risk overcharge unmanaged
    "secondary_supply_setpoint_C": 50.0,  # moderate, safe heat-quality target
    "heat_pump_enabled": True,
    "aux_rejection_enabled": True,      # safe default: reject surplus
    "aux_rejection_level": 1.0,         # full rejection headroom when unmanaged
}


def _request_is_safer(actuator: str, request_val: Any, owner_val: Any) -> bool:
    """Is the requested value the safer/stricter one for this actuator?"""
    if owner_val is None:
        return True
    if actuator == "gpu_load_fraction":
        return float(request_val) < float(owner_val)      # less load is safer
    if actuator == "secondary_pump_speed":
        return float(request_val) > float(owner_val)       # more flow serves comfort
    if actuator in BOOL_ACTUATORS:
        return bool(request_val) and not bool(owner_val)   # enabling rejection/pump safer
    return False


@dataclass
class Decision:
    actuator: str
    value: Any
    owner: str
    rule: str
    rationale: str


@dataclass
class ArbitrationResult:
    values: dict[str, Any] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    faults: list[dict[str, Any]] = field(default_factory=list)


class Arbiter:
    def resolve(
        self,
        outputs: dict[str, AgentOutput],
        alive: dict[str, bool],
        t_s: float,
    ) -> ArbitrationResult:
        result = ArbitrationResult()

        # Gather the owner commit for each actuator (single writer enforced).
        owner_commit: dict[str, tuple[Any, str]] = {}
        for agent_name, out in outputs.items():
            for commit in out.commits:
                owner = OWNERSHIP.get(commit.actuator)
                if owner != agent_name:
                    result.faults.append({
                        "code": "ownership_violation", "actuator": commit.actuator,
                        "by": agent_name, "owner": owner, "t_s": t_s})
                    continue
                owner_commit[commit.actuator] = (commit.value, commit.rationale)

        # Collect best (highest-priority) request per actuator from non-owners.
        best_request: dict[str, Any] = {}
        for agent_name, out in outputs.items():
            for req in out.requests:
                cur = best_request.get(req.actuator)
                if cur is None or req.priority > cur.priority:
                    best_request[req.actuator] = req

        for actuator, owner in OWNERSHIP.items():
            # 1. owner comms loss -> fallback
            if not alive.get(owner, True):
                result.values[actuator] = FALLBACK[actuator]
                result.faults.append({"code": "owner_comms_loss", "actuator": actuator,
                                      "owner": owner, "t_s": t_s})
                result.decisions.append(Decision(
                    actuator, FALLBACK[actuator], owner, "fallback",
                    f"owner {owner!r} unreachable: conservative fallback"))
                continue

            commit = owner_commit.get(actuator)
            owner_val = commit[0] if commit else None
            owner_reason = commit[1] if commit else "no commit this step"

            # 2. owner timed out (alive but silent) -> fallback
            if owner_val is None:
                result.values[actuator] = FALLBACK[actuator]
                result.faults.append({"code": "owner_timeout", "actuator": actuator,
                                      "owner": owner, "t_s": t_s})
                result.decisions.append(Decision(
                    actuator, FALLBACK[actuator], owner, "fallback",
                    f"owner {owner!r} sent no value: fallback"))
                continue

            # 3. honour a safer high-priority request over the owner's value
            req = best_request.get(actuator)
            if req is not None and _request_is_safer(actuator, req.target, owner_val):
                result.values[actuator] = req.target
                result.decisions.append(Decision(
                    actuator, req.target, owner, "request_override",
                    f"request (prio {req.priority}) safer than owner: {req.rationale}"))
            else:
                result.values[actuator] = owner_val
                result.decisions.append(Decision(
                    actuator, owner_val, owner, "owner_commit", owner_reason))

        return result
