# ThermaLoop — Autonomous AI Research & Operations Center (Plan)

Short plan for the multi-agent autonomous operations layer built on top of the
existing deterministic physics simulation. Local-only, no paid APIs, no real
device control, deterministic policies first (no LLM required).

## Design rules (non-negotiable)
1. **Reuse physics, don't rewrite.** `physics.py` primitives and the
   per-timestep thermodynamics are reused verbatim. The existing
   `simulation.py` / `run()` and its 36 tests stay untouched.
2. **Operational model != forecasting model.** The sim is the "real" plant.
   Agents may run their own internal forecast sims (branches) to decide, but
   that is separate from the operational engine.
3. **Single writer per actuator.** Each actuator has exactly one owner agent.
   Everyone else sends `request` events; the owner (or arbiter) decides.
4. **Independent safety layer.** A constraint validator sits between agent
   actions and the plant. It can clamp/override any action. Emergency reactions
   never wait for a forecast or an LLM. Agents cannot change safety limits or
   grant themselves authority.
5. **No fabricated confidence.** Experiments store measured evidence only.
   Nothing auto-promotes to policy. We report when mode C does **not** help.

## Components (modules under `backend/thermalloop/ops/`)
- `engine.py` — stateful stepped engine: `reset(seed) / step(action, dt) ->
  (state, StepRecord) / get_state() / snapshot() / restore()`. Wraps the exact
  per-timestep physics from `simulation.py`.
- `bus.py` — event bus. Event types: `observation, request, proposal,
  decision, action_result, fault`. Append-only log + subscribers.
- `state.py` — shared blackboard: timestamped values with data-quality flags
  (`ok / stale / missing / suspect`).
- `actuators.py` — actuator registry + single-writer ownership table.
- `safety.py` — independent constraint validator (temp/power/flow/rate limits,
  stale data, agent timeout, authority conflict, comfort). Pre-action, not
  post-hoc. Emergency overrides.
- `agents/` — 8 agents, each: observe -> evaluate -> propose/act -> measure ->
  adjust. Explicit inputs / actions / authority.
- `arbiter.py` — collects requests/proposals, applies public rules + response
  deadline, falls back on comms loss.
- `scenarios.py` — runtime injectors: load spike, pump degradation, sensor
  drift/loss, server failure, heating change, forecast mismatch, agent comms
  loss.
- `experiments.py` — SQLite store: hypothesis, config, model version, seed,
  actions, metrics, violations, conclusion, limitations.
- `runtime.py` — the operations loop that ties engine + bus + state + agents +
  arbiter + safety together, mode A/B/C.
- `evaluation.py` — 3-mode comparison harness on identical seed/inputs.

## Agents and authority (single writer)
| Agent          | Owns (write)                        | Reads                        |
|----------------|-------------------------------------|------------------------------|
| Workload       | gpu_load_setpoint                   | job queue, power, temps      |
| GPU            | (requests load shed)                | rack temps, gpu load         |
| Infrastructure | primary_pump_speed                  | primary flow, temps          |
| Building       | zone_setpoints (request)            | zone temps, comfort          |
| PowerCooling   | aux_rejection_enabled, hp_enabled   | primary residual, power      |
| HeatRecovery   | secondary_pump_speed, buffer_charge | demand, buffer, delivered    |
| Fault          | (raises faults, requests failover)  | all sensors, residuals       |
| Research       | (none; proposes experiments only)   | history, snapshots           |

Actuators (single-writer): `gpu_load_setpoint` (Workload),
`primary_pump_speed` (Infrastructure), `secondary_pump_speed` +
`buffer_charge_enable` (HeatRecovery), `heat_pump_enabled` +
`aux_rejection_enabled` (PowerCooling). Building and GPU influence via requests
only.

## Control modes compared
- **A** rule-based baseline (fixed policies, no agents).
- **B** agents without forecast simulation (reactive policies only).
- **C** agents with forecast + validation (branch sims before acting).

Same workload / weather / demand / seed across A/B/C. Metrics: total power,
on-time jobs, temp violations, comfort shortfall, useful heat recovered,
recovery time after a fault, failover count, coordinator compute cost. We do
not tune to make C win; we report honest results.

## Tests
- energy balance holds in the stepped engine (matches `run()`),
- action ownership (single writer enforced),
- limit protection (safety clamps bad actions),
- scenario reproducibility (same seed -> same trace),
- data/agent-failure behavior (stale sensor, agent timeout -> fallback).

## Honesty ledger (status per piece)
Tracked in `docs/AGENTS_STATUS.md`: implemented+tested / simplified model /
not implemented / needs real data.
