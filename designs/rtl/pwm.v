module pwm (
    input wire clk,
    input wire rst,
    input wire [7:0] duty,
    output wire out
);

    reg [7:0] cnt;

    always @(posedge clk) begin
        if (rst) begin
            cnt <= 8'd0;
        end else begin
            cnt <= cnt + 8'd1;
        end
    end

    assign out = (cnt < duty);

endmodule
