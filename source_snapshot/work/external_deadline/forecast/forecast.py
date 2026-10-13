"""Causal noon-issued forecast archive for the frozen external audit benchmark.

Preparation is source-only. The fit command refuses changed preparation inputs
and never tunes specifications or substitutes households based on outcomes.
UTC-shaped timestamps encode the declared benchmark clock, not a claim that
the source provider measured physical UTC interval-start timestamps.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import platform
import time
import warnings
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(name, '2')
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
MLP_PARAMETERS = dict(hidden_layer_sizes=(32, 16), activation='relu', solver='adam',
    alpha=.001, learning_rate_init=.001, batch_size=256, max_iter=1000,
    early_stopping=False, random_state=1729, tol=.0001, n_iter_no_change=10, shuffle=True)
HGB_PARAMETERS = dict(max_iter=100, learning_rate=.08, max_leaf_nodes=15,
    min_samples_leaf=20, l2_regularization=1, max_bins=127, random_state=1729,
    early_stopping=False)
MODEL_NAMES = ['daily', 'ridge', 'hist_gradient_boosting', 'mlp']
FEATURE_NAMES = ['lag2_same_hour', 'lag3_same_hour', 'lag8_same_hour', 'mean_day_minus2',
                 'hour_sin', 'hour_cos', 'weekday_sin', 'weekday_cos', 'month_sin', 'month_cos']


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(8*1024*1024):
            h.update(chunk)
    return h.hexdigest()


def array_sha(value):
    value = np.ascontiguousarray(value)
    return hashlib.sha256(value.tobytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def utc_day(value):
    result = pd.Timestamp(value)
    result = result.tz_localize('UTC') if result.tzinfo is None else result.tz_convert('UTC')
    if result != result.floor('D'):
        raise ValueError('Period endpoints must be UTC days')
    return result


def timestamp_text(value):
    return pd.Timestamp(value).isoformat().replace('+00:00', 'Z')


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    periods = {}
    for name in ('train', 'validation', 'test'):
        start, end = utc_day(config[name+'_start']), utc_day(config[name+'_end'])
        if start > end:
            raise ValueError('Period starts after its end')
        periods[name] = (start, end)
    if not (periods['train'][1] < periods['validation'][0] and periods['validation'][1] < periods['test'][0]):
        raise ValueError('Training, validation and test must be strictly chronological')
    if int(config.get('min_training_days', 30)) < 30:
        raise ValueError('At least 30 feature-valid training days required')
    return config, periods


def parse_eligibility(series):
    text = series.astype(str).str.lower().str.strip()
    if not text.isin(['true', 'false', '1', '0']).all():
        raise ValueError('eligible must contain only true/false/1/0')
    return text.isin(['true', '1']).to_numpy()


def daily_design(series, archive_end):
    """Benchmark-clock features independent of same-day target availability."""
    series = series.sort_index()
    if not isinstance(series.index, pd.DatetimeIndex) or str(series.index.tz) != 'UTC':
        raise ValueError('Expected a UTC DatetimeIndex')
    start = series.index.min().floor('D')
    end = max(series.index.max().floor('D'), utc_day(archive_end))
    index = pd.date_range(start, end+pd.Timedelta(hours=23), freq='h')
    y = series.reindex(index).to_numpy(dtype=float).reshape(-1, 24)
    days = index[::24]
    x = np.full((len(days), 24, 10), np.nan)
    for k, lag in enumerate((2, 3, 8)):
        x[lag:, :, k] = y[:-lag]
    means = np.mean(y, axis=1)
    x[2:, :, 3] = means[:-2, None]
    hours = np.arange(24)
    x[:, :, 4] = np.sin(2*np.pi*hours/24)
    x[:, :, 5] = np.cos(2*np.pi*hours/24)
    x[:, :, 6] = np.sin(2*np.pi*days.dayofweek.to_numpy()[:, None]/7)
    x[:, :, 7] = np.cos(2*np.pi*days.dayofweek.to_numpy()[:, None]/7)
    x[:, :, 8] = np.sin(2*np.pi*(days.month.to_numpy()[:, None]-1)/12)
    x[:, :, 9] = np.cos(2*np.pi*(days.month.to_numpy()[:, None]-1)/12)
    feature_complete = np.isfinite(x).all(axis=(1, 2))
    reference_complete = np.isfinite(y).all(axis=1) & (y >= 0).all(axis=1)
    return days, x, y, feature_complete, reference_complete


def period_mask(days, periods, name):
    start, end = periods[name]
    return np.asarray((days >= start) & (days <= end))


def period_labels(days, periods):
    labels = np.full(len(days), 'context', dtype=object)
    for name in periods:
        labels[period_mask(days, periods, name)] = name
    return labels


def prepare(hourly_path, config_path, output_dir):
    hourly_path, config_path, out = Path(hourly_path).resolve(), Path(config_path).resolve(), Path(output_dir).resolve()
    if (out/'prepared.json').exists():
        raise FileExistsError('Preparation already frozen; use a new output directory')
    config, periods = load_config(config_path)
    data = pd.read_csv(hourly_path, dtype={'household_id': str})
    required = ['household_id', 'timestamp_utc', 'energy_kwh', 'eligible']
    if not set(required).issubset(data.columns):
        raise ValueError('Hourly source missing required columns')
    data = data[required].copy()
    data['timestamp_utc'] = pd.to_datetime(data.timestamp_utc, utc=True)
    if data.duplicated(['household_id', 'timestamp_utc']).any():
        raise ValueError('Duplicate household/hour in frozen source')
    if not (data.timestamp_utc == data.timestamp_utc.dt.floor('h')).all():
        raise ValueError('Hourly source must lie on the declared hourly benchmark grid')
    data['eligible'] = parse_eligibility(data.eligible)
    data['energy_kwh'] = pd.to_numeric(data.energy_kwh, errors='raise')
    eligible_values = data.loc[data.eligible, 'energy_kwh']
    if not np.isfinite(eligible_values).all() or (eligible_values < 0).any():
        raise ValueError('An eligible source hour lacks finite nonnegative energy')
    ids = list(map(str, config.get('household_ids', sorted(data.household_id.unique()))))
    if len(set(ids)) != len(ids) or not set(ids).issubset(set(data.household_id)):
        raise ValueError('Frozen household IDs missing or duplicated')
    archive_end = periods['test'][1]+pd.Timedelta(days=2)
    out.mkdir(parents=True, exist_ok=True)
    counts, inventory, references, array_files = [], [], [], []
    for number, household in enumerate(ids):
        frame = data[data.household_id == household].sort_values('timestamp_utc')
        source = pd.Series(frame.energy_kwh.where(frame.eligible).to_numpy(), index=pd.DatetimeIndex(frame.timestamp_utc))
        days, x, y, feature_complete, reference_complete = daily_design(source, archive_end)
        labels = period_labels(days, periods)
        train = period_mask(days, periods, 'train') & feature_complete & reference_complete
        train_days = int(train.sum())
        if train_days < int(config.get('min_training_days', 30)):
            raise RuntimeError(f'Frozen household {household} has only {train_days} feature-valid training days; do not silently replace it')
        training_mean = float(y[train].mean())
        if not np.isfinite(training_mean) or training_mean <= 0:
            raise ValueError(f'Frozen household {household} has nonpositive training mean')
        train_data_end = days[train][-1]+pd.Timedelta(days=1)
        issue = days-pd.Timedelta(hours=12)
        issue_eligible = np.asarray(issue >= train_data_end)
        archive_day = np.asarray((days >= periods['validation'][0]) & (days <= archive_end))
        learned = feature_complete & issue_eligible & archive_day
        candidate = reference_complete & learned
        file_name = f'household_{number:03d}.npz'
        # Pandas 3 date_range commonly stores microseconds. Pin the unit,
        # rather than assuming DatetimeIndex.asi8 always means nanoseconds.
        day_nanoseconds = days.as_unit('ns').asi8
        if not np.all(pd.to_datetime(day_nanoseconds, unit='ns', utc=True) == days):
            raise AssertionError('Prepared benchmark dates failed exact timestamp round trip')
        np.savez_compressed(out/file_name, days_ns=day_nanoseconds, x=x, y=y, feature_complete=feature_complete,
                            reference_complete=reference_complete, train=train, learned=learned, archive_day=archive_day,
                            candidate=candidate, issue_eligible=issue_eligible)
        array_files.append(file_name)
        per = {'household_id': household, 'array_file': file_name, 'training_days': train_days,
               'training_mean_kwh': training_mean, 'training_data_end_utc': timestamp_text(train_data_end),
               'train_X_sha256': array_sha(x[train].reshape(-1, 10)), 'train_y_sha256': array_sha(y[train].reshape(-1)),
               'counts': {name: {'complete_reference_days': int((reference_complete & period_mask(days, periods, name)).sum()),
                                'feature_complete_days': int((feature_complete & period_mask(days, periods, name)).sum()),
                                'candidate_days': int((candidate & period_mask(days, periods, name)).sum())}
                          for name in periods}}
        if per['counts']['validation']['candidate_days'] == 0:
            raise RuntimeError(f'Frozen household {household} has no causal validation cases for surrogate calibration')
        counts.append(per)
        for j in np.flatnonzero(archive_day):
            inventory.append({'household_id': household, 'day_utc': str(days[j].date()), 'period': labels[j],
                              'reference_complete': bool(reference_complete[j]), 'feature_complete': bool(feature_complete[j]),
                              'model_training_available_at_issue': bool(issue_eligible[j]),
                              'all_forecasts_complete': bool(learned[j]), 'eligible': bool(candidate[j]),
                              'persistence_available_hours': int(np.isfinite(x[j, :, 0]).sum()),
                              'issue_time_utc': timestamp_text(issue[j]), 'training_data_end_utc': timestamp_text(train_data_end)})
            if labels[j] in ('validation', 'test'):
                for h in range(24):
                    references.append({'household_id': household, 'timestamp_utc': timestamp_text(days[j]+pd.Timedelta(hours=h)),
                                       'energy_kwh': float(y[j, h]) if np.isfinite(y[j, h]) else np.nan,
                                       'eligible': bool(np.isfinite(y[j, h]) and y[j, h] >= 0), 'period': labels[j]})
    pd.DataFrame(inventory).to_csv(out/'candidate_days.csv', index=False)
    pd.DataFrame(references).to_csv(out/'reference_targets.csv', index=False, float_format='%.17g')
    save(out/'frozen_config.json', config)
    protocol = config.get('protocol_path')
    protocol_hash = sha(protocol) if protocol else None
    result = {'status': 'prepared', 'prepared_utc': stamp(), 'households': counts,
              'hourly_path': str(hourly_path), 'hourly_sha256': sha(hourly_path), 'config_path': str(config_path),
              'config_sha256': sha(config_path), 'protocol_path': str(Path(protocol).resolve()) if protocol else None,
              'protocol_sha256': protocol_hash, 'script_sha256': sha(__file__),
              'archive_start_utc': timestamp_text(periods['validation'][0]), 'archive_end_day_utc': str(archive_end.date()),
              'feature_names': FEATURE_NAMES, 'chronology': 'Declared benchmark clock stored with UTC-shaped labels: forecast for day D issued noon D-1; latest feature record is assigned available at start of D-1. Persistence copies D-2. Learned archive excludes issues before final training-target availability. Source physical timezone and interval-endpoint semantics require separate provenance and are not inferred here.',
              'clock_basis': config.get('clock_basis', 'Declared benchmark grid; UTC-shaped labels do not establish provider UTC or physical interval-start convention'),
              'day_timestamp_serialization': 'int64 nanoseconds since Unix epoch, explicitly normalized before saving',
              'source_only_preparation': True, 'fits_performed': 0,
              'prepared_hashes': {name: sha(out/name) for name in array_files+['candidate_days.csv', 'reference_targets.csv', 'frozen_config.json']}}
    save(out/'prepared.json', result)
    print(json.dumps({'status': result['status'], 'households': len(counts), 'training_days': sum(h['training_days'] for h in counts), 'output_dir': str(out)}, indent=2))


def fit(prepared_dir):
    out = Path(prepared_dir).resolve()
    if (out/'fit_metadata.json').exists() or (out/'forecast_archive.csv').exists():
        raise FileExistsError('Refuse to overwrite frozen fitted archive; no retries or refits in this directory')
    prepared = json.loads((out/'prepared.json').read_text(encoding='utf-8'))
    for key in ('hourly', 'config'):
        if sha(prepared[key+'_path']) != prepared[key+'_sha256']:
            raise ValueError('Frozen '+key+' changed')
    if prepared['protocol_path'] and sha(prepared['protocol_path']) != prepared['protocol_sha256']:
        raise ValueError('Frozen protocol changed')
    if sha(__file__) != prepared['script_sha256']:
        raise ValueError('Forecast implementation changed after preparation')
    for name, expected in prepared['prepared_hashes'].items():
        if sha(out/name) != expected:
            raise ValueError('Prepared input changed: '+name)
    config, periods = load_config(out/'frozen_config.json')
    archive_rows, household_meta, surrogate = [], [], {}
    started = time.perf_counter()
    for item in prepared['households']:
        household = item['household_id']
        arrays = np.load(out/item['array_file'], allow_pickle=False)
        days = pd.to_datetime(arrays['days_ns'], unit='ns', utc=True)
        x, y, train, learned, archive_day = (arrays[key] for key in ('x', 'y', 'train', 'learned', 'archive_day'))
        if (not np.all(period_mask(days, periods, 'train')[train]) or
                pd.Timestamp(item['training_data_end_utc']) != days[train][-1]+pd.Timedelta(days=1)):
            raise AssertionError('Prepared timestamp units or training chronology are inconsistent; no fitting performed')
        train_x, train_y = x[train].reshape(-1, 10), y[train].reshape(-1)
        predict_x = x[learned].reshape(-1, 10)
        training_mean = float(train_y.mean())
        if array_sha(train_x) != item['train_X_sha256'] or array_sha(train_y) != item['train_y_sha256']:
            raise AssertionError('Training arrays differ from frozen preparation')
        candidates = [make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
                      HistGradientBoostingRegressor(**HGB_PARAMETERS),
                      make_pipeline(StandardScaler(), MLPRegressor(**MLP_PARAMETERS))]
        predictions = np.full((len(days), 24, 4), np.nan)
        predictions[:, :, 0] = x[:, :, 0]
        model_meta = []
        with threadpool_limits(limits=2):
            for index, (name, estimator) in enumerate(zip(MODEL_NAMES[1:], candidates), start=1):
                model_started = time.perf_counter()
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    estimator.fit(train_x, train_y/training_mean if name == 'mlp' else train_y)
                    values = estimator.predict(predict_x).reshape(-1, 24)
                if name == 'mlp':
                    values *= training_mean
                if not np.isfinite(values).all():
                    raise ArithmeticError('Model produced nonfinite forecasts: '+household+'/'+name)
                predictions[learned, :, index] = np.maximum(values, 0.)
                record = {'model': name, 'seconds': time.perf_counter()-model_started,
                          'negative_predictions_clipped': int((values < 0).sum()),
                          'warnings': [{'category': type(w.message).__name__, 'message': str(w.message)} for w in caught]}
                if name == 'mlp':
                    neural = estimator.named_steps['mlpregressor']
                    record.update(epochs=int(neural.n_iter_), training_objective_loss=float(neural.loss_),
                                  target_scale_training_mean_kwh=training_mean)
                model_meta.append(record)
        valid = arrays['candidate'] & period_mask(days, periods, 'validation')
        residuals = y[valid]-predictions[valid, :, 1]
        rmse = float(np.sqrt(np.mean(residuals**2)))
        floor = 1e-8*training_mean
        surrogate[household] = {'mean_model': 'ridge', 'validation_days': int(valid.sum()),
                                'validation_target_count': int(residuals.size),
                                'validation_residual_rmse_kwh': rmse, 'training_scale_floor_kwh': floor,
                                'sd_kwh': max(rmse, floor), 'training_mean_kwh': training_mean,
                                'frozen_before_test_evaluation': True}
        for j in np.flatnonzero(archive_day):
            issue = days[j]-pd.Timedelta(hours=12)
            for h in range(24):
                if not np.isfinite(predictions[j, h]).any():
                    continue
                target = days[j]+pd.Timedelta(hours=h)
                persistence_source = target-pd.Timedelta(days=2)
                latest_end = days[j]-pd.Timedelta(days=1)
                if persistence_source+pd.Timedelta(hours=1) > issue:
                    raise AssertionError('Persistence source occurs after issue')
                if learned[j] and (latest_end > issue or pd.Timestamp(item['training_data_end_utc']) > issue):
                    raise AssertionError('Feature or fitted state occurs after issue')
                archive_rows.append({'household_id': household, 'target_timestamp_utc': timestamp_text(target),
                                     'issue_time_utc': timestamp_text(issue),
                                     'persistence_source_time_utc': timestamp_text(persistence_source) if np.isfinite(predictions[j, h, 0]) else '',
                                     'latest_feature_source_end_utc': timestamp_text(latest_end) if learned[j] else '',
                                     **dict(zip(MODEL_NAMES, predictions[j, h]))})
        household_meta.append({**item, 'models': model_meta, 'learned_prediction_days': int(learned.sum()),
                               'persistence_archive_hours': int(np.isfinite(predictions[archive_day, :, 0]).sum()),
                               'surrogate': surrogate[household]})
        print('Fitted '+household+': '+str(int(train.sum()))+' training days, '+str(int(learned.sum()))+' learned archive days', flush=True)
    frame = pd.DataFrame(archive_rows)
    frame.to_csv(out/'forecast_archive.csv', index=False, float_format='%.17g')
    save(out/'surrogate_parameters.json', surrogate)
    result = {'status': 'passed', 'completed_utc': stamp(), 'seconds': time.perf_counter()-started,
              'households': household_meta, 'model_fit_count': 3*len(household_meta),
              'forecast_archive_rows': len(frame), 'models': MODEL_NAMES, 'feature_names': FEATURE_NAMES,
              'model_parameters': {'ridge': {'alpha': 1.0, 'input_standard_scaler': True},
                                   'hist_gradient_boosting': HGB_PARAMETERS,
                                   'mlp': {**MLP_PARAMETERS, 'input_standard_scaler': True, 'target_scale': 'training mean'}},
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                           'scipy': scipy.__version__, 'scikit_learn': sklearn.__version__},
              'numerical_threads': 2, 'prepared_sha256': sha(out/'prepared.json'), 'script_sha256': sha(__file__),
              'output_hashes': {name: sha(out/name) for name in ('forecast_archive.csv', 'surrogate_parameters.json', 'candidate_days.csv', 'reference_targets.csv')},
              'scope': 'Fixed training-only models, validation-only residual scale, causal forecast archive; no test comparison or acquisition outcome computed.'}
    save(out/'fit_metadata.json', result)
    print(json.dumps({'status': result['status'], 'model_fit_count': result['model_fit_count'], 'forecast_archive_rows': len(frame)}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--hourly', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--output-dir', required=True)
    f = commands.add_parser('fit')
    f.add_argument('--prepared', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.hourly, args.config, args.output_dir)
    else:
        fit(args.prepared)


if __name__ == '__main__':
    main()
