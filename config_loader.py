"""Load and merge the shared JSON configuration contract.

The config/ directory is the single source of truth shared by the backend,
the 3D frontend, and external solver adapters.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

# config lives at repo_root/config ; this file is at repo_root/backend/thermalloop
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

CONFIG_FILES = [
    "units",
    "site",
    "geometry",
    "equipment",
    "network",
    "assumptions",
    "simulation",
]


def config_dir() -> Path:
    env = os.environ.get("THERMALLOOP_CONFIG_DIR")
    return Path(env) if env else _DEFAULT_CONFIG_DIR


def _load_one(name: str, directory: Path) -> dict[str, Any]:
    path = directory / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    directory = config_dir()
    cfg: dict[str, Any] = {}
    for name in CONFIG_FILES:
        cfg[name] = _load_one(name, directory)
    return cfg


def clear_cache() -> None:
    load_config.cache_clear()


def expand_rack_ids(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize the stable rack identifiers declared in equipment.json."""
    gen = cfg["equipment"]["racks"]["generator"]
    racks: list[dict[str, Any]] = []
    for floor in gen["floors"]:
        for i in range(1, gen["per_floor"] + 1):
            rid = gen["id_pattern"].format(floor=floor, index=i)
            racks.append(
                {
                    "id": rid,
                    "floor": floor,
                    "nominal_power_kW": gen["nominal_power_kW_each"],
                }
            )
    return racks
