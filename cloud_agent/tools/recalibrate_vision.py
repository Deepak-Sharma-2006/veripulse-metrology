"""
VeriPulse Active Agentic Vision Recalibration Tool
==================================================
Dynamically tunes edge OpenCV 5 G-API pipeline parameters to eliminate false rejects
caused by substrate foil reflectivity changes or specular lighting variations,
without graph recompilation.

Modifies bilateral spatial/range sigmas and Scharr gradient thresholds directly
in the active shared memory block (veripulse_shm_v1).
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional

# Ensure project root in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from edge_vision.shm_common import (
    SHM_NAME,
    HEADER_SIZE,
    VeriPulseHeader,
    get_or_create_shm,
)

logger = logging.getLogger("RecalibrateVision")


def recalibrate_gapi_vision(
    calibration_adjustments: Dict[str, Any],
    line_id: str = "line_04_lithium_anode",
    target_node_id: str = "fused_subpixel_edge_01",
    agent_visual_rationale: str = "",
) -> Dict[str, Any]:
    """
    Applies real-time calibration updates to the edge OpenCV G-API engine via shared memory.

    Args:
        calibration_adjustments: Target parameters:
            - bilateral_spatial_sigma (float, e.g. 1.8 to 2.5)
            - bilateral_range_sigma (float, e.g. 0.08 to 0.15)
            - scharr_gradient_threshold (float, e.g. 45.0 to 60.0)
            - specular_glare_threshold (float, optional, e.g. 180.0 to 220.0)
        line_id: Production line ID.
        target_node_id: Vision pipeline node ID.
        agent_visual_rationale: Reasoning from Bedrock Claude 3.5 Sonnet.

    Returns:
        dict: Recalibration confirmation with previous and new calibration vectors.
    """
    logger.info("Recalibrating G-API Vision Pipeline on %s (Node: %s)...", line_id, target_node_id)

    # Defaults from config
    new_spatial_sigma = float(calibration_adjustments.get("bilateral_spatial_sigma", 1.8))
    new_range_sigma = float(calibration_adjustments.get("bilateral_range_sigma", 0.08))
    new_scharr = float(calibration_adjustments.get("scharr_gradient_threshold", 45.0))
    new_glare = float(calibration_adjustments.get("specular_glare_threshold", 200.0))

    shm_updated = False
    prev_calib = (1.8, 0.08, 45.0, 180.0)
    shm_obj = None

    try:
        # Try connecting to existing shared memory ring buffer
        try:
            shm_obj = get_or_create_shm(create=False)
        except (FileNotFoundError, Exception):
            # Create if not currently initialized by edge_runner
            shm_obj = get_or_create_shm(create=True)

        buf = shm_obj.buf
        existing_header_bytes = bytes(buf[:HEADER_SIZE])
        
        try:
            header = VeriPulseHeader.unpack(existing_header_bytes)
            prev_calib = header.vision_calib
        except Exception:
            header = VeriPulseHeader()

        # Update calibration vector in header
        header.vision_calib = (new_spatial_sigma, new_range_sigma, new_scharr, new_glare)
        header.alert_flags |= 0x08  # Set Bit 3: Cloud Healer Recalibration Active
        header.timestamp_ns = time.time_ns()

        # Write back packed header to SHM offset 0..1024
        buf[:HEADER_SIZE] = header.pack()
        shm_updated = True
        logger.info(
            "Shared memory (%s) successfully updated with new calibration: %s",
            SHM_NAME,
            header.vision_calib,
        )
    except Exception as e:
        logger.warning("Could not write directly to shared memory: %s (running in virtualized mode)", e)
        shm_updated = False
    finally:
        if shm_obj is not None:
            try:
                shm_obj.close()
            except Exception:
                pass

    return {
        "status": "success",
        "action": "recalibrate_gapi_vision_pipeline",
        "line_id": line_id,
        "target_node_id": target_node_id,
        "timestamp_ns": time.time_ns(),
        "previous_calibration": {
            "bilateral_spatial_sigma": prev_calib[0],
            "bilateral_range_sigma": prev_calib[1],
            "scharr_gradient_threshold": prev_calib[2],
            "specular_glare_threshold": prev_calib[3],
        },
        "new_calibration": {
            "bilateral_spatial_sigma": new_spatial_sigma,
            "bilateral_range_sigma": new_range_sigma,
            "scharr_gradient_threshold": new_scharr,
            "specular_glare_threshold": new_glare,
        },
        "shm_name": SHM_NAME,
        "shm_updated": shm_updated,
        "agent_visual_rationale": agent_visual_rationale,
    }


if __name__ == "__main__":
    res = recalibrate_gapi_vision(
        calibration_adjustments={
            "bilateral_spatial_sigma": 2.2,
            "bilateral_range_sigma": 0.12,
            "scharr_gradient_threshold": 55.0,
            "specular_glare_threshold": 210.0,
        },
        agent_visual_rationale="Foil surface shows elevated specular glare without harmonic ribbing. Widening bilateral spatial kernel and raising Scharr threshold.",
    )
    print(res)
