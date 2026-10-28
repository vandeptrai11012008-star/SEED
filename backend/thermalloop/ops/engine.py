"""Stateful, stepped operational engine.

This is the "real plant" that the agents operate. It reuses the exact
per-timestep thermodynamics of :mod:`thermalloop.simulation` but exposes a
stepped API so an external control loop can observe and act every timestep:

    engine.reset(seed=...)                 -> initial state
    state, record = engine.step(action, dt)
    engine.get_state()                     -> current StepState (deep copy)
    snap = engine.snapshot()               -> opaque restore token
    engine.restore(snap)                   -> rewind to a snapshot

The physics match ``SimplifiedPhysicsEngine.run`` step-for-step when driven
with the default (empty) action, which the test-suite asserts. Actions let a
controller override the GPU load setpoint, scale pump speeds, toggle the heat
pump and auxiliary rejection, and inject sensor faults.

Nothing here invents measured data; every value is a deterministic function of
config, drivers and actions. A per-engine ``random.Random`` seeded in
``reset`` supplies reproducible noise *only* where an action explicitly asks
for it (e.g. sensor drift), so identical seeds reproduce identical traces.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field, replace
from typing import Any

from .. import physics as phys
from ..config_loader import expand_rack_ids, load_config
from ..simulation import StepRecord, ZoneState, _ambient_C, _diurnal_load


@dataclass
class Action:
    """Control action applied for a single timestep.

    All fields are optional; ``None`` means "use the policy/driver default".
    Scalars for pump speed are fractions in [0, 1] of rated flow. The engine
    clamps everything to physical ranges, but the *safety* layer is the thing
    that is supposed to catch bad actions before they get here.
    """

    gpu_load_fraction: float | None = None          # override diurnal driver
    heat_pump_enabled: bool | None = None
    aux_rejection_enabled: bool | None = None
    primary_pump_speed: float | None = None          # fraction of rated flow
    secondary_pump_speed: float | None = None        # fraction of rated flow
    buffer_charge_enabled: bool | None = None
    # Sensor faults keyed by sensor id -> {"mode": "offset|stuck|dropout",
    # "offset_C": float, "stuck_C": float}. Applied to reported sensor_states
    # only; the underlying physics is unaffected (that is the point of a drift).
    sensor_faults: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Multiplier on pump rated flow to model mechanical degradation (<1 slows
    # the pump, modelling a failing bearing / clogged strainer).
    pump_degradation: dict[str, float] = field(default_factory=dict)
    # Fraction of the dry-cooler (auxiliary rejection) capacity that is
    # available. 1.0 = full, 0.0 = cooler offline. Models a heat-wave derate or
    # a fan failure. ``None`` means full capacity.
    dry_cooler_available: float | None = None
    # --- continuous control setpoints owned by agents (None = config default) ---
    # Secondary (heat-recovery) supply temperature target in degC. Raising it
    # delivers hotter, more useful heat but needs more heat-pump lift; lowering
    # it saves pump/HP energy. Lets the heat-recovery agent trade heat quality.
    secondary_supply_setpoint_C: float | None = None
    # Auxiliary rejection as a continuous fraction 0..1 of capacity, so the
    # power/cooling agent can modulate rejection smoothly instead of on/off.
    # When set, it supersedes aux_rejection_enabled.
    aux_rejection_level: float | None = None

    def merged(self, other: "Action") -> "Action":
        """Return a copy of ``self`` with set fields from ``other`` applied."""
        out = replace(self)
        for name in ("gpu_load_fraction", "heat_pump_enabled",
                     "aux_rejection_enabled", "primary_pump_speed",
                     "secondary_pump_speed", "buffer_charge_enabled",
                     "dry_cooler_available", "secondary_supply_setpoint_C",
                     "aux_rejection_level"):
            val = getattr(other, name)
            if val is not None:
                setattr(out, name, val)
        if other.sensor_faults:
            out.sensor_faults = {**self.sensor_faults, **other.sensor_faults}
        if other.pump_degradation:
            out.pump_degradation = {**self.pump_degradation, **other.pump_degradation}
        return out


@dataclass
class StepState:
    """Full mutable state advanced by :meth:`SteppedEngine.step`."""

    index: int
    t_s: float
    start_hour: float
    dt_s: int
    buffer_K: float
    buffer_initial_K: float
    soil_K: float
    zones: dict[str, ZoneState]
    totals: dict[str, float]
    rng_state: Any
    last_record: StepRecord | None = None


class SteppedEngine:
    """Config-driven lumped hydronic/thermal model exposed one step at a time."""

    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_config()
        self.a = self.cfg["assumptions"]
        self.site = self.cfg["site"]
        self.network = self.cfg["network"]
        self.defaults = self.cfg["simulation"]
        self._rack_inventory = expand_rack_ids(self.cfg)
        self._state: StepState | None = None
        self._rng = random.Random()

        # Static driver parameters resolved once at reset().
        self._base_fraction = 0.0
        self._peak_fraction = 0.0
        self._ambient_mean_C = 0.0
        self._total_it_W = 0.0
        self._capture_fraction = 0.0

    # ------------------------------------------------------------------ setup
    def reset(
        self,
        *,
        seed: int = 0,
        start_hour: float | None = None,
        timestep_s: int | None = None,
        drivers: dict[str, Any] | None = None,
    ) -> StepState:
        """Initialise state. Identical args + seed reproduce identical runs."""
        drivers = drivers or {}
        a = self.a
        self._rng = random.Random(seed)

        self._base_fraction = float(drivers.get(
            "gpu_load_base_fraction", self.defaults["drivers"]["gpu_load_base_fraction"]))
        self._peak_fraction = float(drivers.get(
            "gpu_load_peak_fraction", self.defaults["drivers"]["gpu_load_peak_fraction"]))
        self._ambient_mean_C = float(drivers.get(
            "ambient_mean_C", self.site["weather"]["ambient_mean_C"]))
        self._total_it_W = float(drivers.get(
            "total_it_power_kW", a["power"]["total_it_power_kW"])) * 1000.0
        self._capture_fraction = float(drivers.get(
            "liquid_capture_fraction", a["power"]["liquid_capture_fraction"]))

        dt_s = int(timestep_s if timestep_s is not None
                   else self.defaults["time"]["timestep_s"])
        start = float(start_hour if start_hour is not None
                      else self.defaults["time"]["start_hour"])

        tank = a["thermal_buffer"]
        buffer_K = phys.c_to_k(float(tank["initial_temp_C"]))

        zones: dict[str, ZoneState] = {}
        for zone_id, data in a["zones"].items():
            setpoint_K = phys.c_to_k(float(data["setpoint_C"]))
            design_demand_W = float(data["design_heat_demand_kW"]) * 1000.0
            design_delta_K = max(1.0, setpoint_K - phys.c_to_k(-10.0))
            zones[zone_id] = ZoneState(
                zone_id=zone_id,
                setpoint_K=setpoint_K,
                min_supply_K=phys.c_to_k(float(data["min_supply_C"])),
                design_demand_W=design_demand_W,
                temperature_K=setpoint_K,
                thermal_capacitance_J_K=float(data.get("thermal_capacitance_J_per_K", 100_000_000.0)),
                envelope_ua_W_K=design_demand_W / design_delta_K,
            )
        soil_K = phys.c_to_k(float(a["zones"]["zone_greenhouse_soil"]["soil_target_C"]))

        totals = {key: 0.0 for key in (
            "it_generated_J", "liquid_captured_J", "air_remaining_J",
            "primary_pipe_loss_J", "hx_transfer_J", "heat_pump_source_J",
            "aux_rejected_J", "primary_unrejected_J", "heat_pump_thermal_J",
            "heat_pump_elec_J", "delivered_J", "unmet_demand_J",
            "secondary_losses_J", "buried_pipe_loss_J", "secondary_rejected_J",
            "buffer_charge_J", "buffer_discharge_J", "buffer_delta_J",
            "tank_standing_loss_J", "pump_elec_J",
        )}

        self._state = StepState(
            index=0, t_s=0.0, start_hour=start, dt_s=dt_s,
            buffer_K=buffer_K, buffer_initial_K=buffer_K, soil_K=soil_K,
            zones=zones, totals=totals, rng_state=self._rng.getstate(),
        )
        return self.get_state()

    # ----------------------------------------------------------- snapshotting
    def get_state(self) -> StepState:
        if self._state is None:
            raise RuntimeError("engine not reset()")
        return copy.deepcopy(self._state)

    def snapshot(self) -> dict[str, Any]:
        """Opaque, serialisable restore token (deep copy of all state)."""
        if self._state is None:
            raise RuntimeError("engine not reset()")
        return {
            "state": copy.deepcopy(self._state),
            "base_fraction": self._base_fraction,
            "peak_fraction": self._peak_fraction,
            "ambient_mean_C": self._ambient_mean_C,
            "total_it_W": self._total_it_W,
            "capture_fraction": self._capture_fraction,
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self._state = copy.deepcopy(snap["state"])
        self._base_fraction = snap["base_fraction"]
        self._peak_fraction = snap["peak_fraction"]
        self._ambient_mean_C = snap["ambient_mean_C"]
        self._total_it_W = snap["total_it_W"]
        self._capture_fraction = snap["capture_fraction"]
        self._rng.setstate(self._state.rng_state)

    def fork(self) -> "SteppedEngine":
        """Return an independent copy with deep-cloned dynamic state.

        Used by the forecaster/Research agent to run branches without disturbing
        the operational plant. The config dict is shared by reference on
        purpose: ``step`` only ever *reads* config (it never mutates it), and a
        forecast branch runs many forks per control step, so deep-copying the
        whole config each time would be wasteful. All mutable *state*
        (zones, buffer_K, soil_K, totals, rng) is deep-copied via snapshot(),
        so a branch cannot leak into the live plant. Do not mutate ``self.cfg``
        at runtime or the change would be visible to every fork and the plant.
        """
        other = SteppedEngine(self.cfg)
        other.restore(self.snapshot())
        return other

    # -------------------------------------------------------------- stepping
    def _path_pressure_loss(self, circuit: str, mass_flow_kg_s: float, density: float) -> float:
        data = self.network["circuits"][circuit]
        by_id = {segment["id"]: segment for segment in data.get("segments", [])}
        loss = 0.0
        for segment_id in data.get("hydraulic_path", []):
            segment = by_id[segment_id]
            loss += phys.pipe_pressure_loss_Pa(
                mass_flow_kg_s, segment["diameter_m"], segment["length_m"], density=density)
        return loss

    def _greenhouse_demand_W(self, soil_K, ambient_K, deep_soil_K, area_m2, zone) -> float:
        params = self.a["greenhouse_soil"]
        target_K = phys.c_to_k(self.a["zones"]["zone_greenhouse_soil"]["soil_target_C"])
        if soil_K > target_K + 0.25:
            return 0.0
        holding = max(0.0,
            params["u_cover_W_per_m2K"] * area_m2 * (target_K - ambient_K)
            + params["u_ground_W_per_m2K"] * area_m2 * (target_K - deep_soil_K))
        recovery = (params["thermal_mass_J_per_K"] * max(0.0, target_K - soil_K)
                    / params["recovery_time_constant_s"])
        return min(zone.design_demand_W, holding + recovery)

    def _pipe_states(self, primary_flow, secondary_flow, greenhouse_flow,
                     primary_supply_C, primary_return_C, hx_secondary_out_C,
                     secondary_supply_C, secondary_return_C) -> dict[str, dict[str, float]]:
        states: dict[str, dict[str, float]] = {}
        for circuit_name, circuit in self.network["circuits"].items():
            for segment in circuit.get("segments", []):
                role = segment.get("role", "")
                if circuit_name == "primary":
                    flow = primary_flow * segment.get("branch_fraction", 1.0)
                    if role in {"return", "rejection"}:
                        temp = primary_return_C
                    elif role == "rack_heat_pickup":
                        temp = (primary_supply_C + primary_return_C) / 2.0
                    else:
                        temp = primary_supply_C
                else:
                    greenhouse = segment["id"] in {
                        "pipe_greenhouse_header_001", "pipe_buried_supply_001",
                        "pipe_soil_heating_001", "pipe_buried_return_001"}
                    flow = (greenhouse_flow if greenhouse else secondary_flow) * segment.get("branch_fraction", 1.0)
                    if role == "hx_outlet":
                        temp = hx_secondary_out_C
                    elif role in {"return", "rejection_return"}:
                        temp = secondary_return_C
                    else:
                        temp = secondary_supply_C
                states[segment["id"]] = {"mass_flow_kg_s": max(0.0, flow), "temperature_C": temp}
        return states

    def _apply_sensor_faults(
        self, sensor_states: dict[str, dict[str, float | str]], action: Action
    ) -> dict[str, dict[str, float | str]]:
        """Corrupt *reported* sensor values per the action. Physics unchanged.

        Returns a new dict; each affected sensor gets a ``quality`` tag so the
        shared-state layer can mark it stale/suspect/missing.
        """
        if not action.sensor_faults:
            for s in sensor_states.values():
                s.setdefault("quality", "ok")
            return sensor_states
        out: dict[str, dict[str, float | str]] = {}
        for sid, reading in sensor_states.items():
            fault = action.sensor_faults.get(sid)
            new = dict(reading)
            new.setdefault("quality", "ok")
            if fault:
                mode = fault.get("mode", "offset")
                if mode == "dropout":
                    new["value"] = float("nan")
                    new["quality"] = "missing"
                elif mode == "stuck":
                    new["value"] = float(fault.get("stuck_C", reading["value"]))
                    new["quality"] = "suspect"
                else:  # offset / drift
                    drift = float(fault.get("offset_C", 0.0))
                    if fault.get("noisy"):
                        drift += self._rng.uniform(-0.2, 0.2)
                    new["value"] = float(reading["value"]) + drift
                    new["quality"] = "suspect"
            out[sid] = new
        return out

    def step(self, action: Action | None = None, dt: int | None = None) -> tuple[StepState, StepRecord]:
        """Advance one timestep under ``action`` and return (state, record)."""
        if self._state is None:
            raise RuntimeError("engine not reset()")
        st = self._state
        action = action or Action()
        dt_s = int(dt if dt is not None else st.dt_s)

        a = self.a
        defaults = self.defaults
        self._rng.setstate(st.rng_state)

        hour = (st.start_hour + st.t_s / 3600.0) % 24.0
        ambient_C = _ambient_C(hour, self._ambient_mean_C,
                               float(self.site["weather"]["ambient_amplitude_C"]))
        ambient_K = phys.c_to_k(ambient_C)
        deep_soil_K = phys.c_to_k(float(self.site["weather"]["soil_deep_temp_C"]))

        if action.gpu_load_fraction is not None:
            load_fraction = max(0.0, min(1.0, float(action.gpu_load_fraction)))
        else:
            load_fraction = _diurnal_load(hour, self._base_fraction, self._peak_fraction)
        it_W = self._total_it_W * load_fraction
        liquid_W = it_W * self._capture_fraction
        air_W = it_W - liquid_W

        primary = a["primary_circuit"]
        secondary = a["secondary_circuit"]
        cp = float(primary["cp_J_per_kgK"])
        density = float(primary["density_kg_per_m3"])
        primary_setpoint_K = phys.c_to_k(float(primary["supply_temp_C"]))
        primary_delta_T = float(primary["design_delta_T_K"])
        secondary_return_K = phys.c_to_k(float(secondary["return_temp_C"]))
        if action.secondary_supply_setpoint_C is not None:
            # Agent-commanded supply target, clamped to a physically sane band
            # (above the return temperature, below the heat-pump ceiling).
            sp_C = max(float(secondary["return_temp_C"]) + 2.0,
                       min(75.0, float(action.secondary_supply_setpoint_C)))
            secondary_target_K = phys.c_to_k(sp_C)
        else:
            secondary_target_K = phys.c_to_k(float(secondary["supply_temp_C"]))
        secondary_delta_T = float(secondary["design_delta_T_K"])

        pumps = a["pumps"]
        prim_deg = float(action.pump_degradation.get("primary", 1.0))
        sec_deg = float(action.pump_degradation.get("secondary", 1.0))
        grn_deg = float(action.pump_degradation.get("greenhouse", 1.0))
        prim_speed = 1.0 if action.primary_pump_speed is None else max(0.0, min(1.0, action.primary_pump_speed))
        sec_speed = 1.0 if action.secondary_pump_speed is None else max(0.0, min(1.0, action.secondary_pump_speed))
        primary_max_flow = pumps["primary"]["rated_flow_m3_s"] * density * prim_deg * prim_speed
        secondary_max_flow = pumps["secondary"]["rated_flow_m3_s"] * density * sec_deg * sec_speed
        greenhouse_max_flow = pumps["greenhouse"]["rated_flow_m3_s"] * density * grn_deg

        tank = a["thermal_buffer"]
        tank_heat_capacity_J_K = density * tank["volume_m3"] * cp
        buffer_K = st.buffer_K
        buffer_min_useful_K = phys.c_to_k(float(tank["min_useful_temp_C"]))
        buffer_max_K = phys.c_to_k(float(tank["max_temp_C"]))

        zones = st.zones
        greenhouse = self.cfg["geometry"]["greenhouse"]
        soil_area_m2 = greenhouse["width_x"] * greenhouse["depth_y"]
        soil_K = st.soil_K
        soil_params = a["greenhouse_soil"]
        losses = a["distribution_losses"]
        indoor_loss_fraction = float(losses["secondary_indoor_pipe_loss_fraction"])
        primary_pipe_loss_fraction = float(losses["primary_indoor_pipe_loss_fraction"])

        hx_data = a["heat_exchanger"]
        hp_data = a["heat_pump"]
        hp_cop = max(1.0, float(hp_data["cop_heating"]))
        hp_max_W = float(hp_data["max_thermal_output_kW"]) * 1000.0
        dry_cooler_capacity_W = float(a["auxiliary_rejection"]["dry_cooler_capacity_kW"]) * 1000.0
        if action.dry_cooler_available is not None:
            dry_cooler_capacity_W *= max(0.0, min(1.0, float(action.dry_cooler_available)))

        heat_pump_enabled = (defaults["controls"]["heat_pump_enabled"]
                             if action.heat_pump_enabled is None else bool(action.heat_pump_enabled))
        # Continuous aux-rejection level supersedes the on/off flag when given.
        if action.aux_rejection_level is not None:
            aux_level = max(0.0, min(1.0, float(action.aux_rejection_level)))
            aux_enabled = aux_level > 1e-6
        else:
            aux_enabled = (defaults["controls"]["aux_rejection_enabled"]
                           if action.aux_rejection_enabled is None else bool(action.aux_rejection_enabled))
            aux_level = 1.0
        buffer_charge_allowed = True if action.buffer_charge_enabled is None else bool(action.buffer_charge_enabled)
        priority: list[str] = defaults["controls"]["buffer_charge_priority"]

        # ---- zone demand
        for zone_id, zone in zones.items():
            if zone_id == "zone_greenhouse_soil":
                zone.demand_W = self._greenhouse_demand_W(soil_K, ambient_K, deep_soil_K, soil_area_m2, zone)
            else:
                holding_W = max(0.0, zone.envelope_ua_W_K * (zone.setpoint_K - ambient_K))
                recovery_W = zone.thermal_capacitance_J_K * max(0.0, zone.setpoint_K - zone.temperature_K) / 21_600.0
                zone.demand_W = min(zone.design_demand_W, holding_W + recovery_W)
            zone.delivered_W = 0.0
            zone.unmet_W = zone.demand_W
        total_demand_W = sum(zone.demand_W for zone in zones.values())

        # ---- primary loop
        primary_flow = min(primary_max_flow, phys.mass_flow_for_heat(liquid_W, cp, primary_delta_T))
        primary_return_K = primary_setpoint_K + phys.delta_T_for_heat(liquid_W, primary_flow, cp)
        primary_pipe_loss_W = liquid_W * primary_pipe_loss_fraction
        hx_hot_in_K = primary_return_K - phys.delta_T_for_heat(primary_pipe_loss_W, primary_flow, cp)

        standing_loss_W = max(0.0, tank["heat_loss_W_per_K"] * (buffer_K - ambient_K))
        charge_room_W = max(0.0, (buffer_max_K - buffer_K) * tank_heat_capacity_J_K / dt_s + standing_loss_W)
        charge_capacity_W = min(float(tank["max_charge_kW"]) * 1000.0, charge_room_W)
        if not buffer_charge_allowed:
            charge_capacity_W = 0.0
        estimated_buried_loss_W = max(0.0, phys.buried_pipe_heat_loss_W(
            secondary_target_K, deep_soil_K, float(losses["buried_pipe_U_W_per_mK"]),
            float(losses["buried_pipe_length_m"]))) if zones["zone_greenhouse_soil"].demand_W > 0.0 else 0.0
        header_requirement_W = (total_demand_W + estimated_buried_loss_W) / max(1.0 - indoor_loss_fraction, 1e-6)
        secondary_target_heat_W = min(liquid_W, header_requirement_W + charge_capacity_W)
        secondary_flow = min(secondary_max_flow, phys.mass_flow_for_heat(secondary_target_heat_W, cp, secondary_delta_T))

        hx = phys.heat_exchanger_eps_ntu(
            hot_in_K=hx_hot_in_K, cold_in_K=secondary_return_K, m_hot=primary_flow,
            m_cold=secondary_flow, cp_hot=cp, cp_cold=cp,
            ua_W_per_K=float(hx_data["ua_W_per_K"]), effectiveness_override=float(hx_data["effectiveness"]))
        hx_W = min(hx.q_W, max(0.0, liquid_W - primary_pipe_loss_W))
        hx_primary_out_K = hx_hot_in_K - phys.delta_T_for_heat(hx_W, primary_flow, cp)
        hx_secondary_out_K = secondary_return_K + phys.delta_T_for_heat(hx_W, secondary_flow, cp)

        hp_thermal_W = hp_electric_W = hp_source_W = 0.0
        primary_after_hx_W = max(0.0, liquid_W - primary_pipe_loss_W - hx_W)
        if heat_pump_enabled and secondary_flow > 0.0 and header_requirement_W > hx_W:
            temperature_lift_W = secondary_flow * cp * max(0.0, secondary_target_K - hx_secondary_out_K)
            requested_hp_W = min(max(header_requirement_W - hx_W, temperature_lift_W), hp_max_W)
            source_fraction = 1.0 - 1.0 / hp_cop
            source_limited_output_W = (primary_after_hx_W / source_fraction
                                       if source_fraction > 1e-9 else requested_hp_W)
            hp_thermal_W = min(requested_hp_W, source_limited_output_W)
            hp_electric_W = hp_thermal_W / hp_cop
            hp_source_W = hp_thermal_W - hp_electric_W

        direct_secondary_W = hx_W + hp_thermal_W
        direct_supply_K = hx_secondary_out_K + phys.delta_T_for_heat(hp_thermal_W, secondary_flow, cp)

        primary_residual_W = max(0.0, liquid_W - primary_pipe_loss_W - hx_W - hp_source_W)
        aux_rejected_W = min(primary_residual_W,
                             dry_cooler_capacity_W * aux_level if aux_enabled else 0.0)
        primary_unrejected_W = primary_residual_W - aux_rejected_W
        actual_primary_supply_K = primary_setpoint_K + phys.delta_T_for_heat(primary_unrejected_W, primary_flow, cp)

        useful_floor_K = max(buffer_min_useful_K, secondary_return_K + 0.5)
        stored_available_W = max(0.0, (buffer_K - useful_floor_K) * tank_heat_capacity_J_K / dt_s - standing_loss_W)
        discharge_capacity_W = min(float(tank["max_discharge_kW"]) * 1000.0, stored_available_W)
        buffer_discharge_W = 0.0
        required_buffer_supply_K = max(
            (zone.min_supply_K for zone in zones.values() if zone.demand_W > 0.0),
            default=buffer_min_useful_K)
        if buffer_K >= required_buffer_supply_K:
            buffer_discharge_W = min(max(0.0, header_requirement_W - direct_secondary_W), discharge_capacity_W)

        buffer_flow = phys.mass_flow_for_heat(buffer_discharge_W, cp, max(buffer_K - secondary_return_K, 0.0))
        header_flow = secondary_flow + buffer_flow
        if header_flow > 1e-9:
            secondary_supply_K = (secondary_flow * direct_supply_K + buffer_flow * buffer_K) / header_flow
        else:
            secondary_supply_K = secondary_return_K

        header_input_W = direct_secondary_W + buffer_discharge_W
        indoor_loss_W = header_input_W * indoor_loss_fraction
        remaining_W = max(0.0, header_input_W - indoor_loss_W)
        buried_loss_W = 0.0
        for zone_id in priority:
            zone = zones[zone_id]
            if secondary_supply_K + 1e-9 < zone.min_supply_K:
                continue
            if zone_id == "zone_greenhouse_soil" and zone.demand_W > 0.0:
                candidate_buried_loss = max(0.0, phys.buried_pipe_heat_loss_W(
                    secondary_supply_K, deep_soil_K, float(losses["buried_pipe_U_W_per_mK"]),
                    float(losses["buried_pipe_length_m"])))
                branch_take_W = min(remaining_W, zone.demand_W + candidate_buried_loss)
                buried_loss_W = min(candidate_buried_loss, branch_take_W)
                zone.delivered_W = min(zone.demand_W, max(0.0, branch_take_W - buried_loss_W))
            else:
                branch_take_W = min(remaining_W, zone.demand_W)
                zone.delivered_W = branch_take_W
            zone.unmet_W = max(0.0, zone.demand_W - zone.delivered_W)
            remaining_W -= branch_take_W

        delivered_total_W = sum(zone.delivered_W for zone in zones.values())
        unmet_total_W = sum(zone.unmet_W for zone in zones.values())

        for zone_id, zone in zones.items():
            if zone_id == "zone_greenhouse_soil":
                continue
            envelope_loss_W = max(0.0, zone.envelope_ua_W_K * (zone.temperature_K - ambient_K))
            zone.temperature_K += (zone.delivered_W - envelope_loss_W) * dt_s / zone.thermal_capacitance_J_K
            zone.temperature_K = min(zone.setpoint_K + 1.0, max(ambient_K, zone.temperature_K))

        buffer_charge_W = min(remaining_W, charge_capacity_W)
        secondary_rejected_W = max(0.0, remaining_W - buffer_charge_W)
        tank_net_W = buffer_charge_W - buffer_discharge_W - standing_loss_W
        new_buffer_K = buffer_K + tank_net_W * dt_s / tank_heat_capacity_J_K
        new_buffer_K = min(buffer_max_K, max(ambient_K, new_buffer_K))
        buffer_delta_W = (new_buffer_K - buffer_K) * tank_heat_capacity_J_K / dt_s
        buffer_K = new_buffer_K

        greenhouse_delta_T = max(secondary_supply_K - secondary_return_K, 1.0)
        greenhouse_flow = min(greenhouse_max_flow, phys.mass_flow_for_heat(
            zones["zone_greenhouse_soil"].delivered_W + buried_loss_W, cp, greenhouse_delta_T))
        soil_K = phys.soil_temperature_step(
            soil_K, q_pipe_W=zones["zone_greenhouse_soil"].delivered_W, ambient_K=ambient_K,
            deep_soil_K=deep_soil_K, area_m2=soil_area_m2, dt_s=dt_s,
            u_cover_W_per_m2K=float(soil_params["u_cover_W_per_m2K"]),
            u_ground_W_per_m2K=float(soil_params["u_ground_W_per_m2K"]),
            thermal_mass_J_per_K=float(soil_params["thermal_mass_J_per_K"]))
        zones["zone_greenhouse_soil"].temperature_K = soil_K

        primary_pipe_dp = self._path_pressure_loss("primary", primary_flow, density)
        secondary_pipe_dp = self._path_pressure_loss("secondary", secondary_flow, density)
        greenhouse_pipe_dp = sum(
            phys.pipe_pressure_loss_Pa(greenhouse_flow, segment["diameter_m"], segment["length_m"], density=density)
            for segment in self.network["circuits"]["secondary"]["segments"]
            if segment["id"] in {"pipe_buried_supply_001", "pipe_soil_heating_001", "pipe_buried_return_001"})
        primary_head = min(pumps["primary"]["rated_head_Pa"], primary_pipe_dp + pumps["primary"]["equipment_allowance_Pa"])
        secondary_head = min(pumps["secondary"]["rated_head_Pa"], secondary_pipe_dp + pumps["secondary"]["equipment_allowance_Pa"])
        greenhouse_head = min(pumps["greenhouse"]["rated_head_Pa"], greenhouse_pipe_dp + pumps["greenhouse"]["equipment_allowance_Pa"])
        pump_power_W = sum((
            phys.pump_electrical_power_W(phys.volumetric_from_mass(primary_flow, density), primary_head, pumps["primary"]["efficiency"]),
            phys.pump_electrical_power_W(phys.volumetric_from_mass(secondary_flow, density), secondary_head, pumps["secondary"]["efficiency"]),
            phys.pump_electrical_power_W(phys.volumetric_from_mass(greenhouse_flow, density), greenhouse_head, pumps["greenhouse"]["efficiency"]),
        ))

        distribution_loss_W = indoor_loss_W + buried_loss_W
        secondary_residual_W = (direct_secondary_W - delivered_total_W - distribution_loss_W
                                - secondary_rejected_W - buffer_delta_W - standing_loss_W)
        mass_residual_kg_s = 0.0

        pipe_states = self._pipe_states(
            primary_flow, secondary_flow, greenhouse_flow,
            phys.k_to_c(actual_primary_supply_K), phys.k_to_c(primary_return_K),
            phys.k_to_c(hx_secondary_out_K), phys.k_to_c(secondary_supply_K),
            phys.k_to_c(secondary_return_K))
        sensor_states: dict[str, dict[str, float | str]] = {
            "sensor_primary_supply_T": {"value": phys.k_to_c(actual_primary_supply_K), "unit": "degC"},
            "sensor_primary_return_T": {"value": phys.k_to_c(primary_return_K), "unit": "degC"},
            "sensor_secondary_supply_T": {"value": phys.k_to_c(secondary_supply_K), "unit": "degC"},
            "sensor_secondary_return_T": {"value": phys.k_to_c(secondary_return_K), "unit": "degC"},
            "sensor_buffer_T": {"value": phys.k_to_c(buffer_K), "unit": "degC"},
            "sensor_greenhouse_soil_T": {"value": phys.k_to_c(soil_K), "unit": "degC"},
            "sensor_seed_storage_T_RH": {"value": phys.k_to_c(zones["zone_seed_storage"].temperature_K), "unit": "degC"},
            "sensor_seed_testing_T_RH": {"value": phys.k_to_c(zones["zone_seed_testing"].temperature_K), "unit": "degC"},
        }
        sensor_states = self._apply_sensor_faults(sensor_states, action)
        rack_power_W = {rack["id"]: rack["nominal_power_kW"] * 1000.0 * load_fraction
                        for rack in self._rack_inventory}

        for key, value in {
            "it_generated_J": it_W, "liquid_captured_J": liquid_W, "air_remaining_J": air_W,
            "primary_pipe_loss_J": primary_pipe_loss_W, "hx_transfer_J": hx_W,
            "heat_pump_source_J": hp_source_W, "aux_rejected_J": aux_rejected_W,
            "primary_unrejected_J": primary_unrejected_W, "heat_pump_thermal_J": hp_thermal_W,
            "heat_pump_elec_J": hp_electric_W, "delivered_J": delivered_total_W,
            "unmet_demand_J": unmet_total_W, "secondary_losses_J": distribution_loss_W,
            "buried_pipe_loss_J": buried_loss_W, "secondary_rejected_J": secondary_rejected_W,
            "buffer_charge_J": buffer_charge_W, "buffer_discharge_J": buffer_discharge_W,
            "tank_standing_loss_J": standing_loss_W, "pump_elec_J": pump_power_W,
        }.items():
            st.totals[key] += value * dt_s

        record = StepRecord(
            t_s=st.t_s, hour=round(hour, 3), gpu_load_fraction=round(load_fraction, 5),
            it_power_W=it_W, liquid_captured_W=liquid_W, air_remaining_W=air_W,
            hx_transfer_W=hx_W, aux_rejected_W=aux_rejected_W,
            primary_unrejected_W=primary_unrejected_W, primary_pipe_loss_W=primary_pipe_loss_W,
            heat_pump_source_W=hp_source_W, heat_pump_thermal_W=hp_thermal_W,
            heat_pump_elec_W=hp_electric_W, delivered_total_W=delivered_total_W,
            unmet_demand_W=unmet_total_W, distribution_loss_W=distribution_loss_W,
            buried_pipe_loss_W=buried_loss_W, buffer_charge_W=buffer_charge_W,
            buffer_discharge_W=buffer_discharge_W, buffer_temp_C=round(phys.k_to_c(buffer_K), 3),
            soil_temp_C=round(phys.k_to_c(soil_K), 3), ambient_C=round(ambient_C, 3),
            primary_supply_C=round(phys.k_to_c(actual_primary_supply_K), 3),
            primary_return_C=round(phys.k_to_c(primary_return_K), 3),
            hx_primary_out_C=round(phys.k_to_c(hx_primary_out_K), 3),
            hx_secondary_out_C=round(phys.k_to_c(hx_secondary_out_K), 3),
            secondary_supply_C=round(phys.k_to_c(secondary_supply_K), 3),
            secondary_return_C=round(phys.k_to_c(secondary_return_K), 3),
            primary_mass_flow_kg_s=primary_flow, secondary_mass_flow_kg_s=secondary_flow,
            greenhouse_mass_flow_kg_s=greenhouse_flow, primary_pressure_loss_Pa=primary_pipe_dp,
            secondary_pressure_loss_Pa=secondary_pipe_dp, greenhouse_pressure_loss_Pa=greenhouse_pipe_dp,
            pump_power_W=pump_power_W, energy_residual_W=secondary_residual_W,
            mass_residual_kg_s=mass_residual_kg_s,
            zone_demand_W={z: zz.demand_W for z, zz in zones.items()},
            zone_delivered_W={z: zz.delivered_W for z, zz in zones.items()},
            zone_unmet_W={z: zz.unmet_W for z, zz in zones.items()},
            zone_temperature_C={z: round(phys.k_to_c(zz.temperature_K), 3) for z, zz in zones.items()},
            pipe_states=pipe_states, sensor_states=sensor_states, rack_power_W=rack_power_W)

        # commit
        st.buffer_K = buffer_K
        st.soil_K = soil_K
        st.t_s += dt_s
        st.index += 1
        st.rng_state = self._rng.getstate()
        st.last_record = record
        return self.get_state(), record
