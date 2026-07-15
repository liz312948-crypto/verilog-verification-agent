from __future__ import annotations

import sys
from pathlib import Path

from verilog_agent.simulator import CommandRunner, truncate_log


def test_log_truncation_keeps_head_tail_and_marker() -> None:
    value = "A" * 100 + "B" * 100
    truncated, changed = truncate_log(value, 100)
    assert changed
    assert len(truncated) <= 100
    assert truncated.startswith("A")
    assert truncated.endswith("B")
    assert "VVA_LOG_TRUNCATED" in truncated


def test_command_runner_captures_stdout_stderr_and_exit_code(tmp_path: Path) -> None:
    result = CommandRunner().run(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)",
        ],
        cwd=tmp_path,
        timeout_seconds=2,
    )
    assert result.exit_code == 7
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"
    assert not result.timed_out


def test_command_runner_terminates_timeout(tmp_path: Path) -> None:
    result = CommandRunner().run(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout_seconds=0.1,
    )
    assert result.timed_out
    assert result.exit_code is None
    assert result.duration_seconds < 2
