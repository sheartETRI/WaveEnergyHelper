"""Wave Confirmation DB → K 지연 분석 테스트."""

import os

import sys



import numpy as np

import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_confirmation import (

    OUTCOME_CROSS,

    OUTCOME_NO_CONFIRM,

    analyze_episodes_from_arrays,

    cross_confirm_at,

    slope_confirm_at,

)

from analysis.wave_tracker import (

    DOUBLE_BOTTOM_CANDIDATE,

    WAVE3_CANDIDATE,

    WAVE3_COMPLETED,

    _BarSignals,

    _MachineContext,

    step_tracker,

)





def _run_episodes(k_vals, d_vals, db_at, tb_at=None, ll_at=None, os_at=None, n=None):

    n = n or len(k_vals)

    idx = pd.date_range("2026-01-01", periods=n, freq="4h")

    k = pd.Series(k_vals, index=idx)

    d = pd.Series(d_vals, index=idx)

    db = pd.Series(False, index=idx)

    for i in db_at:

        db.iloc[i] = True

    tb = pd.Series(False, index=idx)

    if tb_at:

        for i in tb_at:

            tb.iloc[i] = True

    ll = pd.Series(False, index=idx)

    if ll_at:

        for i in ll_at:

            ll.iloc[i] = True

    os_ = pd.Series(False, index=idx)

    if os_at:

        for i in os_at:

            os_.iloc[i] = True

    return analyze_episodes_from_arrays(idx, k, d, db, tb, ll, os_)





def test_cross_delay_3_bars_after_db():

    n = 15

    k = [50.0] * n

    d = [55.0] * n

    k[7], d[7] = 54.0, 55.0

    k[8], d[8] = 56.0, 55.0

    assert cross_confirm_at(pd.Series(k), pd.Series(d), 8)



    eps = _run_episodes(k, d, db_at=[5])

    assert len(eps) == 1

    assert eps[0].confirm_cross_delay == 3

    assert eps[0].final_outcome == OUTCOME_CROSS





def test_slope_delay_2_bars_after_db():

    n = 12

    k = [40.0, 41.0, 42.0, 43.0, 44.0, 45.0, 44.0, 45.0, 46.0, 47.0, 48.0, 49.0]

    d = [50.0] * n

    k[5], k[6], k[7] = 45.0, 44.0, 46.0

    assert slope_confirm_at(pd.Series(k), 7)



    eps = _run_episodes(k, d, db_at=[5])

    assert eps[0].confirm_slope_delay == 2

    assert eps[0].confirmed_by_slope





def test_no_confirm_within_window():

    n = 20

    k = list(np.linspace(30, 35, n))

    d = [40.0] * n

    eps = _run_episodes(k, d, db_at=[2], n=n)

    assert eps[0].confirm_cross_delay is None

    assert eps[0].confirm_slope_delay is None

    assert eps[0].final_outcome == OUTCOME_NO_CONFIRM

    assert not eps[0].within[13]["cross"]

    assert not eps[0].within[13]["slope"]





def test_tb_before_cross_sets_required_flag():

    n = 15

    k = [50.0] * n

    d = [55.0] * n

    k[8] = 51.0

    k[9], d[9] = 54.0, 55.0

    k[10], d[10] = 56.0, 55.0

    eps = _run_episodes(k, d, db_at=[5], tb_at=[7])

    assert eps[0].confirm_cross_delay == 5

    assert eps[0].required_tb_before_confirm

    assert eps[0].final_outcome == OUTCOME_CROSS





def test_wave_tracker_unchanged():

    ctx = _MachineContext(

        state=DOUBLE_BOTTOM_CANDIDATE,

        state_start_ts=pd.Timestamp("2026-01-02"),

        state_start_idx=5,

    )

    snap = step_tracker(

        ctx,

        _BarSignals(major_k_rising=True, major_k=25.0),

        pd.Timestamp("2026-01-03"),

        8,

    )

    assert snap.state == WAVE3_COMPLETED

    assert "K turned upward" in snap.reason



    ctx2 = _MachineContext()

    step_tracker(ctx2, _BarSignals(oversold_entry=True), pd.Timestamp("2026-01-01"), 0)

    snap2 = step_tracker(

        ctx2,

        _BarSignals(oversold_entry=True, major_ll=True),

        pd.Timestamp("2026-01-02"),

        1,

    )

    assert snap2.state == WAVE3_CANDIDATE


