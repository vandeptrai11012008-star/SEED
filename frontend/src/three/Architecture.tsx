import { Fragment } from "react";
import { Line } from "@react-three/drei";
import type { AppConfig } from "../api/types";
import type { FloorId } from "../store";
import EngineeringLabel from "./Label";

const FLOOR_COLORS: Record<FloorId, string> = {
  b2: "#44515d",
  b1: "#6a5b49",
  gf: "#53677a",
  f1: "#435668",
  f2: "#435668",
  f3: "#435668",
};

function SteelMember({
  position,
  scale,
}: {
  position: [number, number, number];
  scale: [number, number, number];
}) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={scale} />
      <meshStandardMaterial color="#667681" metalness={0.82} roughness={0.28} />
    </mesh>
  );
}

export default function Architecture({
  config,
  visibleFloors,
  cutaway,
  undergroundView,
}: {
  config: AppConfig;
  visibleFloors: Record<FloorId, boolean>;
  cutaway: boolean;
  undergroundView: boolean;
}) {
  const geometry = config.geometry;
  const building = geometry.main_building;
  const floors = geometry.floors as Array<{
    id: FloorId;
    name: string;
    use: string;
    z: [number, number];
  }>;

  return (
    <group name="architectural-structure">
      {floors.map((floor) => {
        if (!visibleFloors[floor.id]) return null;
        const [z0, z1] = floor.z;
        const height = z1 - z0;
        const isBasement = z1 <= 0;
        const isGpu = floor.use === "gpu_data_center";
        return (
          <group key={floor.id} name={`architectural_${floor.id}`}>
            {/* Reinforced concrete slab at the exact floor datum. */}
            <mesh position={[0, z0 + 0.14, 0]} receiveShadow castShadow>
              <boxGeometry args={[building.width_x, 0.28, building.depth_y]} />
              <meshStandardMaterial
                color={FLOOR_COLORS[floor.id]}
                roughness={0.82}
                metalness={0.05}
              />
            </mesh>

            {/* Perimeter edge beam makes every floor legible in cutaway. */}
            <SteelMember position={[0, z1 - 0.22, -10.75]} scale={[35.5, 0.35, 0.35]} />
            {!cutaway && (
              <SteelMember position={[0, z1 - 0.22, 10.75]} scale={[35.5, 0.35, 0.35]} />
            )}
            <SteelMember position={[-17.75, z1 - 0.22, 0]} scale={[0.35, 0.35, 21.5]} />
            <SteelMember position={[17.75, z1 - 0.22, 0]} scale={[0.35, 0.35, 21.5]} />

            {/* 5 x 3 structural grid, full floor-to-floor height. */}
            {[-17.3, -8.65, 0, 8.65, 17.3].map((x) =>
              [-10.3, 0, 10.3].map((z) => {
                if (cutaway && z > 9) return null;
                return (
                  <SteelMember
                    key={`${x}-${z}`}
                    position={[x, z0 + height / 2, z]}
                    scale={[0.28, height, 0.28]}
                  />
                );
              }),
            )}

            {cutaway && <>
              <mesh position={[0, z0 + height / 2, -10.65]} receiveShadow>
                <boxGeometry args={[35.4, height - .3, .12]} />
                <meshStandardMaterial color={isGpu ? "#364452" : "#8b8272"} roughness={.72} />
              </mesh>
              {[-12, -4, 4, 12].map(x => <mesh key={`ceiling-light-${x}`} position={[x, z1 - .36, 0]}>
                <boxGeometry args={[5, .06, .12]} />
                <meshStandardMaterial color="#fff3d8" emissive="#fff0cc" emissiveIntensity={2} toneMapped={false} />
              </mesh>)}
            </>}
            {/* Central service walkway / equipment aisle. */}
            <mesh position={[0, z0 + 0.31, 0]} receiveShadow>
              <boxGeometry args={[32, 0.06, isGpu ? 2.2 : 1.5]} />
              <meshStandardMaterial color="#8996a1" metalness={0.25} roughness={0.55} />
            </mesh>

            {/* Fire-rated equipment/zone partitions with a central access opening. */}
            {!cutaway && (floor.id === "b1" || floor.id === "b2") && [-6.5, 6.5].map((z) => (
              <mesh key={`partition-${z}`} position={[0, z0 + height / 2, z]} castShadow>
                <boxGeometry args={[0.16, height - 0.35, 8.5]} />
                <meshStandardMaterial color={floor.id === "b2" ? "#6f7b82" : "#879087"} roughness={0.72} metalness={0.18} />
              </mesh>
            ))}
            {floor.id === "b2" && [-9, -3, 3, 9].map((x) => (
              <mesh key={`equipment-pad-${x}`} position={[x, z0 + 0.24, 3.8]} receiveShadow>
                <boxGeometry args={[4.4, 0.2, 3.3]} />
                <meshStandardMaterial color="#7b858b" roughness={0.88} />
              </mesh>
            ))}

            {/* Basement retaining walls; front removed in cutaway. */}
            {isBasement && (
              <>
                <mesh position={[-17.86, z0 + height / 2, 0]}>
                  <boxGeometry args={[0.28, height, 22]} />
                  <meshStandardMaterial color="#58616a" roughness={0.9} />
                </mesh>
                <mesh position={[17.86, z0 + height / 2, 0]}>
                  <boxGeometry args={[0.28, height, 22]} />
                  <meshStandardMaterial color="#58616a" roughness={0.9} />
                </mesh>
                <mesh position={[0, z0 + height / 2, -10.86]}>
                  <boxGeometry args={[36, height, 0.28]} />
                  <meshStandardMaterial color="#58616a" roughness={0.9} />
                </mesh>
                {!cutaway && (
                  <mesh position={[0, z0 + height / 2, 10.86]}>
                    <boxGeometry args={[36, height, 0.28]} />
                    <meshStandardMaterial color="#58616a" roughness={0.9} />
                  </mesh>
                )}
              </>
            )}

            <pointLight
              position={[0, z0 + height - 0.45, 0]}
              intensity={isBasement ? 34 : 24}
              distance={28}
              color={isGpu ? "#cce7ff" : "#ffe7c7"}
            />
            {cutaway && (
              <EngineeringLabel
                text={({ f3: "3F · AI DATA CENTER", f2: "2F · AI DATA CENTER", f1: "1F · AI DATA CENTER", gf: "GF · ROBOT LAB", b1: "B1 · SEED RESEARCH", b2: "B2 · HEAT EXCHANGER" })[floor.id]}
                subtext={isGpu ? "GPU servers / Liquid cooling" : floor.id === "b2" ? "Underground mechanical plant" : "Recovered heat / Research zone"}
                position={[-16, z0 + height - 0.9, 11.5]}
                accent={isGpu ? "#45a8ff" : isBasement ? "#d4a96a" : "#9dd7ff"}
              />
            )}
          </group>
        );
      })}

      {/* Above-grade glass curtain wall assembled as real panels. */}
      {Array.from({ length: 8 }, (_, level) => {
        const y = 1.125 + level * 2.25;
        return (
          <Fragment key={`glass-level-${level}`}>
            <mesh position={[-17.9, y, 0]}>
              <boxGeometry args={[0.12, 2.05, 21.6]} />
              <meshPhysicalMaterial color="#80b9ce" transmission={0.72} transparent opacity={0.25} roughness={0.12} metalness={0.05} depthWrite={false} />
            </mesh>
            <mesh position={[17.9, y, 0]}>
              <boxGeometry args={[0.12, 2.05, 21.6]} />
              <meshPhysicalMaterial color="#80b9ce" transmission={0.72} transparent opacity={0.25} roughness={0.12} metalness={0.05} depthWrite={false} />
            </mesh>
            <mesh position={[0, y, -10.9]}>
              <boxGeometry args={[35.7, 2.05, 0.12]} />
              <meshPhysicalMaterial color="#80b9ce" transmission={0.72} transparent opacity={0.22} roughness={0.12} depthWrite={false} />
            </mesh>
            {!cutaway && (
              <mesh position={[0, y, 10.9]}>
                <boxGeometry args={[35.7, 2.05, 0.12]} />
                <meshPhysicalMaterial color="#80b9ce" transmission={0.72} transparent opacity={0.25} roughness={0.12} depthWrite={false} />
              </mesh>
            )}
          </Fragment>
        );
      })}

      {/* Curtain-wall mullions and roof edge. */}
      {[-18, -12, -6, 0, 6, 12, 18].map((x) => (
        <SteelMember key={`mullion-${x}`} position={[x, 9, -10.96]} scale={[0.12, 18, 0.18]} />
      ))}
      {!cutaway && (
        <mesh position={[0, 18.12, 0]} receiveShadow castShadow>
          <boxGeometry args={[36.4, 0.24, 22.4]} />
          <meshStandardMaterial color="#27343f" metalness={0.5} roughness={0.4} />
        </mesh>
      )}

      {/* Ground datum and excavation edge — ground is exactly world Z=0. */}
      {!undergroundView && !cutaway && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[19, -0.04, 0]} receiveShadow>
          <planeGeometry args={[120, 70]} />
          <meshStandardMaterial color="#273229" roughness={0.96} />
        </mesh>
      )}
      <Line
        points={[[-18, 0.03, 11], [18, 0.03, 11], [18, 0.03, -11], [-18, 0.03, -11], [-18, 0.03, 11]]}
        color="#e9b872"
        lineWidth={1.4}
      />
    </group>
  );
}
