from __future__ import annotations

from importlib.metadata import version

import verilog_agent


def test_package_version_comes_from_distribution_metadata() -> None:
    assert verilog_agent.__version__ == version("verilog-verification-agent")
    assert verilog_agent.__version__ == "0.1.0a1"
