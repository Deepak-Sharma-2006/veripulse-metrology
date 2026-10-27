"""
VeriPulse Shared Memory Common Definitions
Standardized Binary Shared Memory Layout (veripulse_shm_v1)
Total Buffer Size: 5,242,880 Bytes (5.0 MB)
Header Size: Exactly 1,024 Bytes (<IIQQfII8h4fIff944x)
"""

import struct
import time
from dataclasses import dataclass
from typing import Tuple, Optional
from multiprocessing import shared_memory

SHM_NAME = "veripulse_shm_v1"
SHM_SIZE = 5 * 1024 * 1024  # 5,242,880 bytes

HEADER_FORMAT = "<IIQQfII8h4fIff944x"
HEADER_SIZE = 1024

OPTICAL_OFFSET = 1024
OPTICAL_SHAPE = (2048, 2048)
OPTICAL_SIZE = 2048 * 2048  # 4,194,304 bytes

THERMAL_OFFSET = OPTICAL_OFFSET + OPTICAL_SIZE  # 4,195,328
THERMAL_SHAPE = (512, 512)
THERMAL_SIZE = 512 * 512  # 262,144 bytes

FFT_OFFSET = THERMAL_OFFSET + THERMAL_SIZE  # 4,457,472
FFT_BINS = 512
FFT_SIZE = 512 * 4  # 2,048 bytes (512 float32)

WEBP_OFFSET = FFT_OFFSET + FFT_SIZE  # 4,459,520
WEBP_MAX_SIZE = 32 * 1024  # 32,768 bytes

MAGIC_NUMBER = 0x5650554C  # 'VPUL'
HEADER_STRUCT = struct.Struct(HEADER_FORMAT)
assert HEADER_STRUCT.size == HEADER_SIZE, f"Header size mismatch: {HEADER_STRUCT.size} != {HEADER_SIZE}"


@dataclass
class VeriPulseHeader:
    magic: int = MAGIC_NUMBER
    version: int = 1
    sequence_id: int = 0
    timestamp_ns: int = 0
    line_speed_mps: float = 2.50
    defect_count: int = 0
    alert_flags: int = 0  # 0x01: Anomaly, 0x02: Ribbing, 0x04: GPIO, 0x08: Healer
    modbus_mirror: Tuple[int, ...] = (2500, 1500, 1200, 12000, 500, 0, 0, 0)
    vision_calib: Tuple[float, ...] = (1.8, 0.08, 45.0, 180.0)
    webp_byte_len: int = 0
    dryer_temp_slope: float = 1.45
    tension_variance: float = 12.8

    def pack(self) -> bytes:
        return HEADER_STRUCT.pack(
            self.magic,
            self.version,
            self.sequence_id,
            self.timestamp_ns if self.timestamp_ns > 0 else time.time_ns(),
            self.line_speed_mps,
            self.defect_count,
            self.alert_flags,
            *self.modbus_mirror[:8],
            *self.vision_calib[:4],
            self.webp_byte_len,
            self.dryer_temp_slope,
            self.tension_variance
        )

    @classmethod
    def unpack(cls, buf: bytes) -> "VeriPulseHeader":
        unpacked = HEADER_STRUCT.unpack(buf[:HEADER_SIZE])
        magic = unpacked[0]
        version = unpacked[1]
        sequence_id = unpacked[2]
        timestamp_ns = unpacked[3]
        line_speed_mps = unpacked[4]
        defect_count = unpacked[5]
        alert_flags = unpacked[6]
        modbus_mirror = unpacked[7:15]
        vision_calib = unpacked[15:19]
        webp_byte_len = unpacked[19]
        dryer_temp_slope = unpacked[20]
        tension_variance = unpacked[21]
        return cls(
            magic=magic,
            version=version,
            sequence_id=sequence_id,
            timestamp_ns=timestamp_ns,
            line_speed_mps=line_speed_mps,
            defect_count=defect_count,
            alert_flags=alert_flags,
            modbus_mirror=modbus_mirror,
            vision_calib=vision_calib,
            webp_byte_len=webp_byte_len,
            dryer_temp_slope=dryer_temp_slope,
            tension_variance=tension_variance
        )


def get_or_create_shm(create: bool = False) -> shared_memory.SharedMemory:
    """Acquires existing shared memory or creates a new ring buffer."""
    if create:
        try:
            # Clean up stale memory block if it exists
            existing = shared_memory.SharedMemory(name=SHM_NAME)
            existing.close()
            existing.unlink()
        except FileNotFoundError:
            pass
        return shared_memory.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
    else:
        return shared_memory.SharedMemory(name=SHM_NAME)
