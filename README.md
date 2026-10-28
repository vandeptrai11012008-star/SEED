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


## Repository structure

```text
SEED/
  frontend/                  React + TypeScript + Three.js / Vite
    index.html
    package.json
    src/
      main.tsx
      App.tsx
      store.ts
      api/                   API contract and client
      three/                 3D scene components
      ui/                    Dashboard and presentation components
  backend/
    serve.py                 Production ASGI server (reads PORT)
    run_server.py            Local development API server
    requirements.txt
    thermalloop/             FastAPI + physics simulation
  config/                    Shared JSON data contract
  Dockerfile                 Multi-stage Node/Python production image
  render.yaml                Render Blueprint
```

## Interactive 3D facility

The default illustrated cutaway frames the complete site with an exaggerated vertical scale for legibility. Simulation view retains the 1:1 SI geometry. The procedural
R3F model includes structural slabs/columns/beams, a transparent curtain wall,
all six cutaway floors, detailed GPU racks and cooling manifolds, robot cells,
seed racks and growth chambers, B2 plate HX/pumps/valves/two tanks, an arched
glass greenhouse with plants and soil beds, and the underground utility tunnel.
All 40 rendered pipe segments come from `config/network.json`; animated particles
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

GPU rack faces use a local detailed panel texture with load-linked status rails.
Crops have curved leaves, growing supports and fruit; crop and tree geometry is
instanced to keep draw calls low. Floor and soil textures are generated locally.
The illustrated view arranges the same rack IDs for readability; Simulation view
retains the engineering coordinates. These visual details do not change simulated
rack counts, hydraulic routing or physics inputs.

## Requirements

- **Windows 11** (instructions below; works on macOS/Linux too)
- **Python 3.10+** (tested on 3.15)
- **Node.js 18+** (tested on 24)
- Optional, for high-fidelity modes: Blender, OpenModelica, EnergyPlus


## Local development

Requirements: Node.js 20+, Python 3.12+.

From the repository root, start the backend in one terminal:

```powershell
python -m pip install -r backend/requirements.txt
python backend/run_server.py
```

The API runs at `http://127.0.0.1:8000` (health: `/api/health`, Swagger: `/docs`).

In another terminal, run the frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the local backend.

## Render deployment (one web service)

The repository includes a **multi-stage Dockerfile**. The Node stage installs
frontend dependencies and builds Vite; the Python stage installs FastAPI,
copies `frontend/dist`, and serves both the UI and API on Render's `PORT`.

1. Push the repository with the directory structure shown above.
2. On Render, create **New > Blueprint**, select this repository and apply `render.yaml`.
   It creates a Docker web service on the free plan.
3. Keep Render's service root at the **repository root**. For a separately
   created Web Service, choose **Docker** instead of Node/Python.
4. After deployment, `/` should load the 3D interface and
   `/api/health` should return a JSON health response.

For this single-service setup, **do not set `VITE_API_BASE`**: browser API calls
must use the same origin as the frontend. There is no need to upload the
`thermal-loop-render.zip` file; Docker uses the checked-in source folders.

Generated simulation result files live on the service's filesystem. The free
Render instance does not preserve these across redeploys/restarts; use a
database or persistent storage if long-term result retention becomes necessary.

## Validation

Run `python -m pytest -q tests` from the repository root for piping regression tests.
They check shared-node continuity, orthogonal routing, separate heat-exchanger and tank
ports, GPU manifold connections, and zero flow in inactive cooler/storage branches.
Pipes use straight runs with bounded elbows; the supply and return risers sit together
on the building's right edge. The external buffer and treatment tanks remain branches
of the secondary circuit, hydraulically isolated from the GPU loop at the B2 exchanger.


The GitHub Actions workflow `.github/workflows/verify.yml` checks the
TypeScript production build, FastAPI health/config/scene endpoints, and
a production Docker image build + HTTP health check.

To run the frontend build locally:

```powershell
cd frontend
npm ci
npm run build
```

## Optional integrations

Blender, OpenModelica, EnergyPlus, and optimization tooling described by the
larger research project are **not included** in this minimal repository. The
web app uses procedural Three.js geometry and the simplified physics backend.

## License / status

Research prototype. Simplified engineering models are clearly labeled; replace
them with validated equipment data or external solver coupling for production
use.
