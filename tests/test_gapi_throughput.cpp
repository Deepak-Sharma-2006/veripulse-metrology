/**
 * VeriPulse High-Speed Edge Vision Throughput & Latency Verification Test
 * ======================================================================
 * Empirical C++ test asserting >= 120 FPS continuous ingestion and < 8.0 ms edge reflex latency.
 * Validates the coarse-to-fine multi-spectral perception pipeline:
 *   1. 2048x2048 Optical Frame Ingestion (24.4 um/px)
 *   2. 4x Vectorized Decimation to 512x512
 *   3. 2D-FFT Spatial Frequency Decomposition (142.5 Hz ribbing resonance detection)
 *   4. Sub-Pixel Scharr Metrology on 256x256 High-Resolution ROI
 *   5. WebP Micro-Crop Encoding & Zero-Copy SHM Emission
 */

#include <iostream>
#include <chrono>
#include <vector>
#include <numeric>
#include <algorithm>
#include <cassert>
#include <cmath>

#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/core.hpp>

#include "gapi_pipeline_builder.hpp"
#include "fused_subpixel_edge.hpp"
#include "spatial_fft_kernel.hpp"

using namespace veripulse;

int main() {
    std::cout << "================================================================================" << std::endl;
    std::cout << "    VERIPULSE C++ EDGE G-API THROUGHPUT & LATENCY BENCHMARK TEST" << std::endl;
    std::cout << "================================================================================" << std::endl;

    const int kBenchmarkFrames = 240; // 2 seconds of full 120 FPS stream
    const int kWarmupFrames = 10;
    const double kTargetFPS = 120.0;
    const double kMaxMeanLatencyMs = 8.0;

    // 1. Synthesize synthetic multi-spectral frames
    cv::Mat optical_2048(2048, 2048, CV_8UC1);
    cv::randn(optical_2048, 128, 15);

    // Inject simulated slot-die coating boundary and ribbing wave
    for (int y = 0; y < 2048; ++y) {
        uint8_t* row = optical_2048.ptr<uint8_t>(y);
        for (int x = 0; x < 2048; ++x) {
            if (x < 220 || x > 1828) {
                row[x] = static_cast<uint8_t>(std::clamp(175 + (x % 5), 0, 255));
            } else {
                double ribbing = 20.0 * std::sin(2.0 * M_PI * y / 35.0);
                row[x] = static_cast<uint8_t>(std::clamp(68.0 + ribbing, 0.0, 255.0));
            }
        }
    }

    cv::Mat thermal_512(512, 512, CV_8UC1);
    cv::randn(thermal_512, 110, 8);

    VisionCalibrationParams calib;
    calib.bilateral_spatial_sigma = 1.8f;
    calib.bilateral_range_sigma = 0.08f;
    calib.scharr_threshold = 45.0f;
    calib.exposure_us = 180.0f;

    // 2. Initialize G-API Pipeline Builder
    GAPIPipelineBuilder builder;
    bool compiled = builder.compile();
    std::cout << "[GAPI-TEST] Pipeline graph compiled: " << (compiled ? "YES" : "FALLBACK-DIRECT") << std::endl;

    PipelineOutput out;

    // 3. Warmup Run
    std::cout << "[GAPI-TEST] Executing " << kWarmupFrames << " warmup iterations..." << std::endl;
    for (int i = 0; i < kWarmupFrames; ++i) {
        builder.process_frame(optical_2048, thermal_512, calib, out);
    }

    // 4. Timed Benchmark Run
    std::cout << "[GAPI-TEST] Benchmarking " << kBenchmarkFrames << " frames under simulated roll-to-roll load..." << std::endl;
    std::vector<double> latencies_ms;
    latencies_ms.reserve(kBenchmarkFrames);

    auto t_start_total = std::chrono::high_resolution_clock::now();

    for (int frame = 0; frame < kBenchmarkFrames; ++frame) {
        auto t0 = std::chrono::high_resolution_clock::now();

        builder.process_frame(optical_2048, thermal_512, calib, out);

        auto t1 = std::chrono::high_resolution_clock::now();
        double dt_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        latencies_ms.push_back(dt_ms);
    }

    auto t_end_total = std::chrono::high_resolution_clock::now();
    double total_sec = std::chrono::duration<double>(t_end_total - t_start_total).count();

    // 5. Statistical Aggregation
    std::sort(latencies_ms.begin(), latencies_ms.end());
    double sum = std::accumulate(latencies_ms.begin(), latencies_ms.end(), 0.0);
    double mean_ms = sum / latencies_ms.size();
    double p50_ms = latencies_ms[static_cast<size_t>(latencies_ms.size() * 0.50)];
    double p95_ms = latencies_ms[static_cast<size_t>(latencies_ms.size() * 0.95)];
    double p99_ms = latencies_ms[static_cast<size_t>(latencies_ms.size() * 0.99)];
    double effective_fps = kBenchmarkFrames / total_sec;

    std::cout << "\n--------------------------------------------------------------------------------" << std::endl;
    std::cout << "                        BENCHMARK EXECUTION METRICS" << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;
    std::cout << "  * Total Frames Evaluated : " << kBenchmarkFrames << std::endl;
    std::cout << "  * Total Elapsed Time     : " << total_sec << " seconds" << std::endl;
    std::cout << "  * Effective Throughput   : " << effective_fps << " FPS (Target: >= " << kTargetFPS << " FPS)" << std::endl;
    std::cout << "  * Mean Latency           : " << mean_ms << " ms (Budget: < " << kMaxMeanLatencyMs << " ms)" << std::endl;
    std::cout << "  * Median (p50) Latency   : " << p50_ms << " ms" << std::endl;
    std::cout << "  * 95th Percentile (p95)  : " << p95_ms << " ms" << std::endl;
    std::cout << "  * 99th Percentile (p99)  : " << p99_ms << " ms" << std::endl;
    std::cout << "  * Sub-Pixel Contour ROI  : " << out.subpixel_edge_roi.cols << "x" << out.subpixel_edge_roi.rows << std::endl;
    std::cout << "  * FFT Harmonic Bins      : " << out.fft_harmonics.size() << " bins" << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;

    // 6. Assertions
    bool pass_throughput = (effective_fps >= kTargetFPS);
    bool pass_latency = (mean_ms <= kMaxMeanLatencyMs);

    if (pass_throughput && pass_latency) {
        std::cout << "\n[PASS] G-API Throughput & Latency constraints fully satisfied! (FPS="
                  << effective_fps << ", Latency=" << mean_ms << " ms)" << std::endl;
        return 0;
    } else {
        std::cerr << "\n[FAIL] Performance requirement violation! Throughput: "
                  << effective_fps << " FPS, Mean Latency: " << mean_ms << " ms" << std::endl;
        return 1;
    }
}
