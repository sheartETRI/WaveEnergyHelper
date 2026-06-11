"""Wave Confirmation Lifecycle 테스트."""

import os

import sys



import numpy as np

import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_confirmation import analyze_episodes_from_arrays

from analysis.wave_confirmation_lifecycle import (

    INITIAL_CROSS,

    INITIAL_NO_CONFIRM,

    INITIAL_SLOPE,

    INITIAL_TB,

    POST_EXPIRED,

    POST_HELD,

    POST_LATER_LL,

    POST_LATER_OS,

    analyze_lifecycle_from_arrays,

)





def _series(n, k_vals, d_vals=None, db_at=None, tb_at=None, ll_at=None, os_at=None):

    idx = pd.date_range("2026-01-01", periods=n, freq="4h")

    k = pd.Series(k_vals, index=idx)

    d = pd.Series(d_vals if d_vals is not None else [50.0] * n, index=idx)

    z = pd.Series(False, index=idx)

    db, tb, ll, os_ = z.copy(), z.copy(), z.copy(), z.copy()

    for i in db_at or []:

        db.iloc[i] = True

    for i in tb_at or []:

        tb.iloc[i] = True

    for i in ll_at or []:

        ll.iloc[i] = True

    for i in os_at or []:

        os_.iloc[i] = True

    return idx, k, d, db, tb, ll, os_





def test_db_slope_then_held():

    n = 20

    k = [40.0] * n

    k[4] = 41.0

    k[5], k[6], k[7] = 45.0, 44.0, 46.0

    idx, k, d, db, tb, ll, os_ = _series(n, k, db_at=[5])

    eps = analyze_lifecycle_from_arrays(idx, k, d, db, tb, ll, os_)

    assert eps[0].initial_outcome == INITIAL_SLOPE

    assert eps[0].post_outcome == POST_HELD

    assert eps[0].bars_until_initial == 2





def test_db_cross_then_new_ll():

    n = 25

    k = [50.0] * n

    k[10] = 56.0

    d = [55.0] * n

    idx, k, d, db, tb, ll, os_ = _series(n, k, d_vals=d, db_at=[5], ll_at=[20])

    eps = analyze_lifecycle_from_arrays(idx, k, d, db, tb, ll, os_)

    assert eps[0].initial_outcome == INITIAL_CROSS

    assert eps[0].post_outcome == POST_LATER_LL

    assert eps[0].bars_held_after_initial == 10





def test_db_tb_then_re_oversold():

    n = 20

    k = [50.0] * n

    idx, k, d, db, tb, ll, os_ = _series(n, k, db_at=[5], tb_at=[9], os_at=[16])

    eps = analyze_lifecycle_from_arrays(idx, k, d, db, tb, ll, os_)

    assert eps[0].initial_outcome == INITIAL_TB

    assert eps[0].post_outcome == POST_LATER_OS





def test_no_confirm_expired():

    n = 20

    k = list(np.linspace(30, 35, n))

    idx, k, d, db, tb, ll, os_ = _series(n, k, db_at=[2])

    eps = analyze_lifecycle_from_arrays(idx, k, d, db, tb, ll, os_)

    assert eps[0].initial_outcome == INITIAL_NO_CONFIRM

    assert eps[0].post_outcome == POST_EXPIRED





def test_wave_confirmation_unchanged():

    n = 15

    k = [50.0] * n

    d = [55.0] * n

    k[7], d[7] = 54.0, 55.0

    k[8], d[8] = 56.0, 55.0

    idx, k, d, db, tb, ll, os_ = _series(n, k, d_vals=d, db_at=[5])

    eps = analyze_episodes_from_arrays(idx, k, d, db, tb, ll, os_)

    assert eps[0].confirm_cross_delay == 3

    assert eps[0].confirmed_by_cross


