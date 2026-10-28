"""LW 표시 상수·외부 라이브러리 위치. 공유 토큰은 theme/settings에서 참조한다."""
import os
from charts.theme import MACD_EVENT_STYLE as _MACD_EVENT_STYLE

VENDOR_VERSION = "5.2.1"

VENDOR_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vendor", "lightweight-charts.standalone.js",
)

VENDOR_HEADER_MARK = f"Lightweight Charts™ v{VENDOR_VERSION}"   # 원본 라이선스 헤더의 버전 문구

STRUCT_LOW_LABEL = "직전 확정 패턴 저점"

STRUCT_LINE_LABEL = "패턴 저점 기준선 (검증 중)"

STRUCT_LINE_MISSING = "기준선 없음"

STRUCT_LOW_COLOR = "#8D6E63"

STRUCT_LINE_COLOR = "#EF5350"

DASHED_MA_PERIODS = {40, 80}          # plotly_builder 와 동일: 40·80 은 점선 보조선

VOLUME_SCALE_TOP_MARGIN = 0.80        # 거래량은 가격 pane 하단 20% 오버레이

PRICE_SCALE_BOTTOM_MARGIN = 0.22      # 캔들이 거래량 띠와 겹치지 않게

LW_LINE_STYLE_SOLID = 0

LW_LINE_STYLE_DOTTED = 1

LW_LINE_STYLE_DASHED = 2

PANE_KINDS = ("price", "stoch", "macd", "rsi")

PANE_STRETCH = {"price": 39, "stoch": 26, "macd": 19, "rsi": 16}

PANE_LABELS = {"price": "가격", "stoch": "스토캐", "macd": "MACD", "rsi": "RSI"}

SOLO_ALL = "all"

SOLO_COLLAPSED_PX = 14

SOLO_STRIP_FONT_PX = 10

SOLO_STRIP_BG = "#F0F3FA"   # 불투명 — 접힌 띠에는 pane 이름만 보인다

LW_OVERLAY_Z = 60

OHLC_OVERLAY_OFFSET_PX = 24   # 실측: 캡션 높이 22.5px(top 6 → bottom 28.5) → 30px 에서 시작

PANE_SEPARATOR_COLOR = "#E0E3EB"

PANE_SEPARATOR_HOVER_COLOR = "rgba(178, 181, 189, 0.35)"

STOCH_GUIDE_COLOR = "rgba(120,120,120,0.9)"

STOCH_SEPARATOR_COLOR = "rgba(80,80,80,0.7)"

MACD_LINE_COLOR = "#FF3344"

MACD_SIGNAL_COLOR = "#2F6BFF"

RSI_LINE_COLOR = "#000000"

RSI_GUIDE_STYLE = (   # (값 키, 색, 선 스타일) — plotly add_rsi_panel 의 ob/os/mid 구성
    ("overbought", "rgba(255,165,0,0.5)", LW_LINE_STYLE_DASHED),
    ("oversold", "rgba(0,255,255,0.5)", LW_LINE_STYLE_DASHED),
    ("midline", "rgba(0,128,0,0.8)", LW_LINE_STYLE_DOTTED),
)

STOCH_MARKER_STYLE = {   # kind → (text, shape, color, position)
    "db": ("DB", "circle", "#0B8F45", "aboveBar"),
    "dt": ("DT", "circle", "#C62828", "belowBar"),
    "tb": ("TB", "square", "#1565C0", "aboveBar"),
    "tt": ("TT", "square", "#AD1457", "belowBar"),
}

_LW_SHAPE = {"circle": "circle", "diamond": "square", "square": "square"}

STRUCTURE_MARKER_SHAPE = {"HH": "arrowUp", "HL": "arrowUp", "LH": "square", "LL": "square", "EQ": "circle"}

TURN_MARKER_SHAPE = "circle"

STRUCTURE_LEGEND_CAPTION = "▲ HH·HL 유지 ■ LH 경고 ■ LL 훼손"

_LW_POSITION = {"top center": "aboveBar", "bottom center": "belowBar"}
