"""Normalize Icarus compile and simulation output into bounded diagnostics."""

from __future__ import annotations

import re

from verilog_agent.models import CommandResult, Diagnostic, DiagnosticKind

COMPILE_LOCATION_RE = re.compile(
    r"(?P<file>[^:\r\n]+):(?P<line>\d+):(?:\s*(?:error|syntax error):?)?\s*(?P<message>.+)",
    re.IGNORECASE,
)
FAIL_FIELD_RE = re.compile(r"\b(vector|expected|actual)=((?:\"[^\"]*\")|[^\s]+)")


def _excerpt(*parts: str, limit: int = 4_000) -> str:
    combined = "\n".join(part for part in parts if part).strip()
    return combined[:limit]


def parse_compile_failure(result: CommandResult, attempt: int) -> Diagnostic:
    if result.timed_out:
        return Diagnostic(
            kind=DiagnosticKind.TIMEOUT,
            message="Icarus compilation timed out",
            attempt=attempt,
            raw_excerpt=_excerpt(result.stdout, result.stderr),
        )
    if result.launch_error:
        return Diagnostic(
            kind=DiagnosticKind.INFRASTRUCTURE_ERROR,
            message=f"could not start compiler: {result.launch_error}",
            attempt=attempt,
        )
    raw = _excerpt(result.stderr, result.stdout)
    match = COMPILE_LOCATION_RE.search(raw)
    return Diagnostic(
        kind=DiagnosticKind.COMPILE_ERROR,
        message=match.group("message").strip() if match else "Icarus compilation failed",
        attempt=attempt,
        file=match.group("file").strip() if match else None,
        line=int(match.group("line")) if match else None,
        raw_excerpt=raw,
    )


def parse_simulation_failure(result: CommandResult, attempt: int) -> Diagnostic:
    if result.timed_out:
        return Diagnostic(
            kind=DiagnosticKind.TIMEOUT,
            message="simulation timed out",
            attempt=attempt,
            raw_excerpt=_excerpt(result.stdout, result.stderr),
        )
    if result.launch_error:
        return Diagnostic(
            kind=DiagnosticKind.INFRASTRUCTURE_ERROR,
            message=f"could not start simulator: {result.launch_error}",
            attempt=attempt,
        )
    raw = _excerpt(result.stdout, result.stderr)
    if "VVA_VERIFICATION_FAIL" in raw:
        fields = {
            key: value.strip('"') for key, value in FAIL_FIELD_RE.findall(raw)
        }
        return Diagnostic(
            kind=DiagnosticKind.ASSERTION_FAILURE,
            message="trusted testbench reported a mismatch",
            attempt=attempt,
            vector=fields.get("vector"),
            expected=fields.get("expected"),
            actual=fields.get("actual"),
            raw_excerpt=raw,
        )
    return Diagnostic(
        kind=DiagnosticKind.SIMULATION_ERROR,
        message="simulation exited unsuccessfully or omitted the pass sentinel",
        attempt=attempt,
        raw_excerpt=raw,
    )
