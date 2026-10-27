"""
End-to-End Test Suite for VeriPulse Cyber-Physical PLC and Synthetic Streaming Engine
=====================================================================================
Validates:
  1. modbus_register_map.json and edge_pipeline.json schema and bounds
  2. HMAC-SHA256 command signing and security rejection
  3. Safety interlock bounding against engineering envelopes
  4. PyModbus 3.5+ server and client read/write on port 5020
  5. Live SHM register mirroring to veripulse_shm_v1
  6. Synthetic 120 FPS generation, defect injection, and closed-loop decay
"""

import os
import sys
import json
import time
import asyncio
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from edge_vision.shm_common import (
    SHM_NAME,
    HEADER_SIZE,
    OPTICAL_OFFSET,
    OPTICAL_SHAPE,
    THERMAL_OFFSET,
    THERMAL_SHAPE,
    VeriPulseHeader,
    get_or_create_shm,
)
from plc_bridge.modbus_client_bridge import (
    sign_actuation_payload,
    verify_actuation_payload,
    ModbusClientBridge,
    SecurityVerificationError,
)
from plc_bridge.simulated_plc_server import SimulatedPLCServer
from synthetic_streamer.defect_injector import DefectInjector
from synthetic_streamer.synthetic_generator import SyntheticFoilGenerator


class TestCyberPhysicalPipeline(unittest.TestCase):
    def test_01_configuration_files(self):
        """Validates modbus_register_map.json and edge_pipeline.json."""
        reg_map_path = os.path.join(PROJECT_ROOT, "config", "modbus_register_map.json")
        edge_pipe_path = os.path.join(PROJECT_ROOT, "config", "edge_pipeline.json")

        self.assertTrue(os.path.exists(reg_map_path), "modbus_register_map.json missing")
        self.assertTrue(os.path.exists(edge_pipe_path), "edge_pipeline.json missing")

        with open(reg_map_path, "r", encoding="utf-8") as f:
            reg_map = json.load(f)
        self.assertEqual(reg_map["port"], 5020)
        self.assertEqual(len(reg_map["holding_registers"]), 5)
        self.assertIn("40001", reg_map["holding_registers"])
        self.assertIn("40005", reg_map["holding_registers"])

        with open(edge_pipe_path, "r", encoding="utf-8") as f:
            edge_pipe = json.load(f)
        opt = edge_pipe["optical_camera"]
        self.assertEqual(opt["width"], 2048)
        self.assertEqual(opt["height"], 2048)
        self.assertEqual(opt["target_fps"], 120.0)
        self.assertAlmostEqual(opt["spatial_resolution_um_per_pixel"], 24.414, places=3)
        self.assertEqual(opt["field_of_view_mm"]["width_mm"], 50.0)

    def test_02_hmac_signing_and_safety_bounds(self):
        """Validates cryptographic signing and safety interlocks."""
        payload = {
            "velocity_mms": 2380,
            "tension_dn": 1450,
            "temp_dc": 1185,
            "pump_drpm": 11800,
            "dancer_dgain": 650,
        }
        sig = sign_actuation_payload(payload)
        self.assertTrue(verify_actuation_payload(payload, sig))
        self.assertFalse(verify_actuation_payload(payload, "invalid_hmac_hex"))

        bridge = ModbusClientBridge()
        # Test violation of safety envelope
        unsafe = {"velocity_mms": 3800, "dancer_dgain": 1200}
        clamped = bridge.clamp_safety_bounds(unsafe)
        self.assertEqual(clamped["velocity_mms"], 2750)  # Max safety bound
        self.assertEqual(clamped["dancer_dgain"], 700)   # Max safety bound

    def test_03_defect_injector_and_decay(self):
        """Validates defect injection and closed-loop decay."""
        injector = DefectInjector()
        injector.trigger_pinhole(cx:=512, cy:=512, diameter_um=50.0)
        injector.trigger_ribbing(amplitude=38.0)
        injector.trigger_specular_glare()

        self.assertEqual(len(injector.pinholes), 1)
        self.assertTrue(injector.ribbing_active)
        self.assertTrue(injector.glare_active)
        self.assertEqual(injector.alert_flags, 0x03)

        # Closed-loop decay test: line velocity shifted to 2380 mm/s and gain increased to 6.50
        for _ in range(120):
            injector.update_closed_loop_state(
                velocity_mms=2380, dancer_gain_x100=650, dt_sec=1.0/120.0
            )

        self.assertFalse(injector.ribbing_active)
        self.assertEqual(injector.ribbing_amplitude, 0.0)

    def test_04_synthetic_generator_shm_output(self):
        """Validates 120 FPS generation and zero-copy SHM buffers."""
        gen = SyntheticFoilGenerator(target_fps=120.0, enable_shm=True)
        gen.defect_injector.trigger_pinhole(500, 500, diameter_um=50.0)
        gen.defect_injector.trigger_ribbing(amplitude=38.0)

        opt, thm, def_count, flags = gen.generate_frame()
        self.assertEqual(opt.shape, (2048, 2048))
        self.assertEqual(thm.shape, (512, 512))
        self.assertEqual(opt.dtype, np.uint8)
        self.assertEqual(thm.dtype, np.uint8)
        self.assertGreaterEqual(def_count, 1)

        gen.publish_to_shm(opt, thm, def_count, flags)

        # Read back from SHM while generator handle is active
        shm = get_or_create_shm(create=False)
        hdr = VeriPulseHeader.unpack(bytes(shm.buf[:HEADER_SIZE]))
        self.assertEqual(hdr.magic, 0x5650554C)
        self.assertEqual(hdr.defect_count, def_count)
        self.assertEqual(hdr.alert_flags, flags)
        shm.close()

        gen.stop()

    def test_05_modbus_server_client_roundtrip_and_shm_mirror(self):
        """Validates live Modbus TCP server and client read/write and SHM mirroring."""
        async def run_roundtrip():
            server = SimulatedPLCServer(host="127.0.0.1", port=5020, enable_shm=True)
            server_task = asyncio.create_task(server.run())
            await asyncio.sleep(0.3)

            bridge = ModbusClientBridge(host="127.0.0.1", port=5020)
            initial = await bridge.read_registers()
            self.assertEqual(initial["velocity_mms"], 2500)

            # Write signed command
            cmd = {"velocity_mms": 2380, "dancer_dgain": 650}
            sig = sign_actuation_payload(cmd)
            success = await bridge.write_registers(cmd, hmac_signature=sig)
            self.assertTrue(success)

            # Read back
            after = await bridge.read_registers()
            self.assertEqual(after["velocity_mms"], 2380)
            self.assertEqual(after["dancer_dgain"], 650)

            # Check SHM mirror
            await asyncio.sleep(0.15)
            shm = get_or_create_shm(create=False)
            hdr = VeriPulseHeader.unpack(bytes(shm.buf[:HEADER_SIZE]))
            self.assertEqual(hdr.modbus_mirror[0], 2380)
            self.assertEqual(hdr.modbus_mirror[4], 650)
            self.assertAlmostEqual(hdr.line_speed_mps, 2.38, places=2)
            shm.close()

            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_roundtrip())


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCyberPhysicalPipeline)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
