EXTERNAL HPM FROZEN-FORECAST GEOMETRY AND STORED-SAMPLE REPLAY

This experiment evaluates the already-frozen Jan-Jun2025 training / July2025
test protocol on public systems1,2,7. No system replacement, new model,
retuning, threshold selection, network request or training occurs here.
It is a stored API-grid sample analysis, not a physical-energy calibration or
proof of measured forecast/reading availability at nominal clock times.

From the project root, with numpy,pandas,scipy installed:
python work/risk_adaptivity_revision/external_validation/replay/run_external.py
python work/risk_adaptivity_revision/external_validation/replay/check_external.py

The executed environment was work/review-env/Scripts/python.exe. Measured
runtime: approximately109seconds for full geometry/replay and10seconds for the
independent checker on this host. These are observed run times, not guarantees.
No fresh forecast refit is claimed by these two commands. The source fit is in
external_validation/operational/train_external.py and fresh_fits_20261012/.

Dependencies retained at their existing paths:
- counter_adaptive/study.py (original five-policy numerical geometry);
- counter_adaptive/feedback_triage/analyze.py (exact triage/finite-game checks);
- counter_adaptive/math_review/check_half_cover.py and check_counter_adaptive.py;
- external_validation/math/counter_two_side.py (separate adaptive verification);
- external_heatpump/hourly/train_test_hourly_counters.csv;
- external_validation/operational/fresh_fits_20261012/{frozen_forecasts.csv,training_report.json};
- external_validation/operational/protocol_lock.json.

Inputs are hash-pinned in the code. Original raw public API responses and URLs,
license/source notes and selection protocol remain in external_heatpump/.
Forecast CSV SHA256:
04dc64193fbcf00879e4f7ba5224d5626def79a8caad474fb3242d3d8d69b12f
Canonical counter CSV SHA256:
b66ed33d2b1b00ac680bf564c3329231317b8176b7e88ac318ee0714494077da

Output mapping:
initial_intake.csv --279calendar blocks and forecast/outer-endpoint eligibility.
geometry.json --1,674coefficient-only geometry cases, exact triage, policy choices.
half_witnesses.json --29exact adverse mixtures and continuum covering witnesses.
replay_attrition.csv --all1,674reference-availability decisions; no exclusions.
query_trace.json --first answer ratio and subsequent optional-query selection.
replay_cases.csv --10,073policy rows: six policies on all1,674cases plus cover29.
policy_summary.csv --policy means; IMPORTANT cover has29cases, other rows1674.
half_policy_summary.csv --all policies restricted to the same29certifiedhalf cases.
meter_policy_summary.csv, pair_policy_summary.csv, meter_pair_policy_summary.csv
  --recorded metrics and explicit case denominators.
geometry_group_counts.csv --triage counts by meter,pair,and meter/pair.
report.json --complete primary summaries, paired outcome counts, source hashes.
verification.json --production rational containment/telescoping checks.
independent_checks.json --separate all-case rational and representative LP checks.
manuscript_fragment.tex --optional methods/results text; main paper not edited.

The five original selective policies keep their objectives and pre-answer tie
rules. Exact rational coefficients determine ties for deterministic/greedy/
adaptive actions; the mean-width mixture retains its uniform-vertex secondary
LP. The precision-cover policy is an added established coefficient-only rule on
cases with matching exact1/2upper/lower certificates. No internal fine answer
enters policy choice before geometry.json is saved. The terminal second action
uses its first observed prefix ratio as specified by adaptation.

Guarantees and threshold comparisons use exact rational representations of
the serialized binary64 coefficient vector and decimal counter values. The
known affine constant is serialized binary64. Independently computed paired
MSE versus affine contrast differs by at most1.33e-16 due to that coefficient/
constant rounding. Numerical mean-risk LPs use HiGHS1e-9feasibility tolerances;
independent endpoint comparisons use2e-8relative-or-absolute tolerance.
Those LP checks are not formal interval arithmetic certificates.

Main result:1,614batch sufficient,29feedback required,31no deterministic adaptive
half-width guarantee; all29have continuum batch optimum exactly1/2. Replay
gain over deterministic batch is net2/1,674cases (0.119pp); greedy adaptive also
succeeds in all29subset cases. This finding cannot support large operational
cost savings. The actual interface permits full-range retrieval, which is
separately measured by the operational benchmark. Five optional values in one
HTTP response must not be confused with five paid HTTP requests.

Internal AI analysis and independent code checking only. No paper or data were
sent to a human specialist; no external-human validation claim is made.
