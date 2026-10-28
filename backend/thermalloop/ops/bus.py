"""Event bus for the operations layer.

An append-only, in-process event log with topic subscriptions. Every message
that flows between agents, the arbiter and the safety layer is an :class:`Event`
so the timeline UI and the experiment store can replay exactly what happened.

Event types (fixed vocabulary):
  observation   - a sensor/derived reading published to the blackboard
  request       - an agent asks the owner of an actuator to change it
  proposal      - an agent proposes a setpoint/plan (may include evidence)
  decision      - the arbiter (or owner) commits to an action
  action_result - the measured outcome of a committed action
  fault         - a detected abnormal condition (sensor, pump, comms, ...)

Nothing here is probabilistic. Ordering is the insertion order; each event has
a monotonically increasing ``seq`` and the simulation time ``t_s`` it belongs
to, so the log is fully reproducible for a given seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

EVENT_TYPES = (
    "observation", "request", "proposal", "decision", "action_result", "fault",
)


@dataclass
class Event:
    seq: int
    t_s: float
    type: str
    source: str
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq, "t_s": self.t_s, "type": self.type,
            "source": self.source, "topic": self.topic, "payload": self.payload,
        }


class EventBus:
    def __init__(self) -> None:
        self._log: list[Event] = []
        self._seq = 0
        self._subscribers: list[tuple[str | None, Callable[[Event], None]]] = []

    def publish(
        self, *, t_s: float, type: str, source: str, topic: str,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type!r}")
        event = Event(seq=self._seq, t_s=t_s, type=type, source=source,
                      topic=topic, payload=payload or {})
        self._seq += 1
        self._log.append(event)
        for want_type, callback in self._subscribers:
            if want_type is None or want_type == type:
                callback(event)
        return event

    def subscribe(self, callback: Callable[[Event], None], *, type: str | None = None) -> None:
        self._subscribers.append((type, callback))

    def events(self, *, type: str | None = None, since_seq: int = -1) -> list[Event]:
        return [e for e in self._log
                if e.seq > since_seq and (type is None or e.type == type)]

    def tail(self, n: int = 50) -> list[Event]:
        return self._log[-n:]

    def clear(self) -> None:
        self._log.clear()
        self._seq = 0
