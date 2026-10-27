"""
VeriPulse Synthetic Defect Injection Engine
===========================================
Injects deterministic physical defects into 120 FPS electrode foil frames:
  1. 50 um Micro-Pinholes: Critical dendrite short-circuit risks spanning ~2.05 pixels.
  2. 142.5 Hz Ribbing Harmonics: Hydrodynamic coating resonance with closed-loop decay.
  3. Bare Copper Specular Glare: High-reflectivity optical saturation on foil margins.

Closed-Loop Decay:
  Reads live PLC registers (velocity, dancer damping gain).
  When velocity shifts out of resonance (|v - 2500| > 40 mm/s) or damping gain >= 5.50,
  the 142.5 Hz ribbing instability decays exponentially, settling in ~0.80 s.
"""

import math
import time
import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import cv2

logger = logging.getLogger("DefectInjector")

SPATIAL_RES_UM = 24.414  # um per pixel
NOMINAL_VELOCITY_MMS = 2500.0  # mm/s
TARGET_RIBBING_FREQ_HZ = 142.5  # Hz


class DefectInjector:
    def __init__(self):
        # Ribbing resonance state
        self.ribbing_active: bool = False
        self.ribbing_amplitude: float = 0.0  # Current grayscale modulation amplitude
        self.ribbing_target_amplitude: float = 38.0
        self.ribbing_freq_hz: float = TARGET_RIBBING_FREQ_HZ
        self.ribbing_decay_tau: float = 0.24  # Settling time ~0.80s matching masterplan

        # Specular glare state
        self.glare_active: bool = False
        self.glare_intensity: float = 245.0
        self.glare_center_x: int = 150
        self.glare_radius_x: int = 100
        self.glare_radius_y: int = 400
        self._init_glare_mask()

        # Micro-pinhole list: list of dicts {x, y, radius_px, brightness, age_frames, max_frames}
        self.pinholes: List[Dict[str, Any]] = []

        # Statistical counters
        self.total_defects_injected: int = 0
        self.alert_flags: int = 0  # 0x01: Anomaly, 0x02: Ribbing, 0x04: GPIO Trip

    def _init_glare_mask(self):
        """Pre-renders an AVX-friendly 2048x2048 uint8 glare mask."""
        mask = np.zeros((2048, 2048), dtype=np.uint8)
        cv2.ellipse(
            mask,
            (self.glare_center_x, 1024),
            (self.glare_radius_x, self.glare_radius_y),
            0, 0, 360,
            int(self.glare_intensity),
            -1
        )
        self.glare_mask = cv2.GaussianBlur(mask, (65, 65), 20.0)

    def trigger_ribbing(self, amplitude: float = 38.0, freq_hz: float = TARGET_RIBBING_FREQ_HZ):
        """Activates 142.5 Hz hydrodynamic meniscus ribbing resonance."""
        self.ribbing_active = True
        self.ribbing_target_amplitude = amplitude
        self.ribbing_amplitude = amplitude
        self.ribbing_freq_hz = freq_hz
        self.alert_flags |= 0x02  # Bit 1: Ribbing resonance
        logger.info("TRIGGERED: 142.5 Hz Ribbing Resonant Defect (Amplitude: %.1f)", amplitude)

    def trigger_pinhole(
        self,
        center_x: Optional[int] = None,
        center_y: Optional[int] = None,
        diameter_um: float = 50.0,
        brightness: int = 240,
    ):
        """Injects a 50 um micro-pinhole (~2.05 pixels) into the electrode slurry."""
        radius_px = max(1, int(round((diameter_um / SPATIAL_RES_UM) / 2.0)))
        x = center_x if center_x is not None else int(np.random.randint(400, 1600))
        y = center_y if center_y is not None else int(np.random.randint(300, 1700))

        self.pinholes.append({
            "x": x,
            "y": y,
            "radius_px": radius_px,
            "diameter_um": diameter_um,
            "brightness": brightness,
            "age_frames": 0,
            "max_frames": 60,
        })
        self.total_defects_injected += 1
        self.alert_flags |= 0x01  # Bit 0: Optical Anomaly
        logger.info(
            "TRIGGERED: %.1f um Micro-Pinhole at (%d, %d) [radius: %d px]",
            diameter_um, x, y, radius_px
        )

    def trigger_specular_glare(self, center_x: int = 150, intensity: float = 245.0):
        """Activates bare copper foil specular reflection glare on the edge margin."""
        self.glare_active = True
        self.glare_center_x = center_x
        self.glare_intensity = intensity
        self._init_glare_mask()
        self.alert_flags |= 0x01  # Bit 0: Optical Anomaly
        logger.info("TRIGGERED: Bare Copper Specular Foil Glare at X=%d (Intensity: %.1f)", center_x, intensity)

    def clear_all(self):
        """Clears all active defect injections."""
        self.ribbing_active = False
        self.ribbing_amplitude = 0.0
        self.glare_active = False
        self.pinholes.clear()
        self.alert_flags = 0
        logger.info("Cleared all defect injections.")

    def update_closed_loop_state(
        self,
        velocity_mms: int,
        dancer_gain_x100: int,
        dt_sec: float = 1.0 / 120.0,
    ):
        """
        Closed-loop physical coupling:
        Checks whether PLC setpoints have shifted away from the 142.5 Hz mechanical resonance window.
        If line velocity shifts by > 40 mm/s or dancer gain >= 550 (5.50), the ribbing decays exponentially.
        """
        if self.ribbing_active:
            vel_shifted = abs(velocity_mms - NOMINAL_VELOCITY_MMS) > 40.0
            damping_increased = dancer_gain_x100 >= 550  # >= 5.50 Gain

            if vel_shifted or damping_increased:
                decay_factor = math.exp(-dt_sec / self.ribbing_decay_tau)
                self.ribbing_amplitude *= decay_factor

                if self.ribbing_amplitude < 1.0:
                    self.ribbing_active = False
                    self.ribbing_amplitude = 0.0
                    self.alert_flags &= ~0x02  # Clear ribbing bit
                    logger.info(
                        "CLOSED-LOOP RESOLUTION: 142.5 Hz Ribbing Resonance Fully Extinguished! "
                        "(PLC Setpoints: %d mm/s, %.2f Gain)",
                        velocity_mms, dancer_gain_x100 / 100.0
                    )

        # Age and remove expired pinholes
        for p in list(self.pinholes):
            p["age_frames"] += 1
            if p["age_frames"] > p["max_frames"]:
                self.pinholes.remove(p)

        if not self.pinholes and not self.glare_active:
            self.alert_flags &= ~0x01

    def apply_to_optical(
        self,
        nominal_slice: np.ndarray,
        ribbing_slice: np.ndarray,
        dest_frame: np.ndarray,
    ) -> Tuple[np.ndarray, int, int]:
        """
        Fast AVX SIMD application of defects directly into dest_frame (< 1.6 ms).
        """
        active_count = len(self.pinholes)

        # 1. 142.5 Hz Ribbing Harmonics via SIMD weighted blend
        if self.ribbing_amplitude > 0.5:
            active_count += 1
            alpha = min(1.0, float(self.ribbing_amplitude / self.ribbing_target_amplitude))
            cv2.addWeighted(ribbing_slice, alpha, nominal_slice, 1.0 - alpha, 0, dst=dest_frame)
        else:
            np.copyto(dest_frame, nominal_slice)

        # 2. Bare Copper Specular Glare via SIMD saturation add
        if self.glare_active:
            active_count += 1
            cv2.add(dest_frame, self.glare_mask, dst=dest_frame)

        # 3. 50 um Micro-Pinholes (~2.05 px)
        for p in self.pinholes:
            cx, cy = p["x"], p["y"]
            r = p["radius_px"]
            # Draw bright bare copper glint
            cv2.circle(dest_frame, (cx, cy), max(1, r), p["brightness"], -1)
            # Add subtle dark meniscus ring around hole
            cv2.circle(dest_frame, (cx, cy), max(2, r + 1), int(p["brightness"] * 0.3), 1)

        return dest_frame, active_count, self.alert_flags

    def apply_to_thermal(
        self,
        base_thermal_slice: np.ndarray,
        dest_thermal: np.ndarray,
    ) -> np.ndarray:
        """
        Applies thermal signatures to the 512x512 thermal IR frame (< 0.1 ms).
        """
        np.copyto(dest_thermal, base_thermal_slice)

        # Bare copper foil low emissivity creates apparent cool strip on left margin
        if self.glare_active:
            dest_thermal[:, :55] = np.clip(dest_thermal[:, :55] * 0.82, 0, 255).astype(np.uint8)

        return dest_thermal
