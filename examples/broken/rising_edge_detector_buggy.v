module rising_edge_detector(
  input wire clk,
  input wire reset,
  input wire signal_in,
  output reg pulse
);
  always @(posedge clk) begin
    if (reset)
      pulse <= 1'b0;
    else
      pulse <= signal_in;
  end
endmodule
