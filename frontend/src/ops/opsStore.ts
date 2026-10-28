import { create } from "zustand";
import { ops, type BusEvent, type Comparison, type OpsMeta, type StepReport } from "./opsClient";

export type OpsTab = "overview" | "agents" | "timeline" | "lab" | "compare";

interface AppliedConfig {
  mode: string;
  scenario: string;
  seed: number;
}

interface OpsState {
  meta?: OpsMeta;
  loading: boolean;
  busy: boolean;
  error?: string;

  // session config
  sessionId?: string;
  mode: string;
  scenario: string;
  seed: number;
  speed: number;          // steps advanced per tick of the player
  running: boolean;
  appliedConfig?: AppliedConfig;

  // live data
  reports: StepReport[];
  events: BusEvent[];
  latestSeq: number;
  coordinatorCost: number;
  totalSteps: number;

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
let _initPromise: Promise<void> | undefined;

export const useOps = create<OpsState>((set, get) => ({
  loading: true,
  busy: false,
  mode: "C",
  scenario: "ai_load_spike",
  seed: 7,
  speed: 2,
  running: false,
  appliedConfig: undefined,
  reports: [],
  events: [],
  latestSeq: -1,
  coordinatorCost: 0,
  totalSteps: 0,
  comparing: false,
  tab: "overview",

  setTab: (t) => set({ tab: t }),

  init: async () => {
    if (get().meta && get().sessionId) {
      set({ loading: false });
      return;
    }
    // React StrictMode may mount twice; both mounts share one initial request.
    if (_initPromise) return _initPromise;
    _initPromise = (async () => {
      try {
        const meta = await ops.meta();
        set({ meta });
        await get().startSession();
      } catch (e: any) {
        set({ error: String(e?.message ?? e) });
      } finally {
        set({ loading: false });
      }
    })();
    try { await _initPromise; } finally { _initPromise = undefined; }
  },

  configure: (p) => set(p),

  startSession: async () => {
    if (get().busy) return;
    const { mode, scenario, seed } = get();
    get().pause();
    const previousId = get().sessionId;
    set({ busy: true, sessionId: undefined, error: undefined });
    if (previousId) {
      try { await ops.deleteSession(previousId); } catch { /* best effort */ }
    }
    try {
      const s = await ops.createSession({ mode, scenario, seed, timestep_s: 600 });
      set({
        sessionId: s.session_id, appliedConfig: { mode, scenario, seed },
        reports: [], events: [], latestSeq: -1, coordinatorCost: 0,
        totalSteps: 0, error: undefined,
      });
    } catch (e: any) {
      set({ error: String(e?.message ?? e) });
    } finally {
      set({ busy: false });
    }
  },

  stepOnce: async (steps) => {
    const { sessionId: sid, appliedConfig, mode, scenario, seed } = get();
    if (!sid || get().busy) return;
    if (!appliedConfig || mode !== appliedConfig.mode || scenario !== appliedConfig.scenario || seed !== appliedConfig.seed) return;
    const n = Math.max(1, Math.min(500, Math.floor(steps ?? get().speed)));
    set({ busy: true });
    try {
      const res = await ops.tick(sid, n);
      const ev = await ops.events(sid, get().latestSeq);
      if (get().sessionId !== sid) return;
      set((st) => ({
        reports: [...st.reports, ...res.reports].slice(-400),
        coordinatorCost: res.coordinator_cost_branch_steps,
        totalSteps: res.total_steps,
        events: [...st.events, ...ev.events].slice(-500),
        latestSeq: ev.latest_seq,
        error: undefined,
      }));
    } catch (e: any) {
      set({ error: String(e?.message ?? e), running: false });
      get().pause();
    } finally {
      if (get().sessionId === sid) set({ busy: false });
    }
  },

  play: () => {
    const st = get();
    if (st.running || st.busy || !st.sessionId || !st.appliedConfig) return;
    if (st.mode !== st.appliedConfig.mode || st.scenario !== st.appliedConfig.scenario || st.seed !== st.appliedConfig.seed) return;
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
    if (get().comparing) return;
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
