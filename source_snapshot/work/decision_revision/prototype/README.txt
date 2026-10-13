DEVELOPMENT-ONLY DECISION-DIRECTED QUERY DIAGNOSTIC

Purpose
The existing batch optimizer minimizes worst residual comparison width. The
practical endpoint is instead the number of observations needed for a strict
paired-loss sign certificate. This additive diagnostic evaluates a different,
explicit surrogate objective without altering any frozen paper experiment.

Policy
At each stage, assign independent uniform distributions to the residual
nonnegative simplices specified by the currently visible readings and exact
block totals. If a block has m unknown coordinates and residual total E,
querying coordinate i has X_i/E ~ Beta(1,m-1). Its post-query comparison
endpoints are affine functions of X_i. Integrating the two disjoint sign events
gives the exact one-query certificate probability under this surrogate prior.
Choose the largest probability; break ties by minimum worst residual width,
then coordinate index. Observe one reading, apply exact-total closure and stop
when the existing numerical certificate test passes. Repeat up to six readings.

The scoring rule uses exact sign inequalities. The executable stopping rule
retains the prior benchmark's floating-point tolerance. Probability scoring
does not claim a calibrated real-data event probability or optimize total
stopping cost. Priors affect query selection only; certificates still cover all
nonnegative completions consistent with the actual available observations.

Fair comparisons
Exact-width and greedy-width policies both acquire one coordinate per step and
use the same deterministic index tie rule. These policies are mathematically
identical at one query, and the program asserts identical realized traces.
Hara and uniform also acquire one coordinate per step, using reproducible
case-specific random streams. The Hara policy retains the benchmark's frozen
Ridge/validation-error Gaussian proposal and aggregate conditioning.
All policies receive the same observations, totals and strict stopping rule.
No query-selector function accepts the hidden reference record.

Protocol and scope
The pilot is the first 100 chronologically ordered cases of each of the first
three household IDs. The full run includes every existing validation case,
all model pairs and all three fixed mask seeds. The pilot and full run use
identical policy code; there are no outcome-based feature or prior choices.
Only validation reference rows are retained after loading the shared frozen
reference CSV. Test cases are never evaluated. Both pilot and full panel are
development evidence, not untouched external confirmation. This experiment
cannot retrospectively satisfy or replace the old prespecified 15% B80 test.

Commands (workspace root, pinned study environment)
work/review-env/Scripts/python.exe work/decision_revision/prototype/check.py
work/review-env/Scripts/python.exe work/decision_revision/prototype/run.py --pilot
work/review-env/Scripts/python.exe work/decision_revision/prototype/run.py

Run directories must not already exist, to prevent accidental overwriting.
Check reports and outputs are additive. policy.py, run.py and input hashes
are captured before each run in its pre_run_manifest.json.

Outputs
cases.csv: every original case_id and policy's stopping cost and status.
trajectories.jsonl: every chosen coordinate, revealed value and resulting bound.
coverage_curves.csv: household-macro conditional coverage at budgets 0 through 6.
summary.json: all-case and learned-pair B80 and mean-request summaries.

The executable checks reference enclosure and strict-sign correctness at every
stage, query eligibility and information monotonicity. The check.py diagnostic
independently evaluates post-query simplex vertices and uniform marginal
quantiles. Neither check is an external reproduction of forecast training.
