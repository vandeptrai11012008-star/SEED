# ThermalLoop AI Center — Physics-Based Digital Twin

An interactive, research-oriented, full-scale (1:1, 1 world unit = 1 meter)
digital twin of an AI data center that recovers server waste heat and
distributes it to laboratory spaces, a seed research facility, and a greenhouse.

This is a **working simulation application**, not only a 3D animation. A
deterministic reduced-order physics backend computes temperatures, flows, powers, and
energy balances; the React/Three.js frontend visualizes the detailed facility,
hydronic circuits, and simulation results.

> **Results disclaimer.** The built-in backend is a *simplified engineering
> model with numerical balance checks*, not a calibrated plant model. Every result is labeled `simplified_physics` and
> `is_measured_data: false`. OpenModelica and EnergyPlus are integrated as
> **adapters that generate solver inputs**; they are only labeled as having run
> after you execute those tools locally. Nothing here fakes measured data or
> random values presented as predictions.

## Architecture at a glance

```
thermal-loop/
  frontend/      React + TypeScript + Three.js / React Three Fiber viewer + dashboards
  backend/       Python + FastAPI simplified-physics engine (exchangeable backend)
  blender/       Blender Python API script -> full-facility GLB export
  modelica/      OpenModelica (.mo) model generator + run script
  energyplus/    EnergyPlus IDF generator
  optimization/  Python GPU-scheduling / heat-recovery optimizer
  config/        Shared JSON data contract (single source of truth)
  data/          Generated artifacts (GLB, etc.)
  results/       Saved simulation runs (run_*.json)
  tests/         pytest unit + API + conservation tests
  docs/          Architecture, requirements, API docs
```

Two hydraulically isolated closed circuits, coupled only through the B2 heat
exchanger:

- **Primary (IT liquid cooling):** blue supply manifold to GPU floors, red hot
  risers down to `hx_b2_primary_001`, cooled water back to the GPU supply, with
  pumps, isolation/modulating valves, and auxiliary heat rejection.
- **Secondary (heat recovery):** recovers energy at the HX, charges the thermal
  buffer tank `tank_buffer_001`, and feeds parallel controllable branches to the
  robot lab, B1 seed zones, and (through buried insulated pipe in the utility
  corridor) the greenhouse soil-heating loop. A heat pump optionally upgrades
  temperature; the capacity-limited dry cooler rejects surplus primary heat.
  Water treatment is a closed-loop sidestream (`tank_verify_001`), not an open
  tank interrupting the loop.

## Interactive 3D facility

The default auto-fit view frames the complete 74 m-wide site. The procedural
R3F model includes structural slabs/columns/beams, a transparent curtain wall,
all six cutaway floors, detailed GPU racks and cooling manifolds, robot cells,
seed racks and growth chambers, B2 plate HX/pumps/valves/two tanks, an arched
glass greenhouse with plants and soil beds, and the underground utility tunnel.
All 33 rendered pipe segments come from `config/network.json`; animated particles
follow their real `from -> to` paths and read temperature/mass flow by stable ID.

Camera controls include auto-fit, isometric, front cutaway, WASD walkthrough,
per-floor focus, greenhouse, and B2/underground inspection. Views can also be
deep-linked, for example `/?view=greenhouse`, `/?view=underground`,
`/?view=floor&floor=f2`, or `/?soil=hidden` to reveal the greenhouse soil-heating
pipes.

Live simulation controls (GPU base/peak load, outdoor mean temperature, heat-pump
booster, auxiliary rejection) map to the existing `/api/simulate` request fields;
adjust and re-run to recompute the physics and update equipment state.

### Fully procedural — no Blender, no GLB

The entire 3D environment is generated at runtime with Three.js / React Three
Fiber geometry. There is no dependency on Blender, `.blend` files, or
pre-generated GLB assets in the application run path. The optional
`blender/` scripts remain in the repo for offline authoring only and are not
required to build, run, or view the digital twin.

## Requirements

- **Windows 11** (instructions below; works on macOS/Linux too)
- **Python 3.10+** (tested on 3.15)
- **Node.js 18+** (tested on 24)
- Optional, for high-fidelity modes: Blender, OpenModelica, EnergyPlus

## Quick start (Windows 11)

Open two terminals.

**Terminal 1 — backend**
```powershell
cd thermal-loop
./scripts/setup.ps1      # creates venv-free install of backend deps + checks
./scripts/run_backend.ps1
# -> http://127.0.0.1:8000  (OpenAPI docs at /docs)
```

**Terminal 2 — frontend**
```powershell
cd thermal-loop/frontend
& "C:\Program Files\nodejs\npm.cmd" install
& "C:\Program Files\nodejs\npm.cmd" run dev
# -> http://localhost:5173  (proxies /api to the backend)
```

> **PowerShell execution policy note.** If `npm`/`npx` fail with
> "running scripts is disabled", either call the `.cmd` directly as shown above,
> or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Backend-only without scripts
```powershell
cd thermal-loop/backend
python -m pip install fastapi uvicorn pydantic httpx pytest
python run_server.py
```

## Validation

```powershell
cd thermal-loop
python scripts/validate_all.py
```

This runs the complete 38-test Python suite, TypeScript typecheck, Vite
production build, and scene/simulation contract validation. It verifies six
floors, 30 × 18 × 5 m greenhouse geometry, renderable connected pipe paths,
pipe-to-simulation state binding, mass/energy balances, and the non-measured-data
label. Live integration can be checked with `python tests/smoke_upgrade.py` while
both servers are running. Optional Chromium screenshots for camera presets are
produced by `scripts/capture_views.ps1`.

The balance tests cover capture split, primary circuit (including HX, heat-pump
source extraction, pipe loss, auxiliary rejection and unrejected heat),
secondary circuit (delivery, distribution loss, buffer state and standing loss),
and closed-loop mass residual.

## External solver integrations (run locally)

```powershell
# Blender geometry + GLB export
blender --background --python blender/build_model.py -- --out data/thermalloop.glb

# OpenModelica model generation, then simulate
python modelica/generate_model.py
omc modelica/run_openmodelica.mos

# EnergyPlus IDF fragment
python energyplus/generate_idf.py
# combine with full IDF + EPW, then: energyplus -w weather.epw -d out thermalloop.idf

# Optimization sweep over the simplified backend
python optimization/optimize.py
```

## Documentation

- `docs/ARCHITECTURE.md` — system architecture and data flow
- `docs/REQUIREMENTS.md` — engineering requirements and assumptions
- `docs/API.md` — REST API contract
- `docs/PHYSICS.md` — the physical models and their simplifications

## License / status

Research prototype. Simplified engineering models are clearly labeled; replace
them with validated equipment data or external solver coupling for production
use.
