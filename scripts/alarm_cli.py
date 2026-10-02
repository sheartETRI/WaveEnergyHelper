#!/usr/bin/env python
"""알람 탭 '전체 복사용 텍스트' CLI — Streamlit 서버 없이 명령 한 줄로 출력 (표시 전용).

main.py 를 streamlit.testing.v1.AppTest 로 실행하고, 알람 탭 맨 아래 접힌 상자 '전체 복사용 텍스트'의 st.code 블록
텍스트(display/alarm_copy_text — 41d22a0·2d566f5)를 꺼내 그대로 출력한다. 재계산·재포맷 없음 — 화면 텍스트와 같다.
데이터는 앱과 같은 실제 전송·같은 저장소(data/ohlcv_store.resolve_store_dir()). 판정·푸시·파라미터 무접촉.

    python scripts/alarm_cli.py                                      # 앱 기본 심볼·TF
    python scripts/alarm_cli.py --tf 2h
    python3 scripts/alarm_cli.py --tf 1h,2h,4h --out /tmp/alarm.md
    python scripts/alarm_cli.py --sections "TF 레이더,기준 TF 레이더"

  · 출력       화면 블록 원문(st.code 는 끝 줄바꿈을 떼고 보인다) + 끝 줄바꿈 하나. stdout 에는 이 텍스트만 — 앱 실행 중
               무엇이 print 되든 stderr 로 돌리고, 앱 예외는 CLI 가 at.exception 으로 stderr 에 한 번만 낸다.
  · 여러 TF    같은 AppTest 에서 사이드바 TF 위젯 값만 바꿔 다시 실행한다. TF 레이더·기준 TF 레이더는 TF 마다 같으므로
               첫 TF 에서만 싣는다. TF 사이는 빈 줄 하나.
  · --sections '## ' 섹션 제목의 앞부분(쉼표로 여러 개)과 맞는 섹션만 남긴다 — 문서 제목(# 줄)은 남는다. 맞는 섹션이
               없는 앞부분이 있으면 섹션 제목 목록을 stderr 로 내고 종료 코드 2.
  · 인코딩     콘솔이면 그대로, 리다이렉트·파이프면 stdout·stderr 를 UTF-8 로 (cp949 에서 🔔📌⚪ 인코딩 오류 방지).
               PowerShell 5.1 의 > 는 받은 바이트를 콘솔 코드페이지로 다시 읽으므로 그때는 --out 을 쓴다.
  · 종료 코드  0 성공 · 1 실행 중 예외(at.exception — stderr 로)·시간 초과·복사용 텍스트 없음·저장 실패 · 2 인자 오류
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
from typing import List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit.logger  # noqa: E402
from streamlit import config as st_config  # noqa: E402

# streamlit 자체 콘솔 출력 끄기 — 런타임 없이 앱 모듈을 임포트할 때의 경고(cache_data·ScriptRunContext)·지원 중단 안내,
# stdout 으로 나가는 rich 트레이스백. 설정을 읽을 때 로거가 설정값으로 돌아가므로 설정값 자체를 바꾸고(set_option 이 설정을
# 먼저 읽는다) 바로 반영한다 — 앱 모듈 임포트보다 앞. 앱 예외는 CLI 가 at.exception 으로 stderr 에 한 번만 낸다.
st_config.set_option("logger.level", "critical")
st_config.set_option("logger.enableRich", False)
streamlit.logger.set_log_level("critical")

from streamlit.testing.v1 import AppTest  # noqa: E402

import display.alarm_copy_text as CT  # noqa: E402
import display.tf_radar_panel as RD  # noqa: E402
import display.wave_basis_radar as BR  # noqa: E402
import main as app  # noqa: E402  — 사이드바 위젯 key·선택지·기본 TF 만 읽는다 (main() 은 AppTest 가 실행)

MAIN_PATH = os.path.join(ROOT, "main.py")
DEFAULT_TIMEOUT_SEC = 120.0
NL = "\n"
# TF 마다 같은 섹션 — 여러 TF 를 출력할 때는 첫 TF 에서만 싣는다.
RADAR_HEADINGS = (f"## {RD.SECTION_TITLE} · ", f"## {BR.SECTION_TITLE} · ")


class CliError(Exception):
    """종료 코드 1 — 메시지는 stderr 로."""


def _utf8_if_redirected(stream) -> None:
    """콘솔이면 그대로, 리다이렉트·파이프면 UTF-8 로 — cp949 에서 🔔📌⚪ 때문에 UnicodeEncodeError 가 나지 않게."""
    try:
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):   # reconfigure 가 없는 대체 스트림은 그대로 둔다
        pass


def _note(message: str) -> None:
    """진행 표시 — 콘솔에서만 (리다이렉트·로그에는 남기지 않는다)."""
    if getattr(sys.stderr, "isatty", lambda: False)():
        print(f"alarm_cli: {message}", file=sys.stderr, flush=True)


# ── AppTest 실행 ─────────────────────────────────────────────────────────────
def _screen_text(at: AppTest, label: str, symbol: Optional[str], tf: Optional[str]) -> str:
    """방금 실행의 복사용 텍스트 원문. 실행 중 예외·블록 없음·위젯 값 미적용은 CliError."""
    if at.exception:
        details = [NL.join([exc.value] + [line.rstrip() for line in exc.stack_trace]) for exc in at.exception]
        raise CliError(f"{label}: 실행 중 예외 {len(details)}건{NL}" + (NL + NL).join(details))
    boxes = [box for box in at.expander if box.label == CT.EXPANDER_LABEL]
    if len(boxes) != 1 or len(boxes[0].code) != 1:
        shown = " / ".join(err.value for err in at.error)
        raise CliError(f"{label}: 알람 탭 '{CT.EXPANDER_LABEL}' 블록을 찾지 못함" + (f" — 화면 오류: {shown}" if shown else ""))
    on_symbol = at.selectbox(key=app.SYMBOL_KEY).value
    on_tf = at.selectbox(key=app.INTERVAL_KEY).value
    if (symbol and on_symbol != symbol) or (tf and on_tf != tf):
        raise CliError(f"{label}: 사이드바 위젯 값이 적용되지 않음 (화면 {on_symbol} {on_tf})")
    text = boxes[0].code[0].value
    title = "# " + CT.DOC_TITLE.format(symbol=on_symbol, interval=on_tf)
    if text.split(NL, 1)[0] != title:
        raise CliError(f"{label}: 복사용 텍스트 제목이 위젯 값과 다름 ({text.split(NL, 1)[0]!r})")
    return text


def collect_texts(symbol: Optional[str], tfs: Sequence[str], timeout: float = DEFAULT_TIMEOUT_SEC) -> List[str]:
    """main.py 를 AppTest 로 실행해 TF 별 복사용 텍스트 원문을 모은다 (실제 전송·앱과 같은 저장소).

    첫 실행 전에는 위젯이 없으므로 같은 key 의 세션 상태로 심볼·TF 를 넣는다(사이드바에서 고른 것과 같다 — 기본값
    실행 한 번을 아낀다). 둘째 TF 부터는 같은 AppTest 에서 TF 위젯 값만 바꿔 다시 실행한다.
    """
    at = AppTest.from_file(MAIN_PATH, default_timeout=timeout)
    if symbol:
        at.session_state[app.SYMBOL_KEY] = symbol
    if tfs:
        at.session_state[app.INTERVAL_KEY] = tfs[0]
    texts = []
    for i, tf in enumerate(list(tfs) or [None]):
        label = f"{symbol or '기본 심볼'} {tf or '기본 TF'}"
        _note(f"{label} 실행 중…")
        if i:
            at.selectbox(key=app.INTERVAL_KEY).set_value(tf)
        try:
            with contextlib.redirect_stdout(sys.stderr):   # stdout 에는 복사용 텍스트만
                at.run()
        except Exception as exc:  # noqa: BLE001 — 시간 초과 등 AppTest 자체 실패
            raise CliError(f"{label}: AppTest 실행 실패 — {type(exc).__name__}: {exc}") from exc
        texts.append(_screen_text(at, label, symbol, tf))
    return texts


# ── 출력 조립 (원문 자르기만 — 재포맷 없음) ─────────────────────────────────────
def split_sections(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """'## ' 제목 줄 기준 분할 → (머리말, [(제목 줄, 섹션 원문)]). 다시 이어 붙이면 원문과 같다(### 소제목은 섹션 안)."""
    lines = [part + NL for part in text.split(NL)]
    lines[-1] = lines[-1][:-1]                   # 마지막 조각에는 줄바꿈이 없었다
    head: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    for line in lines:
        if line.startswith("## "):
            sections.append((line.rstrip(NL), [line]))
        elif sections:
            sections[-1][1].append(line)
        else:
            head.append(line)
    return "".join(head), [(title, "".join(body)) for title, body in sections]


def compose(texts: Sequence[str], prefixes: Optional[Sequence[str]] = None) -> Tuple[str, List[str]]:
    """TF 별 원문 → (출력 텍스트, 맞는 섹션이 없던 --sections 앞부분).

    레이더 2종은 첫 TF 에서만 싣고, prefixes 가 있으면 제목(## 뒤)이 그 앞부분으로 시작하는 섹션만 남긴다. 아무것도
    빼지 않은 TF 는 원문 그대로, 뺀 TF 는 남은 섹션 원문을 이어 붙인 것. 섹션이 하나도 안 남은 TF 는 문서 제목까지
    뺀다. 블록 끝 줄바꿈은 떼고(화면과 같게) 블록 사이 빈 줄 하나, 맨 끝 줄바꿈 하나.
    """
    blocks: List[str] = []
    matched = set()
    for i, text in enumerate(texts):
        head, sections = split_sections(text)
        kept = []
        for title, body in sections:
            if i and title.startswith(RADAR_HEADINGS):
                continue
            if prefixes is not None:
                hits = [p for p in prefixes if title[3:].casefold().startswith(p.casefold())]
                if not hits:
                    continue
                matched.update(hits)
            kept.append(body)
        if len(kept) == len(sections):
            blocks.append(text.rstrip(NL))
        elif kept:
            blocks.append((head + "".join(kept)).rstrip(NL))
    output = (NL + NL).join(blocks) + NL if blocks else ""
    return output, [p for p in (prefixes or []) if p not in matched]


# ── 진입점 ───────────────────────────────────────────────────────────────────
def _csv(text: Optional[str]) -> List[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="알람 탭 '전체 복사용 텍스트'를 Streamlit 서버 없이 출력 (main.py 를 AppTest 로 실행 — 표시 전용)")
    p.add_argument("--symbol", help=f"심볼 (기본: 앱 기본값 {app.SUPPORTED_SYMBOLS[0]})")
    p.add_argument("--tf", help=f"TF — 쉼표로 여러 개 (예: 1h,2h,4h · 기본: 앱 기본 TF {app.DEFAULT_INTERVAL})")
    p.add_argument("--sections", help="'## ' 섹션 제목의 앞부분 — 쉼표로 여러 개 (예: 'TF 레이더,기준 TF 레이더')")
    p.add_argument("--out", metavar="PATH", help="UTF-8 파일로 저장 (stdout 에는 쓰지 않는다)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SEC, metavar="SEC",
                   help=f"AppTest 실행 1회 제한 (기본 {DEFAULT_TIMEOUT_SEC:.0f}초)")
    args = p.parse_args(argv)
    if args.symbol is not None:
        args.symbol = args.symbol.strip().upper()
        if args.symbol not in app.SUPPORTED_SYMBOLS:
            p.error(f"--symbol {args.symbol}: 앱 심볼 목록에 없음 {list(app.SUPPORTED_SYMBOLS)}")
    args.tfs = list(dict.fromkeys(_csv(args.tf)))          # 순서 유지·중복 제거
    if args.tf is not None and not args.tfs:
        p.error("--tf 가 비었습니다")
    unknown = [tf for tf in args.tfs if tf not in app.TIMEFRAMES]
    if unknown:
        p.error(f"--tf {','.join(unknown)}: 앱 TF 목록에 없음 {list(app.TIMEFRAMES)}")
    args.prefixes = _csv(args.sections) if args.sections is not None else None
    if args.sections is not None and not args.prefixes:
        p.error("--sections 가 비었습니다")
    if args.timeout <= 0:
        p.error("--timeout 은 0 보다 커야 합니다")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_if_redirected(sys.stdout)
    _utf8_if_redirected(sys.stderr)
    args = parse_args(argv)
    try:
        texts = collect_texts(args.symbol, args.tfs, args.timeout)
    except CliError as exc:
        print(exc, file=sys.stderr)
        return 1
    output, unmatched = compose(texts, args.prefixes)
    if unmatched:
        titles = dict.fromkeys(title[3:] for text in texts for title, _ in split_sections(text)[1])
        print(f"--sections: 맞는 섹션 없음 — {', '.join(unmatched)}", file=sys.stderr)
        print("섹션 제목: " + " / ".join(titles), file=sys.stderr)
        return 2
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(output)
        except OSError as exc:
            print(f"--out {args.out}: 저장 실패 ({exc})", file=sys.stderr)
            return 1
        print(f"저장: {args.out} ({len(texts)}개 TF)", file=sys.stderr)
        return 0
    sys.stdout.write(output)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
