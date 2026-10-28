"""Cooperating operations agents.

Every agent follows the same loop each step:
    observe -> evaluate -> propose/act -> (outcome measured next step) -> adjust

Agents are deterministic policy objects. They never touch the engine or the
safety limits directly; they read the :class:`~thermalloop.ops.state.Blackboard`
and emit requests/proposals/commits through the runtime. The optional
``forecaster`` lets an agent run a short branch simulation before acting -- that
is the only difference between mode B (no forecaster) and mode C.
"""
from .base import Agent, AgentOutput, Commit, Proposal, Request
from .workload import WorkloadAgent
from .gpu import GPUAgent
from .infrastructure import InfrastructureAgent
from .building import BuildingAgent
from .power_cooling import PowerCoolingAgent
from .heat_recovery import HeatRecoveryAgent
from .fault import FaultAgent
from .research import ResearchAgent

ALL_AGENTS = (
    WorkloadAgent, GPUAgent, InfrastructureAgent, BuildingAgent,
    PowerCoolingAgent, HeatRecoveryAgent, FaultAgent, ResearchAgent,
)

__all__ = [
    "Agent", "AgentOutput", "Commit", "Proposal", "Request",
    "WorkloadAgent", "GPUAgent", "InfrastructureAgent", "BuildingAgent",
    "PowerCoolingAgent", "HeatRecoveryAgent", "FaultAgent", "ResearchAgent",
    "ALL_AGENTS",
]
