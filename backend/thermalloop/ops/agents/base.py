"""Agent base classes and the message types agents emit."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..state import Blackboard


@dataclass
class Commit:
    """A value the agent writes to an actuator it OWNS (single writer)."""
    actuator: str
    value: float | bool
    rationale: str


@dataclass
class Request:
    """A polite ask to the owner of an actuator the agent does NOT own."""
    actuator: str
    target: float | bool
    priority: int           # higher wins at the arbiter
    rationale: str


@dataclass
class Proposal:
    """A plan/setpoint suggestion, optionally backed by forecast evidence."""
    topic: str
    detail: dict[str, Any]
    rationale: str
    evidence: dict[str, Any] | None = None


@dataclass
class AgentOutput:
    commits: list[Commit] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    faults: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    """Base policy agent.

    Subclasses implement :meth:`act`. ``forecaster`` (optional) is a callable
    that, given a candidate action dict and a horizon in steps, returns summary
    metrics of a branch simulation. When it is ``None`` the agent is in reactive
    (mode B) operation; when provided the agent is in validated (mode C) mode.
    """

    name: str = "agent"
    owns: tuple[str, ...] = ()

    def __init__(self, forecaster: Any | None = None) -> None:
        self.forecaster = forecaster
        self.last_output: AgentOutput | None = None
        self.alive = True          # set False to simulate comms loss
        self.compute_cost = 0      # forecast branch steps consumed (mode C cost)

    def reset(self) -> None:
        self.last_output = None
        self.alive = True
        self.compute_cost = 0

    def act(self, board: Blackboard, t_s: float) -> AgentOutput:  # pragma: no cover
        raise NotImplementedError
