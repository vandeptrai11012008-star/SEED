import { useEffect } from "react";
import { ACESFilmicToneMapping, PCFSoftShadowMap, SRGBColorSpace } from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, GizmoHelper, GizmoViewport, Grid, OrbitControls } from "@react-three/drei";
import { useStore } from "../store";
import Building from "./Building";
import CameraRig from "./CameraRig";

// Only equipment/view changes affect shadows; flowing arrows do not cast them.
function StaticShadows() {
  const gl = useThree(s => s.gl);
  const config = useStore(s => s.config);
  const cutaway = useStore(s => s.cutaway);
  const floors = useStore(s => s.visibleFloors);
  const illustration = useStore(s => s.illustration);
  useEffect(() => {
    gl.shadowMap.autoUpdate = false;
    gl.shadowMap.needsUpdate = true;
  }, [gl, config, cutaway, floors, illustration]);
  return null;
}

export default function Viewer() {
  const illustration = useStore((state) => state.illustration);
  const config = useStore((state) => state.config);

  return (
    <Canvas
      shadows="soft"
      camera={{ position: [19, 8, 112], fov: 42, near: 0.08, far: 600 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.outputColorSpace = SRGBColorSpace;
        gl.toneMapping = ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.12;
        gl.shadowMap.enabled = true;
        gl.shadowMap.type = PCFSoftShadowMap;
      }}
    >
      <color attach="background" args={["#82c5ef"]} />
      {!illustration && <fog attach="fog" args={["#82c5ef", 115, 230]} />}
      <ambientLight intensity={0.9} />
      <hemisphereLight intensity={1.0} color="#e6f3ff" groundColor="#4f5145" />
      <directionalLight
        position={[48, 70, 36]}
        intensity={2.25}
        color="#fff2dc"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-75}
        shadow-camera-right={75}
        shadow-camera-top={65}
        shadow-camera-bottom={-45}
        shadow-camera-near={1}
        shadow-camera-far={180}
        shadow-bias={-0.00008}
      />
      <Environment resolution={128} frames={1}>
        <Lightformer form="rect" intensity={2.5} position={[0, 15, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[35, 35, 1]} />
        <Lightformer form="rect" intensity={2} position={[-20, 5, 15]} rotation={[0, Math.PI / 3, 0]} scale={[20, 20, 1]} color="#d5edff" />
        <Lightformer form="rect" intensity={1.3} position={[20, 5, -15]} rotation={[0, -Math.PI / 3, 0]} scale={[15, 20, 1]} color="#ffe7bf" />
      </Environment>
      <StaticShadows />
      <Building />
      {!illustration && <ContactShadows position={[18, 0.015, 0]} opacity={0.32} scale={105} blur={2.4} far={40} />}
      {!illustration && <Grid
        args={[120, 70]}
        position={[19, 0.025, 0]}
        cellSize={1}
        cellThickness={0.3}
        cellColor="#667b72"
        sectionSize={5}
        sectionThickness={0.65}
        sectionColor="#49645a"
        fadeDistance={115}
        fadeStrength={1.2}
      />}
      <OrbitControls
        makeDefault
        target={[17, 4, 0]}
        enableDamping
        dampingFactor={0.08}
        minDistance={1.2}
        maxDistance={450}
        maxPolarAngle={Math.PI * 0.92}
      />
      {config && <CameraRig config={config} />}
      {!illustration && <GizmoHelper alignment="bottom-right" margin={[68, 96]}>
        <GizmoViewport labelColor="white" axisHeadScale={1.1} />
      </GizmoHelper>}
    </Canvas>
  );
}
