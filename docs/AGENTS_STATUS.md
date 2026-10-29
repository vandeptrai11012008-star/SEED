# ThermaLoop Autonomous Ops — Honesty Ledger

What is implemented and tested, what is a simplified model, what is not built,
and what would need real data. This exists so no part of the system is
oversold.

## Implemented + tested
- **Stepped operational engine** (`ops/engine.py`). Bit-for-bit identical to the
  monolithic `simulation.run()` under the default action (verified: max diff
  0.0 over the overlap; `test_stepped_engine_matches_monolithic_run`). Supports
  `reset(seed)`, `step(action, dt)`, `get_state`, `snapshot/restore`, `fork`.
- **Event bus** (`ops/bus.py`) with the six required event types and a
  reproducible append-only log.
- **Shared blackboard** (`ops/state.py`) with per-signal timestamp and quality
  (`ok/stale/suspect/missing`).
- **Single-writer actuator ownership** (`ops/actuators.py`), enforced by both
  the registry and the arbiter (`test_single_writer_enforced`,
  `test_arbiter_rejects_non_owner_commit`).
- **Independent safety layer** (`ops/safety.py`): range + rate clamps and
  emergency overrides (over-temp, buffer over-temp, critical-sensor loss) that
  run from measured state with no forecast/LLM. Agents have no setter for the
  limits (`test_safety_*`).
- **Eight agents** (`ops/agents/`) each with observe→evaluate→act→measure loop
  and structured rationale that matches the code.
- **Arbiter** (`ops/arbiter.py`): priority requests, safer-request override,
  comms-loss/timeout fallback.
- **Runtime scenario/fault injection** (`ops/scenarios.py`): all nine mandatory
  disturbances.
- **SQLite experiment/comparison store** (`ops/experiments.py`), thread-safe for
  FastAPI's threadpool.
- **Three-mode comparison harness** (`ops/evaluation.py`) on identical
  seed/inputs, with an honest per-metric verdict and explicit notes when mode C
  does not help (`test_comparison_reports_all_required_metrics`).
- **FastAPI ops API** (`ops/api.py`) and **React ops UI** (`frontend/src/ops/`):
  overview, per-agent, event timeline, lab (predicted-vs-measured), mode
  comparison, scenario/fault selection. Typecheck + production build pass.
- **Integrated SEED tests**: 43 pass (6 pipe-routing, 35 ops-layer, 2 operations API).
  The GitHub workflow additionally checks the frontend production build,
  HTTP API endpoints, and Docker startup.

## Simplified model (transparent, not calibrated)
- All thermodynamics are the existing lumped engineering model: well-mixed
  tank, single soil node, steady per-step HX, quasi-steady hydraulics. Not
  calibrated against a real plant.
- "Rack coolant temperature" is approximated by the primary supply temperature.
- The mode-C forecaster rolls the engine forward using the **driver**
  assumptions, so under `forecast_mismatch` it is deliberately wrong — that is
  the honest test of forecast value, not a bug.
- `heating_demand_change` is injected as a timeline annotation; the actual
  colder-ambient effect is driven via `drivers.ambient_mean_C` in the harness.

## Not implemented (by design, for now)
- No LLM is used. Policies are deterministic rules. The architecture leaves room
  for an advisory LLM, but safety/emergency never depends on it.
- No real-device adapters. `real_device_enabled` is `False` and there is no code
  path to hardware.
- No automatic promotion of experiments to policy. The Research agent only
  proposes with measured branch evidence; a human decides.
- No fabricated confidence percentages anywhere. Forecast quality is reported as
  a measured error in °C.

## Intelligence upgrade (look-ahead planning)
The coordinator in mode C now runs an **MPC-lite optimiser** (`ops/optimizer.py`):
each re-plan it forks the engine, rolls a bounded set of load and secondary
setpoint candidates
over a short horizon, scores each with an explicit public objective (safety
violations >> unmet heat > energy > recovered heat, with a small switching
penalty), and picks the lowest-cost plan. The optimiser may only *tighten* the
load ceiling the protective heuristic allows, never loosen it, so look-ahead can
make the plant safer/greener but never less safe. The full candidate scoreboard
is attached to the coordinator's proposal so the UI can show *which* plans were
evaluated and *why* one was chosen -- verifiable optimality, not a black box.

Cost is bounded: approximately 6 candidate plans, horizon 5, re-planned every 3 steps (and
immediately whenever the loop is warm, so safety response is never delayed).

Measured outcome: with high heating demand (ambient −5 °C, seed 3, 48 steps),
mode C used about 536 kWh versus 588 kWh for mode B (~9% less electricity)
while delivering approximately the same useful heat (1733 kWh) and recording
zero temperature violations. With low heat demand modes B/C may match the
baseline. The comparison reports this plainly. A naive
"feed-forward on the temperature trend" variant was tried and **removed**: it
made the agents oscillate and spike pump energy without reducing violations,
which the experiments showed clearly. Stable, auditable look-ahead beat a
twitchy predictor.

## Autonomy upgrade (full-control pass)
The agents now operate the *entire* plant, not a subset:
- **Every actuator is agent-owned** (single writer each): GPU load, primary &
  secondary pump speed, buffer charge, heat-pump enable, and the two new
  continuous actuators -- **secondary supply setpoint** (heat-quality knob) and
  **continuous auxiliary-rejection level** (0..1, replacing the old on/off).
- **Supervisory coordinator** (`ops/coordinator.py`): reads the blackboard each
  step, selects a global regime (`protect` / `recover` / `conserve`) from
  measured state, and publishes per-agent targets (load ceiling, secondary
  setpoint, primary band). It owns no actuator -- the single-writer rule is
  intact; agents track its targets. This is the top-level objective layer.
- **Goal-seeking control** (`ops/control.py`): the Infrastructure agent now
  actually uses the PI controller with anti-windup and a bounded adaptive-gain
  tuner to drive primary pump speed. A protective override commands full flow
  when the loop reaches 39 °C, and PI output never goes below 0.7. A separate
  regression test confirms that a cached MPC setpoint cannot override the
  coordinator's protective setpoint when the primary sensor is untrusted.
- **Conditional safety benefit**: in a `pump_degradation` test (seed 3,
  start hour 12, 48 steps, peak GPU load 1.0), mode A recorded 8 temperature
  violations while modes B/C recorded 3. This is not universal: at seed 7,
  start hour 0, the same fault produced 3 violations in A and 4 in B/C.
  More scenario coverage and calibration are required before claiming robust
  superiority.

## Reviewed, fixed, and verified (hardening pass)
A behavioural review surfaced issues that are now fixed and regression-tested
(regression suite passes):
- **On-time metric** no longer uses a phase-misaligned reference engine; it is a
  stateless function of each step's own hour, so A/B/C are judged identically.
- **Safety rate limiter** anchors to the *effective* applied value every step
  (including when an actuator is left None), so a None gap can no longer create
  a stale anchor that mis-throttles the next move; modes A/B/C now experience it
  identically.
- **Scenario disturbance** is computed exactly once per control step, so the
  offline-agent set and the plant-side action can never diverge.
- **Event timestamps** for one control cycle (observation, decisions, safety,
  action_result) now share one `t_s`, fixing the earlier off-by-one in the log.
- **SQLite** uses WAL + busy_timeout, explicit column lists, and is closed on
  shutdown via a FastAPI lifespan handler.
- **Forecast branch isolation** verified: a branch cannot mutate the live plant
  (deep-copied state; config shared read-only by design).
- **Frontend**: fixed the Zustand object-selector infinite-render (blank page);
  the player interval is now cleaned up on unmount.

## Honest finding on mode C (not engineered away)
Mode C's forecaster uses the *operational model*, which does not know about
externally injected faults (a failing dry cooler, a degrading pump). The
forecast can therefore miss these disturbances. In the `pump_degradation`
seed-7 test, neither agent mode prevented more violations than mode A.
The `cooling_derate` stress case and varying random seeds reveal such gaps;
these results must be shown rather than hidden.

## Would need real data
- Calibrating the model (UA values, pump curves, soil properties, zone
  capacitances) against measured plant data.
- Real sensor noise/fault statistics instead of the injected fault modes.
- Validating the heat-pump COP and dry-cooler capacity against equipment tests.
