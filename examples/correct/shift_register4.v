module shift_register4(
  input wire clk,
  input wire reset,
  input wire enable,
  input wire serial_in,
  output reg [3:0] q
);
  always @(posedge clk) begin
    if (reset)
      q <= 4'h0;
    else if (enable)
      q <= {q[2:0], serial_in};
  end
endmodule
