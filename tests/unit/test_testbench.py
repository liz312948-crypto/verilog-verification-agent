from __future__ import annotations

import pytest

from tests.conftest import build_spec
from verilog_agent.spec import CircuitKind
from verilog_agent.testbench import generate_testbench


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_every_circuit_has_a_deterministic_trusted_testbench(kind: CircuitKind) -> None:
    spec = build_spec(kind)
    first = generate_testbench(spec)
    second = generate_testbench(spec)
    assert first == second
    assert "module tb;" in first
    assert f"{kind.value} dut" in first
    assert first.count("VVA_VERIFICATION_PASS") == 1
    assert "VVA_VERIFICATION_FAIL" in first
    assert "$fatal(1)" in first


def test_sequence_testbench_contains_hit_and_overlap_vectors() -> None:
    source = generate_testbench(build_spec(CircuitKind.SEQUENCE_DETECTOR_1011))
    assert "step(1'b1, 1'b1" in source
    assert source.count("step(") >= 19


def test_alu_testbench_documents_no_borrow_oracle_in_logic() -> None:
    source = generate_testbench(build_spec(CircuitKind.ALU4))
    assert "expected_carry = (ai >= bi)" in source
    assert "oi < 8" in source
