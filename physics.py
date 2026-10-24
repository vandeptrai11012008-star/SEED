"""Core engineering physics primitives for ThermalLoop.

All functions use SI units internally:
  temperature in kelvin (K) unless the name says _C,
  power in watts (W), energy in joules (J), mass flow in kg/s,
  cp in J/(kg.K), density in kg/m3, pressure in Pa, length in m.

Every model here is a clearly labeled simplified engineering model.
None of these functions invent random values; they are deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# Unit helpers
# ----------------------------------------------------------------------------
ABS_ZERO_OFFSET = 273.15


def c_to_k(t_c: float) -> float:
    return t_c + ABS_ZERO_OFFSET


def k_to_c(t_k: float) -> float:
    return t_k - ABS_ZERO_OFFSET


# ----------------------------------------------------------------------------
# Sensible heat:  Q = m_dot * cp * dT
# ----------------------------------------------------------------------------
def sensible_heat_W(m_dot: float, cp: float, delta_T: float) -> float:
    """Sensible heat rate [W] for a flow with mass flow m_dot [kg/s]."""
    return m_dot * cp * delta_T


def mass_flow_for_heat(Q_W: float, cp: float, delta_T: float) -> float:
    """Required mass flow [kg/s] to carry Q_W across delta_T.

    Returns 0 for non-positive delta_T to avoid division blow-up; caller
    should treat that as "no usable flow".
    """
    if delta_T <= 1e-9:
        return 0.0
    return Q_W / (cp * delta_T)


def delta_T_for_heat(Q_W: float, m_dot: float, cp: float) -> float:
    """Temperature change [K] produced by heat Q_W on flow m_dot."""
    if m_dot <= 1e-12:
        return 0.0
    return Q_W / (m_dot * cp)


# ----------------------------------------------------------------------------
# Heat exchanger - effectiveness-NTU (simplified, equal-ish streams)
# ----------------------------------------------------------------------------
@dataclass
class HXResult:
    q_W: float
    hot_out_K: float
    cold_out_K: float
    effectiveness: float


def heat_exchanger_eps_ntu(
    hot_in_K: float,
    cold_in_K: float,
    m_hot: float,
    m_cold: float,
    cp_hot: float,
    cp_cold: float,
    ua_W_per_K: float,
    effectiveness_override: float | None = None,
) -> HXResult:
    """Counterflow heat exchanger via effectiveness-NTU.

    If effectiveness_override is provided it is used directly (useful when a
    manufacturer effectiveness is known). Otherwise effectiveness is computed
    from UA using the counterflow correlation.
    """
    C_hot = m_hot * cp_hot
    C_cold = m_cold * cp_cold
    C_min = min(C_hot, C_cold)
    C_max = max(C_hot, C_cold)

    if C_min <= 1e-9:
        return HXResult(0.0, hot_in_K, cold_in_K, 0.0)

    if effectiveness_override is not None:
        eps = max(0.0, min(1.0, effectiveness_override))
    else:
        ntu = ua_W_per_K / C_min
        cr = C_min / C_max
        if abs(cr - 1.0) < 1e-6:
            eps = ntu / (1.0 + ntu)
        else:
            ex = math.exp(-ntu * (1.0 - cr))
            eps = (1.0 - ex) / (1.0 - cr * ex)
        eps = max(0.0, min(1.0, eps))

    q_max = max(0.0, C_min * (hot_in_K - cold_in_K))
    q = eps * q_max
    hot_out = hot_in_K - q / C_hot
    cold_out = cold_in_K + q / C_cold
    return HXResult(q, hot_out, cold_out, eps)


# ----------------------------------------------------------------------------
# Pump hydraulics
# ----------------------------------------------------------------------------
def pump_electrical_power_W(
    volumetric_flow_m3_s: float, head_Pa: float, efficiency: float
) -> float:
    """Pump shaft/electrical power [W]: P = V_dot * dP / eta."""
    if efficiency <= 1e-6:
        return 0.0
    return volumetric_flow_m3_s * head_Pa / efficiency


def volumetric_from_mass(m_dot: float, density: float) -> float:
    if density <= 1e-9:
        return 0.0
    return m_dot / density


# ----------------------------------------------------------------------------
# Pipe friction (Darcy-Weisbach with Swamee-Jain friction factor)
# ----------------------------------------------------------------------------
def pipe_pressure_loss_Pa(
    m_dot: float,
    diameter_m: float,
    length_m: float,
    density: float = 997.0,
    viscosity_Pa_s: float = 0.001,
    roughness_m: float = 4.5e-5,
) -> float:
    """Darcy-Weisbach pressure loss for a round pipe [Pa]."""
    if m_dot <= 1e-9 or diameter_m <= 1e-6:
        return 0.0
    area = math.pi * (diameter_m ** 2) / 4.0
    velocity = (m_dot / density) / area
    Re = density * velocity * diameter_m / viscosity_Pa_s
    if Re < 2300:
        f = 64.0 / max(Re, 1e-6)
    else:
        # Swamee-Jain explicit approximation of Colebrook
        term = (roughness_m / (3.7 * diameter_m)) + (5.74 / (Re ** 0.9))
        f = 0.25 / (math.log10(term) ** 2)
    return f * (length_m / diameter_m) * 0.5 * density * velocity ** 2


# ----------------------------------------------------------------------------
# Buried pipe heat loss to soil
# ----------------------------------------------------------------------------
def buried_pipe_heat_loss_W(
    water_temp_K: float, soil_temp_K: float, u_W_per_mK: float, length_m: float
) -> float:
    """Steady heat loss from a buried insulated pipe to soil [W].

    Simplified linear model: Q = U' * L * (T_water - T_soil), where U' is an
    effective loss coefficient per unit length [W/(m.K)].
    """
    return u_W_per_mK * length_m * (water_temp_K - soil_temp_K)


# ----------------------------------------------------------------------------
# Thermal storage tank (lumped, single node)
# ----------------------------------------------------------------------------
def tank_temperature_step(
    temp_K: float,
    q_in_W: float,
    q_out_W: float,
    ambient_K: float,
    volume_m3: float,
    dt_s: float,
    density: float = 997.0,
    cp: float = 4186.0,
    loss_W_per_K: float = 25.0,
) -> float:
    """Advance a lumped thermal tank one timestep (explicit Euler).

    q_in_W charges the tank, q_out_W discharges it, standing loss to ambient
    proportional to (T - T_ambient).
    """
    mass = density * volume_m3
    heat_cap = mass * cp
    if heat_cap <= 1e-6:
        return temp_K
    q_loss = loss_W_per_K * (temp_K - ambient_K)
    dTdt = (q_in_W - q_out_W - q_loss) / heat_cap
    return temp_K + dTdt * dt_s


# ----------------------------------------------------------------------------
# Greenhouse soil lumped energy balance
# ----------------------------------------------------------------------------
def soil_temperature_step(
    soil_K: float,
    q_pipe_W: float,
    ambient_K: float,
    deep_soil_K: float,
    area_m2: float,
    dt_s: float,
    u_cover_W_per_m2K: float = 6.0,
    u_ground_W_per_m2K: float = 1.5,
    thermal_mass_J_per_K: float = 4.0e7,
) -> float:
    """Advance greenhouse soil node one timestep.

    Gains: pipe heat injection. Losses: through cover to ambient air and down
    to deep ground.
    """
    q_cover = u_cover_W_per_m2K * area_m2 * (soil_K - ambient_K)
    q_ground = u_ground_W_per_m2K * area_m2 * (soil_K - deep_soil_K)
    dTdt = (q_pipe_W - q_cover - q_ground) / max(thermal_mass_J_per_K, 1.0)
    return soil_K + dTdt * dt_s


# ----------------------------------------------------------------------------
# Heating demand (temperature dependent)
# ----------------------------------------------------------------------------
def zone_heat_demand_W(
    design_demand_W: float,
    setpoint_K: float,
    ambient_K: float,
    design_ambient_K: float = c_to_k(-10.0),
    design_indoor_K: float = c_to_k(21.0),
) -> float:
    """Temperature-dependent heating demand via degree ratio.

    Scales the design demand by the ratio of current to design temperature
    difference, clamped to [0, design_demand].
    """
    design_dT = design_indoor_K - design_ambient_K
    if design_dT <= 1e-6:
        return 0.0
    cur_dT = setpoint_K - ambient_K
    frac = max(0.0, cur_dT / design_dT)
    return max(0.0, min(design_demand_W, frac * design_demand_W))


# ----------------------------------------------------------------------------
# Heat pump
# ----------------------------------------------------------------------------
@dataclass
class HeatPumpResult:
    thermal_out_W: float
    electrical_in_W: float
    cop: float


def heat_pump_upgrade(
    thermal_demand_W: float, cop_heating: float, max_output_W: float
) -> HeatPumpResult:
    """Heat pump providing up to max_output_W of upgraded heat."""
    q = max(0.0, min(thermal_demand_W, max_output_W))
    cop = max(1.0, cop_heating)
    elec = q / cop
    return HeatPumpResult(q, elec, cop)
