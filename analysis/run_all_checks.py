"""
SPHEREx Sky Viewer — Master Verification & Release Suite
=========================================================
Runs all test suites from a clean start:
1. Stage 1: Data models and shared interface guards
2. Stage 2: Aperture photometry and sky background subtraction
3. Stage 3: Multi-detector spectrum extraction and 6-band plotting
4. Stage 4: Time-series light curve extraction, AB magnitudes, and saturation
5. Stage 5: Scientific validation of the 5 NASA challenge targets

Prints a comprehensive verification scorecard for delivery to the team.
"""

import sys
import time
import subprocess


TEST_SCRIPTS = [
    ("Stage 1: Data Models & Interfaces", "test_data_models.py"),
    ("Stage 2: Core Photometry Engine", "test_photometry.py"),
    ("Stage 3: Multi-Detector Spectrum Engine", "test_spectrum.py"),
    ("Stage 4: Time-Series Light Curve Engine", "test_light_curve.py"),
    ("Stage 5: 5 Challenge Targets Validation", "test_targets.py"),
    ("Stage 6: Frame Stacking & Coaddition", "test_stacking.py"),
    ("Stage 7: User Target & FITS WCS Pipeline", "test_fits_pipeline.py"),
]


def run_test_suite():
    print("=" * 76)
    print(" SPHEREx Sky Viewer — Member 3 Master Verification Suite")
    print("=" * 76)
    print(f"Python interpreter: {sys.executable}\n")

    results = []
    total_start = time.time()

    for name, script in TEST_SCRIPTS:
        print(f"--> Running: {name} ({script})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, script], capture_output=True, text=True)
        elapsed = time.time() - t0

        if res.returncode == 0:
            print(f"    Status: PASSED ({elapsed:.2f}s)\n")
            results.append((name, "PASSED", elapsed, None))
        else:
            print(f"    Status: FAILED ({elapsed:.2f}s)")
            print("    Error details:\n" + res.stderr)
            results.append((name, "FAILED", elapsed, res.stderr))

    total_time = time.time() - total_start

    print("=" * 76)
    print(" FINAL VERIFICATION SCORECARD")
    print("=" * 76)
    print(f"{'Test Area':<45} | {'Status':<10} | {'Time':<8}")
    print("-" * 76)

    all_passed = True
    for name, status, elapsed, err in results:
        status_str = f"[{status}]"
        print(f"{name:<45} | {status_str:<10} | {elapsed:.2f}s")
        if status != "PASSED":
            all_passed = False

    print("-" * 76)
    print(f"Total Verification Time: {total_time:.2f} seconds")
    print("=" * 76)

    if all_passed:
        print(">> ALL SYSTEMS OPERATIONAL: Member 3 analysis suite is clean & release-ready!")
        print("=" * 76)
        sys.exit(0)
    else:
        print(">> VERIFICATION FAILED: Please inspect errors above.")
        print("=" * 76)
        sys.exit(1)


if __name__ == "__main__":
    run_test_suite()
