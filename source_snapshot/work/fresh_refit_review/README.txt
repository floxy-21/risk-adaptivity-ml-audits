Fresh model-refit verification

The archived run freshly trains the declared Ridge, histogram-gradient-
boosting and MLP estimators for all 64 series, and reconstructs persistence,
from newly parsed pinned raw data. It reuses the declared fitting code.
verify_refit.py is separately written and performs independent arithmetic,
configuration, chronology and feature checks without fitting models or
importing refit.py. This is not an independent implementation of training,
an additional dataset, a retuning exercise, or a full downstream mask rerun.

Default PUBLIC verification, requiring only distributed UCI forecast rows:
  python work/fresh_refit_review/verify_refit.py --public
This compares 61 UCI series and 159,984 hourly rows against the original
lossless forecast archive and the 30-consumer archive. It also checks all 64
archived per-fit metadata records, but does not independently reconstruct
the omitted BLEM hourly rows from distributed data. The all 64 local audit
is preserved separately in independent_verification.json and its metrics.

FULL LOCAL independent verification, after fresh training outputs and
newly rebuilt hourly inputs are present:
  python work/fresh_refit_review/verify_refit.py
This compares 64 series and 166,536 hourly rows, plus all actual reconstructed
feature matrices, training/test calendars and complete-reference metrics.
Run replay checks in an isolated copy to preserve archived report timestamps.

Optional fresh retraining requires an isolated tree with the original
source paths, raw files, source/selection reports and both protocols. The
comparison protocol must be frozen before fitting. Start with no existing
prepared.json, fresh_predictions.csv or hourly/ in the new audit directory:
  python work/fresh_refit_review/refit.py prepare
  python work/fresh_refit_review/refit.py fit
  python work/fresh_refit_review/verify_refit.py
  python work/fresh_refit_review/export_public.py
  python work/fresh_refit_review/verify_refit.py --public
The driver refuses to replace preparation or forecast outputs. Source and
configuration hashes are recorded; failures are retained without retries.
The public ZIP omits the original mixed prediction file containing BLEM
targets/persistence; reconstruct it from pinned raw inputs and the original
lossless export using the package's raw reconstruction procedure before a
fresh refit. No fitted-estimator pickle is read or distributed. New hourly
pickles are intermediate data, not fitted model states, and remain local.

Dependencies: the versions recorded in fresh_result.json, including NumPy,
pandas, SciPy, scikit-learn and threadpoolctl. Original helpers are
outputs/run_energy_rank_study.py, outputs/energy_rank_bounds.py and
work/data_prepare_blem.py. Declared features/hyperparameters are unchanged.
The source trainer sets two numerical threads; the isolated driver runs
one series at a time. Wall timings are descriptive on a shared host.

Redistribution: fresh_predictions.csv and hourly/ remain local. Only
fresh_predictions_public.csv, aggregate comparisons, training metadata,
source/configuration hashes, protocols and executable reconstruction/check
code are supplied. omission_manifest.json identifies the full local archive
by checksum and records the 6,552 BLEM rows omitted from the public export.
