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
  const [legendOpen, setLegendOpen] = useState(() => window.innerWidth > 600);
  const init = useStore((s) => s.init);
  const loading = useStore((s) => s.loading);
  const error = useStore((s) => s.error);
  const result = useStore((s) => s.result);
  const selectedId = useStore((s) => s.selectedId);
  useEffect(() => {
    if (selectedId) setToolsOpen(true);
  }, [selectedId]);
  const scene = useStore((s) => s.scene);

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
          ▶ Present
        </button>
        <span className="disclaimer">
          {result?.disclaimer ?? "Simplified engineering simulation — not measured data."}
        </span>
      </header>

      <button className="view-toggle" onClick={() => {
        useStore.getState().setIllustration(!illustration);
        setToolsOpen(false);
      }}>{illustration ? "Mở bảng mô phỏng ↗" : "← Chế độ minh họa"}</button>
      <LeftPanel />

      <div className="canvas-wrap">
        <Viewer />
        {illustration && <>
          <div className="scene-brand"><span className="eyebrow">THERMALLOOP / DIGITAL TWIN</span><h1>Từ sức mạnh AI.<br />Đến mầm xanh.</h1><p>Thu hồi nhiệt · Nuôi dưỡng tương lai</p></div>
          <aside className={`flow-guide ${legendOpen ? "" : "collapsed"}`} aria-label="Chú giải dòng nhiệt">
            <button className="guide-heading" onClick={() => setLegendOpen(!legendOpen)} aria-expanded={legendOpen}>Vòng tuần hoàn nhiệt <span>{legendOpen ? "−" : "+"}</span></button>
            {legendOpen && <>
              <div className="flow-key"><i className="cold" />Nước mát / hồi về</div>
              <div className="flow-key"><i className="hot" />Nước nóng / cấp nhiệt</div>
              <ol>{[
                "Nước mát được bơm lên ba tầng GPU.",
                "Máy chủ truyền nhiệt vào mạch làm mát.",
                "Nhiệt thu hồi sưởi phòng robot và khu thử hạt.",
                "Bộ trao đổi nhiệt B2 nối hai mạch độc lập.",
                "Ống cách nhiệt đưa nước nóng đến nhà kính.",
                "Nước truyền nhiệt cho đất rồi hồi về.",
                "Bồn đệm và nhánh xử lý ổn định mạch thứ cấp.",
              ].map((text, i) => <li key={text}><b className={i === 0 || i > 4 ? "cold" : "hot"}>{i + 1}</b><span>{text}</span></li>)}</ol>
              <p className="circuit-note">Hai mạch nước tách biệt. Chỉ trao đổi nhiệt tại B2.</p>
            </>}
          </aside>
          <nav className="scene-toolbar" aria-label="Điều khiển góc nhìn">
            <button onClick={() => useStore.getState().setCameraPreset("front_cutaway")}>↺ Toàn cảnh</button>
            <button onClick={() => useStore.getState().setCameraPreset("greenhouse")}>Nhà kính</button>
            <button onClick={() => useStore.getState().setCameraPreset("underground")}>Tầng B2</button>
            <button aria-pressed={toolsOpen} onClick={() => setToolsOpen(!toolsOpen)}>{toolsOpen ? "Đóng thông số" : "Thông số"}</button>
          </nav>
          <div className="scene-footnote"><span className="status-dot" />{loading ? "Đang tính mô phỏng…" : "Mô phỏng vật lý giản lược"}<span>Kéo để xoay · Cuộn để phóng to</span></div>
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
