import type {
  AppConfig,
  Scene,
  SimulationRequest,
  SimulationResult,
} from "./types";

// In dev, BASE is "" so Vite proxies /api to http://127.0.0.1:8000.
// In production, set VITE_API_BASE to the deployed backend URL
// (e.g. https://thermalloop-backend.onrender.com). Trailing slash is trimmed.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then((r) => j<{ status: string }>(r)),
  config: () => fetch(`${BASE}/api/config`).then((r) => j<AppConfig>(r)),
  scene: () => fetch(`${BASE}/api/scene`).then((r) => j<Scene>(r)),
  state: () => fetch(`${BASE}/api/state`).then((r) => j<any>(r)),
  simulate: (req: SimulationRequest) =>
    fetch(`${BASE}/api/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then((r) => j<SimulationResult>(r)),
  results: (runId: string) =>
    fetch(`${BASE}/api/results/${runId}`).then((r) => j<SimulationResult>(r)),
};
