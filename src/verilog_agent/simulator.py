"""Fixed-command Icarus Verilog compiler and simulator wrapper."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from verilog_agent.errors import InfrastructureError
from verilog_agent.models import CommandResult

DEFAULT_LOG_LIMIT = 64 * 1024


def truncate_log(value: str, limit: int = DEFAULT_LOG_LIMIT) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    marker = f"\n... VVA_LOG_TRUNCATED original_chars={len(value)} ...\n"
    if len(marker) >= limit:
        return marker[:limit], True
    remaining = max(0, limit - len(marker))
    head = remaining // 2
    tail = remaining - head
    suffix = value[-tail:] if tail else ""
    return value[:head] + marker + suffix, True


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


class CommandRunner:
    """Run a predetermined argv with bounded output, cwd, and timeout."""

    def __init__(self, log_limit: int = DEFAULT_LOG_LIMIT) -> None:
        self.log_limit = log_limit

    def run(self, argv: Sequence[str], *, cwd: Path, timeout_seconds: float) -> CommandResult:
        started = time.monotonic()
        command = tuple(str(part) for part in argv)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            stdout, stdout_truncated = truncate_log(completed.stdout, self.log_limit)
            stderr, stderr_truncated = truncate_log(completed.stderr, self.log_limit)
            return CommandResult(
                argv=command,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.monotonic() - started,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, stdout_truncated = truncate_log(
                _timeout_text(exc.stdout), self.log_limit
            )
            stderr, stderr_truncated = truncate_log(
                _timeout_text(exc.stderr), self.log_limit
            )
            return CommandResult(
                argv=command,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.monotonic() - started,
                timed_out=True,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
            )
        except OSError as exc:
            return CommandResult(
                argv=command,
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=time.monotonic() - started,
                launch_error=f"{type(exc).__name__}: {exc}",
            )


class Simulator:
    def __init__(
        self,
        *,
        iverilog: str | None = None,
        vvp: str | None = None,
        compile_timeout_seconds: float = 20.0,
        simulation_timeout_seconds: float = 10.0,
        runner: CommandRunner | None = None,
    ) -> None:
        iverilog_candidate = iverilog or os.environ.get("VVA_IVERILOG") or "iverilog"
        vvp_candidate = vvp or os.environ.get("VVA_VVP") or "vvp"
        self.iverilog = shutil.which(iverilog_candidate)
        self.vvp = shutil.which(vvp_candidate)
        self.compile_timeout_seconds = compile_timeout_seconds
        self.simulation_timeout_seconds = simulation_timeout_seconds
        self.runner = runner or CommandRunner()

    @property
    def available(self) -> bool:
        return self.iverilog is not None and self.vvp is not None

    def ensure_available(self) -> None:
        missing: list[str] = []
        if self.iverilog is None:
            missing.append("iverilog")
        if self.vvp is None:
            missing.append("vvp")
        if missing:
            raise InfrastructureError(
                f"required executable(s) not found on PATH: {', '.join(missing)}"
            )

    def tool_versions(self, cwd: Path) -> dict[str, str | None]:
        result: dict[str, str | None] = {
            "iverilog_path": self.iverilog,
            "iverilog_version": None,
            "vvp_path": self.vvp,
            "vvp_version": None,
        }
        for name, executable in (("iverilog", self.iverilog), ("vvp", self.vvp)):
            if executable is None:
                continue
            command_result = self.runner.run(
                [executable, "-V"], cwd=cwd, timeout_seconds=5.0
            )
            combined = "\n".join(
                value for value in (command_result.stdout, command_result.stderr) if value
            )
            first_line = next((line.strip() for line in combined.splitlines() if line.strip()), "")
            result[f"{name}_version"] = first_line or "version output unavailable"
        return result

    def compile(
        self, dut_path: Path, testbench_path: Path, *, workdir: Path, attempt: int
    ) -> tuple[CommandResult, Path]:
        self.ensure_available()
        artifact = workdir / f"simulation_attempt_{attempt:02d}.vvp"
        argv = [
            str(self.iverilog),
            "-g2012",
            "-Wall",
            "-s",
            "tb",
            "-o",
            artifact.name,
            dut_path.name,
            testbench_path.name,
        ]
        return (
            self.runner.run(
                argv, cwd=workdir, timeout_seconds=self.compile_timeout_seconds
            ),
            artifact,
        )

    def run(self, artifact: Path, *, workdir: Path) -> CommandResult:
        self.ensure_available()
        return self.runner.run(
            [str(self.vvp), artifact.name],
            cwd=workdir,
            timeout_seconds=self.simulation_timeout_seconds,
        )
