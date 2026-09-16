# signal-alarm 브랜치 — 차트 세로 조작성 개선 보고 (Plotly 설정 계층만)

작성 2026-09-17. display/charts 계층만. 데이터·지표·알람 로직 무접촉, 신규 라이브러리 없음.

## 1. 커밋

| 구분 | 해시 | 내용 |
|---|---|---|
| 설정 | c5bb7b5 | plotly_builder: 전 y축 fixedrange=False, config doubleClick="reset"(PLOTLY_CONFIG), chart_height 인자, 가격 행 PRICE_ROW_SHARE=0.75, 조작법 캡션. main.py: "차트 높이 (px)" 셀렉트 600/800/1000(기본 800) |
| 테스트 | f926c6a | 슬림 스모크 2건 추가(설정값·배선) |

## 2. 항목별 처리

| 항목 | 수정 전 | 처리 |
|---|---|---|
| set_page_config(layout="wide") | 이미 적용 | 무변경 |
| plotly_chart config | scrollZoom=True, displaylogo=False | doubleClick="reset" 추가 |
| use_container_width=True | `width="stretch"` 사용 중 | 유지 — Streamlit 1.58 에서 use_container_width 는 deprecated, width="stretch" 가 그 현행 표기 |
| y축 fixedrange | 미명시(기본 False) | 전 서브플롯 `fixedrange=False` 명시 |
| rangeslider | 꺼짐 | 확인, 유지 |
| dragmode | "pan" | 확인, 유지(주석 추가) |
| 차트 높이 | 행별 px 합산 고정(스토캐·MACD·RSI 모두 켜면 1460px) | 사이드바 셀렉트 600/800/1000, 기본 800 |
| 가격 행 비중 | 520/1400 ≈ 0.37 | 0.75 고정, 나머지 패널이 0.25 를 기존 weight 비율로 분배 |
| 조작법 표기 | 없음 | 차트 바로 아래 캡션 1줄: "휠 = 커서 기준 확대·축소 · 축(눈금) 위에서 휠 = 그 축만 · 더블클릭 = 초기 범위로 · 드래그 = 이동" |

렌더 스모크: test_slim_app_smoke 11 passed(600/800/1000 각 figure 생성, 전 y축 fixedrange False, rangeslider 꺼짐, dragmode pan, 가격 도메인 ≥ 0.75×0.9), test_panel_smoke(레거시 어댑터는 chart_height 기본값) 3 passed 1 skipped, test_alarm_signals 21 passed.

## 3. 주의 — 가격 0.75 비중이 지표 패널을 매우 얇게 만든다

스토캐(Stacked)·MACD·RSI·거래량을 모두 켠 기본 구성에서 각 패널의 실제 픽셀 높이(마진 제외):

| 차트 높이 | 가격 | 거래량 | 스토캐 3층 | MACD | RSI |
|---|---|---|---|---|---|
| 600 | 365 | 18 | 37 | 33 | 33 |
| 800 | 505 | 25 | 52 | 46 | 46 |
| 1000 | 644 | 32 | 66 | 59 | 59 |

스토캐 3층 스택이 52px, MACD 크로스 마커가 46px 안에 들어가므로 지표 패널은 사실상 "있음" 확인 수준이다. 위임대로 0.75 를 적용했고 `PRICE_ROW_SHARE` 상수 하나로 조정된다(예: 0.55 → 800px 에서 스토캐 ~95px, MACD ~84px). 낮출지는 상위 결정.

## 4. 한계

x축(시간) 줌 시 y축이 보이는 구간의 가격 범위에 자동으로 밀착(autoscale)되지 않는다 — Plotly 는 x 줌과 y 범위를 독립으로 두며 설정으로 바꿀 수 없다. 이번 작업 범위 밖이고, 렌더 엔진 교체(lightweight-charts 류) 사안이다. 현재는 y축 위 휠 또는 더블클릭(초기 범위)으로 수동 보정한다.
