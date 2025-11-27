# Transcational TB in Forastero

Forastero is a lightweight library that helps you write structured, maintainable testbenches on top of cocotb. It takes inspiration from the Unified Verification Methodology (UVM) but includes only the most practical and essential concepts—things like drivers, monitors, transactions, and scoreboards—without the heavy framework overhead.


## Tested module 

For this example, we will test a simple arbiter module that takes two request inputs and grants access to one of them based on a simple priority scheme.

The arbiters are essential components in System on Chip (SoC) designs, managing access to shared resources (slaves) among multiple requesters (master).


### Interface:
```verilog
module arbiter (
      input  logic        i_clk
    , input  logic        i_rst
    // A
    , input  logic [31:0] i_a_data
    , input  logic        i_a_valid
    , output logic        o_a_ready
    // B
    , input  logic [31:0] i_b_data
    , input  logic        i_b_valid
    , output logic        o_b_ready
    // Arbitrated
    , output logic [31:0] o_x_data
    , output logic        o_x_valid
    , input  logic        i_x_ready
);
```
Two input ports (A and B) provide data along with valid signals and ready signals, while the arbiter outputs the selected data and its valid and ready signal.

### Arbitration Logic:

```verilog

// _d: next value to be output, _q: current value being output
logic [31:0] arb_data_d, arb_data_q; 
logic        arb_valid_d, arb_valid_q;
logic        arb_choice_d, arb_choice_q;

// DATA ARBITRATION LOGIC
assign arb_data_d  = (!arb_valid_q || i_x_ready)
                        ? ((arb_choice_d == 'd0) ? i_a_data : i_b_data)
                        : arb_data_q;

assign o_x_data  = arb_data_q;

// VALID SIGNAL GENERATION LOGIC
assign arb_valid_d = (arb_valid_q && !i_x_ready) ||
                     (arb_choice_d == 'd0 && i_a_valid) ||
                     (arb_choice_d == 'd1 && i_b_valid);

assign o_x_valid = arb_valid_q;

// CHOICE DETERMINATION LOGIC
assign arb_choice_d = (arb_valid_q && !i_x_ready) ? arb_choice_q :
                      (arb_choice_q             ) ? !i_a_valid
                                                  : i_b_valid;

// !i_a_valid because arb_choice_d == 0 means A is chosen

assign o_a_ready = (!arb_valid_q || i_x_ready) && (arb_choice_d == 'd0);
assign o_b_ready = (!arb_valid_q || i_x_ready) && (arb_choice_d == 'd1);


```

Logic to determine which input to grant based on the current state and incoming valid signals.

Explanation: 
- DATA ARBITRATION: if the arbiter is currently has no valid data (`arb_valid_q`)    or the connected slave is ready to accept new data (`i_x_ready`), it selects data from either input A or B based on the arbitration choice (`arb_choice_d`) -> 0 for A, 1 for B.
    - if not ready, it retains the current valid data (`arb_data_q`).
- VALID SIGNAL GENERATION: The arbiter's valid signal (`arb_valid_d`) is asserted if it currently has valid data that hasn't been accepted by the slave (`arb_valid_q && !i_x_ready`), or if the selected input (A or B) has valid data based on the arbitration choice.
- CHOICE DETERMINATION: The arbitration choice (`arb_choice_d`) is updated based on whether the arbiter is currently holding valid data that hasn't been accepted by the slave. If it is, it retains the current choice (`arb_choice_q`). If not, it selects the next input based on the current choice and the validity of the inputs.
- READY SIGNALS: The ready signals for inputs A and B (`o_a_ready` and `o_b_ready`) are asserted when the arbiter is either not holding valid data or the connected slave is ready to accept new data, and the arbitration choice matches the respective input.

```verilog
always_ff @(posedge i_clk, posedge i_rst) begin : ff_arb_choice
    if (i_rst) begin
        arb_choice_q <= 'd1;
    end else if (arb_valid_d) begin
        arb_choice_q <= arb_choice_d;
    end
end

always_ff @(posedge i_clk, posedge i_rst) begin : ff_arb_data
    if (i_rst) begin
        { arb_data_q, arb_valid_q } <= 'd0;
    end else begin
        { arb_data_q, arb_valid_q } <= { arb_data_d, arb_valid_d };
    end
end
```
Update flip-flops for arbitration choice, data, and valid signals on clock edges or reset.

```verilog
`ifdef sim_icarus
initial begin : i_trace
    string f_name;
    $timeformat(-9, 2, " ns", 20);
    if ($value$plusargs("WAVE_FILE=%s", f_name)) begin
        $display("%0t: Capturing wave file %s", $time, f_name);
        $dumpfile(f_name);
        $dumpvars(0, arbiter);
    end else begin
        $display("%0t: No filename provided - disabling wave capture", $time);
    end
end
`endif // sim_icarus

endmodule : arbiter
```

Lastly, a simple waveform dump for simulation purposes. Executed in simulation environments like Icarus Verilog.

