import type { SceneObject, StepRecord } from "../api/types";
import type { FloorId } from "../store";
import { worldPosition } from "./coordinates";
import EngineeringLabel from "./Label";

function RobotArm({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      <mesh position={[0, 0.15, 0]} castShadow>
        <cylinderGeometry args={[0.65, 0.8, 0.3, 24]} />
        <meshStandardMaterial color="#26323d" metalness={0.8} roughness={0.28} />
      </mesh>
      <group rotation={[0, 0.35, -0.32]} position={[0, 0.45, 0]}>
        <mesh position={[0, 0.75, 0]} castShadow>
          <cylinderGeometry args={[0.22, 0.31, 1.5, 20]} />
          <meshStandardMaterial color="#f4a62a" metalness={0.62} roughness={0.3} />
        </mesh>
        <mesh position={[0, 1.52, 0]}>
          <sphereGeometry args={[0.34, 20, 16]} />
          <meshStandardMaterial color="#202a33" metalness={0.8} />
        </mesh>
        <group position={[0.45, 1.98, 0]} rotation={[0, 0, -0.78]}>
          <mesh position={[0, 0.55, 0]} castShadow>
            <cylinderGeometry args={[0.16, 0.22, 1.1, 18]} />
            <meshStandardMaterial color="#f4a62a" metalness={0.62} roughness={0.3} />
          </mesh>
          <mesh position={[0, 1.16, 0]}>
            <sphereGeometry args={[0.22, 18, 12]} />
            <meshStandardMaterial color="#202a33" metalness={0.8} />
          </mesh>
          <mesh position={[0, 1.43, 0]}>
            <boxGeometry args={[0.5, 0.12, 0.16]} />
            <meshStandardMaterial color="#768692" metalness={0.9} roughness={0.2} />
          </mesh>
        </group>
      </group>
      {selected && <EngineeringLabel text={object.id} subtext="Industrial robot cell" position={[0, 3.25, 0]} accent="#f4a62a" />}
    </group>
  );
}

function SeedRack({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      {[-0.9, 0.9].map((x) => [-0.48, 0.48].map((z) => (
        <mesh key={`${x}-${z}`} position={[x, 0, z]}>
          <boxGeometry args={[0.08, 2.5, 0.08]} />
          <meshStandardMaterial color="#77838c" metalness={0.9} roughness={0.25} />
        </mesh>
      )))}
      {[-1.05, -0.52, 0.02, 0.56, 1.1].map((y, i) => (
        <group key={y} position={[0, y, 0]}>
          <mesh>
            <boxGeometry args={[1.9, 0.07, 1.05]} />
            <meshStandardMaterial color="#87949c" metalness={0.72} roughness={0.38} />
          </mesh>
          {[-0.6, 0, 0.6].map((x) => (
            <mesh key={x} position={[x, 0.09, 0]}>
              <boxGeometry args={[0.45, 0.13, 0.72]} />
              <meshStandardMaterial color={i % 2 ? "#967344" : "#aa874f"} roughness={0.8} />
            </mesh>
          ))}
        </group>
      ))}
      {selected && <EngineeringLabel text={object.id} subtext="Seed storage rack" position={[0, 1.75, 0]} accent="#d5b06b" />}
    </group>
  );
}

function GrowthChamber({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      <mesh castShadow>
        <boxGeometry args={[2, 2.5, 1.2]} />
        <meshStandardMaterial color="#d4dde1" metalness={0.58} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0, 0.611]}>
        <boxGeometry args={[1.65, 2.05, 0.04]} />
        <meshPhysicalMaterial color="#8ed4df" transmission={0.5} transparent opacity={0.58} roughness={0.12} />
      </mesh>
      {[-0.6, -0.1, 0.4].map((y) => (
        <mesh key={y} position={[0, y, 0.64]}>
          <boxGeometry args={[1.35, 0.035, 0.025]} />
          <meshStandardMaterial color="#a9fff4" emissive="#5fdccf" emissiveIntensity={2.2} />
        </mesh>
      ))}
      <mesh position={[0.65, 0.9, 0.66]}>
        <boxGeometry args={[0.22, 0.14, 0.025]} />
        <meshStandardMaterial color="#57e29d" emissive="#57e29d" emissiveIntensity={3} />
      </mesh>
      {selected && <EngineeringLabel text={object.id} subtext="Controlled germination chamber" position={[0, 1.8, 0]} accent="#75dfce" />}
    </group>
  );
}

function PlateHeatExchanger({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      {Array.from({ length: 15 }, (_, i) => (
        <mesh key={i} position={[-1.0 + i * 0.14, 0, 0]} castShadow>
          <boxGeometry args={[0.065, 2.4, 1.2]} />
          <meshStandardMaterial color={i % 2 ? "#b8c2c8" : "#697985"} metalness={0.86} roughness={0.24} />
        </mesh>
      ))}
      {[-1.2, 1.2].map((x) => (
        <mesh key={x} position={[x, 0, 0]}>
          <boxGeometry args={[0.16, 2.65, 1.4]} />
          <meshStandardMaterial color="#26323b" metalness={0.8} roughness={0.3} />
        </mesh>
      ))}
      {[-1.2, 1.2].flatMap(x => [-.55, .55].map(y => <mesh key={`${x}-${y}`} position={[x, y, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[.2, .2, .5, 16]} />
        <meshStandardMaterial color={y > 0 ? "#ff302a" : "#087dff"} metalness={.65} />
      </mesh>))}
      {selected && <EngineeringLabel text={object.id} subtext="Plate heat exchanger" position={[0, 1.8, 0]} accent="#c584f3" />}
    </group>
  );
}

function Pump({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.48, 0.48, 0.75, 28]} />
        <meshStandardMaterial color="#347eaa" metalness={0.72} roughness={0.3} />
      </mesh>
      <mesh position={[0.7, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.32, 0.32, 0.9, 24]} />
        <meshStandardMaterial color="#45525c" metalness={0.85} roughness={0.3} />
      </mesh>
      <mesh position={[0.25, -0.54, 0]}>
        <boxGeometry args={[1.7, 0.14, 1.1]} />
        <meshStandardMaterial color="#232c33" metalness={0.65} />
      </mesh>
      {selected && <EngineeringLabel text={object.id} subtext="Variable-speed circulation pump" position={[0, 1.15, 0]} />}
    </group>
  );
}

function Tank({ object, step, selected, onSelect }: { object: SceneObject; step?: StepRecord; selected: boolean; onSelect: (id: string) => void }) {
  const isBuffer = object.id === "tank_buffer_001";
  return (
    <group position={worldPosition(object.center!)} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      <mesh castShadow>
        <cylinderGeometry args={[isBuffer ? 1.7 : 1.15, isBuffer ? 1.7 : 1.15, isBuffer ? 3.2 : 2.8, 40]} />
        <meshStandardMaterial color={isBuffer ? "#d94034" : "#087dff"} metalness={0.45} roughness={0.24} />
      </mesh>
      {[-1, 1].map(side => <mesh key={`tank-port-${side}`} position={[side * (isBuffer ? 1.7 : 1.15), side < 0 ? .65 : -.75, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[.14, .14, .4, 16]} /><meshStandardMaterial color={isBuffer ? "#ee3228" : "#087dff"} metalness={.6} />
      </mesh>)}
      {[-1, 1].map(y => <mesh key={`dome-${y}`} position={[0, y * (isBuffer ? 1.6 : 1.4), 0]} scale={[1, .28, 1]} castShadow>
        <sphereGeometry args={[isBuffer ? 1.7 : 1.15, 24, 12]} />
        <meshStandardMaterial color={isBuffer ? "#d94034" : "#087dff"} metalness={.55} roughness={.22} />
      </mesh>)}
      {[-1, 1].map(x => <mesh key={`foot-${x}`} position={[x * (isBuffer ? 1.25 : .8), -1.65, 0]}>
        <boxGeometry args={[.22, .6, .9]} /><meshStandardMaterial color="#37444f" metalness={.7} />
      </mesh>)}
      {[-1, 1].map((y) => (
        <mesh key={y} position={[0, y * (isBuffer ? 1.25 : 1.05), 0]}>
          <torusGeometry args={[isBuffer ? 1.72 : 1.17, 0.055, 10, 40]} />
          <meshStandardMaterial color="#b7c5cc" metalness={0.9} />
        </mesh>
      ))}
      <mesh position={[0, 0.25, isBuffer ? 1.71 : 1.16]}>
        <boxGeometry args={[0.85, 0.42, 0.04]} />
        <meshStandardMaterial color="#182229" emissive="#144c68" emissiveIntensity={1.2} />
      </mesh>
      {(selected || object.floor_id === "external") && (
        <EngineeringLabel
          className={`tank-label ${isBuffer ? "buffer-tank-label" : "treatment-tank-label"}`}
          text={isBuffer ? "Thermal Buffer" : "Water Treatment"}
          subtext={isBuffer ? `${step?.buffer_temp_C?.toFixed(1) ?? "—"} °C thermal buffer` : "Filtered sidestream"}
          position={[0, -.15, 2.0]}
          accent="#5bc6e8"
        />
      )}
    </group>
  );
}

function GenericMechanical({ object, selected, onSelect }: { object: SceneObject; selected: boolean; onSelect: (id: string) => void }) {
  const position = worldPosition(object.center!);
  return (
    <group position={position} onClick={(e) => { e.stopPropagation(); onSelect(object.id); }}>
      <mesh castShadow>
        <boxGeometry args={[object.size?.[0] ?? 2, object.size?.[2] ?? 2, object.size?.[1] ?? 1.4]} />
        <meshStandardMaterial color={object.kind === "dry_cooler" ? "#4b5962" : "#9a496c"} metalness={0.7} roughness={0.32} />
      </mesh>
      {object.kind === "dry_cooler" && [-1.5, 0, 1.5].map((x) => (
        <mesh key={x} position={[x, 0.72, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.48, 0.09, 10, 28]} />
          <meshStandardMaterial color="#1b252b" metalness={0.8} />
        </mesh>
      ))}
      {selected && <EngineeringLabel text={object.id} subtext={object.kind.replace(/_/g, " ")} position={[0, 1.65, 0]} accent="#ef7bac" />}
    </group>
  );
}

export default function InteriorEquipment({
  objects,
  visibleFloors,
  step,
  selectedId,
  onSelect,
}: {
  objects: SceneObject[];
  visibleFloors: Record<FloorId, boolean>;
  step?: StepRecord;
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <group name="laboratory-and-mechanical-equipment">
      {objects.map((object) => {
        const floor = object.floor_id as FloorId | undefined;
        if (floor && floor !== ("roof" as FloorId) && visibleFloors[floor] === false) return null;
        const common = { object, selected: selectedId === object.id, onSelect };
        if (object.kind === "robot_arm") return <RobotArm key={object.id} {...common} />;
        if (object.kind === "seed_rack") return <SeedRack key={object.id} {...common} />;
        if (object.kind === "growth_chamber") return <GrowthChamber key={object.id} {...common} />;
        if (object.kind === "heat_exchanger") return <PlateHeatExchanger key={object.id} {...common} />;
        if (object.kind === "pump") return <Pump key={object.id} {...common} />;
        if (object.kind === "tank") return <Tank key={object.id} {...common} step={step} />;
        if (object.kind === "heat_pump" || object.kind === "dry_cooler" || object.kind === "robot_test_cell") {
          return <GenericMechanical key={object.id} {...common} />;
        }
        return null;
      })}
      {/* GF workstations and guarded robot test lanes. */}
      {visibleFloors.gf && [-12, -4, 4, 12].map((x) => (
        <group key={x} position={[x, 0.78, -5.2]}>
          <mesh castShadow>
            <boxGeometry args={[3.2, 0.12, 1.4]} />
            <meshStandardMaterial color="#73818b" metalness={0.65} roughness={0.38} />
          </mesh>
          <mesh position={[0, 0.72, -0.35]} rotation={[-0.14, 0, 0]}>
            <boxGeometry args={[1.15, 0.72, 0.07]} />
            <meshStandardMaterial color="#122536" emissive="#1c72aa" emissiveIntensity={1.4} />
          </mesh>
        </group>
      ))}
      {/* GF low-temperature radiant distribution loop. */}
      {visibleFloors.gf && (
        <mesh position={[0, 0.42, 6.7]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.07, 0.07, 30, 16]} />
          <meshStandardMaterial color="#e3833c" metalness={0.6} roughness={0.3} />
        </mesh>
      )}
    </group>
  );
}
