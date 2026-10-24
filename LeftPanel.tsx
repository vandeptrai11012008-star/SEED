import { useStore, type CameraPreset, type FloorId, type PipeOverlay } from "../store";

const FLOORS: { id: FloorId; label: string }[] = [
  { id: "f3", label: "3F · GPU Hall" },
  { id: "f2", label: "2F · GPU Hall" },
  { id: "f1", label: "1F · GPU Hall" },
  { id: "gf", label: "GF · Robot Lab" },
  { id: "b1", label: "B1 · Seed Research" },
  { id: "b2", label: "B2 · Mechanical Plant" },
];

const CAMERAS: { id: CameraPreset; label: string }[] = [
  { id: "auto_fit", label: "Auto fit" },
  { id: "isometric", label: "Isometric" },
  { id: "front_cutaway", label: "Front cutaway" },
  { id: "walkthrough", label: "Walkthrough" },
  { id: "greenhouse", label: "Greenhouse" },
  { id: "underground", label: "B2 / underground" },
];

const OVERLAYS: { id: PipeOverlay; label: string }[] = [
  { id: "off", label: "Physical" },
  { id: "temperature", label: "Temperature" },
  { id: "flow", label: "Flow" },
];

export default function LeftPanel() {
  const store = useStore();
  const scenarios: any[] = store.config?.simulation?.scenarios ?? [];

  return (
    <aside className="left">
      <div className="panel">
        <h2>Camera views</h2>
        <div className="camera-grid">
          {CAMERAS.map((camera) => (
            <button
              key={camera.id}
              className={`secondary camera-button ${store.cameraPreset === camera.id ? "active" : ""}`}
              onClick={() => store.setCameraPreset(camera.id)}
            >
              {camera.label}
            </button>
          ))}
        </div>
        {store.cameraPreset === "walkthrough" && (
          <div className="hint">W/A/S/D move · Q/E down/up · drag to look</div>
        )}
        <div className="row split-row">
          <label>Architectural cutaway</label>
          <button
            className={`secondary ${store.cutaway ? "active" : ""}`}
            onClick={() => store.setCutaway(!store.cutaway)}
          >
            {store.cutaway ? "Enabled" : "Closed"}
          </button>
        </div>
        <div className="row">
          <label>Greenhouse soil</label>
          <button
            className={`secondary ${store.showGreenhouseSoil ? "" : "active"}`}
            title="Hide the soil surface to inspect underground heating pipes"
            onClick={() => store.toggleGreenhouseSoil()}
          >
            {store.showGreenhouseSoil ? "Shown" : "Hidden (pipes)"}
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Floor visibility & inspection</h2>
        <div className="floor-list">
          {FLOORS.map((floor) => (
            <div className="floor-control" key={floor.id}>
              <button
                className={`visibility-dot ${store.visibleFloors[floor.id] ? "visible" : "hidden"}`}
                title="Show or hide floor"
                onClick={() => store.toggleFloor(floor.id)}
              >
                {store.visibleFloors[floor.id] ? "●" : "○"}
              </button>
              <span>{floor.label}</span>
              <button
                className="inspect-button"
                title="Inspect this floor"
                onClick={() => store.setCameraPreset("floor", floor.id)}
              >
                Focus
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Hydronic network</h2>
        <div className="segmented-control">
          {OVERLAYS.map((overlay) => (
            <button
              key={overlay.id}
              className={store.pipeOverlay === overlay.id ? "active" : "secondary"}
              onClick={() => store.setPipeOverlay(overlay.id)}
            >
              {overlay.label}
            </button>
          ))}
        </div>
        <div className="pipe-legend">
          <span><i style={{ background: "#318fe8" }} />Primary supply</span>
          <span><i style={{ background: "#ef554d" }} />Primary return</span>
          <span><i style={{ background: "#ef713d" }} />Heating supply</span>
          <span><i style={{ background: "#42d4e7" }} />Heating return</span>
        </div>
      </div>

      <div className="panel">
        <h2>Live simulation controls</h2>
        <div className="slider-row">
          <label>GPU base load</label>
          <span className="slider-value">{Math.round((store.request.gpu_load_base_fraction ?? 0.55) * 100)}%</span>
          <input
            type="range" min="0" max="1" step="0.05"
            value={store.request.gpu_load_base_fraction ?? 0.55}
            onChange={(e) => store.patchRequest({ gpu_load_base_fraction: Number(e.target.value) })}
          />
        </div>
        <div className="slider-row">
          <label>GPU peak load</label>
          <span className="slider-value">{Math.round((store.request.gpu_load_peak_fraction ?? 0.95) * 100)}%</span>
          <input
            type="range" min="0" max="1" step="0.05"
            value={store.request.gpu_load_peak_fraction ?? 0.95}
            onChange={(e) => store.patchRequest({ gpu_load_peak_fraction: Number(e.target.value) })}
          />
        </div>
        <div className="slider-row">
          <label>Outdoor mean temp</label>
          <span className="slider-value">{(store.request.ambient_mean_C ?? 10).toFixed(0)} °C</span>
          <input
            type="range" min="-20" max="40" step="1"
            value={store.request.ambient_mean_C ?? 10}
            onChange={(e) => store.patchRequest({ ambient_mean_C: Number(e.target.value) })}
          />
        </div>
        <div className="row">
          <label>Heat pump booster</label>
          <button
            className={`secondary ${(store.request.heat_pump_enabled ?? true) ? "active" : ""}`}
            onClick={() => store.patchRequest({ heat_pump_enabled: !(store.request.heat_pump_enabled ?? true) })}
          >
            {(store.request.heat_pump_enabled ?? true) ? "On" : "Off"}
          </button>
        </div>
        <div className="row">
          <label>Auxiliary rejection</label>
          <button
            className={`secondary ${(store.request.aux_rejection_enabled ?? true) ? "active" : ""}`}
            onClick={() => store.patchRequest({ aux_rejection_enabled: !(store.request.aux_rejection_enabled ?? true) })}
          >
            {(store.request.aux_rejection_enabled ?? true) ? "On" : "Off"}
          </button>
        </div>
        <div className="hint">Adjust, then Run to recompute the physics.</div>
      </div>

      <div className="panel">
        <h2>Simulation scenario</h2>
        <select
          value={store.request.scenario_id ?? "baseline"}
          onChange={(event) => store.patchRequest({ scenario_id: event.target.value })}
        >
          {scenarios.map((scenario) => (
            <option key={scenario.id} value={scenario.id}>{scenario.label}</option>
          ))}
        </select>
        <div className="row" style={{ marginTop: 10 }}>
          <label>IT design power</label>
          <div className="number-unit">
            <input
              type="number"
              min="0"
              max="10000"
              value={store.request.total_it_power_kW ?? store.config?.assumptions?.power?.total_it_power_kW ?? 1500}
              onChange={(event) => store.patchRequest({ total_it_power_kW: Number(event.target.value) })}
            />
            <span>kW</span>
          </div>
        </div>
        <div className="row">
          <label>Liquid capture</label>
          <div className="number-unit">
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={store.request.liquid_capture_fraction ?? 0.8}
              onChange={(event) => store.patchRequest({ liquid_capture_fraction: Number(event.target.value) })}
            />
            <span>frac</span>
          </div>
        </div>
        <button className="run-button" disabled={store.loading} onClick={() => store.runSimulation()}>
          {store.loading ? "Solving thermal network…" : "Run physics simulation"}
        </button>
      </div>
    </aside>
  );
}
