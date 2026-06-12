"""Wave Final Synthesis 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_final_synthesis import (
    FINAL_VERDICT,
    HYPOTHESES,
    RESEARCH_TIMELINE,
    build_synthesis,
    run_final_synthesis,
    verify_inputs_unchanged,
    write_report,
)

VDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")


def test_timeline_25_steps():
    assert len(RESEARCH_TIMELINE) == 25
    assert RESEARCH_TIMELINE[-1]["step"] == 25


def test_hypotheses_verdicts():
    valid = {"ACCEPTED", "PARTIAL", "REJECTED"}
    assert all(h["verdict"] in valid for h in HYPOTHESES)
    assert len(HYPOTHESES) == 8


def test_build_synthesis():
    s = build_synthesis()
    assert s["final_verdict"] == FINAL_VERDICT
    assert "contribution" in s
    assert s["contribution"]["residual"] > 90


def test_verify_inputs():
    check = verify_inputs_unchanged()
    assert check["csvs_found"] >= 4
    assert check["reports_found"] >= 10


def test_write_report_sections(tmp_path):
    s = build_synthesis()
    out = os.path.join(tmp_path, "test_report.md")
    write_report(s, out)
    with open(out, encoding="utf-8") as f:
        text = f.read()
    for section in (
        "Executive Summary", "Research Timeline", "Hypothesis Validation",
        "Champion Rules", "Champion Filters", "Final Verdict",
    ):
        assert section in text


def test_run_final_synthesis_produces_artifacts():
    result = run_final_synthesis()
    assert result["final_verdict"] in ("FAILED", "WEAK", "CONDITIONAL", "PROMISING", "STRONG")
    assert os.path.isfile(result["report_path"])
    assert os.path.isfile(result["png_path"])


def test_existing_entry_filter_unchanged():
    path = os.path.join(VDIR, "wave_entry_filter_refinement.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert len(df) > 0


def test_existing_journal_unchanged():
    path = os.path.join(VDIR, "wave_live_forward_journal.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "event_id" in df.columns
