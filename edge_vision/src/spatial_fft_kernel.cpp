#include "spatial_fft_kernel.hpp"
#include <opencv2/gapi/cpu/gcpukernel.hpp>
#include <cmath>
#include <algorithm>

namespace veripulse {

static void fftshift(cv::Mat& mag) {
    int cx = mag.cols / 2;
    int cy = mag.rows / 2;

    cv::Mat q0(mag, cv::Rect(0, 0, cx, cy));
    cv::Mat q1(mag, cv::Rect(cx, 0, cx, cy));
    cv::Mat q2(mag, cv::Rect(0, cy, cx, cy));
    cv::Mat q3(mag, cv::Rect(cx, cy, cx, cy));

    cv::Mat tmp;
    q0.copyTo(tmp);
    q3.copyTo(q0);
    tmp.copyTo(q3);

    q1.copyTo(tmp);
    q2.copyTo(q1);
    tmp.copyTo(q2);
}

void compute_spatial_fft(
    const cv::Mat& in_512,
    std::vector<float>& out_bins_512,
    cv::Mat& out_log_mag_img,
    float line_speed_mps
) {
    out_bins_512.resize(512, 0.0f);

    cv::Mat float_img;
    if (in_512.channels() > 1) {
        cv::Mat gray;
        cv::cvtColor(in_512, gray, cv::COLOR_BGR2GRAY);
        gray.convertTo(float_img, CV_32F);
    } else {
        in_512.convertTo(float_img, CV_32F);
    }

    if (float_img.rows != 512 || float_img.cols != 512) {
        cv::resize(float_img, float_img, cv::Size(512, 512), 0, 0, cv::INTER_AREA);
    }

    // 1. Zero-mean normalisation to suppress DC spike
    cv::Scalar mean_val = cv::mean(float_img);
    float_img -= mean_val[0];

    // 2. Complex 2D Forward DFT
    cv::Mat planes[] = {float_img, cv::Mat::zeros(float_img.size(), CV_32F)};
    cv::Mat complex_img;
    cv::merge(planes, 2, complex_img);

    cv::dft(complex_img, complex_img, cv::DFT_COMPLEX_OUTPUT);

    // 3. Compute magnitude spectrum
    cv::split(complex_img, planes);
    cv::Mat mag;
    cv::magnitude(planes[0], planes[1], mag);

    // 4. Center the spectrum (fftshift)
    fftshift(mag);

    // 5. Compute 1D profile across web travel axis (horizontal average across central bands)
    int cy = mag.rows / 2;
    int band_half = 16;
    int y_start = std::max(0, cy - band_half);
    int y_end   = std::min(mag.rows, cy + band_half);

    float max_power = 1e-6f;
    std::vector<float> raw_profile(512, 0.0f);
    for (int x = 0; x < 512; ++x) {
        float sum = 0.0f;
        for (int y = y_start; y < y_end; ++y) {
            sum += mag.at<float>(y, x);
        }
        float avg = sum / (y_end - y_start);
        raw_profile[x] = avg;
        if (avg > max_power) {
            max_power = avg;
        }
    }

    // Normalize power bins to [0.0, 1.0]
    for (int i = 0; i < 512; ++i) {
        out_bins_512[i] = raw_profile[i] / max_power;
    }

    // 6. Generate 8-bit log-magnitude image for visual dashboard / micro-crop
    cv::Mat log_mag;
    mag += cv::Scalar::all(1.0);
    cv::log(mag, log_mag);
    cv::normalize(log_mag, out_log_mag_img, 0, 255, cv::NORM_MINMAX, CV_8U);
}

GAPI_OCV_KERNEL(GOCVSpatialFFT, GSpatialFFT) {
    static void run(const cv::Mat& in, int bins, std::vector<float>& out) {
        cv::Mat dummy_mag;
        compute_spatial_fft(in, out, dummy_mag, 2.50f);
    }
};

cv::GArray<float> spatial_fft_node(const cv::GMat& in_decimated_512, int bins) {
    return GSpatialFFT::on(in_decimated_512, bins);
}

cv::gapi::GKernelPackage get_spatial_fft_kernel() {
    return cv::gapi::kernels<GOCVSpatialFFT>();
}

} // namespace veripulse
