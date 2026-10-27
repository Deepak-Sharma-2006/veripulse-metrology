"""
VeriPulse Cloud Metrology & Bedrock Agent Test Suite
===================================================
End-to-end unit and integration test suite validating:
  1. COOL Spatial Verifier: Arm KleidiCV / Emulation multi-scale morphological metrics
  2. COOL Metrology Server: FastAPI health and crop verification endpoints
  3. COOL vs. x86 Benchmark: Empirical deltas (28% lower latency, 40% cost reduction)
  4. Causal Physics Safety Gate: Envelope checks, slew rate limits, resonance shift, critical damping
  5. PLC Commander Tool: Float to Modbus INT16 mapping, HMAC-SHA256 signing
  6. Recalibrate Vision Tool: Shared memory (veripulse_shm_v1) bilateral/Scharr updates
  7. SCADA Historian Tool: SQLite WAL telemetry queries and trend analysis
  8. Bedrock Metrology Agent: Single-turn multimodal tool calling in DRY_RUN mode
  9. Lambda MQTT Trigger: Serverless event ingress and actuation formatting
"""

import os
import sys
import json
import time
import base64
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cloud_metrology_cool.cool_spatial_verifier import (
    verify_micro_crop,
    generate_test_micro_crop,
    ENGINE_NAME,
)
from cloud_metrology_cool.cool_metrology_server import (
    health_check,
    process_verify_crop_payload,
)
from cloud_metrology_cool.benchmark_cool_vs_x86 import (
    REFERENCE_BENCHMARKS,
    compute_comparative_deltas,
    run_local_empirical_benchmark,
)
from cloud_agent.tools.causal_physics import (
    validate_physics_safety,
    calculate_resonance_shift,
    calculate_dancer_damping,
)
from cloud_agent.tools.plc_commander import execute_plc_recalibration
from cloud_agent.tools.recalibrate_vision import recalibrate_gapi_vision
from cloud_agent.tools.scada_historian import (
    init_scada_db,
    seed_nominal_telemetry_if_empty,
    query_scada_trends,
    record_scada_sample,
)
from cloud_agent.bedrock_metrology_agent import run_metrology_agent
from cloud_agent.lambda_mqtt_trigger import lambda_handler
from plc_bridge.modbus_client_bridge import verify_actuation_payload, DEFAULT_HMAC_SECRET


class TestCloudMetrologyAndAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_scada_db()
        seed_nominal_telemetry_if_empty()

    def test_01_cool_spatial_verifier_morphological_metrics(self):
        """Verifies multi-scale contour and morphological verification across defect types."""
        # 1. Specular Glare: high solidity, low Gabor energy ratio, suspected glare verdict
        glare_bytes = generate_test_micro_crop("glare")
        res_glare = verify_micro_crop(glare_bytes)
        self.assertEqual(res_glare["verdict"], "specular_reflection_suspected")
        self.assertGreaterEqual(res_glare["morphological_solidity"], 0.85)
        self.assertLessEqual(res_glare["gabor_energy_ratio"], 0.20)
        self.assertIn("execution_time_ms", res_glare)

        # 2. 142.5 Hz Ribbing: high periodic Gabor energy, ribbing verdict
        ribbing_bytes = generate_test_micro_crop("ribbing")
        res_ribbing = verify_micro_crop(ribbing_bytes)
        self.assertEqual(res_ribbing["verdict"], "physical_defect_ribbing")
        self.assertGreaterEqual(res_ribbing["gabor_energy_ratio"], 0.40)

        # 3. Pinhole: localized defect, pinhole verdict
        pinhole_bytes = generate_test_micro_crop("pinhole")
        res_pinhole = verify_micro_crop(pinhole_bytes)
        self.assertEqual(res_pinhole["verdict"], "physical_defect_pinhole")

        # 4. Nominal Surface: nominal verdict
        nominal_bytes = generate_test_micro_crop("nominal")
        res_nominal = verify_micro_crop(nominal_bytes)
        self.assertEqual(res_nominal["verdict"], "nominal_surface")

    def test_02_cool_metrology_server_helpers(self):
        """Verifies FastAPI health check and crop verification payload parsing."""
        health = health_check()
        self.assertEqual(health["status"], "ok")
        self.assertIn("engine", health)
        self.assertIn("opencv_version", health)

        # JSON payload verification
        glare_b64 = base64.b64encode(generate_test_micro_crop("glare")).decode("utf-8")
        payload = {"micro_crop_roi": {"format": "webp", "data": glare_b64}}
        verified = process_verify_crop_payload(payload)
        self.assertEqual(verified["verdict"], "specular_reflection_suspected")

    def test_03_benchmark_cool_vs_x86_deltas(self):
        """Validates 28% latency reduction and 40% cost reduction deltas."""
        x86_ref = REFERENCE_BENCHMARKS["aws_x86_c6i_xlarge"]
        arm_ref = REFERENCE_BENCHMARKS["aws_graviton3_cool_c7g_xlarge"]
        deltas = compute_comparative_deltas(x86_ref, arm_ref)

        self.assertGreaterEqual(deltas["latency_reduction_percent"], 28.0)
        self.assertGreaterEqual(deltas["throughput_increase_percent"], 30.0)
        self.assertGreaterEqual(deltas["hourly_cost_reduction_percent"], 39.0)

        # Run minimal local empirical benchmark
        local_res = run_local_empirical_benchmark(iterations=10)
        self.assertGreater(local_res["throughput_rps"], 0)
        self.assertGreater(local_res["avg_latency_ms"], 0)

    def test_04_causal_physics_deterministic_safety_gate(self):
        """Tests hard boundary clamping, slew rate limits, resonance shift, and critical damping."""
        # 1. Valid corrective setpoints (nominal ribbing recalibration)
        valid_cmd = {"line_velocity_mps": 2.38, "dancer_damping_gain": 6.50}
        is_safe, clamped, viols, report = validate_physics_safety(valid_cmd, dt_sec=1.0)
        self.assertTrue(is_safe)
        self.assertEqual(len(viols), 0)
        self.assertEqual(clamped["velocity_mms"], 2380)
        self.assertEqual(clamped["dancer_dgain"], 650)
        self.assertTrue(report["resonance_analysis"]["resonance_broken"])
        self.assertTrue(report["damping_analysis"]["critically_damped"])
        self.assertLessEqual(report["settling_time_estimate_sec"], 1.0)

        # 2. Extreme out-of-boundary values: must clamp to safety bounds
        unsafe_cmd = {"line_velocity_mps": 5.0, "dancer_damping_gain": 15.0}
        is_safe, clamped, viols, report = validate_physics_safety(unsafe_cmd, dt_sec=1.0)
        self.assertFalse(is_safe)
        self.assertGreater(len(viols), 0)
        # Clamped along slew rate and safety boundaries
        self.assertLessEqual(clamped["velocity_mms"], 2750)
        self.assertLessEqual(clamped["dancer_dgain"], 700)

        # 3. Direct resonance calculation
        res_calc = calculate_resonance_shift(2380)
        self.assertTrue(res_calc["resonance_broken"])
        self.assertAlmostEqual(res_calc["delta_from_resonance_hz"], -6.84, delta=0.1)

    def test_05_plc_commander_mapping_and_hmac_signing(self):
        """Validates float to INT16 mapping, HMAC-SHA256 signing, and DRY_RUN execution."""
        setpoints = {
            "line_velocity_mps": 2.38,
            "dancer_damping_gain": 6.50,
            "web_tension_newtons": 145.0,
            "ir_dryer_temp_celsius": 120.0,
            "slurry_pump_rpm": 1200.0,
        }
        res = execute_plc_recalibration(
            engineering_setpoints=setpoints,
            line_id="line_04_lithium_anode",
            mode_override="DRY_RUN",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["mode"], "DRY_RUN")
        regs = res["holding_registers"]
        self.assertEqual(regs["velocity_mms"], 2380)
        self.assertEqual(regs["dancer_dgain"], 650)
        self.assertEqual(regs["tension_dn"], 1450)
        self.assertEqual(regs["temp_dc"], 1200)
        self.assertEqual(regs["pump_drpm"], 12000)

        # Verify HMAC-SHA256 signature
        sig = res["hmac_sha256_signature"]
        self.assertTrue(verify_actuation_payload(regs, sig, DEFAULT_HMAC_SECRET))

    def test_06_recalibrate_vision_shm_update(self):
        """Validates edge OpenCV G-API parameter updates in veripulse_shm_v1."""
        adjustments = {
            "bilateral_spatial_sigma": 2.4,
            "bilateral_range_sigma": 0.14,
            "scharr_gradient_threshold": 52.0,
            "specular_glare_threshold": 215.0,
        }
        res = recalibrate_gapi_vision(
            calibration_adjustments=adjustments,
            line_id="line_04_lithium_anode",
            agent_visual_rationale="Test glare recalibration",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["new_calibration"]["bilateral_spatial_sigma"], 2.4)
        self.assertEqual(res["new_calibration"]["scharr_gradient_threshold"], 52.0)
        self.assertTrue(res["shm_updated"])

    def test_07_scada_historian_queries(self):
        """Validates SQLite WAL telemetry persistence and trend analysis."""
        sample = {
            "line_id": "line_04_lithium_anode",
            "line_speed_mps": 2.50,
            "web_tension_n": 152.0,
            "dryer_temp_c": 121.0,
            "pump_rpm": 1205.0,
            "dancer_gain": 5.00,
        }
        record_scada_sample(sample)
        trends = query_scada_trends(window_sec=60)
        self.assertEqual(trends["status"], "success")
        self.assertGreater(trends["sample_count"], 0)
        self.assertIn("dryer_temp_slope_c_per_min", trends)
        self.assertIn("tension_variance_dn", trends)

    def test_08_bedrock_metrology_agent_glare_self_healing(self):
        """Validates Bedrock agent single-turn diagnosis on glare anomaly."""
        glare_crop_b64 = base64.b64encode(generate_test_micro_crop("glare")).decode("utf-8")
        payload = {
            "header": {
                "signature_id": "sig_test_glare_01",
                "timestamp_ns": time.time_ns(),
                "line_id": "line_04_lithium_anode",
                "line_speed_mps": 2.50,
            },
            "visual_anomaly": {
                "anomaly_type": "surface_reflectance_anomaly",
                "specular_saturation_ratio": 0.88,
            },
            "spatial_fft_harmonics": {
                "fundamental_ribbing_freq_hz": 0.0,
                "spectral_power_db": 8.5,
            },
            "prehydrated_scada_trends": {
                "rolling_window_sec": 60,
                "dryer_temp_slope_c_per_min": 1.45,
                "tension_variance_dn": 12.8,
                "pump_speed_rpm": 1200.0,
                "line_velocity_mps": 2.50,
            },
            "micro_crop_roi": {
                "format": "webp",
                "encoding": "base64",
                "dimensions": {"width": 256, "height": 128},
                "data": glare_crop_b64,
            },
        }

        report = run_metrology_agent(payload, mode_override="DRY_RUN")
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["selected_tool"], "recalibrate_gapi_vision_pipeline")
        self.assertEqual(
            report["cool_graviton_verification"]["verdict"],
            "specular_reflection_suspected",
        )
        self.assertTrue(report["settling_time_budget_met"])
        self.assertIn("tool_result", report)
        self.assertTrue(report["tool_result"].get("shm_updated"))

    def test_09_bedrock_metrology_agent_ribbing_self_healing(self):
        """Validates Bedrock agent single-turn diagnosis on 142.5 Hz ribbing defect."""
        ribbing_crop_b64 = base64.b64encode(generate_test_micro_crop("ribbing")).decode("utf-8")
        payload = {
            "header": {
                "signature_id": "sig_test_ribbing_01",
                "timestamp_ns": time.time_ns(),
                "line_id": "line_04_lithium_anode",
                "line_speed_mps": 2.50,
            },
            "visual_anomaly": {
                "anomaly_type": "ribbing_instability",
                "specular_saturation_ratio": 0.0,
            },
            "spatial_fft_harmonics": {
                "fundamental_ribbing_freq_hz": 142.50,
                "spectral_power_db": 44.3,
            },
            "prehydrated_scada_trends": {
                "rolling_window_sec": 60,
                "dryer_temp_slope_c_per_min": 1.45,
                "tension_variance_dn": 12.8,
                "pump_speed_rpm": 1200.0,
                "line_velocity_mps": 2.50,
            },
            "micro_crop_roi": {
                "format": "webp",
                "encoding": "base64",
                "dimensions": {"width": 256, "height": 128},
                "data": ribbing_crop_b64,
            },
        }

        report = run_metrology_agent(payload, mode_override="DRY_RUN")
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["selected_tool"], "execute_plc_recalibration")
        self.assertEqual(report["cool_graviton_verification"]["verdict"], "physical_defect_ribbing")
        self.assertTrue(report["settling_time_budget_met"])

        regs = report["tool_result"]["holding_registers"]
        self.assertEqual(regs["velocity_mms"], 2380)
        self.assertEqual(regs["dancer_dgain"], 650)
        self.assertTrue(report["tool_result"]["resonance_analysis"]["resonance_broken"])

    def test_10_lambda_mqtt_trigger_ingress(self):
        """Validates serverless Lambda MQTT handler."""
        crop_b64 = base64.b64encode(generate_test_micro_crop("glare")).decode("utf-8")
        event = {
            "header": {
                "signature_id": "sig_lambda_unit_test",
                "plant_id": "plant_01",
                "line_id": "line_04_lithium_anode",
                "line_speed_mps": 2.50,
            },
            "visual_anomaly": {
                "anomaly_type": "surface_reflectance_anomaly",
                "specular_saturation_ratio": 0.82,
            },
            "spatial_fft_harmonics": {"fundamental_ribbing_freq_hz": 0.0},
            "micro_crop_roi": {"format": "webp", "data": crop_b64},
        }
        res = lambda_handler(event)
        self.assertEqual(res["statusCode"], 200)
        self.assertEqual(res["body"]["status"], "success")
        self.assertIn("healing_report", res["body"])
        self.assertIn("veripulse/plants/plant_01/lines/line_04_lithium_anode/actuation_command", res["body"]["egress_topic"])


if __name__ == "__main__":
    unittest.main()
