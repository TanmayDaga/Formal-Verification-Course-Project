module shift_reg (
    input wire clk,
    input wire rst,
    input wire load,
    input wire shift_en,
    input wire [7:0] din,
    input wire serial_in,
    output reg [7:0] q
);

    always @(posedge clk) begin
        if (rst) begin
            q <= 8'd0;
        end else if (load) begin
            q <= din;
        end else if (shift_en) begin
            q <= {q[6:0], serial_in};
        end
    end

endmodule
