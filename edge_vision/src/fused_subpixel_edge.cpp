#include "fused_subpixel_edge.hpp"
#include <opencv2/gapi/cpu/gcpukernel.hpp>
#include <cmath>
#include <algorithm>

namespace veripulse {

cv::Mat compute_fused_subpixel_edge(const cv::Mat& roi_256, const VisionCalibrationParams& calib) {
    if (roi_256.empty()) {
        return cv::Mat();
    }

    cv::Mat gray;
    if (roi_256.channels() > 1) {
        cv::cvtColor(roi_256, gray, cv::COLOR_BGR2GRAY);
    } else {
        gray = roi_256;
    }

    // 1. Bilateral filtering for edge-preserving denoising
    cv::Mat filtered;
    double sigma_color = std::max(1.0, static_cast<double>(calib.bilateral_range_sigma * 255.0f));
    double sigma_space = std::max(0.5, static_cast<double>(calib.bilateral_spatial_sigma));
    cv::bilateralFilter(gray, filtered, 5, sigma_color, sigma_space);

    // 2. Scharr gradient computation (optimal 3x3 rotational symmetry)
    cv::Mat gx, gy;
    cv::Scharr(filtered, gx, CV_32F, 1, 0, 1.0 / 32.0);
    cv::Scharr(filtered, gy, CV_32F, 0, 1, 1.0 / 32.0);

    cv::Mat mag;
    cv::magnitude(gx, gy, mag);

    // 3. Sub-pixel 1D parabolic peak refinement along gradient direction
    cv::Mat edge_map = cv::Mat::zeros(gray.size(), CV_8UC1);
    const int rows = gray.rows;
    const int cols = gray.cols;
    const float threshold = calib.scharr_threshold;

    for (int y = 1; y < rows - 1; ++y) {
        const float* prev_row = mag.ptr<float>(y - 1);
        const float* curr_row = mag.ptr<float>(y);
        const float* next_row = mag.ptr<float>(y + 1);

        const float* gx_row = gx.ptr<float>(y);
        const float* gy_row = gy.ptr<float>(y);
        uint8_t* out_row = edge_map.ptr<uint8_t>(y);

        for (int x = 1; x < cols - 1; ++x) {
            float m0 = curr_row[x];
            if (m0 < threshold) {
                continue;
            }

            float vx = gx_row[x];
            float vy = gy_row[x];

            // Parabolic peak interpolation along dominant axis
            float m_plus = 0.0f;
            float m_minus = 0.0f;

            if (std::abs(vx) >= std::abs(vy)) {
                // Horizontal dominant gradient
                m_plus  = curr_row[x + 1];
                m_minus = curr_row[x - 1];
            } else {
                // Vertical dominant gradient
                m_plus  = next_row[x];
                m_minus = prev_row[x];
            }

            // Local maximum check
            if (m0 >= m_plus && m0 >= m_minus) {
                float denom = 2.0f * (2.0f * m0 - m_plus - m_minus);
                float delta = 0.0f;
                if (std::abs(denom) > 1e-5f) {
                    delta = (m_plus - m_minus) / denom;
                }
                // Precision clamping: +- 0.5 px sub-pixel interval
                if (std::abs(delta) <= 0.5f) {
                    // Mark confirmed sub-pixel edge
                    float scaled_val = std::min(255.0f, m0 * 2.0f);
                    out_row[x] = static_cast<uint8_t>(scaled_val > 50.0f ? scaled_val : 255.0f);
                }
            }
        }
    }

    return edge_map;
}

GAPI_OCV_KERNEL(GOCVFusedSubPixelEdge, GFusedSubPixelEdge) {
    static void run(const cv::Mat& in, const VisionCalibrationParams& calib, cv::Mat& out) {
        out = compute_fused_subpixel_edge(in, calib);
    }
};

cv::GMat fused_subpixel_edge(const cv::GMat& in, const cv::GOpaque<VisionCalibrationParams>& calib) {
    return GFusedSubPixelEdge::on(in, calib);
}

cv::gapi::GKernelPackage get_fused_subpixel_edge_kernel() {
    return cv::gapi::kernels<GOCVFusedSubPixelEdge>();
}

} // namespace veripulse
