"""Compare a fresh external forecast fit with the frozen 2,232-row archive.

Run after train_external.py into a new directory. No fitting or network calls.
Numerical equality is tested explicitly; byte hashes are provenance only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODELS = ['daily', 'ridge', 'hist_gradient_boosting', 'mlp']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--reference', type=Path, default=HERE/'fresh_fits_20261012/frozen_forecasts.csv')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    left = pd.read_csv(args.reference, float_precision='round_trip')
    right = pd.read_csv(args.candidate, float_precision='round_trip')
    assert list(left.columns) == list(right.columns) and len(left) == len(right) == 2232
    other = [column for column in left.columns if column not in MODELS]
    assert left[other].equals(right[other]), 'Nonprediction columns or row order differ'
    results = {}
    for model in MODELS:
        a, b = left[model].to_numpy(), right[model].to_numpy()
        assert np.isfinite(a).all() and np.isfinite(b).all()
        assert np.allclose(a, b, rtol=1e-8, atol=1e-10), model
        results[model] = {'rows': len(a), 'max_absolute_difference': float(np.max(np.abs(a-b))),
                          'max_relative_difference': float(np.max(np.abs(a-b)/np.maximum(np.abs(a), 1e-300)))}
    output = {'status': 'PASS', 'scope': 'Numerical fresh-versus-frozen forecast comparison, no fitting performed by this checker',
              'absolute_tolerance': 1e-10, 'relative_tolerance': 1e-8,
              'rows': 2232, 'forecast_comparisons': 8928, 'nonprediction_columns': 'identical',
              'per_model': results,
              'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
              'candidate_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
