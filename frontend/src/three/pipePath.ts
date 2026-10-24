import * as THREE from "three";

/** Straight pipe runs with local, bounded elbows. Never spline through walls. */
export function pipePath(points: THREE.Vector3[], elbowRadius = 0.38): THREE.CurvePath<THREE.Vector3> {
  const path = new THREE.CurvePath<THREE.Vector3>();
  let previous = points[0];
  for (let i = 1; i < points.length - 1; i++) {
    const corner = points[i];
    const incoming = corner.clone().sub(points[i - 1]);
    const outgoing = points[i + 1].clone().sub(corner);
    const radius = Math.min(elbowRadius, incoming.length() * 0.3, outgoing.length() * 0.3);
    if (radius < 0.0001) continue;
    const entry = corner.clone().addScaledVector(incoming.normalize(), -radius);
    const exit = corner.clone().addScaledVector(outgoing.normalize(), radius);
    path.add(new THREE.LineCurve3(previous, entry));
    path.add(new THREE.QuadraticBezierCurve3(entry, corner, exit));
    previous = exit;
  }
  path.add(new THREE.LineCurve3(previous, points[points.length - 1]));
  return path;
}
