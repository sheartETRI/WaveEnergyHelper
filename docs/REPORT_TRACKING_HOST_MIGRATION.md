# REPORT_TRACKING_HOST_MIGRATION — 전방 추적 이설 (2026-09-17)

전방 추적(F2-b 사이드카 · MM 섀도)의 정본 호스트를 구 호스트(sheart PC)에서
이 PC(DESKTOP-H89O19N, 계정 `C:\Users\user`)로 옮긴 기록이다. 기록·스케줄 계층의
작업이며 **판정·정의·INTEGRITY_FILES·헌장·열람 지시문은 건드리지 않았다.**
성과 지표(Δ′·G 등)는 이 문서에 쓰지 않는다 — 열람 동결(2027-03) 원칙.

§5 는 2027-03 열람 §A-4 커밋 감사표가 사고 커밋 `1857238` 을 만났을 때 참조할
정본 설명이고, §6 은 롤링 윈도우 구조와 이벤트 복원 공식이다.

## 1. 원격 재확인 · 추적 전용 클론

- 클론 직전 `origin/main` HEAD = `74fa4ad` (2026-09-04 18:36 KST). 그 이후 푸시 없음
  → 구 호스트 가동 증거 없음 → 진행.
- 클론 경로 `C:\Users\user\Desktop\WaveEnergyHelper-tracking` (원격 main). 앱 개발용
  signal-alarm 워킹트리(`Desktop\WaveEnergyHelper`)와 별개이며 무접촉.

## 2. 검증 실행

| 실행 | 시각(KST) | 결과 | journal | F2-b 사이드카 | 섀도 (BASE/NOSTOP/STRUCT) |
|---|---|---|---:|---:|---:|
| 기준 (74fa4ad) | 2026-09-04 | — | 4100 | 4100 | 15 (5/5/5) |
| 1차 | 09-17 20:52 → 21:00 | 3/3 ok, rc 0 | 3681 | 3681 | 46 (15/15/16) |
| 2차 (생존 신호 포함) | 09-17 21:08 → 21:15 | 3/3 ok, rc 0, git_publish=ok | 3681 (+0) | 3681 (+0) | 58 (19/19/20) |

- `logs/daily_tracking.log` 생성·성공 기록 확인 (logs/ 는 gitignore).
- integrity 테스트 `tests/test_align_gate_forward_integrity.py` 20건 통과.
- journal·사이드카가 4100→3681 로 **줄어든** 이유는 §6 (append-only 가 아니라 롤링
  윈도우 재생성). 신규 이벤트 746건은 2026-09-04 00:00 ~ 09-17 08:00 구간이며,
  9-04 이후 무인 공백은 이 1회로 복원됐다.

## 3. 스케줄 등록

`scripts/register_daily_tracking.ps1` 로 현재 사용자 등록 (관리자 불필요).

- 작업명 `WaveEnergyHelper Daily Tracking` · 매일 09:30 · StartWhenAvailable · Interactive only
- Run As User 김상철 · 실행 `C:\Python314\python.exe` · Start In = 추적 클론
- 등록 시 다음 실행 2026-09-18 09:30. 실행 제한 2시간.

## 4. 생존 신호 (유일한 코드 변경 — 커밋 `9a7bb7d`)

`scripts/daily_tracking.py` 말미에 `publish_survival_signal` 을 추가했다.

- 추적 파이프라인 CSV 4종(`wave_live_watchlist.csv` · `wave_live_forward_journal.csv` ·
  `wave_align_gate_forward.csv` · `wave_mm_shadow.csv`)을 commit & push. 보고서 md·png 는
  대상이 아니다.
- 경로 가드: `TRACKING_CLONE_ROOT` 와 같은 경로에서만 동작, 다른 워킹트리에서는 no-op.
- push 실패는 `status=warning` 로그만 남기고 추적 실행은 성공(rc 0) 처리.
- 커밋 메시지 `tracking: 주기 실행 (<날짜>) — F2-b <행수>행, 섀도 <행수>행`, 본문 1줄은
  `steps_ok=k/n | elapsed=…s`. 행 수·날짜·소요 시간 외에는 쓰지 않는다.
- **원격 main 의 마지막 `tracking:` 커밋 시각 = 생존 신호.** 첫 실제 커밋 `14ac47a`
  (2026-09-17 21:15 KST).
- 이 변경은 STEPS(기록 단계) 바깥의 별도 계층이며 판정·정의 무접촉. 테스트 11건 추가
  (가드 no-op · 변경 없음 시 커밋 생략 · push 실패 시 warning 과 rc 0 · 메시지 형식 ·
  git stdout 미기록).

## 5. 사고 커밋 `1857238` — 경위 · 무해성 · 원인 차단 (§A-4 감사표 참조용 정본 설명)

**커밋:** `1857238e206a9e9f8b83a4675b56ba54d86d3950`, 2026-09-17 20:57:43 KST,
제목 `tracking: 주기 실행 (2026-09-17) — F2-b 4100행, 섀도 15행`, 본문 `steps_ok=3/3 | elapsed=0.0s`.

**경위.** §4 의 생존 신호를 개발하던 중, 테스트 `test_main_returns_success_even_when_push_fails`
가 `monkeypatch` 로 모듈의 `run_git` 을 가짜로 바꿨으나, 당시 `publish_survival_signal` 의
기본 인자(`git_fn=run_git`, `log_fn=log`, `root=ROOT`)가 **함수 정의 시점에 바인딩**돼 있어
가짜가 아닌 실제 git 이 실행됐다. 실행 위치가 추적 클론이라 경로 가드도 통과했다.
그 순간 1차 검증 실행이 진행 중이었고 1단계(watchlist 스윕)가 막 갱신한
`validation/wave_live_watchlist.csv` 만 변경분으로 잡혀 커밋·푸시됐다. 제목의 행 수와
본문의 `steps_ok=3/3 | elapsed=0.0s` 는 모킹된 `run_steps` 결과이지 실제 실행 요약이 아니다.
(F2-b 4100행·섀도 15행은 그 시각 사이드카의 실제 행 수이긴 하다.)

**무해성.**
- 변경 파일은 `validation/wave_live_watchlist.csv` 1개뿐이다 (3681행, 1차 실행 1단계의
  실제 산출물). 코드·정의 파일·INTEGRITY_FILES·헌장·사이드카·섀도는 포함되지 않았다.
  따라서 §A-4 감사표(감사 기준 커밋 `1906f76` 이후 정의 파일 7개 + integrity 테스트의
  커밋 목록)에는 이 커밋이 나타나지 않는다. 감사표 대상 파일에 대한 `1906f76` 이후
  커밋은 이 보고 시점 기준 `0423094`(2026-09-04, 배선 작업) 하나뿐이다.
- 그 CSV 는 다음 정상 스냅샷 `14ac47a`(21:15) 에서 파이프라인이 다시 생성한 내용으로
  덮어써졌다. 판정·평가에 쓰이는 파일이 아니다(저널 생성의 중간 산출물).
- 원격 이력은 되돌리지 않았다 — main 의 강제 재작성이 더 큰 위험이라 판단.

**원인 차단 (커밋 `9a7bb7d` 에 포함).**
- `publish_survival_signal` 의 기본 인자를 `None` 으로 두고 **호출 시점**에 모듈 전역
  (`ROOT`·`log`·`run_git`)에서 읽도록 바꿔 monkeypatch 가 실제로 먹게 했다.
- `main()` 을 검증하는 테스트는 `ROOT` 를 가짜 경로로 바꿔 경로 가드가 실제로 막는지
  확인한다 (`test_main_publish_is_noop_outside_clone`), push 실패 테스트는 가짜 git 만
  호출됐는지 호출 목록으로 확인한다.
- 이후 실행된 전체 테스트에서 실제 저장소 접촉(로그·인덱스·커밋)이 없음을 확인했다.

## 6. 롤링 윈도우 구조와 이벤트 복원 공식

**구조.** watchlist 스캔은 심볼×TF 마다 **최근 `SCAN_BARS`=500 봉만** 스캔하고
(`analysis/wave_live_watchlist.py`), 저널(`wave_live_forward_journal.csv`)과 F2-b 사이드카
(`wave_align_gate_forward.csv`)는 매 실행 그 결과로 **전량 재생성**된다. append-only 가
아니다. 따라서 이벤트는 약 500봉 동안만 라이브 CSV 에 머문다.

| TF | 창 길이 (500봉) | 실측 창 시작 9-04 → 9-17 |
|---|---|---|
| 1h | ≈ 20.8일 | 08-15 01:00 → 08-27 16:00 |
| 4h | ≈ 83일 | 06-13 → 06-26 |
| 6h | ≈ 125일 | 05-03 → 05-20 |
| 1d | ≈ 500일 | 2025-05-07 → 2025-05-19 |

9-04 → 9-17 사이 탈락 1165건 중 1164건이 해당 TF 의 새 창 시작보다 이른 이벤트였다
(창 앞쪽 탈락). 1건(1d)은 창 안에서 사라졌으며 원인은 조사하지 않았다.
MM 섀도(`wave_mm_shadow.csv`)만 append-only(중복 제거) 이므로 이 절의 대상이 아니다.

**복원 공식.** 추적 창 전 구간의 이벤트 집합은 라이브 CSV 한 장이 아니라 git 스냅샷의
합집합이다.

```
전체 이벤트  E = J(74fa4ad) ∪ ⋃_d J(tracking 커밋 d)        (키 = event_id)
각 event_id 의 상태 = 그 event_id 가 마지막으로 등장한 스냅샷의 행
```

- `J(c)` = 커밋 c 의 `validation/wave_live_forward_journal.csv`. F2-b 사이드카
  (`wave_align_gate_forward.csv`)도 같은 공식으로 복원한다.
- `74fa4ad` 는 이설 직전 원격 HEAD(2026-09-04 산출물 포함). 일일 스냅샷은
  `tracking:` 접두 커밋이다 (`git log --format=%H -- validation/wave_live_forward_journal.csv`
  로 열거, `git show <hash>:validation/wave_live_forward_journal.csv` 로 추출).
- "마지막 등장 행" 을 택하는 이유: 결과 열(status·return_20·return_40·bars_elapsed)은
  봉이 지나며 채워지므로 늦은 스냅샷이 더 성숙한 상태다. 사고 커밋 `1857238` 은 저널
  파일을 포함하지 않으므로 이 열거에 나타나지 않는다.
- 2027-03 열람 §A·§B 는 이 합집합을 입력으로 삼아야 한다. 라이브 CSV 만 쓰면 1h 이벤트는
  마지막 3주치만 남는다. 열람 지시문은 수정하지 않았으며, 이 사항은 열람 보고서 §0 에
  기재할 항목이다.

**무인 공백 상한 ≈ 3주 (1h 창).** 호스트가 멈춰 스냅샷이 끊기면, 그 사이 발생한 1h
이벤트는 약 20.8일 뒤 창 밖으로 밀려 **어떤 스냅샷에도 남지 않고 소실**된다. 4h 이상은
여유가 크다(83일+). 따라서 원격 `tracking:` 커밋 시각이 3주 가까이 멈추면 그 전에
복구해야 한다. `StartWhenAvailable` 은 꺼져 있던 PC 가 켜지면 놓친 실행을 따라잡지만,
3주를 넘긴 공백은 따라잡지 못한다.

## 7. 의존성 핀 (커밋 `ae96714`) 과 열람 경로 드라이런

- `requirements.txt` 에 `numpy==2.4.4`, `pandas==3.0.2` 고정 (이 호스트의 검증 환경).
  정의 파일 무접촉. `pip install --dry-run -r requirements.txt` 해석 정상.
- 근거: `tests/test_wave_ruleset_robustness.py` 2건(walk_forward · robustness_score)이
  이미 numpy2/pandas3 회귀(`'numpy.ndarray' object has no attribute 'empty'`)로 실패
  중이다. 핀은 이 실패를 고치지 않고, 열람 시점까지 더 새 버전으로 같은 부류의 실패가
  열람 경로에 번지는 것을 막는다.
- 열람 경로 임포트 10모듈 정상 (`wave_align_gate_forward(_sweep)`, `mm_shadow`,
  `wave_mm_shadow_sweep`, `wave_htf_gate(_v2)(_sweep)`, `wave_live_forward_journal`,
  `wave_live_watchlist`, `wave_ruleset_robustness`).
- `--report` 드라이런: `review_decision` 만 스텁(판정 미실행)하고 나머지 경로(사이드카
  로드·전방 슬라이스·월 클러스터 부트스트랩·감사표·integrity 테스트·렌더)를 실제로
  실행. 종료코드 0, §1~§4 네 절 렌더, "기한 도달 아니오" 표기 확인. 렌더된 md 는
  중간 수치를 담으므로 커밋하지 않고 `git checkout` 으로 원복했다.
- `wave_mm_shadow_sweep.py --peek` 종료코드 0 (출력은 열람 원칙에 따라 기록하지 않음).

## 8. 테스트

- 핀 이후 전체 테스트: 674 통과 · 2 실패 · 1 스킵 (핀 전 실행과 동일). 실패 2건 = `test_wave_ruleset_robustness.py::test_walk_forward`, `::test_robustness_score`.
- 실패 2건은 §7 의 기존 회귀이며 이설 변경 파일(`scripts/daily_tracking.py`,
  `tests/test_daily_tracking.py`, `requirements.txt`, 이 문서)과 무관하다.

## 9. 남은 것

- 구 호스트(sheart PC)가 가동 중으로 확인되면 그 PC 에서 스케줄러를 해제한다.
- 추적 클론에는 파이프라인이 갱신하는 보고서 md·png 가 미커밋 상태로 남는다(의도적).
- 1d 창 안에서 사라진 이벤트 1건의 원인은 미조사.
- 기존 테스트 `test_shadow_sidecar_is_idempotent_on_rerun`(main 원본)은 실제
  `wave_mm_shadow.csv` 를 다시 쓴다 — 행 수는 같지만 행 순서가 바뀐다. 추적 클론에서
  전체 테스트를 돌린 뒤에는 `git checkout -- validation/wave_mm_shadow.csv` 로 원복해야
  다음 `tracking:` 커밋에 순서 변경만 담긴 diff 가 섞이지 않는다. 이번에도 원복했다.
  테스트 수정은 이 위임 범위 밖이라 하지 않았다.
