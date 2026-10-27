"""
VeriPulse Cyber-Physical Simulated PLC Server
============================================
Industrial Siemens S7-1500 emulation server implementing Modbus TCP on unprivileged port 5020.
Mirrors active holding registers into the VeriPulse shared memory buffer (veripulse_shm_v1)
to enable sub-millisecond cyber-physical state awareness across vision, gateway, and cloud agents.

Holding Register Mapping (0-based offset / 40001-based):
  - 40001 (Offset 0): Line Master Velocity (mm/s, default: 2500)
  - 40002 (Offset 1): Web Tension Setpoint (0.1 N, default: 1500 -> 150.0 N)
  - 40003 (Offset 2): IR Dryer Temp Zone 1 (0.1 °C, default: 1200 -> 120.0 °C)
  - 40004 (Offset 3): Slurry Pump Speed (0.1 RPM, default: 12000 -> 1200.0 RPM)
  - 40005 (Offset 4): Dancer Active Damping Gain (0.01 Gain, default: 500 -> 5.00)
  - 40006-40008 (Offset 5-7): Reserved / Auxiliary telemetry
"""

import sys
import os
import time
import asyncio
import argparse
import signal
import logging
from typing import List, Optional, Tuple

# Add parent directory to path to locate edge_vision modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from edge_vision.shm_common import (
    SHM_NAME,
    HEADER_SIZE,
    VeriPulseHeader,
    get_or_create_shm,
)

# PyModbus 3.5+ cross-version compatibility imports
from pymodbus.server import StartAsyncTcpServer, ModbusTcpServer
try:
    from pymodbus.datastore import ModbusSequentialDataBlock
except ImportError:
    from pymodbus.datastore.sequential import ModbusSequentialDataBlock

try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext

from pymodbus.datastore import ModbusServerContext

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [PLC-SIM] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VeriPulsePLCServer")

# Default holding register values
DEFAULT_REGISTERS = [
    2500,   # 40001: 2.50 m/s (2500 mm/s)
    1500,   # 40002: 150.0 N (1500 * 0.1 N)
    1200,   # 40003: 120.0 °C (1200 * 0.1 °C)
    12000,  # 40004: 1200.0 RPM (12000 * 0.1 RPM)
    500,    # 40005: 5.00 Gain (500 * 0.01 Gain)
    0,      # 40006: Reserved
    0,      # 40007: Reserved
    0       # 40008: Reserved
]


class SafeModbusSequentialDataBlock(ModbusSequentialDataBlock):
    """
    Guarantees cross-version compatibility with PyModbus 3.5 through 3.16+.
    Normalizes 0-based wire address offset without crashing on address-1 bounds checks.
    """
    def __init__(self, address: int, values: list):
        try:
            super().__init__(address, values)
        except (TypeError, ValueError):
            from pymodbus.simulator.simdata import DataType, SimData
            addr = 0 if address <= 0 else address - 1
            self.simdata = [SimData(addr, values=values, datatype=DataType.REGISTERS)]


class SimulatedPLCServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5020,
        sync_interval_sec: float = 0.05,
        enable_shm: bool = True,
        initial_registers: Optional[List[int]] = None,
    ):
        self.host = host
        self.port = port
        self.sync_interval_sec = sync_interval_sec
        self.enable_shm = enable_shm
        self.registers = list(initial_registers or DEFAULT_REGISTERS)
        if len(self.registers) < 8:
            self.registers.extend([0] * (8 - len(self.registers)))
        self.last_mirrored_registers: List[int] = []

        self.shm = None
        self.server: Optional[ModbusTcpServer] = None
        self.is_running = False

        self._init_datastore()

    def _init_datastore(self):
        """Initializes the PyModbus 3.x datastore with holding registers mapped to offset 0."""
        # Use SafeModbusSequentialDataBlock to safely map offset 0 (wire address 0 / 40001)
        self.block = SafeModbusSequentialDataBlock(0, self.registers)
        self.store = ModbusSlaveContext(hr=self.block)
        try:
            # PyModbus 3.14+ prefers devices dict or device context
            self.context = ModbusServerContext(devices={1: self.store})
        except TypeError:
            try:
                self.context = ModbusServerContext(slaves=self.store, single=True)
            except TypeError:
                self.context = ModbusServerContext(self.store)

    def _init_shm(self):
        """Connects to or initializes veripulse_shm_v1."""
        if not self.enable_shm:
            return
        try:
            self.shm = get_or_create_shm(create=False)
            logger.info("Attached to existing shared memory: %s", SHM_NAME)
        except Exception:
            try:
                self.shm = get_or_create_shm(create=True)
                # Seed default header
                hdr = VeriPulseHeader(
                    line_speed_mps=float(self.registers[0]) / 1000.0,
                    modbus_mirror=tuple(self.registers[:8])
                )
                self.shm.buf[:HEADER_SIZE] = hdr.pack()
                logger.info("Initialized shared memory buffer: %s (5.0 MB)", SHM_NAME)
            except Exception as e:
                logger.warning("Shared memory initialization failed: %s. Continuing without SHM.", e)
                self.shm = None

    async def get_live_registers(self) -> List[int]:
        """Extracts the latest register values from PyModbus internal runtime structures."""
        # Method 1: Check active SimCore context
        if self.server and hasattr(self.server, "context"):
            ctx = self.server.context
            if hasattr(ctx, "async_getValues"):
                try:
                    vals = await ctx.async_getValues(1, 3, 0, count=8)
                    if isinstance(vals, list) and len(vals) >= 5:
                        return vals[:8]
                except Exception:
                    pass

        # Method 2: Check context directly
        if hasattr(self.context, "async_getValues"):
            try:
                vals = await self.context.async_getValues(1, 3, 0, count=8)
                if isinstance(vals, list) and len(vals) >= 5:
                    return vals[:8]
            except Exception:
                pass

        # Method 3: Check SimDevice simdata
        if hasattr(self.store, "simdevice") and hasattr(self.store.simdevice, "simdata"):
            try:
                # Simdata index 2 is holding registers
                hr_data = self.store.simdevice.simdata[2][0]
                if hasattr(hr_data, "values") and isinstance(hr_data.values, list):
                    return hr_data.values[:8]
            except Exception:
                pass

        # Method 4: Check block simdata
        if hasattr(self.block, "simdata"):
            try:
                return self.block.simdata[0].values[:8]
            except Exception:
                pass

        return self.registers

    def mirror_to_shm(self, regs: List[int]):
        """Mirrors holding registers directly into veripulse_shm_v1."""
        if not self.shm:
            return
        try:
            current_raw = bytes(self.shm.buf[:HEADER_SIZE])
            try:
                header = VeriPulseHeader.unpack(current_raw)
            except Exception:
                header = VeriPulseHeader()

            # Update mirrored registers and line speed
            padded = list(regs) + [0] * (8 - len(regs))
            header.modbus_mirror = tuple(padded[:8])
            header.line_speed_mps = float(regs[0]) / 1000.0  # mm/s -> m/s
            header.timestamp_ns = time.time_ns()

            self.shm.buf[:HEADER_SIZE] = header.pack()
        except Exception as e:
            logger.debug("SHM mirror write error: %s", e)

    async def _mirror_loop(self):
        """Asynchronous background loop syncing registers to SHM at 20 Hz."""
        logger.info("Started SHM register mirroring loop (interval: %.1f ms)", self.sync_interval_sec * 1000)
        while self.is_running:
            try:
                current_regs = await self.get_live_registers()
                if current_regs != self.last_mirrored_registers:
                    vel = current_regs[0]
                    ten = current_regs[1] / 10.0
                    tmp = current_regs[2] / 10.0
                    pmp = current_regs[3] / 10.0
                    dgn = current_regs[4] / 100.0

                    logger.info(
                        "Holding Registers Updated: [40001: %d mm/s (%.2f m/s), 40002: %.1f N, "
                        "40003: %.1f °C, 40004: %.1f RPM, 40005: %.2f Gain]",
                        vel, vel / 1000.0, ten, tmp, pmp, dgn
                    )
                    self.mirror_to_shm(current_regs)
                    self.last_mirrored_registers = list(current_regs)
            except Exception as e:
                logger.error("Error in mirror loop: %s", e)

            await asyncio.sleep(self.sync_interval_sec)

    async def run(self):
        """Runs the Modbus TCP server and synchronization tasks."""
        self.is_running = True
        self._init_shm()

        self.server = ModbusTcpServer(self.context, address=(self.host, self.port))
        logger.info("=" * 68)
        logger.info("VERIPULSE CYBER-PHYSICAL PLC SERVER ONLINE")
        logger.info("Emulating: Siemens S7-1500 (Modbus TCP Standard)")
        logger.info("Endpoint:  %s:%d (Unprivileged Industrial Port)", self.host, self.port)
        logger.info("Initial Registers: %s", self.registers[:5])
        logger.info("=" * 68)

        mirror_task = asyncio.create_task(self._mirror_loop())
        try:
            await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            self.is_running = False
            mirror_task.cancel()
            try:
                await mirror_task
            except asyncio.CancelledError:
                pass
            if self.server:
                await self.server.shutdown()
            if self.shm:
                try:
                    self.shm.close()
                except Exception:
                    pass
            logger.info("Simulated PLC server stopped cleanly.")


def parse_args():
    parser = argparse.ArgumentParser(description="VeriPulse Simulated Modbus TCP PLC Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Binding host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5020, help="Modbus TCP unprivileged port (default: 5020)")
    parser.add_argument("--interval-ms", type=float, default=50.0, help="SHM sync interval in ms (default: 50.0)")
    parser.add_argument("--no-shm", action="store_true", help="Disable SHM mirroring")
    return parser.parse_args()


async def main_async():
    args = parse_args()
    server = SimulatedPLCServer(
        host=args.host,
        port=args.port,
        sync_interval_sec=args.interval_ms / 1000.0,
        enable_shm=not args.no_shm,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received termination signal. Shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows signal handling fallback
            pass

    server_task = asyncio.create_task(server.run())
    
    # Wait until shutdown requested or task completes
    try:
        await server_task
    except (asyncio.CancelledError, KeyboardInterrupt):
        server_task.cancel()
        await server_task


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
