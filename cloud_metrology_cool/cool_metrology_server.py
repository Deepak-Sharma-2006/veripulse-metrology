"""
VeriPulse COOL Metrology Server
===============================
FastAPI microservice exposing Cloud-Optimized OpenCV Library (COOL v3.1) metrology on port 8000.
Endpoints:
  - GET  /health: Service status, engine architecture, and KleidiCV status.
  - POST /verify_crop: Multi-scale morphological and contour verification on WebP crops.
"""

import os
import sys
import base64
import logging
import platform
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cloud_metrology_cool.cool_spatial_verifier import (
    verify_micro_crop,
    ENGINE_NAME,
    HAS_NATIVE_COOL,
    FORCE_FALLBACK,
)
import cv2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [COOL-SERVER] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("CoolMetrologyServer")

app = FastAPI(
    title="VeriPulse COOL Metrology Microservice",
    description="High-throughput spatial and morphological verification engine powered by COOL v3.1 and Arm KleidiCV.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MicroCropROI(BaseModel):
    format: Optional[str] = "webp"
    encoding: Optional[str] = "base64"
    dimensions: Optional[Dict[str, int]] = None
    data: Optional[str] = None


class VerifyCropRequest(BaseModel):
    micro_crop_roi: Optional[MicroCropROI] = None
    data: Optional[str] = None
    crop_b64: Optional[str] = None
    signature_id: Optional[str] = None


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """Returns microservice health, target architecture, and OpenCV acceleration engine."""
    return {
        "status": "ok",
        "service": "VeriPulse COOL Metrology Microservice",
        "engine": ENGINE_NAME,
        "platform": platform.machine(),
        "arm64_native": HAS_NATIVE_COOL,
        "fallback_mode": FORCE_FALLBACK or not HAS_NATIVE_COOL,
        "opencv_version": getattr(cv2, "__version__", "5.0.0"),
    }


def process_verify_crop_bytes(raw_bytes: bytes) -> Dict[str, Any]:
    """Helper to verify raw WebP bytes directly."""
    return verify_micro_crop(raw_bytes)


def process_verify_crop_payload(body: Any) -> Dict[str, Any]:
    """Helper to verify dict, str, or bytes payload directly."""
    if isinstance(body, bytes):
        return verify_micro_crop(body)

    b64_str = None
    if isinstance(body, dict):
        if "micro_crop_roi" in body and isinstance(body["micro_crop_roi"], dict):
            b64_str = body["micro_crop_roi"].get("data")
        elif "data" in body:
            b64_str = body.get("data")
        elif "crop_b64" in body:
            b64_str = body.get("crop_b64")
    elif isinstance(body, str):
        b64_str = body

    if not b64_str:
        raise ValueError("Payload missing micro_crop_roi.data or base64 WebP content.")

    webp_bytes = base64.b64decode(b64_str)
    return verify_micro_crop(webp_bytes)


@app.post("/verify_crop", status_code=status.HTTP_200_OK)
async def verify_crop_endpoint(request: Request) -> Dict[str, Any]:
    """
    Ingests either:
      1. JSON anomaly payload with base64 encoded micro_crop_roi
      2. Raw binary WebP bytes via multipart or octet-stream
    Executes KleidiCV multi-scale morphological verification and returns metrological verdict.
    """
    content_type = request.headers.get("content-type", "").lower()
    webp_bytes: Optional[bytes] = None

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

        try:
            return process_verify_crop_payload(body)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process crop payload: {e}")
    else:
        # Binary bytes upload
        webp_bytes = await request.body()
        if not webp_bytes or len(webp_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty WebP payload received.")
        return verify_micro_crop(webp_bytes)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="VeriPulse COOL Metrology Microservice")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Listening port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code change")
    args = parser.parse_args()

    logger.info("Starting COOL Metrology Microservice on %s:%d (Engine: %s)...", args.host, args.port, ENGINE_NAME)
    uvicorn.run("cloud_metrology_cool.cool_metrology_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
