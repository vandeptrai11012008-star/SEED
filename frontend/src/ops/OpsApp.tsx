import { useEffect, useState } from "react";
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

function firstVisitGuideVisible() {
  if (new URLSearchParams(window.location.search).get("guide") === "1") return true;
  try { return window.localStorage.getItem("thermalloop_ops_intro_seen") !== "1"; }
  catch { return true; }
}

export default function OpsApp() {
  const [showGuide, setShowGuide] = useState(firstVisitGuideVisible);
  const init = useOps((s) => s.init);
  const loading = useOps((s) => s.loading);
  const error = useOps((s) => s.error);
  const meta = useOps((s) => s.meta);
  const tab = useOps((s) => s.tab);
  const setTab = useOps((s) => s.setTab);

  const hideGuide = () => {
    setShowGuide(false);
    try { window.localStorage.setItem("thermalloop_ops_intro_seen", "1"); }
    catch { /* Storage is optional. */ }
  };

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
          <button className="ops-help-link" onClick={() => setShowGuide(!showGuide)} aria-expanded={showGuide}>
            ❔ {showGuide ? "Hide guide" : "Start guide"}
          </button>
          <span className={`ops-simulation-badge ${meta?.real_device_enabled ? "unsafe" : ""}`}>
            {meta?.real_device_enabled ? "HARDWARE ENABLED" : "● SIMULATION ONLY"}
          </span>
          <a className="ops-link" href="?">← Back to 3D</a>
        </div>
      </header>

      {showGuide && <GettingStarted onDismiss={hideGuide} />}
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
        Deterministic simplified engineering model — not calibrated, not measured data.
        No confidence scores are fabricated; experiments store measured branch outcomes only.
      </footer>
    </div>
  );
}

function GettingStarted({ onDismiss }: { onDismiss: () => void }) {
  const reports = useOps((s) => s.reports);
  const tab = useOps((s) => s.tab);
  const setTab = useOps((s) => s.setTab);
  const busy = useOps((s) => s.busy);
  const loading = useOps((s) => s.loading);
  const running = useOps((s) => s.running);
  const sessionId = useOps((s) => s.sessionId);
  const appliedConfig = useOps((s) => s.appliedConfig);
  const mode = useOps((s) => s.mode);
  const scenario = useOps((s) => s.scenario);
  const seed = useOps((s) => s.seed);
  const startSession = useOps((s) => s.startSession);
  const hasSteps = reports.length > 0;
  const step = !hasSteps ? 1 : tab === "agents" ? 3 : tab === "timeline" ? 4 : 2;
  const needsNewSession = !sessionId || !appliedConfig || mode !== appliedConfig.mode || scenario !== appliedConfig.scenario || seed !== appliedConfig.seed;

  const runExample = async () => {
    if (needsNewSession) await startSession();
    if (useOps.getState().sessionId) {
      await useOps.getState().stepOnce(6); // 6 × 10 minutes = 1 simulated hour.
      setTab("overview");
    }
  };

  return (
    <section className="ops-getting-started" aria-label="Beginner's guide">
      <div className="ops-getting-title">
        <span className="ops-eyebrow">👋 NEW HERE? · DÀNH CHO NGƯỜI MỚI</span>
        <h2>Thử mô phỏng trong 3 bước</h2>
        <p>Chưa cần chỉnh thông số. Chạy một ví dụ, xem kết quả rồi tìm hiểu AI Agents đã làm gì.</p>
        <button className="ops-guide-dismiss" onClick={onDismiss}>Ẩn hướng dẫn ×</button>
      </div>
      <ol className="ops-guide-steps">
        <li className={step === 1 ? "current" : "done"}><b>1</b><span><strong>Chạy ví dụ</strong><small>1 giờ mô phỏng</small></span></li>
        <li className={step === 2 ? "current" : step > 2 ? "done" : ""}><b>2</b><span><strong>Xem kết quả</strong><small>Nhiệt độ và an toàn</small></span></li>
        <li className={step === 3 ? "current" : step > 3 ? "done" : ""}><b>3</b><span><strong>Xem AI Agents</strong><small>Quyết định & sự kiện</small></span></li>
      </ol>
      <div className="ops-guide-action">
        {!hasSteps ? (
          <button className="primary" disabled={busy || loading || running} onClick={() => void runExample()}>
            {busy || loading ? "Đang chuẩn bị…" : "▶ Bắt đầu chạy thử 1 giờ"}
          </button>
        ) : tab === "agents" ? (
          <button className="primary" onClick={() => setTab("timeline")}>Xem nhật ký sự kiện →</button>
        ) : tab === "timeline" ? (
          <button className="primary" onClick={() => { setTab("overview"); onDismiss(); }}>✓ Xong · Về kết quả</button>
        ) : (
          <button className="primary" onClick={() => setTab("agents")}>Xem quyết định AI Agents →</button>
        )}
        <small>{hasSteps ? `Đã chạy ${reports.length} bước gần nhất. Bạn có thể thử kịch bản khác ở bên dưới.` : "Mô phỏng thử nghiệm, không điều khiển thiết bị thật."}</small>
      </div>
    </section>
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
          <h2>Chọn tình huống, rồi bấm Run</h2>
          <p>Mỗi bước = 10 phút trong mô hình. Các chỉ số là dữ liệu mô phỏng.</p>
        </div>
        <div className={`ops-run-status ${statusTone}`} role="status" aria-live="polite">
          <span className="ops-status-dot" /> {status}
        </div>
      </div>

      <div className="ops-command-body">
        <div className="ops-fields">
          <label>Ai điều khiển? / Control mode
            <select value={mode} disabled={running || busy || loading} onChange={(e) => configure({ mode: e.target.value })}>
              {Object.entries(meta?.modes ?? { A: "Rules", B: "Agents", C: "Agents + forecast" }).map(([k, v]) => (
                <option key={k} value={k}>{MODE_LABELS[k] ?? `${k} · ${v}`}</option>
              ))}
            </select>
          </label>
          <label>Chuyện gì xảy ra? / Test scenario
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
        <summary>⚙ Advanced settings · manual steps, speed, reset, export</summary>
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
