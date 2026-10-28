// Tiny inline sparkline for a numeric series. No external chart deps.
export function Spark({
  data, width = 240, height = 48, color = "#39d0d8", label, unit = "",
}: {
  data: number[]; width?: number; height?: number; color?: string;
  label?: string; unit?: string;
}) {
  if (data.length === 0) {
    return <div className="spark empty">{label}: no data</div>;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const n = data.length;
  const pts = data
    .map((v, i) => {
      const x = (i / Math.max(1, n - 1)) * width;
      const y = height - ((v - min) / span) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const last = data[data.length - 1];
  return (
    <div className="spark">
      {label && (
        <div className="spark-label">
          <span>{label}</span>
          <strong style={{ color }}>
            {last.toFixed(1)}
            {unit}
          </strong>
        </div>
      )}
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <polyline
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          points={pts}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="spark-range">
        <span>{min.toFixed(1)}</span>
        <span>{max.toFixed(1)}</span>
      </div>
    </div>
  );
}
