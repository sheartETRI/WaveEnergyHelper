# signal-alarm 브랜치 — 스토캐 쌍봉/쌍바닥 정의 교체(폭 비교) + Plotly 분리 보고

작성 2026-09-22. 정의 변경: `indicators/stochastic.py`(쌍바닥/쌍봉 검출기 교체, 이전 정의는 RSI 전용으로 개명),
`config/settings.py`(`STOCH_DOUBLE_PARAMS`), `indicators/oscillators.py`(RSI 는 이전 정의 유지), 알람 문구 2곳.
Plotly 분리: `charts/theme.py`(공통 토큰 단일 공급원), `charts/lw_builder.py`, `charts/plotly_builder.py`(재노출만), `main.py`,
`requirements.txt` / `requirements-legacy.txt`(신설). 테스트: 신설 1파일, 개정 6파일, 골든 재생성 1건.
**적용하려면 실행 중인 Streamlit 재시작 필요**(indicators·config·main·charts 모듈 변경). 커밋 미실행(작업 트리 상태).

> 발단: BTCUSDT 1h 대파동(20,10,10) 화면에서 과매수권 둥근 봉우리 하나에 DT 마커가 찍힘. 이전 검출기의 쌍봉은
> "연속한 두 피봇 고점(50 위 5봉 국소 최대) 사이의 홈(넥라인)을 하향 돌파" 였고, 과매수 조건·홈 깊이·간격 조건이 없어
> 화면 밖의 더 낮은 고점과 묶이거나(HH), 정점대의 1pt 잔홈으로도 쌍봉이 됐다(합성 재현: 홈 1.0pt/폭 6봉이면 확정).

## 1. 정의 (김박사, 2026-09-22)

- **쌍봉**: 과매수권(K ≥ 80)에 들어간 첫 봉우리가 과매수권을 **벗어난 뒤** 두 번째 봉우리를 만들되, 두 번째 봉우리의
  **봉우리 기간이 첫 번째보다 짧아야** 한다. **쌍바닥은 대칭**(K ≤ 20).
- **봉우리 기간 = 정점 전후 대칭 폭**: 정점값에서 `width_drop`(기본 10pt) 만큼 내려온 높이 위(K ≥ 정점 − 10)에 머문
  연속 봉 수. 바닥은 K ≤ 바닥 + 10.
- **두 번째 봉우리는 과매수권 재진입이 필수가 아니다**(80 미달 봉우리도 인정). 다만 두 봉우리 사이의 골이 과매수선
  아래이고 두 봉우리 각각의 폭 구간 밖(골 < 정점2 − 10)까지 내려가야 별개 봉우리로 본다 — 골이 얕으면 봉우리 하나.
- **확정 봉 = 두 번째 봉우리가 과매수권 아래로 이탈하는 봉**. 폭이 그 시점에 정해져야 비교가 되므로 정확히는
  `K < min(80, 정점2 − 10)` 이 처음 성립하는 봉(정점2 ≥ 90 이면 80 이탈 봉과 같고, 80 미달 봉우리면 정점2 − 10 이탈 봉).
  그 봉에서 폭2 < 폭1 이면 확정, 아니면 실패. 실패한 두 번째 봉우리가 과매수권 봉우리였으면 그것이 새 첫 봉우리가
  되고, 아니면 다음 과매수권 진입을 기다린다(세 번째 봉우리를 "두 번째"로 재사용하지 않는다).
- 확정은 이탈 봉의 과거 값만으로 정해진다(피봇 lookback 같은 후행 봉 불필요 — 룩어헤드 없음).

## 2. 구현

- `detect_double_bottom_patterns`(바닥 공간 상태머신 idle→first→second)를 새로 쓰고, 쌍봉은 이전과 같이 `100 − K`
  반전 호출(`detect_double_top_patterns`)로 봉 단위 대칭을 보장. 컬럼 계약 유지: `stoch_db/dt`(확정 봉 K),
  `_candidate`(두 번째 극점 봉, 폭 조건 현재 충족·이탈 전), `neckline`(확정 기준선 = 위 K 임계값), `kind/delta`
  (HL/LL/EQ·LH/HH/EQ), `first_pos`(첫 극점 iloc), `prev_opp`(첫 극점 직전 반대 피봇, 피봇 컬럼 사용).
- 피봇(`compute_stochastic_pivots`, `STOCH_PIVOT_PARAMS`)은 쌍바닥/쌍봉에 더는 쓰이지 않고 쓰리바닥/쓰리봉·prev_opp
  기록에만 남는다. 이전 정의는 `detect_pivot_double_bottom_patterns` / `detect_pivot_double_top_patterns` 로 개명해
  **RSI 쌍바닥/쌍봉(`rsi_db/dt`)이 그대로 사용**(RSI 는 이번 정의의 대상이 아님).
- 파라미터 `STOCH_DOUBLE_PARAMS = {overbought 80, oversold 20, width_drop 10}` — 김박사 조정 대상.
- 적용 범위: **전체 교체** — 차트 마커·알람은 물론 `stoch_db/dt_*` 를 읽는 analysis/validation 모듈(18개)과
  추세 레이어 4층(40,20,20)도 새 정의를 따른다. `validation/wave_ma60_turn_probe.extract_signals` 의
  `known = max(확정봉, 둘째 피봇 + lookback)` 은 이전 정의의 후행성 보정이라 지금은 보수적(늦게 앎)일 뿐 오류는 아님.

## 3. 합성 검증 (tests/test_stoch_double_width.py)

| 파동 | 결과 |
|---|---|
| 과매수권 둥근 봉우리 하나(김박사 화면 사례) | DT 없음 |
| 정점 92·폭 12 → 골 70 → 정점 88·폭 5 | DT 1건, LH, 기준선 78 을 처음 하향 이탈한 봉에 확정, first_pos = 첫 정점 봉 |
| 첫 봉우리 폭 5 → 두 번째 폭 12 | DT 없음(더 넓음) |
| 두 번째 봉우리 정점 74(80 미달)·폭 4 | DT 1건, 기준선 64(=74−10) 이탈 봉에 확정 |
| 골 85(과매수 미이탈) → 정점 90 | DT 없음(봉우리 하나) |
| 위 쌍봉 파동을 100−K 로 뒤집음 | 같은 봉에서 DB, kind HL, 기준선 100−값 |

## 4. Plotly 분리 (같은 날 선행 작업)

- 기본 경로가 LW 로 넘어간 뒤에도 `main.py` 가 `charts.plotly_builder` 를 무조건 import 해 plotly 가 기동 의존이었고,
  "차트 엔진" 라디오·"표시 모드"·"스토캐 표시" 컨트롤은 Plotly 전용(죽은 UI)이었다.
- 공통 토큰(`COLOR_BULL/BEAR`, `TV_*`, `RECENT_WINDOW`, `STOCH_GUIDES`, `CHART_HEIGHT_OPTIONS/DEFAULT_CHART_HEIGHT`,
  `MACD_EVENT_STYLE`)을 `charts/theme.py` 로 옮겨 단일 공급원으로 삼고, `lw_builder` 는 theme 만 import,
  `plotly_builder` 는 같은 이름을 theme 에서 재노출(하위 호환·파일 유지). `main.py` 는 LW 단일 경로.
- `requirements.txt` = requests·pandas·streamlit. `requirements-legacy.txt` = plotly(레거시 빌더·legacy_main),
  mplfinance(plot_btcusdt_ma·validation/g1a_render). `streamlit-lightweight-charts` 는 코드 어디서도 안 써 주석 처리.
- 별도 프로세스에서 plotly·mplfinance import 를 막고 `main` 을 들여오는 테스트 추가(streamlit 은 plotly 가 설치돼
  있으면 스스로 가져오므로 sys.modules 검사로는 판별 불가).

## 5. 테스트

| 범위 | 결과 (VM: Python 3.10, pandas 2.3.3, numpy 2.2.6) |
|---|---|
| 신설 tests/test_stoch_double_width.py | 7 passed |
| 개정 test_stoch_kind(골든 재생성·first_pos 5), test_triple_patterns(공존 파동 바닥1 확장), test_ma60_turn_tracker(상태별 낱말) | passed |
| 개정 test_lw_builder(LW 단일·plotly 미설치 import), test_slim_app_smoke(Plotly 테스트 11건 skip 마커) | 51 passed |
| 전체 tests/ (4묶음) | **718 passed, 3 skipped, 7 failed — 7건 전부 환경**: Binance 차단(fetch 빈 응답) 6건, jinja2 3.0.3(<3.1.2, pandas Styler) 1건 |

골든 `tests/data_golden_stoch.json` 은 새 정의로 재생성(seed 7/11/21/42 × 3층, db/dt 위치·kind 완전 일치 요구).
확정 봉 K 가 db 는 20 초과 / dt 는 80 미만임을 골든 테스트가 함께 단언.

## 6. 한계·비고

- `width_drop = 10` 은 초기값. 슬로우 스토캐(20,10,10)에서 정점대 폭을 재는 높이로 적절한지는 실측으로 조정 필요.
- 이 VM 에서는 Binance API 가 막혀 BTCUSDT 1h 실측(화면 사례의 첫 고점·기준선 값)은 하지 못했다 — 앱 재시작 후
  같은 구간에서 DT 마커가 사라졌는지 확인 요망.
- RSI 쌍바닥/쌍봉·MA 패턴(`indicators/ma_patterns`)은 이전 정의 그대로다.
