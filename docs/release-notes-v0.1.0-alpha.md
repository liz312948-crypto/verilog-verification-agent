# Verilog Verification Agent v0.1.0-alpha

Git tag identity: `v0.1.0-alpha`  
Python distribution version: `0.1.0a1`

## Project positioning

This alpha is a narrow, auditable harness for producing or repairing one Verilog DUT and
checking it against a trusted deterministic oracle. It is not an AI chip designer, a general
EDA platform, an arbitrary-Verilog specification engine, or a public untrusted-code service.

## Main capabilities

- Strict JSON specifications for exactly seven fixed circuit semantics.
- Deterministic Python-generated testbenches, vectors, clocks, resets, expected results, and
  pass/fail sentinels; a model controls only the DUT.
- Real Icarus Verilog compilation and simulation with normalized diagnostics.
- One initial attempt plus at most three repairs, never more than four total attempts.
- Immutable per-attempt evidence and final JSON/Markdown reports.
- Offline `ScriptedModelClient` and an optional, separately installed OpenAI adapter.

## Verification evidence

The tagged alpha baseline contained 87 passing tests and an Ubuntu GitHub Actions workflow that
installs Icarus Verilog before running all non-live tests. The suite exercises all seven correct
examples, all seven deliberately broken examples, successful scripted repairs, strict retry
exhaustion, real compiler/simulator failures, timeout termination, reports, and secret handling.
Automated tests do not call a real LLM API.

Release-readiness work additionally builds both sdist and wheel, inspects their members, installs
the wheel into a fresh virtual environment outside the repository, and runs offline generate and
repair demonstrations. Exact local results should be recorded in the audit handoff; these notes do
not claim a PyPI publication.

## Security boundary

The harness confines requested paths to the repository, uses fixed argv with `shell=False`, checks
tool availability, applies compile/simulation timeouts, bounds logs, validates one expected module
with an exact fixed port contract, and filters dangerous model-output constructs. These controls
are defense in depth, not an OS sandbox. Use a separately hardened execution environment if HDL or
tool inputs may be hostile.

## Known limitations

- Only `mux2`, `adder4`, `counter4`, `shift_register4`, `rising_edge_detector`,
  `sequence_detector_1011`, and `alu4` are accepted.
- No arbitrary ports or natural-language circuit semantics, formal verification, waveform
  interpretation, coverage database, vendor toolchain, or alternative HDL.
- Synthesizability is constrained and prompted but not formally proven.
- Live-model behavior depends on an installed optional SDK, API credentials, and a model name
  chosen at runtime.
- Native Icarus processes remain subject to the host operating system's security boundary.

## Install from the repository

```powershell
cd D:\Projects\verilog-verification-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\verilog-agent.exe doctor
```

## Offline generate demonstration

```powershell
.\.venv\Scripts\verilog-agent.exe generate `
  --spec examples/specs/mux2.json `
  --output runs/release-generate `
  --scripted-response examples/correct/mux2.v
```

Expected evidence: `PASSED`, one total attempt, zero repair retries, a trusted generated
testbench, the final DUT, compiler/simulator logs, and matching JSON/Markdown reports.

## Offline repair demonstration

```powershell
.\.venv\Scripts\verilog-agent.exe repair `
  --spec examples/specs/counter4.json `
  --rtl examples/broken/counter4_buggy.v `
  --output runs/release-counter4-repair `
  --scripted-response examples/correct/counter4.v
```

Expected evidence: attempt one is rejected by the trusted testbench with an assertion failure;
attempt two passes using the scripted repair; `total_attempts` is 2 and
`repair_retries_used` is 1. Supplying `--scripted-response` selects the offline client and does
not call the OpenAI adapter.
