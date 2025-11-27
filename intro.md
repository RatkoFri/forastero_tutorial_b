# Introduction to Transactional Testbench 


The growing complexity of digital designs has made traditional testbenches increasingly inadequate for thorough verification. Transactional testbenches have emerged as a powerful solution to address these challenges by enabling higher-level abstractions and more efficient testing methodologies.

## What is a Transactional Testbench?

A transactional testbench is a TB that uses transactions as the primary means of communication between the testbench components and the design under test (DUT). Instead of dealing with low-level signal manipulations, transactional testbenches operate at a higher level of abstraction, allowing for more intuitive and efficient verification processes.

Traditional Testbench vs. Transactional Testbench:

| Aspect                     | Traditional Testbench               | Transactional Testbench            |
|----------------------------|------------------------------------|-----------------------------------|
| Level of Abstraction       | Low-level signal manipulation      | High-level transactions           |
| Communication Method       | Direct signal driving and monitoring| Transaction-based communication   |
| Reusability                | Limited                           | High                              |
| Complexity Handling       | Difficult for complex designs      | Easier with modular transactions  |  

## Transactions as primitive

Transaction is a high-level exchange of information between components in a testbench. It encapsulates the data and control information needed to perform a specific operation on the DUT. Transactions can represent various operations, such as read/write requests, data transfers, or protocol-specific commands.

Transaction item is the basic unit of a transaction. Nothing more than a data packet that consists of data or instruction to be sent to the DUT or received from it. Transaction items can be simple (e.g., a single data word) or complex (e.g., a structured packet with multiple fields).

For UART receive operation, a transaction item might include fields such as:

```systemverilog
uart_tx_tr tr = new();
tr.data      = 8'h41;
tr.parity    = NONE;
tr.stop_bits = 1;
tr.baud      = 115200;
tr.start_bit = 1;
```

As you can see it, the transaction item encapsulates all the necessary information for a UART transmission in a single object.

## Key components of a Transactional Testbench

### Transaction Generators: 
These components create transactions items, which are used to drive DUT (desing under test) inputs. 

```systemverilog
uart_tx_tr tr = list of uart_tx_tr::type::new[10];
for (int i = 0; i < tr.size(); i++) begin
    tr[i].data      = $urandom_range(0, 255);
    tr[i].parity    = NONE;
    tr[i].stop_bits = 1;
    tr[i].baud      = 115200;
end
send_transactions_to_driver(tr);
```

### **Drivers**: 

Drivers take transaction items from the generators and convert them into low-level signal manipulations to interact with the DUT.

```systemverilog
virtual task drive_transaction(uart_tx_tr tr);
    // Convert transaction item to signal-level operations
    @(posedge clk);
    tx_line <= 0; // Start bit
    // Send data bits
    for (int i = 0; i < 8; i++) begin
        tx_line <= tr.data[i];
        @(posedge clk);
    end
    if (tr.parity != NONE) begin
        // Send parity bit
        tx_line <= calculate_parity(tr.data, tr.parity);
        @(posedge clk);
    end
    // Stop bit
    tx_line <= 1;
    @(posedge clk);
endtask
``` 

The previous code snippet demonstrates how a driver might convert a UART transaction item into signal-level operations to transmit data. 

### **Interface**:

Collection or group of signals that connect the DUT to the testbench components. It provides a standardized way to communicate between the DUT and the testbench.

In our UART example, the input interface includes signals such as `rx_line`, `clk`, and `reset`, while the output interface includes signals like `data_out` and `data_valid`.

Another example dual-port RAM interface:
    - interface A
    - interface B

```systemverilog
module #(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 8
) sync_dual_port_RAM (

    input logic clock,
    // interface A 
    input logic [ADDR_WIDTH-1:0] addr_a,
    input logic [DATA_WIDTH-1:0] datain_a,
    input logic we_a,
    output logic [DATA_WIDTH-1:0] dataout_a,

    // interface B
    input logic [ADDR_WIDTH-1:0] addr_b,
    input logic [DATA_WIDTH-1:0] datain_b,
    input logic we_b,
    output logic [DATA_WIDTH-1:0] dataout_b
);
```

### **Monitors**:

Monitors observe the DUT outputs and convert low-level signal changes back into transaction items for analysis.

```systemverilog
uart_rec_tr tr = new();
tr.data_rec     = 8'h41;

virtual task monitor_transaction();
    // Observe signal-level operations and convert to transaction item
    @(posedge clk);
    if (data_valid) begin
        tr.data_rec = data_out;
    end
    else begin
        tr.data_rec = 'X;
    end
endtask
```

### Scoreboard 

The scoreboard is responsible for comparing the expected transaction items with the actual transaction items observed by the monitors. It helps in determining whether the DUT behaves as expected.


> Inspired by: https://itsembedded.com/dhd/verilator_4/



