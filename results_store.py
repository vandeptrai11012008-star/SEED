"""Persist simulation results to the results/ directory as JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class ResultsStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, dict[str, Any]] = {}

    def _path(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.json"

    def save(self, run_id: str, result: dict[str, Any]) -> None:
        self._mem[run_id] = result
        with self._path(run_id).open("w", encoding="utf-8") as fh:
            json.dump(result, fh)

    def load(self, run_id: str) -> Optional[dict[str, Any]]:
        if run_id in self._mem:
            return self._mem[run_id]
        p = self._path(run_id)
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._mem[run_id] = data
        return data
