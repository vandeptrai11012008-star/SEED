import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { SceneObject, ScenePipe, StepRecord } from "../api/types";
import type { PipeOverlay } from "../store";
import { pipePath } from "./pipePath";
import { tempColor } from "./colors";
import { worldPosition, worldVector } from "./coordinates";
import EngineeringLabel from "./Label";

function conventionColor(pipe: ScenePipe): string {
  const role = pipe.role ?? "";
  if (pipe.circuit === "primary") {
    return role === "return" || role === "rejection" || role === "rack_heat_pickup" ? "#ff302a" : "#087dff";
  }
  return role === "return" || role === "sidestream" ? "#087dff" : "#ff302a";
}

function FlowParticle({
  curve,
  phase,
  speed,
}: {
  curve: THREE.Curve<THREE.Vector3>;
  phase: number;
  speed: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = (clock.elapsedTime * speed + phase) % 1;
    ref.current.position.copy(curve.getPointAt(t));
    ref.current.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), curve.getTangentAt(t).normalize());
  });
  return (
    <mesh ref={ref}>
      <coneGeometry args={[0.16, 0.5, 8]} />
      <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={1.8} toneMapped={false} />
    </mesh>
  );
}

function FlowPipe({
  pipe,
  step,
  overlay,
  selected,
  onSelect,
}: {
  pipe: ScenePipe;
  step?: StepRecord;
  overlay: PipeOverlay;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const curve = useMemo(() => {
    const points = (pipe.points ?? []).map((point) => worldVector(point));
    if (points.length < 2) points.push(new THREE.Vector3());
    return pipePath(points);
  }, [pipe.points]);
  const geometry = useMemo(
    () => new THREE.TubeGeometry(curve, Math.max(24, (pipe.points?.length ?? 2) * 18), Math.max(0.12, (pipe.diameter_m ?? 0.08) / 2), 10, false),
    [curve, pipe.diameter_m, pipe.points?.length],
  );
  useEffect(() => () => geometry.dispose(), [geometry]);
  const state = step?.pipe_states?.[pipe.id];
  const flow = state?.mass_flow_kg_s ?? 0;
  const temperature = state?.temperature_C;
  const baseColor = conventionColor(pipe);
  const color = overlay === "temperature" && temperature !== undefined
    ? `#${tempColor(temperature, 25, 60).getHexString()}`
    : baseColor;
  const visibleFlow = overlay !== "off" && flow > 0.001;
  const speed = 0.025 + Math.min(0.16, flow / 90);
  const midpoint = curve.getPointAt(0.5);
  const arrowCount = Math.min(18, Math.max(2, Math.ceil(curve.getLength() / 5)));

  return (
    <group name={pipe.id}>
      <mesh
        geometry={geometry}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(pipe.id);
        }}
        castShadow
      >
        <meshStandardMaterial
          color={overlay === "off" ? "#53606a" : selected ? "#ffffff" : color}
          metalness={0.68}
          roughness={0.3}
          emissive={color}
          emissiveIntensity={selected ? 0.8 : 0.28}
          transparent={pipe.buried}
          opacity={pipe.buried ? 0.9 : 1}
        />
      </mesh>
      {visibleFlow && Array.from({ length: arrowCount }, (_, i) => i / arrowCount).map((phase) => (
        <FlowParticle key={phase} curve={curve} phase={phase} speed={speed} />
      ))}
      {selected && (
        <EngineeringLabel
          text={pipe.id}
          subtext={`${temperature?.toFixed(1) ?? "—"} °C · ${flow.toFixed(2)} kg/s · ${pipe.from} → ${pipe.to}`}
          position={[midpoint.x, midpoint.y + 0.7, midpoint.z]}
          accent={color}
        />
      )}
    </group>
  );
}

function Valve({ object, selectedId, onSelect }: { object: SceneObject; selectedId?: string; onSelect: (id: string) => void }) {
  const selected = selectedId === object.id;
  return (
    <group position={worldPosition(object.center!)} onClick={(event) => { event.stopPropagation(); onSelect(object.id); }}>
      <mesh>
        <sphereGeometry args={[0.28, 18, 12]} />
        <meshStandardMaterial color={selected ? "#ffffff" : "#c99035"} metalness={0.82} roughness={0.25} />
      </mesh>
      <mesh position={[0, 0.35, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.25, 0.04, 10, 24]} />
        <meshStandardMaterial color="#d9a345" metalness={0.8} />
      </mesh>
      {selected && <EngineeringLabel text={object.id} subtext="Controllable mixing / isolation valve" position={[0, 0.9, 0]} accent="#e2a842" />}
    </group>
  );
}

function Sensor({ object, step, selectedId, onSelect }: { object: SceneObject; step?: StepRecord; selectedId?: string; onSelect: (id: string) => void }) {
  const selected = selectedId === object.id;
  const state = step?.sensor_states?.[object.id];
  return (
    <group position={worldPosition(object.center!)} onClick={(event) => { event.stopPropagation(); onSelect(object.id); }}>
      <mesh>
        <cylinderGeometry args={[0.08, 0.11, 0.42, 12]} />
        <meshStandardMaterial color="#b8c7cf" metalness={0.8} roughness={0.24} />
      </mesh>
      <mesh position={[0, 0.22, 0]}>
        <sphereGeometry args={[0.11, 12, 8]} />
        <meshStandardMaterial color="#55d9e9" emissive="#22a8c1" emissiveIntensity={2} />
      </mesh>
      {selected && <EngineeringLabel text={object.id} subtext={`${state?.value !== undefined ? Number(state.value).toFixed(1) : "—"} ${state?.unit ?? ""}`} position={[0, 0.8, 0]} accent="#55d9e9" />}
    </group>
  );
}

export default function Hydronics({
  pipes,
  objects,
  step,
  overlay,
  selectedId,
  onSelect,
}: {
  pipes: ScenePipe[];
  objects: SceneObject[];
  step?: StepRecord;
  overlay: PipeOverlay;
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  // Hooks live inside each always-mounted FlowPipe; toggling overlay only changes
  // materials/particles and never changes this component's hook order.
  return (
    <group name="connected-hydronic-networks">
      {pipes.map((pipe) => (
        <FlowPipe
          key={pipe.id}
          pipe={pipe}
          step={step}
          overlay={overlay}
          selected={selectedId === pipe.id}
          onSelect={onSelect}
        />
      ))}
      {objects.filter((object) => object.kind === "valve").map((object) => (
        <Valve key={object.id} object={object} selectedId={selectedId} onSelect={onSelect} />
      ))}
      {objects.filter((object) => object.kind === "sensor").map((object) => (
        <Sensor key={object.id} object={object} step={step} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </group>
  );
}
