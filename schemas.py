"""Pydantic schemas for the ThermalLoop API contract."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

SimMode = Literal["simplified_physics", "openmodelica", "energyplus", "coupled"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str = "thermalloop-backend"
    version: str


class SimulationRequest(BaseModel):
    mode: SimMode = "simplified_physics"
    scenario_id: Optional[str] = Field(
        default=None, description="Optional named scenario from simulation.json."
    )
    duration_s: Optional[int] = Field(default=None, ge=60, le=2_678_400)
    timestep_s: Optional[int] = Field(default=None, ge=1, le=86_400)
    start_hour: Optional[float] = Field(default=None, ge=0, lt=24)

    total_it_power_kW: Optional[float] = Field(default=None, ge=0, le=10_000)
    liquid_capture_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    gpu_load_base_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    gpu_load_peak_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    ambient_mean_C: Optional[float] = Field(default=None, ge=-60, le=60)

    heat_pump_enabled: Optional[bool] = None
    aux_rejection_enabled: Optional[bool] = None

    overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_run_limits(self) -> "SimulationRequest":
        if self.duration_s is not None and self.timestep_s is not None:
            if self.timestep_s > self.duration_s:
                raise ValueError("timestep_s must not exceed duration_s")
            if self.duration_s % self.timestep_s != 0:
                raise ValueError("duration_s must be an integer multiple of timestep_s")
            if self.duration_s // self.timestep_s > 10_000:
                raise ValueError("simulation is limited to 10,000 timesteps")
        if (
            self.gpu_load_base_fraction is not None
            and self.gpu_load_peak_fraction is not None
            and self.gpu_load_base_fraction > self.gpu_load_peak_fraction
        ):
            raise ValueError("gpu_load_base_fraction must not exceed gpu_load_peak_fraction")

        allowed_overrides = {
            "controls.heat_pump_enabled": bool,
            "weather.ambient_mean_C": (int, float),
            "gpu_load_base_fraction": (int, float),
            "gpu_load_peak_fraction": (int, float),
        }
        unknown = set(self.overrides) - set(allowed_overrides)
        if unknown:
            raise ValueError(f"unsupported override keys: {sorted(unknown)}")
        for key, value in self.overrides.items():
            expected = allowed_overrides[key]
            if not isinstance(value, expected) or isinstance(value, bool) and expected != bool:
                raise ValueError(f"invalid value type for override '{key}'")
            if key.startswith("gpu_load_") and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"override '{key}' must be in [0, 1]")
            if key == "weather.ambient_mean_C" and not -60.0 <= float(value) <= 60.0:
                raise ValueError("weather.ambient_mean_C must be between -60 and 60 C")
        return self

    def to_engine_request(self) -> dict[str, Any]:
        d = {k: v for k, v in self.model_dump().items() if v is not None}
        d.setdefault("overrides", {})
        return d


class ConservationCheck(BaseModel):
    lhs_J: float
    rhs_J: float
    relative_error: float
    passed: bool


class SimulationResult(BaseModel):
    run_id: str
    mode: SimMode
    is_measured_data: bool = False
    disclaimer: Optional[str] = None
    executed: bool = True
    status: Optional[str] = None
    message: Optional[str] = None
    timestep_s: Optional[int] = None
    duration_s: Optional[int] = None
    n_steps: Optional[int] = None
    series: Optional[list[dict[str, Any]]] = None
    energy_totals_J: Optional[dict[str, float]] = None
    energy_totals_kWh: Optional[dict[str, float]] = None
    conservation_checks: Optional[dict[str, Any]] = None
    summary: Optional[dict[str, Any]] = None


class StateResponse(BaseModel):
    """Lightweight current-state snapshot (last step of a short default run)."""
    mode: SimMode
    is_measured_data: bool = False
    snapshot: dict[str, Any]
