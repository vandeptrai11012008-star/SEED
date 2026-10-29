import { useOps } from "../opsStore";
import { Spark } from "../Spark";
import { Gauge, Metric } from "../Gauge";

export function Overview() {
  const reports = useOps((s) => s.reports);
  const setTab = useOps((s) => s.setTab);
  if (reports.length === 0) {
    return (
      <section className="card ops-welcome">
        <div className="ops-welcome-icon" aria-hidden="true">◎</div>
        <span className="ops-eyebrow">YOUR FIRST EXPERIMENT</span>
        <h2>Kết quả mô phỏng sẽ hiện ở đây</h2>
        <p>Bấm <strong>"Run 1 hour"</strong> phía trên (hoặc nút chạy thử trong hướng dẫn) để thấy nhiệt độ, đồ thị và các quyết định điều khiển.</p>
        <ol>
          <li>Chạy một giờ thử nghiệm — không ảnh hưởng thiết bị thật.</li>
          <li>Xem nhiệt độ và trạng thái an toàn tại Dashboard.</li>
          <li>Mở <strong>8 Agents</strong> để xem lý do hệ thống đưa ra quyết định.</li>
        </ol>
      </section>
    );
  }
  const last = reports[reports.length - 1];
  const m = last.metrics;
  const series = (f: (r: typeof reports[number]) => number) => reports.map(f);

  const faults = reports.flatMap((r) => r.faults);
  const safety = reports.flatMap((r) => r.safety_events);

  // status thresholds (engineering convention): primary loop trips at 45 °C.
  const primaryStatus = m.primary_supply_C >= 44 ? "alarm"
    : m.primary_supply_C >= 42 ? "caution" : "ok";
  const unmetStatus = m.unmet_demand_W > 20000 ? "caution" : "ok";
  const safetyTitle = m.primary_supply_C >= 45 ? "Temperature limit reached"
    : primaryStatus === "caution" || primaryStatus === "alarm" ? "Coolant near the safety limit"
    : "Coolant temperature in the safe band";

  return (
    <div className="ops-grid">
      <section className={`ops-health-banner ${primaryStatus}`}>
        <div>
          <span className="ops-eyebrow">CURRENT OPERATING STATUS</span>
          <h2>{safetyTitle}</h2>
          <p>Primary supply {m.primary_supply_C.toFixed(1)} °C · 45 °C trip limit · {safety.length} safety interventions observed</p>
        </div>
        <button onClick={() => setTab("agents")}>Inspect agent decisions →</button>
      </section>
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <h2>Key indicators · simulated</h2>
        <div className="metrics">
          <Metric label="GPU load" value={m.gpu_load_fraction * 100} unit="%" digits={0} />
          <Metric label="Primary supply" value={m.primary_supply_C} unit="°C" status={primaryStatus} />
          <Metric label="Secondary supply" value={m.secondary_supply_C} unit="°C" />
          <Metric label="Buffer" value={m.buffer_temp_C} unit="°C" />
          <Metric label="Delivered heat" value={m.delivered_total_W / 1000} unit="kW" digits={0} />
          <Metric label="Unmet demand" value={m.unmet_demand_W / 1000} unit="kW" digits={0} status={unmetStatus} />
          <Metric label="Pump power" value={m.pump_power_W / 1000} unit="kW" />
          <Metric label="Unrejected" value={m.primary_unrejected_W / 1000} unit="kW" digits={0} />
        </div>
        {last.scenario_label && <p className="ops-tag">▲ disturbance: {last.scenario_label}</p>}
      </section>

      <section className="card">
        <h2>Thermal limits</h2>
        <Gauge label="Primary coolant supply" value={m.primary_supply_C} unit="°C"
          min={25} max={50} caution={42} alarm={45} />
        <Gauge label="Buffer store" value={m.buffer_temp_C} unit="°C"
          min={20} max={85} caution={70} alarm={80} />
        <Gauge label="GPU load" value={m.gpu_load_fraction * 100} unit="%"
          min={0} max={100} />
      </section>

      <section className="card">
        <h2>Trends (last {reports.length} steps)</h2>
        <Spark label="Primary supply" unit=" °C" color="var(--heat)"
          data={series((r) => r.metrics.primary_supply_C)} />
        <Spark label="GPU load" unit=" %" color="var(--accent)"
          data={series((r) => r.metrics.gpu_load_fraction * 100)} />
        <Spark label="Delivered heat" unit=" kW" color="var(--ok)"
          data={series((r) => r.metrics.delivered_total_W / 1000)} />
        <Spark label="Pump power" unit=" kW" color="var(--violet)"
          data={series((r) => r.metrics.pump_power_W / 1000)} />
      </section>

      <section className="card">
        <h2>Zone temperatures</h2>
        <div className="kv">
          {Object.entries(m.zone_temperature_C).map(([z, t]) => (
            <div key={z}><span>{z.replace("zone_", "")}</span><strong>{t.toFixed(1)} °C</strong></div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Safety & faults</h2>
        <p className="ops-counter">{safety.length} safety interventions · {faults.length} faults this run</p>
        <ul className="ops-list">
          {safety.slice(-6).reverse().map((s, i) => (
            <li key={i}>
              <span className={`pill ${s.kind}`}>{s.kind}</span>
              <code>{s.actuator}</code> — {s.reason}
            </li>
          ))}
          {safety.length === 0 && <li className="muted">no safety interventions yet</li>}
        </ul>
      </section>
    </div>
  );
}
