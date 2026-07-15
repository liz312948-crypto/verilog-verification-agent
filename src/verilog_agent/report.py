"""Machine-readable and human-readable verification reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verilog_agent.models import AttemptRecord, FinalStatus


@dataclass
class VerificationReport:
    task_id: str
    mode: str
    circuit_kind: str
    module_name: str
    spec_sha256: str
    started_at: str
    finished_at: str = ""
    final_status: FinalStatus = FinalStatus.FAILED
    repair_retries_used: int = 0
    tool_versions: dict[str, str | None] = field(default_factory=dict)
    attempts: list[AttemptRecord] = field(default_factory=list)
    duration_seconds: float = 0.0
    final_rtl_path: str | None = None
    testbench_path: str = "generated_tb.v"
    log_truncated: bool = False
    failure_kind: str | None = None
    failure_reason: str | None = None

    @property
    def total_attempts(self) -> int:
        return len(self.attempts)

    def to_dict(self) -> dict[str, Any]:
        diagnostics = [
            attempt.diagnostic.to_dict()
            for attempt in self.attempts
            if attempt.diagnostic is not None
        ]
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "circuit_kind": self.circuit_kind,
            "module_name": self.module_name,
            "spec_sha256": self.spec_sha256,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "final_status": self.final_status.value,
            "total_attempts": self.total_attempts,
            "repair_retries_used": self.repair_retries_used,
            "tool_versions": self.tool_versions,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "diagnostics": diagnostics,
            "duration_seconds": self.duration_seconds,
            "final_rtl_path": self.final_rtl_path,
            "testbench_path": self.testbench_path,
            "log_truncated": self.log_truncated,
            "failure_kind": self.failure_kind,
            "failure_reason": self.failure_reason,
            "security_note": (
                "Fixed commands and timeouts reduce risk but are not a complete OS sandbox; "
                "do not expose this harness as a public untrusted-code execution service."
            ),
        }


def render_markdown(report: VerificationReport) -> str:
    lines = [
        f"# Verification report: {report.task_id}",
        "",
        f"- Status: **{report.final_status.value}**",
        f"- Mode: {report.mode}",
        f"- Circuit: {report.circuit_kind}",
        f"- Module: {report.module_name}",
        f"- Spec SHA-256: {report.spec_sha256}",
        f"- Attempts: {report.total_attempts}",
        f"- Repair retries used: {report.repair_retries_used}",
        f"- Duration: {report.duration_seconds:.3f} seconds",
        f"- Logs truncated: {'yes' if report.log_truncated else 'no'}",
    ]
    if report.failure_kind:
        lines.append(f"- Failure kind: {report.failure_kind}")
    if report.failure_reason:
        lines.append(f"- Failure reason: {report.failure_reason}")
    lines.extend(["", "## Attempt timeline", ""])
    if not report.attempts:
        lines.append("No DUT attempt was executed.")
    for attempt in report.attempts:
        outcome = attempt.diagnostic.kind.value if attempt.diagnostic else "PASSED"
        lines.extend(
            [
                f"### Attempt {attempt.attempt:02d}: {outcome}",
                "",
                f"- RTL: {attempt.rtl_path}",
                f"- RTL SHA-256: {attempt.rtl_sha256}",
                f"- Compile exit: {attempt.compile_exit_code}",
                f"- Simulation exit: {attempt.simulation_exit_code}",
                f"- Duration: {attempt.duration_seconds:.3f} seconds",
            ]
        )
        if attempt.diagnostic:
            lines.append(f"- Diagnostic: {attempt.diagnostic.message}")
        lines.append("")
    lines.extend(
        [
            "## Security boundary",
            "",
            "The harness uses fixed argv commands, repository-confined paths, timeouts, and "
            "bounded logs. It is not a complete OS sandbox and must not be offered as a "
            "public service for arbitrary untrusted Verilog.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: VerificationReport, output_dir: Path) -> None:
    (output_dir / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
