// Types mirror the FastAPI scene/simulation contract. World geometry is SI and
// Z-up; conversion to Three.js Y-up happens only in three/coordinates.ts.

export type SimMode = "simplified_physics" | "openmodelica" | "energyplus" | "coupled";
export type WorldPoint = [number, number, number];

export interface SceneObject {
  id: string;
  kind: string;
  type: string;
  center?: WorldPoint;
  size?: WorldPoint;
  floor_id?: string;
  name?: string;
  use?: string;
  z_range?: [number, number];
  nominal_power_kW?: number;
  rated_power_kW?: number;
  opacity?: number;
  zone?: string;
  role?: string;
  roof?: string;
  [key: string]: unknown;
}

export interface ScenePipe {
  id: string;
  kind: "pipe";
  type: "pipe";
  circuit: "primary" | "secondary";
  from: string;
  to: string;
  role?: string;
  color?: string;
  length_m?: number;
  diameter_m?: number;
  buried?: boolean;
  branch_fraction?: number;
  points: WorldPoint[];
}

export interface Scene {
  site_id: string;
  name: string;
  units: string;
  axes: { x: string; y: string; z: string };
  objects: SceneObject[];
  pipes: ScenePipe[];
  counts: {
    objects: number;
    pipes: number;
    gpu_racks: number;
    floors?: number;
    sensors?: number;
  };
}

export interface PipeState {
  mass_flow_kg_s: number;
  temperature_C: number;
}

export interface SensorState {
  value: number | string;
  unit: string;
}

export interface StepRecord {
  t_s: number;
  hour: number;
  gpu_load_fraction: number;
  it_power_W: number;
  liquid_captured_W: number;
  air_remaining_W: number;
  hx_transfer_W: number;
  aux_rejected_W: number;
  primary_unrejected_W: number;
  primary_pipe_loss_W: number;
  heat_pump_source_W: number;
  heat_pump_thermal_W: number;
  heat_pump_elec_W: number;
  delivered_total_W: number;
  unmet_demand_W: number;
  distribution_loss_W: number;
  buried_pipe_loss_W: number;
  buffer_charge_W: number;
  buffer_discharge_W: number;
  buffer_temp_C: number;
  soil_temp_C: number;
  ambient_C: number;
  primary_supply_C: number;
  primary_return_C: number;
  hx_primary_out_C: number;
  hx_secondary_out_C: number;
  secondary_supply_C: number;
  secondary_return_C: number;
  primary_mass_flow_kg_s: number;
  secondary_mass_flow_kg_s: number;
  greenhouse_mass_flow_kg_s: number;
  primary_pressure_loss_Pa: number;
  secondary_pressure_loss_Pa: number;
  greenhouse_pressure_loss_Pa: number;
  pump_power_W: number;
  energy_residual_W: number;
  mass_residual_kg_s: number;
  zone_demand_W: Record<string, number>;
  zone_delivered_W: Record<string, number>;
  zone_unmet_W: Record<string, number>;
  zone_temperature_C: Record<string, number>;
  pipe_states: Record<string, PipeState>;
  sensor_states: Record<string, SensorState>;
  rack_power_W: Record<string, number>;
}

export interface ConservationCheck {
  lhs_J: number;
  rhs_J: number;
  relative_error: number;
  passed: boolean;
}

export interface SimulationResult {
  run_id: string;
  mode: SimMode;
  is_measured_data: boolean;
  disclaimer?: string;
  executed: boolean;
  status?: string;
  message?: string;
  timestep_s?: number;
  duration_s?: number;
  n_steps?: number;
  series?: StepRecord[];
  energy_totals_J?: Record<string, number>;
  energy_totals_kWh?: Record<string, number>;
  conservation_checks?: {
    tolerance_relative: number;
    capture_split: ConservationCheck;
    primary_balance: ConservationCheck;
    secondary_balance: ConservationCheck;
    mass_balance?: { max_residual_kg_s: number; passed: boolean };
  };
  summary?: Record<string, number>;
}

export interface SimulationRequest {
  mode?: SimMode;
  scenario_id?: string;
  duration_s?: number;
  timestep_s?: number;
  start_hour?: number;
  total_it_power_kW?: number;
  liquid_capture_fraction?: number;
  gpu_load_base_fraction?: number;
  gpu_load_peak_fraction?: number;
  ambient_mean_C?: number;
  heat_pump_enabled?: boolean;
  aux_rejection_enabled?: boolean;
  overrides?: Record<string, unknown>;
}

export interface AppConfig {
  units: any;
  site: any;
  geometry: any;
  equipment: any;
  network: any;
  assumptions: any;
  simulation: any;
}
