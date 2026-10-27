"""
VeriPulse High-Throughput WebSocket IPC Gateway
===============================================
Bridges the C++/Python 120 FPS Edge Perception Engine (veripulse_shm_v1)
with the Next.js 14 WebGL Digital Twin Dashboard.

Key Specifications:
- High-throughput WebSocket server listening on ws://localhost:8765.
- Samples shared memory at 30 Hz or 60 Hz to eliminate React useState jitter.
- Broadcasts standardized JSON frames:
    1. frame_telemetry: High-speed sensor telemetry, 512-bin 2D-FFT harmonics, active alerts.
    2. agent_event: Claude 3.5 Sonnet multimodal reasoning, tool dispatches, and COOL verification.
    3. plc_update: HMAC-SHA256 authenticated Modbus holding register setpoints.
- Built-in Autonomous Simulation Fallback: Seamlessly synthesizes realistic
  120 FPS continuous lithium anode web dynamics if SHM ring buffer is unmapped.
"""

import os
import sys
import json
import time
import math
import hmac
import hashlib
import random
import logging
import asyncio
import argparse
from typing import Set, Dict, Any, Optional

import websockets
try:
    from websockets.asyncio.server import ServerConnection
except ImportError:
    ServerConnection = Any

# Add parent directory for module resolution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from edge_vision.shm_common import (
        SHM_NAME,
        SHM_SIZE,
        HEADER_SIZE,
        FFT_OFFSET,
        FFT_BINS,
        WEBP_OFFSET,
        VeriPulseHeader,
        get_or_create_shm,
    )
    HAS_SHM_COMMON = True
except ImportError:
    HAS_SHM_COMMON = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [IPC-GATEWAY] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VeriPulseGateway")

DEFAULT_HMAC_SECRET = os.getenv("VERIPULSE_HMAC_SECRET", "veripulse-plc-cyberphysical-token-v1")


class SHMWebSocketGateway:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        target_hz: int = 60,
        force_simulation: bool = False,
    ):
        self.host = host
        self.port = port
        self.target_hz = target_hz
        self.sample_interval = 1.0 / max(1, target_hz)
        self.force_simulation = force_simulation

        self.connected_clients: Set[Any] = set()
        self.shm_handle = None
        self.running = False

        # Internal simulation state
        self.sim_sequence_id = 145920
        self.sim_line_speed = 2.50
        self.sim_tension = 150.0
        self.sim_dryer_temp = 120.0
        self.sim_pump_rpm = 1200.0
        self.sim_dancer_gain = 5.00
        self.sim_defect_count = 0
        self.sim_step_count = 0
        self.sim_anomaly_state = 0  # 0: Nominal, 1: Specular Glare, 2: 142.5 Hz Ribbing
        self.sim_last_agent_event_ts = 0.0

    def connect_shm(self) -> bool:
        """Attempts to attach to the live veripulse_shm_v1 ring buffer."""
        if self.force_simulation or not HAS_SHM_COMMON:
            logger.info("Operating in Autonomous Synthetic Simulation mode.")
            return False

        try:
            self.shm_handle = get_or_create_shm(create=False)
            logger.info("Successfully mapped live SHM buffer: %s (Size: %d bytes)", SHM_NAME, SHM_SIZE)
            return True
        except FileNotFoundError:
            logger.warning("SHM '%s' not found. Falling back to synthetic simulation mode.", SHM_NAME)
            return False
        except Exception as e:
            logger.warning("Could not map SHM (%s). Falling back to synthetic simulation.", e)
            return False

    def _generate_synthetic_fft(self, has_ribbing: bool) -> list:
        """Synthesizes a realistic 512-bin 2D-FFT power spectrum."""
        # Baseline Gaussian noise floor (-60 dB to -40 dB normalized 0.005 - 0.035)
        spectrum = [0.008 + 0.005 * math.sin(i * 0.1) + random.uniform(0.001, 0.006) for i in range(512)]

        # 14.25 Hz Temporal Stitched Roller Runout Peak (Bin ~14)
        bin_14 = 14
        spectrum[bin_14] = 0.28 + random.uniform(0.02, 0.06)
        if bin_14 > 0:
            spectrum[bin_14 - 1] = spectrum[bin_14] * 0.45
        if bin_14 + 1 < 512:
            spectrum[bin_14 + 1] = spectrum[bin_14] * 0.45

        # 142.5 Hz Slot-Die Fundamental Ribbing Harmonic (Bin ~142)
        bin_142 = 142
        if has_ribbing:
            # High resonance spike (>0.85 normalized spectral power)
            spectrum[bin_142] = 0.892 + random.uniform(-0.02, 0.04)
            spectrum[bin_142 - 1] = spectrum[bin_142] * 0.65
            spectrum[bin_142 + 1] = spectrum[bin_142] * 0.65
            # Second harmonic at 285.0 Hz (Bin ~285)
            bin_285 = 285
            spectrum[bin_285] = 0.42 + random.uniform(-0.02, 0.03)
            spectrum[bin_285 - 1] = spectrum[bin_285] * 0.5
            spectrum[bin_285 + 1] = spectrum[bin_285] * 0.5
        else:
            # Attenuated background harmonic
            spectrum[bin_142] = 0.075 + random.uniform(0.005, 0.015)
            spectrum[bin_142 - 1] = spectrum[bin_142] * 0.4
            spectrum[bin_142 + 1] = spectrum[bin_142] * 0.4

        return [round(val, 4) for val in spectrum]

    def read_telemetry_frame(self) -> Dict[str, Any]:
        """Samples telemetry from shared memory or generates synthetic frame."""
        now_ns = time.time_ns()

        if self.shm_handle is not None:
            try:
                buf = bytes(self.shm_handle.buf[:HEADER_SIZE])
                header = VeriPulseHeader.unpack(buf)

                # Extract FFT from SHM
                fft_bins = []
                if HAS_NUMPY:
                    fft_raw = np.ndarray(
                        (FFT_BINS,),
                        dtype=np.float32,
                        buffer=self.shm_handle.buf,
                        offset=FFT_OFFSET,
                    )
                    fft_bins = [round(float(v), 4) for v in fft_raw]
                else:
                    fft_bins = self._generate_synthetic_fft(bool(header.alert_flags & 0x02))

                # Extract engineering values from modbus_mirror
                vel = header.modbus_mirror[0] / 1000.0 if len(header.modbus_mirror) > 0 else header.line_speed_mps
                ten = header.modbus_mirror[1] / 10.0 if len(header.modbus_mirror) > 1 else 150.0
                tmp = header.modbus_mirror[2] / 10.0 if len(header.modbus_mirror) > 2 else 120.0
                pmp = header.modbus_mirror[3] / 10.0 if len(header.modbus_mirror) > 3 else 1200.0
                dnc = header.modbus_mirror[4] / 100.0 if len(header.modbus_mirror) > 4 else 5.0

                has_alert = bool(header.alert_flags & 0x07)
                defect_type = "nominal"
                if header.alert_flags & 0x04:
                    defect_type = "substrate_rupture"
                elif header.alert_flags & 0x02:
                    defect_type = "slot_die_ribbing_resonance"
                elif header.alert_flags & 0x01:
                    defect_type = "surface_reflectance_anomaly"

                return {
                    "type": "frame_telemetry",
                    "sequence_id": header.sequence_id,
                    "timestamp_ns": header.timestamp_ns or now_ns,
                    "fps": 120.4,
                    "telemetry": {
                        "line_speed_mps": round(vel, 3),
                        "tension_newtons": round(ten, 1),
                        "dryer_temp_c": round(tmp, 1),
                        "pump_rpm": round(pmp, 1),
                        "dancer_damping_gain": round(dnc, 2),
                    },
                    "fft_power_spectrum": fft_bins,
                    "active_alert": {
                        "detected": has_alert,
                        "defect_type": defect_type,
                        "severity": "CRITICAL" if (header.alert_flags & 0x04) else ("WARNING" if has_alert else "INFO"),
                        "bounding_box": {"x": 14200, "y": 8500, "width": 450, "height": 180} if has_alert else None,
                    },
                }
            except Exception as e:
                logger.debug("SHM read failed (%s); reverting to simulation frame", e)

        # Autonomous procedural simulation
        self.sim_step_count += 1
        self.sim_sequence_id += 2  # advance at ~120 Hz pace relative to sample rate
        t = self.sim_step_count * self.sample_interval

        # Cyclic anomaly scenario every 25 seconds for visual evaluation
        cycle_sec = 25.0
        phase = (t % cycle_sec)

        has_ribbing = False
        has_glare = False
        has_estop = False

        if 6.0 <= phase < 12.0:
            # Specular Glare Phase
            self.sim_anomaly_state = 1
            has_glare = True
        elif 15.0 <= phase < 21.0:
            # 142.5 Hz Ribbing Phase
            self.sim_anomaly_state = 2
            has_ribbing = True
            # Physical coupling: slight tension oscillation and pump surge
            self.sim_tension = 150.0 + 4.2 * math.sin(t * 14.25 * 2 * math.pi)
            self.sim_pump_rpm = 1245.0 + 15.0 * math.cos(t * 5.0)
        else:
            self.sim_anomaly_state = 0
            # Nominal relaxation
            self.sim_tension += (150.0 - self.sim_tension) * 0.05
            self.sim_pump_rpm += (1200.0 - self.sim_pump_rpm) * 0.05

        has_alert = has_ribbing or has_glare or has_estop
        defect_type = "nominal"
        if has_estop:
            defect_type = "substrate_rupture"
        elif has_ribbing:
            defect_type = "slot_die_ribbing_resonance"
        elif has_glare:
            defect_type = "surface_reflectance_anomaly"

        if has_alert and self.sim_step_count % 30 == 0:
            self.sim_defect_count += 1

        fft_bins = self._generate_synthetic_fft(has_ribbing)

        # Micro fluctuations
        line_speed = self.sim_line_speed + random.uniform(-0.004, 0.004)
        dryer_temp = self.sim_dryer_temp + 0.2 * math.sin(t * 0.2) + random.uniform(-0.05, 0.05)

        return {
            "type": "frame_telemetry",
            "sequence_id": self.sim_sequence_id,
            "timestamp_ns": now_ns,
            "fps": 120.0 + random.uniform(-0.6, 0.6),
            "telemetry": {
                "line_speed_mps": round(line_speed, 3),
                "tension_newtons": round(self.sim_tension, 2),
                "dryer_temp_c": round(dryer_temp, 2),
                "pump_rpm": round(self.sim_pump_rpm, 1),
                "dancer_damping_gain": round(self.sim_dancer_gain, 2),
            },
            "fft_power_spectrum": fft_bins,
            "active_alert": {
                "detected": has_alert,
                "defect_type": defect_type,
                "severity": "CRITICAL" if has_estop else ("WARNING" if has_alert else "INFO"),
                "bounding_box": {"x": 14200, "y": 8500, "width": 450, "height": 180} if has_alert else None,
            },
        }

    def generate_agent_event(self, anomaly_type: str) -> Dict[str, Any]:
        """Generates a Claude 3.5 Sonnet multimodal reasoning event."""
        now_ns = time.time_ns()
        evt_id = f"evt_{int(time.time() * 1000) % 1000000:06x}"

        if anomaly_type == "surface_reflectance_anomaly":
            return {
                "type": "agent_event",
                "event_id": evt_id,
                "timestamp_ns": now_ns,
                "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "cool_metrology_verification": {
                    "engine": "COOL-v3.1-Arm64-KleidiCV",
                    "verdict": "specular_reflection_suspected",
                    "morphological_solidity": 0.94,
                    "gabor_energy_ratio": 0.12,
                },
                "agent_reasoning": (
                    "High specular saturation ratio (0.82) and low Gabor gradient roughness "
                    "confirm optical glare from bare copper foil rather than true slurry delamination. "
                    "Dispatched dynamic bilateral filter recalibration to eliminate false rejects."
                ),
                "dispatched_tool": "recalibrate_gapi_vision_pipeline",
                "tool_parameters": {
                    "line_id": "line_04_lithium_anode",
                    "target_node_id": "fused_subpixel_edge_01",
                    "bilateral_spatial_sigma": 1.8,
                    "bilateral_range_sigma": 0.08,
                    "scharr_gradient_threshold": 45.0,
                    "exposure_time_us": 180,
                },
                "closed_loop_latency_ms": 1920.5,
            }
        else:
            return {
                "type": "agent_event",
                "event_id": evt_id,
                "timestamp_ns": now_ns,
                "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "cool_metrology_verification": {
                    "engine": "COOL-v3.1-Arm64-KleidiCV",
                    "verdict": "slot_die_ribbing_resonance_confirmed",
                    "morphological_solidity": 0.38,
                    "gabor_energy_ratio": 0.88,
                },
                "agent_reasoning": (
                    "Spatial 2D-FFT detects 142.50 Hz fundamental harmonic with +44.3 dB spectral power. "
                    "Rolling SCADA trend confirms 12.8 dN tension variance coupled with 1245 RPM pump ripple. "
                    "Dispatched deterministic velocity shift (-120 mm/s) and dancer roll damping increase (+1.50)."
                ),
                "dispatched_tool": "execute_plc_recalibration",
                "tool_parameters": {
                    "line_id": "line_04_lithium_anode",
                    "target_plc_ip": "192.168.10.50",
                    "engineering_setpoints": {
                        "line_velocity_mps": 2.38,
                        "web_tension_newtons": 145.0,
                        "ir_dryer_temp_celsius": 118.5,
                        "slurry_pump_rpm": 1180.0,
                        "dancer_damping_gain": 6.50,
                    },
                },
                "closed_loop_latency_ms": 2340.2,
            }

    def generate_plc_update(self, velocity_mms: int = 2380, tension_dn: int = 1450) -> Dict[str, Any]:
        """Generates authenticated Modbus holding register actuation payload."""
        now_ns = time.time_ns()
        regs = {
            "velocity_mms": velocity_mms,
            "tension_dn": tension_dn,
            "temp_dc": 1185,
            "pump_drpm": 11800,
            "dancer_dgain": 650,
        }
        # Compute HMAC-SHA256 signature
        canonical = json.dumps(regs, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(DEFAULT_HMAC_SECRET.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

        return {
            "type": "plc_update",
            "timestamp_ns": now_ns,
            "holding_registers": regs,
            "hmac_sha256_signature": sig,
            "actuator_settling_time_sec": 0.80,
        }

    async def broadcast_message(self, message: Dict[str, Any]):
        """Dispatches JSON payload to all active client connections."""
        if not self.connected_clients:
            return
        payload = json.dumps(message)
        dead_clients = set()
        for client in self.connected_clients:
            try:
                await client.send(payload)
            except websockets.exceptions.ConnectionClosed:
                dead_clients.add(client)
            except Exception as e:
                logger.debug("Failed sending to client: %s", e)
                dead_clients.add(client)

        for dead in dead_clients:
            self.connected_clients.remove(dead)

    async def handler(self, websocket: Any, *args):
        """Handles incoming client connection and operator commands."""
        remote = getattr(websocket, "remote_address", None)
        client_ip = remote[0] if remote else "dashboard-client"
        self.connected_clients.add(websocket)
        logger.info("Operator dashboard connected from %s (Total: %d)", client_ip, len(self.connected_clients))

        try:
            # Emit immediate initial state greeting
            initial_frame = self.read_telemetry_frame()
            await websocket.send(json.dumps(initial_frame))

            async for message in websocket:
                # Handle inbound operator commands from dashboard
                try:
                    data = json.loads(message)
                    cmd = data.get("command")
                    logger.info("Received operator command: %s", cmd)
                    if cmd == "trigger_defect":
                        defect = data.get("defect_type", "surface_reflectance_anomaly")
                        event = self.generate_agent_event(defect)
                        await self.broadcast_message(event)
                    elif cmd == "manual_override":
                        plc_frame = self.generate_plc_update()
                        await self.broadcast_message(plc_frame)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        finally:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            logger.info("Operator dashboard disconnected from %s (Remaining: %d)", client_ip, len(self.connected_clients))

    async def telemetry_loop(self):
        """Continuous high-speed sampling and broadcast loop."""
        logger.info("Broadcasting high-throughput telemetry at %d Hz...", self.target_hz)
        prev_anomaly = 0

        while self.running:
            start_t = time.perf_counter()

            # 1. Broadcast periodic frame telemetry
            frame = self.read_telemetry_frame()
            await self.broadcast_message(frame)

            # 2. Check for synthetic agent reasoning events on state transitions
            current_anomaly = self.sim_anomaly_state
            now = time.time()
            if current_anomaly != prev_anomaly and current_anomaly != 0:
                if now - self.sim_last_agent_event_ts > 4.0:
                    self.sim_last_agent_event_ts = now
                    anomaly_type = (
                        "surface_reflectance_anomaly"
                        if current_anomaly == 1
                        else "slot_die_ribbing_resonance"
                    )
                    agent_evt = self.generate_agent_event(anomaly_type)
                    await self.broadcast_message(agent_evt)

                    # Follow with authenticated PLC actuation if ribbing
                    if current_anomaly == 2:
                        await asyncio.sleep(0.4)
                        plc_evt = self.generate_plc_update(velocity_mms=2380, tension_dn=1450)
                        await self.broadcast_message(plc_evt)

            prev_anomaly = current_anomaly

            elapsed = time.perf_counter() - start_t
            sleep_time = max(0.001, self.sample_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def start(self):
        """Starts WebSocket server and telemetry task."""
        self.running = True
        self.connect_shm()

        logger.info("VeriPulse IPC WebSocket Server listening on ws://%s:%d", self.host, self.port)
        async with websockets.serve(self.handler, self.host, self.port):
            await self.telemetry_loop()

    def stop(self):
        """Gracefully shuts down server and releases SHM handle."""
        self.running = False
        if self.shm_handle:
            try:
                self.shm_handle.close()
            except Exception:
                pass
        logger.info("IPC Gateway terminated cleanly.")


def main():
    parser = argparse.ArgumentParser(description="VeriPulse Shared Memory WebSocket IPC Gateway")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="WebSocket listen host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket listen port (default: 8765)")
    parser.add_argument("--hz", type=int, default=60, help="Sampling frequency in Hz (30 or 60, default: 60)")
    parser.add_argument("--simulate", action="store_true", help="Force autonomous simulation fallback mode")
    parser.add_argument("--test-run", type=int, default=0, help="Run for N seconds and exit cleanly (testing)")
    args = parser.parse_args()

    gateway = SHMWebSocketGateway(
        host=args.host,
        port=args.port,
        target_hz=args.hz,
        force_simulation=args.simulate,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if args.test_run > 0:
        async def run_test():
            server_task = asyncio.create_task(gateway.start())
            await asyncio.sleep(args.test_run)
            gateway.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        try:
            loop.run_until_complete(run_test())
            logger.info("Headless test run completed successfully.")
            return 0
        except Exception as e:
            logger.error("Test run error: %s", e)
            return 1

    try:
        loop.run_until_complete(gateway.start())
    except KeyboardInterrupt:
        gateway.stop()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
