"""
VeriPulse AWS Bedrock Agent Tool Schema & Single-Turn Reasoning Test Suite
=========================================================================
Validates:
  1. aws_bedrock_agent_spec.json OpenAPI and tool calling schema specifications.
  2. Concrete tool execution and bounds validation:
     - recalibrate_gapi_vision_pipeline
     - execute_plc_recalibration (HMAC signing + safety envelope clamping)
     - query_scada_historian
     - validate_physics_safety
  3. Single-turn multimodal reasoning in DRY_RUN mode meeting <= 3.5s latency budget.
"""

import os
import sys
import json
import time
import base64
import unittest
from typing import Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cloud_agent.bedrock_metrology_agent import (
    load_agent_spec,
    get_bedrock_tool_config,
    run_metrology_agent,
    dispatch_tool_execution,
)
from cloud_agent.tools.causal_physics import validate_physics_safety
from cloud_agent.tools.plc_commander import execute_plc_recalibration
from cloud_agent.tools.recalibrate_vision import recalibrate_gapi_vision
from cloud_agent.tools.scada_historian import query_scada_trends
from cloud_metrology_cool.cool_spatial_verifier import generate_test_micro_crop


class TestBedrockToolCalling(unittest.TestCase):
    def setUp(self):
        self.spec = load_agent_spec()

    def test_01_bedrock_agent_specification_schema(self):
        """Validates that aws_bedrock_agent_spec.json adheres to Bedrock Action Group schemas."""
        self.assertIn("agent_name", self.spec)
        self.assertIn("model_id", self.spec)

        tool_config = get_bedrock_tool_config()
        self.assertIn("tools", tool_config)
        tools = tool_config["tools"]
        self.assertGreaterEqual(len(tools), 3)

        tool_names = [t["toolSpec"]["name"] for t in tools]
        self.assertIn("recalibrate_gapi_vision_pipeline", tool_names)
        self.assertIn("execute_plc_recalibration", tool_names)
        self.assertIn("query_scada_historian", tool_names)

    def test_02_converse_tool_config_formatting(self):
        """Validates dynamic conversion of OpenAPI spec to AWS Bedrock Converse API format."""
        tool_config = get_bedrock_tool_config()
        self.assertIn("tools", tool_config)
        tools = tool_config["tools"]

        for t in tools:
            spec = t["toolSpec"]
            self.assertIn("name", spec)
            self.assertIn("description", spec)
            self.assertIn("inputSchema", spec)
            self.assertEqual(spec["inputSchema"].get("json", {}).get("type"), "object")

    def test_03_recalibrate_vision_tool(self):
        """Validates active agentic recalibrate_vision execution."""
        calib = {
            "bilateral_spatial_sigma": 2.2,
            "bilateral_range_sigma": 0.10,
            "scharr_gradient_threshold": 52.0,
            "specular_glare_threshold": 195.0,
        }
        res = recalibrate_gapi_vision(calibration_adjustments=calib)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["new_calibration"]["bilateral_spatial_sigma"], 2.2)
        self.assertEqual(res["new_calibration"]["scharr_gradient_threshold"], 52.0)

    def test_04_execute_plc_recalibration_tool(self):
        """Validates PLC command dispatch, HMAC cryptographic signing, and safety envelopes."""
        setpoints = {
            "line_velocity_mps": 2.38,
            "dancer_damping_gain": 6.50,
            "web_tension_newtons": 145.0,
            "ir_dryer_temp_celsius": 118.5,
            "slurry_pump_rpm": 1180.0,
        }
        res = execute_plc_recalibration(engineering_setpoints=setpoints, mode_override="DRY_RUN")
        self.assertEqual(res["status"], "success")
        self.assertIn("hmac_sha256_signature", res)
        self.assertEqual(res["holding_registers"]["velocity_mms"], 2380)
        self.assertEqual(res["holding_registers"]["dancer_dgain"], 650)

        # Dispatch via tool router
        routed = dispatch_tool_execution(
            "execute_plc_recalibration",
            {"engineering_setpoints": setpoints},
            mode="DRY_RUN",
        )
        self.assertEqual(routed["status"], "success")

    def test_05_scada_historian_and_causal_physics_tools(self):
        """Validates SCADA historian time-series queries and causal physics constraint checking."""
        scada_res = query_scada_trends(window_sec=60)
        self.assertIn("status", scada_res)
        self.assertIn("line_id", scada_res)
        self.assertIn("pump_speed_rpm", scada_res)

        # Valid physics configuration
        safe, clamped, violations, report = validate_physics_safety(
            {"velocity_mms": 2380, "dancer_dgain": 650}
        )
        self.assertTrue(safe)
        self.assertEqual(len(violations), 0)

        # Hazardous physics configuration: beyond safety envelope
        unsafe, clamped_u, violations_u, report_u = validate_physics_safety(
            {"velocity_mms": 3800, "dancer_dgain": 1200}
        )
        self.assertFalse(unsafe)
        self.assertGreater(len(violations_u), 0)

    def test_06_single_turn_reasoning_and_budget(self):
        """Validates single-turn DRY_RUN agent decision and supervisory settling latency (<= 3.5s)."""
        raw_crop = generate_test_micro_crop("glare")
        b64_crop = base64.b64encode(raw_crop).decode("utf-8")

        anomaly_payload = {
            "header": {
                "signature_id": "test_sig_001",
                "timestamp_ns": time.time_ns(),
                "line_id": "line_04_lithium_anode",
                "line_speed_mps": 2.50,
                "frame_index": 12000,
            },
            "visual_anomaly": {
                "anomaly_type": "surface_reflectance_anomaly",
                "specular_saturation_ratio": 0.85,
                "mean_intensity": 182.0,
            },
            "spatial_fft_harmonics": {
                "fundamental_ribbing_freq_hz": 0.0,
                "spectral_power_db": 10.0,
            },
            "prehydrated_scada_trends": {
                "rolling_window_sec": 60,
                "dryer_temp_slope_c_per_min": 1.2,
                "tension_variance_dn": 10.0,
                "pump_speed_rpm": 1200.0,
                "line_velocity_mps": 2.50,
            },
            "micro_crop_roi": {
                "format": "webp",
                "encoding": "base64",
                "dimensions": {"width": 256, "height": 128},
                "data": b64_crop,
            },
        }

        report = run_metrology_agent(anomaly_payload, mode_override="DRY_RUN")
        self.assertEqual(report["selected_tool"], "recalibrate_gapi_vision_pipeline")
        self.assertTrue(report["settling_time_budget_met"])
        self.assertLessEqual(
            report["latency_metrics"]["total_supervisory_latency_ms"], 3500.0
        )


if __name__ == "__main__":
    unittest.main()
