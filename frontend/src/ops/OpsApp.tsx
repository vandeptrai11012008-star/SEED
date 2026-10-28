import { useEffect } from "react";
import { useOps, type OpsTab } from "./opsStore";
import { Overview } from "./panels/Overview";
import { Agents } from "./panels/Agents";
import { TimelinePanel } from "./panels/TimelinePanel";
import { Lab } from "./panels/Lab";
import { ComparePanel } from "./panels/ComparePanel";
import "./ops.css";

const TABS: { id: OpsTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "agents", label: "Agents" },
  { id: "timeline", label: "Event timeline" },
  { id: "lab", label: "Lab · predicted vs measured" },
  { id: "compare", label: "Control-mode comparison" },
];

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
        <div>
          <h1>ThermaLoop · Autonomous Operations Center</h1>
          <p className="ops-sub">
            Multi-agent control over a deterministic physics twin.{" "}
            {meta ? `model ${meta.model_version}` : ""} · real-device control{" "}
            <strong>{meta?.real_device_enabled ? "ENABLED" : "disabled"}</strong>
          </p>
        </div>
        <a className="ops-link" href="?">← 3D twin</a>
      </header>

      <SessionBar />

      <nav className="ops-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {loading && <div className="ops-note">Loading operations layer…</div>}
      {error && <div className="ops-error">Error: {error}</div>}

      <main className="ops-main">
        {tab === "overview" && <Overview />}
        {tab === "agents" && <Agents />}
        {tab === "timeline" && <TimelinePanel />}
        {tab === "lab" && <Lab />}
        {tab === "compare" && <ComparePanel />}
      </main>

      <footer className="ops-footer">
        Deterministic simplified engineering model — not calibrated, not measured data.
        No confidence scores are fabricated; experiments store measured branch outcomes only.
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
  const configure = useOps((s) => s.configure);
  const startSession = useOps((s) => s.startSession);
  const stepOnce = useOps((s) => s.stepOnce);
  const play = useOps((s) => s.play);
  const pause = useOps((s) => s.pause);
  const reports = useOps((s) => s.reports);
  const cost = useOps((s) => s.coordinatorCost);

  return (
    <div className="ops-session">
      <label>
        Mode
        <select value={mode} onChange={(e) => configure({ mode: e.target.value })}>
          {meta && Object.entries(meta.modes).map(([k, v]) => (
            <option key={k} value={k}>{k} · {v}</option>
          ))}
        </select>
      </label>
      <label>
        Scenario
        <select value={scenario} onChange={(e) => configure({ scenario: e.target.value })}>
          {meta && Object.entries(meta.scenarios).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </label>
      <label>
        Seed
        <input type="number" value={seed}
          onChange={(e) => configure({ seed: Number(e.target.value) })} />
      </label>
      <label>
        Speed
        <select value={speed} onChange={(e) => configure({ speed: Number(e.target.value) })}>
          <option value={1}>1× (step)</option>
          <option value={2}>2×</option>
          <option value={4}>4×</option>
          <option value={8}>8×</option>
        </select>
      </label>

      <button className="primary" onClick={() => void startSession()}>Apply / Reset</button>
      {running
        ? <button onClick={() => pause()}>⏸ Pause</button>
        : <button onClick={() => play()}>▶ Resume</button>}
      <button onClick={() => void stepOnce(1)}>⏭ Step</button>

      <span className="ops-stat">step {reports.length}</span>
      <span className="ops-stat">coordinator cost {cost} branch-steps</span>
    </div>
  );
}
