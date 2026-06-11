# REPORT_WAVE_CANDIDATE_RULES

Confluence 우수 조건 Candidate Rule 강건성·안정성 관측

## ETHUSDT 4h

- CSV: `wave_candidate_rules_ETHUSDT_4h.csv`
- PNG: `wave_candidate_rules_ETHUSDT_4h.png`
- Confluence 이벤트: 25

### Rule Performance

| rule | n | win | expectancy |
|---|---:|---:|---:|
| RULE_B | 5 | 4 | 2.34 |
| RULE_C | 4 | 3 | 2.18 |
| RULE_D | 4 | 3 | 2.18 |
| RULE_E | 4 | 3 | 2.18 |
| RULE_F | 4 | 3 | 2.18 |
| RULE_G | 4 | 3 | 2.18 |
| RULE_H | 4 | 3 | 2.18 |
| RULE_SCORE_3 | 4 | 3 | 2.18 |
| RULE_A | 7 | 5 | 1.67 |
| RULE_SCORE_4 | 1 | 0 | -0.29 |

### Rule Robustness

| rule | windowA | windowB | gap |
|---|---:|---:|---:|
| RULE_B | 3.00 | 1.90 | 1.10 |
| RULE_C | 3.00 | 1.36 | 1.64 |
| RULE_D | 3.00 | 1.36 | 1.64 |
| RULE_E | 3.00 | 1.36 | 1.64 |
| RULE_F | 3.00 | 1.36 | 1.64 |
| RULE_G | 3.00 | 1.36 | 1.64 |
| RULE_H | 3.00 | 1.36 | 1.64 |
| RULE_SCORE_3 | 3.00 | 1.36 | 1.64 |
| RULE_A | 3.00 | 0.68 | 2.32 |
| RULE_SCORE_4 | — | — | — |

### Rule Stability Score

| rule | stability | expectancy | n |
|---|---:|---:|---:|
| RULE_B | 1.91 | 2.34 | 5 |
| RULE_C | 1.58 | 2.18 | 4 |
| RULE_D | 1.58 | 2.18 | 4 |
| RULE_E | 1.58 | 2.18 | 4 |
| RULE_F | 1.58 | 2.18 | 4 |
| RULE_G | 1.58 | 2.18 | 4 |
| RULE_H | 1.58 | 2.18 | 4 |
| RULE_SCORE_3 | 1.58 | 2.18 | 4 |
| RULE_A | 1.03 | 1.67 | 7 |
| RULE_SCORE_4 | -0.00 | -0.29 | 1 |

### Top Rules

1. RULE_B — stability 1.91, exp 2.34%, n=5
2. RULE_C — stability 1.58, exp 2.18%, n=4
3. RULE_D — stability 1.58, exp 2.18%, n=4
4. RULE_E — stability 1.58, exp 2.18%, n=4
5. RULE_F — stability 1.58, exp 2.18%, n=4
6. RULE_G — stability 1.58, exp 2.18%, n=4
7. RULE_H — stability 1.58, exp 2.18%, n=4
8. RULE_SCORE_3 — stability 1.58, exp 2.18%, n=4
9. RULE_A — stability 1.03, exp 1.67%, n=7
10. RULE_SCORE_4 — stability -0.00, exp -0.29%, n=1

### Failure Analysis

| rule | failure reason | % |
|---|---|---:|
| RULE_A | STOP_LOSS | 50.00 |
| RULE_A | TIMEOUT | 50.00 |
| RULE_B | TIMEOUT | 100.00 |
| RULE_C | TIMEOUT | 100.00 |
| RULE_D | TIMEOUT | 100.00 |
| RULE_E | TIMEOUT | 100.00 |
| RULE_F | TIMEOUT | 100.00 |
| RULE_G | TIMEOUT | 100.00 |
| RULE_H | TIMEOUT | 100.00 |
| RULE_SCORE_3 | TIMEOUT | 100.00 |
| RULE_SCORE_4 | TIMEOUT | 100.00 |

- Most Stable: RULE_B (score 1.91)
- Least Stable: RULE_SCORE_4 (score -0.00)

## BTCUSDT 1d

- CSV: `wave_candidate_rules_BTCUSDT_1d.csv`
- PNG: `wave_candidate_rules_BTCUSDT_1d.png`
- Confluence 이벤트: 3

### Rule Performance

| rule | n | win | expectancy |
|---|---:|---:|---:|
| RULE_A | 2 | 0 | -3.00 |
| RULE_B | 0 | 0 | — |
| RULE_C | 0 | 0 | — |
| RULE_D | 0 | 0 | — |
| RULE_E | 0 | 0 | — |
| RULE_F | 0 | 0 | — |
| RULE_G | 0 | 0 | — |
| RULE_H | 0 | 0 | — |
| RULE_SCORE_3 | 0 | 0 | — |
| RULE_SCORE_4 | 0 | 0 | — |

### Rule Robustness

| rule | windowA | windowB | gap |
|---|---:|---:|---:|
| RULE_A | — | — | — |
| RULE_B | — | — | — |
| RULE_C | — | — | — |
| RULE_D | — | — | — |
| RULE_E | — | — | — |
| RULE_F | — | — | — |
| RULE_G | — | — | — |
| RULE_H | — | — | — |
| RULE_SCORE_3 | — | — | — |
| RULE_SCORE_4 | — | — | — |

### Rule Stability Score

| rule | stability | expectancy | n |
|---|---:|---:|---:|
| RULE_A | -0.00 | -3.00 | 2 |
| RULE_B | — | — | 0 |
| RULE_C | — | — | 0 |
| RULE_D | — | — | 0 |
| RULE_E | — | — | 0 |
| RULE_F | — | — | 0 |
| RULE_G | — | — | 0 |
| RULE_H | — | — | 0 |
| RULE_SCORE_3 | — | — | 0 |
| RULE_SCORE_4 | — | — | 0 |

### Top Rules

1. RULE_A — stability -0.00, exp -3.00%, n=2
2. RULE_B — stability —, exp —%, n=0
3. RULE_C — stability —, exp —%, n=0
4. RULE_D — stability —, exp —%, n=0
5. RULE_E — stability —, exp —%, n=0
6. RULE_F — stability —, exp —%, n=0
7. RULE_G — stability —, exp —%, n=0
8. RULE_H — stability —, exp —%, n=0
9. RULE_SCORE_3 — stability —, exp —%, n=0
10. RULE_SCORE_4 — stability —, exp —%, n=0

### Failure Analysis

| rule | failure reason | % |
|---|---|---:|
| RULE_A | STOP_LOSS | 100.00 |

- Most Stable: RULE_A (score -0.00)
- Least Stable: RULE_A (score -0.00)

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| top rule | RULE_B | RULE_A |
| top stability | 1.91 | -0.00 |
| top expectancy | 2.34 | -3.00 |
| RULE_SCORE_3 exp | 2.18 | — |
| RULE_SCORE_3 n | 4 | 0 |
