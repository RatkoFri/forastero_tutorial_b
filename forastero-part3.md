# Building the Testbench

The testbench is a crucial part of the verification environment, responsible for stimulating the DUT (design under test) and checking its responses. A well-structured testbench typically consists of several key components, including transaction generators, drivers, monitors, and scoreboards.

## Testbench class 

The testbench class serves as the top-level container for all testbench components. It orchestrates the interactions between drivers, monitors, and scoreboards, ensuring that the DUT is properly stimulated and its responses are accurately checked.

```python
class Testbench(BaseBench):
    """
    Testbench wrapped around the simple 2-to-1 stream arbiter.

    :param dut: Reference to the arbiter DUT
    """

    def __init__(self, dut: HierarchyObject) -> None:
        super().__init__(
            dut,
            clk=dut.i_clk,
            rst=dut.i_rst,
            clk_drive=True,
            clk_period=1,
            clk_units="ns",
        )

```
- The `Testbench` class inherits from `BaseBench`, which provides common functionality for testbenches in Forastero.
- The constructor initializes the testbench with the DUT reference, clock, and reset signals, setting up the clock generation parameters.

## Instantiating Components

```python
# Wrap stream I/O on the arbiter
a_io = StreamIO(dut, "a", IORole.RESPONDER)
b_io = StreamIO(dut, "b", IORole.RESPONDER)
x_io = StreamIO(dut, "x", IORole.INITIATOR)
```

- Here, we instantiate the `StreamIO` interfaces for the arbiter's input ports (A and B) and output port (X), specifying their roles as responder or initiator.
  - if the interface is passing signals into the DUT, it is a RESPONDER
  - if the interface is receiving signals from the DUT, it is an INITIATOR
> note: here we are looking at the arbiter from the perspective of the TB environment 

## Registering drivers and monitors

```python
self.register("a_init", StreamInitiator(self, a_io, self.clk, self.rst))
self.register("b_init", StreamInitiator(self, b_io, self.clk, self.rst))
self.register("x_resp", StreamResponder(self, x_io, self.clk, self.rst, blocking=False))
```
- We register two `StreamInitiator` drivers for the input interfaces (A and B) to send transactions to the DUT.
- We register a `StreamResponder` monitor for the output interface (X) to receive transactions from the DUT.
  - The `blocking=False` parameter allows the monitor to operate in a non-blocking mode, enabling concurrent transaction handling.

## Register monitors to observe DUT behavior

```python
self.register(
    "x_mon",
    StreamMonitor(self, x_io, self.clk, self.rst),
    scoreboard_match_window=4,
    )
```

- We register a `StreamMonitor` for the output interface (X) to observe the DUT's behavior and capture transactions for analysis.
- The `scoreboard_match_window=4` parameter specifies the time window for matching transactions in the scoreboard.

## Register callbacks

```python
# Register callbacks to the model
self.a_init.subscribe(DriverEvent.ENQUEUE, self.model)
self.b_init.subscribe(DriverEvent.ENQUEUE, self.model)
```

- We subscribe the transaction generators (drivers) to the model, allowing the model to receive notifications when new transactions are enqueued.
- As transactions progress through a driver, events are emitted to allow observers such as models or stimulus generation to track its progress. There are 3 different events defined:
  - ENQUEUE - emitted when a transaction is enqueued into a driver by a test or sequence, this may happen long before the transaction is driven into the DUT;
  - PRE_DRIVE - emitted just prior to a queued transaction being driven into the DUT;
  - POST_DRIVE - emitted just after a queued transaction is driven into the DUT;

- By subscribing the model to the ENQUEUE event, we ensure that it is notified whenever a new transaction is added to the driver's queue, allowing it to update its internal state accordingly.

## Scoreboard   
```python

def model(self, driver: StreamInitiator, event: DriverEvent, obj: StreamTransaction) -> None:
    """
    Demonstration model that forwards transactions seen on interfaces A & B
    and sets bit 32 (to match the filtering behaviour below)
    """
    assert driver in (self.a_init, self.b_init)
    assert event == DriverEvent.ENQUEUE
    self.scoreboard.channels["x_mon"].push_reference(obj)
```



