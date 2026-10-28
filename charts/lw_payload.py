"""프레임·신호를 차트 데이터로 직렬화. 마커 억제 로직 없음."""
from __future__ import annotations
import os
from typing import Optional
import pandas as pd
from analysis.alarm_signals import macd_event_positions
from charts.theme import (
    COLOR_BEAR, COLOR_BULL, MACD_EVENT_STYLE as _MACD_EVENT_STYLE,
    MACD_HIST_COLORS, RECENT_WINDOW, STOCH_GUIDES, TV_BACKGROUND, TV_GRID, TV_TEXT, ZONE_FILL_COLORS,
)
from utils.time_display import KST_LABEL, to_kst
from config.settings import MA_COLORS, MA_LINE_WIDTHS, RSI_PARAMS, STOCH_BAND, STOCH_GAP, STOCH_LAYERS, STOCH_MAX_Y

from charts.lw_config import *
from charts.lw_config import _LW_SHAPE, _LW_POSITION

def lw_line_width(width: float) -> int:
    """Plotly 선 굵기(실수 px) → LW lineWidth(정수 1~4). 1.0/1.2/1.4 → 1, 1.6/1.8 → 2."""
    return max(1, min(4, int(round(float(width)))))


def ma_styles() -> dict:
    """이평 토큰 승계: config.MA_COLORS · MA_LINE_WIDTHS, 40·80 점선."""
    return {
        str(period): {
            "color": color,
            "width": lw_line_width(MA_LINE_WIDTHS.get(period, 1.0)),
            "style": LW_LINE_STYLE_DASHED if period in DASHED_MA_PERIODS else LW_LINE_STYLE_SOLID,
        }
        for period, color in MA_COLORS.items()
    }


def macd_hist_color(cur, prev) -> str:
    """MACD 히스토그램 4색 (charts/theme.MACD_HIST_COLORS): 부호가 1차, 직전 봉 대비 증감이 2차.

    hist ≥ 0 & hist > prev → 진한 적 / hist ≥ 0 & hist ≤ prev → 옅은 적 /
    hist < 0 & hist < prev → 진한 청 / hist < 0 & hist ≥ prev → 옅은 청. 첫 봉(prev 결측)은 부호의 진한 색.
    표시 계층 내부 계산 — df 에 컬럼을 쓰지 않는다. (Plotly 경로의 규칙과는 다르다: 그쪽은 이번 범위 밖.)
    """
    cur = float(cur)
    if cur >= 0:
        if pd.isna(prev) or cur > float(prev):
            return MACD_HIST_COLORS["pos_rising"]
        return MACD_HIST_COLORS["pos_falling"]
    if pd.isna(prev) or cur < float(prev):
        return MACD_HIST_COLORS["neg_falling"]
    return MACD_HIST_COLORS["neg_rising"]


def _unix_seconds(ts: pd.Timestamp) -> int:
    """naive 인덱스는 UTC 로 간주한다(변환 없음). 데이터 계층 규약 그대로."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return int(ts.timestamp())


def _display_seconds(ts: pd.Timestamp) -> int:
    """LW 에 넘길 time — **표시용 KST 시프트**. LW 는 시간대 개념 없이 epoch 를 UTC 벽시계로 그리므로,
    naive UTC 인덱스에 +9h 를 더한 값을 epoch 로 넘기면 축·툴팁이 KST 벽시계로 읽힌다(LW 공식 권장 방식).
    시간축 자체(눈금 단계·밀도)는 옮기지 않는다. 프레임 인덱스는 건드리지 않는다."""
    return _unix_seconds(to_kst(ts))


def _line_points(times: list[int], series: pd.Series) -> list[dict]:
    return [{"time": t, "value": float(v)} for t, v in zip(times, series) if pd.notna(v)]


def _normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    frame = df.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame, [_display_seconds(ts) for ts in frame.index]   # 표시 시프트는 여기 1회


def stoch_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    """스토캐 3중 — 한 pane 에 오프셋 배치(shifted 컬럼 그대로), 층당 20/80 참조선, 분리선 2."""
    layers = []
    for layer in STOCH_LAYERS:
        label, offset = layer["label"], float(layer["offset"])
        k_col, d_col = f"stoch_k_shifted_{label}", f"stoch_d_shifted_{label}"
        if k_col not in frame.columns or d_col not in frame.columns:
            continue
        k, d = _line_points(times, frame[k_col]), _line_points(times, frame[d_col])
        if not k:
            continue
        layers.append({
            "label": label, "offset": offset, "k": k, "d": d,
            "k_color": layer["k_color"], "d_color": layer["d_color"],
            "guides": [float(g + offset) for g in STOCH_GUIDES],
        })
    if not layers:
        return None
    return {
        "layers": layers,
        "separators": [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5],
        "max_y": float(STOCH_MAX_Y),
    }


def macd_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    if not {"macd", "macd_signal", "macd_hist"}.issubset(frame.columns):
        return None
    prev = frame["macd_hist_prev"] if "macd_hist_prev" in frame.columns else frame["macd_hist"].shift(1)
    hist = [
        {"time": t, "value": float(c), "color": macd_hist_color(float(c), p)}
        for t, c, p in zip(times, frame["macd_hist"], prev) if pd.notna(c)
    ]
    macd, signal = _line_points(times, frame["macd"]), _line_points(times, frame["macd_signal"])
    if not macd:
        return None
    return {"hist": hist, "macd": macd, "signal": signal}


def rsi_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    if "rsi" not in frame.columns:
        return None
    line = _line_points(times, frame["rsi"])
    if not line:
        return None
    guides = [{"value": float(RSI_PARAMS[key]), "color": color, "style": style}
              for key, color, style in RSI_GUIDE_STYLE]
    return {"line": line, "guides": guides}


def _marker(t: int, style: tuple) -> dict:
    text, shape, color, position = style
    return {"time": t, "position": position, "shape": shape, "color": color, "text": text}


def _column_markers(frame: pd.DataFrame, times: list[int], col: str, style: tuple) -> list[dict]:
    if col not in frame.columns:
        return []
    return [_marker(t, style) for t, v in zip(times, frame[col]) if pd.notna(v)]


def markers_payload(frame: pd.DataFrame, times: list[int]) -> dict:
    """알람 마커 — 시리즈별(스토캐 층별 K · RSI · MACD) 시간 오름차순 목록.

    - 스토캐 DB/DT/TB/TT: ``stoch_{kind}_{label}`` non-null 봉 (plotly 와 동일 컬럼).
    - RSI DB/DT: ``rsi_db`` / ``rsi_dt`` (plotly 는 스토캐 DB/DT 마커 함수를 재사용 → 같은 스타일).
    - MACD GC/DC/0↑/0↓: ``analysis.alarm_signals.macd_event_positions`` 의 확정 봉 (알람과 동일).
    """
    time_of = dict(zip(pd.to_datetime(frame.index), times))
    stoch: dict = {}
    for layer in STOCH_LAYERS:
        label = layer["label"]
        out: list[dict] = []
        for kind, style in STOCH_MARKER_STYLE.items():
            out += _column_markers(frame, times, f"stoch_{kind}_{label}", style)
        out.sort(key=lambda m: m["time"])
        if out:
            stoch[label] = out
    rsi = (_column_markers(frame, times, "rsi_db", STOCH_MARKER_STYLE["db"])
           + _column_markers(frame, times, "rsi_dt", STOCH_MARKER_STYLE["dt"]))
    rsi.sort(key=lambda m: m["time"])
    macd: list[dict] = []
    if "macd" in frame.columns:
        for kind, positions in macd_event_positions(frame).items():
            text, symbol, color, text_position = _MACD_EVENT_STYLE[kind]
            style = (text, _LW_SHAPE[symbol], color, _LW_POSITION[text_position])
            macd += [_marker(time_of[ts], style) for ts in positions if ts in time_of]
        macd.sort(key=lambda m: m["time"])
    return {"stoch": stoch, "rsi": rsi, "macd": macd}


def frame_to_lw_payload(df: pd.DataFrame) -> dict:
    """데이터프레임 → LW setData 용 JSON 직렬화 가능 dict.

    - 시간 오름차순 정렬, 중복 시각은 마지막 행만(LW 는 단조 증가 시각을 요구).
    - NaN 은 시리즈별로 그 점만 뺀다(캔들은 OHLC 중 하나라도 NaN 이면 제외).
    - 거래량 색은 종가≥시가 적 / 그 외 청 (plotly_builder.add_volume_panel 과 동일 규칙).
    - 하위 패널(stoch/macd/rsi)은 컬럼이 없으면 None — pane 을 만들지 않는다.
    """
    empty = {"candles": [], "volume": [], "mas": {}, "stoch": None, "macd": None, "rsi": None,
             "markers": {"stoch": {}, "rsi": [], "macd": []}, "zones": zone_thresholds()}
    required = {"open", "high", "low", "close"}
    if df is None or df.empty or not required.issubset(df.columns):
        return empty

    frame, times = _normalize(df)
    candles, volume = [], []
    ohlc_ok = frame[["open", "high", "low", "close"]].notna().all(axis=1).to_numpy()
    has_volume = "volume" in frame.columns
    for i, (t, row) in enumerate(zip(times, frame.itertuples(index=False))):
        if not ohlc_ok[i]:
            continue
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        if has_volume and pd.notna(row.volume):
            volume.append({"time": t, "value": float(row.volume),
                           "color": COLOR_BULL if c >= o else COLOR_BEAR})

    mas: dict = {}
    for period in MA_COLORS:
        col = f"MA{period}"
        if col in frame.columns:
            pts = _line_points(times, frame[col])
            if pts:
                mas[str(period)] = pts
    return {
        "candles": candles, "volume": volume, "mas": mas,
        "stoch": stoch_payload(frame, times),
        "macd": macd_payload(frame, times),
        "rsi": rsi_payload(frame, times),
        "markers": markers_payload(frame, times),
        # 영역 음영 임계값 — plotly 와 동일: 스토캐 20/80(층별 오프셋은 layers[].guides), RSI oversold/overbought
        "zones": zone_thresholds(),
    }


def zone_thresholds() -> dict:
    """과매수·과매도 임계값(표시 계층). 스토캐는 STOCH_GUIDES(20/80), RSI 는 RSI_PARAMS 의 oversold/overbought."""
    return {
        "stoch": {"low": float(STOCH_GUIDES[0]), "high": float(STOCH_GUIDES[1])},
        "rsi": {"low": float(RSI_PARAMS["oversold"]), "high": float(RSI_PARAMS["overbought"])},
    }


def structure_markers_payload(markers: Optional[list[dict]]) -> list[dict]:
    """가격 pane 마커 직렬화 — ts(naive UTC) 를 표시 시프트(_display_seconds)한 time 으로. 시간순 정렬(LW 요구)."""
    if not markers:
        return []
    out = []
    for m in markers:
        out.append({"time": _display_seconds(pd.Timestamp(m["ts"])), "position": m.get("position", "aboveBar"),
                    "color": m.get("color", TV_TEXT), "shape": m.get("shape", "circle"), "text": m.get("text", "")})
    return sorted(out, key=lambda x: x["time"])
