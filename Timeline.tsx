import { useEffect } from "react";
import { useStore } from "../store";

export default function Timeline() {
  const result = useStore((s) => s.result);
  const stepIndex = useStore((s) => s.stepIndex);
  const setStep = useStore((s) => s.setStep);
  const playing = useStore((s) => s.playing);
  const setPlaying = useStore((s) => s.setPlaying);
  const step = useStore((s) => s.currentStep());

  const n = result?.series?.length ?? 0;

  useEffect(() => {
    if (!playing || n === 0) return;
    const id = setInterval(() => {
      const cur = useStore.getState().stepIndex;
      useStore.getState().setStep((cur + 1) % n);
    }, 120);
    return () => clearInterval(id);
  }, [playing, n]);

  if (n === 0) return null;
  const hour = step?.hour ?? 0;

  return (
    <div className="overlay-controls">
      <button onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play"}</button>
      <input
        type="range"
        min={0}
        max={n - 1}
        value={stepIndex}
        onChange={(e) => setStep(Number(e.target.value))}
      />
      <span style={{ width: 90, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        t = {hour.toFixed(1)} h
      </span>
    </div>
  );
}
