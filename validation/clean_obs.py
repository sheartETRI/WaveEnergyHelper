"""[F7-a] 깔끔함(clean) 관측 — ETHUSDT 4h (읽기 전용).

규칙·게이트·UI 연결 없음. 실행: python validation/clean_obs.py
"""
import os
import sys
import datetime
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    parse_transition_row,
    classify_structure_at,
    pair_formation_completion,
    _atom_kr,
)
from indicators.pattern_clean import atom_clean_at_confirm, iter_db_dt_confirmations
from validation.gt_trace import (
    load_df_gt,
    zone_ranges,
    evaluate_transition_in_zone,
    SYMBOL,
    INTERVAL,
    fmt_ts,
)
from validation.sweep import atom_confirm_positions

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_df():
    df, _ = load_df_gt(SYMBOL, INTERVAL)
    return df


def global_clean_stats(df):
    """전역 db/dt 확정에 대한 clean / not-clean / indeterminate."""
    totals = Counter()
    by_detector = defaultdict(Counter)
    kind_match_not_clean = 0
    kind_match_total = 0

    for item in iter_db_dt_confirmations(df):
        atom = item["atom"]
        cr = atom_clean_at_confirm(df, atom, item["confirm_pos"])
        status = cr["status"]
        totals[status] += 1
        by_detector[item["detector"]][status] += 1

        pat = item["pattern"]
        kind = cr["kind"]
        if pat == "db" and kind == "HL":
            kind_match_total += 1
            if status == "not-clean":
                kind_match_not_clean += 1
        elif pat == "dt" and kind == "LH":
            kind_match_total += 1
            if status == "not-clean":
                kind_match_not_clean += 1

    return {
        "totals": totals,
        "by_detector": dict(by_detector),
        "kind_match_not_clean": kind_match_not_clean,
        "kind_match_total": kind_match_total,
    }


def collect_hit_atoms(df, zones):
    """엔진 HIT 8건 — db/dt 구성 원자별 clean 판정."""
    rows = []
    rule_rows = {parse_transition_row(r)[2]: parse_transition_row(r) for r in TRANSITION_RULE_TABLE}
    for zone in zones:
        buf = zone["buffer_pos"]
        _, events, _ = evaluate_transition_in_zone(df, buf)
        for e in events:
            if e["mode"] != "HIT":
                continue
            rule_id = e["rule_id"]
            structure, atoms, _, _, window = rule_rows[rule_id]
            a_pos = atom_confirm_positions(df, atoms[0])
            b_pos = atom_confirm_positions(df, atoms[1])
            for i in a_pos:
                for j in b_pos:
                    if abs(i - j) > window - 1:
                        continue
                    form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                    if comp_pos != e["comp_pos"]:
                        continue
                    if classify_structure_at(df, form_pos) != structure:
                        continue
                    for atom, cpos in ((atoms[0], i), (atoms[1], j)):
                        if atom["pattern"] not in ("db", "dt"):
                            continue
                        cr = atom_clean_at_confirm(df, atom, cpos)
                        rows.append({
                            "zone": zone["id"],
                            "rule_id": rule_id,
                            "atom": _atom_kr(atom),
                            "confirm_ts": fmt_ts(df.index[cpos]),
                            "kind": cr["kind"],
                            "prev_opp": cr["prev_opp"],
                            "neckline": cr["neckline"],
                            "clean": cr["status"],
                        })
    return rows


def collect_sweep_atoms(df):
    """스윕 WOULD_HIT — db/dt 원자 clean."""
    rows = []
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, _, window = parse_transition_row(row)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        for i in a_pos:
            for j in b_pos:
                if abs(i - j) > window - 1:
                    continue
                form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                if classify_structure_at(df, form_pos) != structure:
                    continue
                for atom, cpos in ((atoms[0], i), (atoms[1], j)):
                    if atom["pattern"] not in ("db", "dt"):
                        continue
                    cr = atom_clean_at_confirm(df, atom, cpos)
                    rows.append({
                        "rule_id": rule_id,
                        "atom": _atom_kr(atom),
                        "confirm_ts": fmt_ts(df.index[cpos]),
                        "kind": cr["kind"],
                        "clean": cr["status"],
                    })
    return rows


def write_report(global_stats, hit_atoms, sweep_atoms):
    L = []
    L.append("# 깔끔함(clean) 관측 리포트 — ETHUSDT 4h")
    L.append("")
    L.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("- [F7-a] 관측 전용 (규칙·게이트·UI 연결 없음)")
    L.append("- clean 쌍바닥: kind=HL ∧ M1>M0 / clean 쌍봉: kind=LH ∧ T1<T0")
    L.append("")

    t = global_stats["totals"]
    n = sum(t.values()) or 1
    L.append("## 1. 전역 선택도 (db/dt 확정 전체)")
    L.append("")
    L.append(f"- 확정 패턴 수: {n}")
    L.append(f"- clean: {t.get('clean', 0)} ({t.get('clean', 0) / n * 100:.1f}%)")
    L.append(f"- not-clean: {t.get('not-clean', 0)} ({t.get('not-clean', 0) / n * 100:.1f}%)")
    L.append(f"- indeterminate: {t.get('indeterminate', 0)} ({t.get('indeterminate', 0) / n * 100:.1f}%)")
    L.append("")
    L.append("| detector | clean | not-clean | indeterminate |")
    L.append("|---|---|---|---|")
    for det, cnt in sorted(global_stats["by_detector"].items()):
        L.append(
            f"| {det} | {cnt.get('clean', 0)} | {cnt.get('not-clean', 0)} | {cnt.get('indeterminate', 0)} |"
        )
    L.append("")

    L.append("## 2. 기존 hit 생존 — 엔진 HIT db/dt 원자")
    L.append("")
    L.append(f"- db/dt 원자 행 수: {len(hit_atoms)}")
    z2_rows = [r for r in hit_atoms if r["rule_id"] == "F6-5c-b"]
    L.append("")
    L.append("### Z2 F6-5c-b (2 hit × 2 db 원자)")
    L.append("")
    if z2_rows:
        for r in z2_rows:
            po = f"{r['prev_opp']:.4f}" if r["prev_opp"] is not None else "NaN"
            nl = f"{r['neckline']:.4f}" if r["neckline"] is not None else "NaN"
            L.append(
                f"- {r['atom']} @ {r['confirm_ts']}: kind={r['kind']}, "
                f"prev_opp(M0)={po}, neckline(M1)={nl}, **clean={r['clean']}**"
            )
    else:
        L.append("- (없음)")
    L.append("")
    L.append("| zone | rule_id | atom | confirm | kind | clean |")
    L.append("|---|---|---|---|---|---|")
    for r in hit_atoms:
        L.append(f"| {r['zone']} | {r['rule_id']} | {r['atom']} | {r['confirm_ts']} | {r['kind']} | {r['clean']} |")
    L.append("")

    L.append("## 2b. 스윕 WOULD_HIT db/dt 원자")
    L.append("")
    sc = Counter(r["clean"] for r in sweep_atoms)
    sn = len(sweep_atoms) or 1
    L.append(f"- db/dt 원자 행 수: {len(sweep_atoms)}")
    L.append(f"- clean: {sc.get('clean', 0)} ({sc.get('clean', 0) / sn * 100:.1f}%)")
    L.append(f"- not-clean: {sc.get('not-clean', 0)} ({sc.get('not-clean', 0) / sn * 100:.1f}%)")
    L.append(f"- indeterminate: {sc.get('indeterminate', 0)} ({sc.get('indeterminate', 0) / sn * 100:.1f}%)")
    L.append("")

    km = global_stats["kind_match_total"]
    knc = global_stats["kind_match_not_clean"]
    L.append("## 3. kind와의 관계")
    L.append("")
    L.append(f"- kind 일치(HL/LH) 확정 수: {km}")
    L.append(f"- kind 일치이나 not-clean: {knc} ({knc / km * 100:.1f}% of kind-match)" if km else "- kind 일치(HL/LH) 확정: 0")
    L.append("")

    path = os.path.join(OUT_DIR, "REPORT_CLEAN.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"REPORT_CLEAN 작성: {path}")


def main():
    print(f"Loading {SYMBOL} {INTERVAL}...")
    df = _load_df()
    zones = zone_ranges(df)

    global_stats = global_clean_stats(df)
    hit_atoms = collect_hit_atoms(df, zones)
    sweep_atoms = collect_sweep_atoms(df)

    write_report(global_stats, hit_atoms, sweep_atoms)
    print("Done.")


if __name__ == "__main__":
    main()
