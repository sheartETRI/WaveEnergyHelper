"""MTF 역할·시간 계약의 오프라인 기술 감사. 전략 성과를 평가하지 않는다.

시세 수신·주문·기존 결과 수정 없이 합성 입력과 현재 정의만 확인한다.
실행: python validation/mtf_contract_audit.py
기본 출력: artifacts/mtf_research_audit.json
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


def run_audit() -> dict:
    from analysis.campaign_promotion import resolve_promotions
    from analysis.pattern_scanner import PatternEvent
    from analysis.tf_ladder import TF_POOL, assess_tf_data, lower, upper
    from analysis.wave_align_gate_forward import PROMOTED_LTF_TO_HTF
    from analysis.wave_energy import resolve_lower_frame, resolve_upper_frame
    from config.settings import TIMEFRAMES, TF_RADAR_PARAMS
    from data.binance import get_auto_limit
    from data.processor import resample_timeframe
    from display.asof import truncate_to_asof
    from indicators.moving_averages import add_moving_averages

    mapping = [dict(tf=tf, v1_upper=resolve_upper_frame(tf), v1_lower=resolve_lower_frame(tf),
                    v2_upper=upper(tf), v2_lower=lower(tf),
                    display_gate=PROMOTED_LTF_TO_HTF.get(tf)) for tf in TIMEFRAMES]

    # 같은 240시간 창이어도 종가를 추출하는 간격에 따라 평균은 다르다.
    # 각 일의 23개 종가는 200, 마지막 1개 종가는 100인 합성 경로.
    hourly = np.tile(np.r_[np.full(23, 200.), 100.], 10)
    equivalent_horizons = dict(hours=240, ma_1h_240=float(hourly.mean()),
                               ma_4h_60=float(hourly[3::4].mean()),
                               ma_1d_10=float(hourly[23::24].mean()))
    assert len({equivalent_horizons[k] for k in ("ma_1h_240", "ma_4h_60", "ma_1d_10")}) == 3

    # 현재 후보의 1봉 SMA60 방향을 설명할 수 있는 정확한 관계.
    closes = pd.Series(100.+np.cumsum(np.random.default_rng(42).normal(size=700)),
                       index=pd.date_range("2024-01-01", periods=700, freq="4h"))
    calculated = add_moving_averages(pd.DataFrame({"close": closes}))
    ma60 = pd.to_numeric(calculated["MA60"], errors="coerce").astype(float)
    observed_delta = ma60.diff()
    identity_delta = (closes-closes.shift(60))/60
    valid = observed_delta.notna() & identity_delta.notna()
    max_error = float((observed_delta[valid]-identity_delta[valid]).abs().max())
    assert max_error < 1e-10
    next_reference = float(closes.iloc[-60])  # 마지막 행이 마감봉 t: t+1-60=t-59
    next_cases = []
    for next_close in (next_reference-1., next_reference, next_reference+1.):
        next_ma = float(pd.concat([closes, pd.Series([next_close])], ignore_index=True).tail(60).mean())
        observed = next_ma-float(ma60.iloc[-1])
        expected = (next_close-next_reference)/60
        assert abs(observed-expected) < 1e-10
        next_cases.append(dict(next_close=next_close, actual_delta=observed, formula_delta=expected))
    sma_identity = dict(period=60, difference_bars=1, synthetic_bars=len(closes),
                        max_absolute_error=max_error, next_reference=next_reference,
                        next_cases=next_cases,
                        interpretation="마지막 행이 마감봉 t일 때 다음 봉 방향 조건. 가격 예측·목표가가 아님")

    index = pd.date_range("2024-01-01", periods=1000, freq="D")
    daily = pd.DataFrame({"open": 100.+np.arange(1000), "high": 101.+np.arange(1000),
                          "low": 99.+np.arange(1000), "close": 100.+np.arange(1000),
                          "volume": 1.}, index=index)
    budgets = []
    grids = []
    for tf in ("2d", "4d", "2w"):
        budget = get_auto_limit(tf)
        bars = resample_timeframe(daily.tail(budget), tf)
        sufficiency = asdict(assess_tf_data(len(bars), tf))
        budgets.append(dict(tf=tf, requested_daily_bars=budget, result=sufficiency))
        full = resample_timeframe(daily, tf)
        shifted = resample_timeframe(daily.iloc[1:], tf)
        common = full.index.intersection(shifted.index)
        grids.append(dict(tf=tf, full_first_labels=[str(x) for x in full.index[:3]],
                          shifted_first_labels=[str(x) for x in shifted.index[:3]],
                          common_label_count=len(common)))

    # 현재 helper는 봉 open_time 기준으로 자른다. 이는 HTF close 가용성 증명이 아니다.
    decision_at = pd.Timestamp("2024-01-02 04:00")
    historical_daily = daily.iloc[:2]
    selected = truncate_to_asof(historical_daily, decision_at)
    unavailable = selected.index[selected.index + pd.Timedelta(days=1) > decision_at]
    asof = dict(decision_at=str(decision_at), included_opens=[str(x) for x in selected.index],
                included_but_not_closed=[str(x) for x in unavailable],
                risk_observed=bool(len(unavailable)),
                scope="연구 helper의 시간 계약 예시이며 현재 앱 성과 영향은 평가하지 않음")

    def event(tf, timestamp):
        return PatternEvent(symbol="SYN", tf=tf, kind_pattern="double_bottom", ma_or_layer="MA10",
                            direction="long", confirmed_bar=pd.Timestamp(timestamp),
                            neckline_price=100., kind="HL", source="ma", clean="clean",
                            confirmed_pos=100, price_at_confirm=101., strength=1.)

    base = event("4h", "2024-01-02 12:00")
    future = event("1d", "2024-01-03 00:00")
    promoted = resolve_promotions([base, future])
    base_result = next(row for row in promoted if row.base_tf == "4h")
    suppression = dict(base_confirmed=str(base.confirmed_bar), upper_confirmed=str(future.confirmed_bar),
                       upper_is_future=bool(future.confirmed_bar > base.confirmed_bar),
                       status=base_result.status, suppressed_by=base_result.suppressed_by,
                       risk_observed=base_result.suppressed_by == "1d",
                       scope="전이력 후보 목록을 전달한 연구용 다중TF 예시. 현재 앱과 단일TF 캠페인 손익의 버그 판정이 아님")

    journal_path = ROOT / "validation/wave_live_forward_journal.csv"
    journal = None
    if journal_path.is_file():
        with journal_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        times = [row["timestamp"] for row in rows]
        unique = {(r["symbol"], r["timeframe"], r["timestamp"]) for r in rows}
        journal = dict(path=journal_path.relative_to(ROOT).as_posix(), rows=len(rows),
                       unique_symbol_tf_timestamp=len(unique), first=min(times), last=max(times),
                       sha256=hashlib.sha256(journal_path.read_bytes()).hexdigest())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    metadata = dict(audit_version=2, collected_at_utc=pd.Timestamp.now(tz="UTC").isoformat(),
                    repo_head=commit.stdout.strip() if commit.returncode == 0 else None)
    return dict(metadata=metadata, scope="오프라인 기술 감사 / 성과 백테스트 아님",
                timeframe_sets=dict(display=TIMEFRAMES, radar=TF_RADAR_PARAMS["intervals"], v2_pool=TF_POOL),
                mapping=mapping, equal_horizon_counterexample=equivalent_horizons,
                sma_direction_identity=sma_identity,
                custom_frame_budgets=budgets, resample_window_shift=grids,
                asof_open_vs_close=asof, future_upper_suppression=suppression,
                historical_journal_snapshot=journal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/mtf_research_audit.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.ERROR)
    import streamlit.logger
    streamlit.logger.set_log_level("error")
    with patch("requests.sessions.Session.send", side_effect=AssertionError("오프라인 감사에서는 HTTP를 요청하지 않습니다.")):
        result = run_audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
