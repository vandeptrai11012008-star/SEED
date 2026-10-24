import { useEffect } from "react";
import { useStore, type CameraPreset, type FloorId } from "./store";
import Viewer from "./three/Viewer";
import LeftPanel from "./ui/LeftPanel";
import Presentation from "./ui/Presentation";
import RightPanel from "./ui/RightPanel";
import Timeline from "./ui/Timeline";

export default function App() {
  const init = useStore((s) => s.init);
  const loading = useStore((s) => s.loading);
  const error = useStore((s) => s.error);
  const result = useStore((s) => s.result);
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
    <div className="app">
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

      <LeftPanel />

      <div className="canvas-wrap">
        <Viewer />
        {loading && <div className="loading">Loading…</div>}
        {error && <div className="error">Backend error: {error}</div>}
        <Presentation />
        <Timeline />
      </div>

      <RightPanel />
    </div>
  );
}
