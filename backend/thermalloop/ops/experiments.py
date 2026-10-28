"""SQLite-backed experiment and run store.

Records research experiments and mode-comparison runs so results are durable
and auditable. We store the hypothesis, the exact config (mode, scenario, seed,
model version), the resulting metrics, any constraint violations, and a plain
conclusion with explicit limitations. Nothing is auto-promoted to policy and no
fabricated confidence is stored -- only measured outcomes.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    created_s     REAL NOT NULL,
    mode          TEXT NOT NULL,
    scenario      TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    n_steps       INTEGER NOT NULL,
    metrics_json  TEXT NOT NULL,
    violations_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    exp_id        TEXT PRIMARY KEY,
    created_s     REAL NOT NULL,
    hypothesis    TEXT NOT NULL,
    config_json   TEXT NOT NULL,
    model_version TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    metrics_json  TEXT NOT NULL,
    violations_json TEXT NOT NULL,
    conclusion    TEXT NOT NULL,
    limitations   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comparisons (
    cmp_id        TEXT PRIMARY KEY,
    created_s     REAL NOT NULL,
    scenario      TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    result_json   TEXT NOT NULL
);
"""


class ExperimentStore:
    def __init__(self, path: str | Path = "results/experiments.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # FastAPI runs sync endpoints in a threadpool, so the connection may be
        # touched from multiple threads. check_same_thread=False + a lock makes
        # that safe for our low write volume.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            # WAL allows concurrent readers alongside a writer; busy_timeout
            # avoids "database is locked" if another connection ever appears.
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -------------------------------------------------------------- runs
    def save_run(self, run_id: str, *, mode: str, scenario: str, seed: int,
                 model_version: str, n_steps: int, metrics: dict[str, Any],
                 violations: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, created_s, mode, scenario, "
                "seed, model_version, n_steps, metrics_json, violations_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, time.time(), mode, scenario, seed, model_version, n_steps,
                 json.dumps(metrics), json.dumps(violations)))
            self._conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._row_run(row) if row else None

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY created_s DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_run(r) for r in rows]

    # -------------------------------------------------------- experiments
    def save_experiment(self, exp_id: str, *, hypothesis: str, config: dict[str, Any],
                        model_version: str, seed: int, metrics: dict[str, Any],
                        violations: dict[str, Any], conclusion: str,
                        limitations: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO experiments (exp_id, created_s, hypothesis, "
                "config_json, model_version, seed, metrics_json, violations_json, "
                "conclusion, limitations) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (exp_id, time.time(), hypothesis, json.dumps(config), model_version,
                 seed, json.dumps(metrics), json.dumps(violations), conclusion, limitations))
            self._conn.commit()

    def list_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM experiments ORDER BY created_s DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            out.append({
                "exp_id": r[0], "created_s": r[1], "hypothesis": r[2],
                "config": json.loads(r[3]), "model_version": r[4], "seed": r[5],
                "metrics": json.loads(r[6]), "violations": json.loads(r[7]),
                "conclusion": r[8], "limitations": r[9]})
        return out

    # --------------------------------------------------------- comparisons
    def save_comparison(self, cmp_id: str, *, scenario: str, seed: int,
                       model_version: str, result: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO comparisons (cmp_id, created_s, scenario, "
                "seed, model_version, result_json) VALUES (?,?,?,?,?,?)",
                (cmp_id, time.time(), scenario, seed, model_version, json.dumps(result)))
            self._conn.commit()

    def list_comparisons(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM comparisons ORDER BY created_s DESC LIMIT ?", (limit,)).fetchall()
        return [{"cmp_id": r[0], "created_s": r[1], "scenario": r[2], "seed": r[3],
                 "model_version": r[4], "result": json.loads(r[5])} for r in rows]

    @staticmethod
    def _row_run(r: Any) -> dict[str, Any]:
        return {"run_id": r[0], "created_s": r[1], "mode": r[2], "scenario": r[3],
                "seed": r[4], "model_version": r[5], "n_steps": r[6],
                "metrics": json.loads(r[7]), "violations": json.loads(r[8])}
