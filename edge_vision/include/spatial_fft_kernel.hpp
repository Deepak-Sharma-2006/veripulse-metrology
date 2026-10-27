#pragma once

#include <opencv2/opencv.hpp>
#include <opencv2/gapi.hpp>
#include <opencv2/gapi/gkernel.hpp>
#include <vector>

namespace veripulse {

/**
 * @brief G-API Operation for Spatial 2D-FFT Frequency Analysis.
 * Analyzes the 512x512 area-decimated optical field (50.0 mm aperture).
 * Resolves 142.5 Hz slot-die ribbing harmonics (lambda = 17.54 mm, 2.85 cycles/frame)
 * and 14.25 Hz bearing runout harmonics.
 */
G_API_OP(GSpatialFFT, <cv::GArray<float>(cv::GMat, int)>, "veripulse.spatial_fft") {
    static cv::GArrayDesc outMeta(const cv::GMatDesc&, int) {
        return cv::empty_array_desc();
    }
};

/**
 * @brief Graph node constructor for SpatialFFT.
 */
cv::GArray<float> spatial_fft_node(const cv::GMat& in_decimated_512, int bins = 512);

/**
 * @brief Returns the G-API kernel package containing the AVX/CPU implementation.
 */
cv::gapi::GKernelPackage get_spatial_fft_kernel();

/**
 * @brief Standalone FFT solver for 2D spatial spectrum analysis.
 * Computes 512-bin power spectrum and generates visual log-magnitude spectrum.
 */
void compute_spatial_fft(
    const cv::Mat& in_512,
    std::vector<float>& out_bins_512,
    cv::Mat& out_log_mag_img,
    float line_speed_mps = 2.50f
);

} // namespace veripulse
