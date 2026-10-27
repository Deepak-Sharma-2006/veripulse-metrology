#include "gapi_pipeline_builder.hpp"
#include <opencv2/gapi/core.hpp>
#include <opencv2/gapi/imgproc.hpp>
#include <iostream>

namespace veripulse {

GAPIPipelineBuilder::GAPIPipelineBuilder(const std::string& model_path)
    : model_path_(model_path), is_compiled_(false) {}

bool GAPIPipelineBuilder::compile() {
    try {
        cv::GMat in_optical;
        cv::GMat in_thermal;
        cv::GOpaque<VisionCalibrationParams> in_calib;

        // Stage 1: Coarse decimation
        cv::GMat decimated_optical = cv::gapi::resize(in_optical, cv::Size(512, 512), 0, 0, cv::INTER_AREA);
        cv::GArray<float> fft_harmonics = spatial_fft_node(decimated_optical, 512);

        // Targeted 256x256 crop around center anomaly window
        cv::GMat crop_optical_256 = cv::gapi::crop(in_optical, cv::Rect(896, 896, 256, 256));

        // Stage 2: Fine targeted sub-pixel metrology
        cv::GMat subpixel_edges_roi = fused_subpixel_edge(crop_optical_256, in_calib);
        cv::GOpaque<TopologicalSignature> signature = extract_topology(decimated_optical, subpixel_edges_roi, fft_harmonics, in_thermal);
        cv::GMat micro_crop_roi = compose_micro_crop(crop_optical_256, subpixel_edges_roi, fft_harmonics);

        cv::GComputation pipeline(
            cv::GIn(in_optical, in_thermal, in_calib),
            cv::GOut(subpixel_edges_roi, fft_harmonics, signature, micro_crop_roi)
        );

        auto custom_kernels = cv::gapi::combine(
            get_fused_subpixel_edge_kernel(),
            get_spatial_fft_kernel(),
            get_topological_extractor_kernels()
        );

        auto all_kernels = cv::gapi::combine(
            cv::gapi::core::cpu::kernels(),
            cv::gapi::imgproc::cpu::kernels(),
            custom_kernels
        );

        streaming_pipeline_ = std::make_unique<cv::GStreamingCompiled>(
            pipeline.compileStreaming(cv::compile_args(all_kernels))
        );

        is_compiled_ = true;
        std::cout << "[GAPI_BUILDER] Successfully compiled OpenCV 5 G-API streaming computational graph." << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[GAPI_BUILDER] Warning: Streaming compilation fallback: " << e.what() << std::endl;
        is_compiled_ = false;
        return false;
    }
}

bool GAPIPipelineBuilder::process_frame(
    const cv::Mat& optical_2048,
    const cv::Mat& thermal_512,
    const VisionCalibrationParams& calib,
    PipelineOutput& out
) {
    if (optical_2048.empty()) {
        return false;
    }

    if (is_compiled_ && streaming_pipeline_) {
        try {
            streaming_pipeline_->setSource(cv::gin(optical_2048, thermal_512, calib));
            if (streaming_pipeline_->pull(cv::gout(out.subpixel_edge_roi, out.fft_harmonics, out.signature, out.micro_crop_roi))) {
                return true;
            }
        } catch (...) {
            // Fallthrough to direct optimized execution
        }
    }

    // Direct High-Performance Coarse-to-Fine Execution
    // 1. Stage 1 Area Decimation
    cv::Mat decimated_optical;
    cv::resize(optical_2048, decimated_optical, cv::Size(512, 512), 0, 0, cv::INTER_AREA);

    // 2. Spatial 2D-FFT
    cv::Mat log_mag_img;
    compute_spatial_fft(decimated_optical, out.fft_harmonics, log_mag_img, 2.50f);

    // 3. Stage 2 Targeted 256x256 crop
    cv::Rect roi_rect(
        std::clamp(896, 0, optical_2048.cols - 256),
        std::clamp(896, 0, optical_2048.rows - 256),
        256, 256
    );
    cv::Mat crop_256 = optical_2048(roi_rect).clone();

    // 4. Sub-pixel Scharr interpolation (+- 2.44 um precision)
    out.subpixel_edge_roi = compute_fused_subpixel_edge(crop_256, calib);

    // 5. Signature & Micro-crop synthesis
    out.signature = calculate_topological_signature(decimated_optical, out.subpixel_edge_roi, out.fft_harmonics, thermal_512);
    out.micro_crop_roi = create_composite_micro_crop(crop_256, out.subpixel_edge_roi, out.fft_harmonics);

    return true;
}

} // namespace veripulse
