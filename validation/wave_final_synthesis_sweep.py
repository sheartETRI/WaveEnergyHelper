"""Wave Final Synthesis 스윕 — REPORT · PNG 생성."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_final_synthesis import run_final_synthesis

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("building final synthesis...")
    result = run_final_synthesis()
    print(f"report: {os.path.basename(result['report_path'])}")
    print(f"png: {os.path.basename(result['png_path'])}")
    print(f"verdict: {result['final_verdict']}")
    print("final synthesis complete")


if __name__ == "__main__":
    main()
