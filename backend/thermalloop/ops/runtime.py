"""Operations runtime -- the control loop over the stepped engine.

Each step:
  1. publish observations from the latest record to the blackboard (+ bus)
  2. every agent observes -> evaluates -> commits/requests/proposes
  3. the arbiter resolves actuator values (single-writer + requests + fallback)
  4. the safety layer validates/overrides the resolved action (emergency-safe)
  5. a scenario disturbance is merged in (what the world does to the plant)
  6. the engine steps; the measured outcome becomes next step's observation

Three control modes share this exact loop; only the controller differs:
  A  rule_based   - fixed policies, no agents (deterministic baseline)
  B  agents       - agents without a forecaster (reactive)
  C  agents_fc    - agents with a forecaster (branch sims before acting)

Pause/resume/step/speed live in the engine's stepped API; this runtime just
calls ``step`` once per ``tick`` so an outer server can control cadence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import MODEL_VERSION
from .actuators import ActuatorRegistry
from .agents import ALL_AGENTS
from .arbiter import Arbiter
from .bus import EventBus
from .coordinator import Coordinator
from .engine import Action, SteppedEngine
from .forecaster import make_forecaster
from .safety import Limits, SafetyLayer
from .scenarios import SCENARIOS, Disturbance
from .state import Blackboard


def _rule_based_action(board: Blackboard) -> tuple[Action, list[dict[str, Any]]]:
    """Mode A: a single fixed policy, no agents, no arbitration."""
    decisions: list[dict[str, Any]] = []
    primary = board.signal("sensor_primary_supply_T")
    primary_C = float(primary.value) if primary and primary.quality == "ok" else None
    gpu = board.read("gpu_load_fraction", 0.55)
    unrejected = float(board.read("primary_unrejected_W", 0.0) or 0.0)

    gpu_target = float(gpu)
    if primary_C is not None and primary_C >= 46.0:
        gpu_target = min(gpu_target, 0.6)
    pump = 1.0 if (primary_C is None or primary_C >= 40.0) else 0.8
    aux = unrejected > 20_000.0
    action = Action(gpu_load_fraction=round(gpu_target, 4), primary_pump_speed=pump,
                    secondary_pump_speed=0.9, buffer_charge_enabled=True,
                    heat_pump_enabled=True, aux_rejection_enabled=aux)
    decisions.append({"controller": "rule_based",
                      "gpu_load_fraction": action.gpu_load_fraction,
                      "primary_pump_speed": pump, "aux_rejection_enabled": aux})
    return action, decisions


@dataclass
class StepReport:
    index: int
    t_s: float
    record: Any
    decisions: list[dict[str, Any]] = field(default_factory=list)
    safety_events: list[dict[str, Any]] = field(default_factory=list)
    faults: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    scenario_label: str = ""


class OpsRuntime:
    MODES = ("A", "B", "C")

    def __init__(
        self,
        *,
        mode: str = "C",
        scenario: str = "none",
        seed: int = 0,
        timestep_s: int = 600,
        start_hour: float = 0.0,
        drivers: dict[str, Any] | None = None,
        limits: Limits | None = None,
    ) -> None:
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}")
        self.mode = mode
        self.scenario_name = scenario
        self.scenario = SCENARIOS[scenario]
        self.seed = seed
        self.model_version = MODEL_VERSION

        self.engine = SteppedEngine()
        self.engine.reset(seed=seed, start_hour=start_hour,
                          timestep_s=timestep_s, drivers=drivers)
        self.board = Blackboard()
        self.bus = EventBus()
        self.registry = ActuatorRegistry(real_device_enabled=False)
        self.arbiter = Arbiter()
        self.safety = SafetyLayer(limits)

        forecaster = (make_forecaster(self.engine, drivers, start_hour, timestep_s)
                      if mode == "C" else None)
        self.agents = [cls(forecaster=forecaster) for cls in ALL_AGENTS] if mode in ("B", "C") else []
        # Supervisory coordinator: sets the global regime + per-agent targets
        # each step (modes B and C). In mode C it is given the engine so it can
        # run an MPC-lite look-ahead and choose the load ceiling optimally;
        # mode B gets the heuristic coordinator (no look-ahead). Mode A is the
        # fixed rule-based baseline and deliberately has no coordinator.
        if mode == "C":
            self.coordinator = Coordinator(engine=self.engine)
        elif mode == "B":
            self.coordinator = Coordinator()
        else:
            self.coordinator = None

        self.index = 0
        self.reports: list[StepReport] = []
        self.coordinator_compute_cost = 0   # forecast branch steps consumed

        # prime the blackboard with an initial zero-th observation
        _, record = self.engine.step(Action(), timestep_s)
        self.board.set_time(record.t_s)
        self.board.ingest_record(record, record.t_s)
        self._bootstrap_record = record

    # ---------------------------------------------------------------- control
    def tick(self) -> StepReport:
        """Advance exactly one control step and return its report.

        ``t_s`` is the clock of the step we are about to compute (equal to the
        ``record.t_s`` the engine will stamp, because ``engine.step`` records
        the pre-increment time). Every event for this control cycle -- the
        observation, the agents' decisions/requests, the safety interventions
        and the resulting action_result -- is stamped with this same ``t_s`` so
        the timeline correlates cleanly. The blackboard values the agents read
        were measured on the *previous* step; ``Blackboard.signal`` exposes
        their age so staleness is still visible.
        """
        board = self.board
        t_s = self.engine.get_state().t_s
        board.set_time(t_s)

        decisions: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        faults: list[dict[str, Any]] = []

        # The scenario disturbance is a pure function of the step index. Compute
        # it exactly once so the offline-agent set and the plant-side action can
        # never diverge, even if a future scenario becomes stateful.
        disturbance = self.scenario(self.index)

        # 1. observations already on the board; echo a couple to the bus
        self.bus.publish(t_s=t_s, type="observation", source="plant",
                         topic="primary_supply_T",
                         payload={"value_C": board.read("sensor_primary_supply_T")})

        # 2-3. controller decides actuator values
        if self.mode == "A":
            resolved_action, decisions = _rule_based_action(board)
        else:
            # 2a. supervisor sets the global regime + per-agent targets first.
            if self.coordinator is not None:
                plan = self.coordinator.plan(board, t_s)
                # Attach the MPC scoreboard as evidence so the UI can show which
                # candidate plans were evaluated and why this one was chosen.
                evidence = ({"mpc_scoreboard": self.coordinator.last_scoreboard}
                            if self.coordinator.last_scoreboard else None)
                prop = {"agent": "coordinator", "topic": "regime",
                        "detail": plan.as_dict(), "rationale": plan.rationale,
                        "evidence": evidence}
                proposals.append(prop)
                self.bus.publish(t_s=t_s, type="proposal", source="coordinator",
                                 topic="regime", payload=prop)

            outputs = {}
            alive = {}
            for agent in self.agents:
                agent.alive = agent.name not in disturbance.offline_agents
                alive[agent.name] = agent.alive
                if agent.alive:
                    out = agent.act(board, t_s)
                    outputs[agent.name] = out
                    for c in out.commits:
                        self.bus.publish(t_s=t_s, type="decision", source=agent.name,
                                         topic=c.actuator,
                                         payload={"value": c.value, "rationale": c.rationale})
                    for r in out.requests:
                        self.bus.publish(t_s=t_s, type="request", source=agent.name,
                                         topic=r.actuator,
                                         payload={"target": r.target, "priority": r.priority,
                                                  "rationale": r.rationale})
                    for p in out.proposals:
                        prop = {"agent": agent.name, "topic": p.topic, "detail": p.detail,
                                "rationale": p.rationale, "evidence": p.evidence}
                        proposals.append(prop)
                        self.bus.publish(t_s=t_s, type="proposal", source=agent.name,
                                         topic=p.topic, payload=prop)
                    for fault in out.faults:
                        faults.append(fault)
                        self.bus.publish(t_s=t_s, type="fault", source=agent.name,
                                         topic=fault.get("code", "fault"), payload=fault)

            arb = self.arbiter.resolve(outputs, alive, t_s)
            for d in arb.decisions:
                decisions.append(vars(d))
            for f in arb.faults:
                faults.append(f)
                self.bus.publish(t_s=t_s, type="fault", source="arbiter",
                                 topic=f.get("code", "fault"), payload=f)
            # commit through the registry (re-enforces single writer)
            for actuator, value in arb.values.items():
                owner = self.registry.owner(actuator)
                self.registry.commit(actuator, value, owner)
            resolved_action = self.registry.to_action()
            coord_cost = self.coordinator.compute_cost if self.coordinator else 0
            self.coordinator_compute_cost = sum(a.compute_cost for a in self.agents) + coord_cost

        # 4. independent safety validation / override
        safety_result = self.safety.validate(resolved_action, board)
        safe_action = safety_result.action
        for ev in safety_result.events:
            self.bus.publish(t_s=t_s, type="decision", source="safety",
                             topic=ev.actuator,
                             payload={"kind": ev.kind, "reason": ev.reason,
                                      "old": ev.old, "new": ev.new})

        # 5. merge the world's disturbance (external, post-decision)
        world_action = safe_action.merged(disturbance.action)

        # 6. step the plant. record.t_s == t_s (pre-increment clock), so the
        # action_result shares the timestamp of this cycle's other events.
        _, record = self.engine.step(world_action, self.engine.get_state().dt_s)
        board.set_time(record.t_s)
        board.ingest_record(record, record.t_s)
        self.bus.publish(t_s=record.t_s, type="action_result", source="plant",
                         topic="step",
                         payload={"primary_supply_C": record.primary_supply_C,
                                  "delivered_total_W": record.delivered_total_W,
                                  "unmet_demand_W": record.unmet_demand_W,
                                  "pump_power_W": record.pump_power_W})

        report = StepReport(
            index=self.index, t_s=record.t_s, record=record, decisions=decisions,
            safety_events=safety_result.as_dicts(), faults=faults,
            proposals=proposals, scenario_label=disturbance.label)
        self.reports.append(report)
        self.index += 1
        return report

    def run(self, n_steps: int) -> list[StepReport]:
        for _ in range(n_steps):
            self.tick()
        return self.reports
