SCALAR/JOINT MECHANISM AND ABSOLUTE-PRECISION DIAGNOSTIC

This folder addresses two reviewer questions using the existing frozen
forecasts, exact retained counter endpoints, and original training calendars.
PROTOCOL.json was saved before the floor outcomes were computed. Its primary
floor and complete grid are retained, including unfavorable sensitivity.
This is a retrospective diagnostic, not a new confirmatory cohort or refit.

ENTRY POINTS (from the repository root; Python 3.11+ standard library only)

DEFAULT, ALL 1,098 BLOCKS, WITHOUT RAW BLEM FILES

python work/risk_adaptivity_revision/joint_certification/review_mechanism/analyze.py --output-dir RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/check.py --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/check_training.py --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/diagnose_floor.py --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/decision_plan.py --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/decision_plan.py --results RESULTS --verify-only

This route checks the pinned frozen_inputs.json, recomputes all 1,098 policy
instances and all 225-case mechanism diagnostics, and verifies their rational
plans. It reconstructs external training moments from bundled decimal counter
records. Original BLEM moments are source-linked saved inputs: the default
checks their frozen means/counts and arithmetic use but does not claim a fresh
raw training-data reconstruction. No optimizer result is taken as a verdict.

FULL SOURCE/TRAINING RECONSTRUCTION

First produce a successful both-source provenance chain with the documented
joint_certification/provenance_chain/run_chain.py command. Set CHAIN to that
run's output directory; the chain must include its original_raw/prepared
source reconstruction. This diagnostic refuses a mismatched source chain.

python work/risk_adaptivity_revision/joint_certification/review_mechanism/analyze.py --chain-dir CHAIN --output-dir RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/check.py --chain-dir CHAIN --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/check_training.py --chain-dir CHAIN --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/diagnose_floor.py --results RESULTS
python work/risk_adaptivity_revision/joint_certification/review_mechanism/decision_plan.py --results RESULTS

The packaged executed/ results are the actual full 1,098-block run. The
producer takes about 45 seconds and the independent policy checker about
140 seconds on the development machine. Training checking takes seconds.
Timing is descriptive and includes rational computations, not forecasting.

OUTPUTS AND CHECKS

ledger.json: every block, six scalar budgets, deletion-binding rows, exact
initial loss widths, minimum obstructing contrast subsets, and all seven
floor plans, closed adaptive branch covers, and fixed minima.
report.json: source, cohort and system summaries, input hashes, provenance,
and source hash. Quantiles use linear interpolation at (n-1)*p.
training_scales.json: exact training-day membership, first and second
moments, sequence hashes, and agreement with frozen fitting metadata.
independent_check.json: separate shortest-path minima, exhaustive 32-batch
checks, exact first-answer cell probes, and branch endpoint inequalities.
training_independent_check.json: independently reconstructs BLEM training
values from integer counter endpoints (rather than the producer hourly CSV),
and external values from decimal cumulative records; checks exact moments.
floor_assurance_diagnostic.json: distinguishes preserved adaptive assurance
from continued need for feedback and verifies all-floor budget monotonicity.
decision_plan.json: one concrete fixed-or-adaptive acquisition plan for each
of the original 57 external qualifying blocks under the primary floor.
decision_plan_check.json: direct exact inequality and minimum fixed-budget
verification for all 57 plans; 70 selected readings versus88 fixed readings.

INTERPRETATION

191/225 original saving cases isolate a shared-budget obstruction: every
scalar fixed budget is <=2, but the six-contrast fixed minimum is3. Of these,
168 already have a two-contrast obstruction and23 require at least3 contrasts.
The other34 cases include a scalar obstruction. 188/222 matched-half cases
are joint-only. The full case ledger keeps these subsets distinct.

The primary floor epsilon=.01*M2 uses training hourly RMS squared, NOT squared
training mean and NOT one-percent measurement noise. The MSE contrast has
kWh^2 units: E(kWh)*range(2*(b-a)/6)(kWh). Both E and predictions are available
before optional queries; M2 uses only the actual training-eligible days.

All225/225 original saving blocks remain assured with at most2 readings,
including57/57 external. Under the absolute floor39 external blocks become
fixed-certifiable:15 at budget0,14 at1,10 at2. Eighteen still require
adaptive2 versus fixed3. This is simplified acquisition, not lost assurance.
The fixed-or-adaptive planner needs70 readings on this unchanged57-case
cohort, versus88 under minimum fixed acquisition (20.45% fewer). The complete
external panel remains358 versus378 (5.29% fewer). Both denominators and the
different scopes are retained.
The all-source diagnostic preserves all counts rather than redefining the
denominator to the surviving subset. No physical noise, capacity, financial
threshold, or deployed retrieval restriction is inferred from this analysis.

Individual deletion binding is not a unique active-constraint definition:
redundant constraints can require a joint budget without any individually
binding row. We report69 such saving blocks and provide all six raw widths
for all225, rather than discard them from the scale diagnostics.
