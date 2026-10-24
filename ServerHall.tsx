import { useMemo } from "react";
import * as THREE from "three";
import type { SceneObject, StepRecord } from "../api/types";
import type { FloorId } from "../store";
import { worldPosition } from "./coordinates";
import EngineeringLabel from "./Label";

function Rack({
  rack,
  step,
  selected,
  onSelect,
}: {
  rack: SceneObject;
  step?: StepRecord;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const position = worldPosition(rack.center!);
  const load = step?.rack_power_W?.[rack.id]
    ? step.rack_power_W[rack.id] / ((rack.nominal_power_kW ?? 1) * 1000)
    : step?.gpu_load_fraction ?? 0;
  const ledColor = new THREE.Color().setHSL(0.58 - load * 0.08, 1, 0.55);

  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(rack.id);
      }}
    >
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.8, 2.2, 1.2]} />
        <meshStandardMaterial
          color={selected ? "#9ed8ff" : "#18222d"}
          metalness={0.82}
          roughness={0.3}
          emissive={selected ? "#1463a5" : "#02070b"}
          emissiveIntensity={selected ? 0.55 : 0.2}
        />
      </mesh>
      {/* rack rails and top cap */}
      {[-0.36, 0.36].map((x) =>
        [-0.56, 0.56].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 0, z]}>
            <boxGeometry args={[0.045, 2.1, 0.045]} />
            <meshStandardMaterial color="#8b9aa6" metalness={0.95} roughness={0.2} />
          </mesh>
        )),
      )}
      {/* visible GPU server blades */}
      {Array.from({ length: 9 }, (_, i) => (
        <group key={i} position={[0, -0.86 + i * 0.205, 0.611]}>
          <mesh>
            <boxGeometry args={[0.69, 0.155, 0.035]} />
            <meshStandardMaterial color="#243746" metalness={0.72} roughness={0.36} />
          </mesh>
          <mesh position={[-0.26, 0, 0.025]}>
            <boxGeometry args={[0.065, 0.035, 0.025]} />
            <meshStandardMaterial color={ledColor} emissive={ledColor} emissiveIntensity={4.5} toneMapped={false} />
          </mesh>
          <mesh position={[-0.16, 0, 0.025]}>
            <boxGeometry args={[0.04, 0.035, 0.025]} />
            <meshStandardMaterial color="#4de2a8" emissive="#4de2a8" emissiveIntensity={3} toneMapped={false} />
          </mesh>
        </group>
      ))}
      {/* rear direct-to-chip manifold */}
      <mesh position={[0.31, 0, -0.64]}>
        <cylinderGeometry args={[0.035, 0.035, 1.85, 12]} />
        <meshStandardMaterial color="#258ee8" metalness={0.55} roughness={0.25} />
      </mesh>
      <mesh position={[-0.31, 0, -0.64]}>
        <cylinderGeometry args={[0.035, 0.035, 1.85, 12]} />
        <meshStandardMaterial color="#e64d44" metalness={0.55} roughness={0.25} />
      </mesh>
      {selected && (
        <EngineeringLabel
          text={rack.id}
          subtext={`${((rack.nominal_power_kW ?? 0) * load).toFixed(1)} kW · ${(load * 100).toFixed(0)}%`}
          position={[0, 1.65, 0]}
        />
      )}
    </group>
  );
}

export default function ServerHalls({
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
  const racks = useMemo(
    () => objects.filter((object) => object.kind === "gpu_rack"),
    [objects],
  );
  const pdus = objects.filter((object) => object.kind === "power_distribution");
  const manifolds = objects.filter((object) => object.kind === "manifold");

  return (
    <group name="gpu-server-halls">
      {racks.map((rack) =>
        visibleFloors[rack.floor_id as FloorId] ? (
          <Rack
            key={rack.id}
            rack={rack}
            step={step}
            selected={selectedId === rack.id}
            onSelect={onSelect}
          />
        ) : null,
      )}
      {pdus.map((pdu) =>
        visibleFloors[pdu.floor_id as FloorId] ? (
          <group key={pdu.id} position={worldPosition(pdu.center!)} onClick={() => onSelect(pdu.id)}>
            <mesh castShadow>
              <boxGeometry args={[1.8, 2.4, 1]} />
              <meshStandardMaterial color="#303941" metalness={0.78} roughness={0.32} />
            </mesh>
            {Array.from({ length: 5 }, (_, i) => (
              <mesh key={i} position={[0, -0.72 + i * 0.36, 0.51]}>
                <boxGeometry args={[1.45, 0.16, 0.035]} />
                <meshStandardMaterial color="#43505a" metalness={0.6} />
              </mesh>
            ))}
            <mesh position={[0.62, 0.88, 0.53]}>
              <boxGeometry args={[0.22, 0.12, 0.025]} />
              <meshStandardMaterial color="#52e39e" emissive="#52e39e" emissiveIntensity={3} />
            </mesh>
          </group>
        ) : null,
      )}
      {manifolds.map((manifold) =>
        visibleFloors[manifold.floor_id as FloorId] ? (
          <group key={manifold.id} position={worldPosition(manifold.center!)}>
            <mesh rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.13, 0.13, 2.8, 18]} />
              <meshStandardMaterial color={manifold.role === "return" ? "#d84e45" : "#2c91e8"} metalness={0.68} roughness={0.25} />
            </mesh>
            {[-1, -0.5, 0, 0.5, 1].map((x) => (
              <mesh key={x} position={[x, -0.24, 0]}>
                <cylinderGeometry args={[0.035, 0.035, 0.45, 10]} />
                <meshStandardMaterial color={manifold.role === "return" ? "#d84e45" : "#2c91e8"} metalness={0.6} />
              </mesh>
            ))}
          </group>
        ) : null,
      )}
    </group>
  );
}
