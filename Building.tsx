import { useStore } from "../store";
import Architecture from "./Architecture";
import Greenhouse from "./Greenhouse";
import Hydronics from "./Hydronics";
import InteriorEquipment from "./InteriorEquipment";
import ServerHalls from "./ServerHall";

// Entirely procedural facility. No GLB / Blender / external assets: every mesh
// below is generated at runtime with Three.js geometry.
function UndergroundSection() {
  return (
    <group name="underground-cross-section">
      {/* Utility tunnel: open-front concrete shell between building and greenhouse. */}
      <mesh position={[22, -3.02, 0]} receiveShadow>
        <boxGeometry args={[8.4, 0.18, 2.8]} />
        <meshStandardMaterial color="#69737a" roughness={0.88} />
      </mesh>
      <mesh position={[22, -1.48, 0]}>
        <boxGeometry args={[8.4, 0.18, 2.8]} />
        <meshStandardMaterial color="#69737a" roughness={0.88} />
      </mesh>
      {[-1.32, 1.32].map((z) => (
        <mesh key={z} position={[22, -2.25, z]}>
          <boxGeometry args={[8.4, 1.55, 0.16]} />
          <meshStandardMaterial color="#69737a" roughness={0.88} />
        </mesh>
      ))}
      {/* Reinforced concrete foundation raft under the whole building footprint. */}
      <mesh position={[0, -8.85, 0]} receiveShadow>
        <boxGeometry args={[37.5, 0.7, 23.5]} />
        <meshStandardMaterial color="#52575c" roughness={0.95} metalness={0.05} />
      </mesh>
      {/* Perimeter pile caps. */}
      {[-17, -8.5, 0, 8.5, 17].map((x) =>
        [-10.5, 10.5].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, -8.65, z]} receiveShadow>
            <boxGeometry args={[1.6, 0.9, 1.6]} />
            <meshStandardMaterial color="#5a6066" roughness={0.95} />
          </mesh>
        )),
      )}
      {/* Layered soil cut faces showing excavation depth and grade. */}
      <mesh position={[-25, -4.25, 0]} receiveShadow>
        <boxGeometry args={[14, 8.5, 24]} />
        <meshStandardMaterial color="#5a4a35" roughness={1} />
      </mesh>
      <mesh position={[-25, -1.4, 0]}>
        <boxGeometry args={[14.02, 1.6, 24.02]} />
        <meshStandardMaterial color="#6b5a40" roughness={1} />
      </mesh>
      <mesh position={[68, -2.2, 0]} receiveShadow>
        <boxGeometry args={[24, 4.4, 24]} />
        <meshStandardMaterial color="#5a4a35" roughness={1} />
      </mesh>
    </group>
  );
}

// Procedural core-and-stair tower spanning every level, so floors read as one
// connected building rather than stacked slabs.
function AccessCore({ visibleFloors }: { visibleFloors: Record<string, boolean> }) {
  const steel = "#6a7883";
  const landings: { id: string; z0: number; z1: number }[] = [
    { id: "b2", z0: -8.5, z1: -4.0 },
    { id: "b1", z0: -4.0, z1: 0.0 },
    { id: "gf", z0: 0.0, z1: 4.5 },
    { id: "f1", z0: 4.5, z1: 9.0 },
    { id: "f2", z0: 9.0, z1: 13.5 },
    { id: "f3", z0: 13.5, z1: 18.0 },
  ];
  return (
    <group name="access-core">
      {/* Core shaft shell on the east side of the plan. */}
      <mesh position={[15, 4.75, 8]}>
        <boxGeometry args={[4.2, 26.6, 4.2]} />
        <meshStandardMaterial color="#3d4650" roughness={0.8} transparent opacity={0.18} />
      </mesh>
      {landings.map((floor) => {
        if (!visibleFloors[floor.id]) return null;
        const steps = 10;
        const rise = (floor.z1 - floor.z0) / steps;
        return (
          <group key={floor.id} name={`stair_${floor.id}`}>
            {/* Half-landing. */}
            <mesh position={[15, floor.z0 + 0.35, 9.3]} castShadow receiveShadow>
              <boxGeometry args={[3.6, 0.14, 1.4]} />
              <meshStandardMaterial color={steel} metalness={0.6} roughness={0.4} />
            </mesh>
            {/* Procedural flight of treads. */}
            {Array.from({ length: steps }, (_, i) => (
              <mesh
                key={i}
                position={[13.6 + (i / steps) * 2.8, floor.z0 + 0.35 + i * rise, 7.4]}
                castShadow
              >
                <boxGeometry args={[0.32, 0.05, 1.3]} />
                <meshStandardMaterial color={steel} metalness={0.6} roughness={0.4} />
              </mesh>
            ))}
          </group>
        );
      })}
    </group>
  );
}

export default function Building() {
  const config = useStore((state) => state.config);
  const scene = useStore((state) => state.scene);
  const cutaway = useStore((state) => state.cutaway);
  const visibleFloors = useStore((state) => state.visibleFloors);
  const pipeOverlay = useStore((state) => state.pipeOverlay);
  const selectedId = useStore((state) => state.selectedId);
  const select = useStore((state) => state.select);
  const cameraPreset = useStore((state) => state.cameraPreset);
  const showSoil = useStore((state) => state.showGreenhouseSoil);
  const step = useStore((state) => state.currentStep());

  if (!config || !scene) return null;
  const beds = scene.objects.filter((object) => object.kind === "growing_bed");

  return (
    <group name="thermalloop-facility" onPointerMissed={() => select(undefined)}>
      <Architecture
        config={config}
        visibleFloors={visibleFloors}
        cutaway={cutaway}
        undergroundView={cameraPreset === "underground"}
      />
      <AccessCore visibleFloors={visibleFloors} />
      <UndergroundSection />
      <ServerHalls
        objects={scene.objects}
        visibleFloors={visibleFloors}
        step={step}
        selectedId={selectedId}
        onSelect={select}
      />
      <InteriorEquipment
        objects={scene.objects}
        visibleFloors={visibleFloors}
        step={step}
        selectedId={selectedId}
        onSelect={select}
      />
      <Greenhouse
        config={config}
        beds={beds}
        step={step}
        showSoil={showSoil}
        selectedId={selectedId}
        onSelect={select}
      />
      <Hydronics
        pipes={scene.pipes}
        objects={scene.objects}
        step={step}
        overlay={pipeOverlay}
        selectedId={selectedId}
        onSelect={select}
      />
    </group>
  );
}
