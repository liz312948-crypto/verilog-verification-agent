# Architecture decisions

## 2026-07-14 — Trusted deterministic oracle

- Project: Verilog Verification Agent.
- Decision or fact: Testbenches, vectors, clocks, resets, expected values, and pass/fail
  sentinels are generated only by deterministic Python mapped to one of seven circuit kinds.
- Context: Allowing one model to author both a DUT and its oracle can make matching mistakes
  appear correct.
- Alternatives considered: model-authored testbenches and generic natural-language specs
  were rejected because neither provides an independent auditable oracle.
- Verification: unit tests assert deterministic generation for every kind; integration tests
  compile correct examples and require every paired broken example to fail.
- Follow-up: any new circuit kind requires a reviewed specification and independent testbench
  generator before it can enter the enum.

## 2026-07-14 — Strict four-attempt ceiling

- Project: Verilog Verification Agent.
- Decision or fact: one initial DUT plus at most three repairs is a system invariant.
- Context: retries must expose model quality rather than hide defects or loop indefinitely.
- Alternatives considered: configurable unbounded loops and adaptive retry increases were
  rejected.
- Verification: specification parsing rejects values above three; unit and E2E tests assert
  exactly four attempts and three repair calls on exhaustion.
- Follow-up: do not weaken both parser and orchestration guards in the same change.

## 2026-07-14 — Stable sequential and ALU semantics

- Project: Verilog Verification Agent.
- Decision or fact: resets are synchronous and active high; sequence_detector_1011 is an
  overlapping Mealy-style detector with a registered one-cycle detected output; ALU
  subtraction carry is one when no borrow occurs, meaning a is greater than or equal to b.
- Context: these details otherwise admit multiple individually plausible implementations.
- Alternatives considered: borrow-as-carry and non-overlapping FSM behavior were rejected.
- Verification: generated testbenches explicitly cover reset timing, overlap, every ALU opcode,
  all four-bit inputs, undefined opcodes, carry, and zero.
- Follow-up: preserve these semantics in prompts, examples, and documentation.

## 2026-07-14 — Process containment is not an OS sandbox

- Project: Verilog Verification Agent.
- Decision or fact: the runner uses repository-confined workspaces, fixed argv, shell disabled,
  bounded logs, and compile/simulation timeouts, but makes no claim of OS-level isolation.
- Context: generated HDL is still code consumed by native tools.
- Alternatives considered: Docker and a public arbitrary-code service are outside version-one
  scope.
- Verification: command-runner, traversal, timeout, and immutable-evidence tests cover the
  implemented controls; every report repeats the residual-risk warning.
- Follow-up: use this only with trusted or controlled model outputs on a local/CI machine.

## 2026-07-14 — Alpha version mapping and single package source

- Project: Verilog Verification Agent.
- Decision or fact: the existing public Git tag remains `v0.1.0-alpha`, while the equivalent
  PEP 440 Python distribution version is `0.1.0a1`. `pyproject.toml` is the only manually
  maintained package-version source; `verilog_agent.__version__` reads installed distribution
  metadata.
- Context: the original `0.1.0` package metadata incorrectly implied a final release and a
  second handwritten value in `__init__.py` could drift.
- Alternatives considered: moving the published Git tag was disallowed; duplicating the value
  in package source with only a consistency test was less robust.
- Verification: a unit test compares the public package attribute, installed metadata, and
  expected PEP 440 value; wheel smoke tests import the package outside the repository.
- Follow-up: future releases update the version only in `pyproject.toml`, then create a new Git
  tag after the release commit rather than rewriting an existing remote tag.
