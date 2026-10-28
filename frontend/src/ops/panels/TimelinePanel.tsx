import { useState } from "react";
import { useOps } from "../opsStore";

const TYPE_COLORS: Record<string, string> = {
  observation: "#5a7", request: "#e0a93b", proposal: "#8c6fff",
  decision: "#39d0d8", action_result: "#9cd039", fault: "#ff5c5c",
};

const TYPES = ["observation", "request", "proposal", "decision", "action_result", "fault"];

export function TimelinePanel() {
  const events = useOps((s) => s.events);
  const [filter, setFilter] = useState<string>("all");

  const shown = (filter === "all" ? events : events.filter((e) => e.type === filter))
    .slice(-200).reverse();

  return (
    <div className="ops-timeline">
      <div className="ops-filter">
        <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>all</button>
        {TYPES.map((t) => (
          <button key={t} className={filter === t ? "active" : ""}
            style={{ borderColor: TYPE_COLORS[t] }} onClick={() => setFilter(t)}>
            {t}
          </button>
        ))}
      </div>
      <table className="ops-table">
        <thead>
          <tr><th>seq</th><th>t (s)</th><th>type</th><th>source</th><th>topic</th><th>payload</th></tr>
        </thead>
        <tbody>
          {shown.map((e) => (
            <tr key={e.seq}>
              <td>{e.seq}</td>
              <td>{e.t_s.toFixed(0)}</td>
              <td><span className="pill" style={{ background: TYPE_COLORS[e.type] }}>{e.type}</span></td>
              <td>{e.source}</td>
              <td><code>{e.topic}</code></td>
              <td><code className="payload">{JSON.stringify(e.payload)}</code></td>
            </tr>
          ))}
          {shown.length === 0 && <tr><td colSpan={6} className="muted">no events — step the run</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
