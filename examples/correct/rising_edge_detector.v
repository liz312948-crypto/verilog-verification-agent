module rising_edge_detector(
  input wire clk,
  input wire reset,
  input wire signal_in,
  output reg pulse
);
  reg previous;
  always @(posedge clk) begin
    if (reset) begin
      previous <= 1'b0;
      pulse <= 1'b0;
    end else begin
      pulse <= signal_in & ~previous;
      previous <= signal_in;
    end
  end
endmodule
