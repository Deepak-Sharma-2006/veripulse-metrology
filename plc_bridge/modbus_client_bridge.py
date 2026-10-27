"""
VeriPulse Modbus TCP Client Bridge
==================================
Secure cyber-physical actuation client connecting to the plant PLC (localhost:5020).
Features:
  - Cryptographic HMAC-SHA256 signature generation and verification.
  - Multi-tier deterministic safety bounding and interlock clamping.
  - Conversion between raw INT16 Modbus fixed-point registers and SI engineering units.
  - Asynchronous and synchronous client APIs.
"""

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import argparse
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union

# PyModbus 3.5+ client imports
from pymodbus.client import AsyncModbusTcpClient, ModbusTcpClient

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "modbus_register_map.json")

# Default secret key for plant-floor HMAC command authentication
DEFAULT_HMAC_SECRET = os.getenv("VERIPULSE_HMAC_SECRET", "veripulse-plc-cyberphysical-token-v1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [PLC-CLIENT] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ModbusClientBridge")


class SecurityVerificationError(Exception):
    """Raised when an actuation payload fails HMAC-SHA256 signature verification."""
    pass


class SafetyInterlockViolationError(Exception):
    """Raised when an actuation command violates physical hardware safety limits."""
    pass


def load_register_map() -> Dict[str, Any]:
    """Loads register limits and scaling metadata from config."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read register map from %s: %s", CONFIG_PATH, e)
    return {}


def canonicalize_registers(registers_dict: Dict[str, Any]) -> bytes:
    """Produces deterministic UTF-8 canonical JSON bytes for hashing."""
    # Retain strictly the core 5 holding register keys if present
    canonical_keys = ["velocity_mms", "tension_dn", "temp_dc", "pump_drpm", "dancer_dgain"]
    filtered = {k: registers_dict[k] for k in canonical_keys if k in registers_dict}
    if not filtered:
        filtered = registers_dict
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_actuation_payload(registers_dict: Dict[str, Any], secret_key: str = DEFAULT_HMAC_SECRET) -> str:
    """Computes HMAC-SHA256 hex digest for holding registers payload."""
    canonical_bytes = canonicalize_registers(registers_dict)
    secret_bytes = secret_key.encode("utf-8")
    return hmac.new(secret_bytes, canonical_bytes, hashlib.sha256).hexdigest()


def verify_actuation_payload(
    registers_dict: Dict[str, Any],
    provided_signature: str,
    secret_key: str = DEFAULT_HMAC_SECRET,
) -> bool:
    """Verifies that the provided HMAC matches the registers dictionary."""
    expected_sig = sign_actuation_payload(registers_dict, secret_key=secret_key)
    return hmac.compare_digest(expected_sig, provided_signature)


class ModbusClientBridge:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5020,
        unit_id: int = 1,
        secret_key: str = DEFAULT_HMAC_SECRET,
        enforce_safety: bool = True,
    ):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.secret_key = secret_key
        self.enforce_safety = enforce_safety
        self.reg_config = load_register_map().get("holding_registers", {})

    async def _get_async_client(self) -> AsyncModbusTcpClient:
        client = AsyncModbusTcpClient(self.host, port=self.port)
        await client.connect()
        return client

    async def read_registers(self, address: int = 0, count: int = 5) -> Dict[str, Any]:
        """
        Reads holding registers from the simulated PLC server.
        Returns both raw register integers and engineering SI units.
        """
        client = await self._get_async_client()
        try:
            # PyModbus 3.8+ uses device_id, older uses slave
            try:
                rr = await client.read_holding_registers(address, count=count, device_id=self.unit_id)
            except TypeError:
                rr = await client.read_holding_registers(address, count=count, slave=self.unit_id)

            if rr.isError():
                raise IOError(f"Modbus read error: {rr}")

            raw = list(rr.registers)
            padded = raw + [0] * max(0, 5 - len(raw))

            result = {
                "raw": raw,
                "velocity_mms": padded[0],
                "tension_dn": padded[1],
                "temp_dc": padded[2],
                "pump_drpm": padded[3],
                "dancer_dgain": padded[4],
                "engineering_units": {
                    "line_velocity_mps": padded[0] / 1000.0,
                    "web_tension_n": padded[1] / 10.0,
                    "ir_dryer_temp_c": padded[2] / 10.0,
                    "slurry_pump_rpm": padded[3] / 10.0,
                    "dancer_damping_gain": padded[4] / 100.0,
                },
                "timestamp_ns": time.time_ns(),
            }
            return result
        finally:
            client.close()

    def clamp_safety_bounds(self, registers_dict: Dict[str, int]) -> Dict[str, int]:
        """
        Validates values against safety envelopes defined in modbus_register_map.json.
        """
        key_to_reg = {
            "velocity_mms": ("40001", 2250, 2750),
            "tension_dn": ("40002", 1250, 1750),
            "temp_dc": ("40003", 1050, 1350),
            "pump_drpm": ("40004", 10500, 13500),
            "dancer_dgain": ("40005", 300, 700),
        }

        clamped = dict(registers_dict)
        for key, (reg_id, fallback_min, fallback_max) in key_to_reg.items():
            if key in clamped:
                meta = self.reg_config.get(reg_id, {})
                s_min = meta.get("safety_min", fallback_min)
                s_max = meta.get("safety_max", fallback_max)
                val = clamped[key]
                if val < s_min or val > s_max:
                    clamped_val = max(s_min, min(s_max, val))
                    logger.warning(
                        "Safety Clamp Activated on %s: requested %d outside safety envelope [%d, %d]. Clamped to %d.",
                        key, val, s_min, s_max, clamped_val
                    )
                    clamped[key] = clamped_val
        return clamped

    async def write_registers(
        self,
        registers_dict: Dict[str, int],
        hmac_signature: Optional[str] = None,
        address: int = 0,
    ) -> bool:
        """
        Verifies HMAC signature, clamps to physical safety envelope, and writes to PLC.
        """
        # Step 1: Cryptographic HMAC-SHA256 signature verification
        if hmac_signature is not None:
            if not verify_actuation_payload(registers_dict, hmac_signature, self.secret_key):
                raise SecurityVerificationError(
                    f"HMAC-SHA256 signature verification failed for payload: {registers_dict}"
                )
            logger.info("HMAC-SHA256 command signature verified successfully.")
        else:
            logger.warning("Actuation command submitted without signature (internal development mode).")

        # Step 2: Safety envelope validation & clamping
        if self.enforce_safety:
            validated = self.clamp_safety_bounds(registers_dict)
        else:
            validated = registers_dict

        # Step 3: Map dictionary to ordered list [40001..40005]
        # First read current registers to preserve untouched values
        current = await self.read_registers(address=0, count=5)
        raw_values = [
            validated.get("velocity_mms", current["velocity_mms"]),
            validated.get("tension_dn", current["tension_dn"]),
            validated.get("temp_dc", current["temp_dc"]),
            validated.get("pump_drpm", current["pump_drpm"]),
            validated.get("dancer_dgain", current["dancer_dgain"]),
        ]

        # Step 4: Write to PLC over Modbus TCP
        client = await self._get_async_client()
        try:
            try:
                wr = await client.write_registers(address, raw_values, device_id=self.unit_id)
            except TypeError:
                wr = await client.write_registers(address, raw_values, slave=self.unit_id)

            if wr.isError():
                raise IOError(f"Modbus write failed: {wr}")

            logger.info("Successfully actuated PLC holding registers: %s", raw_values)
            return True
        finally:
            client.close()

    async def apply_actuation_frame(self, frame: Dict[str, Any]) -> bool:
        """
        Ingests a full Bedrock or Gateway actuation frame (e.g., from Bedrock Healer):
        {
          "type": "plc_update",
          "holding_registers": { ... },
          "hmac_sha256_signature": "..."
        }
        """
        regs = frame.get("holding_registers", {})
        sig = frame.get("hmac_sha256_signature")
        return await self.write_registers(regs, hmac_signature=sig)


def main():
    parser = argparse.ArgumentParser(description="VeriPulse Modbus TCP Client Bridge")
    parser.add_argument("--host", default="127.0.0.1", help="PLC Server Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5020, help="PLC Modbus Port (default: 5020)")
    parser.add_argument("--read", action="store_true", help="Read holding registers")
    parser.add_argument("--write-velocity", type=int, help="Write Line Velocity (mm/s)")
    parser.add_argument("--write-dancer-gain", type=int, help="Write Dancer Gain (0.01 Gain)")
    parser.add_argument("--sign-sample", action="store_true", help="Generate valid HMAC-SHA256 signature for test payload")
    args = parser.parse_args()

    bridge = ModbusClientBridge(host=args.host, port=args.port)

    if args.sign_sample:
        sample_payload = {
            "velocity_mms": 2380,
            "tension_dn": 1450,
            "temp_dc": 1185,
            "pump_drpm": 11800,
            "dancer_dgain": 650,
        }
        sig = sign_actuation_payload(sample_payload)
        frame = {
            "type": "plc_update",
            "timestamp_ns": time.time_ns(),
            "holding_registers": sample_payload,
            "hmac_sha256_signature": sig,
            "actuator_settling_time_sec": 0.80,
        }
        print("Generated Signed Bedrock Actuation Payload:")
        print(json.dumps(frame, indent=2))
        return

    if args.read:
        res = asyncio.run(bridge.read_registers())
        print(json.dumps(res, indent=2))
        return

    if args.write_velocity is not None or args.write_dancer_gain is not None:
        cmd: Dict[str, int] = {}
        if args.write_velocity is not None:
            cmd["velocity_mms"] = args.write_velocity
        if args.write_dancer_gain is not None:
            cmd["dancer_dgain"] = args.write_dancer_gain
        sig = sign_actuation_payload(cmd)
        success = asyncio.run(bridge.write_registers(cmd, hmac_signature=sig))
        print(f"Write operation completed. Status: {success}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
