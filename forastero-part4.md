
# Generating stimulus and monitoring the DUT

## Defining the stimulus test case

```python
@Testbench.testcase()
@Testbench.parameter("packets", int)
@Testbench.parameter("delay", int)
async def random(tb: Testbench, log: Logger, packets: int = 1000, delay: int = 5000):
    # Disable backpressure on input
    tb.x_resp.enqueue(StreamBackpressure(ready=True))
```

- The `random` method is defined as a test case for the testbench, allowing it to be executed as part of the verification process.
- The method takes parameters for the number of packets to generate and the delay between packets.
- The first step in the test case is to disable backpressure on the input by enqueuing a `StreamBackpressure` transaction with `ready=True` to the `x_resp` driver.
- parameters are defined using the `@Testbench.parameter` decorator, allowing them to be easily modified when running the test case.
  - they can be set using json configuration files or command line arguments when executing the testbench.

## Generating and enqueueing traffic

```python
# Queue traffic onto interfaces A & B and interleave on the exit port (A & B
# aren't allowed to drift more than 2 transactions out of sync)
num_a, num_b = 0, 0
for _ in range(packets):
    obj = StreamTransaction(data=tb.random.getrandbits(32))
    if (num_b > (num_a + 2)) or ((num_a < (num_b + 2)) and tb.random.choice((True, False))):
        tb.a_init.enqueue(obj)
        num_a += 1
    else:
        tb.b_init.enqueue(obj)
        num_b += 1
```            

- The test case then enters a loop to generate and enqueue random transactions onto the input interfaces (A and B).
- Each transaction is created with random 32-bit data.
- The transactions are interleaved between interfaces A and B, ensuring that neither interface drifts more than 2 transactions out of sync

## Generating random backpressure on output

```python
    # Queue up random backpressure
    def _rand_bp(*_):
        tb.x_resp.enqueue(
            StreamBackpressure(
                ready=tb.random.choice((True, False)), cycles=tb.random.randint(1, 10)
            )
        )
```

- After enqueueing the transactions, the test case defines a helper function `_rand_bp` to generate random backpressure on the output interface (X).

```python
tb.x_resp.subscribe(DriverEvent.POST_DRIVE, _rand_bp)
_rand_bp()
```

- The test case subscribes the `_rand_bp` function to the `POST_DRIVE` event of the `x_resp` driver, ensuring that random backpressure is applied after each transaction is driven.
- The `_rand_bp` function is called once initially to set up the first backpressure condition

## Completing the stimulus generation

```python
# Register a long-running coroutine
async def _wait():
    await ClockCycles(tb.clk, delay)

tb.register("wait", _wait())
```