# REPORT_APP_RESTRUCTURE — 11차 위임: Streamlit 앱 전면 재구성 (표시 레이어)

작성일: 2026-07-10 / 실행: Claude Code / 성격: **표시 레이어 재구성** (분석·검출기·엔진 무수정)

677줄·45패널 직접 조립 `main.py`를 **~50줄 조립부 + 3탭 + 패널 레지스트리** 구조로 이관.
분석 모듈은 한 줄도 수정하지 않았다(display 어댑터·main 조립부만). 전 구간 "관측" 라벨 유지.

---

## 0. 요약 (한눈에)

| 항목 | 결과 |
|---|---|
| main.py | 677줄 → 51줄 (45개 개별 import/호출 제거) |
| 탭 구조 | 계기판 / 상세 분석 / 저널 (st.tabs) |
| 레지스트리 | 47 스펙 = 38 Type A + 9 컨텍스트 패널(핵심·사전계산·차트) |
| 카테고리 | 라이브 7 + 사전계산 1 + 레거시 1 + 차트 1 (총 10 그룹) |
| 레거시 격리 | 9종 (전역 스윕/신패널 대체본 — 삭제 아님, 접힘 격리) |
| 스모크 테스트 | 4개 (정합·Type A 오프라인·핵심 컨텍스트·사전계산 opt-in) |
| Type A 렌더 | 37/38 클린 · 1 pre-existing(wave_paths, 구 CSV 스키마) |
| 구동 스모크 | streamlit run → 3탭 BTCUSDT·ETHUSDT 렌더 확인(브라우저) |
| 분석 모듈 수정 | 0 |

---

## 1. 새 구조 (파일)

```
main.py                    진입점(51줄): 공유 심볼 사이드바 + 3탭 배선
legacy_main.py             구 main.py 원본 보존(참조용, 다음 라운드 삭제)
display/
  panel_context.py    [신] 심볼·TF당 1회 OHLCV·지표·분석 로드 → PanelContext (패널 공유)
  core_panels.py      [신] 파동에너지 요약/변곡 레이더/역학/AI 해설/디버그 (구 main.py 이관)
  panel_registry.py   [개] PanelSpec + 카테고리/어댑터/레거시 + 45패널 선언 + 렌더 헬퍼
  detail_tab.py       [신] [탭2] 사이드바(카테고리 토글) + 본문 카테고리 루프 렌더
  journal_tab.py      [신] [탭3] 관측 계기판 저널 · forward 저널 최근 기록 표
  v2_campaign_view.py [기존] [탭1] 계기판(9차 관측 계기판 + 캠페인 카드) — 재사용
tests/
  test_panel_smoke.py [신] 패널 스모크(정합·Type A·컨텍스트·사전계산 opt-in)
  test_narration.py   [개] 이동한 해설 헬퍼 import/patch → display.core_panels
docs/앱_사용법.md      [신] 3탭 구조·실행법·스모크
```

## 2. 탭 구성 (위임 A)

- **[탭1] 계기판** — `render_v2_campaign_view(symbol)` 재사용. 심볼당 slope 계기판(1d·4d 60MA
  3단+종합), 월봉 대파동 위치, TF 사다리 캠페인 카드, 형성 중 candidate/캔들, 전조 채널 슬롯(§2.5).
- **[탭2] 상세 분석** — 45패널 카테고리 레지스트리 루프. 사이드바에서 TF·기준시점·지표·패널 토글.
  파동에너지 요약·변곡 레이더·메인 차트는 항상, 나머지는 토글. 레거시는 접힘 격리.
- **[탭3] 저널** — 관측 계기판 저널 + forward 저널 최근 기록 표(부재를 정상 처리).

## 3. 패널 전수 목록 (카테고리·레거시 분류)

레지스트리 = 데이터 선언. Type A는 `render_xxx_panel(symbol, interval)`, 컨텍스트 패널은
`PanelContext` 어댑터. (`display/panel_registry.py`)

### 핵심 분석 (4) — 컨텍스트 어댑터
| key | 렌더 | always |
|---|---|---|
| core_wave_summary | 파동에너지 요약(4지표+verdict+역학) | ✓ |
| core_transition_radar | 변곡 레이더 | ✓ |
| show_ai_narration | AI 해설(옵트인) | |
| debug_dynamics_trace | 변곡점 트레이스+구조 분포(관측) | |

### 파동 구조·추적 (8, Type A · per-symbol CSV)
survival, outcome*, exit, expectancy, paths†, branch, confluence, candidate_rules
(*outcome: CSV 우선, CSV 부재 시 OHLCV fetch 폴백 — 유일한 네트워크 경로. †paths: 아래 3.1 참조)

### 관측 지표 (7, Type A)
volume_energy, energy_divergence, money_flow, structure_confirmation, structure_lte,
quality_score, quality_ruleset

### 세그먼트 (4, Type A)
wave_segmentation(per-symbol), symbol_segmentation, regime_segmentation, survival_segmentation

### 검증·강건성 (4, Type A)
ruleset_robustness, cross_market, failure_trigger_validation, robustness_validation

### 시뮬·정제 (2, Type A)
exit_policy_simulation, entry_filter_refinement

### 라이브·포워드·종합 (4, Type A)
live_watchlist, live_forward_journal, forward_observation, final_synthesis

### 파동 상태 (사전계산) (4) — 컨텍스트 어댑터, 기본 off
stability_verdict, wave_tracker, wave_confirmation, wave_lifecycle
(build_ohlcv_cache를 컨텍스트가 **1회** 생성해 4종이 공유 — 구 main.py는 패널마다 4번 호출)

### 차트 (1) — 컨텍스트 어댑터
core_chart (메인 Plotly, always, 마지막 — 구 main.py 순서 보존)

### 레거시 (9) — 격리(삭제 아님)
| key | 격리 사유 |
|---|---|
| generalization | 전역 12셀 스윕(symbol/interval 무시) · robustness_validation이 대체 |
| regime_gated | 전역 레짐 필터 스윕 · regime_segmentation+robustness가 대체 |
| rule_grading | ALL_SYMBOL/ALL_TF 전역 캘리브레이션 · quality_score가 대체 |
| grade_origin | 1회성 리포트-파싱 스윕(symbol/interval 무시) |
| grade_early_warning | 1회성 조기경보 스윕(symbol/interval 무시) |
| grade_failure | 1회성 실패원인 스윕(symbol/interval 무시) |
| grade_post_event | 대부분 전역 지연 스윕(per-symbol 최소) |
| confirmation_gate | 전역 게이트 P/R 스윕 · entry_filter_refinement가 대체 |
| watchlist_tracker | 전역 상태전이 스윕(코드 주석 "실시간 상태머신 아님") · live_watchlist가 대체 |

> 레거시 판정 근거: 전용 조사(display/wave_*_ui.py 전수 + analysis 추적). 9종 모두 현재
> 심볼/TF를 무시하고 최신 `*_sweep.py` 산출물(전역 CSV/REPORT)만 렌더 → 심볼별 상세 분석
> 맥락에서 오해 소지. 삭제하지 않고 접힘 expander로 격리.

### 3.1 pre-existing 예외 1건 (회귀 아님)
- **show_wave_paths**: `validation/wave_paths_BTCUSDT_1d.csv` 스키마가 구버전 —
  `timestamp,path,success,return_pct,expectancy_group`만 있고 `analysis/wave_path_analysis.py`가
  요구하는 `survival_bars` 컬럼 부재 → `KeyError`. **11차 이전부터** 동일 호출로 실패(재구성
  무관). 분석 모듈·CSV 재생성은 11차 범위 밖. 앱에서는 `render_panel_safe`가 패널 단위 격리 →
  앱 계속(레거시의 단일 외곽 try/except보다 안전: 한 패널 실패가 이후 패널/차트를 막지 않음).

## 4. 어댑터 방식 (위임 B)

- `PanelSpec.render(ctx)`: `adapter`가 있으면 `adapter(ctx)`, 없으면 `resolve()(ctx.symbol, ctx.interval)`.
- **Type A**(38): 시그니처가 이미 `(symbol, interval)`로 통일 → 어댑터 불요, 지연 import로 참조.
- **컨텍스트 패널**(9): 시그니처가 제각각(사전 계산 상태/분석 결과 주입) → display 얇은 어댑터가
  `PanelContext`에서 필요한 조각만 꺼내 기존 렌더 함수 호출. **분석 모듈 무수정.** 예:
  - `_adapt_wave_summary(ctx)` → `render_wave_summary(ctx.report, ctx.alignment)`
  - `_adapt_stability(ctx)` → `render_stability_verdict_panel(ctx.stability_aligned())`
  - `_adapt_chart(ctx)` → `render_chart(ctx.df, …, stability_aligned=ctx.stability_aligned() if 토글 else None, …)`
- **데이터 1회 공유**(위임 C): `build_panel_context`가 심볼·TF당 OHLCV·지표·분석(정합·리포트·
  레이더)을 1회 산출, 모든 패널이 공유. 사전계산 4종은 `ohlcv_cache()`를 1회 생성해 공유
  (구 main.py는 패널마다 `build_ohlcv_cache` 별도 호출 → fetch 중복). 기존 `@st.cache_data`는 유지.

## 5. 스모크 테스트 결과 (위임 C)

`tests/test_panel_smoke.py` — 렌더 산출 비교 없이 예외/공백 여부만.

| 테스트 | 결과 | 비고 |
|---|---|---|
| test_registry_integrity | **PASS** | 키 유일·38 Type A resolve·카테고리 유효·레거시 9 |
| test_type_a_panels_render_offline | **PASS** | BTCUSDT/1d, 37/38 클린. 신규 예외 0(회귀 가드) |
| test_context_panels_render_fast | **PASS** | 핵심 요약·레이더·해설(게이트)·디버그·차트 어댑터, ~10s |
| test_precomputed_panels_render_slow | SKIP(opt-in) | RUN_SLOW=1. stability ~68s/500행 검증. 아래 6-③ |

- bare streamlit 모드(streamlit run 없이 st.* 호출)에서 개별 패널을 직접 호출해 예외 표면화.
  render_panel_safe(격리 래퍼)가 아니라 raw 호출이라 실제 예외를 잡아낸다.
- 회귀 가드: 알려진 사전 예외(`{show_wave_paths}`) 외 신규 예외 발생 시 실패.

**전체 스위트 회귀 스윕**: `python -m pytest` → **565 passed, 1 skipped, 2 failed (2:45)**.
2 failed는 `test_wave_ruleset_robustness.py`(`analysis/wave_ruleset_robustness.py:246` —
`'numpy.ndarray' object has no attribute 'empty'`, pandas 3.0 호환 이슈)로 **pre-existing**:
11차 이전 커밋 `7160a7b`에서 동일 실패 재현 확인, 해당 테스트는 11차 변경 파일을 하나도
import하지 않으며 analysis 모듈 무수정. **11차로 인한 신규 테스트 실패 0.**
- 커밋 단위 bisect: 마이그레이션 위험(카테고리 배선)은 레지스트리 커밋(0485a75)에 집중,
  스모크 커밋(1caed18)이 패널 단위로 예외를 국소화. (38 Type A는 PHASE1에서 이미 레지스트리에
  등록됨 — 11차는 카테고리·어댑터·탭 루프 추가. "45개 일괄 커밋"은 발생하지 않음.)

## 6. 구동 스모크 (위임 D)

`streamlit run main.py` (headless :8599) 기동 → Playwright 브라우저로 3탭 확인.

**탭별 렌더 텍스트 (BTCUSDT/1d):**
- **[탭1] 계기판**: "v2 캠페인 종합 · BTCUSDT" / "추세 slope 계기판 · BTCUSDT — [관측]"
  (1d 60MA 하락 slope -x.xx%, 4d 60MA, 종합) / "월봉(1M) 대대파동 스토캐(40,20,20) 위치" /
  캠페인 카드(발단·진행·2파 예측·재진입, [관측 등급]) / "형성 중 후보 (candidate)" / "캔들 패턴" /
  "전조 슬롯 (1M) — 배열 기타 [관측 · 스펙 §2.5]".
- **[탭2] 상세 분석**: "상세 분석 · BTCUSDT · 1d" / "파동에너지 분석"(일봉 60MA 추세 하락 -2.11%,
  대파동 상승, 상위 4d 소파동 상승, 소파동 타이밍 하락) / "⚠️ 하락 추세 중 대파동 쌍바닥 —
  추세 전환 가능성 관찰" / "MA 배열: Mixed / Consolidation" / "변곡 레이더"(형성 중 [F6-5a]/[F6-5b]).
- **[탭3] 저널**: "관측 계기판 저널"(slope/월봉/전조 스냅샷) / "Forward 저널"(총 이벤트 2091,
  COMPLETED 1890, 진행/대기 201, 최근 30행 표).

**심볼 커버리지:**
- BTCUSDT·ETHUSDT: 3탭 전부 정상 렌더(브라우저 확인). ETHUSDT 탭1 슬로프/월봉/캠페인 카드 확인.
- USDT.D·BTC.D·ETH.D(도미넌스): Binance klines 0봉 → 탭1 "수집 중"·탭2 "데이터 로드 실패"로
  **graceful 처리**(크래시 없음). → 6-① 확인 요청.
- 콘솔 에러 0.

## 7. 미결 / 김박사 확인 요청

1. **① 심볼 구성 불일치 (확인 요청)**: 위임 문서는 "BTC/ETH/BNB/SOL 4심볼"이라 했으나
   `config.SUPPORTED_SYMBOLS`는 `[BTCUSDT, ETHUSDT, USDT.D, BTC.D, ETH.D]` 5개. BTC/ETH만
   Binance klines fetch 성공(각 500봉), 도미넌스 3종은 0봉(klines 미지원). BNB/SOL은 config에 없음
   (단 forward 저널엔 BNBUSDT 데이터 존재). **config 수정은 analysis 인접이라 11차 무수정** — 심볼
   목록 확정을 요청(도미넌스 데이터 소스 별도? BNB/SOL 추가?).
2. **② wave_paths pre-existing 예외**: 구 CSV 스키마('survival_bars' 부재). 분석/CSV 재생성 필요
   (11차 범위 밖). 현재 앱은 격리로 계속. → 후속 라운드에서 CSV 재생성 또는 분석 정합 결정 요청.
3. **③ 사전계산 패널 성능(pre-existing)**: stability ~68s, wave_tracker/confirmation/lifecycle는
   개별 **>5분**(get_*_timeline이 봉당 재계산). 기본 off + 격리라 부팅/일반 사용 영향 없음. 최적화
   (캐시/샘플링)는 분석 내부 → 향후 별도 위임 권장.
4. **④ st.tabs eager 렌더**: 3탭 본문이 매 rerun 계산(계기판+상세 동시). 부팅 비용은 구 앱과 유사
   (구 앱도 v2뷰+본분석 동시 렌더). 지연 로딩(active-tab 게이트)은 향후 옵션으로 남김.
5. **⑤ legacy_main.py 삭제**: 다음 라운드에서 새 구조 문제 없음 확인 후(11차 범위 아님).

## 8. 커밋 해시 목록 (레이어 단위, bisectable)

| 해시 | 커밋 |
|---|---|
| 17697c1 | chore: preserve v1 main.py as legacy_main.py (안전장치) |
| 6a54f31 | feat(display): 공유 PanelContext + 핵심 패널 이관 (B) |
| 0485a75 | feat(registry): 45패널 카테고리 분류 + 컨텍스트 어댑터 + 레거시 격리 (B) |
| 1caed18 | test: 패널 스모크 테스트 (C) |
| 1169585 | feat(display): 상세 분석 탭(레지스트리 루프)+저널 탭 (A) |
| 966aeb4 | feat(app): main.py 3탭 재구성 (A) |
| b3356d6 | docs: 앱 사용법 (D) |
| 47727d6 | test: 사전계산 slow 테스트 타이밍 주석 정확화 |
| (이 파일) | docs: REPORT_APP_RESTRUCTURE (11차 보고) |

## 9. 금지 준수 확인

- 분석 모듈·검출기·엔진 내부 무수정 — display 어댑터·main 조립부만. (변경 파일: main.py,
  display/panel_registry.py + 신규 display 모듈 + tests. analysis/·indicators/·charts/ 무수정.)
- 패널 삭제 0 — 레거시 9종은 격리만.
- 등급/추천 문구 없음 — "관측" 라벨 유지.
- 기존 리포트·스펙 무수정.
