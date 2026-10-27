#pragma once

#include <cstdint>
#include <cstddef>

#pragma pack(push, 1)
struct VeriPulseSHMHeader {
    uint32_t magic;                 // 4 B - 0x5650554C ('VPUL')
    uint32_t version;               // 4 B - Version 1
    uint64_t sequence_id;           // 8 B - Monotonic frame index
    uint64_t timestamp_ns;          // 8 B - Epoch nanoseconds
    float    line_speed_mps;        // 4 B - Velocity (m/s)
    uint32_t defect_count;          // 4 B - Cumulative defect count
    uint32_t alert_flags;           // 4 B - Bitwise alert flags
    int16_t  modbus_mirror[8];      // 16 B - Holding registers
    float    vision_calib[4];       // 16 B - [bilateral_spatial_sigma, bilateral_range_sigma, scharr_th, exposure_us]
    uint32_t webp_byte_len;         // 4 B - Micro-crop payload size
    float    dryer_temp_slope;      // 4 B - Rolling temperature trend
    float    tension_variance;      // 4 B - Rolling tension variance
    char     reserved_padding[944]; // 944 B - Zero padding to 1024 bytes
};
#pragma pack(pop)

static_assert(sizeof(VeriPulseSHMHeader) == 1024, "VeriPulseSHMHeader must be exactly 1024 bytes");

constexpr const char* SHM_NAME = "veripulse_shm_v1";
constexpr size_t SHM_TOTAL_SIZE = 5242880; // 5.0 MB
constexpr size_t OPTICAL_FRAME_OFFSET = 1024;
constexpr size_t OPTICAL_FRAME_SIZE = 2048 * 2048; // 4,194,304 B (CV_8UC1)
constexpr size_t THERMAL_FRAME_OFFSET = 4195328;
constexpr size_t THERMAL_FRAME_SIZE = 512 * 512; // 262,144 B (CV_8UC1)
constexpr size_t FFT_SPECTRUM_OFFSET = 4457472;
constexpr size_t FFT_SPECTRUM_SIZE = 512 * sizeof(float); // 2,048 B (512 float32)
constexpr size_t WEBP_CROP_OFFSET = 4459520;
constexpr size_t WEBP_CROP_MAX_SIZE = 32768; // 32 KB
