FEEDBACK TRIAGE: POST-ANALYSIS OF THE UNCHANGED PRIMARY COUNTER STUDY

Purpose
=======
Decide before requesting any internal register whether two timestamps can be
selected together, whether a feedback-dependent second timestamp is necessary
for a guaranteed half-width certificate, or whether the deterministic two-query
guarantee is unavailable. This diagnostic retains all 4,914 original cases,
the same forecast vectors, the same five available internal register queries,
the same two-query budget, and the original terminal-width <= 0.5 W0 threshold.
It does not modify the frozen protocol or the failed 10% prevalence screen.

Results
=======
Batch sufficient:              4,371 / 4,914 (88.94994%)
Feedback essential:              290 / 4,914 ( 5.90151%)
Deterministic guarantee absent:   253 / 4,914 ( 5.14856%)

Every feedback-essential case has exact full-continuum randomized-batch
precision success 1/2, while the deterministic adaptive policy guarantees
success. These 290 exhaust the cases where the deterministic adaptive policy
changes feasibility of the full precision guarantee. They were not selected
using the withheld fine-resolution consumption values.

The finite adverse-profile upper bound alone is not a full-continuum optimum.
Equality at 1/2 uses the constructive two-batch cover, which guarantees at least
1/2 success for every feasible completion, and the adverse weights, which
limit every batch mixture to at most 1/2. For the 253 other cases the finite
profile bounds (5 cases at 1/4, 61 at 1/3, 187 at 1/2) remain upper bounds.

Executable recommendations
==========================
recommendations.json gives one prescription for every case:
  batch: retrieve the listed two internal hour boundaries together;
  adaptive: retrieve the listed first boundary, compute the prefix fraction t,
            then choose the second boundary minimizing alpha*t + beta*(1-t),
            breaking ties by smaller boundary index;
  escalate: the stated deterministic two-reading guarantee is not available.
            A larger budget or different precision is outside this experiment.

All boundaries are hours after the start of that case's six-hour block.
The recommendation construction reads forecast geometry only. It completes
before any replay file is opened. The original 290 adaptive first boundaries
match these exact-rational recommendations.

Practical interpretation
========================
If a service supports sending two selected register requests in one batch,
the batch-sufficient class can obtain the same precision guarantee without
waiting for an intermediate answer. Feedback is required on the 290 cases
for which its guarantee changes feasibility. This is a protocol-level
information-round distinction; retrieval latency, cash expenditure and an
actual deployed retrieval service are not measured. Every executed policy
still retrieves two readings.

An optional exploratory hybrid uses the original deterministic batch whenever
it guarantees precision and otherwise uses the original adaptive policy.
It batches 4,371 cases, uses feedback on 543, and retains 98.63655% recorded
precision success over all 4,914 cases. In fact its half-width success
indicator agrees with the original adaptive policy for every feasible
completion: both guarantee success in the batch-sufficient cases, and the
policies are identical in all other cases. The script verifies the original
implemented first-query envelope as well as the independent optimum before
making this statement. Relative mean width rises from
0.18590243 (adaptive) to 0.18723647 (hybrid); winner certification decreases
from 50.48840% to 50.06105%. Thus this diagnostic concerns choosing when
feedback is needed for precision, not universal superiority across outcomes.
The main guarantee-based prescription instead flags the 253 unresolved cases
for escalation and makes no claim about an optimal subunit adaptive success
probability for them.

Files
=====
analyze.py: independent exact-rational reconstruction from original serialized
  coefficient vectors; all batch maxima, adaptive envelopes and finite games.
case_ledger.csv: case classes, exact ratios, finite-game binary matrix,
  adverse weights, matching finite-game batch weights, original query indices.
recommendations.json: executable geometry-only prescriptions.
report.json: complete counts, meter/pair/phase results, replay comparisons,
  hashes, numerical discrepancies and limitations.
policy_summary.csv: observed policy outcomes by class and meter.
batch_upper_distribution.csv: exact finite-game bound distribution by class.
verify_bundled.py: checks bundled counts, exact finite-game primal/dual
  certificates and the 290 adaptive envelopes/constructive half covers.
verification.json: actual output of that bundled checker.

Reproduction
============
From the extracted supplement root, first regenerate the existing counter
geometry/replay from the pinned original raw-source files and frozen forecasts:

  python work/risk_adaptivity_revision/counter_adaptive/reproduce_counter.py

For --panel all (the default), the updated wrapper also runs this diagnostic
and its bundled checker in its new output directory. It does not refit models.

To rerun only this diagnostic on an already regenerated all-panel result:

  python work/risk_adaptivity_revision/counter_adaptive/feedback_triage/analyze.py --geometry PATH/results/geometry.json --replay PATH/results/replay_cases.csv --output-dir NEW_TRIAGE_DIRECTORY

To check only the bundled certificates without raw downloads:

  python work/risk_adaptivity_revision/counter_adaptive/feedback_triage/verify_bundled.py --output NEW_VERIFICATION_REPORT.json

Expected counts are stated above. Timings and input path strings may differ.
The executed geometry analysis took approximately 34 seconds on the study
machine; this is a diagnostic script runtime, not a retrieval latency result.
The independent bundled checker took approximately five seconds.

Verification precision
======================
Fractions are exact rational representations of serialized binary64 original
forecast coefficients. The source forecast values are not exact physical
truths or a formal enclosure of every numerical model-fitting operation.
The independent analysis checked 49,140 batch columns and 24,570 first-query
envelopes. Each of 4,914 finite games has exact rational primal/dual equality.
Maximum discrepancies from the archived normalized geometry were 2.724e-16
for vertex widths and 2.360e-16 for adaptive values; all upper bounds and
classifications agreed. No original tie choice was nonoptimal in exact
arithmetic, and no class optimum was within 1e-8 of the primary threshold.

Study limitations
=================
The triage and hybrid were added after the primary analysis, and are labeled
post-analysis. The inference applies to the declared intraday counter-access
protocol, not the historical complete-archive regime. The same three meters
and six model pairs are reused; cases are dependent. The original 290/4,914
prevalence result remains 5.90%, below the prespecified 10% screen. This
diagnostic adds an operational decision rule and verifies exhaustive
classification under that protocol; it does not increase prevalence.
