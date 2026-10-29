import { useEffect, useState } from "react";
import { useStore, type CameraPreset, type FloorId } from "./store";
import Viewer from "./three/Viewer";
import LeftPanel from "./ui/LeftPanel";
import Presentation from "./ui/Presentation";
import RightPanel from "./ui/RightPanel";
import Timeline from "./ui/Timeline";

export default function App() {
  const illustration = useStore((s) => s.illustration);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [legendOpen, setLegendOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(() => {
    try { return window.localStorage.getItem("thermalloop_intro_seen") !== "1"; }
    catch { return true; }
  });
  const init = useStore((s) => s.init);
  const loading = useStore((s) => s.loading);
  const error = useStore((s) => s.error);
  const result = useStore((s) => s.result);
  const selectedId = useStore((s) => s.selectedId);
  useEffect(() => {
    if (selectedId) setToolsOpen(true);
  }, [selectedId]);
  const scene = useStore((s) => s.scene);

  const dismissWelcome = () => {
    setWelcomeOpen(false);
    try { window.localStorage.setItem("thermalloop_intro_seen", "1"); }
    catch { /* Private browsing can disable storage. */ }
  };

  const startGuidedTour = () => {
    dismissWelcome();
    useStore.getState().setIllustration(false);
    useStore.getState().startPresentation();
  };

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedView = params.get("view");
    const allowedViews = new Set([
      "auto_fit", "isometric", "front_cutaway", "walkthrough",
      "floor", "greenhouse", "underground",
    ]);
    if (requestedView && allowedViews.has(requestedView)) {
      const floor = params.get("floor");
      const allowedFloors = new Set(["b2", "b1", "gf", "f1", "f2", "f3"]);
      useStore.getState().setCameraPreset(
        requestedView as CameraPreset,
        floor && allowedFloors.has(floor) ? floor as FloorId : undefined,
      );
    }
    if (params.get("soil") === "hidden" && useStore.getState().showGreenhouseSoil) {
      useStore.getState().toggleGreenhouseSoil();
    }
    if (params.get("present") === "1" || params.get("present") === "true") {
      useStore.getState().startPresentation();
    }
  }, []);

  return (
    <div className={`app ${illustration ? "illustration-mode" : ""} ${toolsOpen ? "tools-open" : ""}`}>
      <header className="header">
        <h1>
          ThermalLoop AI Center
          <span>Physics-based facility digital twin</span>
        </h1>
        <span className="badge">1:1 · SI metres</span>
        <span className="badge">{scene?.counts.floors ?? 6} floors · {scene?.counts.gpu_racks ?? 0} GPU racks</span>
        <span className="badge">{result?.mode ?? "loading"}</span>
        <button className="present-button" onClick={() => useStore.getState().startPresentation()}>
          ▶ Guided tour
        </button>
        <a className="ops-button" href="?ops=1" title="Open the multi-agent Operations Center">
          🤖 Test AI agents
        </a>
        <span className="disclaimer">
          {result?.disclaimer ?? "Simplified engineering simulation — not measured data."}
        </span>
      </header>

      <button className="view-toggle" onClick={() => {
        useStore.getState().setIllustration(!illustration);
        setToolsOpen(false);
      }}>{illustration ? "Advanced 3D controls ↗" : "← Back to 3D overview"}</button>
      <LeftPanel />

      <div className="canvas-wrap">
        <Viewer />
        {illustration && <>
          <a className="agents-shortcut" href="?ops=1" aria-label="Open AI Agents Operations Center">
            <span aria-hidden="true">🤖</span> Try AI Agents
          </a>
          {welcomeOpen && (
            <section className="first-visit-card" aria-label="Getting started" aria-labelledby="first-visit-title">
              <span className="first-visit-kicker">👋 START HERE · BẮT ĐẦU</span>
              <h2 id="first-visit-title">Lần đầu vào ThermalLoop?</h2>
              <p>Chọn một cách khám phá. Bạn không cần biết về mô phỏng hay AI trước.</p>
              <button className="first-visit-primary" onClick={startGuidedTour}>
                <span className="first-visit-number">1</span>
                <span><strong>Xem hướng dẫn 3D</strong><small>Tour có hướng dẫn qua các tầng của tòa nhà</small></span>
                <span aria-hidden="true">→</span>
              </button>
              <a className="first-visit-secondary" href="?ops=1&guide=1" onClick={dismissWelcome}>
                <span className="first-visit-number">2</span>
                <span><strong>Chạy thử AI Agents</strong><small>Một nút chạy mẫu, sau đó xem kết quả</small></span>
                <span aria-hidden="true">→</span>
              </a>
              <button className="first-visit-skip" onClick={dismissWelcome}>Để tôi tự khám phá / Skip</button>
            </section>
          )}
          <div className="scene-brand"><span className="eyebrow">THERMALLOOP AI CENTER</span><h1>Powered by AI.<br />Growing a greener future.</h1><p>Recovering heat · Cultivating the future</p></div>
          <aside className={`flow-guide ${legendOpen ? "" : "collapsed"}`} aria-label="Heat flow legend">
            <button className="guide-heading" onClick={() => setLegendOpen(!legendOpen)} aria-expanded={legendOpen}>The heat recovery loop <span>{legendOpen ? "−" : "+"}</span></button>
            {legendOpen && <>
              <div className="flow-key"><i className="cold" />Cool water · GPU supply / heating return</div>
              <div className="flow-key"><i className="hot" />Hot water · GPU return / heating supply</div>
              <ol>{[
                "Cool water is pumped up to all three GPU floors.",
                "Servers transfer waste heat into the cooling circuit.",
                "Recovered heat warms the robot lab and seed testing zones.",
                "The B2 heat exchanger transfers heat between two isolated circuits.",
                "Insulated pipes carry hot water to the greenhouse.",
                "Water heats the soil, then returns to the plant.",
                "A buffer tank and treatment sidestream stabilize the secondary circuit.",
              ].map((text, i) => <li key={text}><b className={i === 0 || i > 4 ? "cold" : "hot"}>{i + 1}</b><span>{text}</span></li>)}</ol>
              <p className="circuit-note">Two isolated water circuits. Heat transfers only at the B2 heat exchanger.</p>
            </>}
          </aside>
          <nav className="scene-toolbar" aria-label="View controls">
            <button onClick={() => useStore.getState().setCameraPreset("front_cutaway")}>↺ Overview</button>
            <button onClick={() => useStore.getState().setCameraPreset("greenhouse")}>Greenhouse</button>
            <button onClick={() => useStore.getState().setCameraPreset("underground")}>B2 plant</button>
            <button aria-pressed={toolsOpen} onClick={() => setToolsOpen(!toolsOpen)}>{toolsOpen ? "Close details" : "Details"}</button>
            <button aria-expanded={welcomeOpen} onClick={() => { setWelcomeOpen(!welcomeOpen); setLegendOpen(false); }}>❔ Help</button>
          </nav>
          <div className="scene-footnote"><span className="status-dot" />{loading ? "Running simulation…" : "Simplified physics simulation"}<span>Illustrative scale · Explore the 1:1 model in Simulation view</span></div>
        </>}
        {loading && <div className="loading">Loading…</div>}
        {error && <div className="error">Backend error: {error}</div>}
        <Presentation />
        <Timeline />
      </div>

      <RightPanel />
    </div>
  );
}
