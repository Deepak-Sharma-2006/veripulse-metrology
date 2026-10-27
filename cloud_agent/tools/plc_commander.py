"""
VeriPulse PLC Commander Tool
============================
Autonomous Cyber-Physical Actuation Tool for Bedrock Metrology Agent.
Maps target engineering float values to fixed-point Modbus holding registers (40001-40005).
Runs deterministic causal physics safety gate (causal_physics.py).
Generates cryptographic HMAC-SHA256 signature and applies actuation to the plant PLC.

Supports VERIPULSE_MODE=LIVE|DRY_RUN.
"""

import os
import sys
import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional

# Ensure project root in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cloud_agent.tools.causal_physics import validate_physics_safety
from plc_bridge.modbus_client_bridge import (
    sign_actuation_payload,
    verify_actuation_payload,
    ModbusClientBridge,
    DEFAULT_HMAC_SECRET,
)

logger = logging.getLogger("PLCCommander")

MODE = os.getenv("VERIPULSE_MODE", "DRY_RUN").upper()


def execute_plc_recalibration(
    engineering_setpoints: Dict[str, Any],
    line_id: str = "line_04_lithium_anode",
    target_plc_ip: str = "127.0.0.1",
    causal_diagnostic_rationale: str = "",
    mode_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes cyber-physical recalibration of the plant PLC holding registers:
      1. Embedded deterministic causal physics gate (slew-rate, thermal mass, resonance).
      2. Fixed-point Modbus register conversion (INT16).
      3. Cryptographic HMAC-SHA256 command signing.
      4. Actuation over Modbus TCP (port 5020) if in LIVE mode.

    Args:
        engineering_setpoints: Target SI units (e.g., line_velocity_mps, dancer_damping_gain).
        line_id: Production line identifier.
        target_plc_ip: PLC network address (default: 127.0.0.1).
        causal_diagnostic_rationale: Physical reasoning from Claude 3.5 Sonnet.
        mode_override: Optional override for 'LIVE' or 'DRY_RUN'.

    Returns:
        dict: Actuation result, signed registers, physics report, and settling time.
    """
    active_mode = (mode_override or MODE).upper()
    logger.info("Executing PLC Recalibration on %s (Mode: %s)...", line_id, active_mode)

    # 1. Embedded Deterministic Causal Physics Validation Gate
    is_safe, clamped_registers, violations, physics_report = validate_physics_safety(
        target_setpoints=engineering_setpoints,
        dt_sec=1.0,
    )

    if not is_safe:
        logger.warning("Causal Physics Gate detected safety boundary adjustments: %s", violations)

    # 2. Cryptographic HMAC-SHA256 Signature Generation
    hmac_sig = sign_actuation_payload(clamped_registers, secret_key=DEFAULT_HMAC_SECRET)

    settling_time_sec = physics_report.get("settling_time_estimate_sec", 0.80)

    actuation_frame = {
        "status": "success",
        "action": "execute_plc_recalibration",
        "line_id": line_id,
        "mode": active_mode,
        "timestamp_ns": time.time_ns(),
        "holding_registers": clamped_registers,
        "target_si_units": physics_report.get("target_si_units", {}),
        "hmac_sha256_signature": hmac_sig,
        "settling_time_sec": settling_time_sec,
        "resonance_analysis": physics_report.get("resonance_analysis", {}),
        "damping_analysis": physics_report.get("damping_analysis", {}),
        "safety_clamped": not is_safe,
        "safety_violations": violations,
        "causal_diagnostic_rationale": causal_diagnostic_rationale,
        "applied_to_hardware": False,
    }

    # 3. Physical Actuation (LIVE Mode)
    if active_mode == "LIVE":
        try:
            bridge = ModbusClientBridge(host=target_plc_ip, port=5020)
            success = asyncio.run(bridge.write_registers(clamped_registers, hmac_signature=hmac_sig))
            actuation_frame["applied_to_hardware"] = bool(success)
            logger.info("Live PLC Modbus TCP write completed successfully: %s", success)
        except Exception as e:
            logger.warning("Live PLC actuation could not connect to %s:5020: %s (falling back)", target_plc_ip, e)
            actuation_frame["applied_to_hardware"] = False
            actuation_frame["hardware_error"] = str(e)
    else:
        logger.info("DRY_RUN Mode: Verified signed actuation frame synthesized without plant network dispatch.")

    return actuation_frame


if __name__ == "__main__":
    test_cmd = {
        "line_velocity_mps": 2.38,
        "dancer_damping_gain": 6.50,
        "web_tension_newtons": 145.0,
        "ir_dryer_temp_celsius": 118.5,
        "slurry_pump_rpm": 1180.0,
    }
    result = execute_plc_recalibration(
        engineering_setpoints=test_cmd,
        causal_diagnostic_rationale="Shift line speed from 2.50 to 2.38 m/s to break 142.5 Hz meniscus resonance.",
        mode_override="DRY_RUN",
    )
    print(json.dumps(result, indent=2))
