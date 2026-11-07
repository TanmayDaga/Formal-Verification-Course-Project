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
            if (count != 4'd15) begin
                count <= count + 4'd1;
            end
        end
    end

endmodule
