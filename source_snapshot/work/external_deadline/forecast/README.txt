CAUSAL FORECAST ARCHIVE GENERATION

No actual external fits are performed merely by importing this module.
Run preparation only after the source-only eligibility rule, household list,
period amendment and experimental protocol have been frozen:

 python work/external_deadline/forecast/forecast.py prepare --hourly HOURLY.csv --config CONFIG.json --output-dir PREPARED_DIRECTORY
 python work/external_deadline/forecast/forecast.py fit --prepared PREPARED_DIRECTORY

Config keys (inclusive benchmark-day endpoints, stored as UTC-shaped labels):
 train_start, train_end, validation_start, validation_end, test_start, test_end
 Optional: household_ids (explicit frozen list), min_training_days (>=30),
 protocol_path (absolute/working-directory-relative path pinned by SHA256).
Hourly input columns: household_id,timestamp_utc,energy_kwh,eligible.
The timestamp is an index on the source conversion's declared benchmark
grid. Its UTC-shaped representation does not itself verify the provider's
physical timezone or whether the original labels are starts or ends. For
the LCL source, both physical details remain unverified; the declared mapping
preserves source labels and forms hourly target records from two half-hour
energy rows. Requested coordinates count these hourly target records, not
physical meter transactions. See the source manifest for its exact pairing.
Ineligible
source hours become NaN before any targets or lagged features are built.
Only finite, nonnegative eligible source values may enter the benchmark.

Forecast schedule and features
For target day D, every hour's forecast is assigned issued at noon on D-1
under the declared benchmark clock.
Inputs are corresponding-hour energy from D-2,D-3,D-8; the complete mean
energy on D-2; and sine/cosine encodings of hour, weekday and month.
The latest feature-source day is assigned available at midnight beginning
D-1, twelve hours before issue. Stored day grids have 24 indexed hours; no
conversion from a verified provider timezone or production-arrival log is
claimed. Duplicate or missing clock-label episodes are handled by the source
quality rules, not silently used as measured complete reference hours.

Fitting uses complete reference/feature days in the training period only,
requiring at least 30. Specifications are unchanged from the frozen main
study: standardized Ridge(alpha=1), HGB(max_iter=100,learning_rate=.08,
max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,max_bins=127,
random_state=1729,early_stopping=False), and the fixed (32,16) MLP with its
previous iteration allowance and convergence rule. The MLP target is divided
by the training mean during fitting and rescaled afterward. All forecasts
are nonnegative-clipped. Two numerical threads and all library versions,
fit durations, warnings and MLP iterations are recorded. No retries,
hyperparameter tuning or household replacements are implemented.

The fitted model state cannot be used before the declared final training
target availability. For training ending Dec31, this excludes the Jan1 validation
forecast (issued noon Dec31); Jan2 can be generated. The exact exclusion is
recorded in candidate_days.csv and fit metadata rather than hidden.

The learned forecast archive includes every complete FEATURE day from
validation start through test-end+2, regardless of whether its own targets
are observed/eligible. This preserves available later prediction records.
Persistence is independently generated for every hour with an eligible
D-2 source reading, even when other lagged features or target hours are
missing. No already-issued persistence prediction is discarded because
learned forecasts or reference targets are incomplete.

Outputs
- prepared.json: input/config/protocol/code SHA256 pins; per-household counts;
  training-array hashes; source-only preparation with zero fits.
- household_NNN.npz: numeric prepared day/feature/target arrays and masks.
- candidate_days.csv: all archive days, reference/feature/model-state flags,
  period, issue date, persistence availability and final eligibility.
- reference_targets.csv: separate validation/test hourly targets and source
  eligibility flags. The acquisition selector must not read this file.
- forecast_archive.csv: household_id,target_timestamp_utc,issue_time_utc,
  persistence_source_time_utc,latest_feature_source_end_utc,daily,ridge,
  hist_gradient_boosting,mlp. Missing predictions are blank. Rows with no
  available prediction at all are omitted. Every nonblank persistence copy
  retains its exact source-target timestamp.
- surrogate_parameters.json: per-household Hara mean-model specification,
  validation-only Ridge residual RMSE, training-mean floor and fixed SD.
- fit_metadata.json: all model parameters, training-array/source hashes,
  warnings, durations, versions, output hashes, and execution counts.

The residual SD is sqrt(mean squared validation residual), bounded below by
1e-8 times the positive training mean. It is not a test-set residual estimate.
The fit command does not compute test model rankings or recovery outcomes.
It rejects modified pinned inputs and refuses to overwrite an existing fit.

No-fit synthetic checks:
 python work/external_deadline/forecast/check_design.py
Checks lag identities, same-day/future target perturbation invariance,
independent persistence availability, reference-target/forecast separation,
the training/issue boundary, and unchanged model specifications using AST
comparison with the frozen trainer. It does not train models or inspect
external source outcomes.
