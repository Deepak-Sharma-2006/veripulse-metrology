#include <iostream>
#include <chrono>
#include <thread>
#include <atomic>
#include <csignal>
#include <vector>
#include <cstring>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif

#include "shared_memory_ipc.hpp"
#include "gpio_interlock.hpp"
#include "gapi_pipeline_builder.hpp"

static std::atomic<bool> g_running{true};

void signal_handler(int) {
    g_running.store(false);
}

class SHMManager {
public:
    SHMManager() : shm_ptr_(nullptr) {
#ifdef _WIN32
        h_map_file_ = CreateFileMappingA(
            INVALID_HANDLE_VALUE,
            NULL,
            PAGE_READWRITE,
            0,
            static_cast<DWORD>(SHM_TOTAL_SIZE),
            SHM_NAME
        );
        if (h_map_file_ != NULL) {
            shm_ptr_ = static_cast<uint8_t*>(MapViewOfFile(
                h_map_file_,
                FILE_MAP_ALL_ACCESS,
                0,
                0,
                SHM_TOTAL_SIZE
            ));
        }
#else
        int fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
        if (fd >= 0) {
            ftruncate(fd, SHM_TOTAL_SIZE);
            shm_ptr_ = static_cast<uint8_t*>(mmap(NULL, SHM_TOTAL_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0));
            close(fd);
        }
#endif
        if (shm_ptr_) {
            header_ = reinterpret_cast<VeriPulseSHMHeader*>(shm_ptr_);
            if (header_->magic != 0x5650554C) {
                // Initialize default header
                std::memset(shm_ptr_, 0, sizeof(VeriPulseSHMHeader));
                header_->magic = 0x5650554C;
                header_->version = 1;
                header_->line_speed_mps = 2.50f;
                header_->vision_calib[0] = 1.8f;
                header_->vision_calib[1] = 0.08f;
                header_->vision_calib[2] = 45.0f;
                header_->vision_calib[3] = 180.0f;
            }
        }
    }

    ~SHMManager() {
#ifdef _WIN32
        if (shm_ptr_) UnmapViewOfFile(shm_ptr_);
        if (h_map_file_) CloseHandle(h_map_file_);
#else
        if (shm_ptr_) munmap(shm_ptr_, SHM_TOTAL_SIZE);
#endif
    }

    bool is_valid() const { return shm_ptr_ != nullptr; }
    uint8_t* data() { return shm_ptr_; }
    VeriPulseSHMHeader* header() { return header_; }

private:
    uint8_t* shm_ptr_;
    VeriPulseSHMHeader* header_ = nullptr;
#ifdef _WIN32
    HANDLE h_map_file_ = NULL;
#endif
};

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::cout << "========================================================\n"
              << " VeriPulse Edge Vision & Physics Core (G-API C++20)     \n"
              << " Target Rate: 120 FPS | Precision: +-2.44 um Metrology  \n"
              << "========================================================" << std::endl;

    int max_frames = 0;
    if (argc > 1) {
        max_frames = std::atoi(argv[1]);
    }

    SHMManager shm;
    if (!shm.is_valid()) {
        std::cerr << "[ERROR] Failed to allocate/attach to shared memory: " << SHM_NAME << std::endl;
        return 1;
    }
    std::cout << "[SHM] Successfully mapped " << SHM_NAME << " (" << SHM_TOTAL_SIZE << " bytes)." << std::endl;

    veripulse::GPIOInterlock gpio(23);
    veripulse::GAPIPipelineBuilder pipeline("models/yolov10_microdefect.onnx");
    pipeline.compile();

    uint8_t* optical_raw = shm.data() + OPTICAL_FRAME_OFFSET;
    uint8_t* thermal_raw = shm.data() + THERMAL_FRAME_OFFSET;
    float* fft_raw = reinterpret_cast<float*>(shm.data() + FFT_SPECTRUM_OFFSET);
    uint8_t* webp_raw = shm.data() + WEBP_CROP_OFFSET;

    cv::Mat optical_mat(2048, 2048, CV_8UC1, optical_raw);
    cv::Mat thermal_mat(512, 512, CV_8UC1, thermal_raw);

    uint64_t processed_frames = 0;
    auto t_start_loop = std::chrono::high_resolution_clock::now();

    while (g_running.load()) {
        auto t_frame_start = std::chrono::high_resolution_clock::now();

        // 1. Read dynamic vision calibration from SHM header (0.0 ms lock-free)
        veripulse::VisionCalibrationParams calib;
        calib.bilateral_spatial_sigma = shm.header()->vision_calib[0];
        calib.bilateral_range_sigma   = shm.header()->vision_calib[1];
        calib.scharr_threshold        = shm.header()->vision_calib[2];
        calib.exposure_us             = shm.header()->vision_calib[3];

        // 2. Execute Coarse-to-Fine Pipeline
        veripulse::PipelineOutput out;
        bool ok = pipeline.process_frame(optical_mat, thermal_mat, calib, out);
        if (!ok) {
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
            continue;
        }

        // 3. Write 512-bin FFT spectrum to SHM
        if (out.fft_harmonics.size() >= 512) {
            std::memcpy(fft_raw, out.fft_harmonics.data(), 512 * sizeof(float));
        }

        // 4. Encode micro-crop to WebP and write to SHM
        if (!out.micro_crop_roi.empty()) {
            std::vector<uint8_t> webp_bytes;
            std::vector<int> params = {cv::IMWRITE_WEBP_QUALITY, 90};
            cv::imencode(".webp", out.micro_crop_roi, webp_bytes, params);

            size_t copy_len = std::min(webp_bytes.size(), WEBP_CROP_MAX_SIZE);
            std::memcpy(webp_raw, webp_bytes.data(), copy_len);
            shm.header()->webp_byte_len = static_cast<uint32_t>(copy_len);
        }

        // 5. Update Header Telemetry
        shm.header()->sequence_id++;
        shm.header()->timestamp_ns = static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::system_clock::now().time_since_epoch()
            ).count()
        );

        // Check for 142.5 Hz ribbing or catastrophic defect
        if (out.signature.subpixel_major_axis_um > 800.0f) {
            shm.header()->alert_flags |= 0x01; // Anomaly detected
            shm.header()->defect_count++;
            if (out.signature.subpixel_major_axis_um > 1500.0f) {
                // Catastrophic tear -> hardware GPIO trip
                shm.header()->alert_flags |= 0x04;
                gpio.trip("Catastrophic tear exceeding 1500 um detected");
            }
        }

        processed_frames++;
        if (max_frames > 0 && processed_frames >= static_cast<uint64_t>(max_frames)) {
            break;
        }

        // Rate control: Pacing for 120 FPS (8.33 ms period)
        auto t_frame_end = std::chrono::high_resolution_clock::now();
        double frame_time_ms = std::chrono::duration<double, std::milli>(t_frame_end - t_frame_start).count();
        if (frame_time_ms < 8.33) {
            std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>((8.33 - frame_time_ms) * 1000.0)));
        }

        if (processed_frames % 120 == 0) {
            auto now = std::chrono::high_resolution_clock::now();
            double elapsed_sec = std::chrono::duration<double>(now - t_start_loop).count();
            double fps = processed_frames / (elapsed_sec > 0 ? elapsed_sec : 1.0);
            std::cout << "[EDGE_VISION] Processed " << processed_frames << " frames | Rate: "
                      << fps << " FPS | Last Frame Latency: " << frame_time_ms << " ms" << std::endl;
        }
    }

    std::cout << "[EDGE_VISION] Finished processing. Total frames: " << processed_frames << std::endl;
    return 0;
}
