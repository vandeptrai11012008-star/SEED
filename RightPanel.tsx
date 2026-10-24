import { useStore } from "../store";
import MiniChart from "./MiniChart";
import { exportRun } from "./exportRun";

const ZONE_LABELS: Record<string, string> = {
  zone_robot_lab: "Robot laboratory",
  zone_seed_storage: "Seed storage",
  zone_seed_testing: "Seed testing",
  zone_greenhouse_soil: "Greenhouse soil",
};

function kW(value?: number) {
  return ((value ?? 0) / 1000).toFixed(1);
}

function flow(value?: number) {
  return (value ?? 0).toFixed(2);
}

export default function RightPanel() {
  const result = useStore((state) => state.result);
  const step = useStore((state) => state.currentStep());
  const stepIndex = useStore((state) => state.stepIndex);
  const selectedId = useStore((state) => state.selectedId);
  const scene = useStore((state) => state.scene);
  const series = result?.series ?? [];
  const checks = result?.conservation_checks;
  const summary = result?.summary ?? {};
  const selectedObject = scene?.objects.find((object) => object.id === selectedId);
  const selectedPipe = scene?.pipes.find((pipe) => pipe.id === selectedId);
  const selectedPipeState = selectedPipe ? step?.pipe_states?.[selectedPipe.id] : undefined;

  return (
    <aside className="right">
      {(selectedObject || selectedPipe) && (
        <div className="panel inspection-card">
          <h2>Digital-twin object</h2>
          <strong className="object-id">{selectedId}</strong>
          <table>
            <tbody>
              <tr><td>Type</td><td className="r">{selectedObject?.kind ?? "pipe segment"}</td></tr>
              {selectedObject?.floor_id && <tr><td>Floor</td><td className="r">{selectedObject.floor_id}</td></tr>}
              {selectedObject?.nominal_power_kW !== undefined && <tr><td>Nominal</td><td className="r">{selectedObject.nominal_power_kW.toFixed(1)} kW</td></tr>}
              {selectedObject?.kind === "gpu_rack" && step && <tr><td>Current rack load</td><td className="r">{kW(step.rack_power_W?.[selectedObject.id])} kW</td></tr>}
              {selectedPipe && <tr><td>Connection</td><td className="r">{selectedPipe.from} → {selectedPipe.to}</td></tr>}
              {selectedPipeState && <tr><td>Temperature</td><td className="r">{selectedPipeState.temperature_C.toFixed(1)} °C</td></tr>}
              {selectedPipeState && <tr><td>Mass flow</td><td className="r">{selectedPipeState.mass_flow_kg_s.toFixed(2)} kg/s</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel metric-panel">
        <h2>Heat recovery now</h2>
        <div className="metric-grid">
          <div><span>IT heat</span><strong>{kW(step?.it_power_W)} kW</strong></div>
          <div><span>Liquid captured</span><strong>{kW(step?.liquid_captured_W)} kW</strong></div>
          <div><span>HX transfer</span><strong>{kW(step?.hx_transfer_W)} kW</strong></div>
          <div><span>Delivered</span><strong className="positive">{kW(step?.delivered_total_W)} kW</strong></div>
        </div>
        <div className="energy-explanation">
          <strong>Where undelivered thermal energy goes</strong>
          <div className="row"><label>Air-side IT heat</label><span>{kW(step?.air_remaining_W)} kW</span></div>
          <div className="row"><label>Primary pipe loss</label><span>{kW(step?.primary_pipe_loss_W)} kW</span></div>
          <div className="row"><label>Auxiliary rejection</label><span>{kW(step?.aux_rejected_W)} kW</span></div>
          <div className="row"><label>Distribution loss</label><span>{kW(step?.distribution_loss_W)} kW</span></div>
          <div className="row"><label>Unrejected / cooling shortfall</label><span className={(step?.primary_unrejected_W ?? 0) > 1 ? "negative" : ""}>{kW(step?.primary_unrejected_W)} kW</span></div>
          <div className="row"><label>Unmet zone demand</label><span className={(step?.unmet_demand_W ?? 0) > 1 ? "warning" : ""}>{kW(step?.unmet_demand_W)} kW</span></div>
        </div>
      </div>

      <div className="panel">
        <h2>Hydronic operating point</h2>
        <table>
          <tbody>
            <tr><td>Primary flow</td><td className="r">{flow(step?.primary_mass_flow_kg_s)} kg/s</td></tr>
            <tr><td>Secondary flow</td><td className="r">{flow(step?.secondary_mass_flow_kg_s)} kg/s</td></tr>
            <tr><td>Greenhouse branch</td><td className="r">{flow(step?.greenhouse_mass_flow_kg_s)} kg/s</td></tr>
            <tr><td>Pump electricity</td><td className="r">{kW(step?.pump_power_W)} kW</td></tr>
            <tr><td>Heat-pump electricity</td><td className="r">{kW(step?.heat_pump_elec_W)} kW</td></tr>
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Zone thermal delivery</h2>
        <table className="zone-table">
          <thead><tr><th>Zone</th><th>Temp</th><th>Demand</th><th>Delivered</th></tr></thead>
          <tbody>
            {Object.keys(ZONE_LABELS).map((zoneId) => (
              <tr key={zoneId}>
                <td>{ZONE_LABELS[zoneId]}</td>
                <td className="r">{step?.zone_temperature_C?.[zoneId]?.toFixed(1) ?? "—"}°</td>
                <td className="r">{kW(step?.zone_demand_W?.[zoneId])}</td>
                <td className={`r ${(step?.zone_unmet_W?.[zoneId] ?? 0) > 1 ? "warning" : "positive"}`}>{kW(step?.zone_delivered_W?.[zoneId])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Energy balance · power over time</h2>
        <MiniChart
          cursor={stepIndex}
          unit=" kW"
          series={[
            { label: "IT", color: "#52616e", values: series.map((record) => record.it_power_W / 1000) },
            { label: "Captured", color: "#f49a4a", values: series.map((record) => record.liquid_captured_W / 1000) },
            { label: "Delivered", color: "#33b77a", values: series.map((record) => record.delivered_total_W / 1000) },
            { label: "Rejected", color: "#e5534b", values: series.map((record) => record.aux_rejected_W / 1000) },
          ]}
        />
      </div>

      <div className="panel">
        <h2>Calculated water temperatures</h2>
        <MiniChart
          cursor={stepIndex}
          unit=" °C"
          series={[
            { label: "Primary supply", color: "#318fe8", values: series.map((record) => record.primary_supply_C) },
            { label: "Primary return", color: "#ef554d", values: series.map((record) => record.primary_return_C) },
            { label: "HX secondary out", color: "#f6a34f", values: series.map((record) => record.hx_secondary_out_C) },
            { label: "Secondary supply", color: "#ef713d", values: series.map((record) => record.secondary_supply_C) },
            { label: "Secondary return", color: "#42d4e7", values: series.map((record) => record.secondary_return_C) },
          ]}
        />
      </div>

      <div className="panel">
        <h2>Thermal storage · tank_buffer_001</h2>
        <div className="row"><label>Tank temperature</label><span>{step?.buffer_temp_C?.toFixed(1) ?? "—"} °C</span></div>
        <div className="row"><label>Charging</label><span>{kW(step?.buffer_charge_W)} kW</span></div>
        <div className="row"><label>Discharging</label><span>{kW(step?.buffer_discharge_W)} kW</span></div>
        <MiniChart cursor={stepIndex} unit=" °C" height={78} series={[{ label: "Buffer", color: "#35a8c9", values: series.map((record) => record.buffer_temp_C) }]} />
      </div>

      <div className="panel conserv">
        <h2>Numerical balance checks</h2>
        {checks ? (
          <table>
            <tbody>
              {(["capture_split", "primary_balance", "secondary_balance"] as const).map((key) => (
                <tr key={key}>
                  <td>{key.replace(/_/g, " ")}</td>
                  <td className="r">
                    {checks[key].relative_error.toExponential(1)}{" "}
                    <span className={checks[key].passed ? "ok" : "bad"}>{checks[key].passed ? "PASS" : "FAIL"}</span>
                  </td>
                </tr>
              ))}
              {checks.mass_balance && (
                <tr><td>mass balance</td><td className="r"><span className={checks.mass_balance.passed ? "ok" : "bad"}>{checks.mass_balance.passed ? "PASS" : "FAIL"}</span></td></tr>
              )}
            </tbody>
          </table>
        ) : <div>No run yet.</div>}
        <div className="model-note">Deterministic simplified engineering simulation — not calibrated or measured data.</div>
      </div>

      <div className="panel">
        <h2>Research export</h2>
        <div className="row">
          <button className="secondary" onClick={() => exportRun(result, "json")} disabled={!result}>Export JSON</button>
          <button className="secondary" onClick={() => exportRun(result, "csv")} disabled={!result}>Export CSV</button>
        </div>
        {result && <div className="run-id">{result.run_id} · {result.mode} · {(summary.total_recovered_kWh ?? 0).toFixed(1)} kWh recovered</div>}
      </div>
    </aside>
  );
}
