// Client for the autonomous operations API (/api/ops/*).
// BASE mirrors the main client: "" in dev (Vite proxy), VITE_API_BASE in prod.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return (await res.json()) as T;
}

export interface OpsMeta {
  model_version: string;
  modes: Record<string, string>;
  scenarios: Record<string, string>;
  agents: { name: string; owns: string[] }[];
  ownership: Record<string, string>;
  actuator_ranges: Record<string, [number, number]>;
  real_device_enabled: boolean;
}

export interface StepReport {
  index: number;
  t_s: number;
  hour: number;
  scenario_label: string;
  metrics: {
    gpu_load_fraction: number;
    primary_supply_C: number;
    secondary_supply_C: number;
    buffer_temp_C: number;
    soil_temp_C: number;
    delivered_total_W: number;
    unmet_demand_W: number;
    pump_power_W: number;
    heat_pump_elec_W: number;
    primary_unrejected_W: number;
    zone_temperature_C: Record<string, number>;
  };
  decisions: any[];
  safety_events: any[];
  faults: any[];
  proposals: any[];
}

export interface BusEvent {
  seq: number;
  t_s: number;
  type: string;
  source: string;
  topic: string;
  payload: Record<string, any>;
}

export interface Comparison {
  scenario: string;
  seed: number;
  n_steps: number;
  model_version: string;
  per_mode: Record<string, Record<string, number>>;
  verdict: Record<string, any> & { _notes: string[]; _honesty: string };
  cmp_id?: string;
}

export const ops = {
  meta: () => fetch(`${BASE}/api/ops/meta`).then((r) => j<OpsMeta>(r)),

  createSession: (body: {
    mode: string; scenario: string; seed: number; timestep_s?: number;
    start_hour?: number; drivers?: Record<string, number>;
  }) =>
    fetch(`${BASE}/api/ops/session`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => j<{ session_id: string; mode: string; scenario: string; seed: number; model_version: string }>(r)),

  tick: (sid: string, steps: number) =>
    fetch(`${BASE}/api/ops/session/${sid}/tick`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ steps }),
    }).then((r) => j<{ reports: StepReport[]; coordinator_cost_branch_steps: number; total_steps: number }>(r)),

  events: (sid: string, sinceSeq = -1) =>
    fetch(`${BASE}/api/ops/session/${sid}/events?since_seq=${sinceSeq}`).then(
      (r) => j<{ events: BusEvent[]; latest_seq: number }>(r)),

  deleteSession: (sid: string) =>
    fetch(`${BASE}/api/ops/session/${sid}`, { method: "DELETE" }).then((r) => j<{ deleted: boolean }>(r)),

  compare: (body: {
    scenario: string; seed: number; n_steps: number; timestep_s?: number;
    drivers?: Record<string, number>; persist?: boolean;
  }) =>
    fetch(`${BASE}/api/ops/compare`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => j<Comparison>(r)),

  comparisons: () => fetch(`${BASE}/api/ops/comparisons`).then((r) => j<{ comparisons: any[] }>(r)),
  experiments: () => fetch(`${BASE}/api/ops/experiments`).then((r) => j<{ experiments: any[] }>(r)),
};
