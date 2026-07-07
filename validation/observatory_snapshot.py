"""9차 위임 보고 — 관측 계기판 현재 시점 스냅샷 (BTC·ETH) + REPORT_OBSERVATORY_R1.md 생성.

표시·관측 전용. UI(streamlit) 렌더 텍스트를 build_* 순수 함수로 그대로 산출해 리포트에 싣는다
(스크린샷 대체 — 텍스트 리포트엔 실제 렌더 라인이 더 정확). 판정·통계 아님.

실행: `python validation/observatory_snapshot.py`
"""
import logging
import os
import sys
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_state_machine import prepare_base_frame  # noqa: E402
from analysis.observatory import (  # noqa: E402
    composite_trend_label,
    monthly_stoch_position,
    precursor_channel,
    slope_state,
)
from analysis.tf_ladder import assess_tf_data, lower, upper  # noqa: E402
from analysis.trend_layer import add_trend_observation  # noqa: E402
from config.settings import OBSERVATORY_PARAMS  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402
from display.observatory import (  # noqa: E402
    build_monthly_stoch_lines,
    build_precursor_lines,
    build_slope_dashboard_lines,
)

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
PRECURSOR_TFS = ["1d", "4d", "1M"]
HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_OBSERVATORY_R1.md")


def _load(symbol, tf):
    bare = fetch_ohlcv_bare(symbol, tf)
    if bare is None or bare.empty:
        return None
    return prepare_base_frame(bare)


def snapshot(symbol):
    f1d, f4d, f1m = _load(symbol, "1d"), _load(symbol, "4d"), _load(symbol, "1M")
    s1d = slope_state(f1d, 60) if f1d is not None else None
    s4d = slope_state(f4d, 60) if f4d is not None else None
    comp = composite_trend_label(s1d["state"] if s1d else None, s4d["state"] if s4d else None)
    # 월봉
    m_bars = 0 if f1m is None else len(f1m)
    m_pos = None
    if f1m is not None:
        m_pos = monthly_stoch_position(add_trend_observation(f1m.copy()))
    m_assess = assess_tf_data(m_bars, "1M")
    # 전조 채널 (TF별)
    frames = {"1d": f1d, "4d": f4d, "1M": f1m}
    precursors = {}
    for tf in PRECURSOR_TFS:
        fr = frames[tf]
        precursors[tf] = precursor_channel(fr, symbol, tf) if fr is not None else None
    return {
        "symbol": symbol, "s1d": s1d, "s4d": s4d, "comp": comp,
        "slope_lines": build_slope_dashboard_lines(symbol, s1d, s4d),
        "m_bars": m_bars, "m_pos": m_pos, "m_assess": m_assess,
        "m_lines": build_monthly_stoch_lines(symbol, m_pos, m_bars),
        "precursors": precursors, "frames": frames,
        "span": (f1d.index[0], f1d.index[-1]) if f1d is not None else (None, None),
    }


def write_report(snaps):
    L = [
        "# REPORT_OBSERVATORY_R1 — 관측 계기판 1라운드 (9차 위임)\n",
        "성격: **표시·관측 전용.** 판정·게이트·필터·백테스트·시그널 등급 없음. PHASE7 결론",
        "(\"관측·의사결정 보조 도구로 확정\")의 첫 구현 라운드. 모든 신규 기능은 표시와 저널 기록까지만.\n",
        "## A. 밀린 커밋 정리 (선행 — 완료)\n",
        "PHASE3 이후 미커밋 백로그를 논리 단위 4커밋으로 정리:",
        "",
        "| 커밋 | 내용 |",
        "|---|---|",
        "| `v2 PHASE4-6` | 파동 번역충실도(array_context·candle·concordance) + 기법0 추세 관측계기(trend_layer) + 저널 배선. trend_layer/settings/test는 PHASE7 스펙 교정 최종 상태 포함(백로그 병합) |",
        "| `v2 PHASE7` | 기법0 스펙 정합 재주석 리포트·스크립트(H-T1/H-T2 양대 기각 → 시그널 검증 경로 종료) |",
        "| `8차 60MA` | 일봉 60MA 추세선 구조 검증(H-1 미달·H-2 통과·H-3 미달) |",
        "| `스펙 v1.1` | 기법0 동결 스펙 §2.5 전조 채널 디스패처 추가 |",
        "",
        "> 주: PHASE4~7이 커밋 없이 누적돼 다회차가 건드린 파일(trend_layer·settings)은 파일 단위 분리가",
        "> 불가하여 최종 상태로 대표 라운드 커밋에 포함하고 커밋 메시지에 명시(정직성).",
        "",
        "## B. 1M(월봉) TF 추가 — 관측 전용\n",
        "- `TF_POOL`에 `\"1M\"` 추가(최상단). 인접 비율(×3.5~×6)상 2w와 ×2.14 → **상·하위 없는 고립 TF**.",
        f"  단위 테스트 고정: `upper(\"1M\")={upper('1M')}`, `lower(\"1M\")={lower('1M')}`, `upper(\"2w\")={upper('2w')}`",
        "  (`tests/test_tf_ladder.py::test_1M_isolated_observation_tf`, 인접표에 `(\"1M\", None, None)` 행 고정).",
        "- 데이터: 바이낸스 **1M 네이티브**(fetch_ohlcv_bare, 리샘플 아님).",
        "- CORE_MA 부분집합 운용 (심볼별 가용 봉수 기준):",
        "",
        "| 심볼 | 월봉 수 | usable MA | missing MA | 비고 |",
        "|---|---|---|---|---|",
    ]
    for s in snaps:
        a = s["m_assess"]
        L.append(f"| {s['symbol']} | {s['m_bars']} | {'/'.join('MA'+str(p) for p in a.usable_ma_periods)} | "
                 f"{'/'.join('MA'+str(p) for p in a.missing_ma_periods) or '—'} | MA60 산출 가능·MA120 불가 |")
    L += [
        "",
        "- 월봉 패턴/candidate·대파동 위치는 **표시만**(표본 희소 — 승격·통계 대상 아님, UI 명시).",
        "- 스토캐 4층(40,20,20)은 산출 가능(워밍업 ~80봉 < 가용).",
        "",
        "## C. 추세 slope 계기판 (1d·4d 60MA 병렬)\n",
        "- 3단: 상승 / 평탄 / 하락. **평탄 = |정규화 slope| 가 해당 심볼·TF 히스토리 하위",
        f"  {OBSERVATORY_PARAMS['slope_flat_pctile']*100:.0f}% 이하** (8차 부가기록 정의 재사용).",
        "- 종합 라벨(김박사 규칙, 표시 전용): 1d↑&4d↑=\"강한 추세 후보\" / 1d↑&4d非↑=\"초기 전환 관찰\" /",
        "  1d 평탄=\"횡보 주의\"(8차 관측: 평탄 국면 fwd20 음수 — 툴팁 인용). 1d 하락은 규칙 미정의→중립 관찰.",
        "- 저널: 표시 시점 상태 누적(`validation/observatory_journal.csv`).",
        "",
        "## D. 전조 채널 디스패처 표시 (스펙 §2.5)\n",
        "- 배열 상태: 정배열(10>20>60>120) / 비정배열(120>60) / 기타.",
        "- 전조 슬롯: 정배열→이평선 10MA 쌍봉(candidate 포함) · 비정배열→대파동 스토캐(20,10,10) 쌍봉.",
        "  활성 채널과 이유(배열 상태) 함께 표기. 재사용: array_context·ma10_dt·stoch_dt·scan_ma_candidates(신규 검출기 없음).",
        "",
        "## 상수 목록 (노출)\n",
        "```",
        "OBSERVATORY_PARAMS = {",
    ]
    for k, v in OBSERVATORY_PARAMS.items():
        L.append(f"    {k!r}: {v!r},")
    L += [
        "}",
        "```",
        "",
        "## 현재 시점 BTC·ETH 계기판 스냅샷\n",
        "> UI 렌더 텍스트(build_* 순수 함수 산출 — 실제 화면 캡션과 동일). 스냅샷 시각 = 각 심볼 1d 최신봉.",
        "",
    ]
    for s in snaps:
        sp0, sp1 = s["span"]
        L.append(f"### {s['symbol']}  (1d {sp0:%Y-%m-%d}~{sp1:%Y-%m-%d})" if sp0 is not None else f"### {s['symbol']}")
        L.append("")
        L.append("**C. slope 계기판**")
        L.append("```")
        L += s["slope_lines"]
        L.append("```")
        L.append("**B. 월봉 대파동 위치**")
        L.append("```")
        L += s["m_lines"]
        L.append("```")
        L.append("**D. 전조 채널 슬롯 (TF별)**")
        L.append("```")
        for tf in PRECURSOR_TFS:
            pc = s["precursors"].get(tf)
            if pc is None:
                L.append(f"전조 슬롯 ({tf}) — 데이터 없음")
                continue
            L += build_precursor_lines(tf, pc)
            L.append("")
        L.append("```")
        L.append("")

    L += [
        "## 미결 · 캐비엇\n",
        "- **스크린샷**: 본 리포트는 UI 렌더 텍스트(캡션 원문)로 화면 구성을 대체했다. 실제 streamlit",
        "  화면 캡처는 앱 구동 필요(별도). 패널 3종은 `display/observatory.py` 렌더러로 카드 컨테이너에 표시.",
        "- **스토캐 candidate 부재**: 비정배열 채널(대파동 스토캐 쌍봉)은 candidate 스캐너가 없어 확정만",
        "  표시(스펙 D의 'candidate 포함'은 MA 채널만 충족). 스토캐 candidate 스캐너는 별도 위임 대상.",
        "- **월봉 표본 희소**: 통계·승격 금지 규율 유지. 대파동 위치는 눈대중 대체 수치 표시 용도만.",
        "- **평탄 정의 이원화**: C 계기판의 '평탄'(|slope| 하위20% 분위)은 기법0 상태기계의 slope 부호",
        "  (순수 부호, PHASE7)와 다른 표시용 정의다(8차 재사용). 혼동 방지 위해 계기판 한정 사용.",
        "- **1d 하락 종합 라벨**: 김박사 규칙 미정의 → 중립 '하락 국면(관찰)'로 표기(추천 아님).",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    snaps = [snapshot(s) for s in SYMBOLS]
    write_report(snaps)
    for s in snaps:
        print(f"{s['symbol']}: 1d={s['s1d']['state'] if s['s1d'] else None} "
              f"4d={s['s4d']['state'] if s['s4d'] else None} 종합={s['comp']['label']} | "
              f"월봉 {s['m_bars']}봉 pos={s['m_pos']} | "
              f"전조 " + ", ".join(f"{tf}:{(s['precursors'][tf] or {}).get('state')}→{(s['precursors'][tf] or {}).get('channel')}" for tf in PRECURSOR_TFS))
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
