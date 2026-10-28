import { useState } from "react";
import { useOps } from "../opsStore";

const METRIC_LABELS: Record<string, string> = {
  total_power_kWh: "Total power (kWh)",
  on_time_job_fraction: "On-time jobs",
  temp_violation_steps: "Temp violation steps",
  comfort_shortfall_Kh: "Comfort shortfall (K·h)",
  useful_heat_kWh: "Useful heat (kWh)",
  peak_primary_supply_C: "Peak primary (°C)",
  recovery_time_steps: "Recovery time (steps)",
  failover_count: "Failovers",
  coordinator_cost_branch_steps: "Coordinator cost (branch steps)",
};

export function ComparePanel() {
  const cmp = useOps((s) => s.comparison);
  const comparing = useOps((s) => s.comparing);
  const runCompare = useOps((s) => s.runCompare);
  const scenario = useOps((s) => s.scenario);
  const seed = useOps((s) => s.seed);
  const [n, setN] = useState(48);

  return (
    <div className="ops-compare">
      <div className="ops-session">
        <span className="ops-stat">scenario <strong>{scenario}</strong></span>
        <span className="ops-stat">seed <strong>{seed}</strong></span>
        <label>steps (10 min each)<input type="number" min={1} max={240} value={n} onChange={(e) => setN(Number(e.target.value))} /></label>
        <div className="ops-compare-presets" aria-label="Comparison duration presets">
          {[12, 48, 96].map((steps) => (
            <button key={steps} className={n === steps ? "active" : ""}
              onClick={() => setN(steps)}>{steps / 6} h</button>
          ))}
        </div>
        <button className="primary" disabled={comparing || !Number.isInteger(n) || n < 1 || n > 240} onClick={() => void runCompare(n)}>
          {comparing ? "Running A/B/C…" : "Run A vs B vs C"}
        </button>
      </div>

      {!cmp && <div className="ops-note">Run the comparison to evaluate all three control modes on identical seed and inputs.</div>}

      {cmp && (
        <>
          <div className="ops-table-scroll" role="region" aria-label="Control mode comparison" tabIndex={0}>
          <table className="ops-table compare">
            <thead>
              <tr>
                <th>Metric</th>
                <th>A · rule-based</th>
                <th>B · agents</th>
                <th>C · agents+forecast</th>
                <th>Best</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(METRIC_LABELS).map((key) => {
                const v = cmp.verdict[key];
                const best = v?.best_mode;
                return (
                  <tr key={key}>
                    <td>{METRIC_LABELS[key]}</td>
                    {["A", "B", "C"].map((m) => (
                      <td key={m} className={best === m ? "best" : ""}>
                        {cmp.per_mode[m][key]}
                      </td>
                    ))}
                    <td>{best ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>

          <section className="card">
            <h2>Honest verdict</h2>
            <ul className="ops-list">
              {cmp.verdict._notes.map((note, i) => <li key={i}>{note}</li>)}
            </ul>
            <p className="muted">{cmp.verdict._honesty}</p>
            {cmp.cmp_id && <p className="muted">stored as {cmp.cmp_id} · model {cmp.model_version}</p>}
          </section>
        </>
      )}
    </div>
  );
}
