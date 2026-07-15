"""Minimal prompts that preserve the DUT/oracle trust boundary."""

from __future__ import annotations

import json

from verilog_agent.models import Diagnostic
from verilog_agent.spec import TaskSpec

MODEL_RULES = """Return exactly one complete synthesizable Verilog DUT module.
Return no Markdown, explanation, or testbench.
Do not use include directives, simulation output/termination tasks, $system, file I/O,
VPI, PLI, or DPI.
Do not create additional modules.
The module name and ports must exactly match the structured specification.
Use non-blocking assignments in sequential logic.
Fully assign combinational outputs and avoid inferred latches."""


def generation_prompt(spec: TaskSpec) -> str:
    return (
        f"{MODEL_RULES}\n\nStructured specification:\n"
        f"{json.dumps(spec.to_dict(), sort_keys=True, indent=2)}"
    )


def repair_prompt(
    spec: TaskSpec,
    current_rtl: str,
    diagnostic: Diagnostic,
    attempt: int,
    remaining_retries: int,
) -> str:
    context = {
        "specification": spec.to_dict(),
        "diagnostic": diagnostic.to_dict(),
        "attempt": attempt,
        "remaining_retries": remaining_retries,
    }
    return (
        f"{MODEL_RULES}\nMinimize the change needed to repair the DUT.\n\n"
        f"Bounded repair context:\n{json.dumps(context, sort_keys=True, indent=2)}\n\n"
        f"Current DUT:\n{current_rtl}"
    )
