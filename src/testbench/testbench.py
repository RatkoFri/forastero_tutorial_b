from cocotb.triggers import RisingEdge

from forastero.driver import BaseDriver

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

from collections.abc import Callable

from cocotb.triggers import RisingEdge

from forastero import BaseMonitor

from .transaction import StreamTransaction


class StreamMonitor(BaseMonitor):
    async def monitor(self, capture: Callable) -> None:
        while True:
            await RisingEdge(self.clk)
            if self.rst.value == self.tb.rst_active_value:
                continue
            if self.io.get("valid", 1) and self.io.get("ready", 1):
                capture(StreamTransaction(data=self.io.get("data", 0)))



from cocotb.triggers import ClockCycles

from forastero.driver import BaseDriver

from .transaction import StreamBackpressure


class StreamResponder(BaseDriver):
    async def drive(self, obj: StreamBackpressure) -> None:
        self.io.set("ready", obj.ready)
        await ClockCycles(self.clk, obj.cycles)

import forastero
from forastero import DriverEvent, SeqContext

from .initiator import StreamInitiator
from .responder import StreamResponder
from .transaction import StreamBackpressure, StreamTransaction


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
        async with ctx.lock(stream):
            stream.enqueue(StreamTransaction(data=ctx.random.getrandbits(32)))


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

from dataclasses import dataclass

from forastero import BaseTransaction


@dataclass(kw_only=True)
class StreamTransaction(BaseTransaction):
    data: int = 0


@dataclass(kw_only=True)
class StreamBackpressure(BaseTransaction):
    ready: bool = True
    cycles: int = 1


from cocotb.handle import HierarchyObject
from common.io.stream import (
    StreamInitiator,
    StreamIO,
    StreamMonitor,
    StreamResponder,
    StreamTransaction,
)

from forastero.bench import BaseBench
from forastero.driver import DriverEvent
from forastero.io import IORole


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
        # Wrap stream I/O on the arbiter
        a_io = StreamIO(dut, "a", IORole.RESPONDER)
        b_io = StreamIO(dut, "b", IORole.RESPONDER)
        x_io = StreamIO(dut, "x", IORole.INITIATOR)
        # Register drivers and monitors for the stream interfaces
        self.register("a_init", StreamInitiator(self, a_io, self.clk, self.rst))
        self.register("b_init", StreamInitiator(self, b_io, self.clk, self.rst))
        self.register("x_resp", StreamResponder(self, x_io, self.clk, self.rst, blocking=False))
        self.register(
            "x_mon",
            StreamMonitor(self, x_io, self.clk, self.rst),
            scoreboard_match_window=4,
        )
        # Register callbacks to the model
        self.a_init.subscribe(DriverEvent.ENQUEUE, self.model)
        self.b_init.subscribe(DriverEvent.ENQUEUE, self.model)

    def model(self, driver: StreamInitiator, event: DriverEvent, obj: StreamTransaction) -> None:
        """
        Demonstration model that forwards transactions seen on interfaces A & B
        and sets bit 32 (to match the filtering behaviour below)
        """
        assert driver in (self.a_init, self.b_init)
        assert event == DriverEvent.ENQUEUE
        self.scoreboard.channels["x_mon"].push_reference(obj)



from logging import Logger

from cocotb.triggers import ClockCycles
from common.io.stream import StreamBackpressure, StreamTransaction

from forastero import DriverEvent

from ..testbench import Testbench


@Testbench.testcase()
@Testbench.parameter("packets", int)
@Testbench.parameter("delay", int)
async def random(tb: Testbench, log: Logger, packets: int = 1000, delay: int = 5000):
    # Disable backpressure on input
    tb.x_resp.enqueue(StreamBackpressure(ready=True))

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

    # Queue up random backpressure
    def _rand_bp(*_):
        tb.x_resp.enqueue(
            StreamBackpressure(
                ready=tb.random.choice((True, False)), cycles=tb.random.randint(1, 10)
            )
        )

    tb.x_resp.subscribe(DriverEvent.POST_DRIVE, _rand_bp)
    _rand_bp()

    # Register a long-running coroutine
    async def _wait():
        await ClockCycles(tb.clk, delay)

    tb.register("wait", _wait())