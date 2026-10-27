#pragma once

#include <opencv2/opencv.hpp>
#include <opencv2/gapi.hpp>
#include <opencv2/gapi/core.hpp>
#include <opencv2/gapi/imgproc.hpp>
#include <memory>
#include <string>

#include "fused_subpixel_edge.hpp"
#include "spatial_fft_kernel.hpp"
#include "topological_extractor.hpp"

namespace veripulse {

struct PipelineOutput {
    cv::Mat subpixel_edge_roi;
    std::vector<float> fft_harmonics;
    TopologicalSignature signature;
    cv::Mat micro_crop_roi; // 256x128 CV_8UC3
};

class GAPIPipelineBuilder {
public:
    GAPIPipelineBuilder(const std::string& model_path = "models/yolov10_microdefect.onnx");
    ~GAPIPipelineBuilder() = default;

    /**
     * @brief Builds and compiles the G-API streaming execution graph.
     */
    bool compile();

    /**
     * @brief Processes a single multi-spectral frame through the coarse-to-fine graph.
     */
    bool process_frame(
        const cv::Mat& optical_2048,
        const cv::Mat& thermal_512,
        const VisionCalibrationParams& calib,
        PipelineOutput& out
    );

    bool is_compiled() const { return is_compiled_; }

private:
    std::string model_path_;
    bool is_compiled_;
    std::unique_ptr<cv::GStreamingCompiled> streaming_pipeline_;
};

} // namespace veripulse
