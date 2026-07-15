"""Command-line entry point for doctor, generation, and repair."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from verilog_agent.errors import (
    ModelClientError,
    SpecValidationError,
    WorkspaceError,
)
from verilog_agent.loop import VerificationLoop
from verilog_agent.model_client import ModelClient, OpenAIModelClient, ScriptedModelClient
from verilog_agent.models import FinalStatus
from verilog_agent.simulator import Simulator
from verilog_agent.spec import Mode, load_spec
from verilog_agent.workspace import read_bounded_rtl, resolve_repository_path

EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_INVALID_INPUT = 2
EXIT_INFRASTRUCTURE = 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verilog-agent",
        description="Bounded Verilog DUT generation and repair verification harness",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="inspect Python, Icarus, and optional LLM setup")

    generate = subparsers.add_parser("generate", help="generate and verify a DUT")
    generate.add_argument("--spec", required=True, help="repository-relative JSON spec")
    generate.add_argument("--output", required=True, help="new repository-relative run directory")
    generate.add_argument(
        "--scripted-response",
        action="append",
        default=[],
        metavar="RTL_FILE",
        help="use deterministic response file(s), in call order, instead of a live model",
    )

    repair = subparsers.add_parser("repair", help="repair and verify an existing DUT")
    repair.add_argument("--spec", required=True, help="repository-relative JSON repair spec")
    repair.add_argument("--rtl", required=True, help="repository-relative existing DUT")
    repair.add_argument("--output", required=True, help="new repository-relative run directory")
    repair.add_argument(
        "--scripted-response",
        action="append",
        default=[],
        metavar="RTL_FILE",
        help="use deterministic repair response file(s), in call order",
    )
    return parser


def doctor(repository_root: Path) -> int:
    simulator = Simulator()
    versions = simulator.tool_versions(repository_root)
    info = {
        "python_version": sys.version.split()[0],
        **versions,
        "openai_dependency_installed": importlib.util.find_spec("openai") is not None,
        "openai_api_key_set": bool(os.environ.get("OPENAI_API_KEY")),
        "openai_model_set": bool(os.environ.get("OPENAI_MODEL")),
        "ready": sys.version_info >= (3, 11) and simulator.available,
    }
    print(json.dumps(info, indent=2, sort_keys=True))
    return EXIT_SUCCESS if info["ready"] else EXIT_INFRASTRUCTURE


def _model_client(repository_root: Path, response_paths: list[str]) -> ModelClient:
    if response_paths:
        responses = [
            read_bounded_rtl(
                resolve_repository_path(repository_root, path, must_exist=True)
            )
            for path in response_paths
        ]
        return ScriptedModelClient(responses)
    return OpenAIModelClient.from_environment()


def _run(args: argparse.Namespace, repository_root: Path) -> int:
    expected_mode = Mode.GENERATE if args.command == "generate" else Mode.REPAIR
    rtl_override = args.rtl if args.command == "repair" else None
    spec = load_spec(
        args.spec,
        repository_root,
        expected_mode=expected_mode,
        rtl_override=rtl_override,
    )
    client = _model_client(repository_root, args.scripted_response)
    loop = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
    )
    report = loop.run(spec, args.output)
    print(
        json.dumps(
            {
                "status": report.final_status.value,
                "attempts": report.total_attempts,
                "report": str((repository_root / args.output / "report.json").resolve()),
            },
            sort_keys=True,
        )
    )
    if report.final_status is FinalStatus.PASSED:
        return EXIT_SUCCESS
    if report.final_status is FinalStatus.INFRASTRUCTURE_ERROR:
        return EXIT_INFRASTRUCTURE
    return EXIT_VERIFICATION_FAILED


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository_root = Path.cwd().resolve()
    if args.command == "doctor":
        return doctor(repository_root)
    try:
        return _run(args, repository_root)
    except (SpecValidationError, WorkspaceError) as exc:
        print(f"INVALID_SPEC: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except ModelClientError as exc:
        print(f"INFRASTRUCTURE_ERROR: {exc}", file=sys.stderr)
        return EXIT_INFRASTRUCTURE
