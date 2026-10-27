"""
VeriPulse AWS Lambda MQTT Ingress Trigger
=========================================
Production serverless bridge connecting AWS IoT Core MQTT anomaly alerts to the
AWS Bedrock Autonomous Metrology Agent and Graviton COOL verification service.

IoT Core Routing Rule:
  SELECT * FROM 'veripulse/plants/+/lines/+/anomaly_payload'
  WHERE visual_anomaly.specular_saturation_ratio > 0.80
     OR spatial_fft_harmonics.spectral_power_db > 30.0

Egress Actuation Topic:
  veripulse/plants/{plant_id}/lines/{line_id}/actuation_command
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any

# Ensure project root in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from cloud_agent.bedrock_metrology_agent import run_metrology_agent
from cloud_metrology_cool.cool_spatial_verifier import generate_test_micro_crop
import base64

logger = logging.getLogger("LambdaMQTTTrigger")
logger.setLevel(logging.INFO)

IOT_DATA_ENDPOINT = os.getenv("AWS_IOT_DATA_ENDPOINT", "")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODE = os.getenv("VERIPULSE_MODE", "DRY_RUN").upper()


def get_iot_client():
    """Initializes AWS IoT Data client if endpoint is configured."""
    if IOT_DATA_ENDPOINT and MODE == "LIVE":
        return boto3.client("iot-data", endpoint_url=f"https://{IOT_DATA_ENDPOINT}", region_name=REGION)
    return None


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AWS Lambda entry point for IoT Core MQTT messages.
    Processes anomalous edge payload, invokes Bedrock agent, and returns healing command.
    """
    t_start = time.perf_counter()
    logger.info("Received anomaly payload event: %s", json.dumps(event, default=str)[:200])

    # Extract plant and line identifiers
    header = event.get("header", {})
    plant_id = header.get("plant_id", "plant_01")
    line_id = header.get("line_id", "line_04_lithium_anode")
    sig_id = header.get("signature_id", f"sig_{int(time.time())}")

    # Invoke the Bedrock Metrology Healer
    healing_report = run_metrology_agent(anomaly_payload=event, mode_override=MODE)

    # Prepare outbound MQTT actuation command
    actuation_payload = {
        "event_type": "supervisory_healing_command",
        "signature_id": sig_id,
        "plant_id": plant_id,
        "line_id": line_id,
        "timestamp_ns": time.time_ns(),
        "selected_tool": healing_report.get("selected_tool"),
        "tool_input": healing_report.get("tool_input"),
        "tool_result": healing_report.get("tool_result"),
        "agent_reasoning": healing_report.get("agent_reasoning"),
        "latency_metrics": healing_report.get("latency_metrics"),
        "settling_time_budget_met": healing_report.get("settling_time_budget_met"),
    }

    egress_topic = f"veripulse/plants/{plant_id}/lines/{line_id}/actuation_command"

    # Publish to AWS IoT Core broker if client is available
    iot_client = get_iot_client()
    published_to_broker = False
    if iot_client is not None:
        try:
            iot_client.publish(
                topic=egress_topic,
                qos=1,
                payload=json.dumps(actuation_payload).encode("utf-8"),
            )
            published_to_broker = True
            logger.info("Actuation published to IoT Core topic: %s", egress_topic)
        except Exception as e:
            logger.warning("Failed to publish actuation to IoT Core: %s", e)

    t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    return {
        "statusCode": 200,
        "body": {
            "status": "success",
            "egress_topic": egress_topic,
            "published_to_broker": published_to_broker,
            "healing_report": healing_report,
            "lambda_duration_ms": round(t_elapsed_ms, 2),
        },
    }


if __name__ == "__main__":
    # Test local execution with synthetic glare payload
    test_crop_b64 = base64.b64encode(generate_test_micro_crop("glare")).decode("utf-8")
    test_event = {
        "header": {
            "signature_id": "sig_lambda_test_01",
            "plant_id": "plant_01",
            "line_id": "line_04_lithium_anode",
            "timestamp_ns": time.time_ns(),
            "line_speed_mps": 2.50,
        },
        "visual_anomaly": {
            "anomaly_type": "surface_reflectance_anomaly",
            "specular_saturation_ratio": 0.85,
        },
        "spatial_fft_harmonics": {
            "fundamental_ribbing_freq_hz": 0.0,
            "spectral_power_db": 10.0,
        },
        "micro_crop_roi": {
            "format": "webp",
            "encoding": "base64",
            "data": test_crop_b64,
        },
    }

    res = lambda_handler(test_event)
    print(json.dumps(res, indent=2))
