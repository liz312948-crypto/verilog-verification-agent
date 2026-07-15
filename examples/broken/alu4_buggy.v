module alu4(
  input wire [3:0] a,
  input wire [3:0] b,
  input wire [2:0] op,
  output reg [3:0] result,
  output reg carry,
  output wire zero
);
  reg [4:0] extended;
  always @* begin
    result = 4'h0;
    carry = 1'b0;
    extended = 5'h00;
    case (op)
      3'b000: begin
        extended = {1'b0, a} + {1'b0, b};
        result = extended[3:0];
        carry = extended[4];
      end
      3'b001: begin
        result = a + b;
        carry = 1'b0;
      end
      3'b010: result = a & b;
      3'b011: result = a | b;
      3'b100: result = a ^ b;
      default: begin result = 4'h0; carry = 1'b0; end
    endcase
  end
  assign zero = (result == 4'h0);
endmodule
