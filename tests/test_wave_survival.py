"""Wave Survival 분석 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_survival import (

    INITIAL_CROSS,

    INITIAL_SLOPE,

    INITIAL_TB,

    TERM_CENSORED,

    TERM_NEW_LL,

    TERM_RE_OVERSOLD,

    build_survival_from_lifecycle,

    summarize_survival,

    survival_rate_at,

)

from analysis.wave_confirmation_lifecycle import (

    INITIAL_NO_CONFIRM,

    POST_EXPIRED,

    POST_HELD,

    POST_LATER_LL,

    POST_LATER_OS,

    lifecycle_to_dataframe,

    analyze_lifecycle_from_arrays,

)





def _lifecycle_row(ts, initial, post, held):

    return {

        "timestamp": ts,

        "initial_outcome": initial,

        "post_outcome": post,

        "bars_until_initial": 2,

        "bars_until_post": 10,

        "bars_held_after_initial": held,

    }





def test_survival_bars_from_held():

    lc = pd.DataFrame([_lifecycle_row("2026-01-01", INITIAL_SLOPE, POST_HELD, 28)])

    sv = build_survival_from_lifecycle(lc)

    assert sv.iloc[0]["survival_bars"] == 28





def test_held_is_censored():

    lc = pd.DataFrame([_lifecycle_row("2026-01-01", INITIAL_CROSS, POST_HELD, 15)])

    sv = build_survival_from_lifecycle(lc)

    assert sv.iloc[0]["censored"]

    assert sv.iloc[0]["termination_reason"] == TERM_CENSORED





def test_expired_no_confirm_excluded():

    lc = pd.DataFrame([_lifecycle_row("2026-01-01", INITIAL_NO_CONFIRM, POST_EXPIRED, 0)])

    sv = build_survival_from_lifecycle(lc)

    assert sv.empty





def test_new_ll_termination():

    lc = pd.DataFrame([_lifecycle_row("2026-01-02", INITIAL_SLOPE, POST_LATER_LL, 14)])

    sv = build_survival_from_lifecycle(lc)

    assert not sv.iloc[0]["censored"]

    assert sv.iloc[0]["termination_reason"] == TERM_NEW_LL

    assert sv.iloc[0]["survival_bars"] == 14





def test_re_oversold_termination():

    lc = pd.DataFrame([_lifecycle_row("2026-01-03", INITIAL_CROSS, POST_LATER_OS, 25)])

    sv = build_survival_from_lifecycle(lc)

    assert sv.iloc[0]["termination_reason"] == TERM_RE_OVERSOLD





def test_survival_rate_threshold():

    rows = [

        _lifecycle_row("2026-01-01", INITIAL_SLOPE, POST_LATER_OS, 25),

        _lifecycle_row("2026-01-02", INITIAL_SLOPE, POST_LATER_LL, 8),

        _lifecycle_row("2026-01-03", INITIAL_SLOPE, POST_HELD, 30),

    ]

    sv = build_survival_from_lifecycle(pd.DataFrame(rows))

    assert abs(survival_rate_at(sv, 20, INITIAL_SLOPE) - 200 / 3) < 0.01





def test_lifecycle_unchanged():

    import numpy as np

    n = 20

    k = list(np.linspace(30, 35, n))

    idx = pd.date_range("2026-01-01", periods=n, freq="4h")

    k_s = pd.Series(k, index=idx)

    d_s = pd.Series([40.0] * n, index=idx)

    db = pd.Series(False, index=idx)

    db.iloc[2] = True

    z = pd.Series(False, index=idx)

    eps = analyze_lifecycle_from_arrays(idx, k_s, d_s, db, z, z, z)

    df = lifecycle_to_dataframe(eps)

    assert df.iloc[0]["initial_outcome"] == INITIAL_NO_CONFIRM

    assert df.iloc[0]["post_outcome"] == POST_EXPIRED


