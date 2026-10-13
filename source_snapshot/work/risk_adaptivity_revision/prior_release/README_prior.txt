ONLINE RESOURCE 1: EXECUTABLE RESEARCH SUPPLEMENT
Article title: Exact Algorithms and Limits for Auditing Machine-Learning Forecasts with Aggregate Targets
Journal: Applied Intelligence (intended submission)
Author and corresponding author: Jishan Kapoor
Affiliation: Independent Researcher, Toronto M4Y 1C9, Canada
Correspondence: kapoorjishan19@gmail.com


Extract this ZIP. Run commands at its root with Python 3.12 and the versions in
outputs/requirements-study.txt installed in a separate environment.
The clean replay is verified on Windows. The retained historical development
checker uses Windows path conventions; cross-platform execution of every
optional historical route has not been established.

QUICK MATHEMATICAL CHECKS (no empirical traces parsed; all hashes checked)
  python work/reproduce_decision_revision.py --small

DEFAULT: SOURCE, CONFIRMATION, ORACLE, QUERY-ELIGIBILITY, PUBLIC CERTIFICATE GRID, EXACT TEX
  python work/reproduce_decision_revision.py

ALSO CHECK EVERY DEVELOPMENT CASE AND EVERY CONCENTRATION
  python work/reproduce_decision_revision.py --development

ALSO REPLAY THE PREVIOUS EXTERNAL EXPERIMENT
  python work/reproduce_decision_revision.py --legacy

REFIT THE NEW CONSUMER MODELS AND RERUN NEW ACQUISITION
  python work/reproduce_decision_revision.py --refit
This creates new fits/outcomes in an isolated directory and does not silently
replace the paper's saved outcomes. It uses bundled hourly source references.
The original 60-model fit is also supplied with its execution metadata.

WHAT DEFAULT REPRODUCTION DOES
Every supplied checksum is checked; a new isolated workspace is created. The
literal source subset is independently checked against every hourly reference,
every new acquisition trace is replayed with independent endpoints, query
scores/proposals, cost/stopping and aggregation, and all hindsight subsets are
enumerated again. For randomized-width traces the independent checker verifies
finite-game objectives, mixture moments and support; it does not reconstruct
the compact sampler's exact random draw. The sampler is supplied, and --refit
reruns its acquisition. Frozen report bytes needed by the manuscript builder are
restored only after retaining the fresh checks in the wrapper report. The
current manuscript must rebuild to exactly the supplied source SHA-256.
This is a fresh replay, not fresh model fitting or a new dependency installation.

QUERY ELIGIBILITY AND HISTORICAL BATCH ACCOUNTING
The default route also executes:
  python work/eligibility_review_20261011/check_review.py
This bounded command takes approximately 23 seconds on the reported host;
runtime depends on hardware and current load. It checks the exact-rational
zero-coefficient counterexample against frozen selectors and the hindsight
driver, then accounts for all saved stages in the earlier two-reading study:
44,442 base cases, 222,210 five-policy cases, 129,718 batches and 257,399
requested readings, plus 120 acquisition-API fixture calls. This verifies
query eligibility, per-block batch caps and payment accounting. It does not
rerun every historical policy optimization or replace the --legacy route.
Fresh results are retained in outputs/query_eligibility_review_replay.json
and its log; the command restores archived report bytes after retaining the
fresh checks. Under the default route these outputs reside in the new
work/dreplay_* workspace, and the wrapper also includes the review report.

POST HOC CONFIRMATION DIAGNOSIS (READ-ONLY WITH RESPECT TO STUDY INPUTS)
Two optional scripts summarize already computed confirmation trajectories:
  python work/eligibility_review_20261011/ml_diagnosis/read_only_diagnosis.py
  python work/eligibility_review_20261011/ml_diagnosis/divergence.py
Run at the root of a disposable extraction. They write diagnostics.json and
divergence.json in their own directory, replacing those descriptive reports.
They compare policy costs, query divergence, hindsight headroom and selected
surrogate scores; they do not fit, tune or rerun policies, select a new
endpoint, establish population calibration or create confirmation evidence.
These post hoc summaries are bundled separately from the frozen experiment.

REPRODUCTION OUTPUTS AND TIMING
Each command prints its new work/dreplay_* directory. The final report is
outputs/decision_revision_reproduction.json inside that directory. Per-step
logs and measured seconds are retained there. Original execution times are in
confirmation/run_result.json and independent_verification.json under
work/decision_revision. Default is a full scientific check, not a fast smoke test;
--development adds the 26,910-case, six-concentration development replay.
All case CSVs, traces, forecast archives, protocol versions, source manifests,
selection logs and reference values are bundled. MANIFEST.sha256 covers every
member except itself, and the current manuscript SHA is additionally pinned in
outputs/decision_release_manifest.json. Hardware-dependent timing values are
not expected to reproduce byte-for-byte.

RAW INPUT BOUNDARY
The 8.54 GB official LCL CSV and its ZIP are not redistributed here. Official
download and source hashes are in the retained external-source documentation.
The completed independent raw re-extraction scanned all 167,932,474 rows and
matched the selected literal-row stream; its report is
work/decision_revision/math/confirmation_source_check.json.
To rerun that full scan, place the verified full CSV at
work/external_deadline/source/lcl_raw/CC_LCL-FullData.csv and execute:
  python work/decision_revision/math/verify_confirmation_source.py --raw
Run this optional command in a disposable extraction: it writes a fresh report.
Default uses the bundled literal source subset and makes no fresh full-raw claim.

COMPLETE EXISTING CERTIFICATE GRID (about 3 seconds separately)
  python work/certificate_grid_review/summarize_certificates.py --source public --output-dir outputs/certificate_grid_replay
The default reproducer runs this command in its isolated copy and checks every
generated CSV/table checksum against the archived public results. It replays
60,264 paired/separate comparisons across all 216 existing Portugal/household
scenario cells, including both access regimes and exact/1%/5% totals. It checks
matched information, reference enclosure, interval nesting, saved numerical
decisions, the full Cartesian grid and zero separate-only certificates.
The archived full 34-series summary additionally includes the three counter
series: 66,096 comparisons, 324 scenario cells. Its full table and verification
are included and hash-checked, but are NOT recomputed by default because detailed
BLEM endpoints are omitted under the existing redistribution policy. See
work/certificate_grid_review/README.txt and outputs/REPRODUCE.txt for the existing
raw-regeneration route and --source full --input-root usage. No raw BLEM records
or full BLEM per-case endpoints are added by this revision. These are descriptive
repeated-scenario counts, not new independent experiments, and the separate-loss
certificate comparator is not the strongest point-imputation/acquisition policy.

EXPERIMENT CHRONOLOGY AND INTERPRETATION
The original two-query 15% B80 target failed and is retained. All existing London
validation cases were used for development, including the finite concentration
grid; they are not presented as fresh confirmation. The next 20 consumers were
chosen from training eligibility alone, and the complete new protocol, selected
concentration and code hashes were frozen before their forecasting fits.
The new empirical efficiency endpoint was motivated by an exhaustive development
oracle diagnosis. The unrun alternative 15%-mean proposal remains archived.
All comparator efficiencies are reported; near-minimum cost does not imply a
new-policy advantage when a simple baseline is equally efficient. The oracle
uses hidden values for an explicitly clairvoyant lower bound, never for selecting
an executable query. Same-source consumer confirmation is not a production trial.

HISTORICAL EVIDENCE
The preceding release's scientific members are carried forward byte-for-byte
except its current-paper source and entry README/checksum list. See
work/decision_revision/release_ancestry.json. The --legacy option invokes its
reproducer with the appropriate archived manuscript. Older standalone commands
describe their historical targets, not this complete new revision. No prior full
suite is represented as newly executed by default. All checks are separately
implemented within this AI-assisted study, not external journal peer review.
