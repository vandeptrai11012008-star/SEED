import { useOps } from "../opsStore";
import { Spark } from "../Spark";

// Prediction-vs-measured: pair each Research/Workload proposal that carried a
// forecast "probe_peak_primary_C" with the primary supply temperature actually
// measured a few steps later. Shows whether the forecast model tracked reality.
export function Lab() {
  const reports = useOps((s) => s.reports);
  const mode = useOps((s) => s.mode);

  if (mode !== "C") {
    return (
      <div className="ops-note">
        Forecasting is only active in <strong>mode C</strong>. Switch mode to C and reset to
        populate predicted-vs-measured evidence. Modes A and B make no forecast, so there is
        nothing to validate here — that is by design, not a gap.
      </div>
    );
  }

  // Pair only the workload agent's own probe (peak primary over a 6-step
  // horizon) against the measured peak over that same 6-step window. Mixing in
  // the research agent's different candidate/horizon would make the error
  // meaningless, so it is intentionally excluded from the accuracy metric.
  const PROBE_HORIZON = 6;
  const pairs: { step: number; predicted: number; measured: number }[] = [];
  for (let i = 0; i < reports.length; i++) {
    const r = reports[i];
    for (const p of r.proposals) {
      const probe = p.evidence?.probe_peak_primary_C;
      if (typeof probe === "number") {
        const end = Math.min(reports.length - 1, i + PROBE_HORIZON);
        const window = reports.slice(i, end + 1).map((x) => x.metrics.primary_supply_C);
        if (window.length === 0) continue;
        const measured = Math.max(...window);
        pairs.push({ step: r.index, predicted: probe, measured });
      }
    }
  }

  const errors = pairs.map((p) => p.measured - p.predicted);
  const mae = errors.length ? errors.reduce((a, b) => a + Math.abs(b), 0) / errors.length : 0;

  const experiments = reports.flatMap((r) => r.proposals.filter((p) => p.topic === "experiment"));

  return (
    <div className="ops-grid">
      <section className="card">
        <h2>Forecast vs measured — primary peak</h2>
        {pairs.length === 0 ? (
          <p className="muted">No forecast probes captured yet — keep stepping the run.</p>
        ) : (
          <>
            <Spark label="Predicted peak" unit="°C" color="#8c6fff"
              data={pairs.map((p) => p.predicted)} />
            <Spark label="Measured peak" unit="°C" color="#ff8c42"
              data={pairs.map((p) => p.measured)} />
            <p className="ops-counter">
              mean absolute error {mae.toFixed(2)} °C over {pairs.length} forecasts
            </p>
            <p className="muted">
              Error is reported as a measured quantity (°C). No confidence percentage is invented.
            </p>
          </>
        )}
      </section>

      <section className="card">
        <h2>Experiments proposed (not auto-applied)</h2>
        <ul className="ops-list">
          {experiments.slice(-6).reverse().map((e, i) => (
            <li key={i}>
              <strong>{e.detail?.hypothesis}</strong>
              <br /><span className="muted">{e.rationale}</span>
              {e.evidence && (
                <pre className="evidence">
constraints_ok: {String(e.evidence.constraints_ok)}
Δdelivered: {e.evidence.delta_delivered_kWh} kWh
                </pre>
              )}
            </li>
          ))}
          {experiments.length === 0 && <li className="muted">no experiments proposed yet</li>}
        </ul>
      </section>
    </div>
  );
}
