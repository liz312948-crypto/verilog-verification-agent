# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) in a compact form.

## [Unreleased]

### Changed

- Normalized the Python distribution version to PEP 440 `0.1.0a1` while retaining the existing
  Git tag identity `v0.1.0-alpha`.
- Added wheel-install validation guidance and release-readiness documentation.

### Security

- Enforced exact fixed DUT port contracts for all seven supported circuit kinds.
- Rejected Windows drive-qualified and rooted paths explicitly, and stopped persisting raw
  rejected model responses in run evidence.
- Made each reported RTL SHA-256 digest verifiable directly against the persisted artifact bytes
  on Windows as well as POSIX systems.
- Classified compiler/simulator process launch failures as top-level infrastructure errors
  without invoking a model repair.

## [0.1.0-alpha] - 2026-07-14

### Added

- Strict, size-bounded JSON specifications for exactly seven fixed circuits: `mux2`, `adder4`,
  `counter4`, `shift_register4`, `rising_edge_detector`, `sequence_detector_1011`, and `alu4`.
- Trusted deterministic Python testbench generation, independent of the DUT-producing model.
- Real `iverilog` compilation and `vvp` simulation with fixed argv, timeouts, and bounded logs.
- A bounded loop allowing at most three repairs and four total attempts.
- Auditable JSON and Markdown reports with per-attempt RTL, hashes, commands, diagnostics, and
  logs.
- `ScriptedModelClient` for offline and deterministic workflows, plus an optional OpenAI adapter
  that is excluded from core and live-free automated tests.
- An 87-test alpha baseline covering unit, real-Icarus integration, end-to-end repair, and
  exhaustion behavior, with Ubuntu GitHub Actions CI.

### Security

- Repository-confined paths, strict model-output filtering, no model-controlled shell command,
  and no API-key recording.
- The execution controls are not an OS sandbox; generated HDL must not be offered as a public
  arbitrary-untrusted-code execution service.

### Known limitations

- Only the seven documented circuit semantics are supported; arbitrary Verilog specifications,
  user-defined ports, formal verification, coverage databases, and vendor flows are out of
  scope.
- The optional live-model path depends on separately installed SDK and runtime configuration.

[Unreleased]: https://github.com/liz312948-crypto/verilog-verification-agent/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/liz312948-crypto/verilog-verification-agent/tree/v0.1.0-alpha
