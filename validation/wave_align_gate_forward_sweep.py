"""§6 전방 추적 실행기 — gate_align 기록 · 6개월 보고.

docs/SPEC_WAVE_ALIGN_GATE_FORWARD.md (동결 헌장) 의 실행 도구.

    python validation/wave_align_gate_forward_sweep.py --status    # 현재 게이트 개방 여부
    python validation/wave_align_gate_forward_sweep.py --annotate  # 사이드카 기록 (무개입)
    python validation/wave_align_gate_forward_sweep.py --report    # 6개월 보고 + 재검토 판정
"""
from __future__ import annotations

import os
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_align_gate_forward import (
    CHARTER_FROZEN_AT,
    INTEGRITY_FILES,
    PROMOTED_LTF_TO_HTF,
    REVIEW_RULE,
    SIDECAR_COLS,
    TRACKING_START,
    annotate_gate_align,
    current_gate_status,
    forward_slice,
    gate_states,
    load_htf_pipe,
    review_decision,
    sidecar_path,
    tracking_status,
)
from analysis.wave_htf_gate import expectancy_20, gate_mask
from analysis.wave_htf_gate_v2 import SYMBOLS_V2
from validation.wave_align_gate_sweep import (
    BOOTSTRAP_SEED,
    add_cluster_keys,
    month_cluster_bootstrap,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT_DIR)
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_ALIGN_GATE_FORWARD.md")


def _fmt(v, d=4):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    return f"{v:.{d}f}"


def load_live_journal() -> pd.DataFrame:
    path = os.path.join(OUT_DIR, "wave_live_forward_journal.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


# ------------------------------------------------------------------ 무개입
def integrity_commits(since: pd.Timestamp = CHARTER_FROZEN_AT) -> list[dict]:
    """추적 기간 중 정의 파일에 발생한 커밋 (헌장 §3 감사용)."""
    rows: list[dict] = []
    for rel in INTEGRITY_FILES:
        try:
            out = subprocess.run(
                ["git", "log", f"--since={since.date()}", "--format=%h|%ad|%s",
                 "--date=short", "--", rel],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            ).stdout.strip()
        except Exception as exc:  # noqa: BLE001 — 감사 정보이므로 실패해도 계속
            rows.append({"file": rel, "commit": "", "date": "", "subject": f"git 실패: {exc}"})
            continue
        for line in filter(None, out.splitlines()):
            h, d, s = (line.split("|", 2) + ["", "", ""])[:3]
            rows.append({"file": rel, "commit": h, "date": d, "subject": s})
    return rows


def integrity_tests_pass() -> tuple[bool, str]:
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/test_align_gate_forward_integrity.py", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=600,
        )
        tail = (res.stdout or "").strip().splitlines()
        return res.returncode == 0, tail[-1] if tail else ""
    except Exception as exc:  # noqa: BLE001
        return False, f"실행 실패: {exc}"


# ------------------------------------------------------------------ 명령
def cmd_status() -> None:
    rows = current_gate_status()
    print(f"[gate] F2-b 개방 여부 (마지막 닫힌 봉 기준) — 기록 전용, 매매 신호 아님")
    for r in rows:
        state = "OPEN" if r.get("gate_align") else "CLOSED"
        if r.get("gate_align") is None:
            state = "N/A"
        print(f"  {r['symbol']:9s} {r['htf']:3s} {state:6s} "
              f"연속 {r.get('open_bars', 0)}봉  최근120봉 개방률 "
              f"{r.get('open_rate_recent')}  ({r.get('htf_open_time')})")


def cmd_annotate() -> None:
    journal = load_live_journal()
    if journal.empty:
        raise SystemExit("wave_live_forward_journal.csv 없음")

    htfs = sorted(set(PROMOTED_LTF_TO_HTF.values()))
    states: dict[tuple, pd.DataFrame] = {}
    for htf in htfs:
        for sym in SYMBOLS_V2:
            states[(sym, htf)] = gate_states(sym, htf, load_htf_pipe(sym, htf))

    sidecar = annotate_gate_align(journal, states)
    sidecar.to_csv(sidecar_path(), index=False)
    scope = sidecar["gate_scope"].value_counts().to_dict()
    fwd = forward_slice(sidecar)
    print(f"[annotate] events={len(sidecar)} -> {sidecar_path()}")
    print(f"[annotate] scope={scope}")
    print(f"[annotate] 전방({TRACKING_START.date()} 이후) 평가 대상={len(fwd)}건 "
          f"gate_align=True {int(fwd['gate_align'].fillna(False).astype(bool).sum()) if len(fwd) else 0}건")
    print("[annotate] 원본 저널은 수정하지 않았다 (기록 전용).")


def _delta_prime_forward(df: pd.DataFrame):
    if df.empty:
        return None
    d = df.copy()
    d["g_align"] = d["gate_align"].fillna(False).astype(bool)
    e_align = expectancy_20(d[gate_mask(d, "G_ALIGN")])
    e_all = expectancy_20(d)
    if e_align is None or e_all is None:
        return None
    return round(e_align - e_all, 4)


def cmd_report() -> None:
    path = sidecar_path()
    if not os.path.isfile(path):
        raise SystemExit("사이드카 없음 — 먼저 --annotate 실행")
    sidecar = pd.read_csv(path, parse_dates=["timestamp"])
    fwd = forward_slice(sidecar)
    fwd = fwd[fwd["return_20"].notna()] if "return_20" in fwd.columns else fwd

    status = tracking_status()
    if not fwd.empty:
        fwd = fwd.copy()
        fwd["g_align"] = fwd["gate_align"].fillna(False).astype(bool)
        fwd["ltf"] = fwd["timeframe"]
        fwd = add_cluster_keys(fwd)
        boot = month_cluster_bootstrap(fwd, seed=BOOTSTRAP_SEED)
    else:
        boot = {"delta": None, "ci_low": None, "ci_high": None, "n_boot": 0,
                "n_blocks": 0, "n_events": 0, "seed": BOOTSTRAP_SEED}
    decision = review_decision(boot)
    commits = integrity_commits()
    tests_ok, tests_line = integrity_tests_pass()

    L: list[str] = []
    L.append("# REPORT_WAVE_ALIGN_GATE_FORWARD")
    L.append("")
    L.append("SPEC_WAVE_ALIGN_GATE §6 전방 추적. "
             "**새 판정이 아니라 승격 유지/회수 재검토의 트리거다.**")
    L.append("")
    L.append("## 1. 추적 상태")
    L.append("")
    L.append(f"- 시작 {status['start'].date()} · 보고 예정 {status['due'].date()} "
             f"({status['months']}개월)")
    L.append(f"- 현재 {status['now'].date()} · 경과 {status['elapsed_days']}일 · "
             f"기한 도달 {'예' if status['due_reached'] else '아니오'}")
    L.append(f"- 전방 평가 대상 이벤트 {len(fwd)}건 (승격 쌍 · 결과 확정분)")
    if not status["due_reached"]:
        L.append("")
        L.append("**기한 미도달 — 아래 수치는 중간 관측이며 재검토 판정의 근거가 아니다.**")
    L.append("")

    L.append("## 2. 전방 Δ′ 와 재검토 판정")
    L.append("")
    L.append(f"동결 규칙: {REVIEW_RULE}")
    L.append("")
    L.append(f"Δ′ = **{_fmt(boot.get('delta'))}** "
             f"(월 클러스터 부트스트랩 {boot.get('n_boot')}회, 95% CI "
             f"[{_fmt(boot.get('ci_low'))}, {_fmt(boot.get('ci_high'))}], "
             f"블록 {boot.get('n_blocks')}개, 이벤트 {boot.get('n_events')}건, "
             f"seed={boot.get('seed')})")
    L.append("")
    L.append(f"**판정: {decision['decision']}** — {decision['reason']}")
    L.append("")

    L.append("## 3. 무개입 감사 (헌장 §3)")
    L.append("")
    L.append(f"- 회귀 테스트 `tests/test_align_gate_forward_integrity.py`: "
             f"**{'PASS' if tests_ok else 'FAIL'}** ({tests_line})")
    if not tests_ok:
        L.append("- **테스트가 깨져 있다. 정의가 바뀌었다면 이 추적은 무효이며 "
                 "기간을 리셋하고 그 사실을 남겨야 한다 (헌장 §3-5).**")
    L.append("")
    L.append(f"헌장 동결({CHARTER_FROZEN_AT.date()}) 이후 정의 파일 커밋 "
             f"(그 이전 커밋은 헌장·배선 수립 작업 자체이므로 감사 대상이 아니다):")
    L.append("")
    if commits:
        L.append("| 파일 | 커밋 | 날짜 | 제목 |")
        L.append("|---|---|---|---|")
        for c in commits:
            L.append(f"| `{c['file']}` | {c['commit']} | {c['date']} | {c['subject']} |")
        L.append("")
        L.append("**커밋이 존재한다. 각 건이 정의를 바꿨는지 확인해야 한다** — "
                 "회귀 테스트 통과는 산출물 동치성만 보장하며, 리팩터링은 통과할 수 있다.")
    else:
        L.append("없음. 추적 기간 중 정의 파일은 변경되지 않았다.")
    L.append("")

    L.append("## 4. 한계")
    L.append("")
    L.append("- 본 검정(같은 데이터)의 보조 진단이 나빴다는 점은 그대로다: "
             "에피소드 부호 비율 0.24~0.41, 연도별 Δ′ 6년 중 3년 음수.")
    L.append("- 전방 표본은 6개월치이므로 월 블록 수가 적고 CI 가 넓다. "
             "`EXTEND` 결정이 자주 나올 수 있으며, 그것이 설계 의도다.")
    L.append("- gate_align 은 기록 전용이었고 이벤트 집합·순서에 영향을 주지 않았다.")
    L.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[report] -> {REPORT_PATH}")
    print(f"[report] decision={decision['decision']} delta={boot.get('delta')} "
          f"CI=[{boot.get('ci_low')}, {boot.get('ci_high')}] integrity_tests={'PASS' if tests_ok else 'FAIL'}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--status":
        cmd_status()
    elif args and args[0] == "--annotate":
        cmd_annotate()
    elif args and args[0] == "--report":
        cmd_report()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
