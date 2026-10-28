import { useState } from "react";
import { useOps } from "../opsStore";

// Static descriptions matching the actual policy code so the UI explains the
// real algorithm, not a plausible story.
const AGENT_INFO: Record<string, { goal: string; cycle: string }> = {
  workload: { goal: "Run as much compute as possible without overheating the loop.",
    cycle: "honour coordinator load ceiling → proportionally trim near the 45C trip → (mode C) forecast peak and pre-trim → measure." },
  gpu: { goal: "Protect racks; request load shed only as coolant nears the trip.",
    cycle: "observe coolant temp → request lower load (cannot set it) → measure." },
  infrastructure: { goal: "Hold the rack loop in band with least pumping energy.",
    cycle: "observe primary temp → bias flow HIGH for safety, trim only when cool → measure." },
  building: { goal: "Occupant comfort; flag and request heat for cold zones.",
    cycle: "observe zone temps → request more secondary flow → measure gap in K." },
  power_cooling: { goal: "Reject only unusable heat, modulated continuously; lift on demand.",
    cycle: "observe surplus + margin to band → set continuous aux level + heat pump → measure." },
  heat_recovery: { goal: "Maximise useful delivered heat; set heat-quality setpoint; store surplus.",
    cycle: "track coordinator secondary setpoint → set secondary pump + buffer charge → measure." },
  fault: { goal: "Detect sensor loss, residual drift, pump degradation, unmet demand.",
    cycle: "cross-check blackboard → raise faults + high-priority requests → measure." },
  research: { goal: "Propose experiments from branch sims; never writes an actuator.",
    cycle: "snapshot → run branches on same inputs → compare constraints → propose with evidence." },
};

export function Agents() {
  const [query, setQuery] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);
  const meta = useOps((s) => s.meta);
  const reports = useOps((s) => s.reports);
  const last = reports[reports.length - 1];

  // latest decision/request/proposal per agent from the newest step
  const bySource: Record<string, { decisions: any[]; proposals: any[] }> = {};
  for (const r of reports.slice(-4)) {
    for (const d of r.decisions) {
      const src = d.owner ?? d.controller ?? "rule_based";
      (bySource[src] ??= { decisions: [], proposals: [] }).decisions.push(d);
    }
    for (const p of r.proposals) {
      (bySource[p.agent] ??= { decisions: [], proposals: [] }).proposals.push(p);
    }
  }

  // latest coordinator regime (supervisory layer) from recent proposals
  let coordPlan: any = null;
  for (const r of reports) {
    for (const p of r.proposals) {
      if (p.agent === "coordinator") coordPlan = p;
    }
  }

  if (!meta) return <div className="ops-note">loading…</div>;

  const isRecent = (name: string) => Boolean(bySource[name]?.decisions.length || bySource[name]?.proposals.length);
  const activeCount = meta.agents.filter((a) => isRecent(a.name)).length;
  const visibleAgents = meta.agents.filter((a) => {
    const matches = `${a.name} ${a.owns.join(" ")} ${AGENT_INFO[a.name]?.goal ?? ""}`
      .toLowerCase().includes(query.trim().toLowerCase());
    return matches && (!activeOnly || isRecent(a.name));
  });

  return (
    <div className="ops-agents">
      <div className="ops-agents-toolbar">
        <div>
          <span className="ops-eyebrow">AGENT INSPECTOR</span>
          <h2>8 agents · {activeCount} recently active</h2>
          <p>Search by agent or actuator, then open its policy details when needed.</p>
        </div>
        <div className="ops-agent-filters">
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Find agent or actuator…" aria-label="Search agents" />
          <button className={!activeOnly ? "active" : ""} onClick={() => setActiveOnly(false)}>All 8</button>
          <button className={activeOnly ? "active" : ""} onClick={() => setActiveOnly(true)}>Active ({activeCount})</button>
        </div>
      </div>
      {coordPlan && (
        <section className="card coord-banner">
          <h2>Coordinator · {coordPlan.detail?.regime} regime</h2>
          <p className="goal">{coordPlan.rationale}</p>
          <p className="cycle">
            load ceiling <strong>{coordPlan.detail?.gpu_load_ceiling}</strong> ·
            secondary target <strong>{coordPlan.detail?.secondary_supply_C} °C</strong> ·
            primary band <strong>{coordPlan.detail?.primary_supply_band_C} °C</strong>
          </p>
          {coordPlan.evidence?.mpc_scoreboard?.length ? (
            <>
              <h3>MPC look-ahead — plans evaluated</h3>
              <table className="ops-table">
                <thead>
                  <tr><th>plan</th><th>load</th><th>peak °C</th><th>viol</th><th>cost</th></tr>
                </thead>
                <tbody>
                  {coordPlan.evidence.mpc_scoreboard.map((c: any, i: number) => (
                    <tr key={i} className={i === 0 ? "best" : ""}>
                      <td><code>{c.label}</code></td>
                      <td>{c.candidate?.gpu_load_fraction}</td>
                      <td>{c.peak_primary_C}</td>
                      <td>{c.violation_steps}</td>
                      <td>{c.cost}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted">Lowest-cost plan (top row) is chosen. Safety violations dominate the cost.</p>
            </>
          ) : null}
          <p className="owns"><em>Supervisory layer — owns no actuator; sets targets the agents track.</em></p>
        </section>
      )}
      {visibleAgents.map((a) => {
        const info = AGENT_INFO[a.name];
        const live = bySource[a.name];
        const recent = isRecent(a.name);
        return (
          <section className="card agent" key={a.name}>
            <h2>{a.name.replace("_", " ")}
              <span className={`agent-status ${recent ? "active" : "idle"}`}>
                {recent ? "● Recent action" : "○ Waiting"}
              </span>
            </h2>
            <p className="goal">{info?.goal}</p>
            <p className="owns">
              <strong>Owns (single writer):</strong>{" "}
              {a.owns.length ? a.owns.map((o) => <code key={o}>{o}</code>) : <em>none — requests only</em>}
            </p>
            <details className="agent-policy">
              <summary>How this agent decides</summary>
              <p className="cycle">{info?.cycle}</p>
            </details>
            <div className="agent-live">
              <h3>Latest decisions</h3>
              <ul className="ops-list">
                {live?.decisions?.slice(-3).reverse().map((d, i) => (
                  <li key={i}>
                    <code>{d.actuator}</code> = <strong>{String(d.value)}</strong>
                    <br /><span className="muted">{d.rationale ?? d.rule}</span>
                  </li>
                ))}
                {(!live || live.decisions.length === 0) && <li className="muted">no recent decision</li>}
              </ul>
              {live?.proposals?.length ? (
                <>
                  <h3>Proposals / evidence</h3>
                  <ul className="ops-list">
                    {live.proposals.slice(-2).reverse().map((p, i) => (
                      <li key={i}>
                        <span className="muted">{p.rationale}</span>
                        {p.evidence && <pre className="evidence">{JSON.stringify(p.evidence, null, 0)}</pre>}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          </section>
        );
      })}
      {visibleAgents.length === 0 && (
        <div className="ops-note">No matching agents. Clear the search or show all agents.</div>
      )}
      {!last && <div className="ops-note">Step the run to see agent activity.</div>}
    </div>
  );
}
