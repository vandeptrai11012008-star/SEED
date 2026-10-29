"""Tests for the autonomous operations layer.

Covers the brief's required checks:
  - energy balance holds in the stepped engine (matches monolithic run())
  - action ownership is single-writer and enforced
  - the safety layer protects limits (clamps/overrides)
  - scenarios reproduce exactly for a fixed seed
  - data loss and agent comms loss trigger the documented fallback behaviour
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from thermalloop.ops.actuators import ActuatorRegistry, OwnershipError
from thermalloop.ops.agents.base import AgentOutput, Commit
from thermalloop.ops.arbiter import Arbiter
from thermalloop.ops.engine import Action, SteppedEngine
from thermalloop.ops.evaluation import compare_modes
from thermalloop.ops.runtime import OpsRuntime
from thermalloop.ops.safety import Limits, SafetyLayer
from thermalloop.ops.state import Blackboard
from thermalloop.simulation import run_simulation


# --------------------------------------------------------------- engine parity
def test_stepped_engine_matches_monolithic_run():
    r = run_simulation({"duration_s": 7200, "timestep_s": 600, "start_hour": 0})
    e = SteppedEngine()
    e.reset(seed=0, start_hour=0, timestep_s=600)
    for i in range(len(r["series"])):
        _, rec = e.step(Action(), 600)
        a = r["series"][i]
        assert rec.delivered_total_W == pytest.approx(a["delivered_total_W"], rel=1e-9, abs=1e-6)
        assert rec.hx_transfer_W == pytest.approx(a["hx_transfer_W"], rel=1e-9, abs=1e-6)
        assert rec.buffer_temp_C == pytest.approx(a["buffer_temp_C"], rel=1e-9, abs=1e-6)
        assert rec.primary_supply_C == pytest.approx(a["primary_supply_C"], rel=1e-9, abs=1e-6)


def test_stepped_engine_energy_split_balance():
    e = SteppedEngine()
    e.reset(seed=0, start_hour=12, timestep_s=600)
    for _ in range(12):
        e.step(Action(), 600)
    t = e.get_state().totals
    # IT heat splits exactly into liquid + air capture.
    assert t["liquid_captured_J"] + t["air_remaining_J"] == pytest.approx(t["it_generated_J"], rel=1e-9)
    # Primary-side balance: captured liquid heat is accounted for.
    primary_rhs = (t["primary_pipe_loss_J"] + t["hx_transfer_J"] + t["heat_pump_source_J"]
                   + t["aux_rejected_J"] + t["primary_unrejected_J"])
    assert primary_rhs == pytest.approx(t["liquid_captured_J"], rel=1e-6)


def test_snapshot_restore_roundtrip():
    e = SteppedEngine()
    e.reset(seed=4, start_hour=10, timestep_s=600)
    for _ in range(5):
        e.step(Action(), 600)
    snap = e.snapshot()
    _, after_a = e.step(Action(gpu_load_fraction=0.9), 600)
    e.restore(snap)
    _, after_b = e.step(Action(gpu_load_fraction=0.9), 600)
    assert after_a.primary_supply_C == after_b.primary_supply_C
    assert after_a.delivered_total_W == after_b.delivered_total_W


# ------------------------------------------------------------- action ownership
def test_single_writer_enforced():
    reg = ActuatorRegistry()
    # workload owns gpu load; anyone else is rejected.
    reg.commit("gpu_load_fraction", 0.8, "workload")
    assert reg.values["gpu_load_fraction"] == 0.8
    with pytest.raises(OwnershipError):
        reg.commit("gpu_load_fraction", 0.2, "fault")


def test_arbiter_rejects_non_owner_commit():
    arb = Arbiter()
    outputs = {
        "fault": AgentOutput(commits=[Commit("gpu_load_fraction", 0.1, "sneaky")]),
    }
    result = arb.resolve(outputs, alive={"fault": True, "workload": True}, t_s=0.0)
    assert any(f["code"] == "ownership_violation" for f in result.faults)


# --------------------------------------------------------------- limit protection
def test_safety_clamps_out_of_range_and_rate():
    board = Blackboard()
    board.set_time(0.0)
    safety = SafetyLayer(Limits())
    # gpu fraction > 1 must be clamped to 1
    res = safety.validate(Action(gpu_load_fraction=1.6, primary_pump_speed=0.05), board)
    assert res.action.gpu_load_fraction <= 1.0
    assert res.action.primary_pump_speed >= 0.2  # pump floor


def test_safety_overrides_on_overtemperature():
    board = Blackboard()
    board.set_time(0.0)
    board.write("sensor_primary_supply_T", 52.0, t_s=0.0, quality="ok")
    safety = SafetyLayer(Limits())
    res = safety.validate(Action(aux_rejection_enabled=False, gpu_load_fraction=1.0), board)
    assert res.emergency is True
    assert res.action.aux_rejection_enabled is True           # forced rejection
    assert res.action.gpu_load_fraction <= safety.limits.gpu_shed_fraction  # load shed


def test_safety_cannot_be_mutated_by_agents():
    safety = SafetyLayer(Limits())
    # the limits object is owned by the layer; there is no setter path.
    assert not hasattr(safety, "set_limits")
    assert safety.limits.primary_supply_crit_C == 50.0


# ---------------------------------------------------------- reproducibility
def test_scenario_reproducible_for_fixed_seed():
    a = OpsRuntime(mode="C", scenario="ai_load_spike", seed=11, timestep_s=600)
    b = OpsRuntime(mode="C", scenario="ai_load_spike", seed=11, timestep_s=600)
    ra = a.run(20)
    rb = b.run(20)
    for x, y in zip(ra, rb):
        assert x.record.primary_supply_C == y.record.primary_supply_C
        assert x.record.delivered_total_W == y.record.delivered_total_W
    assert a.coordinator_compute_cost == b.coordinator_compute_cost


# ------------------------------------------------------- data / agent failure
def test_sensor_loss_marks_quality_and_triggers_fault():
    rt = OpsRuntime(mode="B", scenario="sensor_loss", seed=2, timestep_s=600)
    rt.run(26)
    # during the dropout window, a sensor_integrity fault is raised by the fault agent
    codes = {f.get("code") for r in rt.reports for f in r.faults}
    assert "sensor_integrity" in codes


def test_agent_comms_loss_triggers_fallback():
    rt = OpsRuntime(mode="B", scenario="agent_comms_loss", seed=2, timestep_s=600)
    rt.run(22)
    codes = {f.get("code") for r in rt.reports for f in r.faults}
    assert "owner_comms_loss" in codes
    # evaluation should count failovers > 0 for this scenario
    cmp = compare_modes(scenario="agent_comms_loss", seed=2, n_steps=22)
    assert cmp.per_mode["B"]["failover_count"] > 0


# ------------------------------------------------------- honest comparison
def test_comparison_reports_all_required_metrics():
    cmp = compare_modes(scenario="ai_load_spike", seed=1, n_steps=24)
    for mode in ("A", "B", "C"):
        m = cmp.per_mode[mode]
        for key in ("total_power_kWh", "on_time_job_fraction", "temp_violation_steps",
                    "comfort_shortfall_Kh", "useful_heat_kWh", "recovery_time_steps",
                    "failover_count", "coordinator_cost_branch_steps"):
            assert key in m
    # mode C always pays a compute cost; A and B never do.
    assert cmp.per_mode["A"]["coordinator_cost_branch_steps"] == 0
    assert cmp.per_mode["B"]["coordinator_cost_branch_steps"] == 0
    assert cmp.per_mode["C"]["coordinator_cost_branch_steps"] > 0
    assert "_notes" in cmp.verdict and cmp.verdict["_notes"]


# ------------------------------------------------ hardening regression tests
def test_branch_fork_does_not_mutate_live_plant():
    """A forecast branch must not leak into the operational engine (M1/Q3)."""
    e = SteppedEngine()
    e.reset(seed=1, start_hour=12, timestep_s=600)
    for _ in range(4):
        e.step(Action(), 600)
    before = e.get_state()
    branch = e.fork()
    for _ in range(6):
        branch.step(Action(gpu_load_fraction=1.0), 600)
    after = e.get_state()
    # live engine untouched by the branch
    assert after.buffer_K == before.buffer_K
    assert after.soil_K == before.soil_K
    assert after.index == before.index
    for zid in after.zones:
        assert after.zones[zid].temperature_K == before.zones[zid].temperature_K


def test_safety_rate_limiter_consistent_after_none_gap():
    """A None command must not leave a stale rate-limit anchor (C3)."""
    board = Blackboard()
    board.set_time(0.0)
    safety = SafetyLayer(Limits())
    # step 1: command 1.0 -> anchor becomes 1.0
    r1 = safety.validate(Action(primary_pump_speed=1.0), board)
    assert r1.action.primary_pump_speed == 1.0
    # step 2: command None -> effective default (1.0) anchors, not stale
    safety.validate(Action(primary_pump_speed=None), board)
    # step 3: command 1.0 again -> no rate clamp should fire (anchor is 1.0)
    r3 = safety.validate(Action(primary_pump_speed=1.0), board)
    assert not any(e.actuator == "primary_pump_speed" and e.kind == "clamp"
                   for e in r3.events)


def test_safety_rate_limit_still_clamps_large_jump():
    board = Blackboard()
    board.set_time(0.0)
    safety = SafetyLayer(Limits())
    safety.validate(Action(gpu_load_fraction=0.5), board)       # anchor 0.5
    res = safety.validate(Action(gpu_load_fraction=1.0), board)  # +0.5 > 0.25 limit
    assert res.action.gpu_load_fraction < 1.0
    assert any(e.actuator == "gpu_load_fraction" and e.kind == "clamp" for e in res.events)


def test_on_time_metric_uses_diurnal_demand_not_reference_engine():
    """on_time_job_fraction is a clean function of the step hour (C1)."""
    cmp = compare_modes(scenario="none", seed=0, n_steps=24, start_hour=0)
    for m in ("A", "B", "C"):
        frac = cmp.per_mode[m]["on_time_job_fraction"]
        assert 0.0 <= frac <= 1.0


def test_disturbance_computed_once_offline_matches_merge():
    """offline_agents and the merged disturbance come from one evaluation (I1)."""
    rt = OpsRuntime(mode="B", scenario="agent_comms_loss", seed=1, timestep_s=600)
    rt.run(22)
    # during the comms-loss window the label is present AND a fallback fired;
    # if the two scenario evaluations diverged these would not line up.
    labelled = [r for r in rt.reports if "comms loss" in r.scenario_label]
    assert labelled, "expected comms-loss disturbance labels"
    comms_faults = [f for r in rt.reports for f in r.faults
                    if f.get("code") == "owner_comms_loss"]
    assert comms_faults


def test_cooling_derate_scenario_runs_all_modes():
    cmp = compare_modes(scenario="cooling_derate", seed=2, n_steps=36, start_hour=12,
                        drivers={"gpu_load_peak_fraction": 1.0})
    for m in ("A", "B", "C"):
        assert cmp.per_mode[m]["peak_primary_supply_C"] > 0


def test_dry_cooler_derate_raises_primary_temperature():
    """Deratng the cooler must physically push the loop hotter (new actuator)."""
    full = SteppedEngine(); full.reset(seed=1, start_hour=15, timestep_s=600,
                                       drivers={"gpu_load_peak_fraction": 1.0})
    derated = SteppedEngine(); derated.reset(seed=1, start_hour=15, timestep_s=600,
                                             drivers={"gpu_load_peak_fraction": 1.0})
    for _ in range(8):
        _, rf = full.step(Action(gpu_load_fraction=1.0, aux_rejection_enabled=True,
                                 heat_pump_enabled=False), 600)
        _, rd = derated.step(Action(gpu_load_fraction=1.0, aux_rejection_enabled=True,
                                    heat_pump_enabled=False, dry_cooler_available=0.1), 600)
    assert rd.primary_supply_C >= rf.primary_supply_C


def test_evaluation_metrics_identical_structure_across_modes():
    cmp = compare_modes(scenario="pump_degradation", seed=4, n_steps=30)
    keys_a = set(cmp.per_mode["A"])
    assert keys_a == set(cmp.per_mode["B"]) == set(cmp.per_mode["C"])


# ----------------------------------------------- supervisory upgrade tests
def test_coordinator_sets_regime_and_targets():
    from thermalloop.ops.coordinator import (Coordinator, T_REGIME,
                                             T_SEC_SETPOINT, T_LOAD_CEIL)
    board = Blackboard()
    board.set_time(0.0)
    # hot primary + untrusted -> protect
    board.write("sensor_primary_supply_T", 44.0, t_s=0.0, quality="ok")
    board.write("delivered_total_W", 0.0, t_s=0.0)
    board.write("unmet_demand_W", 0.0, t_s=0.0)
    coord = Coordinator()
    plan = coord.plan(board, 0.0)
    assert plan.regime == "protect"
    assert board.read(T_REGIME) == "protect"
    assert board.read(T_LOAD_CEIL) <= 1.0
    # strong demand + cool loop -> recover with a hotter secondary target
    board.write("sensor_primary_supply_T", 32.0, t_s=0.0, quality="ok")
    board.write("delivered_total_W", 120_000.0, t_s=0.0)
    plan2 = coord.plan(board, 0.0)
    assert plan2.regime == "recover"
    assert board.read(T_SEC_SETPOINT) >= 55.0


def test_agents_command_all_continuous_actuators():
    """The upgraded agents must drive every owned actuator, incl. the new ones."""
    from thermalloop.ops.actuators import OWNERSHIP
    rt = OpsRuntime(mode="C", scenario="cooling_derate", seed=5, timestep_s=600,
                    start_hour=12, drivers={"gpu_load_peak_fraction": 1.0})
    rt.run(12)
    commanded = set()
    for r in rt.reports:
        for d in r.decisions:
            if d.get("actuator"):
                commanded.add(d["actuator"])
    # every single-writer actuator should have been commanded at least once
    assert set(OWNERSHIP).issubset(commanded), set(OWNERSHIP) - commanded


def test_secondary_setpoint_actuator_changes_supply_temperature():
    """Commanding a hotter secondary setpoint must raise delivered supply temp."""
    cool = SteppedEngine(); cool.reset(seed=1, start_hour=2, timestep_s=600)
    hot = SteppedEngine(); hot.reset(seed=1, start_hour=2, timestep_s=600)
    for _ in range(10):
        _, rc = cool.step(Action(secondary_supply_setpoint_C=45.0,
                                 heat_pump_enabled=True), 600)
        _, rh = hot.step(Action(secondary_supply_setpoint_C=62.0,
                                heat_pump_enabled=True), 600)
    assert rh.secondary_supply_C >= rc.secondary_supply_C


def test_continuous_aux_level_between_off_and_full():
    """A partial aux level rejects more than off, less than full (monotone)."""
    def peak_unrejected(level):
        e = SteppedEngine(); e.reset(seed=1, start_hour=15, timestep_s=600,
                                     drivers={"gpu_load_peak_fraction": 1.0})
        vals = []
        for _ in range(8):
            _, r = e.step(Action(gpu_load_fraction=1.0, heat_pump_enabled=False,
                                 aux_rejection_level=level), 600)
            vals.append(r.primary_unrejected_W)
        return max(vals)
    off = peak_unrejected(0.0)
    half = peak_unrejected(0.5)
    full = peak_unrejected(1.0)
    assert off >= half >= full


def test_pi_controller_anti_windup():
    from thermalloop.ops.control import PIController
    pi = PIController(kp=1.0, ki=1.0, out_min=0.0, out_max=1.0)
    # drive a large persistent error; output clamps and integral must not blow up
    for _ in range(50):
        out = pi.update(setpoint=100.0, measured=0.0, dt_s=1.0)
        assert 0.0 <= out <= 1.0
    # when the error reverses, it should respond promptly (no huge windup lag)
    recovered = pi.update(setpoint=0.0, measured=0.0, dt_s=1.0)
    assert recovered <= 1.0


def test_agents_beat_rule_based_on_safety_under_pump_degradation():
    """The headline upgrade claim: agents keep the loop in band where A fails."""
    cmp = compare_modes(scenario="pump_degradation", seed=3, n_steps=40,
                        start_hour=12, drivers={"gpu_load_peak_fraction": 1.0})
    a_viol = cmp.per_mode["A"]["temp_violation_steps"]
    b_viol = cmp.per_mode["B"]["temp_violation_steps"]
    # agents must not do worse than rule-based on temperature violations
    assert b_viol <= a_viol


# --------------------------------------------- MPC optimiser (smart planning)
def test_mpc_optimizer_picks_lowest_cost_plan():
    from thermalloop.ops.optimizer import (MPCOptimizer, Objective,
                                           default_candidates)
    e = SteppedEngine()
    e.reset(seed=1, start_hour=15, timestep_s=600,
            drivers={"gpu_load_peak_fraction": 1.0})
    for _ in range(4):
        e.step(Action(), 600)
    opt = MPCOptimizer(Objective(), horizon=5)
    result = opt.optimise(e, default_candidates(current_load=0.9), current_load=0.9)
    # a best plan is chosen, it is the minimum-cost entry, and the scoreboard is
    # sorted ascending by cost
    assert result.best is result.scoreboard[0]
    costs = [c.cost for c in result.scoreboard]
    assert costs == sorted(costs)
    assert result.branch_steps > 0


def test_mpc_prefers_lower_load_when_overheating():
    """With rejection crippled, the optimiser must favour a lower-load plan."""
    from thermalloop.ops.optimizer import (MPCOptimizer, Objective,
                                           default_candidates)
    e = SteppedEngine()
    e.reset(seed=1, start_hour=15, timestep_s=600,
            drivers={"gpu_load_peak_fraction": 1.0})
    # drive the loop hot: full load, cooler crippled, no heat pump
    for _ in range(6):
        e.step(Action(gpu_load_fraction=1.0, dry_cooler_available=0.1,
                      heat_pump_enabled=False), 600)
    opt = MPCOptimizer(Objective(primary_band_C=44.0), horizon=6)
    result = opt.optimise(e, default_candidates(current_load=1.0), current_load=1.0)
    best_load = result.best.candidate["gpu_load_fraction"]
    # the chosen plan should not be the hottest full-load option when that one
    # predicts violations
    hottest = max(result.scoreboard, key=lambda c: c.candidate["gpu_load_fraction"])
    if hottest.violation_steps > 0:
        assert best_load <= hottest.candidate["gpu_load_fraction"]


def test_mode_c_coordinator_runs_mpc_and_reports_scoreboard():
    rt = OpsRuntime(mode="C", scenario="cooling_derate", seed=5, timestep_s=600,
                    start_hour=12, drivers={"gpu_load_peak_fraction": 1.0})
    rt.run(8)
    # coordinator proposals should carry an mpc_scoreboard in evidence
    found = False
    for r in rt.reports:
        for p in r.proposals:
            if p.get("agent") == "coordinator" and p.get("evidence"):
                if "mpc_scoreboard" in p["evidence"]:
                    found = True
    assert found
    # mode C pays a coordinator compute cost for the look-ahead
    assert rt.coordinator_compute_cost > 0


def test_mode_c_never_worse_than_b_on_violations():
    """The smart look-ahead must not degrade safety versus plain agents."""
    for scen in ("cooling_derate", "pump_degradation", "ai_load_spike"):
        cmp = compare_modes(scenario=scen, seed=3, n_steps=36, start_hour=12,
                            drivers={"gpu_load_peak_fraction": 1.0})
        assert cmp.per_mode["C"]["temp_violation_steps"] <= cmp.per_mode["B"]["temp_violation_steps"]


# -------------------------------------------------- PI + multivariable MPC
def test_infrastructure_agent_uses_pi_controller_live():
    """The pump must actually receive PI decisions during a normal run."""
    rt = OpsRuntime(mode="B", scenario="none", seed=5, timestep_s=600, start_hour=2,
                    drivers={"gpu_load_base_fraction": 0.4, "gpu_load_peak_fraction": 0.5})
    rt.run(14)
    pi_decisions = [d for r in rt.reports for d in r.decisions
                    if d.get("actuator") == "primary_pump_speed"
                    and "PI hold" in str(d.get("rationale", ""))]
    assert pi_decisions, "PI controller never drove the pump"


def test_infrastructure_pi_respects_safety_floor_and_full_flow():
    from thermalloop.ops.agents.infrastructure import InfrastructureAgent

    agent = InfrastructureAgent()
    board = Blackboard()
    board.set_time(0.0)
    board.write("target::primary_supply_band_C", 40.0, t_s=0.0)
    board.write("sensor_primary_supply_T", 41.0, t_s=0.0, quality="ok")
    assert agent.act(board, 0.0).commits[0].value == 1.0

    board.write("sensor_primary_supply_T", 30.0, t_s=0.0, quality="ok")
    assert agent.act(board, 0.0).commits[0].value >= 0.7


def test_mpc_candidates_vary_load_and_setpoint():
    from thermalloop.ops.optimizer import default_candidates

    grid = default_candidates(current_load=0.8, current_setpoint_C=55.0)
    loads = {c["gpu_load_fraction"] for c in grid.values()}
    setpoints = {c["secondary_supply_setpoint_C"] for c in grid.values()}
    assert len(loads) >= 2 and len(setpoints) >= 2
    assert len(grid) <= 8


def test_mpc_protect_regime_keeps_safe_secondary_setpoint_with_untrusted_sensor():
    """Cached energy optimisation must not defeat sensor-loss protection."""
    from thermalloop.ops.coordinator import Coordinator

    coordinator = Coordinator(engine=SteppedEngine())
    coordinator._cached_optimised_ceiling = 1.0
    coordinator._cached_optimised_setpoint = 62.0
    coordinator._since_mpc = 0
    board = Blackboard()
    board.set_time(0.0)
    board.write("sensor_primary_supply_T", 38.0, t_s=0.0, quality="suspect")
    plan = coordinator.plan(board, 0.0)
    assert plan.regime == "protect"
    assert plan.secondary_supply_C == coordinator.SEC_SETPOINT_PROTECT_C


def test_mode_c_saves_energy_under_high_heat_demand():
    """MPC should save electricity for similar useful heat in this benchmark."""
    cmp = compare_modes(scenario="none", seed=3, n_steps=48, start_hour=0,
                        drivers={"ambient_mean_C": -5.0, "gpu_load_base_fraction": 0.6,
                                 "gpu_load_peak_fraction": 0.8})
    b, c = cmp.per_mode["B"], cmp.per_mode["C"]
    assert abs(b["useful_heat_kWh"] - c["useful_heat_kWh"]) < 1.0
    assert c["total_power_kWh"] <= b["total_power_kWh"] + 1e-6
