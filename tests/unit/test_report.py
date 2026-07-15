from __future__ import annotations

import json
from pathlib import Path

from verilog_agent.models import AttemptRecord, Diagnostic, DiagnosticKind
from verilog_agent.report import VerificationReport, write_report


def test_report_serializes_complete_attempt_timeline(tmp_path: Path) -> None:
    report = VerificationReport(
        task_id="mux_test",
        mode="generate",
        circuit_kind="mux2",
        module_name="mux2",
        spec_sha256="a" * 64,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        attempts=[
            AttemptRecord(
                attempt=1,
                rtl_path="dut_attempt_01.v",
                rtl_sha256="b" * 64,
                model_response_sha256="c" * 64,
                compile_command=["iverilog", "-g2012"],
                compile_exit_code=1,
                diagnostic=Diagnostic(
                    kind=DiagnosticKind.COMPILE_ERROR,
                    message="syntax error",
                    attempt=1,
                    file="dut_attempt_01.v",
                    line=2,
                ),
            )
        ],
    )
    write_report(report, tmp_path)
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert data["total_attempts"] == 1
    assert data["attempts"][0]["diagnostic"]["line"] == 2
    assert "not a complete OS sandbox" in data["security_note"]
    assert "Attempt 01" in (tmp_path / "report.md").read_text(encoding="utf-8")
