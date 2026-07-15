module sequence_detector_1011(
  input wire clk,
  input wire reset,
  input wire serial_in,
  output reg detected
);
  localparam S0 = 2'd0, S1 = 2'd1, S10 = 2'd2, S101 = 2'd3;
  reg [1:0] state;
  reg [1:0] next_state;

  always @* begin
    case (state)
      S0: next_state = serial_in ? S1 : S0;
      S1: next_state = serial_in ? S1 : S10;
      S10: next_state = serial_in ? S101 : S0;
      S101: next_state = serial_in ? S0 : S10;
      default: next_state = S0;
    endcase
  end

  always @(posedge clk) begin
    if (reset) begin
      state <= S0;
      detected <= 1'b0;
    end else begin
      detected <= (state == S101) && serial_in;
      state <= next_state;
    end
  end
endmodule
