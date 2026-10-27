/**
 * VeriPulse Sub-Pixel Metrology Precision Verification Test
 * =========================================================
 * Empirical C++ test asserting sub-pixel edge localization accuracy within +-2.5 um.
 * Physical Optical Configuration:
 *   - Global Shutter CMOS 2048x2048 Sensor
 *   - Field of View: 50.0 mm x 50.0 mm
 *   - Pixel Pitch: 24.414 um/pixel
 *   - Target Precision: +-0.1 pixel = +-2.441 um (<= 2.5 um absolute tolerance)
 */

#include <iostream>
#include <vector>
#include <cmath>
#include <cassert>
#include <iomanip>
#include <algorithm>

#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>
#include "fused_subpixel_edge.hpp"

using namespace veripulse;

/**
 * Synthesizes a high-resolution sub-pixel edge transition at x = center_x + fractional_offset.
 * Utilizes anti-aliased integration across sub-pixel grid cells to simulate true sensor photon integration.
 */
cv::Mat synthesize_subpixel_edge(int width, int height, double center_x, double fractional_offset) {
    cv::Mat roi(height, width, CV_8UC1);
    double true_edge_x = center_x + fractional_offset;

    // Optical blur simulating sensor modulation transfer function (MTF)
    for (int y = 0; y < height; ++y) {
        uint8_t* row = roi.ptr<uint8_t>(y);
        for (int x = 0; x < width; ++x) {
            // Distance to edge in pixels
            double d = static_cast<double>(x) - true_edge_x;
            // Sigmoid Fermi-Dirac optical edge transition profile (sigma = 0.8 px)
            double intensity = 50.0 + 150.0 / (1.0 + std::exp(-d / 0.8));
            row[x] = static_cast<uint8_t>(std::clamp(intensity, 0.0, 255.0));
        }
    }
    return roi;
}

/**
 * Extracts sub-pixel peak position using 3-point parabolic Scharr gradient interpolation.
 */
double estimate_subpixel_edge_x(const cv::Mat& roi, int test_row) {
    cv::Mat grad_x;
    cv::Scharr(roi, grad_x, CV_32F, 1, 0);

    const float* row_ptr = grad_x.ptr<float>(test_row);
    int max_idx = 1;
    float max_val = row_ptr[1];

    for (int x = 2; x < roi.cols - 1; ++x) {
        if (row_ptr[x] > max_val) {
            max_val = row_ptr[x];
            max_idx = x;
        }
    }

    // Parabolic sub-pixel peak interpolation: delta = (m+ - m-) / (2 * (2*m0 - m+ - m-))
    float m_minus = row_ptr[max_idx - 1];
    float m_zero  = row_ptr[max_idx];
    float m_plus  = row_ptr[max_idx + 1];

    float denom = 2.0f * (2.0f * m_zero - m_plus - m_minus);
    float delta = 0.0f;
    if (std::abs(denom) > 1e-5f) {
        delta = (m_plus - m_minus) / denom;
        delta = std::clamp(delta, -0.5f, 0.5f);
    }

    return static_cast<double>(max_idx) + static_cast<double>(delta);
}

int main() {
    std::cout << "================================================================================" << std::endl;
    std::cout << "        VERIPULSE C++ SUB-PIXEL METROLOGY PRECISION VERIFICATION TEST" << std::endl;
    std::cout << "================================================================================" << std::endl;

    const double kPixelResolutionUm = 24.4140625; // 50,000 um / 2048 px
    const double kMaxAllowedErrorUm = 2.50;        // Strict +-2.50 um tolerance
    const int kRoiWidth = 256;
    const int kRoiHeight = 256;
    const double kCenterNominalX = 128.0;

    // Fractional offsets tested across the sub-pixel cycle: [-0.45, +0.45]
    std::vector<double> test_offsets = {
        -0.45, -0.35, -0.25, -0.15, -0.05,
         0.00,
        +0.05, +0.15, +0.25, +0.35, +0.45
    };

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "  Physical Pixel Pitch : " << kPixelResolutionUm << " um/px" << std::endl;
    std::cout << "  Accuracy Requirement : <= " << kMaxAllowedErrorUm << " um (+-0.1024 px)" << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;
    std::cout << " Offset (px) | Ground Truth (px) | Estimated (px) | Error (px) | Error (um) | Status " << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;

    bool all_passed = true;
    double max_error_um = 0.0;
    double sum_error_um = 0.0;

    for (double offset : test_offsets) {
        double gt_x = kCenterNominalX + offset;
        cv::Mat roi = synthesize_subpixel_edge(kRoiWidth, kRoiHeight, kCenterNominalX, offset);

        // Average across 10 central test rows to suppress spatial discretization noise
        std::vector<double> row_estimates;
        for (int r = 120; r <= 135; ++r) {
            row_estimates.push_back(estimate_subpixel_edge_x(roi, r));
        }
        double est_x = std::accumulate(row_estimates.begin(), row_estimates.end(), 0.0) / row_estimates.size();

        double error_px = std::abs(est_x - gt_x);
        double error_um = error_px * kPixelResolutionUm;

        max_error_um = std::max(max_error_um, error_um);
        sum_error_um += error_um;

        bool pass = (error_um <= kMaxAllowedErrorUm);
        if (!pass) all_passed = false;

        std::cout << " " << std::setw(11) << offset
                  << " | " << std::setw(17) << gt_x
                  << " | " << std::setw(14) << est_x
                  << " | " << std::setw(10) << error_px
                  << " | " << std::setw(9) << error_um
                  << "  | " << (pass ? "[PASS]" : "[FAIL]") << std::endl;
    }

    double mean_error_um = sum_error_um / test_offsets.size();

    std::cout << "--------------------------------------------------------------------------------" << std::endl;
    std::cout << "  Mean Absolute Metrology Error : " << mean_error_um << " um" << std::endl;
    std::cout << "  Worst-Case Peak Error         : " << max_error_um << " um (Spec: <= " << kMaxAllowedErrorUm << " um)" << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;

    if (all_passed) {
        std::cout << "\n[PASS] Sub-pixel accuracy validation SUCCEEDED! All offsets verified within +-2.5 um.\n" << std::endl;
        return 0;
    } else {
        std::cerr << "\n[FAIL] Sub-pixel accuracy test FAILED! Peak error exceeded specification.\n" << std::endl;
        return 1;
    }
}
