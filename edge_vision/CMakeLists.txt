cmake_minimum_required(VERSION 3.20)
project(veripulse_edge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable optimizations
if(MSVC)
    add_compile_options(/O2 /W4 /fp:fast /arch:AVX2)
else()
    add_compile_options(-O3 -Wall -Wextra -mavx2 -mfma -ffast-math)
endif()

find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs gapi)
find_package(Threads REQUIRED)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${OpenCV_INCLUDE_DIRS}
)

set(LIB_SOURCES
    src/fused_subpixel_edge.cpp
    src/spatial_fft_kernel.cpp
    src/topological_extractor.cpp
    src/gapi_pipeline_builder.cpp
)

add_library(veripulse_edge_lib STATIC ${LIB_SOURCES})
target_link_libraries(veripulse_edge_lib PUBLIC ${OpenCV_LIBS} Threads::Threads)

if(UNIX AND NOT APPLE)
    target_link_libraries(veripulse_edge_lib PUBLIC rt)
endif()

add_executable(veripulse_edge src/main_edge.cpp)
target_link_libraries(veripulse_edge PRIVATE veripulse_edge_lib)

# Benchmark & Verification Tests
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../tests/test_gapi_throughput.cpp")
    add_executable(test_gapi_throughput ../tests/test_gapi_throughput.cpp)
    target_link_libraries(test_gapi_throughput PRIVATE veripulse_edge_lib)
endif()

if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../tests/test_subpixel_accuracy.cpp")
    add_executable(test_subpixel_accuracy ../tests/test_subpixel_accuracy.cpp)
    target_link_libraries(test_subpixel_accuracy PRIVATE veripulse_edge_lib)
endif()

message(STATUS "VeriPulse Edge Vision CMake configured with OpenCV: ${OpenCV_VERSION}")
