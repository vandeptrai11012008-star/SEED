import type { SimulationResult } from "../api/types";

function download(name: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportRun(result: SimulationResult | undefined, kind: "json" | "csv") {
  if (!result) return;
  if (kind === "json") {
    download(`${result.run_id}.json`, JSON.stringify(result, null, 2), "application/json");
    return;
  }
  const series = result.series ?? [];
  if (series.length === 0) return;
  const cols = Object.keys(series[0]).filter((c) => c !== "zone_delivered_W");
  const zoneKeys = Object.keys(series[0].zone_delivered_W ?? {});
  const header = [...cols, ...zoneKeys.map((z) => `delivered_${z}_W`)].join(",");
  const rows = series.map((r) => {
    const base = cols.map((c) => (r as any)[c]);
    const zones = zoneKeys.map((z) => r.zone_delivered_W[z]);
    return [...base, ...zones].join(",");
  });
  download(`${result.run_id}.csv`, [header, ...rows].join("\n"), "text/csv");
}
