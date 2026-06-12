"""Wave Rule Set Robustness UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_RULESET_ROBUSTNESS.md")
    if not os.path.isfile(path):
        return {}
    data = {"champion": "", "pass_fail": "", "scores": [], "walk": []}
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 9."):
                section = "champion"
            elif line.startswith("## 10."):
                section = "pass"
            elif line.startswith("## 8."):
                section = "scores"
            elif line.startswith("## 2."):
                section = "walk"
            elif line.startswith("## ") and section:
                section = None
            elif section == "champion" and line.startswith("**"):
                data["champion"] = line.replace("**", "")
            elif section == "pass" and line.startswith("**"):
                data["pass_fail"] = line.replace("**", "")
            elif section == "scores" and line.startswith("|") and "---" not in line and "rule" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    data["scores"].append({"rule": parts[0], "score": parts[1]})
            elif section == "walk" and line.startswith("|") and "---" not in line and "rule" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    data["walk"].append({
                        "rule": parts[0], "quarter": parts[1],
                        "n": parts[2], "exp": parts[4],
                    })
    return data


def render_wave_ruleset_robustness_panel(symbol: str, interval: str) -> None:
    st.markdown("### Rule Set Robustness")

    report = _load_report()
    if not report:
        st.warning("Robustness 데이터 없음 — wave_ruleset_robustness_sweep.py 실행 필요")
        return

    if report.get("pass_fail"):
        st.caption(f"실전 가능성: {report['pass_fail']}")

    st.markdown("**Champion Rule**")
    st.caption(report.get("champion") or "—")

    st.markdown("**Robustness Score**")
    for row in report.get("scores", [])[:5]:
        st.caption(f"{row['rule']}: {row['score']}")

    st.markdown("**Walk Forward (expectancy)**")
    for row in report.get("walk", [])[:8]:
        if row["rule"] in ("RULE_A", "RULE_B"):
            st.caption(f"{row['rule']} {row['quarter']}: n={row['n']}, exp={row['exp']}")
