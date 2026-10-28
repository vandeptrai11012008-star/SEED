import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { SceneObject, StepRecord } from "../api/types";
import { useStore } from "../store";
import { makeRackFace } from "./surfaceTextures";
import type { FloorId } from "../store";
import { worldPosition } from "./coordinates";
import EngineeringLabel from "./Label";

function Rack({
  rack,
  face,
  step,
  selected,
  onSelect,
}: {
  rack: SceneObject;
  face: THREE.Texture;
  step?: StepRecord;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const illustration = useStore(s => s.illustration);
  const position = worldPosition(rack.center!);
  if (illustration) {
    // Spread the same 12 racks across the illustrated floor, not additional equipment.
    const index = Number(rack.id.split("_").slice(-1)[0]) - 1;
    position[0] = -12.8 + (index % 6) * 4.5 + (index >= 6 ? 1.7 : 0);
    position[1] += .2;
  }
  const load = step?.rack_power_W?.[rack.id]
    ? step.rack_power_W[rack.id] / ((rack.nominal_power_kW ?? 1) * 1000)
    : step?.gpu_load_fraction ?? 0;
  const ledColor = new THREE.Color().setHSL(0.58 - load * 0.08, 1, 0.55);

  return (
    <group
      position={position}
      scale={illustration ? [2.2, 1.18, 1] : [1, 1, 1]}
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
      {/* Fan trays, handles and blade separators share one detailed face texture. */}
      <mesh position={[0, 0, .611]}>
        <planeGeometry args={[.7, 2.04]} />
        <meshStandardMaterial map={face} emissiveMap={face} emissive="#ffffff" emissiveIntensity={.25} metalness={.35} roughness={.45} />
      </mesh>
      {[-.345, .345].map(x => <mesh key={`status-rail-${x}`} position={[x, 0, .635]}>
        <boxGeometry args={[.012, 1.98, .018]} />
        <meshStandardMaterial color={ledColor} emissive={ledColor} emissiveIntensity={1.8} toneMapped={false} />
      </mesh>)}
      <mesh position={[0, 1.08, 0]}><boxGeometry args={[.84, .06, 1.24]} /><meshStandardMaterial color="#687986" metalness={.8} roughness={.25} /></mesh>
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
  const face = useMemo(makeRackFace, []);
  useEffect(() => () => face.dispose(), [face]);
  const config = useStore(s => s.config);
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
            face={face}
            step={step}
            selected={selectedId === rack.id}
            onSelect={onSelect}
          />
        ) : null,
      )}
      {config?.geometry.floors.filter((floor: { use: string }) => floor.use === "gpu_data_center").map((floor: { id: FloorId; z: [number, number] }) => visibleFloors[floor.id] && <group key={`service-tray-${floor.id}`} position={[0, floor.z[1] - .8, -1.5]} name={`electrical-cable-tray-${floor.id}`}>
        {[-.55, .55].map(z => <mesh key={z} position={[0, 0, z]}><boxGeometry args={[30, .16, .08]} /><meshStandardMaterial color="#77858c" metalness={.8} roughness={.36} /></mesh>)}
        {Array.from({ length: 20 }, (_, i) => <mesh key={i} position={[-14.7 + i * 1.55, -.04, 0]}><boxGeometry args={[.06, .06, 1.1]} /><meshStandardMaterial color="#83929a" metalness={.8} /></mesh>)}
        {[-10, 0, 10].map(x => <mesh key={x} position={[x, .3, 0]}><boxGeometry args={[.035, .6, .035]} /><meshStandardMaterial color="#7e8d97" metalness={.8} /></mesh>)}
      </group>)}
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
