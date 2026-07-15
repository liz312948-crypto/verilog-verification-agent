"""Deterministic, trusted testbench generation for the seven supported circuits."""

from __future__ import annotations

from textwrap import dedent

from verilog_agent.spec import CircuitKind, TaskSpec

PASS_SENTINEL = "VVA_VERIFICATION_PASS"
FAIL_SENTINEL = "VVA_VERIFICATION_FAIL"


def _render(template: str, module_name: str) -> str:
    return dedent(template).replace("__MODULE__", module_name).lstrip()


def _mux2(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg a, b, sel;
          wire y;
          integer ai, bi, si;
          __MODULE__ dut (.a(a), .b(b), .sel(sel), .y(y));

          initial begin
            for (si = 0; si < 2; si = si + 1)
              for (ai = 0; ai < 2; ai = ai + 1)
                for (bi = 0; bi < 2; bi = bi + 1) begin
                  sel = si; a = ai; b = bi; #1;
                  if (y !== (sel ? b : a)) begin
                    $display("VVA_VERIFICATION_FAIL vector=mux_%0d%0d%0d expected=%0d actual=%0d",
                             si, ai, bi, (sel ? b : a), y);
                    $fatal(1);
                  end
                end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


def _adder4(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg [3:0] a, b;
          reg cin;
          wire [3:0] sum;
          wire cout;
          reg [4:0] expected;
          integer ai, bi, ci;
          __MODULE__ dut (.a(a), .b(b), .cin(cin), .sum(sum), .cout(cout));

          initial begin
            for (ai = 0; ai < 16; ai = ai + 1)
              for (bi = 0; bi < 16; bi = bi + 1)
                for (ci = 0; ci < 2; ci = ci + 1) begin
                  a = ai; b = bi; cin = ci; expected = ai + bi + ci; #1;
                  if ({cout, sum} !== expected) begin
                    $display("VVA_VERIFICATION_FAIL vector=add_%0d_%0d_%0d expected=%0h actual=%0h",
                             ai, bi, ci, expected, {cout, sum});
                    $fatal(1);
                  end
                end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


def _counter4(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg clk = 0;
          reg reset = 0;
          reg enable = 0;
          wire [3:0] count;
          reg [3:0] expected;
          integer vector;
          __MODULE__ dut (.clk(clk), .reset(reset), .enable(enable), .count(count));
          always #5 clk = ~clk;

          task check_count;
            input [3:0] wanted;
            begin
              #1;
              if (count !== wanted) begin
                $display("VVA_VERIFICATION_FAIL vector=counter_%0d expected=%0h actual=%0h",
                         vector, wanted, count);
                $fatal(1);
              end
            end
          endtask

          initial begin
            vector = 0;
            @(negedge clk); reset = 1; enable = 0;
            @(posedge clk); check_count(4'h0);
            @(negedge clk); reset = 0; enable = 0; vector = vector + 1;
            @(posedge clk); check_count(4'h0);
            expected = 0;
            repeat (18) begin
              @(negedge clk); enable = 1; vector = vector + 1;
              expected = expected + 1'b1;
              @(posedge clk); check_count(expected);
            end
            @(negedge clk); enable = 0; vector = vector + 1;
            @(posedge clk); check_count(expected);
            @(negedge clk); reset = 1; enable = 1; vector = vector + 1;
            @(posedge clk); check_count(4'h0);
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


def _shift_register4(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg clk = 0;
          reg reset = 0;
          reg enable = 0;
          reg serial_in = 0;
          wire [3:0] q;
          integer vector = 0;
          __MODULE__ dut (
            .clk(clk), .reset(reset), .enable(enable), .serial_in(serial_in), .q(q)
          );
          always #5 clk = ~clk;

          task step;
            input en;
            input bit_in;
            input [3:0] wanted;
            begin
              @(negedge clk); enable = en; serial_in = bit_in; vector = vector + 1;
              @(posedge clk); #1;
              if (q !== wanted) begin
                $display("VVA_VERIFICATION_FAIL vector=shift_%0d expected=%0h actual=%0h",
                         vector, wanted, q);
                $fatal(1);
              end
            end
          endtask

          initial begin
            @(negedge clk); reset = 1;
            @(posedge clk); #1;
            if (q !== 4'h0) begin
              $display("VVA_VERIFICATION_FAIL vector=shift_reset expected=0 actual=%0h", q);
              $fatal(1);
            end
            @(negedge clk); reset = 0;
            step(1, 1, 4'b0001);
            step(1, 0, 4'b0010);
            step(1, 1, 4'b0101);
            step(0, 0, 4'b0101);
            step(1, 1, 4'b1011);
            step(1, 0, 4'b0110);
            step(1, 0, 4'b1100);
            step(1, 1, 4'b1001);
            @(negedge clk); reset = 1; enable = 1;
            @(posedge clk); #1;
            if (q !== 4'h0) begin
              $display("VVA_VERIFICATION_FAIL vector=shift_reset2 expected=0 actual=%0h", q);
              $fatal(1);
            end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


def _rising_edge_detector(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg clk = 0;
          reg reset = 0;
          reg signal_in = 0;
          wire pulse;
          integer vector = 0;
          __MODULE__ dut (.clk(clk), .reset(reset), .signal_in(signal_in), .pulse(pulse));
          always #5 clk = ~clk;

          task step;
            input value;
            input wanted;
            begin
              @(negedge clk); signal_in = value; vector = vector + 1;
              @(posedge clk); #1;
              if (pulse !== wanted) begin
                $display("VVA_VERIFICATION_FAIL vector=edge_%0d expected=%0d actual=%0d",
                         vector, wanted, pulse);
                $fatal(1);
              end
            end
          endtask

          initial begin
            @(negedge clk); reset = 1; signal_in = 0;
            @(posedge clk); #1;
            if (pulse !== 0) begin
              $display("VVA_VERIFICATION_FAIL vector=edge_reset expected=0 actual=%0d", pulse);
              $fatal(1);
            end
            @(negedge clk); reset = 0;
            step(0, 0);
            step(1, 1);
            step(1, 0);
            step(0, 0);
            step(1, 1);
            step(0, 0);
            step(0, 0);
            step(1, 1);
            @(negedge clk); reset = 1; signal_in = 1;
            @(posedge clk); #1;
            if (pulse !== 0) begin
              $display("VVA_VERIFICATION_FAIL vector=edge_reset2 expected=0 actual=%0d", pulse);
              $fatal(1);
            end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


def _sequence_vectors() -> str:
    bits = "0010110101101011011"
    history = ""
    lines: list[str] = []
    for index, bit in enumerate(bits, start=1):
        history = (history + bit)[-4:]
        expected = int(history == "1011")
        lines.append(f"    step(1'b{bit}, 1'b{expected}, {index});")
    return "\n".join(lines)


def _sequence_detector_1011(module_name: str) -> str:
    template = """
        module tb;
          reg clk = 0;
          reg reset = 0;
          reg serial_in = 0;
          wire detected;
          __MODULE__ dut (
            .clk(clk), .reset(reset), .serial_in(serial_in), .detected(detected)
          );
          always #5 clk = ~clk;

          task step;
            input value;
            input wanted;
            input integer vector;
            begin
              @(negedge clk); serial_in = value;
              @(posedge clk); #1;
              if (detected !== wanted) begin
                $display("VVA_VERIFICATION_FAIL vector=seq_%0d expected=%0d actual=%0d",
                         vector, wanted, detected);
                $fatal(1);
              end
            end
          endtask

          initial begin
            @(negedge clk); reset = 1; serial_in = 0;
            @(posedge clk); #1;
            if (detected !== 0) begin
              $display("VVA_VERIFICATION_FAIL vector=seq_reset expected=0 actual=%0d", detected);
              $fatal(1);
            end
            @(negedge clk); reset = 0;
        __VECTORS__
            @(negedge clk); reset = 1;
            @(posedge clk); #1;
            if (detected !== 0) begin
              $display("VVA_VERIFICATION_FAIL vector=seq_reset2 expected=0 actual=%0d", detected);
              $fatal(1);
            end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
    """
    return _render(template.replace("__VECTORS__", _sequence_vectors()), module_name)


def _alu4(module_name: str) -> str:
    return _render(
        """
        module tb;
          reg [3:0] a, b;
          reg [2:0] op;
          wire [3:0] result;
          wire carry, zero;
          reg [3:0] expected_result;
          reg expected_carry, expected_zero;
          reg [4:0] extended;
          integer ai, bi, oi;
          __MODULE__ dut (
            .a(a), .b(b), .op(op), .result(result), .carry(carry), .zero(zero)
          );

          task check;
            begin
              extended = 0;
              expected_result = 0;
              expected_carry = 0;
              case (oi)
                0: begin
                  extended = ai + bi;
                  expected_result = extended[3:0];
                  expected_carry = extended[4];
                end
                1: begin
                  expected_result = ai - bi;
                  expected_carry = (ai >= bi);
                end
                2: expected_result = ai & bi;
                3: expected_result = ai | bi;
                4: expected_result = ai ^ bi;
                default: begin expected_result = 0; expected_carry = 0; end
              endcase
              expected_zero = (expected_result == 0);
              #1;
              if ((result !== expected_result) || (carry !== expected_carry) ||
                  (zero !== expected_zero)) begin
                $display("VVA_VERIFICATION_FAIL vector=alu_%0d_%0d_%0d", ai, bi, oi);
                $display("expected=%0h/%0d/%0d actual=%0h/%0d/%0d",
                         expected_result, expected_carry, expected_zero, result, carry, zero);
                $fatal(1);
              end
            end
          endtask

          initial begin
            for (oi = 0; oi < 8; oi = oi + 1)
              for (ai = 0; ai < 16; ai = ai + 1)
                for (bi = 0; bi < 16; bi = bi + 1) begin
                  op = oi; a = ai; b = bi; check;
                end
            $display("VVA_VERIFICATION_PASS");
            $finish;
          end
        endmodule
        """,
        module_name,
    )


GENERATORS = {
    CircuitKind.MUX2: _mux2,
    CircuitKind.ADDER4: _adder4,
    CircuitKind.COUNTER4: _counter4,
    CircuitKind.SHIFT_REGISTER4: _shift_register4,
    CircuitKind.RISING_EDGE_DETECTOR: _rising_edge_detector,
    CircuitKind.SEQUENCE_DETECTOR_1011: _sequence_detector_1011,
    CircuitKind.ALU4: _alu4,
}


def generate_testbench(spec: TaskSpec) -> str:
    """Generate the trusted oracle without consulting a model."""
    return GENERATORS[spec.circuit_kind](spec.module_name)
