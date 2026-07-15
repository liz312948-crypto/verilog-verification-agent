"""Bounded Verilog generation and repair verification harness."""

from verilog_agent.loop import VerificationLoop
from verilog_agent.model_client import ModelClient, OpenAIModelClient, ScriptedModelClient
from verilog_agent.spec import CircuitKind, Mode, TaskSpec, load_spec

__all__ = [
    "CircuitKind",
    "Mode",
    "ModelClient",
    "OpenAIModelClient",
    "ScriptedModelClient",
    "TaskSpec",
    "VerificationLoop",
    "load_spec",
]

__version__ = "0.1.0"
