import { ACESFilmicToneMapping, PCFSoftShadowMap, SRGBColorSpace } from "three";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, GizmoHelper, GizmoViewport, Grid, OrbitControls } from "@react-three/drei";
import { useStore } from "../store";
import Building from "./Building";
import CameraRig from "./CameraRig";

export default function Viewer() {
  const config = useStore((state) => state.config);

  return (
    <Canvas
      shadows="soft"
      camera={{ position: [77, 43, 67], fov: 42, near: 0.08, far: 600 }}
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
      <color attach="background" args={["#a9bbc7"]} />
      <fog attach="fog" args={["#a9bbc7", 115, 230]} />
      <ambientLight intensity={0.62} />
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
      <Building />
      <ContactShadows position={[18, 0.015, 0]} opacity={0.32} scale={105} blur={2.4} far={40} />
      <Grid
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
      />
      <OrbitControls
        makeDefault
        target={[17, 4, 0]}
        enableDamping
        dampingFactor={0.08}
        minDistance={1.2}
        maxDistance={190}
        maxPolarAngle={Math.PI * 0.92}
      />
      {config && <CameraRig config={config} />}
      <GizmoHelper alignment="bottom-right" margin={[68, 96]}>
        <GizmoViewport labelColor="white" axisHeadScale={1.1} />
      </GizmoHelper>
    </Canvas>
  );
}
