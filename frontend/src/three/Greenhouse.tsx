import { useMemo } from "react";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { AppConfig, SceneObject, StepRecord } from "../api/types";
import { useStore } from "../store";
import { tempColor } from "./colors";
import { CropBed } from "./Vegetation";
import { useSurfaceTexture } from "./surfaceTextures";
import EngineeringLabel from "./Label";

// Serpentine soil-heating circuit buried under one bed, generated as a tube.
function SoilHeatingCoil({
  width,
  depth,
  temperatureC,
}: {
  width: number;
  depth: number;
  temperatureC: number;
}) {
  const geometry = useMemo(() => {
    const passes = 5;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < passes; i += 1) {
      const z = -depth / 2 + 0.6 + (i * (depth - 1.2)) / (passes - 1);
      const x0 = -width / 2 + 0.6;
      const x1 = width / 2 - 0.6;
      const y = 0.12; // just inside the exposed bed frame so pipes read clearly
      if (i % 2 === 0) {
        pts.push(new THREE.Vector3(x0, y, z), new THREE.Vector3(x1, y, z));
      } else {
        pts.push(new THREE.Vector3(x1, y, z), new THREE.Vector3(x0, y, z));
      }
    }
    const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.1);
    return new THREE.TubeGeometry(curve, 140, 0.06, 10, false);
  }, [width, depth]);
  const color = `#${tempColor(temperatureC, 25, 60).getHexString()}`;
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} metalness={0.5} roughness={0.3} />
    </mesh>
  );
}

export default function Greenhouse({
  config,
  beds,
  step,
  showSoil,
  selectedId,
  onSelect,
}: {
  config: AppConfig;
  beds: SceneObject[];
  step?: StepRecord;
  showSoil: boolean;
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  const illustration = useStore(s => s.illustration);
  const soilTexture = useSurfaceTexture("soil");
  const soilSupplyC = step?.secondary_supply_C ?? 45;
  const greenhouse = config.geometry.greenhouse;
  const centerX = greenhouse.center[0] as number;
  const halfWidth = greenhouse.width_x / 2;
  const halfDepth = greenhouse.depth_y / 2;
  const eave = 2.35;
  const roofRise = greenhouse.max_height_z - eave;

  const frameStations = useMemo(
    () => Array.from({ length: 10 }, (_, i) => -halfDepth + (i * greenhouse.depth_y) / 9),
    [greenhouse.depth_y, halfDepth],
  );
  const archPoints = (worldY: number): [number, number, number][] => {
    if (illustration) return [
      [centerX - halfWidth, 0, -worldY], [centerX - halfWidth, eave, -worldY],
      [centerX, greenhouse.max_height_z, -worldY], [centerX + halfWidth, eave, -worldY],
      [centerX + halfWidth, 0, -worldY],
    ];
    const points: [number, number, number][] = [[centerX - halfWidth, 0, -worldY], [centerX - halfWidth, eave, -worldY]];
    for (let i = 0; i <= 24; i += 1) {
      const theta = Math.PI - (Math.PI * i) / 24;
      points.push([
        centerX + halfWidth * Math.cos(theta),
        eave + roofRise * Math.sin(theta),
        -worldY,
      ]);
    }
    points.push([centerX + halfWidth, 0, -worldY]);
    return points;
  };

  return (
    <group name="greenhouse" onClick={(e) => e.stopPropagation()}>
      {/* Glass side walls; arched steel frames define the roof exactly. */}
      <mesh position={[centerX - halfWidth, eave / 2, 0]}>
        <boxGeometry args={[0.08, eave, greenhouse.depth_y]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.3} transparent opacity={0.17} roughness={0.08} metalness={0.02} depthWrite={false} />
      </mesh>
      <mesh position={[centerX + halfWidth, eave / 2, 0]}>
        <boxGeometry args={[0.08, eave, greenhouse.depth_y]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.3} transparent opacity={0.17} roughness={0.08} metalness={0.02} depthWrite={false} />
      </mesh>
      <mesh position={[centerX, eave / 2, -halfDepth]}>
        <boxGeometry args={[greenhouse.width_x, eave, 0.08]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.3} transparent opacity={0.13} roughness={0.1} depthWrite={false} />
      </mesh>
      <mesh position={[centerX, eave / 2, halfDepth]}>
        <boxGeometry args={[greenhouse.width_x, eave, 0.08]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.3} transparent opacity={0.13} roughness={0.1} depthWrite={false} />
      </mesh>
      {/* Semi-cylindrical PBR glass roof, flattened to specified 5 m maximum. */}
      {!illustration && <mesh position={[centerX, eave, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, roofRise / halfWidth]}>
        <cylinderGeometry args={[halfWidth, halfWidth, greenhouse.depth_y, 64, 1, true, 0, Math.PI]} />
        <meshPhysicalMaterial color="#b7eadc" transmission={0.82} transparent opacity={0.22} roughness={0.08} side={2} depthWrite={false} />
      </mesh>}

      {illustration && [-1, 1].map(side => <mesh key={`roof-${side}`} position={[centerX + side * halfWidth / 2, eave + roofRise / 2, 0]} rotation={[0, 0, -side * Math.atan2(roofRise, halfWidth)]}>
        <boxGeometry args={[Math.hypot(halfWidth, roofRise), .045, greenhouse.depth_y]} />
        <meshPhysicalMaterial color="#cde6f0" transparent opacity={.22} roughness={.09} metalness={.12} clearcoat={1} clearcoatRoughness={.1} depthWrite={false} />
      </mesh>)}
      {illustration && Array.from({ length: 11 }, (_, i) => centerX - halfWidth + i * greenhouse.width_x / 10).map(x => <Line key={`front-mullion-${x}`} points={[[x, 0, halfDepth], [x, eave + roofRise * (1 - Math.abs(x - centerX) / halfWidth), halfDepth]]} color="#746955" lineWidth={2.4} />)}
      {frameStations.map((station) => (
        <Line key={station} points={archPoints(station)} color="#706a59" lineWidth={2.3} />
      ))}
      {[0, eave, greenhouse.max_height_z].map((height) => (
        <Line
          key={height}
          points={[[centerX, height, halfDepth], [centerX, height, -halfDepth]]}
          color="#758982"
          lineWidth={1.6}
        />
      ))}

      {[-halfDepth, halfDepth].map(z => <mesh key={`greenhouse-plinth-${z}`} position={[centerX, -.12, z]} receiveShadow>
        <boxGeometry args={[greenhouse.width_x + .3, .45, .35]} /><meshStandardMaterial color="#a2a294" roughness={.85} />
      </mesh>)}
      {Array.from({ length: 9 }, (_, i) => centerX - halfWidth + 1.5 + i * 3.35).map(x => <group key={`roof-rails-${x}`}>
        <Line points={[[x, eave + roofRise * (1 - Math.abs(x - centerX) / halfWidth), -halfDepth], [x, eave + roofRise * (1 - Math.abs(x - centerX) / halfWidth), halfDepth]]} color="#8b8671" lineWidth={1.5} />
      </group>)}
      {beds.map((bed) => {
        const [x, y] = bed.center!;
        return (
          <group
            key={bed.id}
            position={[x, 0, -y]}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(bed.id);
            }}
          >
            {/* Raised bed frame always visible; soil fill + plants hide so the
                buried heating pipes can be inspected. */}
            <mesh position={[0, 0.1, 0]} receiveShadow castShadow>
              <boxGeometry args={[bed.size![0], 0.2, bed.size![1]]} />
              <meshStandardMaterial color="#6a7179" roughness={0.7} metalness={0.3} />
            </mesh>
            {showSoil ? (
              <>
                <mesh position={[0, 0.3, 0]} receiveShadow castShadow>
                  <boxGeometry args={[bed.size![0] - 0.1, 0.24, bed.size![1] - 0.1]} />
                  <meshStandardMaterial map={soilTexture} bumpMap={soilTexture} bumpScale={.045} roughness={1} />
                </mesh>
                <group position={[0, .42, 0]}>
                  <CropBed width={bed.size![0]} depth={bed.size![1]} scale={illustration ? 1.55 : .95} />
                </group>
              </>
            ) : (
              <SoilHeatingCoil width={bed.size![0]} depth={bed.size![1]} temperatureC={soilSupplyC} />
            )}
            {selectedId === bed.id && (
              <EngineeringLabel
                text={bed.id}
                subtext={showSoil ? "Hydronically heated soil bed" : `Soil heating coil · ${soilSupplyC.toFixed(1)} °C supply`}
                position={[0, 2.0, 0]}
                accent="#69b958"
              />
            )}
          </group>
        );
      })}

      <EngineeringLabel
        text="Greenhouse"
        subtext={`${greenhouse.width_x} × ${greenhouse.depth_y} × ${greenhouse.max_height_z} m · soil ${step?.soil_temp_C?.toFixed(1) ?? "—"} °C`}
        position={[centerX, illustration ? 4.8 : 6.3, halfDepth + 1]}
        accent="#66c786"
      />
      <pointLight position={[centerX, 4.3, 0]} intensity={36} distance={35} color="#ffe8ba" />
    </group>
  );
}
