import { create } from "zustand";
import type {
  AppConfig,
  Scene,
  SimulationRequest,
  SimulationResult,
  StepRecord,
} from "./api/types";
import { api } from "./api/client";

export type FloorId = "b2" | "b1" | "gf" | "f1" | "f2" | "f3";
export type PipeOverlay = "off" | "temperature" | "flow";
export type CameraPreset =
  | "auto_fit"
  | "isometric"
  | "front_cutaway"
  | "walkthrough"
  | "floor"
  | "greenhouse"
  | "underground";

interface AppState {
  config?: AppConfig;
  scene?: Scene;
  result?: SimulationResult;
  loading: boolean;
  error?: string;

  illustration: boolean;
  setIllustration: (value: boolean) => void;
  cutaway: boolean;
  visibleFloors: Record<FloorId, boolean>;
  pipeOverlay: PipeOverlay;
  showGreenhouseSoil: boolean;
  selectedId?: string;
  cameraPreset: CameraPreset;
  cameraRequestId: number;
  inspectedFloor: FloorId;

  stepIndex: number;
  playing: boolean;
  request: SimulationRequest;

  // Guided presentation (slide-by-slide scene tour).
  presenting: boolean;
  slideIndex: number;
  autoAdvance: boolean;

  init: () => Promise<void>;
  runSimulation: (over?: Partial<SimulationRequest>) => Promise<void>;
  setCutaway: (value: boolean) => void;
  toggleFloor: (floor: FloorId) => void;
  setPipeOverlay: (overlay: PipeOverlay) => void;
  toggleGreenhouseSoil: () => void;
  select: (id?: string) => void;
  setCameraPreset: (preset: CameraPreset, floor?: FloorId) => void;
  setStep: (index: number) => void;
  setPlaying: (playing: boolean) => void;
  patchRequest: (patch: Partial<SimulationRequest>) => void;
  currentStep: () => StepRecord | undefined;

  startPresentation: () => void;
  stopPresentation: () => void;
  goToSlide: (index: number) => void;
  nextSlide: () => void;
  prevSlide: () => void;
  setAutoAdvance: (value: boolean) => void;
}

// A presentation slide drives the camera and view settings. Camera transitions
// are already smooth (CameraRig lerps to each preset's destination), so stepping
// through slides produces cinematic fly-throughs between areas.
export interface Slide {
  id: string;
  title: string;
  subtitle?: string;
  description: string;
  points?: string[];
  camera: CameraPreset;
  floor?: FloorId;
  overlay?: PipeOverlay;
  cutaway?: boolean;
}

// Narrated tour. Captions are English and follow the ThermalLoop facility brief:
// each stop introduces one area with its purpose and its role in the thermal loop.
export const SLIDES: Slide[] = [
  {
    id: "overview",
    title: "ThermalLoop AI Center",
    subtitle: "Integrated AI computing & waste-heat recovery",
    description:
      "A research facility that turns AI computing waste heat into useful energy for science and sustainable agriculture. A full 1:1 model of six levels plus an external greenhouse.",
    points: [
      "Recovers usable waste heat from GPU servers",
      "Redistributes it to labs, seed research and a greenhouse",
      "Two hydraulically isolated water circuits linked by a heat exchanger",
    ],
    camera: "auto_fit",
    overlay: "temperature",
    cutaway: true,
  },
  {
    id: "gpu",
    title: "AI Data Center — 3F / 2F / 1F",
    subtitle: "GPU servers · 1.5 MW total IT power",
    description:
      "Three floors dedicated to AI computing: GPU server racks, electrical distribution and liquid cooling. 500 kW nominal IT power per floor.",
    points: [
      "Runs AI model training, inference and compute workloads",
      "Cold water circulates up; servers heat it; hot water returns to B2",
      "At full load ~80% of 1.5 MW (~1.2 MW) is captured in the liquid loop",
    ],
    camera: "floor",
    floor: "f2",
    overlay: "temperature",
    cutaway: true,
  },
  {
    id: "robot",
    title: "Robotics & Smart Materials Lab — GF",
    subtitle: "Robotics · soft actuators · thermo-responsive materials",
    description:
      "The ground-floor laboratory develops robotic systems, embedded control and temperature-responsive materials.",
    points: [
      "Builds and tests robots, sensors and embedded control",
      "Studies soft actuators and thermally responsive polymers",
      "Recovered GPU heat supplies lab space heating (≈120 kW design)",
    ],
    camera: "floor",
    floor: "gf",
    overlay: "flow",
    cutaway: true,
  },
  {
    id: "seed",
    title: "Seed Storage & Testing — B1",
    subtitle: "Preservation · germination · controlled environment",
    description:
      "The first basement preserves seeds and runs germination and early plant-growth experiments under controlled conditions.",
    points: [
      "Monitors temperature, humidity and experimental conditions",
      "Recovered heat supports germination and plant testing zones",
      "Cold preservation stays independently temperature-controlled",
    ],
    camera: "floor",
    floor: "b1",
    overlay: "temperature",
    cutaway: true,
  },
  {
    id: "plant",
    title: "Heat Exchanger & Mechanical Plant — B2",
    subtitle: "Where the two circuits meet",
    description:
      "The second basement houses the thermal recovery equipment that transfers heat from the GPU cooling loop into the heating network.",
    points: [
      "Plate heat exchanger, primary & secondary circulation pumps",
      "Control valves, manifolds, temperature & pressure sensors",
      "Heat pump and dry cooler balance delivery and heat rejection",
    ],
    camera: "underground",
    overlay: "flow",
    cutaway: true,
  },
  {
    id: "storage",
    title: "Thermal Buffer & Water Treatment",
    subtitle: "Storage · balancing · water quality",
    description:
      "A buffer tank stores recovered energy to balance the gap between GPU heat production and heating demand, while a sidestream system keeps the closed-loop water quality in check.",
    points: [
      "50 m³ buffer tank charges and discharges on demand",
      "Smooths fluctuations between heat supply and heat use",
      "Closed-loop water verification protects the pipe network",
    ],
    camera: "underground",
    overlay: "temperature",
    cutaway: true,
  },
  {
    id: "greenhouse",
    title: "Research Greenhouse",
    subtitle: "30 × 18 × 5 m · controlled-environment agriculture",
    description:
      "An external greenhouse studies sustainable agriculture using recovered data-center heat delivered through buried insulated piping.",
    points: [
      "Heated water warms soil and root zones (≈300 kW design)",
      "Insulated underground supply/return link it to the B2 plant",
      "Cooler return water flows back for reheating",
    ],
    camera: "greenhouse",
    overlay: "temperature",
    cutaway: false,
  },
  {
    id: "walkthrough",
    title: "Explore It Yourself",
    subtitle: "First-person walkthrough",
    description:
      "Step inside the facility and move freely. Turning AI computing waste heat into useful energy for science, innovation and sustainable agriculture.",
    points: ["W / A / S / D to move", "Q / E for height", "Drag to look around"],
    camera: "walkthrough",
    overlay: "temperature",
    cutaway: true,
  },
];

const floorIds: FloorId[] = ["b2", "b1", "gf", "f1", "f2", "f3"];

export const useStore = create<AppState>((set, get) => ({
  illustration: true,
  setIllustration: (illustration) => {
    set({ illustration });
    if (illustration) {
      set({ presenting: false, autoAdvance: false, pipeOverlay: "flow" });
      get().setCameraPreset("front_cutaway");
    }
  },
  loading: false,
  cutaway: true,
  visibleFloors: Object.fromEntries(floorIds.map((floor) => [floor, true])) as Record<FloorId, boolean>,
  pipeOverlay: "flow",
  showGreenhouseSoil: true,
  cameraPreset: "front_cutaway",
  cameraRequestId: 0,
  inspectedFloor: "f1",
  stepIndex: 0,
  playing: false,
  presenting: false,
  slideIndex: 0,
  autoAdvance: false,
  request: {
    mode: "simplified_physics",
    scenario_id: "baseline",
    duration_s: 86400,
    timestep_s: 600,
  },

  init: async () => {
    set({ loading: true, error: undefined });
    try {
      const [config, scene] = await Promise.all([api.config(), api.scene()]);
      set({ config, scene });
      await get().runSimulation();
    } catch (error: any) {
      set({ error: String(error?.message ?? error) });
    } finally {
      set({ loading: false });
    }
  },

  runSimulation: async (override) => {
    set({ loading: true, error: undefined });
    try {
      const request = { ...get().request, ...(override ?? {}) };
      const result = await api.simulate(request);
      set({ result, request, stepIndex: 0 });
    } catch (error: any) {
      set({ error: String(error?.message ?? error) });
    } finally {
      set({ loading: false });
    }
  },

  setCutaway: (cutaway) => set({ cutaway }),
  toggleFloor: (floor) => set((state) => ({
    visibleFloors: { ...state.visibleFloors, [floor]: !state.visibleFloors[floor] },
  })),
  setPipeOverlay: (pipeOverlay) => set({ pipeOverlay }),
  toggleGreenhouseSoil: () => set((state) => ({ showGreenhouseSoil: !state.showGreenhouseSoil })),
  select: (selectedId) => set({ selectedId }),
  setCameraPreset: (cameraPreset, inspectedFloor) => set((state) => ({
    cameraPreset,
    inspectedFloor: inspectedFloor ?? state.inspectedFloor,
    cameraRequestId: state.cameraRequestId + 1,
    cutaway: cameraPreset === "front_cutaway" || cameraPreset === "floor" || cameraPreset === "underground"
      ? true
      : state.cutaway,
  })),
  setStep: (stepIndex) => set({ stepIndex }),
  setPlaying: (playing) => set({ playing }),
  patchRequest: (patch) => set((state) => ({ request: { ...state.request, ...patch } })),

  currentStep: () => {
    const { result, stepIndex } = get();
    return result?.series?.[stepIndex];
  },

  startPresentation: () => {
    set({ presenting: true, slideIndex: 0 });
    applySlide(set, get, 0);
  },
  stopPresentation: () => set({ presenting: false, autoAdvance: false }),
  goToSlide: (index) => {
    const clamped = Math.max(0, Math.min(SLIDES.length - 1, index));
    set({ slideIndex: clamped, presenting: true });
    applySlide(set, get, clamped);
  },
  nextSlide: () => get().goToSlide(get().slideIndex + 1),
  prevSlide: () => get().goToSlide(get().slideIndex - 1),
  setAutoAdvance: (autoAdvance) => set({ autoAdvance }),
}));

// Applies a slide's camera + view settings. Reuses setCameraPreset so the
// existing smooth lerp transition runs for each scene change.
function applySlide(
  set: (partial: Partial<AppState>) => void,
  get: () => AppState,
  index: number,
) {
  const slide = SLIDES[index];
  if (!slide) return;
  if (slide.overlay) set({ pipeOverlay: slide.overlay });
  if (typeof slide.cutaway === "boolean") set({ cutaway: slide.cutaway });
  get().setCameraPreset(slide.camera, slide.floor);
}
