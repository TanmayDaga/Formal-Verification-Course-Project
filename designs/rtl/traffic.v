module traffic (
    input wire clk,
    input wire rst,
    output reg [1:0] state,
    output wire red,
    output wire green,
    output wire yellow
);

    localparam RED    = 2'd0;
    localparam GREEN  = 2'd1;
    localparam YELLOW = 2'd2;

    reg [1:0] timer;

    assign red    = (state == RED);
    assign green  = (state == GREEN);
    assign yellow = (state == YELLOW);

    always @(posedge clk) begin
        if (rst) begin
            state <= RED;
            timer <= 2'd0;
        end else begin
            if (timer == 2'd3) begin
                timer <= 2'd0;
                case (state)
                    RED:    state <= GREEN;
                    GREEN:  state <= YELLOW;
                    YELLOW: state <= RED;
                    default: state <= RED;
                endcase
            end else begin
                timer <= timer + 2'd1;
            end
        end
    end

endmodule
