#pragma once

#include <opencv2/opencv.hpp>
#include <opencv2/gapi.hpp>
#include <opencv2/gapi/gkernel.hpp>
#include <opencv2/gapi/gopaque.hpp>
#include <vector>
#include <string>

namespace veripulse {

struct BoundingBoxMicrons {
    float x = 0.0f;
    float y = 0.0f;
    float width = 0.0f;
    float height = 0.0f;
};

struct TopologicalSignature {
    char anomaly_type[64] = "surface_reflectance_anomaly";
    BoundingBoxMicrons bbox;
    float subpixel_major_axis_um = 0.0f;
    float subpixel_minor_axis_um = 0.0f;
    float contour_perimeter_um = 0.0f;
    float mean_intensity = 0.0f;
    float specular_saturation_ratio = 0.0f;
    float fundamental_ribbing_freq_hz = 142.50f;
    float single_frame_wavelength_mm = 17.54f;
    float waves_per_50mm_fov = 2.85f;
    float temporal_stitched_roller_harmonic_hz = 14.25f;
    float mean_surface_temp_c = 58.4f;
    float hotspot_delta_c = 0.0f;
    float thermal_gradient_dx = 0.0f;
    float thermal_gradient_dy = 0.0f;
};

// G-API Operations
G_API_OP(GExtractTopology, <cv::GOpaque<TopologicalSignature>(cv::GMat, cv::GMat, cv::GArray<float>, cv::GMat)>, "veripulse.extract_topology") {
    static cv::GOpaqueDesc outMeta(const cv::GMatDesc&, const cv::GMatDesc&, const cv::GArrayDesc&, const cv::GMatDesc&) {
        return cv::empty_gopaque_desc();
    }
};

G_API_OP(GComposeMicroCrop, <cv::GMat(cv::GMat, cv::GMat, cv::GArray<float>)>, "veripulse.compose_micro_crop") {
    static cv::GMatDesc outMeta(const cv::GMatDesc&, const cv::GMatDesc&, const cv::GArrayDesc&) {
        return cv::GMatDesc{CV_8U, 3, cv::Size(256, 128)};
    }
};

cv::GOpaque<TopologicalSignature> extract_topology(
    const cv::GMat& coarse_defect_rois,
    const cv::GMat& subpixel_edges_roi,
    const cv::GArray<float>& fft_harmonics,
    const cv::GMat& in_thermal
);

cv::GMat compose_micro_crop(
    const cv::GMat& crop_optical_256,
    const cv::GMat& subpixel_edges_roi,
    const cv::GArray<float>& fft_harmonics
);

cv::gapi::GKernelPackage get_topological_extractor_kernels();

/**
 * @brief Generates 256x128 composite micro-crop [Visual ROI (128x128) | 2D-FFT Spectrum (128x128)].
 */
cv::Mat create_composite_micro_crop(
    const cv::Mat& crop_optical_256,
    const cv::Mat& subpixel_edges_roi,
    const std::vector<float>& fft_harmonics
);

/**
 * @brief Standalone topology calculation.
 */
TopologicalSignature calculate_topological_signature(
    const cv::Mat& coarse_rois,
    const cv::Mat& subpixel_edges_roi,
    const std::vector<float>& fft_harmonics,
    const cv::Mat& in_thermal
);

} // namespace veripulse
