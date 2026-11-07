module fifo (
    input wire clk,
    input wire rst,
    input wire wr_en,
    input wire rd_en,
    input wire [7:0] din,
    output wire [7:0] dout,
    output wire full,
    output wire empty,
    output reg [2:0] cnt
);

    reg [7:0] mem [0:3];
    reg [1:0] wr_ptr;
    reg [1:0] rd_ptr;

    assign full  = (cnt >= 3'd4);
    assign empty = (cnt == 3'd0);
    assign dout  = mem[rd_ptr];

    // Injected bug: accepts writes even when full
    wire wr_valid = wr_en;
    wire rd_valid = rd_en && !empty;

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 2'd0;
            rd_ptr <= 2'd0;
            cnt    <= 3'd0;
            mem[0] <= 8'd0;
            mem[1] <= 8'd0;
            mem[2] <= 8'd0;
            mem[3] <= 8'd0;
        end else begin
            if (wr_valid) begin
                mem[wr_ptr] <= din;
                wr_ptr      <= wr_ptr + 2'd1;
            end
            if (rd_valid) begin
                rd_ptr <= rd_ptr + 2'd1;
            end
            case ({wr_valid, rd_valid})
                2'b10:   cnt <= cnt + 3'd1;
                2'b01:   cnt <= cnt - 3'd1;
                default: cnt <= cnt;
            endcase
        end
    end

endmodule
