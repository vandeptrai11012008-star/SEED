import * as THREE from "three";

export type WorldPoint = [number, number, number];

/** Project coordinates (X east, Y north, Z up) -> Three.js (X east, Y up, Z south). */
export function worldVector([x, y, z]: WorldPoint): THREE.Vector3 {
  return new THREE.Vector3(x, z, -y);
}

export function worldPosition(point: WorldPoint): [number, number, number] {
  const v = worldVector(point);
  return [v.x, v.y, v.z];
}

/** Project dimensions [width X, depth Y, height Z] -> Three dimensions. */
export function worldSize([x, y, z]: WorldPoint): [number, number, number] {
  return [x, z, y];
}
