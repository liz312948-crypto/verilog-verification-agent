"""Bounded generation/repair orchestration with immutable attempt evidence."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from verilog_agent.diagnostics import parse_compile_failure, parse_simulation_failure
from verilog_agent.errors import (
    InfrastructureError,
    InvalidModelOutputError,
    ModelClientError,
)
from verilog_agent.model_client import ModelClient, clean_and_validate_model_output
from verilog_agent.models import (
    AttemptRecord,
    Diagnostic,
    DiagnosticKind,
    FinalStatus,
)
from verilog_agent.report import VerificationReport, write_report
from verilog_agent.simulator import Simulator
from verilog_agent.spec import Mode, TaskSpec
from verilog_agent.testbench import FAIL_SENTINEL, PASS_SENTINEL, generate_testbench
from verilog_agent.workspace import (
    copy_final_rtl,
    prepare_output_directory,
    read_bounded_rtl,
    resolve_repository_path,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_command_logs(
    output_dir: Path,
    attempt: int,
    phase: str,
    stdout: str,
    stderr: str,
) -> None:
    (output_dir / f"{phase}_stdout.txt").write_text(stdout, encoding="utf-8")
    (output_dir / f"{phase}_stderr.txt").write_text(stderr, encoding="utf-8")
    (output_dir / f"attempt_{attempt:02d}_{phase}_stdout.txt").write_text(
        stdout, encoding="utf-8"
    )
    (output_dir / f"attempt_{attempt:02d}_{phase}_stderr.txt").write_text(
        stderr, encoding="utf-8"
    )


class VerificationLoop:
    def __init__(
        self,
        *,
        repository_root: Path,
        model_client: ModelClient,
        simulator: Simulator | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.model_client = model_client
        self.simulator = simulator or Simulator()

    def run(self, spec: TaskSpec, output_path: str) -> VerificationReport:
        output_dir = prepare_output_directory(self.repository_root, output_path)
        started_clock = time.monotonic()
        report = VerificationReport(
            task_id=spec.task_name,
            mode=spec.mode.value,
            circuit_kind=spec.circuit_kind.value,
            module_name=spec.module_name,
            spec_sha256=spec.spec_sha256,
            started_at=_utc_now(),
        )
        try:
            return self._run_prepared(spec, output_dir, report, started_clock)
        except Exception as exc:
            report.final_status = FinalStatus.INTERNAL_ERROR
            report.failure_kind = DiagnosticKind.INTERNAL_ERROR.value
            report.failure_reason = f"{type(exc).__name__}: {exc}"
            report.finished_at = _utc_now()
            report.duration_seconds = time.monotonic() - started_clock
            write_report(report, output_dir)
            return report

    def _run_prepared(
        self,
        spec: TaskSpec,
        output_dir: Path,
        report: VerificationReport,
        started_clock: float,
    ) -> VerificationReport:
        (output_dir / "spec.json").write_text(
            json.dumps(spec.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        testbench_path = output_dir / report.testbench_path
        testbench_path.write_text(generate_testbench(spec), encoding="utf-8")
        for name in (
            "compile_stdout.txt",
            "compile_stderr.txt",
            "simulation_stdout.txt",
            "simulation_stderr.txt",
        ):
            (output_dir / name).write_text("", encoding="utf-8")

        report.tool_versions = self.simulator.tool_versions(output_dir)
        try:
            self.simulator.ensure_available()
        except InfrastructureError as exc:
            return self._finish(
                report,
                output_dir,
                started_clock,
                FinalStatus.INFRASTRUCTURE_ERROR,
                DiagnosticKind.INFRASTRUCTURE_ERROR,
                str(exc),
            )

        try:
            if spec.mode is Mode.GENERATE:
                current_raw = self.model_client.generate_rtl(spec)
            else:
                assert spec.rtl_path is not None
                rtl_path = resolve_repository_path(
                    self.repository_root, spec.rtl_path, must_exist=True
                )
                current_raw = read_bounded_rtl(rtl_path)
        except (ModelClientError, OSError) as exc:
            return self._finish(
                report,
                output_dir,
                started_clock,
                FinalStatus.FAILED,
                DiagnosticKind.INVALID_MODEL_OUTPUT,
                str(exc),
            )

        last_diagnostic: Diagnostic | None = None
        for attempt_number in range(1, spec.max_attempts + 1):
            attempt_started = time.monotonic()
            raw_for_evidence = (
                current_raw if isinstance(current_raw, str) else repr(current_raw)
            )
            response_sha = _sha256_text(raw_for_evidence)
            attempt_path = output_dir / f"dut_attempt_{attempt_number:02d}.v"

            try:
                current_rtl = clean_and_validate_model_output(
                    current_raw, spec.module_name
                )
                attempt_path.write_text(current_rtl, encoding="utf-8")
                rtl_sha = _sha256_text(current_rtl)
            except InvalidModelOutputError as exc:
                current_rtl = raw_for_evidence
                attempt_path.write_text(raw_for_evidence, encoding="utf-8")
                _write_command_logs(output_dir, attempt_number, "compile", "", "")
                _write_command_logs(output_dir, attempt_number, "simulation", "", "")
                rtl_sha = _sha256_text(raw_for_evidence)
                last_diagnostic = Diagnostic(
                    kind=DiagnosticKind.INVALID_MODEL_OUTPUT,
                    message=str(exc),
                    attempt=attempt_number,
                )
                record = AttemptRecord(
                    attempt=attempt_number,
                    rtl_path=attempt_path.name,
                    rtl_sha256=rtl_sha,
                    model_response_sha256=response_sha,
                    diagnostic=last_diagnostic,
                    duration_seconds=time.monotonic() - attempt_started,
                )
                report.attempts.append(record)
                copy_final_rtl(attempt_path, output_dir / "final_dut.v")
                report.final_rtl_path = "final_dut.v"
                if not self._can_repair(spec, attempt_number, last_diagnostic):
                    break
                repair = self._request_repair(
                    spec, current_rtl, last_diagnostic, attempt_number, report
                )
                if repair is None:
                    break
                current_raw = repair
                continue

            compile_result, artifact = self.simulator.compile(
                attempt_path,
                testbench_path,
                workdir=output_dir,
                attempt=attempt_number,
            )
            _write_command_logs(
                output_dir,
                attempt_number,
                "compile",
                compile_result.stdout,
                compile_result.stderr,
            )
            _write_command_logs(output_dir, attempt_number, "simulation", "", "")
            truncated = compile_result.stdout_truncated or compile_result.stderr_truncated

            record = AttemptRecord(
                attempt=attempt_number,
                rtl_path=attempt_path.name,
                rtl_sha256=rtl_sha,
                model_response_sha256=response_sha,
                compile_command=list(compile_result.argv),
                compile_exit_code=compile_result.exit_code,
            )
            if compile_result.exit_code != 0 or compile_result.timed_out:
                last_diagnostic = parse_compile_failure(compile_result, attempt_number)
                record.diagnostic = last_diagnostic
                record.duration_seconds = time.monotonic() - attempt_started
                record.log_truncated = truncated
                report.attempts.append(record)
                copy_final_rtl(attempt_path, output_dir / "final_dut.v")
                report.final_rtl_path = "final_dut.v"
                if not self._can_repair(spec, attempt_number, last_diagnostic):
                    break
                repair = self._request_repair(
                    spec, current_rtl, last_diagnostic, attempt_number, report
                )
                if repair is None:
                    break
                current_raw = repair
                continue

            simulation_result = self.simulator.run(artifact, workdir=output_dir)
            _write_command_logs(
                output_dir,
                attempt_number,
                "simulation",
                simulation_result.stdout,
                simulation_result.stderr,
            )
            truncated = truncated or simulation_result.stdout_truncated
            truncated = truncated or simulation_result.stderr_truncated
            record.simulation_command = list(simulation_result.argv)
            record.simulation_exit_code = simulation_result.exit_code
            output = simulation_result.stdout + "\n" + simulation_result.stderr
            output_lines = [line.strip() for line in output.splitlines()]
            passed = (
                simulation_result.exit_code == 0
                and not simulation_result.timed_out
                and output_lines.count(PASS_SENTINEL) == 1
                and FAIL_SENTINEL not in output
            )
            if passed:
                record.duration_seconds = time.monotonic() - attempt_started
                record.log_truncated = truncated
                report.attempts.append(record)
                copy_final_rtl(attempt_path, output_dir / "final_dut.v")
                report.final_rtl_path = "final_dut.v"
                return self._finish(
                    report,
                    output_dir,
                    started_clock,
                    FinalStatus.PASSED,
                    None,
                    None,
                )

            last_diagnostic = parse_simulation_failure(
                simulation_result, attempt_number
            )
            record.diagnostic = last_diagnostic
            record.duration_seconds = time.monotonic() - attempt_started
            record.log_truncated = truncated
            report.attempts.append(record)
            copy_final_rtl(attempt_path, output_dir / "final_dut.v")
            report.final_rtl_path = "final_dut.v"
            if not self._can_repair(spec, attempt_number, last_diagnostic):
                break
            repair = self._request_repair(
                spec, current_rtl, last_diagnostic, attempt_number, report
            )
            if repair is None:
                break
            current_raw = repair

        reason = (
            report.failure_reason
            or (last_diagnostic.message if last_diagnostic else "verification failed")
        )
        kind = (
            DiagnosticKind(report.failure_kind)
            if report.failure_kind
            else (last_diagnostic.kind if last_diagnostic else DiagnosticKind.INTERNAL_ERROR)
        )
        return self._finish(
            report,
            output_dir,
            started_clock,
            FinalStatus.FAILED,
            kind,
            reason,
        )

    @staticmethod
    def _can_repair(
        spec: TaskSpec, attempt_number: int, diagnostic: Diagnostic
    ) -> bool:
        return (
            attempt_number < spec.max_attempts
            and diagnostic.kind is not DiagnosticKind.INFRASTRUCTURE_ERROR
        )

    def _request_repair(
        self,
        spec: TaskSpec,
        current_rtl: str,
        diagnostic: Diagnostic,
        attempt_number: int,
        report: VerificationReport,
    ) -> str | None:
        remaining = spec.max_repair_retries - report.repair_retries_used
        if remaining <= 0:
            return None
        report.repair_retries_used += 1
        try:
            return self.model_client.repair_rtl(
                spec, current_rtl, diagnostic, attempt_number, remaining
            )
        except ModelClientError as exc:
            report.failure_kind = DiagnosticKind.INVALID_MODEL_OUTPUT.value
            report.failure_reason = str(exc)
            return None

    @staticmethod
    def _finish(
        report: VerificationReport,
        output_dir: Path,
        started_clock: float,
        status: FinalStatus,
        failure_kind: DiagnosticKind | None,
        failure_reason: str | None,
    ) -> VerificationReport:
        if report.total_attempts > 4:
            raise AssertionError("verification loop exceeded four attempts")
        report.final_status = status
        report.failure_kind = failure_kind.value if failure_kind else None
        report.failure_reason = failure_reason
        report.log_truncated = any(attempt.log_truncated for attempt in report.attempts)
        report.finished_at = _utc_now()
        report.duration_seconds = time.monotonic() - started_clock
        write_report(report, output_dir)
        return report
