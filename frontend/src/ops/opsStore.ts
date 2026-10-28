import { create } from "zustand";
import { ops, type BusEvent, type Comparison, type OpsMeta, type StepReport } from "./opsClient";

export type OpsTab = "overview" | "agents" | "timeline" | "lab" | "compare";

interface OpsState {
  meta?: OpsMeta;
  loading: boolean;
  error?: string;

  // session config
  sessionId?: string;
  mode: string;
  scenario: string;
  seed: number;
  speed: number;          // steps advanced per tick of the player
  running: boolean;

  // live data
  reports: StepReport[];
  events: BusEvent[];
  latestSeq: number;
  coordinatorCost: number;

  // comparison
  comparison?: Comparison;
  comparing: boolean;

  // actions
  tab: OpsTab;
  setTab: (t: OpsTab) => void;

  init: () => Promise<void>;
  configure: (p: Partial<Pick<OpsState, "mode" | "scenario" | "seed" | "speed">>) => void;
  startSession: () => Promise<void>;
  stepOnce: (steps?: number) => Promise<void>;
  play: () => void;
  pause: () => void;
  reset: () => Promise<void>;
  runCompare: (nSteps: number) => Promise<void>;
}

let _timer: number | undefined;

export const useOps = create<OpsState>((set, get) => ({
  loading: true,
  mode: "C",
  scenario: "ai_load_spike",
  seed: 7,
  speed: 2,
  running: false,
  reports: [],
  events: [],
  latestSeq: -1,
  coordinatorCost: 0,
  comparing: false,
  tab: "overview",

  setTab: (t) => set({ tab: t }),

  init: async () => {
    try {
      const meta = await ops.meta();
      set({ meta, loading: false });
      await get().startSession();
    } catch (e: any) {
      set({ loading: false, error: String(e?.message ?? e) });
    }
  },

  configure: (p) => set(p),

  startSession: async () => {
    const { mode, scenario, seed } = get();
    get().pause();
    if (get().sessionId) {
      try { await ops.deleteSession(get().sessionId!); } catch { /* ignore */ }
    }
    try {
      const s = await ops.createSession({ mode, scenario, seed, timestep_s: 600 });
      set({ sessionId: s.session_id, reports: [], events: [], latestSeq: -1, coordinatorCost: 0, error: undefined });
    } catch (e: any) {
      set({ error: String(e?.message ?? e) });
    }
  },

  stepOnce: async (steps) => {
    const sid = get().sessionId;
    if (!sid) return;
    const n = steps ?? get().speed;
    try {
      const res = await ops.tick(sid, n);
      const ev = await ops.events(sid, get().latestSeq);
      set((st) => ({
        reports: [...st.reports, ...res.reports].slice(-400),
        coordinatorCost: res.coordinator_cost_branch_steps,
        events: [...st.events, ...ev.events].slice(-500),
        latestSeq: ev.latest_seq,
      }));
    } catch (e: any) {
      set({ error: String(e?.message ?? e), running: false });
      get().pause();
    }
  },

  play: () => {
    if (get().running) return;
    // Always clear any stray timer first (guards against StrictMode double
    // mount or a leaked interval) before starting a new one.
    if (_timer) { window.clearInterval(_timer); _timer = undefined; }
    set({ running: true });
    // One step per tick; cadence stays fixed so each advance is visible. The
    // "speed" setting controls how many steps advance per tick via stepOnce.
    _timer = window.setInterval(() => { void get().stepOnce(); }, 700);
  },

  pause: () => {
    if (_timer) { window.clearInterval(_timer); _timer = undefined; }
    set({ running: false });
  },

  reset: async () => {
    await get().startSession();
  },

  runCompare: async (nSteps) => {
    const { scenario, seed } = get();
    set({ comparing: true, error: undefined });
    try {
      const cmp = await ops.compare({ scenario, seed, n_steps: nSteps, persist: true });
      set({ comparison: cmp, comparing: false });
    } catch (e: any) {
      set({ comparing: false, error: String(e?.message ?? e) });
    }
  },
}));
