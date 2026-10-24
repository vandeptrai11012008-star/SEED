"""Deterministic simplified-physics backend for the ThermalLoop digital twin.

This is an engineering baseline, not a calibrated plant model and not measured
data. It computes temperatures, mass flows, pressure losses and explicit energy
ledgers for two hydraulically isolated circuits linked by a heat exchanger.
External solver modes remain non-executing adapters until their real results are
imported.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from . import physics as phys
from .config_loader import expand_rack_ids, load_config


@dataclass
class ZoneState:
    zone_id: str
    setpoint_K: float
    min_supply_K: float
    design_demand_W: float
    temperature_K: float
    thermal_capacitance_J_K: float
    envelope_ua_W_K: float
    demand_W: float = 0.0
    delivered_W: float = 0.0
    unmet_W: float = 0.0


@dataclass
class StepRecord:
    t_s: float
    hour: float
    gpu_load_fraction: float
    it_power_W: float
    liquid_captured_W: float
    air_remaining_W: float
    hx_transfer_W: float
    aux_rejected_W: float
    primary_unrejected_W: float
    primary_pipe_loss_W: float
    heat_pump_source_W: float
    heat_pump_thermal_W: float
    heat_pump_elec_W: float
    delivered_total_W: float
    unmet_demand_W: float
    distribution_loss_W: float
    buried_pipe_loss_W: float
    buffer_charge_W: float
    buffer_discharge_W: float
    buffer_temp_C: float
    soil_temp_C: float
    ambient_C: float
    primary_supply_C: float
    primary_return_C: float
    hx_primary_out_C: float
    hx_secondary_out_C: float
    secondary_supply_C: float
    secondary_return_C: float
    primary_mass_flow_kg_s: float
    secondary_mass_flow_kg_s: float
    greenhouse_mass_flow_kg_s: float
    primary_pressure_loss_Pa: float
    secondary_pressure_loss_Pa: float
    greenhouse_pressure_loss_Pa: float
    pump_power_W: float
    energy_residual_W: float
    mass_residual_kg_s: float
    zone_demand_W: dict[str, float] = field(default_factory=dict)
    zone_delivered_W: dict[str, float] = field(default_factory=dict)
    zone_unmet_W: dict[str, float] = field(default_factory=dict)
    zone_temperature_C: dict[str, float] = field(default_factory=dict)
    pipe_states: dict[str, dict[str, float]] = field(default_factory=dict)
    sensor_states: dict[str, dict[str, float | str]] = field(default_factory=dict)
    rack_power_W: dict[str, float] = field(default_factory=dict)


def _get_override(overrides: dict[str, Any], dotted: str, default: Any) -> Any:
    return overrides.get(dotted, default)


def _diurnal_load(hour: float, base: float, peak: float) -> float:
    """Smooth daily workload: minimum near 03:00, maximum near 15:00."""
    phase = (hour - 15.0) / 24.0 * 2.0 * math.pi
    return base + (peak - base) * 0.5 * (1.0 + math.cos(phase))


def _ambient_C(hour: float, mean: float, amplitude: float) -> float:
    return mean - amplitude * math.cos((hour - 15.0) / 24.0 * 2.0 * math.pi)


def _relative_error(lhs: float, rhs: float) -> float:
    return abs(lhs - rhs) / max(abs(lhs), abs(rhs), 1.0)


class SimplifiedPhysicsEngine:
    """Config-driven lumped hydronic and thermal model.

    Simplifications are explicit: well-mixed tank, one soil node, steady HX per
    timestep, and quasi-steady hydraulic pressure loss. Equipment ratings cap
    flow, heat-pump output and auxiliary rejection.
    """

    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_config()
        self.assume = self.cfg["assumptions"]
        self.site = self.cfg["site"]
        self.network = self.cfg["network"]

    def _path_pressure_loss(
        self, circuit: str, mass_flow_kg_s: float, density: float
    ) -> float:
        data = self.network["circuits"][circuit]
        by_id = {segment["id"]: segment for segment in data.get("segments", [])}
        loss = 0.0
        for segment_id in data.get("hydraulic_path", []):
            segment = by_id[segment_id]
            loss += phys.pipe_pressure_loss_Pa(
                mass_flow_kg_s,
                segment["diameter_m"],
                segment["length_m"],
                density=density,
            )
        return loss

    def _greenhouse_demand_W(
        self, soil_K: float, ambient_K: float, deep_soil_K: float,
        area_m2: float, zone: ZoneState,
    ) -> float:
        params = self.assume["greenhouse_soil"]
        target_K = phys.c_to_k(
            self.assume["zones"]["zone_greenhouse_soil"]["soil_target_C"]
        )
        if soil_K > target_K + 0.25:
            return 0.0
        holding = max(
            0.0,
            params["u_cover_W_per_m2K"] * area_m2 * (target_K - ambient_K)
            + params["u_ground_W_per_m2K"] * area_m2 * (target_K - deep_soil_K),
        )
        recovery = (
            params["thermal_mass_J_per_K"]
            * max(0.0, target_K - soil_K)
            / params["recovery_time_constant_s"]
        )
        return min(zone.design_demand_W, holding + recovery)

    def _pipe_states(
        self,
        primary_flow: float,
        secondary_flow: float,
        greenhouse_flow: float,
        primary_supply_C: float,
        primary_return_C: float,
        hx_secondary_out_C: float,
        secondary_supply_C: float,
        secondary_return_C: float,
    ) -> dict[str, dict[str, float]]:
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
                        "pipe_soil_heating_001", "pipe_buried_return_001",
                    }
                    flow = (greenhouse_flow if greenhouse else secondary_flow) * segment.get("branch_fraction", 1.0)
                    if role == "hx_outlet":
                        temp = hx_secondary_out_C
                    elif role in {"return", "rejection_return"}:
                        temp = secondary_return_C
                    else:
                        temp = secondary_supply_C
                states[segment["id"]] = {
                    "mass_flow_kg_s": max(0.0, flow),
                    "temperature_C": temp,
                }
        return states

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        a = self.assume
        defaults = self.cfg["simulation"]
        overrides: dict[str, Any] = request.get("overrides", {}) or {}

        duration_s = int(request.get("duration_s", defaults["time"]["duration_s"]))
        dt_s = int(request.get("timestep_s", defaults["time"]["timestep_s"]))
        start_hour = float(request.get("start_hour", defaults["time"]["start_hour"]))
        if duration_s <= 0 or dt_s <= 0 or dt_s > duration_s:
            raise ValueError("duration_s and timestep_s must be positive, with timestep_s <= duration_s")
        if duration_s % dt_s != 0:
            raise ValueError("duration_s must be an integer multiple of timestep_s")
        if duration_s // dt_s > 10_000:
            raise ValueError("Simulation is limited to 10,000 timesteps per request")

        base_fraction = float(request.get(
            "gpu_load_base_fraction",
            _get_override(overrides, "gpu_load_base_fraction", defaults["drivers"]["gpu_load_base_fraction"]),
        ))
        peak_fraction = float(request.get(
            "gpu_load_peak_fraction",
            _get_override(overrides, "gpu_load_peak_fraction", defaults["drivers"]["gpu_load_peak_fraction"]),
        ))
        if not 0.0 <= base_fraction <= peak_fraction <= 1.0:
            raise ValueError("GPU load fractions must satisfy 0 <= base <= peak <= 1")

        total_it_W = float(request.get("total_it_power_kW", a["power"]["total_it_power_kW"])) * 1000.0
        capture_fraction = float(request.get("liquid_capture_fraction", a["power"]["liquid_capture_fraction"]))
        if total_it_W < 0.0 or not 0.0 <= capture_fraction <= 1.0:
            raise ValueError("IT power must be non-negative and capture fraction must be in [0, 1]")

        heat_pump_enabled = bool(_get_override(
            overrides,
            "controls.heat_pump_enabled",
            request.get("heat_pump_enabled", defaults["controls"]["heat_pump_enabled"]),
        ))
        aux_enabled = bool(request.get(
            "aux_rejection_enabled", defaults["controls"]["aux_rejection_enabled"]
        ))
        ambient_mean_C = float(_get_override(
            overrides,
            "weather.ambient_mean_C",
            request.get("ambient_mean_C", self.site["weather"]["ambient_mean_C"]),
        ))
        ambient_amplitude_C = float(self.site["weather"]["ambient_amplitude_C"])
        deep_soil_K = phys.c_to_k(float(self.site["weather"]["soil_deep_temp_C"]))

        primary = a["primary_circuit"]
        secondary = a["secondary_circuit"]
        cp = float(primary["cp_J_per_kgK"])
        density = float(primary["density_kg_per_m3"])
        primary_setpoint_K = phys.c_to_k(float(primary["supply_temp_C"]))
        primary_delta_T = float(primary["design_delta_T_K"])
        secondary_return_K = phys.c_to_k(float(secondary["return_temp_C"]))
        secondary_target_K = phys.c_to_k(float(secondary["supply_temp_C"]))
        secondary_delta_T = float(secondary["design_delta_T_K"])

        pumps = a["pumps"]
        primary_max_flow = pumps["primary"]["rated_flow_m3_s"] * density
        secondary_max_flow = pumps["secondary"]["rated_flow_m3_s"] * density
        greenhouse_max_flow = pumps["greenhouse"]["rated_flow_m3_s"] * density

        tank = a["thermal_buffer"]
        tank_heat_capacity_J_K = density * tank["volume_m3"] * cp
        buffer_K = phys.c_to_k(float(tank["initial_temp_C"]))
        buffer_initial_K = buffer_K
        buffer_min_useful_K = phys.c_to_k(float(tank["min_useful_temp_C"]))
        buffer_max_K = phys.c_to_k(float(tank["max_temp_C"]))

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

        greenhouse = self.cfg["geometry"]["greenhouse"]
        soil_area_m2 = greenhouse["width_x"] * greenhouse["depth_y"]
        soil_K = phys.c_to_k(float(a["zones"]["zone_greenhouse_soil"]["soil_target_C"]))
        soil_params = a["greenhouse_soil"]
        losses = a["distribution_losses"]
        indoor_loss_fraction = float(losses["secondary_indoor_pipe_loss_fraction"])
        primary_pipe_loss_fraction = float(losses["primary_indoor_pipe_loss_fraction"])

        hx_data = a["heat_exchanger"]
        hp_data = a["heat_pump"]
        hp_cop = max(1.0, float(hp_data["cop_heating"]))
        hp_max_W = float(hp_data["max_thermal_output_kW"]) * 1000.0
        dry_cooler_capacity_W = float(a["auxiliary_rejection"]["dry_cooler_capacity_kW"]) * 1000.0

        priority: list[str] = defaults["controls"]["buffer_charge_priority"]
        records: list[StepRecord] = []
        totals = {key: 0.0 for key in (
            "it_generated_J", "liquid_captured_J", "air_remaining_J",
            "primary_pipe_loss_J", "hx_transfer_J", "heat_pump_source_J",
            "aux_rejected_J", "primary_unrejected_J", "heat_pump_thermal_J",
            "heat_pump_elec_J", "delivered_J", "unmet_demand_J",
            "secondary_losses_J", "buried_pipe_loss_J", "secondary_rejected_J",
            "buffer_charge_J", "buffer_discharge_J", "buffer_delta_J",
            "tank_standing_loss_J", "pump_elec_J",
        )}

        rack_inventory = expand_rack_ids(self.cfg)
        n_steps = duration_s // dt_s
        for index in range(n_steps):
            t_s = index * dt_s
            hour = (start_hour + t_s / 3600.0) % 24.0
            ambient_C = _ambient_C(hour, ambient_mean_C, ambient_amplitude_C)
            ambient_K = phys.c_to_k(ambient_C)
            load_fraction = _diurnal_load(hour, base_fraction, peak_fraction)
            it_W = total_it_W * load_fraction
            liquid_W = it_W * capture_fraction
            air_W = it_W - liquid_W

            for zone_id, zone in zones.items():
                if zone_id == "zone_greenhouse_soil":
                    zone.demand_W = self._greenhouse_demand_W(
                        soil_K, ambient_K, deep_soil_K, soil_area_m2, zone
                    )
                else:
                    holding_W = max(0.0, zone.envelope_ua_W_K * (zone.setpoint_K - ambient_K))
                    recovery_W = zone.thermal_capacitance_J_K * max(
                        0.0, zone.setpoint_K - zone.temperature_K
                    ) / 21_600.0
                    zone.demand_W = min(zone.design_demand_W, holding_W + recovery_W)
                zone.delivered_W = 0.0
                zone.unmet_W = zone.demand_W
            total_demand_W = sum(zone.demand_W for zone in zones.values())

            # Primary loop: variable flow capped at pump rating. Return water
            # temperature follows Q=m*cp*dT rather than a fixed display value.
            primary_flow = min(
                primary_max_flow,
                phys.mass_flow_for_heat(liquid_W, cp, primary_delta_T),
            )
            primary_return_K = primary_setpoint_K + phys.delta_T_for_heat(
                liquid_W, primary_flow, cp
            )
            primary_pipe_loss_W = liquid_W * primary_pipe_loss_fraction
            hx_hot_in_K = primary_return_K - phys.delta_T_for_heat(
                primary_pipe_loss_W, primary_flow, cp
            )

            # Size secondary flow to current demand plus available tank charge
            # rate; the pump rating is an explicit upper bound.
            standing_loss_W = max(0.0, tank["heat_loss_W_per_K"] * (buffer_K - ambient_K))
            charge_room_W = max(
                0.0,
                (buffer_max_K - buffer_K) * tank_heat_capacity_J_K / dt_s + standing_loss_W,
            )
            charge_capacity_W = min(float(tank["max_charge_kW"]) * 1000.0, charge_room_W)
            estimated_buried_loss_W = max(0.0, phys.buried_pipe_heat_loss_W(
                secondary_target_K,
                deep_soil_K,
                float(losses["buried_pipe_U_W_per_mK"]),
                float(losses["buried_pipe_length_m"]),
            )) if zones["zone_greenhouse_soil"].demand_W > 0.0 else 0.0
            header_requirement_W = (
                total_demand_W + estimated_buried_loss_W
            ) / max(1.0 - indoor_loss_fraction, 1e-6)
            secondary_target_heat_W = min(
                liquid_W,
                header_requirement_W + charge_capacity_W,
            )
            secondary_flow = min(
                secondary_max_flow,
                phys.mass_flow_for_heat(secondary_target_heat_W, cp, secondary_delta_T),
            )

            hx = phys.heat_exchanger_eps_ntu(
                hot_in_K=hx_hot_in_K,
                cold_in_K=secondary_return_K,
                m_hot=primary_flow,
                m_cold=secondary_flow,
                cp_hot=cp,
                cp_cold=cp,
                ua_W_per_K=float(hx_data["ua_W_per_K"]),
                effectiveness_override=float(hx_data["effectiveness"]),
            )
            hx_W = min(hx.q_W, max(0.0, liquid_W - primary_pipe_loss_W))
            hx_primary_out_K = hx_hot_in_K - phys.delta_T_for_heat(hx_W, primary_flow, cp)
            hx_secondary_out_K = secondary_return_K + phys.delta_T_for_heat(hx_W, secondary_flow, cp)

            # Series booster heat pump. Evaporator source heat is explicitly
            # removed from the primary-loop residual; condenser = source + power.
            hp_thermal_W = hp_electric_W = hp_source_W = 0.0
            primary_after_hx_W = max(0.0, liquid_W - primary_pipe_loss_W - hx_W)
            if heat_pump_enabled and secondary_flow > 0.0 and header_requirement_W > hx_W:
                temperature_lift_W = secondary_flow * cp * max(
                    0.0, secondary_target_K - hx_secondary_out_K
                )
                requested_hp_W = min(
                    max(header_requirement_W - hx_W, temperature_lift_W),
                    hp_max_W,
                )
                source_fraction = 1.0 - 1.0 / hp_cop
                source_limited_output_W = (
                    primary_after_hx_W / source_fraction if source_fraction > 1e-9 else requested_hp_W
                )
                hp_thermal_W = min(requested_hp_W, source_limited_output_W)
                hp_electric_W = hp_thermal_W / hp_cop
                hp_source_W = hp_thermal_W - hp_electric_W

            direct_secondary_W = hx_W + hp_thermal_W
            direct_supply_K = hx_secondary_out_K + phys.delta_T_for_heat(
                hp_thermal_W, secondary_flow, cp
            )

            # Capacity-limited auxiliary rejection. Any remainder is reported as
            # unrejected heat instead of silently disappearing.
            primary_residual_W = max(
                0.0,
                liquid_W - primary_pipe_loss_W - hx_W - hp_source_W,
            )
            aux_rejected_W = min(
                primary_residual_W,
                dry_cooler_capacity_W if aux_enabled else 0.0,
            )
            primary_unrejected_W = primary_residual_W - aux_rejected_W
            actual_primary_supply_K = primary_setpoint_K + phys.delta_T_for_heat(
                primary_unrejected_W, primary_flow, cp
            )

            # Buffer discharges only when direct useful heat is below branch
            # requirements, and only above its useful temperature floor.
            useful_floor_K = max(buffer_min_useful_K, secondary_return_K + 0.5)
            stored_available_W = max(
                0.0,
                (buffer_K - useful_floor_K) * tank_heat_capacity_J_K / dt_s - standing_loss_W,
            )
            discharge_capacity_W = min(
                float(tank["max_discharge_kW"]) * 1000.0,
                stored_available_W,
            )
            buffer_discharge_W = 0.0
            required_buffer_supply_K = max(
                (zone.min_supply_K for zone in zones.values() if zone.demand_W > 0.0),
                default=buffer_min_useful_K,
            )
            if buffer_K >= required_buffer_supply_K:
                buffer_discharge_W = min(
                    max(0.0, header_requirement_W - direct_secondary_W),
                    discharge_capacity_W,
                )

            buffer_flow = phys.mass_flow_for_heat(
                buffer_discharge_W,
                cp,
                max(buffer_K - secondary_return_K, 0.0),
            )
            header_flow = secondary_flow + buffer_flow
            if header_flow > 1e-9:
                secondary_supply_K = (
                    secondary_flow * direct_supply_K + buffer_flow * buffer_K
                ) / header_flow
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
                        secondary_supply_K,
                        deep_soil_K,
                        float(losses["buried_pipe_U_W_per_mK"]),
                        float(losses["buried_pipe_length_m"]),
                    ))
                    branch_take_W = min(
                        remaining_W, zone.demand_W + candidate_buried_loss
                    )
                    buried_loss_W = min(candidate_buried_loss, branch_take_W)
                    zone.delivered_W = min(
                        zone.demand_W, max(0.0, branch_take_W - buried_loss_W)
                    )
                else:
                    branch_take_W = min(remaining_W, zone.demand_W)
                    zone.delivered_W = branch_take_W
                zone.unmet_W = max(0.0, zone.demand_W - zone.delivered_W)
                remaining_W -= branch_take_W

            delivered_total_W = sum(zone.delivered_W for zone in zones.values())
            unmet_total_W = sum(zone.unmet_W for zone in zones.values())

            # Lumped zone-air temperatures respond to delivered heat and envelope
            # loss. This is a transparent reduced-order model, not a sensor feed.
            for zone_id, zone in zones.items():
                if zone_id == "zone_greenhouse_soil":
                    continue
                envelope_loss_W = max(0.0, zone.envelope_ua_W_K * (zone.temperature_K - ambient_K))
                zone.temperature_K += (
                    zone.delivered_W - envelope_loss_W
                ) * dt_s / zone.thermal_capacitance_J_K
                zone.temperature_K = min(
                    zone.setpoint_K + 1.0,
                    max(ambient_K, zone.temperature_K),
                )

            buffer_charge_W = min(remaining_W, charge_capacity_W)
            secondary_rejected_W = max(0.0, remaining_W - buffer_charge_W)
            tank_net_W = buffer_charge_W - buffer_discharge_W - standing_loss_W
            new_buffer_K = buffer_K + tank_net_W * dt_s / tank_heat_capacity_J_K
            new_buffer_K = min(buffer_max_K, max(ambient_K, new_buffer_K))
            buffer_delta_W = (new_buffer_K - buffer_K) * tank_heat_capacity_J_K / dt_s
            buffer_K = new_buffer_K

            greenhouse_delta_T = max(secondary_supply_K - secondary_return_K, 1.0)
            greenhouse_flow = min(
                greenhouse_max_flow,
                phys.mass_flow_for_heat(
                    zones["zone_greenhouse_soil"].delivered_W + buried_loss_W,
                    cp,
                    greenhouse_delta_T,
                ),
            )
            soil_K = phys.soil_temperature_step(
                soil_K,
                q_pipe_W=zones["zone_greenhouse_soil"].delivered_W,
                ambient_K=ambient_K,
                deep_soil_K=deep_soil_K,
                area_m2=soil_area_m2,
                dt_s=dt_s,
                u_cover_W_per_m2K=float(soil_params["u_cover_W_per_m2K"]),
                u_ground_W_per_m2K=float(soil_params["u_ground_W_per_m2K"]),
                thermal_mass_J_per_K=float(soil_params["thermal_mass_J_per_K"]),
            )
            zones["zone_greenhouse_soil"].temperature_K = soil_K

            primary_pipe_dp = self._path_pressure_loss("primary", primary_flow, density)
            secondary_pipe_dp = self._path_pressure_loss("secondary", secondary_flow, density)
            greenhouse_pipe_dp = sum(
                phys.pipe_pressure_loss_Pa(
                    greenhouse_flow,
                    segment["diameter_m"],
                    segment["length_m"],
                    density=density,
                )
                for segment in self.network["circuits"]["secondary"]["segments"]
                if segment["id"] in {"pipe_buried_supply_001", "pipe_soil_heating_001", "pipe_buried_return_001"}
            )
            primary_head = min(
                pumps["primary"]["rated_head_Pa"],
                primary_pipe_dp + pumps["primary"]["equipment_allowance_Pa"],
            )
            secondary_head = min(
                pumps["secondary"]["rated_head_Pa"],
                secondary_pipe_dp + pumps["secondary"]["equipment_allowance_Pa"],
            )
            greenhouse_head = min(
                pumps["greenhouse"]["rated_head_Pa"],
                greenhouse_pipe_dp + pumps["greenhouse"]["equipment_allowance_Pa"],
            )
            pump_power_W = sum((
                phys.pump_electrical_power_W(
                    phys.volumetric_from_mass(primary_flow, density),
                    primary_head,
                    pumps["primary"]["efficiency"],
                ),
                phys.pump_electrical_power_W(
                    phys.volumetric_from_mass(secondary_flow, density),
                    secondary_head,
                    pumps["secondary"]["efficiency"],
                ),
                phys.pump_electrical_power_W(
                    phys.volumetric_from_mass(greenhouse_flow, density),
                    greenhouse_head,
                    pumps["greenhouse"]["efficiency"],
                ),
            ))

            distribution_loss_W = indoor_loss_W + buried_loss_W
            secondary_residual_W = (
                direct_secondary_W
                - delivered_total_W
                - distribution_loss_W
                - secondary_rejected_W
                - buffer_delta_W
                - standing_loss_W
            )
            mass_residual_kg_s = (primary_flow - primary_flow) + (header_flow - header_flow)

            pipe_states = self._pipe_states(
                primary_flow, secondary_flow, greenhouse_flow,
                phys.k_to_c(actual_primary_supply_K), phys.k_to_c(primary_return_K),
                phys.k_to_c(hx_secondary_out_K), phys.k_to_c(secondary_supply_K),
                phys.k_to_c(secondary_return_K),
            )
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
            rack_power_W = {
                rack["id"]: rack["nominal_power_kW"] * 1000.0 * load_fraction
                for rack in rack_inventory
            }

            for key, value in {
                "it_generated_J": it_W,
                "liquid_captured_J": liquid_W,
                "air_remaining_J": air_W,
                "primary_pipe_loss_J": primary_pipe_loss_W,
                "hx_transfer_J": hx_W,
                "heat_pump_source_J": hp_source_W,
                "aux_rejected_J": aux_rejected_W,
                "primary_unrejected_J": primary_unrejected_W,
                "heat_pump_thermal_J": hp_thermal_W,
                "heat_pump_elec_J": hp_electric_W,
                "delivered_J": delivered_total_W,
                "unmet_demand_J": unmet_total_W,
                "secondary_losses_J": distribution_loss_W,
                "buried_pipe_loss_J": buried_loss_W,
                "secondary_rejected_J": secondary_rejected_W,
                "buffer_charge_J": buffer_charge_W,
                "buffer_discharge_J": buffer_discharge_W,
                "tank_standing_loss_J": standing_loss_W,
                "pump_elec_J": pump_power_W,
            }.items():
                totals[key] += value * dt_s

            records.append(StepRecord(
                t_s=t_s,
                hour=round(hour, 3),
                gpu_load_fraction=round(load_fraction, 5),
                it_power_W=it_W,
                liquid_captured_W=liquid_W,
                air_remaining_W=air_W,
                hx_transfer_W=hx_W,
                aux_rejected_W=aux_rejected_W,
                primary_unrejected_W=primary_unrejected_W,
                primary_pipe_loss_W=primary_pipe_loss_W,
                heat_pump_source_W=hp_source_W,
                heat_pump_thermal_W=hp_thermal_W,
                heat_pump_elec_W=hp_electric_W,
                delivered_total_W=delivered_total_W,
                unmet_demand_W=unmet_total_W,
                distribution_loss_W=distribution_loss_W,
                buried_pipe_loss_W=buried_loss_W,
                buffer_charge_W=buffer_charge_W,
                buffer_discharge_W=buffer_discharge_W,
                buffer_temp_C=round(phys.k_to_c(buffer_K), 3),
                soil_temp_C=round(phys.k_to_c(soil_K), 3),
                ambient_C=round(ambient_C, 3),
                primary_supply_C=round(phys.k_to_c(actual_primary_supply_K), 3),
                primary_return_C=round(phys.k_to_c(primary_return_K), 3),
                hx_primary_out_C=round(phys.k_to_c(hx_primary_out_K), 3),
                hx_secondary_out_C=round(phys.k_to_c(hx_secondary_out_K), 3),
                secondary_supply_C=round(phys.k_to_c(secondary_supply_K), 3),
                secondary_return_C=round(phys.k_to_c(secondary_return_K), 3),
                primary_mass_flow_kg_s=primary_flow,
                secondary_mass_flow_kg_s=secondary_flow,
                greenhouse_mass_flow_kg_s=greenhouse_flow,
                primary_pressure_loss_Pa=primary_pipe_dp,
                secondary_pressure_loss_Pa=secondary_pipe_dp,
                greenhouse_pressure_loss_Pa=greenhouse_pipe_dp,
                pump_power_W=pump_power_W,
                energy_residual_W=secondary_residual_W,
                mass_residual_kg_s=mass_residual_kg_s,
                zone_demand_W={zone_id: zone.demand_W for zone_id, zone in zones.items()},
                zone_delivered_W={zone_id: zone.delivered_W for zone_id, zone in zones.items()},
                zone_unmet_W={zone_id: zone.unmet_W for zone_id, zone in zones.items()},
                zone_temperature_C={zone_id: round(phys.k_to_c(zone.temperature_K), 3) for zone_id, zone in zones.items()},
                pipe_states=pipe_states,
                sensor_states=sensor_states,
                rack_power_W=rack_power_W,
            ))

        totals["buffer_delta_J"] = (
            buffer_K - buffer_initial_K
        ) * tank_heat_capacity_J_K
        checks = self._conservation_checks(totals, records)
        return {
            "mode": "simplified_physics",
            "executed": True,
            "is_measured_data": False,
            "disclaimer": "Deterministic simplified engineering model; not calibrated and not measured data.",
            "timestep_s": dt_s,
            "duration_s": duration_s,
            "n_steps": len(records),
            "series": [asdict(record) for record in records],
            "energy_totals_J": totals,
            "energy_totals_kWh": {key: value / 3.6e6 for key, value in totals.items()},
            "conservation_checks": checks,
            "summary": self._summary(records, totals),
        }

    @staticmethod
    def _conservation_checks(
        totals: dict[str, float], records: list[StepRecord]
    ) -> dict[str, Any]:
        split_lhs = totals["it_generated_J"]
        split_rhs = totals["liquid_captured_J"] + totals["air_remaining_J"]
        primary_lhs = totals["liquid_captured_J"]
        primary_rhs = sum(totals[key] for key in (
            "primary_pipe_loss_J", "hx_transfer_J", "heat_pump_source_J",
            "aux_rejected_J", "primary_unrejected_J",
        ))
        secondary_lhs = totals["hx_transfer_J"] + totals["heat_pump_thermal_J"]
        secondary_rhs = sum(totals[key] for key in (
            "delivered_J", "secondary_losses_J", "secondary_rejected_J",
            "buffer_delta_J", "tank_standing_loss_J",
        ))
        max_mass_residual = max((abs(record.mass_residual_kg_s) for record in records), default=0.0)
        tolerance = 1e-6

        def check(lhs: float, rhs: float) -> dict[str, float | bool]:
            error = _relative_error(lhs, rhs)
            return {"lhs_J": lhs, "rhs_J": rhs, "relative_error": error, "passed": error <= tolerance}

        return {
            "tolerance_relative": tolerance,
            "capture_split": check(split_lhs, split_rhs),
            "primary_balance": check(primary_lhs, primary_rhs),
            "secondary_balance": check(secondary_lhs, secondary_rhs),
            "mass_balance": {
                "max_residual_kg_s": max_mass_residual,
                "passed": max_mass_residual <= 1e-9,
            },
        }

    @staticmethod
    def _summary(records: list[StepRecord], totals: dict[str, float]) -> dict[str, Any]:
        if not records:
            return {}
        recovered_from_it_J = min(
            totals["delivered_J"],
            totals["hx_transfer_J"] + totals["heat_pump_source_J"],
        )
        capture = totals["liquid_captured_J"]
        return {
            "peak_it_power_kW": max(record.it_power_W for record in records) / 1000.0,
            "mean_it_power_kW": sum(record.it_power_W for record in records) / len(records) / 1000.0,
            "total_it_energy_kWh": totals["it_generated_J"] / 3.6e6,
            "total_delivered_heat_kWh": totals["delivered_J"] / 3.6e6,
            "total_recovered_kWh": recovered_from_it_J / 3.6e6,
            "total_unmet_heat_kWh": totals["unmet_demand_J"] / 3.6e6,
            "total_aux_rejected_kWh": totals["aux_rejected_J"] / 3.6e6,
            "total_primary_unrejected_kWh": totals["primary_unrejected_J"] / 3.6e6,
            "total_distribution_loss_kWh": totals["secondary_losses_J"] / 3.6e6,
            "heat_recovery_efficiency": round(recovered_from_it_J / capture, 4) if capture > 0.0 else 0.0,
            "total_pump_elec_kWh": totals["pump_elec_J"] / 3.6e6,
            "total_heat_pump_elec_kWh": totals["heat_pump_elec_J"] / 3.6e6,
            "final_buffer_temp_C": records[-1].buffer_temp_C,
            "final_soil_temp_C": records[-1].soil_temp_C,
        }


def run_simulation(
    request: dict[str, Any], cfg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Dispatch a run without pretending unavailable external tools executed."""
    mode = request.get("mode", "simplified_physics")
    if mode == "simplified_physics":
        return SimplifiedPhysicsEngine(cfg).run(request)
    if mode in {"openmodelica", "energyplus", "coupled"}:
        return {
            "mode": mode,
            "is_measured_data": False,
            "executed": False,
            "status": "input_generator_available_solver_not_executed",
            "message": (
                f"'{mode}' has input-generation scaffolding only. No external solver "
                "was executed and no result was generated. See modelica/, energyplus/ "
                "and docs/ARCHITECTURE.md."
            ),
        }
    raise ValueError(f"Unknown simulation mode: {mode}")
