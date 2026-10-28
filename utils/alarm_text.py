"""화면·구형 외부 알림이 공유하는 신호 문구. 렌더링·발송 없음."""
from analysis.alarm_signals import AlarmSignal, DIR_BULL, SEV_CONFIRMED


def signal_icon(signal: AlarmSignal) -> str:
    """방향·확정 여부를 한 글자로. 확정은 채운 표식, 후보는 빈 표식."""
    if signal.severity == SEV_CONFIRMED:
        return "🔵" if signal.direction == DIR_BULL else "🔴"
    return "🔹" if signal.direction == DIR_BULL else "🔸"


def format_signal_line(signal: AlarmSignal) -> str:
    """신호 한 줄 — "🔵 스토캐 쌍바닥 · 대(20,10,10) · %K 18.4 · HL" 형태.

    MACD 는 가격 스케일이라 소수 한 자리로 뭉개지므로 유효숫자 4자리로 적는다
    ("🔵 MACD 골든크로스 · MACD · hist 12.34 · MACD -56.7").
    """
    parts = [f"{signal_icon(signal)} {signal.label}", signal.layer_name]
    if signal.value is not None:
        metric = signal.metric_name
        value = f"{signal.value:.4g}" if signal.layer_name == "MACD" else f"{signal.value:.1f}"
        parts.append(f"{metric} {value}")
    if signal.detail:
        parts.append(signal.detail)
    if signal.severity != SEV_CONFIRMED:
        parts.append("미확정(이탈 확정 전)")
    return " · ".join(parts)
