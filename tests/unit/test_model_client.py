from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tests.conftest import build_spec
from verilog_agent.errors import InvalidModelOutputError, ModelClientError
from verilog_agent.model_client import (
    MAX_MODEL_OUTPUT_CHARS,
    OpenAIModelClient,
    ScriptedModelClient,
    clean_and_validate_model_output,
)
from verilog_agent.models import Diagnostic, DiagnosticKind
from verilog_agent.spec import CircuitKind

VALID_MUX = "module mux2(input a, input b, input sel, output y); assign y=sel?b:a; endmodule"


def test_removes_single_markdown_fence() -> None:
    fence = chr(96) * 3
    raw = f"{fence}verilog\n{VALID_MUX}\n{fence}"
    assert clean_and_validate_model_output(raw, "mux2") == VALID_MUX + "\n"


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_accepts_exact_port_contract_for_all_supported_circuits(
    repository_root: Path, kind: CircuitKind
) -> None:
    spec = build_spec(kind)
    source = (repository_root / "examples" / "correct" / f"{kind.value}.v").read_text(
        encoding="utf-8"
    )
    assert (
        clean_and_validate_model_output(source, spec.module_name, spec.port_contract)
        == source.strip() + "\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        "module mux2(input a, input b, input sel, input extra, output y); "
        "assign y=sel?b:a; endmodule",
        "module mux2(input [1:0] a, input b, input sel, output y); "
        "assign y=sel?b:a[0]; endmodule",
        "module mux2(output a, input b, input sel, output y); "
        "assign y=sel?b:a; endmodule",
    ],
)
def test_rejects_incorrect_port_contract(source: str) -> None:
    spec = build_spec()
    with pytest.raises(InvalidModelOutputError, match="port contract"):
        clean_and_validate_model_output(source, spec.module_name, spec.port_contract)


@pytest.mark.parametrize(
    "raw, message",
    [
        ("module other; endmodule", "expected"),
        ("module mux2; endmodule module extra; endmodule", "exactly one"),
        ("module mux2; initial $system(\"x\"); endmodule", "forbidden"),
        ("module mux2; initial $finish; endmodule", "forbidden"),
        (
            "module mux2; initial $display(\"VVA_VERIFICATION_PASS\"); endmodule",
            "forbidden",
        ),
        ("module mux2; initial begin end endmodule", "forbidden"),
        ("module mux2; wire x = tb.some_signal; endmodule", "forbidden"),
        ("module mux2; initial $dumpfile(\"outside.vcd\"); endmodule", "forbidden"),
        ("", "empty"),
    ],
)
def test_rejects_invalid_model_output(raw: str, message: str) -> None:
    with pytest.raises(InvalidModelOutputError, match=message):
        clean_and_validate_model_output(raw, "mux2")


def test_rejects_oversized_model_output() -> None:
    with pytest.raises(InvalidModelOutputError, match="exceeds"):
        clean_and_validate_model_output("x" * (MAX_MODEL_OUTPUT_CHARS + 1), "mux2")


def test_scripted_client_returns_responses_in_order() -> None:
    client = ScriptedModelClient(["first", "second"])
    spec = build_spec()
    diagnostic = Diagnostic(
        kind=DiagnosticKind.COMPILE_ERROR,
        message="bad",
        attempt=1,
    )
    assert client.generate_rtl(spec) == "first"
    assert client.repair_rtl(spec, "rtl", diagnostic, 1, 2) == "second"
    with pytest.raises(ModelClientError, match="no response"):
        client.generate_rtl(spec)


def test_openai_client_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(ModelClientError, match="OPENAI_API_KEY"):
        OpenAIModelClient()


def test_api_key_is_redacted_from_repr_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "sk-test-super-secret"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("OPENAI_MODEL", "configured-at-runtime")
    client = OpenAIModelClient()
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("test").debug("client=%r", client)
    assert secret not in repr(client)
    assert secret not in caplog.text
    assert "<redacted>" in repr(client)
