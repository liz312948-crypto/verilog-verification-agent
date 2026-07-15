module adder4(
  input wire [3:0] a,
  input wire [3:0] b,
  input wire cin,
  output wire [3:0] sum,
  output wire cout
);
  wire [4:0] extended;
  assign extended = {1'b0, a} + {1'b0, b} + cin;
  assign {cout, sum} = extended;
endmodule
