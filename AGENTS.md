# Verilog Verification Agent contributor instructions

## Project scope

This repository implements a narrow, auditable harness for generating or repairing one
Verilog DUT and verifying it with Icarus Verilog. Version 1 supports exactly mux2, adder4,
counter4, shift_register4, rising_edge_detector, sequence_detector_1011, and alu4.

Do not expand this repository into a general EDA platform. Do not add web services,
databases, HDL families, vendor toolchains, agent frameworks, or live-LLM test dependencies.

## Directory ownership

- src/verilog_agent/spec.py owns the strict JSON trust boundary.
- src/verilog_agent/testbench.py owns deterministic trusted testbenches and oracles.
- src/verilog_agent/model_client.py and prompts.py own the DUT-only model boundary.
- src/verilog_agent/simulator.py owns fixed argv process execution and tool discovery.
- src/verilog_agent/diagnostics.py owns normalization of bounded tool output.
- src/verilog_agent/loop.py owns the maximum-four-attempt workflow.
- src/verilog_agent/report.py owns JSON and Markdown evidence reports.
- examples contains reviewed specifications and paired correct/broken RTL.
- tests/unit may isolate Python components; tests/integration and tests/e2e must use real
  iverilog and vvp whenever the tools are installed.

## Invariants

- A model may generate or repair only the DUT. It must never control the testbench,
  test vectors, expected values, clock, reset, or pass sentinel.
- The initial DUT is attempt one. At most three repair calls are allowed, so no workflow
  may exceed four total attempts.
- Missing tools, invalid specifications, workspace failures, process launch failures, and
  harness exceptions do not trigger model repair.
- Simulator commands are fixed argv lists, run with shell disabled and a fixed cwd.
- Paths must remain inside the repository. Existing non-empty run directories are immutable.
- Never log API keys or put them in reports.
- Never fake a passing compiler, simulator, or test result.

## Common commands

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    .\.venv\Scripts\python.exe -m verilog_agent doctor
    .\.venv\Scripts\python.exe -m pytest
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m mypy src
    .\.venv\Scripts\python.exe -m compileall -q src tests

## Required checks after changes

Run tests first, then lint, type checking, and Python compilation. If Icarus is absent,
integration and E2E tests must report explicit skips. State those skips and their cause;
never describe skipped simulations as passed. Review git diff and git diff --check before
handoff.
