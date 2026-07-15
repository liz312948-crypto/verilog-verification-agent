module adder4(
  input wire [3:0] a,
  input wire [3:0] b,
  input wire cin,
  output wire [3:0] sum,
  output wire cout
);
  assign sum = a + b + cin;
  assign cout = 1'b0;
endmodule
