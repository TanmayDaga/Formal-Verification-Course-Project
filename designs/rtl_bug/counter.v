module counter (
    input wire clk,
    input wire rst,
    input wire en,
    output reg [3:0] count
);

    always @(posedge clk) begin
        if (rst) begin
            count <= 4'd0;
        end else if (en) begin
            // Injected bug: wraps to 0 instead of saturating at 15
            count <= count + 4'd1;
        end
    end

endmodule
