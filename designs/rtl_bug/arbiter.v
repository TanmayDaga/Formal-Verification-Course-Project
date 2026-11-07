module arbiter (
    input wire clk,
    input wire rst,
    input wire req0,
    input wire req1,
    output reg gnt0,
    output reg gnt1
);

    always @(posedge clk) begin
        if (rst) begin
            gnt0 <= 1'b0;
            gnt1 <= 1'b0;
        end else begin
            // Injected bug: priority removed, both can be granted simultaneously
            gnt0 <= req0;
            gnt1 <= req1;
        end
    end

endmodule
