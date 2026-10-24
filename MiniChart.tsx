interface Series {
  label: string;
  color: string;
  values: number[];
}

// Lightweight multi-series line chart drawn with inline SVG (no chart lib).
export default function MiniChart({
  series,
  height = 120,
  cursor,
  unit = "",
}: {
  series: Series[];
  height?: number;
  cursor?: number;
  unit?: string;
}) {
  const n = Math.max(...series.map((s) => s.values.length), 1);
  const all = series.flatMap((s) => s.values);
  const min = Math.min(0, ...all);
  const max = Math.max(1, ...all);
  const W = 320;
  const H = height;
  const pad = 4;

  const x = (i: number) => pad + (i / Math.max(1, n - 1)) * (W - 2 * pad);
  const y = (v: number) => H - pad - ((v - min) / (max - min || 1)) * (H - 2 * pad);

  return (
    <div>
      <svg className="mini-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {series.map((s) => (
          <polyline
            key={s.label}
            fill="none"
            stroke={s.color}
            strokeWidth={1.5}
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
          />
        ))}
        {cursor !== undefined && (
          <line x1={x(cursor)} x2={x(cursor)} y1={pad} y2={H - pad} stroke="#ffffff55" strokeWidth={1} />
        )}
      </svg>
      <div className="legend">
        {series.map((s) => (
          <span key={s.label}>
            <span className="sw" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
        <span style={{ marginLeft: "auto" }}>
          {max.toFixed(0)}
          {unit} max
        </span>
      </div>
    </div>
  );
}
