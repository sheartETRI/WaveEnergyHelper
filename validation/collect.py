"""실데이터 검증 수집기 (관측 전용).

앱(main.py)과 '동일한' 엔진 함수·데이터 파이프라인을 사용해 6개 조합의 역학관계
트레이스/구조 분포/검출 분포를 수집하고 validation/REPORT.md를 생성한다.

파라미터·규칙·검출기·임계값을 일절 변경하지 않는다. 읽기 전용 관측 도구다.
실행: python validation/collect.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    CUSTOM_INTERVALS,
    WAVE_ENERGY_PARAMS,
    WAVE_LAYER_ROLES,
    CORE_MA_PERIODS,
)
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, resample_timeframe, get_fetch_interval
from indicators.moving_averages import add_moving_averages
from indicators.ma_patterns import add_ma_patterns
from indicators.stochastic import add_stochastic_slow_layers
from analysis.engine import get_ma_alignment
from analysis.wave_energy import analyze_wave_energy
from analysis.dynamics_rules import trace_transitions, structure_distribution

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVALS = ["1d", "4h", "1h"]
GATES = ["HIT", "ATOM_MISSING", "WINDOW_BLOCKED", "KIND_MISMATCH", "STRUCTURE_MISMATCH"]
KINDS = ["HL", "LL", "HH", "LH", "EQ"]


def load_df(symbol, interval):
    """main.py와 동일한 순서로 지표 포함 DataFrame을 만든다 (+트레이스용 MA 패턴)."""
    limit = get_auto_limit(interval)
    fetch_interval = get_fetch_interval(interval)
    raw = fetch_klines(symbol, fetch_interval, limit)
    if not raw:
        raise RuntimeError("fetch_klines가 빈 응답을 반환")
    df = build_dataframe(raw)
    if df is None:
        raise RuntimeError("build_dataframe 실패")
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)
    df = add_moving_averages(df)
    df = add_ma_patterns(df)
    df = add_stochastic_slow_layers(df)
    return df


def gate_of(result):
    return result.split(":", 1)[0]


def count_kinds(df):
    """검출된 모든 패턴 신호의 kind 분포 (스토캐스틱 db/dt/tb/tt 3레이어 + 이평 db/dt)."""
    counter = Counter()
    for suffix in WAVE_LAYER_ROLES.values():
        for pat in ("db", "dt", "tb", "tt"):
            sig = f"stoch_{pat}_{suffix}"
            kind = f"stoch_{pat}_kind_{suffix}"
            if sig in df.columns and kind in df.columns:
                vals = df.loc[df[sig].notna(), kind].dropna()
                counter.update(str(v) for v in vals)
    for n in CORE_MA_PERIODS:
        for pat in ("db", "dt"):
            sig = f"ma{n}_{pat}"
            kind = f"ma{n}_{pat}_kind"
            if sig in df.columns and kind in df.columns:
                vals = df.loc[df[sig].notna(), kind].dropna()
                counter.update(str(v) for v in vals)
    return counter


def fmt_bar(ts):
    if ts is None:
        return "-"
    try:
        return ts.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        return str(ts)


def collect():
    combos = []
    overall_gate = Counter()
    overall_kind = Counter()
    window_blocked_total = 0

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            entry = {"symbol": symbol, "interval": interval}
            try:
                df = load_df(symbol, interval)
                report = analyze_wave_energy(df, symbol, interval)
                alignment = get_ma_alignment(df)
                traces = trace_transitions(df)
                dist = structure_distribution(df)
                kinds = count_kinds(df)

                dyn = report.dynamics
                entry.update({
                    "ok": True,
                    "bars": len(df),
                    "regime": dyn.regime if dyn else "-",
                    "candle_zone": dyn.candle_zone if dyn else "-",
                    "verdict": report.verdict,
                    "alignment": alignment,
                    "trend_hits": [(h.rule_id, h.description) for h in (dyn.hits if dyn else [])],
                    "transition_hits": [(h.rule_id, h.description, fmt_bar(h.bar_index)) for h in (dyn.transition_hits if dyn else [])],
                    "traces": [(t.rule_id, t.result, t.structure_required, str(t.structure_actual), fmt_bar(t.completion_bar)) for t in traces],
                    "gate_counts": Counter(gate_of(t.result) for t in traces),
                    "dist": dist,
                    "kinds": kinds,
                })
                for t in traces:
                    g = gate_of(t.result)
                    overall_gate[g] += 1
                    if g == "WINDOW_BLOCKED":
                        window_blocked_total += 1
                overall_kind.update(kinds)
            except Exception as exc:  # 한 조합 실패해도 계속
                entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            combos.append(entry)

    return combos, overall_gate, overall_kind, window_blocked_total


def dist_ratio(dist):
    total = sum(dist.values()) or 1
    parts = []
    for key in ["U1", "U2", "U3", "D1", "D2", "D3", None]:
        v = dist.get(key, 0)
        label = "None" if key is None else key
        parts.append((label, v, v / total * 100.0))
    none_ratio = dist.get(None, 0) / total * 100.0
    return parts, none_ratio, total


def write_report(combos, overall_gate, overall_kind, window_blocked_total):
    import datetime
    lines = []
    lines.append("# 실데이터 검증 리포트 — §6 역학관계 공식 엔진")
    lines.append("")
    lines.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("- 데이터 소스: 앱과 동일한 엔진 함수(`analyze_wave_energy`, `trace_transitions`, "
                 "`structure_distribution`, `get_ma_alignment`)와 동일 파이프라인(Binance 실데이터)")
    lines.append(f"- 검증 매트릭스: {', '.join(SYMBOLS)} × {', '.join(INTERVALS)} (6조합)")
    lines.append(f"- 윈도: transition_recent_bars = {WAVE_ENERGY_PARAMS['transition_recent_bars']}봉")
    lines.append("- 본 리포트는 관측 전용이다. 파라미터/규칙 변경 제안은 포함하지 않는다 (해석은 검토자의 몫).")
    lines.append("")
    none_high = []

    for e in combos:
        title = f"## {e['symbol']} {e['interval']}"
        lines.append(title)
        if not e.get("ok"):
            lines.append("")
            lines.append(f"**실패**: {e.get('error')}")
            lines.append("")
            continue
        lines.append("")
        lines.append(f"- 봉 수: {e['bars']}")
        lines.append(f"- 레짐: `{e['regime']}` / 캔들존: `{e['candle_zone']}`")
        lines.append(f"- verdict: {e['verdict']}")
        lines.append(f"- MA 배열: {e['alignment']}")
        lines.append(f"- 스크린샷: [{e['symbol']}_{e['interval']}.png](./{e['symbol']}_{e['interval']}.png)")
        lines.append("")
        # trend / transition hits
        if e["trend_hits"]:
            lines.append("**추세 hit (①②):**")
            for rid, desc in e["trend_hits"]:
                lines.append(f"- `{rid}` {desc}")
        else:
            lines.append("**추세 hit (①②):** 없음")
        lines.append("")
        if e["transition_hits"]:
            lines.append("**변곡점 hit (④⑤):**")
            for rid, desc, bar in e["transition_hits"]:
                lines.append(f"- `{rid}` {desc} (완성 봉 {bar})")
        else:
            lines.append("**변곡점 hit (④⑤):** 없음")
        lines.append("")
        # 8행 트레이스
        lines.append("**8행 트레이스:**")
        lines.append("")
        lines.append("| rule_id | result | 구조(req/actual) | 완성 봉 |")
        lines.append("|---|---|---|---|")
        for rid, result, req, actual, bar in e["traces"]:
            lines.append(f"| {rid} | `{result}` | {req}/{actual} | {bar} |")
        lines.append("")
        gc = e["gate_counts"]
        gate_line = ", ".join(f"{g}={gc.get(g, 0)}" for g in GATES)
        lines.append(f"- result 분포: {gate_line}")
        lines.append("")
        # 구조 분포
        parts, none_ratio, total = dist_ratio(e["dist"])
        dist_str = ", ".join(f"{label}={v}({pct:.1f}%)" for label, v, pct in parts)
        lines.append(f"**구조 분포** (총 {total}봉): {dist_str}")
        lines.append(f"- None 비율: **{none_ratio:.1f}%**")
        lines.append("")
        if none_ratio >= 50.0:
            none_high.append((f"{e['symbol']} {e['interval']}", none_ratio))

    # 종합 섹션
    lines.append("---")
    lines.append("")
    lines.append("## 종합 (관측만)")
    lines.append("")
    total_rules = sum(overall_gate.values()) or 1
    lines.append("### 1) 전 조합 합산 차단 게이트 빈도")
    lines.append("")
    lines.append("| 게이트 | 건수 | 비율 |")
    lines.append("|---|---|---|")
    for g in GATES:
        v = overall_gate.get(g, 0)
        lines.append(f"| {g} | {v} | {v / total_rules * 100:.1f}% |")
    lines.append(f"| (합계) | {total_rules} | 100.0% |")
    lines.append("")
    lines.append("### 2) WINDOW_BLOCKED 총 건수")
    lines.append("")
    lines.append(f"- 원자는 데이터에 존재하나 transition_recent_bars"
                 f"({WAVE_ENERGY_PARAMS['transition_recent_bars']}봉) 윈도에 들어오지 못해 차단된 규칙: "
                 f"**{window_blocked_total}건** (8행 × 6조합 = 48행 중)")
    lines.append("")
    lines.append("### 3) 검출된 kind 분포 (HL/LL/HH/LH)")
    lines.append("")
    total_kind = sum(overall_kind.get(k, 0) for k in KINDS) or 1
    lines.append("| kind | 건수 | 비율 |")
    lines.append("|---|---|---|")
    for k in KINDS:
        v = overall_kind.get(k, 0)
        lines.append(f"| {k} | {v} | {v / total_kind * 100:.1f}% |")
    lines.append(f"| (합계) | {total_kind} | 100.0% |")
    lines.append("")
    lines.append("### 4) 구조 None 비율이 높은 조합")
    lines.append("")
    if none_high:
        for name, ratio in sorted(none_high, key=lambda x: -x[1]):
            lines.append(f"- {name}: None **{ratio:.1f}%**")
    else:
        lines.append("- None 비율 50% 이상 조합 없음 (각 조합 섹션의 None 비율 참조)")
    lines.append("")
    lines.append("### 스크린샷 링크")
    lines.append("")
    for e in combos:
        lines.append(f"- [{e['symbol']}_{e['interval']}.png](./{e['symbol']}_{e['interval']}.png)")
    lines.append("")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "REPORT.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"REPORT 작성: {out_path}")


if __name__ == "__main__":
    combos, overall_gate, overall_kind, window_blocked_total = collect()
    write_report(combos, overall_gate, overall_kind, window_blocked_total)
    for e in combos:
        status = "OK" if e.get("ok") else f"FAIL({e.get('error')})"
        print(f"{e['symbol']} {e['interval']}: {status}")
