"""FastAPI application exposing the ThermalLoop digital-twin backend.

Endpoints (see docs/API.md):
  GET  /api/health
  GET  /api/config
  GET  /api/scene
  GET  /api/state
  POST /api/simulate
  GET  /api/results/{run_id}
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config_loader import load_config
from .results_store import ResultsStore
from .scene import build_scene
from .schemas import (
    HealthResponse,
    SimulationRequest,
    SimulationResult,
    StateResponse,
)
from .simulation import run_simulation

app = FastAPI(
    title="ThermalLoop AI Center API",
    version=__version__,
    description="Physics-based digital twin of an AI data center waste-heat recovery loop.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
store = ResultsStore(_RESULTS_DIR)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return load_config()


@app.get("/api/scene")
def get_scene() -> dict[str, Any]:
    return build_scene()


@app.get("/api/state", response_model=StateResponse)
def get_state() -> StateResponse:
    """Snapshot: run a short baseline and return the last timestep."""
    result = run_simulation({"mode": "simplified_physics", "duration_s": 3600, "timestep_s": 600})
    series = result.get("series") or []
    snapshot = series[-1] if series else {}
    snapshot["summary"] = result.get("summary", {})
    return StateResponse(mode="simplified_physics", snapshot=snapshot)


@app.post("/api/simulate", response_model=SimulationResult)
def simulate(req: SimulationRequest) -> SimulationResult:
    cfg = load_config()
    engine_req = req.to_engine_request()

    # expand named scenario overrides
    if req.scenario_id:
        scenario = next(
            (s for s in cfg["simulation"]["scenarios"] if s["id"] == req.scenario_id),
            None,
        )
        if scenario is None:
            raise HTTPException(404, f"Unknown scenario_id: {req.scenario_id}")
        merged = dict(scenario.get("overrides", {}))
        merged.update(engine_req.get("overrides", {}))
        engine_req["overrides"] = merged

    try:
        result = run_simulation(engine_req, cfg)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    result["run_id"] = run_id
    store.save(run_id, result)
    return SimulationResult(**result)


@app.get("/api/results/{run_id}", response_model=SimulationResult)
def get_results(run_id: str) -> SimulationResult:
    result = store.load(run_id)
    if result is None:
        raise HTTPException(404, f"Unknown run_id: {run_id}")
    return SimulationResult(**result)


# ---------------------------------------------------------------------------
# Static frontend (single-service deploy).
# After `npm run build`, frontend/dist exists and is served at "/". The SPA
# fallback returns index.html for non-API paths so client routing works.
# This block is a no-op in dev (dist absent) where Vite serves the frontend.
# ---------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Hashed build assets (JS/CSS) under /assets.
    _assets = _FRONTEND_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/")
    def _serve_index() -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def _spa_fallback(full_path: str) -> FileResponse:
        # Serve a real file if it exists (favicon, etc.); otherwise the SPA shell.
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
