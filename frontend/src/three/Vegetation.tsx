import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

type Entry = { matrix: THREE.Matrix4; color: string };
const matrix = (p: number[], s: number[], r = [0, 0, 0]) => new THREE.Matrix4().compose(
  new THREE.Vector3(...p), new THREE.Quaternion().setFromEuler(new THREE.Euler(...r)), new THREE.Vector3(...s),
);

function Batch({ geometry, entries, doubleSide = false }: { geometry: THREE.BufferGeometry; entries: Entry[]; doubleSide?: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current!;
    entries.forEach((entry, i) => {
      mesh.setMatrixAt(i, entry.matrix);
      mesh.setColorAt(i, new THREE.Color(entry.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [entries]);
  return <instancedMesh ref={ref} args={[geometry, undefined, entries.length]} castShadow receiveShadow>
    <meshStandardMaterial roughness={.82} side={doubleSide ? THREE.DoubleSide : THREE.FrontSide} />
  </instancedMesh>;
}

function leafGeometry() {
  const shape = new THREE.PlaneGeometry(1, 1, 10, 4);
  const pos = shape.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const u = pos.getX(i) + .5;
    const v = pos.getY(i) * 2;
    pos.setXYZ(i, u * .58, Math.sin(u * Math.PI) * .08 + u * u * .1,
      v * Math.sin(u * Math.PI) * .18 * (1 - .3 * u));
  }
  shape.computeVertexNormals();
  return shape;
}

/** Detailed crops use three draw calls per bed instead of one mesh per leaf. */
export function CropBed({ width, depth, scale = 1 }: { width: number; depth: number; scale?: number }) {
  const resources = useMemo(() => [leafGeometry(), new THREE.CylinderGeometry(1, 1, 1, 6), new THREE.SphereGeometry(.075, 8, 6)], []);
  useEffect(() => () => resources.forEach(g => g.dispose()), [resources]);
  const data = useMemo(() => {
    const leaves: Entry[] = [], stems: Entry[] = [], fruit: Entry[] = [];
    for (let i = 0; i < 15; i++) {
      const x = -width / 2 + .65 + (i % 5) * (width - 1.3) / 4;
      const z = -depth / 2 + .6 + Math.floor(i / 5) * (depth - 1.2) / 2;
      const height = (.82 + (i % 4) * .07) * scale;
      stems.push({ matrix: matrix([x, height / 2, z], [.024 * scale, height, .024 * scale]), color: "#587143" });
      // Slender growing strings support the crop without hiding the glazing.
      stems.push({ matrix: matrix([x + .08, .65 * scale, z], [.006, 1.3 * scale, .006]), color: "#bbc0a1" });
      for (let j = 0; j < 8; j++) {
        const angle = j * 2.399 + i * .7;
        const leafScale = scale * (.8 + (j % 3) * .13);
        leaves.push({ matrix: matrix([x, height * (.2 + j * .09), z], [leafScale, leafScale, leafScale], [0, angle, -.15 + (j % 2) * .3]), color: ["#295b2f", "#3e6b31", "#5a7c37", "#2e5832"][(i + j) % 4] });
      }
      for (let j = 0; j < 3; j++) {
        const angle = i + j * 2.1;
        fruit.push({ matrix: matrix([x + Math.cos(angle) * .16 * scale, height * (.5 + j * .1), z + Math.sin(angle) * .16 * scale], [scale, scale, scale]), color: (i + j) % 4 === 0 ? "#d86132" : "#819c46" });
      }
    }
    return { leaves, stems, fruit };
  }, [width, depth, scale]);
  return <group name="supported-greenhouse-crops">
    <Batch geometry={resources[0]} entries={data.leaves} doubleSide />
    <Batch geometry={resources[1]} entries={data.stems} />
    <Batch geometry={resources[2]} entries={data.fruit} />
  </group>;
}

export function LandscapeTrees() {
  const resources = useMemo(() => [new THREE.CylinderGeometry(1, 1, 1, 8), new THREE.SphereGeometry(1, 10, 8)], []);
  useEffect(() => () => resources.forEach(g => g.dispose()), [resources]);
  const data = useMemo(() => {
    const trunks: Entry[] = [], foliage: Entry[] = [];
    for (let i = 0; i < 24; i++) {
      const x = -36 + i * 5, z = -25 - (i % 3) * 2;
      const h = 3.8 + (i % 4) * .7;
      trunks.push({ matrix: matrix([x, h / 2, z], [.16, h, .16]), color: "#6c6048" });
      for (let j = 0; j < 26; j++) {
        const v = 1 - 2 * (j + .5) / 26;
        const angle = j * 2.399 + i;
        const radius = Math.sqrt(1 - v * v) * 1.9;
        foliage.push({ matrix: matrix([x + Math.cos(angle) * radius, h + .9 + v * 1.8, z + Math.sin(angle) * radius], [.8 + (j % 3) * .1, .5 + (j % 3) * .08, .9]), color: ["#587b42", "#6d894b", "#3d6845", "#829452"][(i + j) % 4] });
      }
    }
    return { trunks, foliage };
  }, []);
  return <group name="planted-landscape">
    <Batch geometry={resources[0]} entries={data.trunks} />
    <Batch geometry={resources[1]} entries={data.foliage} />
  </group>;
}
