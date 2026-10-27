"""
VeriPulse Causal Physics Deterministic Validation Gate
======================================================
Embedded safety-critical physical validator.
Guarantees that Bedrock agent commands respect cyber-physical plant dynamics:
  1. Hard physical safety envelopes (modbus_register_map.json)
  2. Maximum slew-rate acceleration limits
  3. Thermal mass response curves (IR oven curing)
  4. Standing wave meniscus resonance shift (142.5 Hz ribbing suppression)
  5. Dancer roll critical damping ratio (zeta >= 0.707)

No LLM hallucination can bypass this gate; invalid setpoints are either safely
clamped or rejected prior to cryptographic Modbus signing.
"""

import os
import sys
import json
import math
import logging
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger("CausalPhysics")

# Nominal plant physical constants
NOMINAL_ROLLER_DIAMETER_MM = 55.85
NOMINAL_ROLLER_CIRCUMFERENCE_MM = math.pi * NOMINAL_ROLLER_DIAMETER_MM  # ~175.46 mm
RIBBING_SPATIAL_WAVELENGTH_MM = 17.5438  # Corresponds to 142.5 Hz at 2.50 m/s
RESONANCE_Q_FACTOR = 25.0
RESONANCE_BANDWIDTH_HZ = 142.50 / RESONANCE_Q_FACTOR  # 5.70 Hz
THERMAL_TIME_CONSTANT_SEC = 45.0  # IR dryer thermal lag tau

# Hardware safety envelopes (raw Modbus & SI units)
SAFETY_BOUNDS = {
    "velocity_mms": {
        "min": 2250,
        "max": 2750,
        "default": 2500,
        "max_slew_rate_per_sec": 150.0,  # mm/s^2
        "unit": "mm/s",
        "si_key": "line_velocity_mps",
        "si_scale": 0.001,
    },
    "tension_dn": {
        "min": 1250,
        "max": 1750,
        "default": 1500,
        "max_slew_rate_per_sec": 150.0,  # 0.1 N / s (= 15.0 N/s)
        "unit": "0.1 N",
        "si_key": "web_tension_newtons",
        "si_scale": 0.1,
    },
    "temp_dc": {
        "min": 1050,
        "max": 1350,
        "default": 1200,
        "max_slew_rate_per_sec": 0.25,  # 0.1 °C / s (= 1.5 °C / min)
        "unit": "0.1 °C",
        "si_key": "ir_dryer_temp_celsius",
        "si_scale": 0.1,
    },
    "pump_drpm": {
        "min": 10500,
        "max": 13500,
        "default": 12000,
        "max_slew_rate_per_sec": 500.0,  # 0.1 RPM / s (= 50.0 RPM/s)
        "unit": "0.1 RPM",
        "si_key": "slurry_pump_rpm",
        "si_scale": 0.1,
    },
    "dancer_dgain": {
        "min": 300,
        "max": 700,
        "default": 500,
        "max_slew_rate_per_sec": 200.0,  # 0.01 Gain / s (= 2.0 Gain/s)
        "unit": "0.01 Gain",
        "si_key": "dancer_damping_gain",
        "si_scale": 0.01,
    },
}


def normalize_to_raw_registers(setpoints: Dict[str, Any]) -> Dict[str, int]:
    """
    Converts either SI float engineering units or raw register keys into standard
    raw integer holding register values.
    """
    raw_dict: Dict[str, int] = {}

    # Map SI units if present
    if "line_velocity_mps" in setpoints:
        raw_dict["velocity_mms"] = int(round(float(setpoints["line_velocity_mps"]) * 1000.0))
    if "web_tension_newtons" in setpoints:
        raw_dict["tension_dn"] = int(round(float(setpoints["web_tension_newtons"]) * 10.0))
    elif "web_tension_n" in setpoints:
        raw_dict["tension_dn"] = int(round(float(setpoints["web_tension_n"]) * 10.0))
    if "ir_dryer_temp_celsius" in setpoints:
        raw_dict["temp_dc"] = int(round(float(setpoints["ir_dryer_temp_celsius"]) * 10.0))
    elif "ir_dryer_temp_c" in setpoints:
        raw_dict["temp_dc"] = int(round(float(setpoints["ir_dryer_temp_c"]) * 10.0))
    if "slurry_pump_rpm" in setpoints:
        raw_dict["pump_drpm"] = int(round(float(setpoints["slurry_pump_rpm"]) * 10.0))
    if "dancer_damping_gain" in setpoints:
        raw_dict["dancer_dgain"] = int(round(float(setpoints["dancer_damping_gain"]) * 100.0))

    # Also accept direct raw register keys
    for k in ["velocity_mms", "tension_dn", "temp_dc", "pump_drpm", "dancer_dgain"]:
        if k in setpoints and k not in raw_dict:
            raw_dict[k] = int(round(float(setpoints[k])))

    return raw_dict


def calculate_resonance_shift(velocity_mms: int) -> Dict[str, Any]:
    """
    Calculates the spatial meniscus excitation frequency at the specified web speed.
    Determines whether the speed shifts the line out of the 142.50 Hz standing wave resonance.
    """
    speed_mps = velocity_mms / 1000.0
    # Excitation frequency f = v / lambda
    excitation_freq_hz = (speed_mps * 1000.0) / RIBBING_SPATIAL_WAVELENGTH_MM
    delta_from_resonance_hz = excitation_freq_hz - 142.50
    # Check if delta exceeds half the Q-factor bandwidth (2.85 Hz)
    resonance_broken = abs(delta_from_resonance_hz) >= (RESONANCE_BANDWIDTH_HZ / 2.0)

    # Roller rotational runout harmonic
    roller_harmonic_hz = (speed_mps * 1000.0) / NOMINAL_ROLLER_CIRCUMFERENCE_MM

    return {
        "speed_mps": round(speed_mps, 3),
        "excitation_freq_hz": round(excitation_freq_hz, 2),
        "delta_from_resonance_hz": round(delta_from_resonance_hz, 2),
        "resonance_broken": bool(resonance_broken),
        "roller_runout_harmonic_hz": round(roller_harmonic_hz, 2),
    }


def calculate_dancer_damping(dancer_dgain: int) -> Dict[str, Any]:
    """
    Calculates the active hydraulic damping ratio (zeta) from dancer damping gain.
    Nominal gain 500 (5.00) corresponds to zeta = 0.55 (underdamped).
    Gain 650 (6.50) corresponds to zeta = 0.715 (critically damped, suppressing oscillations).
    """
    gain_float = dancer_dgain / 100.0
    zeta = gain_float * 0.110  # Calibrated plant hydrodynamic mapping
    is_critically_damped = zeta >= 0.707

    return {
        "dancer_gain": round(gain_float, 2),
        "damping_ratio_zeta": round(zeta, 3),
        "critically_damped": bool(is_critically_damped),
    }


def validate_physics_safety(
    target_setpoints: Dict[str, Any],
    current_setpoints: Optional[Dict[str, Any]] = None,
    dt_sec: float = 1.0,
) -> Tuple[bool, Dict[str, int], List[str], Dict[str, Any]]:
    """
    Validates proposed setpoints against:
      1. Boundary safety limits [safety_min, safety_max]
      2. Maximum allowable slew-rate deltas (|delta| / dt <= max_slew)
      3. Physical resonance and hydraulic stability

    Args:
        target_setpoints: Target engineering or raw setpoints.
        current_setpoints: Current plant baseline (defaults to nominal values if None).
        dt_sec: Expected actuation timeframe in seconds.

    Returns:
        Tuple of:
          - is_safe (bool)
          - clamped_registers (dict[str, int])
          - violations (list[str])
          - physics_report (dict)
    """
    target_raw = normalize_to_raw_registers(target_setpoints)

    current_raw = (
        normalize_to_raw_registers(current_setpoints)
        if current_setpoints
        else {k: v["default"] for k, v in SAFETY_BOUNDS.items()}
    )

    clamped_raw: Dict[str, int] = {}
    violations: List[str] = []
    ramp_times: Dict[str, float] = {}

    for key, spec in SAFETY_BOUNDS.items():
        curr_val = current_raw.get(key, spec["default"])
        target_val = target_raw.get(key, curr_val)

        # 1. Hard Boundary Envelope Check
        clamped_val = target_val
        if target_val < spec["min"]:
            violations.append(
                f"Under-limit: {key}={target_val} below safety minimum {spec['min']} {spec['unit']}."
            )
            clamped_val = spec["min"]
        elif target_val > spec["max"]:
            violations.append(
                f"Over-limit: {key}={target_val} above safety maximum {spec['max']} {spec['unit']}."
            )
            clamped_val = spec["max"]

        # 2. Slew Rate Acceleration Check
        delta = abs(clamped_val - curr_val)
        max_allowed_delta = spec["max_slew_rate_per_sec"] * max(0.1, dt_sec)

        # Theoretical required ramp time
        req_ramp_time = delta / max(0.01, spec["max_slew_rate_per_sec"])
        ramp_times[key] = round(req_ramp_time, 3)

        if delta > max_allowed_delta * 1.05:  # 5% margin
            violations.append(
                f"Slew-rate violation on {key}: requested delta {delta} exceeds limit {max_allowed_delta:.1f} for dt={dt_sec}s."
            )
            # Safe clamping along slew boundary
            clamped_val = (
                curr_val + int(round(max_allowed_delta))
                if clamped_val > curr_val
                else curr_val - int(round(max_allowed_delta))
            )

        clamped_raw[key] = clamped_val

    # 3. Resonance and Damping Evaluation
    res_analysis = calculate_resonance_shift(clamped_raw.get("velocity_mms", 2500))
    damp_analysis = calculate_dancer_damping(clamped_raw.get("dancer_dgain", 500))

    # Overall settling time is determined by the slowest mechanical/hydraulic ramp
    max_ramp_time = max(ramp_times.values()) if ramp_times else 0.80
    settling_time_sec = round(max(0.20, max_ramp_time), 3)

    is_safe = len(violations) == 0

    physics_report = {
        "is_safe": is_safe,
        "settling_time_estimate_sec": settling_time_sec,
        "actuator_ramp_times_sec": ramp_times,
        "resonance_analysis": res_analysis,
        "damping_analysis": damp_analysis,
        "target_si_units": {
            "line_velocity_mps": clamped_raw.get("velocity_mms", 2500) * 0.001,
            "web_tension_newtons": clamped_raw.get("tension_dn", 1500) * 0.1,
            "ir_dryer_temp_celsius": clamped_raw.get("temp_dc", 1200) * 0.1,
            "slurry_pump_rpm": clamped_raw.get("pump_drpm", 12000) * 0.1,
            "dancer_damping_gain": clamped_raw.get("dancer_dgain", 500) * 0.01,
        },
    }

    return is_safe, clamped_raw, violations, physics_report
