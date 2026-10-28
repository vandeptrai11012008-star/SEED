import { useEffect, useMemo } from "react";
import * as THREE from "three";

/** Local material detail; no remote texture requests or external assets. */
export function useSurfaceTexture(kind: "concrete" | "soil") {
  const texture = useMemo(() => {
    const size = 256, data = new Uint8Array(size * size * 4);
    let seed = kind === "soil" ? 713 : 113;
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      seed = (1664525 * seed + 1013904223) >>> 0;
      const grit = (seed / 4294967296 - .5) * (kind === "soil" ? 38 : 17);
      const seam = kind === "concrete" && (x % 64 < 1 || y % 64 < 1) ? 24 : 0;
      const base = kind === "soil" ? [91, 67, 43] : [218, 220, 217];
      const i = (y * size + x) * 4;
      data.set([base[0] + grit - seam, base[1] + grit - seam, base[2] + grit - seam, 255], i);
    }
    const tex = new THREE.DataTexture(data, size, size);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(kind === "soil" ? 3 : 4, kind === "soil" ? 2 : 3);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.needsUpdate = true;
    return tex;
  }, [kind]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

export function makeRackFace() {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 768;
  const c = canvas.getContext("2d")!;
  c.fillStyle = "#111a22"; c.fillRect(0, 0, 256, 768);
  for (let row = 0; row < 12; row++) {
    const y = 15 + row * 62;
    const finish = c.createLinearGradient(0, y, 0, y + 52);
    finish.addColorStop(0, "#657381"); finish.addColorStop(.16, "#344554"); finish.addColorStop(1, "#14232e");
    c.fillStyle = finish; c.fillRect(10, y, 236, 52);
    c.strokeStyle = "#86949c"; c.lineWidth = 2; c.strokeRect(14, y + 8, 14, 34); c.strokeRect(228, y + 8, 12, 34);
    for (let fan = 0; fan < 4; fan++) {
      const x = 56 + fan * 45;
      c.fillStyle = "#080f15"; c.beginPath(); c.arc(x, y + 26, 17, 0, Math.PI * 2); c.fill();
      c.strokeStyle = "#4c606b"; c.lineWidth = 2;
      for (let blade = 0; blade < 6; blade++) {
        const a = blade * Math.PI / 3;
        c.beginPath(); c.moveTo(x + Math.cos(a) * 4, y + 26 + Math.sin(a) * 4);
        c.lineTo(x + Math.cos(a + .55) * 14, y + 26 + Math.sin(a + .55) * 14); c.stroke();
      }
      c.fillStyle = "#658491"; c.beginPath(); c.arc(x, y + 26, 3, 0, 7); c.fill();
    }
    c.fillStyle = "#79ecff"; c.fillRect(18, y + 42, 6, 4);
    c.fillStyle = "#63eaa8"; c.fillRect(230, y + 42, 5, 4);
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}
