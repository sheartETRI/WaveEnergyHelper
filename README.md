# WaveEnergyHelper

Binance 암호화폐 시세를 바탕으로 스토캐스틱 패턴, 60MA 전환, 추세 구조를 관찰하는 Streamlit 앱입니다. 현재 기본 화면은 **차트 / 알람** 두 탭입니다. 별도 스크립트로 Pushbullet 알림과 명령행 보고서를 제공합니다.

## 시작하기

저장소 루트에서 실행합니다. 아래는 PowerShell 기준입니다.

```powershell
python -m pip install -r requirements.txt
$env:PYTHONUTF8 = "1"
python -m streamlit run main.py
```

Python 3.10 기준 의존성과 전이 패키지는 검증한 버전으로 고정했습니다. 개발·연구·브라우저 설치 범위와 테스트 명령은 [개발·검증 안내](docs/개발_검증.md)에 있습니다.

## 현재 기능과 실행 경로

| 경로 | 용도 |
|---|---|
| [main.py](main.py) | BTC·ETH·BNB·SOL, 19개 시간봉의 차트·알람·레이더·60MA 및 추세 구조 추적 |
| [scripts/alarm_cli.py](scripts/alarm_cli.py) | 앱의 통합 알람 텍스트 추출, 시간봉·섹션 선택, 파일 저장 |
| [scripts/push_alarms.py](scripts/push_alarms.py) | Pushbullet 이벤트 알림, 중복 방지, 후보 기록, 일일 요약 |
| [scripts/sweep_scan_report.py](scripts/sweep_scan_report.py) | 수동 스윕·합류 스캔과 CSV 보고서 |
| [deploy/push_alarms.service](deploy/push_alarms.service) | Linux 상주 알림 서비스 설정 예시 |

```powershell
python scripts/alarm_cli.py --tf 1h,2h,4h --out logs/alarm.md
python scripts/push_alarms.py --help
```

앱은 수동 새로고침을 사용합니다. 푸시 폴러는 별도로 실행하며, 기본 대상은 BTCUSDT의 1h·2h·4h·6h·12h·1d·2d입니다. 앱 알람에는 진행 중 봉이 포함될 수 있고, 푸시는 마감된 봉을 사용합니다. 화면 신호 전체가 푸시 대상인 것은 아닙니다.

화면 사용법은 [현재 사용법](docs/앱_사용법.md), 푸시 설정·명령과 상태 파일 관리는 [운영 안내](docs/운영_안내.md)를 참고하세요. 전체 문서는 [문서 색인](docs/README.md)에서 찾을 수 있습니다.

## 코드 구성

| 폴더 | 역할 |
|---|---|
| `data/`, `indicators/` | OHLCV 수신·저장·리샘플, 공용 프레임 적재(`data/frames.py`), 기술지표 |
| `analysis/` | 현재 분석 경로와 연구·시뮬레이션 모듈 |
| `tracking/` | 앱·알림이 함께 사용하는 후보 추출·60MA 추적·다이버전스·추세 구조 계산 |
| `display/`, `charts/` | 현재 UI, 이전 상세 패널, 차트 렌더링 |
| `notify/`, `scripts/` | 외부 알림·이력·구형 알림 구현과 CLI 조립 |
| `utils/` | 공용 KST 표시와 알람 문구 |
| `narration/` | 현재 기본 화면에서 호출하지 않는 AI 해설 |
| `validation/` | 원본 계측 스크립트·연구 실행·보존 결과물 |
| `tests/`, `docs/` | 테스트, 규칙·사용법·변경 보고서 |

원본 계측 코드는 출처 검증용으로 보존하고 운영 계산은 `tracking/`으로 분리했습니다. 연구 모듈의 사용처와 자료 경로는 [연구·산출물 안내](docs/연구_산출물.md) 및 색인에 기록합니다. Plotly와 이전 상세 분석·저널 UI는 보존되어 있으며 현재 기본 화면에는 연결되어 있지 않습니다.

## 정리 작업

[정리 계획 및 체크리스트](docs/정리_계획.md)에 근거·완료 기준을, [작업 기록](docs/정리_작업_기록.md)에 실제 변경·검증 결과를 기록합니다.

테스트 실행 기준과 이전 분석에서 확인한 결과도 해당 문서에 있습니다. 실제 주문을 실행하는 경로는 이번 코드 조사에서 확인되지 않았습니다.
