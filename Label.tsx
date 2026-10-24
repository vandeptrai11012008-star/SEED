import { Html } from "@react-three/drei";

export default function EngineeringLabel({
  text,
  subtext,
  position = [0, 0, 0],
  accent = "#62b6ff",
}: {
  text: string;
  subtext?: string;
  position?: [number, number, number];
  accent?: string;
}) {
  return (
    <Html position={position} center distanceFactor={32} zIndexRange={[20, 0]}>
      <div className="engineering-label" style={{ borderColor: accent }}>
        <strong>{text}</strong>
        {subtext && <span>{subtext}</span>}
      </div>
    </Html>
  );
}
