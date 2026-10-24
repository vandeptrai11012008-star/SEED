import { useMemo } from "react";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { AppConfig, SceneObject, StepRecord } from "../api/types";
import { tempColor } from "./colors";
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

function Plant({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <mesh position={[0, 0.34, 0]}>
        <cylinderGeometry args={[0.025, 0.035, 0.68, 8]} />
        <meshStandardMaterial color="#3f7f3c" roughness={0.8} />
      </mesh>
      {[-0.18, 0.02, 0.22].map((y, index) => (
        <group key={y} position={[0, 0.45 + y, 0]} rotation={[0, index * 2.1, index % 2 ? -0.5 : 0.5]}>
          <mesh position={[0.15, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <sphereGeometry args={[0.18, 10, 8]} />
            <meshStandardMaterial color={index === 2 ? "#69a94c" : "#4b943f"} roughness={0.75} />
          </mesh>
        </group>
      ))}
    </group>
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
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.82} transparent opacity={0.28} roughness={0.08} metalness={0.02} depthWrite={false} />
      </mesh>
      <mesh position={[centerX + halfWidth, eave / 2, 0]}>
        <boxGeometry args={[0.08, eave, greenhouse.depth_y]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.82} transparent opacity={0.28} roughness={0.08} metalness={0.02} depthWrite={false} />
      </mesh>
      <mesh position={[centerX, eave / 2, -halfDepth]}>
        <boxGeometry args={[greenhouse.width_x, eave, 0.08]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.78} transparent opacity={0.24} roughness={0.1} depthWrite={false} />
      </mesh>
      <mesh position={[centerX, eave / 2, halfDepth]}>
        <boxGeometry args={[greenhouse.width_x, eave, 0.08]} />
        <meshPhysicalMaterial color="#a8e0d0" transmission={0.78} transparent opacity={0.24} roughness={0.1} depthWrite={false} />
      </mesh>
      {/* Semi-cylindrical PBR glass roof, flattened to specified 5 m maximum. */}
      <mesh position={[centerX, eave, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, roofRise / halfWidth]}>
        <cylinderGeometry args={[halfWidth, halfWidth, greenhouse.depth_y, 64, 1, true, 0, Math.PI]} />
        <meshPhysicalMaterial color="#b7eadc" transmission={0.82} transparent opacity={0.22} roughness={0.08} side={2} depthWrite={false} />
      </mesh>

      {frameStations.map((station) => (
        <Line key={station} points={archPoints(station)} color="#8a9a94" lineWidth={1.7} />
      ))}
      {[0, eave, greenhouse.max_height_z].map((height) => (
        <Line
          key={height}
          points={[[centerX, height, halfDepth], [centerX, height, -halfDepth]]}
          color="#758982"
          lineWidth={1.6}
        />
      ))}

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
                  <meshStandardMaterial color="#45341f" roughness={1} />
                </mesh>
                {Array.from({ length: 15 }, (_, i) => {
                  const px = -3.1 + (i % 5) * 1.55;
                  const pz = -2.0 + Math.floor(i / 5) * 2.0;
                  return <Plant key={i} position={[px, 0.42, pz]} scale={0.8 + (i % 3) * 0.08} />;
                })}
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
        text="Research Greenhouse"
        subtext={`${greenhouse.width_x} × ${greenhouse.depth_y} × ${greenhouse.max_height_z} m · soil ${step?.soil_temp_C?.toFixed(1) ?? "—"} °C`}
        position={[centerX, 6.3, 0]}
        accent="#66c786"
      />
      <pointLight position={[centerX, 4.3, 0]} intensity={36} distance={35} color="#ffe8ba" />
    </group>
  );
}
