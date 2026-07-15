# Verilog Verification Agent Implementation Plan

Last updated: 2026-07-14

## Scope and invariants

- Build a narrowly scoped harness for exactly seven supported circuit kinds.
- Generate every testbench and oracle deterministically from a validated JSON specification.
- Permit the model to generate or repair only the DUT; never accept a model-authored oracle.
- Run only fixed `iverilog` and `vvp` argv commands with `shell=False` in per-task workspaces.
- Allow at most three repairs after the initial DUT, for no more than four total attempts.
- Preserve immutable per-attempt evidence and produce JSON and Markdown reports on success or failure.
- Do not call a live LLM in automated tests and do not treat generated RTL execution as a complete OS sandbox.

## Environment baseline

- [x] Confirmed working directory is `D:\Projects\verilog-verification-agent`.
- [x] Confirmed Git repository is an empty independent repository on `main` with no unrelated changes.
- [x] Confirmed Python 3.12.10 (meets Python 3.11+ requirement).
- [x] Initial PATH checks found no Icarus. A portable Icarus 12.0 was later extracted
  under the ignored repository-local `.tools` directory without running its installer;
  both `iverilog` and `vvp` were executed successfully.

## Implementation phases

### Phase 1: foundation

- [x] Inspect repository and toolchain.
- [x] Create the maintained implementation plan.
- [x] Add package skeleton, `pyproject.toml`, ignore rules, and public typed models.
- [x] Create an in-repository virtual environment and install development dependencies.

### Phase 2: trusted verification core

- [x] Implement strict JSON specification parsing, hashing, path validation, and size limits.
- [x] Implement deterministic testbenches for all seven circuit kinds.
- [x] Implement fixed-command process runner and simulator with timeouts and bounded logs.
- [x] Implement normalized compiler, simulator, assertion, timeout, model-output, spec, infrastructure, and internal diagnostics.

### Phase 3: bounded agent workflow

- [x] Implement model protocol, scripted client, optional OpenAI client, prompt constraints, output cleaning, and validation.
- [x] Implement a maximum-four-attempt verification loop with immutable evidence.
- [x] Implement JSON/Markdown reporting and stable CLI exit behavior.
- [x] Implement `doctor`, `generate`, and `repair` commands.

### Phase 4: examples and verification

- [x] Add specifications plus correct and deliberately broken RTL for all seven circuit kinds.
- [x] Add unit tests for validation, model isolation, diagnostics, retry bounds, truncation, reports, and secret handling.
- [x] Add real-Icarus integration tests with explicit skips only when tools are unavailable.
- [x] Add end-to-end tests for all circuits, repair success, retry exhaustion, and report evidence.

### Phase 5: documentation and automation

- [x] Add `README.md`, repository `AGENTS.md`, MIT `LICENSE`, architecture decision record, and Ubuntu CI.
- [x] Document ALU SUB carry as `carry = 1` when no borrow (`a >= b`).
- [x] Document the overlapping Mealy-style `1011` detector semantics.

### Phase 6: final verification and audit

- [x] Run tests: 87 passed, 0 failed, 0 skipped with portable Icarus enabled.
- [x] Run lint: Ruff passed.
- [x] Run type checking: mypy passed for 26 source and test files.
- [x] Run Python bytecode compilation.
- [x] Run real `iverilog`/`vvp` verification with portable Icarus 12.0.
- [x] Review `git diff`, repository boundary, retry limits, testbench independence, shell safety, path safety, secret handling, and evidence integrity.
- [x] Update this plan so completed work is not left as an unexecuted plan.

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tests
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m verilog_agent doctor
git diff --check
git status --short
```

## Known risk and recovery

- The initial workstation PATH had no Icarus executables. The final local test run used
  repository-local portable binaries through explicit executable configuration; CI installs
  the distribution Icarus package. The portable `.tools` directory is ignored by Git.
- A failed implementation stage will be diagnosed before scope expands. Changes are confined to this repository and can be reviewed per file through Git.
