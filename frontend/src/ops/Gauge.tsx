// A linear gauge showing a measured value within a scale, with caution/alarm
// bands and a limit marker -- the standard way an engineering console shows a
// value relative to its operating limits.
export function Gauge({
  label, value, unit = "", min, max, caution, alarm,
}: {
  label: string; value: number; unit?: string; min: number; max: number;
  caution?: number; alarm?: number;
}) {
  const clamp = (v: number) => Math.max(min, Math.min(max, v));
  const pct = (v: number) => ((clamp(v) - min) / (max - min)) * 100;
  const status = alarm !== undefined && value >= alarm ? "alarm"
    : caution !== undefined && value >= caution ? "caution" : "ok";
  const color = status === "alarm" ? "var(--alarm)"
    : status === "caution" ? "var(--caution)" : "var(--ok)";
  return (
    <div className="gauge">
      <div className="gauge-head">
        <span>{label}</span>
        <strong style={{ color }}>{value.toFixed(1)}{unit}</strong>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${pct(value)}%`, background: color }} />
        {alarm !== undefined && <div className="gauge-limit" style={{ left: `${pct(alarm)}%` }} />}
      </div>
      <div className="gauge-scale">
        <span>{min}</span>
        {alarm !== undefined && <span>trip {alarm}{unit}</span>}
        <span>{max}</span>
      </div>
    </div>
  );
}

// A readout tile: large monospace value with a unit and a status colour.
export function Metric({
  label, value, unit = "", status = "ok", digits = 1,
}: {
  label: string; value: number; unit?: string;
  status?: "ok" | "caution" | "alarm"; digits?: number;
}) {
  return (
    <div className={`metric ${status}`}>
      <div className="m-label">{label}</div>
      <div className="m-value">
        {value.toFixed(digits)}<span className="m-unit">{unit}</span>
      </div>
    </div>
  );
}
