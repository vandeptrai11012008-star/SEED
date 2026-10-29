import { useEffect } from "react";
import { useOps, type OpsTab } from "./opsStore";
import { Overview } from "./panels/Overview";
import { Agents } from "./panels/Agents";
import { TimelinePanel } from "./panels/TimelinePanel";
import { Lab } from "./panels/Lab";
import { ComparePanel } from "./panels/ComparePanel";
import "./ops.css";

const TABS: { id: OpsTab; label: string }[] = [
  { id: "overview", label: "Dashboard" },
  { id: "agents", label: "8 Agents" },
  { id: "timeline", label: "Event log" },
];

const ADVANCED_TABS: { id: OpsTab; label: string }[] = [
  { id: "lab", label: "Forecast lab" },
  { id: "compare", label: "Compare A/B/C" },
];

const MODE_HELP: Record<string, string> = {
  A: "Fixed baseline rules — a useful reference for comparing the agents.",
  B: "Eight agents coordinate using live readings, without a forecast.",
  C: "Agents use short-horizon look-ahead planning with independent safety checks.",
};

const MODE_LABELS: Record<string, string> = {
  A: "A · Fixed rules (no agents)",
  B: "B · Agents react to changes",
  C: "C · Agents + forecast",
};

export default function OpsApp() {
  const init = useOps((s) => s.init);
  const loading = useOps((s) => s.loading);
  const error = useOps((s) => s.error);
  const meta = useOps((s) => s.meta);
  const tab = useOps((s) => s.tab);
  const setTab = useOps((s) => s.setTab);

  useEffect(() => {
    void init();
    // ?autostart=1 begins stepping automatically once the session is ready
    // (handy for demos and headless capture).
    const params = new URLSearchParams(window.location.search);
    if (params.get("autostart") === "1") {
      const t = window.setTimeout(() => { void useOps.getState().stepOnce(16); }, 1200);
      return () => { window.clearTimeout(t); useOps.getState().pause(); };
    }
    // Stop the player if this view unmounts so no interval keeps hitting the
    // API after the component is gone.
    return () => { useOps.getState().pause(); };
  }, [init]);

  return (
    <div className="ops">
      <header className="ops-header">
        <div className="ops-brand">
          <span className="ops-eyebrow">THERMALLOOP / CONTROL ROOM</span>
          <h1>AI Agent Operations Center</h1>
          <p className="ops-sub">
            Test scenarios, inspect decisions and compare control strategies.
            {meta ? ` Model ${meta.model_version}.` : ""}
          </p>
        </div>
        <div className="ops-header-actions">
          <span className={`ops-simulation-badge ${meta?.real_device_enabled ? "unsafe" : ""}`}>
            {meta?.real_device_enabled ? "HARDWARE ENABLED" : "● SIMULATION ONLY"}
          </span>
          <a className="ops-link" href="?">← Back to 3D</a>
        </div>
      </header>

      <SessionBar />

      <nav className="ops-tabs" aria-label="Operations pages">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
          >
            {t.label}
          </button>
        ))}
        <details className="ops-more-tabs">
          <summary>⚙ More experiments</summary>
          <div className="ops-more-choices">
            {ADVANCED_TABS.map((t) => (
              <button key={t.id} className={tab === t.id ? "active" : ""}
                onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}>
                {t.label}
              </button>
            ))}
          </div>
        </details>
      </nav>

      {loading && <div className="ops-note" role="status">Connecting to the operations engine…</div>}
      {error && <div className="ops-error" role="alert">Connection or simulation error: {error}</div>}

      <main className="ops-main">
        {tab === "overview" && <Overview />}
        {tab === "agents" && <Agents />}
        {tab === "timeline" && <TimelinePanel />}
        {tab === "lab" && <Lab />}
        {tab === "compare" && <ComparePanel />}
      </main>

      <footer className="ops-footer">
        Simulation only · Simplified physics model · Not calibrated against measured data.
      </footer>
    </div>
  );
}

function SessionBar() {
  // Each selector returns a single primitive. Returning a fresh object from a
  // Zustand v5 selector causes an infinite render loop (the old code did that,
  // which blanked the whole page).
  const meta = useOps((s) => s.meta);
  const mode = useOps((s) => s.mode);
  const scenario = useOps((s) => s.scenario);
  const seed = useOps((s) => s.seed);
  const speed = useOps((s) => s.speed);
  const running = useOps((s) => s.running);
  const busy = useOps((s) => s.busy);
  const loading = useOps((s) => s.loading);
  const sessionId = useOps((s) => s.sessionId);
  const appliedConfig = useOps((s) => s.appliedConfig);
  const totalSteps = useOps((s) => s.totalSteps);
  const events = useOps((s) => s.events);
  const configure = useOps((s) => s.configure);
  const startSession = useOps((s) => s.startSession);
  const stepOnce = useOps((s) => s.stepOnce);
  const pause = useOps((s) => s.pause);
  const reports = useOps((s) => s.reports);
  const cost = useOps((s) => s.coordinatorCost);
  const last = reports[reports.length - 1];
  const pending = Boolean(appliedConfig && (mode !== appliedConfig.mode || scenario !== appliedConfig.scenario || seed !== appliedConfig.seed));
  const canStep = Boolean(sessionId && !busy && !running && !pending);
  const status = loading ? "Connecting" : !sessionId ? "No session" : running ? "Running" : busy ? "Calculating" : pending ? "New settings selected" : "Paused / ready";
  const statusTone = running ? "running" : !sessionId ? "idle" : busy ? "working" : "ready";

  const exportVisibleData = () => {
    if (!reports.length) return;
    const payload = {
      exported_at: new Date().toISOString(),
      model_version: meta?.model_version,
      source: "simplified_physics_simulation",
      is_measured_data: false,
      scope: "last 400 stored steps and last 500 events",
      config: appliedConfig,
      total_steps: totalSteps,
      coordinator_cost_branch_steps: cost,
      reports,
      events,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `thermalloop-ops-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const prepareSession = async () => {
    if (pending || !useOps.getState().sessionId) await startSession();
    return Boolean(useOps.getState().sessionId);
  };

  const runOrPause = async () => {
    if (running) { pause(); return; }
    if (await prepareSession()) useOps.getState().play();
  };

  const runOneHour = async () => {
    if (await prepareSession()) await useOps.getState().stepOnce(6);
  };

  return (
    <section className="ops-command" aria-label="Simulation control panel">
      <div className="ops-command-head">
        <div>
          <span className="ops-eyebrow">SIMULATION CONTROLS</span>
          <h2>Simulation controls</h2>
          <p>Select a strategy and scenario to evaluate the simulated system response.</p>
        </div>
        <div className={`ops-run-status ${statusTone}`} role="status" aria-live="polite">
          <span className="ops-status-dot" /> {status}
        </div>
      </div>

      <div className="ops-command-body">
        <div className="ops-fields">
          <label>Control strategy
            <select value={mode} disabled={running || busy || loading} onChange={(e) => configure({ mode: e.target.value })}>
              {Object.entries(meta?.modes ?? { A: "Rules", B: "Agents", C: "Agents + forecast" }).map(([k, v]) => (
                <option key={k} value={k}>{MODE_LABELS[k] ?? `${k} · ${v}`}</option>
              ))}
            </select>
          </label>
          <label>Test scenario
            <select value={scenario} disabled={running || busy || loading} onChange={(e) => configure({ scenario: e.target.value })}>
              {Object.entries(meta?.scenarios ?? { ai_load_spike: "AI load spike" }).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="ops-actions">
          <button className="ops-run-button primary" disabled={busy || loading} onClick={() => void runOrPause()}>
            {running ? "⏸ Pause" : "▶ Auto run"}
          </button>
          <button disabled={busy || loading || running} onClick={() => void runOneHour()}>▶ Run 1 hour</button>
        </div>
      </div>

      <details className="ops-advanced">
        <summary>⚙ Advanced controls</summary>
        <div className="ops-advanced-body">
          <div className="ops-fields ops-advanced-fields">
            <label>Random seed
              <input type="number" value={seed} disabled={running || busy || loading}
                onChange={(e) => configure({ seed: Number(e.target.value) })} />
            </label>
            <label>Run speed
              <select value={speed} onChange={(e) => configure({ speed: Number(e.target.value) })}>
                <option value={1}>1 step / tick</option>
                <option value={2}>2 steps / tick</option>
                <option value={4}>4 steps / tick</option>
                <option value={8}>8 steps / tick</option>
              </select>
            </label>
          </div>
          <div className="ops-advanced-actions">
            <button disabled={!canStep} onClick={() => void stepOnce(1)}>+1 step</button>
            <button disabled={!canStep} onClick={() => void stepOnce(10)}>+10 steps</button>
            <button disabled={busy || loading || running} onClick={() => void startSession()}>
              {pending ? "✓ Apply new settings" : "↻ Reset test"}
            </button>
            <button disabled={reports.length === 0} onClick={exportVisibleData} title="Download retained simulation steps and events as JSON">
              ↓ Export JSON
            </button>
          </div>
        </div>
      </details>

      <div className="ops-command-foot">
        <p className={`ops-config-note ${pending ? "pending" : ""}`}>
          {pending ? "New selections are ready. Press Auto run or Run 1 hour to start a fresh test." : MODE_HELP[mode]}
        </p>
        <div className="ops-session-stats">
          <span>Step <strong>{totalSteps}</strong></span>
          <span>Simulated time <strong>{last ? `${last.hour.toFixed(1)} h` : "—"}</strong></span>
          <span>Events <strong>{events.length}</strong></span>
          <span>Look-ahead cost <strong>{cost}</strong></span>
        </div>
      </div>
    </section>
  );
}
