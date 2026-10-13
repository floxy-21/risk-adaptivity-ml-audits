"""No-fit chronology and source-quality fixtures for the external archive."""
from pathlib import Path
import ast
import hashlib
import json
import numpy as np
import pandas as pd
from forecast import daily_design, MLP_PARAMETERS, HGB_PARAMETERS, FEATURE_NAMES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    index = pd.date_range('2014-10-01', '2015-04-03 23:00', freq='h', tz='UTC')
    values = 1+np.arange(len(index))/1000
    series = pd.Series(values, index=index)
    days, x, y, features, reference = daily_design(series, pd.Timestamp('2015-04-02', tz='UTC'))
    # Exercise the actual disk serialization/decoder units, including a
    # microsecond-index source (pandas3 defaults) and a nanosecond source.
    # No source data or model is involved in these regression fixtures.
    import io
    for unit in ('us', 'ns'):
        original_dates = days.as_unit(unit)
        saved = io.BytesIO()
        np.savez_compressed(saved, days_ns=original_dates.as_unit('ns').asi8)
        saved.seek(0)
        loaded = np.load(saved, allow_pickle=False)
        decoded = pd.to_datetime(loaded['days_ns'], unit='ns', utc=True)
        assert np.all(decoded == original_dates)
        assert decoded.min().year == 2014 and decoded.max().year == 2015
    assert len(days) == len(index)//24 and np.all(features[8:]) and not features[:8].any()
    scalar_checks = 0
    for j in range(8, len(days)):
        for k, lag in enumerate((2, 3, 8)):
            np.testing.assert_array_equal(x[j, :, k], y[j-lag])
            scalar_checks += 24
        np.testing.assert_array_equal(x[j, :, 3], np.repeat(y[j-2].mean(), 24))
        scalar_checks += 24
        latest_end = days[j]-pd.Timedelta(days=1)
        issue = days[j]-pd.Timedelta(hours=12)
        assert latest_end < issue
    # All same-day and future target perturbations leave the issue-time input
    # unchanged, including the UK spring clock transition on this UTC grid.
    for day in ('2015-01-01', '2015-02-14', '2015-03-29'):
        start = pd.Timestamp(day, tz='UTC')
        perturbed = series.copy()
        perturbed.loc[start:] += 1000
        d2, x2, _, _, _ = daily_design(perturbed, pd.Timestamp('2015-04-02', tz='UTC'))
        j = days.get_loc(start)
        np.testing.assert_array_equal(x2[j], x[j])
        scalar_checks += 240
    # One missing lagged hour removes a whole learned feature day but leaves
    # the other 23 independent persistence copies available.
    broken = series.copy()
    broken.loc[pd.Timestamp('2015-02-01 04:00', tz='UTC')] = np.nan
    _, xb, _, fb, _ = daily_design(broken, pd.Timestamp('2015-04-02', tz='UTC'))
    j = days.get_loc(pd.Timestamp('2015-02-03', tz='UTC'))
    assert not fb[j] and np.isfinite(xb[j, :, 0]).sum() == 23
    # Same-day reference absence must not suppress a valid forecast archive.
    hidden = series.copy()
    hidden.loc['2015-02-10'] = np.nan
    _, xh, _, fh, rh = daily_design(hidden, pd.Timestamp('2015-04-02', tz='UTC'))
    j = days.get_loc(pd.Timestamp('2015-02-10', tz='UTC'))
    assert fh[j] and not rh[j]
    np.testing.assert_array_equal(xh[j], x[j])
    # New-year validation issue boundary: training includes Dec31, so model
    # state first exists Jan1 midnight. Jan1 forecast was issued earlier;
    # Jan2 forecast is permissible without shortening the training period.
    train_end = pd.Timestamp('2015-01-01', tz='UTC')
    assert pd.Timestamp('2015-01-01', tz='UTC')-pd.Timedelta(hours=12) < train_end
    assert pd.Timestamp('2015-01-02', tz='UTC')-pd.Timedelta(hours=12) >= train_end
    # Fixed forecasting specifications equal the frozen existing trainer.
    source = ROOT/'outputs/run_energy_rank_study.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    original_mlp = None
    original_hgb = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MLP_PARAMETERS' for t in node.targets):
            original_mlp = {kw.arg: ast.literal_eval(kw.value) for kw in node.value.keywords}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'HistGradientBoostingRegressor':
            original_hgb = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
    assert original_mlp == MLP_PARAMETERS
    assert original_hgb == HGB_PARAMETERS
    report = {'status': 'passed', 'fits_performed': 0, 'external_data_opened': False,
              'feature_scalar_checks': scalar_checks, 'feature_names': FEATURE_NAMES,
              'same_day_future_perturbation_fixtures': 3, 'missing_lag_persistence_independence': 'passed',
              'missing_target_forecast_independence': 'passed', 'training_issue_boundary': 'passed',
              'saved_day_timestamp_unit_roundtrip_fixtures': ['microsecond index', 'nanosecond index'],
              'frozen_model_parameters_equal': True,
              'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (HERE/'forecast.py', HERE/'check_design.py', source)}}
    (HERE/'design_check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
