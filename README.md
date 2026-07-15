# Verilog Verification Agent

[![CI](https://github.com/liz312948-crypto/verilog-verification-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/liz312948-crypto/verilog-verification-agent/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Version: v0.1.0-alpha](https://img.shields.io/badge/Version-v0.1.0--alpha-orange.svg)

Current version identity: Git tag `v0.1.0-alpha`; Python distribution version `0.1.0a1`.
The PEP 440 package version is maintained in `pyproject.toml` and exposed as
`verilog_agent.__version__` from installed distribution metadata. This repository does not
claim a PyPI release.

Verilog Verification Agent is a deliberately small, testable harness that turns a validated
JSON circuit specification into an independently generated testbench, asks a model for only
the DUT, runs real Icarus compilation and simulation, and permits at most three repairs. Every
attempt and diagnostic is retained in an auditable report.

It is not an “AI chip designer” and not a general EDA platform.

## Why the model cannot own the oracle

If one model writes both RTL and the testbench, the same misunderstanding can appear on both
sides and produce a false pass. This project therefore treats the testbench as trusted code:
Python selects fixed vectors and expected behavior from a strict CircuitKind enum. The model
sees the specification and diagnostics, but never chooses the clock, reset, expected result,
verification command, or success sentinel.

## Architecture

    JSON specification
          |
          v
    strict parser + SHA-256 -------- invalid input -> INVALID_SPEC
          |
          +------> deterministic Python testbench/oracle
          |
          +------> model generates or repairs DUT only
                           |
                           v
                  output validator and cleaner
                           |
                           v
                  fixed iverilog argv -> fixed vvp argv
                           |
                 +---------+----------+
                 |                    |
              PASS sentinel      normalized diagnostic
                 |                    |
              final report       repair, at most 3 times

The main call chain is CLI → load_spec → VerificationLoop → generate_testbench →
clean_and_validate_model_output → Simulator → diagnostics → report.

## Supported circuits

| Circuit | Fixed behavior | Trusted coverage |
| --- | --- | --- |
| mux2 | y selects a for sel=0 and b for sel=1 | All 8 inputs |
| adder4 | Full five-bit a + b + cin | All 512 inputs |
| counter4 | Rising edge, synchronous reset, enabled increment, wrap | Reset, hold, overflow |
| shift_register4 | Enabled left shift q={q[2:0], serial_in} | Reset, hold, direction, patterns |
| rising_edge_detector | One-cycle pulse on sampled 0-to-1 transition | Repeated rise/high/fall/reset |
| sequence_detector_1011 | Overlapping Mealy-style FSM, registered pulse | Hits, misses, consecutive and overlap |
| alu4 | ADD, SUB, AND, OR, XOR; undefined gives zero | Every a, b, and all 8 opcodes |

For ALU subtraction, carry is one when no borrow occurs: a is greater than or equal to b.
The zero output is derived from result for every opcode.

## Install on Windows

Requirements are Python 3.11 or newer plus iverilog and vvp on PATH.

    cd D:\Projects\verilog-verification-agent
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    .\.venv\Scripts\python.exe -m verilog_agent doctor

The core package has no runtime Python dependency. To use the live OpenAI adapter:

    .\.venv\Scripts\python.exe -m pip install -e ".[llm]"
    $env:OPENAI_API_KEY = "set-in-your-shell-or-secret-store"
    $env:OPENAI_MODEL = "choose-an-available-model-at-runtime"

No model name is hard-coded. The API key is not included in prompts, logs, repr output, or
reports. Automated tests never call a live model.

## Doctor

    .\.venv\Scripts\python.exe -m verilog_agent doctor

Doctor prints the Python version, executable paths and version text for Icarus and vvp,
whether the optional SDK is installed, whether required environment variable names are set,
and a final ready boolean. Missing Icarus produces a nonzero infrastructure exit.
For hermetic CI or portable tools, VVA_IVERILOG and VVA_VVP may point to explicit executable
paths; those values still pass through shutil.which validation and cannot be selected by a model.

## Specification

Unknown fields are rejected. Files are UTF-8 JSON, limited to 64 KiB, and addressed by
repository-relative paths only.

    {
      "schema_version": "1.0",
      "task_name": "mux2_demo",
      "mode": "generate",
      "circuit_kind": "mux2",
      "module_name": "mux2",
      "description": "2-to-1 multiplexer",
      "max_repair_retries": 3
    }

Repair specifications use mode repair and must resolve an existing RTL path, either from
rtl_path in JSON or from the CLI --rtl override. Absolute paths and any path containing a
parent traversal segment are rejected.

## Generate and repair

With the optional OpenAI adapter configured:

    .\.venv\Scripts\python.exe -m verilog_agent generate --spec examples/specs/mux2.json --output runs/mux2

For a deterministic local demonstration with no API call:

    .\.venv\Scripts\python.exe -m verilog_agent generate --spec examples/specs/mux2.json --output runs/mux2-scripted --scripted-response examples/correct/mux2.v

Repair an existing counter, using a scripted reviewed repair for the demonstration:

    .\.venv\Scripts\python.exe -m verilog_agent repair --spec examples/specs/counter4.json --rtl examples/broken/counter4_buggy.v --output runs/counter4-repair --scripted-response examples/correct/counter4.v

The scripted option consumes response files in call order. It exists for tests and auditable
offline demonstrations; it does not weaken the same output validation or simulation path.

## Evidence and reports

Every output path must be a new or empty directory. A typical successful repair contains:

    runs/counter4-repair/
      spec.json
      generated_tb.v
      dut_attempt_01.v
      dut_attempt_02.v
      final_dut.v
      compile_stdout.txt
      compile_stderr.txt
      simulation_stdout.txt
      simulation_stderr.txt
      attempt_01_compile_stdout.txt
      attempt_01_compile_stderr.txt
      attempt_01_simulation_stdout.txt
      attempt_01_simulation_stderr.txt
      report.json
      report.md

Report JSON includes the task identity and spec hash, timestamps, status, tool paths/versions,
retry counts, every RTL and raw-response hash, fixed commands, exit codes, normalized
diagnostics, duration, truncation flags, and final artifact paths. A shortened shape is:

    {
      "final_status": "PASSED",
      "total_attempts": 2,
      "repair_retries_used": 1,
      "attempts": [
        {"attempt": 1, "diagnostic": {"kind": "ASSERTION_FAILURE"}},
        {"attempt": 2, "diagnostic": null}
      ],
      "final_rtl_path": "final_dut.v",
      "testbench_path": "generated_tb.v"
    }

Top-level compile and simulation logs describe the latest attempt; attempt-prefixed copies are
immutable evidence for the full timeline. Logs are length-bounded with an explicit truncation
marker.

## Testing

    .\.venv\Scripts\python.exe -m pytest
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m mypy src tests
    .\.venv\Scripts\python.exe -m compileall -q src tests

Unit tests do not need Icarus. Integration and E2E tests use real iverilog and vvp and are
explicitly skipped when either executable is missing; a skip is never reported as a pass.
CI installs Icarus on Ubuntu and runs every non-live test.

## Security boundary

The harness checks executable availability before calling a model, creates one
repository-confined output workspace per task, uses fixed argv lists with shell disabled,
sets separate compiler and simulator timeouts, caps captured logs, validates a single expected
module and its exact fixed port contract, and rejects include directives plus obvious
system/file/VPI/PLI/DPI constructs. Invalid raw model responses are represented in evidence by
a SHA-256 digest rather than being copied verbatim into run artifacts.

These controls are not a complete OS sandbox. Icarus and generated code still execute as local
processes. Do not expose this project as a public arbitrary-untrusted-code execution service.
Use a separately hardened execution boundary if the threat model requires hostile inputs.

## Current limitations

- Exactly seven fixed circuit semantics; no user-defined ports or arbitrary HDL behavior.
- Synthesizability is prompted and structurally constrained but not formally proven.
- No formal verification, waveform interpretation, coverage database, or vendor flow.
- Diagnostic parsing targets common Icarus formats and machine-readable testbench failures.
- Live model behavior depends on the separately installed SDK and runtime model availability.
- Run directories are intentionally not resumable or overwritable in version one.

## Non-goals

This project does not provide VHDL, Cocotb, Verilator, Vivado, Quartus, Docker, web APIs,
databases, frontends, multi-agent orchestration, vector databases, or a general EDA abstraction.

## Interview or résumé summary

Built a bounded Verilog generation-and-repair agent harness with strict JSON specifications,
model-independent deterministic verification oracles, real Icarus compile/simulation feedback,
defensive single-module validation, a maximum-four-attempt repair loop, normalized diagnostics,
and immutable JSON/Markdown evidence. Added exhaustive and stateful testbenches for seven
circuits plus unit, real-tool integration, end-to-end, and Ubuntu CI coverage without using a
live LLM in tests.
