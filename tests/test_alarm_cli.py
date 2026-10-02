"""scripts/alarm_cli.py — 알람 탭 '전체 복사용 텍스트' CLI. main.py 를 AppTest 로 실제 실행한다.

가짜 전송은 이 테스트에만 있다(CLI 코드에는 없음): data/binance.requests.get 을 test_page_render_smoke 의 합성 kline 으로
바꾼다. 저장소는 conftest 가 테스트마다 임시 폴더로 돌리고(WEH_OHLCV_STORE_DIR), 실제 data/cache 에 쓰려 하면 트립와이어가
RuntimeError 를 낸다 — CLI 에서는 실행 중 예외로 잡혀 종료 코드 1.
"""
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pytest.importorskip("streamlit.testing.v1")

import data.binance as B  # noqa: E402
import display.alarm_copy_text as CT  # noqa: E402
import display.alarm_panel as AP  # noqa: E402
import display.ma60_down_tracker as D  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402
import display.tf_radar_panel as RD  # noqa: E402
import display.trend_structure as TS  # noqa: E402
import display.wave_basis_radar as BR  # noqa: E402
from data import ohlcv_store  # noqa: E402
from scripts import alarm_cli as CLI  # noqa: E402
from test_page_render_smoke import _Resp, _synthetic_klines  # noqa: E402


def _headings(symbol, interval, radars=True):
    """화면 순서의 '## ' 섹션 제목 — 레이더 2종(심볼 단위) + 알람·상방 추적·하방 추적·추세 구조."""
    radar = [f"## {RD.SECTION_TITLE} · {symbol}", f"## {BR.SECTION_TITLE} · {symbol}"] if radars else []
    return radar + [f"## {AP.build_header(symbol, interval)}", f"## {T.SECTION_TITLE} · {symbol} {interval}",
                    f"## {D.SECTION_TITLE} · {symbol} {interval}", f"## {TS.SECTION_TITLE} · {symbol} {interval}"]


def _section_lines(text):
    return [line for line in text.split("\n") if line.startswith("## ")]


def _real_cache_state():
    real = ohlcv_store.REAL_STORE_DIR
    if not os.path.isdir(real):
        return None
    return {name: os.stat(os.path.join(real, name)).st_mtime_ns for name in sorted(os.listdir(real))}


@pytest.fixture
def fake_binance(monkeypatch):
    """가짜 전송 — 테스트에서만. 모든 심볼·TF 에 같은 합성 시계열(마지막 봉이 '지금')."""
    def fake_get(url, params=None, timeout=None, **kw):
        params = params or {}
        return _Resp(_synthetic_klines(params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)))

    monkeypatch.setattr(B.requests, "get", fake_get)
    B.reset_data_url()
    yield
    B.reset_data_url()


@pytest.fixture
def raw_texts(monkeypatch):
    """CLI 가 AppTest 에서 꺼낸 원문을 옆에 기록 — 출력이 화면 원문 그대로인지 대조용."""
    seen = []
    original = CLI.collect_texts

    def spy(*args, **kwargs):
        texts = original(*args, **kwargs)
        seen.append(list(texts))
        return texts

    monkeypatch.setattr(CLI, "collect_texts", spy)
    return seen


# ── AppTest 로 main.py 실행 ──────────────────────────────────────────────────
def test_single_tf_prints_screen_text_verbatim(fake_binance, raw_texts, capsys):
    assert CLI.main(["--symbol", "ethusdt", "--tf", "4h"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# 알람 탭 · ETHUSDT 4h\n")
    assert _section_lines(out) == _headings("ETHUSDT", "4h")          # 레이더 2종 + 알람 섹션 전부, 화면 순서
    assert out == raw_texts[0][0] + "\n"                               # 화면 st.code 블록 원문 그대로 + 끝 줄바꿈 (재포맷 없음)


def test_multiple_tfs_print_radars_once_and_out_writes_utf8_file(fake_binance, raw_texts, capsys, tmp_path):
    path = tmp_path / "alarm.md"
    assert CLI.main(["--tf", "1h,2h", "--out", str(path)]) == 0
    out, err = capsys.readouterr()
    assert out == "" and f"저장: {path}" in err                        # --out 이면 stdout 에 쓰지 않는다
    text = path.read_text(encoding="utf-8")
    assert _section_lines(text) == _headings("BTCUSDT", "1h") + _headings("BTCUSDT", "2h", radars=False)
    first, second = raw_texts[0]
    head, sections = CLI.split_sections(second)
    rest = "".join(body for title, body in sections if not title.startswith(CLI.RADAR_HEADINGS))
    assert text == first + "\n\n" + (head + rest).rstrip("\n") + "\n"  # 첫 TF 원문 + 빈 줄 + 둘째 TF 원문에서 레이더만 뺀 것


def test_sections_keeps_only_requested_sections_after_doc_title(fake_binance, capsys):
    assert CLI.main(["--sections", "TF 레이더,기준 TF 레이더"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# 알람 탭 · BTCUSDT 1h\n")                   # 앱 기본 심볼·TF
    assert _section_lines(out) == _headings("BTCUSDT", "1h")[:2]


def test_cli_writes_only_to_isolated_store_never_real_cache(fake_binance, capsys):
    """트립와이어에 걸리지 않는다 — 저장은 conftest 의 임시 폴더로만, 실제 data/cache 는 파일 목록·mtime 그대로."""
    before = _real_cache_state()
    assert CLI.main(["--tf", "2h"]) == 0
    assert _real_cache_state() == before
    stored = set(os.listdir(os.environ[ohlcv_store.STORE_DIR_ENV]))
    assert {"ohlcv_BTCUSDT_2h.csv", "ohlcv_BTCUSDT_1w.csv"} <= stored  # 메인 TF + TF 레이더
    assert "실행 중 예외" not in capsys.readouterr().err


def test_app_exception_goes_to_stderr_with_exit_code_1(fake_binance, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("복사용 텍스트 조립 실패 (테스트)")

    monkeypatch.setattr(CT, "build_copy_text", boom)                   # main.py 가 실행 때 가져가는 함수
    assert CLI.main([]) == 1
    out, err = capsys.readouterr()
    assert out == "" and "실행 중 예외 1건" in err and "복사용 텍스트 조립 실패 (테스트)" in err


# ── 조립·인자·인코딩 (AppTest 없음) ───────────────────────────────────────────
SAMPLE = "\n\n".join([
    "# 알람 탭 · BTCUSDT 1h",
    f"## {RD.SECTION_TITLE} · BTCUSDT", "레이더 표",
    f"## {BR.SECTION_TITLE} · BTCUSDT", "기준 레이더 표",
    f"## {AP.build_header('BTCUSDT', '1h')}", f"### {AP.CURRENT_TITLE}", "- 🔵 스토캐 쌍바닥",
    f"## {TS.SECTION_TITLE} · BTCUSDT 1h", "| a | b |",
])                                                                    # 화면 블록처럼 끝 줄바꿈 없음


def test_split_sections_is_lossless_and_keeps_subheadings_inside():
    head, sections = CLI.split_sections(SAMPLE)
    assert head + "".join(body for _, body in sections) == SAMPLE
    assert [title for title, _ in sections] == _section_lines(SAMPLE)
    assert f"### {AP.CURRENT_TITLE}" in sections[2][1]                # ### 소제목은 섹션 안에 남는다
    assert CLI.compose([SAMPLE]) == (SAMPLE + "\n", [])               # 한 TF·필터 없음 → 원문 그대로 + 끝 줄바꿈


def test_unmatched_section_prefix_lists_titles_with_exit_code_2(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "collect_texts", lambda *a, **k: [SAMPLE])
    assert CLI.main(["--sections", "추세 구조,없는 섹션"]) == 2
    out, err = capsys.readouterr()
    assert out == "" and "맞는 섹션 없음 — 없는 섹션" in err and f"{RD.SECTION_TITLE} · BTCUSDT" in err
    assert CLI.main(["--sections", "추세 구조"]) == 0
    assert _section_lines(capsys.readouterr().out) == [f"## {TS.SECTION_TITLE} · BTCUSDT 1h"]


def test_redirected_stream_is_switched_to_utf8_but_console_is_left_alone():
    with pytest.raises(UnicodeEncodeError):
        io.TextIOWrapper(io.BytesIO(), encoding="cp949").write("🔔")   # 고치지 않으면 cp949 리다이렉트에서 깨진다
    raw = io.BytesIO()
    piped = io.TextIOWrapper(raw, encoding="cp949")
    CLI._utf8_if_redirected(piped)
    piped.write("🔔📌⚪ 알람")
    piped.flush()
    assert raw.getvalue().decode("utf-8") == "🔔📌⚪ 알람"

    class Console(io.TextIOWrapper):
        def isatty(self):
            return True

    console = Console(io.BytesIO(), encoding="cp949")
    CLI._utf8_if_redirected(console)
    assert console.encoding == "cp949"


def test_arguments_are_checked_against_app_choices():
    args = CLI.parse_args(["--symbol", " solusdt ", "--tf", "4h, 1h,4h"])
    assert args.symbol == "SOLUSDT" and args.tfs == ["4h", "1h"] and args.prefixes is None
    for bad in (["--tf", "7h"], ["--symbol", "DOGEUSDT"], ["--tf", " , "], ["--sections", ""]):
        with pytest.raises(SystemExit) as exc:
            CLI.parse_args(bad)
        assert exc.value.code == 2
