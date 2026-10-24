import * as THREE from "three";

// Map a temperature (deg C) to a blue->red color for water visualization.
// Clamped to [tMin, tMax]. Deterministic; purely for display.
export function tempColor(tC: number, tMin = 25, tMax = 60): THREE.Color {
  const t = Math.max(0, Math.min(1, (tC - tMin) / (tMax - tMin)));
  // blue (cold) -> orange -> red (hot)
  const cold = new THREE.Color(0.29, 0.64, 1.0);
  const mid = new THREE.Color(1.0, 0.65, 0.34);
  const hot = new THREE.Color(1.0, 0.35, 0.37);
  if (t < 0.5) return cold.clone().lerp(mid, t / 0.5);
  return mid.clone().lerp(hot, (t - 0.5) / 0.5);
}

export const KIND_COLOR: Record<string, string> = {
  building_shell: "#3a4654",
  floor_slab: "#2a3544",
  gpu_rack: "#6e86a3",
  greenhouse_shell: "#2e7d4f",
  growing_bed: "#5a3b22",
  utility_corridor: "#4a4a2a",
  heat_exchanger: "#c77dff",
  pump: "#ffd166",
  tank: "#4cc9f0",
  heat_pump: "#f72585",
};

export function kindColor(kind: string): string {
  return KIND_COLOR[kind] ?? "#7d8590";
}
