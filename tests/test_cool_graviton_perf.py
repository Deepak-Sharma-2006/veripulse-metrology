"""
VeriPulse COOL vs. x86 Graviton Performance & Consistency Benchmark Test
=======================================================================
Validates:
  1. AWS Graviton3 (Arm Neoverse-V1) COOL v3.1 reference efficiency calculations:
     - 28% lower latency (4.18 ms vs 5.82 ms)
     - 35% higher throughput (238 rps vs 176 rps)
     - 40% cloud cost reduction ($0.0816/hr vs $0.1360/hr)
  2. Numerical and topological equivalence across defect profiles:
     - Specular glare, slot-die ribbing, micro-pinhole, nominal substrate
  3. Real-time micro-crop processing latency and throughput jitter.
"""

import os
import sys
import time
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cloud_metrology_cool.cool_spatial_verifier import (
    verify_micro_crop,
    generate_test_micro_crop,
    ENGINE_NAME,
    IS_ARM64,
)
from cloud_metrology_cool.benchmark_cool_vs_x86 import (
    REFERENCE_BENCHMARKS,
    run_local_empirical_benchmark,
)


class TestCoolGravitonPerformance(unittest.TestCase):
    def test_01_reference_benchmark_metrics(self):
        """Validates the official AWS Graviton3 vs x86 benchmark specs and cost model."""
        x86_spec = REFERENCE_BENCHMARKS["aws_x86_c6i_xlarge"]
        graviton_spec = REFERENCE_BENCHMARKS["aws_graviton3_cool_c7g_xlarge"]

        # 1. Latency advantage >= 25%
        latency_reduction_pct = (
            (x86_spec["avg_latency_ms"] - graviton_spec["avg_latency_ms"])
            / x86_spec["avg_latency_ms"]
        ) * 100.0
        self.assertGreaterEqual(latency_reduction_pct, 25.0)

        # 2. Throughput advantage >= 30%
        throughput_increase_pct = (
            (graviton_spec["throughput_rps"] - x86_spec["throughput_rps"])
            / x86_spec["throughput_rps"]
        ) * 100.0
        self.assertGreaterEqual(throughput_increase_pct, 30.0)

        # 3. Cost reduction >= 35%
        cost_reduction_pct = (
            (x86_spec["hourly_cost_usd"] - graviton_spec["hourly_cost_usd"])
            / x86_spec["hourly_cost_usd"]
        ) * 100.0
        self.assertGreaterEqual(cost_reduction_pct, 35.0)

        # 4. Latency budget compliance (< 8.0 ms edge / cloud roundtrip)
        self.assertLess(graviton_spec["avg_latency_ms"], 5.0)
        self.assertLess(graviton_spec["p99_latency_ms"], 6.0)

    def test_02_spatial_verification_consistency(self):
        """Verifies topological metrics consistency across all physical defect classes."""
        defect_classes = ["glare", "ribbing", "pinhole", "nominal"]

        for defect in defect_classes:
            raw_crop = generate_test_micro_crop(defect)
            self.assertGreater(len(raw_crop), 0, f"Generated empty crop for {defect}")

            result = verify_micro_crop(raw_crop)
            self.assertIn("verdict", result)
            self.assertIn("morphological_solidity", result)
            self.assertIn("aspect_ratio", result)
            self.assertIn("execution_time_ms", result)

            if defect == "glare":
                self.assertEqual(result["verdict"], "specular_reflection_suspected")
                self.assertGreaterEqual(result["specular_saturation_ratio"], 0.05)
            elif defect == "pinhole":
                self.assertEqual(result["verdict"], "physical_defect_pinhole")
                self.assertGreaterEqual(result["verified_contour_count"], 1)
            elif defect == "ribbing":
                self.assertEqual(result["verdict"], "physical_defect_ribbing")
            elif defect == "nominal":
                self.assertEqual(result["verdict"], "nominal_surface")

    def test_03_empirical_local_benchmark_execution(self):
        """Runs reproducible benchmark on active host and validates latency bounds."""
        iterations = 50
        bench_result = run_local_empirical_benchmark(iterations=iterations)

        self.assertEqual(bench_result["iterations"], iterations)
        self.assertGreater(bench_result["throughput_rps"], 0.0)
        self.assertLess(bench_result["avg_latency_ms"], 30.0, "Local verification latency too high")

        # P99 must be bounded to prevent supervisory buffer backpressure
        self.assertLess(bench_result["p99_latency_ms"], 50.0)


if __name__ == "__main__":
    unittest.main()
