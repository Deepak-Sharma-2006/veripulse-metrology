#pragma once

#include <opencv2/opencv.hpp>
#include <opencv2/gapi.hpp>
#include <opencv2/gapi/gkernel.hpp>
#include <opencv2/gapi/gopaque.hpp>

namespace veripulse {

/**
 * @brief Dynamic vision calibration parameters received from cloud agent or local loop.
 * Updates edge filter thresholds without G-API graph recompilation.
 */
struct VisionCalibrationParams {
    float bilateral_spatial_sigma = 1.8f;
    float bilateral_range_sigma = 0.08f;
    float scharr_threshold = 45.0f;
    float exposure_us = 180.0f;
};

// G-API Operation Declaration for Fused Sub-Pixel Edge Detection
G_API_OP(GFusedSubPixelEdge, <cv::GMat(cv::GMat, cv::GOpaque<VisionCalibrationParams>)>, "veripulse.fused_subpixel_edge") {
    static cv::GMatDesc outMeta(const cv::GMatDesc& in, const cv::GOpaqueDesc&) {
        return in.withType(CV_8U, 1);
    }
};

/**
 * @brief Graph interface for FusedSubPixelEdgeOp.
 * Executes bilateral denoising and sub-pixel Scharr gradient interpolation
 * yielding +-2.44 um physical precision on anomalous 256x256 ROIs.
 */
cv::GMat fused_subpixel_edge(const cv::GMat& in, const cv::GOpaque<VisionCalibrationParams>& calib);

/**
 * @brief Returns the G-API kernel package containing the CPU/Fluid implementation.
 */
cv::gapi::GKernelPackage get_fused_subpixel_edge_kernel();

/**
 * @brief Standalone non-GAPI implementation for direct execution and unit testing.
 */
cv::Mat compute_fused_subpixel_edge(const cv::Mat& roi_256, const VisionCalibrationParams& calib);

} // namespace veripulse
