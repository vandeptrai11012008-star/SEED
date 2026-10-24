import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { AppConfig } from "../api/types";
import { useStore } from "../store";

type ControlsLike = { target: THREE.Vector3; update: () => void; enabled: boolean };

export default function CameraRig({ config }: { config: AppConfig }) {
  const size = useThree((state) => state.size);
  const camera = useThree((state) => state.camera as THREE.PerspectiveCamera);
  const controls = useThree((state) => state.controls as unknown as ControlsLike | undefined);
  const preset = useStore((state) => state.cameraPreset);
  const requestId = useStore((state) => state.cameraRequestId);
  const inspectedFloor = useStore((state) => state.inspectedFloor);
  const transitioning = useRef(true);
  const keys = useRef(new Set<string>());

  const destination = useMemo(() => {
    const geometry = config.geometry;
    const building = geometry.main_building;
    const greenhouse = geometry.greenhouse;
    const siteMinX = building.footprint.x[0] as number;
    const siteMaxX = greenhouse.footprint.x[1] as number;
    const target = new THREE.Vector3((siteMinX + siteMaxX) / 2, 4.2, 0);
    const fullWidth = siteMaxX - siteMinX;
    const verticalSpan = 26.5;
    const maxDimension = Math.max(fullWidth, building.depth_y, verticalSpan);
    const fovRadians = THREE.MathUtils.degToRad(camera.fov);
    const fitDistance = (maxDimension / (2 * Math.tan(fovRadians / 2))) * 1.18;
    const isoDirection = new THREE.Vector3(1, 0.58, 0.92).normalize();

    if (preset === "auto_fit") {
      return { position: target.clone().add(isoDirection.multiplyScalar(fitDistance)), target };
    }
    if (preset === "isometric") {
      return { position: new THREE.Vector3(77, 43, 67), target: new THREE.Vector3(17, 4, 0) };
    }
    if (preset === "front_cutaway") {
      const aspect = size.width / Math.max(size.height, 1);
      const distance = Math.max(38 / (2 * Math.tan(fovRadians / 2)), 92 / (2 * Math.tan(fovRadians / 2) * aspect));
      return { position: new THREE.Vector3(19, 8, distance), target: new THREE.Vector3(19, 5, 0) };
    }
    if (preset === "walkthrough") {
      return { position: new THREE.Vector3(15, 1.7, -7.5), target: new THREE.Vector3(0, 1.5, 3) };
    }
    if (preset === "greenhouse") {
      return { position: new THREE.Vector3(68, 14, 28), target: new THREE.Vector3(41, 2.2, 0) };
    }
    if (preset === "underground") {
      return { position: new THREE.Vector3(25, -4.6, 31), target: new THREE.Vector3(0, -6.15, 0) };
    }
    const floor = (geometry.floors as Array<{ id: string; z: [number, number] }>).find(
      (candidate) => candidate.id === inspectedFloor,
    );
    const elevation = floor ? (floor.z[0] + floor.z[1]) / 2 : 6.75;
    return { position: new THREE.Vector3(34, elevation + 3.8, 34), target: new THREE.Vector3(0, elevation, 0) };
  }, [camera.fov, config, inspectedFloor, preset, requestId, size.width, size.height]);

  useEffect(() => {
    transitioning.current = true;
  }, [destination]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => keys.current.add(event.key.toLowerCase());
    const up = (event: KeyboardEvent) => keys.current.delete(event.key.toLowerCase());
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  useFrame((_, delta) => {
    if (!controls) return;
    if (transitioning.current) {
      const alpha = 1 - Math.exp(-delta * 3.6);
      camera.position.lerp(destination.position, alpha);
      controls.target.lerp(destination.target, alpha);
      camera.lookAt(controls.target);
      controls.update();
      if (
        camera.position.distanceTo(destination.position) < 0.08
        && controls.target.distanceTo(destination.target) < 0.05
      ) {
        transitioning.current = false;
      }
      return;
    }

    if (preset !== "walkthrough") return;
    const direction = new THREE.Vector3();
    camera.getWorldDirection(direction);
    direction.y = 0;
    direction.normalize();
    const right = new THREE.Vector3().crossVectors(direction, camera.up).normalize();
    const movement = new THREE.Vector3();
    if (keys.current.has("w")) movement.add(direction);
    if (keys.current.has("s")) movement.sub(direction);
    if (keys.current.has("d")) movement.add(right);
    if (keys.current.has("a")) movement.sub(right);
    if (keys.current.has("q")) movement.y -= 1;
    if (keys.current.has("e")) movement.y += 1;
    if (movement.lengthSq() > 0) {
      movement.normalize().multiplyScalar(delta * 4.2);
      camera.position.add(movement);
      controls.target.add(movement);
      controls.update();
    }
  });

  return null;
}
