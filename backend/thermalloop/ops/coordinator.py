"""Supervisory coordinator -- sets the global objective and per-agent targets.

The agents are good at their local job, but something has to decide the
*operating mode* of the whole plant: are we in a heat-recovery-maximising
regime, an energy-saving regime, or a thermal-protection regime? The
coordinator reads the shared blackboard once per step, picks a regime from
measured state, and publishes targets (setpoints + load ceiling) that the
agents then track with their controllers.

It owns NO actuator -- it only writes *targets* to the blackboard under the
``target::`` namespace and emits a ``proposal`` describing the regime. The
safety layer still sits below everything. This keeps the single-writer rule
intact while giving the system a coherent top-level goal.

Regimes (measured, deterministic):
  protect   - primary loop hot or a safety sensor is untrusted: cap load, cold
              secondary setpoint, full rejection headroom.
  recover   - real heat demand downstream: raise the secondary setpoint to
              deliver useful heat, keep the heat pump available.
  conserve  - low demand and cool loop: trim setpoints and rejection to save
              pump/heat-pump energy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .optimizer import MPCOptimizer, default_candidates
from .state import Blackboard

# Blackboard keys the coordinator publishes and the agents read.
T_REGIME = "target::regime"
T_LOAD_CEIL = "target::gpu_load_ceiling"
T_SEC_SETPOINT = "target::secondary_supply_C"
T_PRIMARY_BAND = "target::primary_supply_band_C"
T_PLAN_SOURCE = "target::plan_source"   # "heuristic" or "mpc"


@dataclass
class CoordinatorPlan:
    regime: str
    gpu_load_ceiling: float
    secondary_supply_C: float
    primary_supply_band_C: float
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "gpu_load_ceiling": round(self.gpu_load_ceiling, 3),
            "secondary_supply_C": round(self.secondary_supply_C, 2),
            "primary_supply_band_C": round(self.primary_supply_band_C, 2),
            "rationale": self.rationale,
        }


class Coordinator:
    name = "coordinator"

    # Objective weights are public and fixed (no hidden tuning): hold thermal
    # safety first, then serve heat demand, then save energy.
    PRIMARY_SOFT_C = 43.0      # above this we lean protective (near the 45C trip)
    PRIMARY_HARD_C = 44.0      # approaching the 45C trip
    SEC_SETPOINT_RECOVER_C = 58.0
    SEC_SETPOINT_CONSERVE_C = 48.0
    SEC_SETPOINT_PROTECT_C = 45.0

    def __init__(self, engine: Any | None = None) -> None:
        # When an engine is supplied (mode C), the coordinator runs an MPC-lite
        # look-ahead to choose the load ceiling optimally instead of the fixed
        # heuristic. compute_cost accrues the branch steps used, like an agent.
        self.engine = engine
        self.optimizer = MPCOptimizer(horizon=5) if engine is not None else None
        self.compute_cost = 0
        self.last_scoreboard: list[dict[str, Any]] = []
        # Run the MPC look-ahead every few steps (not every step) to bound cost;
        # the chosen ceiling is held between re-plans. Re-plan immediately when
        # the loop is in the upper range so safety response is never delayed.
        self._mpc_period = 3
        self._since_mpc = 999
        self._cached_optimised_ceiling: float | None = None
        self._last_best_peak = 0.0
        self._last_best_label = ""
        # Feed-forward: remember recent primary temperatures to estimate the
        # trend (degC per step) and act on where the loop is HEADING, not only
        # where it is. Deterministic, bounded window.
        self._primary_history: list[float] = []
        self.predicted_primary_C: float | None = None

    def _primary_trend(self, primary_C: float | None) -> float:
        """Return estimated degC/step change from the recent window."""
        if primary_C is None:
            return 0.0
        self._primary_history.append(primary_C)
        if len(self._primary_history) > 4:
            self._primary_history.pop(0)
        if len(self._primary_history) < 3:
            return 0.0
        # simple least-effort slope: mean of successive differences
        diffs = [self._primary_history[i + 1] - self._primary_history[i]
                 for i in range(len(self._primary_history) - 1)]
        return sum(diffs) / len(diffs)

    def plan(self, board: Blackboard, t_s: float) -> CoordinatorPlan:
        primary_sig = board.signal("sensor_primary_supply_T")
        primary_trusted = primary_sig is not None and primary_sig.quality == "ok"
        primary_C = float(primary_sig.value) if primary_trusted else None

        unmet = float(board.read("unmet_demand_W", 0.0) or 0.0)
        delivered = float(board.read("delivered_total_W", 0.0) or 0.0)
        demand = delivered + unmet

        # Track the primary-temperature trend for display/telemetry only. We do
        # NOT feed it back into regime selection: experiments showed that acting
        # on the projected temperature made the agents thrash (oscillating load,
        # large pump-energy spikes) without reducing violations, because the
        # plant already stays safe under the reactive policy. The honest, stable
        # intelligence upgrade is the MPC look-ahead below, not this projection.
        trend = self._primary_trend(primary_C)
        self.predicted_primary_C = (
            primary_C + trend * 3.0 if primary_C is not None else None)

        # --- regime selection from measured state ---
        primary_for_regime = primary_C
        if primary_for_regime is None or (primary_for_regime is not None
                                          and primary_for_regime >= self.PRIMARY_SOFT_C):
            regime = "protect"
            # Shed only as the loop nears the trip: full load at the soft line,
            # down to 0.6 as it reaches the hard line. Untrusted sensor -> 0.75.
            if primary_for_regime is None:
                ceiling = 0.75
            else:
                span = max(1.0, 45.0 - self.PRIMARY_SOFT_C)
                ceiling = max(0.6, 1.0 - 0.4 * (primary_for_regime - self.PRIMARY_SOFT_C) / span)
            sec_sp = self.SEC_SETPOINT_PROTECT_C
            band = self.PRIMARY_HARD_C
            if primary_C is None:
                why = "primary untrusted"
            else:
                why = f"primary {primary_C:.1f}C>= {self.PRIMARY_SOFT_C}C"
            rationale = f"protect regime ({why}): cap load {ceiling:.2f}, cool secondary"
        elif demand > 20_000.0:
            regime = "recover"
            ceiling = 1.0
            # Hotter secondary serves more useful heat; back off if demand tiny.
            sec_sp = self.SEC_SETPOINT_RECOVER_C
            band = self.PRIMARY_SOFT_C
            rationale = (f"recover regime (demand {demand/1000:.0f}kW): "
                         f"raise secondary to {sec_sp:.0f}C, full load headroom")
        else:
            regime = "conserve"
            ceiling = 1.0
            sec_sp = self.SEC_SETPOINT_CONSERVE_C
            band = self.PRIMARY_SOFT_C
            rationale = (f"conserve regime (demand {demand/1000:.0f}kW low): "
                         f"trim secondary to {sec_sp:.0f}C to save energy")

        plan_source = "heuristic"
        self.last_scoreboard = []

        # --- MPC-lite refinement (mode C): look ahead and pick the optimal
        # load ceiling. We only let the optimiser make things SAFER or more
        # efficient than the heuristic -- it can lower the ceiling to avoid a
        # predicted violation, or confirm full load is safe, but it never raises
        # the ceiling above what the protective heuristic already allows.
        if self.optimizer is not None and self.engine is not None:
            current_load = float(board.read("gpu_load_fraction", ceiling) or ceiling)
            self._since_mpc += 1
            # Re-plan on cadence, OR right away when the loop is warm (safety).
            warm = primary_C is not None and primary_C >= self.PRIMARY_SOFT_C - 2.0
            if self._since_mpc >= self._mpc_period or warm:
                result = self.optimizer.optimise(
                    self.engine, default_candidates(current_load), current_load)
                self.compute_cost += result.branch_steps
                self.last_scoreboard = [c.as_dict() for c in result.scoreboard]
                best_load = float(result.best.candidate.get("gpu_load_fraction", ceiling))
                self._cached_optimised_ceiling = best_load
                self._since_mpc = 0
                self._last_best_peak = result.best.peak_primary_C
                self._last_best_label = result.best.label
            # Optimiser may only tighten the ceiling, never loosen it.
            if self._cached_optimised_ceiling is not None:
                optimised_ceiling = min(ceiling, self._cached_optimised_ceiling)
                if optimised_ceiling < ceiling - 1e-6:
                    rationale = (f"MPC look-ahead: best plan '{self._last_best_label}' "
                                 f"(peak {self._last_best_peak:.1f}C); tighten ceiling "
                                 f"{ceiling:.2f} -> {optimised_ceiling:.2f}")
                    ceiling = optimised_ceiling
                plan_source = "mpc"

        plan = CoordinatorPlan(
            regime=regime, gpu_load_ceiling=ceiling, secondary_supply_C=sec_sp,
            primary_supply_band_C=band, rationale=rationale)

        # publish targets for the agents to track
        board.write(T_REGIME, regime, t_s=t_s)
        board.write(T_LOAD_CEIL, ceiling, t_s=t_s)
        board.write(T_SEC_SETPOINT, sec_sp, t_s=t_s)
        board.write(T_PRIMARY_BAND, band, t_s=t_s)
        board.write(T_PLAN_SOURCE, plan_source, t_s=t_s)
        return plan
