# Forastero part 2: Building the Componets of Testbench for an Arbiter


## Building the Interface

Let's recollect the interface of the arbiter module we are going to test:

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

Notice, that every interface has three main signals:
- Data signal (e.g., `i_a_data`, `i_b_data`, `o_x_data`)
- Valid signal (e.g., `i_a_valid`, `i_b_valid`, `o_x_valid`)
- Ready signal (e.g., `o_a_ready`, `o_b_ready`, `i_x_ready`)

Based on this interface, we can build the corresponding testbench interface.

```python
from collections.abc import Callable
from cocotb.handle import HierarchyObject

from forastero import BaseIO
from forastero.io import IORole


class StreamIO(BaseIO):
    def __init__(
        self,
        dut: HierarchyObject,
        name: str | None,
        role: IORole,
        io_style: Callable[[str | None, str, IORole, IORole], str] | None = None,
    ) -> None:
        super().__init__(
            dut=dut,
            name=name,
            role=role,
            init_sigs=["data", "valid"],
            resp_sigs=["ready"],
            io_style=io_style,
        )
```

- This `StreamIO` class defines the input/output interface for the arbiter module, encapsulating the data, valid, and ready signals.

- Arguments of the `__init__` method:
  - `dut`: HierarchyObject - The DUT instance from Cocotb.
  - `name`: str | None - The base name for the interface signals.
    - in our case, names like this 
  - `role`: IORole - Specifies the role of the interface 
    -  iniatior (role = IORole.INITIATOR) for x interface
    -  responder (role = IORole.RESPONDER) for a and b interfaces
  - `io_style`: Optional callable to customize signal naming conventions.
- Initialization of the base class `BaseIO` with the appropriate signals for data, valid, and ready.

### IO Naming Convention

- The default naming convention for the signals in the `StreamIO` class follows the pattern:
  - Data signal: `<direction>_<bus_name>_data`, where:
    - `<direction>` is `i` for input and `o` for output.
    - `<bus_name>` is the name provided during instantiation (e.g., `a`, `b`, `x`).
  - Valid signal: `<direction>_<bus_name>_valid`
  - Ready signal: `<direction>_<bus_name>_ready`
- When designing the design, ensure that the signal names in the DUT match this convention for seamless integration with the testbench interface.
  - otherewise, you can provide a custom `io_style` function to map the signal names accordingly.

## Transaction Items

The transaction items represent the data structures used to encapsulate the information exchanged between the testbench and the DUT.

```python
from dataclasses import dataclass

from forastero import BaseTransaction


@dataclass(kw_only=True)
class StreamTransaction(BaseTransaction):
    data: int = 0


@dataclass(kw_only=True)
class StreamBackpressure(BaseTransaction):
    ready: bool = True
    cycles: int = 1
```

We have defined two transaction items:
- `StreamTransaction`: Represents a data transaction with a single field `data` to hold the data value.
- `StreamBackpressure`: Represents backpressure control with fields `ready` (indicating if the interface is ready to accept data) and `cycles` (number of clock cycles to wait).


## Building the drivers

- Two types of drivers:
  - Responder driver
  - Initiator driver

- Initator drivers sends the data to the DUT

```python
from cocotb.triggers import RisingEdge
from forastero import BaseDriver
from .transaction import StreamTransaction

class StreamInitiator(BaseDriver):
    async def drive(self, obj: StreamTransaction) -> None:
        self.io.set("data", obj.data)
        self.io.set("valid", 1)
        while True:
            await RisingEdge(self.clk)
            if self.io.get("ready", 1):
                break
        self.io.set("valid", 0)
```

- the `StreamInitiator` class extends the `BaseDriver` class to implement the driving logic for the interface.
- The `drive` method takes a `StreamTransaction` object as input, which contains the data to be sent to the DUT.
- The method sets the data and valid signals on the interface, then waits for the ready signal from the DUT before de-asserting the valid signal.

> The async keyword marks this as a coroutine, meaning it can perform non-blocking operations and yield control back to the event loop. In hardware verification, this is essential because drivers need to wait for clock edges and signal changes without blocking other concurrent processes in the testbench.


- Responder drivers receive data from the DUT

```python
from cocotb.triggers import ClockCycles

from forastero.driver import BaseDriver

from .transaction import StreamBackpressure


class StreamResponder(BaseDriver):
    async def drive(self, obj: StreamBackpressure) -> None:
        self.io.set("ready", obj.ready)
        await ClockCycles(self.clk, obj.cycles)
```

- the `StreamResponder` class extends the `BaseDriver` class to implement the driving logic for the interface.
- The `drive` method takes a `StreamBackpressure` object as input, which contains the ready signal value and the number of clock cycles to wait.
- The method sets the ready signal on the interface and waits for the specified number of clock cycles.

### Generating sequences 

- sequences are used to generate a series of transaction items for the drivers to send to the DUT.

```python
@forastero.sequence()
@forastero.requires("stream", StreamInitiator)
@forastero.randarg("length", range=(100, 1000))
async def stream_traffic_seq(ctx: SeqContext, stream: StreamInitiator, length: int):
    """
    Generates random traffic on a stream interface, locking and releasing the
    driver for each packet.

    :param length: Length of the stream of traffic to produce
    """
    ctx.log.info(f"Generating {length} random transactions")
    for _ in range(length):
        async with ctx.lock(stream): # Lock the sequence for exclusive access
            stream.enqueue(StreamTransaction(data=ctx.random.getrandbits(32)))
```

- The `stream_traffic_seq` function is decorated with `@forastero.sequence()` to indicate that it is a sequence generator.
- The `@forastero.requires("stream", StreamInitiator)` decorator specifies that this sequence requires a `StreamInitiator` driver named "stream".
- The `@forastero.randarg("length", range=(100, 1000))` decorator defines a random argument `length` that determines the number of transactions to generate.
- Inside the function, a loop generates random `StreamTransaction` objects and enqueues them to the driver for sending to the DUT.

```python

@forastero.sequence()
@forastero.requires("stream", StreamResponder)
@forastero.randarg("min_interval", range=(1, 10))
@forastero.randarg("max_interval", range=(10, 20))
@forastero.randarg("backpressure", range=(0.1, 0.9))
async def stream_backpressure_seq(
    ctx: SeqContext,
    stream: StreamResponder,
    min_interval: int,
    max_interval: int,
    backpressure: float,
):
    """
    Generate random backpressure using the READY signal of a stream interface,
    with options to tune how often backpressure is applied.

    :param min_interval: Shortest time to hold ready constant
    :param max_interval: Longest time to hold ready constant
    :param backpressure: Weighting proportion for how often ready should be low,
                         i.e. values approaching 1 mean always backpressure,
                         while values approaching 0 mean never backpressure
    """
    async with ctx.lock(stream):
        while True:
            await stream.enqueue(
                StreamBackpressure(
                    ready=ctx.random.choices(
                        (True, False),
                        weights=(1.0 - backpressure, backpressure),
                        k=1,
                    )[0],
                    cycles=ctx.random.randint(min_interval, max_interval),
                ),
                DriverEvent.PRE_DRIVE,
            ).wait()
```

- The `stream_backpressure_seq` function is decorated with `@forastero.sequence()` to indicate that it is a sequence generator.


## Monitoring the DUT

- The monitor observes the DUT outputs and converts low-level signal changes back into transaction items for analysis.

```python
class StreamMonitor(BaseMonitor):
    async def monitor(self, capture: Callable) -> None:
        while True:
            await RisingEdge(self.clk)
            if self.rst.value == self.tb.rst_active_value:
                continue
            if self.io.get("valid", 1) and self.io.get("ready", 1):
                capture(StreamTransaction(data=self.io.get("data", 0)))
``` 

- The `StreamMonitor` class extends the `BaseMonitor` class to implement the monitoring logic for the interface.
- The `monitor` method continuously checks for valid transactions on the interface.
- When a valid transaction is detected (both valid and ready signals are asserted), it captures the data and creates a `StreamTransaction` object, which is then passed to the capture function for further processing.

 
