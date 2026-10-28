"""Autonomous operations layer for the ThermalLoop digital twin.

This package adds a stateful stepped simulation engine, an event bus, a shared
blackboard, an independent constraint-safety layer, a set of cooperating
agents, an arbitration layer, runtime scenario/fault injectors, a SQLite
experiment store, and a three-mode evaluation harness.

It reuses the physics primitives in ``thermalloop.physics`` and mirrors the
per-timestep thermodynamics of ``thermalloop.simulation``. The monolithic
``SimplifiedPhysicsEngine.run`` and its tests are left untouched.
"""

MODEL_VERSION = "ops-engine-1.0.0"
