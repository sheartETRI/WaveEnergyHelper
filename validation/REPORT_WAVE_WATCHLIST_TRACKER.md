# REPORT_WAVE_WATCHLIST_TRACKER

Watchlist State Machine — Grade A Formation Tracking

- events: 2145
- GRADE_A_READY: 11
- riskiest state: STATE_STRONG_CONFIRMING

## Transition Matrix

| from | to | count | pct |
|---|---|---:|---:|
| STATE_NONE | STATE_EARLY_WARNING | 2145 | 35.11 |
| STATE_EARLY_WARNING | STATE_CONFIRMING | 1358 | 22.23 |
| STATE_CONFIRMING | STATE_FAILED | 893 | 14.62 |
| STATE_EARLY_WARNING | STATE_FAILED | 782 | 12.80 |
| STATE_CONFIRMING | STATE_STRONG_CONFIRMING | 461 | 7.55 |
| STATE_STRONG_CONFIRMING | STATE_FAILED | 459 | 7.51 |
| STATE_EARLY_WARNING | STATE_GRADE_A_READY | 5 | 0.08 |
| STATE_CONFIRMING | STATE_GRADE_A_READY | 4 | 0.07 |
| STATE_STRONG_CONFIRMING | STATE_GRADE_A_READY | 2 | 0.03 |

## State Duration

| state | avg | median | max |
|---|---:|---:|---:|
| STATE_NONE | 0.00 | 0.00 | 0 |
| STATE_EARLY_WARNING | 1.97 | 2.00 | 7 |
| STATE_CONFIRMING | 1.00 | 1.00 | 1 |
| STATE_STRONG_CONFIRMING | 1.71 | 1.00 | 7 |
| STATE_GRADE_A_READY | — | — | None |
| STATE_FAILED | — | — | None |

## Conversion Rate

| state | entered | conversion |
|---|---:|---:|
| STATE_EARLY_WARNING | 2145 | 0.51% |
| STATE_CONFIRMING | 1358 | 0.44% |
| STATE_STRONG_CONFIRMING | 461 | 0.43% |

## Failure Leakage

| state | fail_count | total_exits | fail_rate |
|---|---:|---:|---:|
| STATE_STRONG_CONFIRMING | 459 | 461 | 99.57% |
| STATE_CONFIRMING | 893 | 1358 | 65.76% |
| STATE_EARLY_WARNING | 782 | 2145 | 36.46% |

## Watchlist Funnel

| state | count | pct |
|---|---:|---:|
| STATE_EARLY_WARNING | 2145 | 100.00% |
| STATE_CONFIRMING | 1358 | 63.31% |
| STATE_STRONG_CONFIRMING | 461 | 21.49% |
| STATE_GRADE_A_READY | 11 | 0.51% |

## Success Paths

| path | count | pct |
|---|---:|---:|
| STATE_EARLY_WARNING → STATE_GRADE_A_READY | 5 | 45.45% |
| STATE_EARLY_WARNING → STATE_CONFIRMING → STATE_GRADE_A_READY | 4 | 36.36% |
| STATE_EARLY_WARNING → STATE_CONFIRMING → STATE_STRONG_CONFIRMING → STA | 2 | 18.18% |

## Failure Paths

| path | count | pct |
|---|---:|---:|
| STATE_EARLY_WARNING → STATE_CONFIRMING → STATE_FAILED | 893 | 41.85% |
| STATE_EARLY_WARNING → STATE_FAILED | 782 | 36.64% |
| STATE_EARLY_WARNING → STATE_CONFIRMING → STATE_STRONG_CONFIRMING → STA | 459 | 21.51% |

## ETH / BTC / SOL / BNB 비교

| symbol | n | conversion | fail_rate |
|---|---:|---:|---:|
| ETHUSDT | 487 | 1.44% | 98.56% |
| BTCUSDT | 548 | 0.00% | 100.00% |
| SOLUSDT | 509 | 0.79% | 99.21% |
| BNBUSDT | 601 | 0.00% | 100.00% |

- PNG: `wave_watchlist_tracker.png`
