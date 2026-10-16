EXACT COMPLETION OF THE RANDOMIZED-BATCH PRECISION COMPARATOR
Protocol date: 15 October 2026. Retrospective analysis, no new model fits.

Purpose
Close the 418 formerly open continuum batch-precision games under the same
uncapped exact-total simplex, ten two-prefix batches and half-width target.
All 1,098 blocks then have matching lower and upper precision bounds.
Do not apply these optima to capped or bounded-error feasible sets.

Inputs and chronology
inputs/precision_catalog.json is a byte-identical copy of the source-bound
full-panel precision catalog. source_binding.json records its hash and source
hash chain. It contains contrast coefficients and existing policies, not the
withheld fine-resolution answers. Each normalized row is reconstructed from
the saved binary64 contrast coefficients by the independent checker.
The original raw-source reconstruction is a separate provenance step; this
module does not claim to repeat it. Six pilot cases were selected as the
first formerly open ID in each source/system, before any outcome replay.

Methods
For a proposed mixture, failure of its precision lower guarantee requires
a set of failed batches carrying enough mixture probability. The producer
checks every inclusion-minimal such set. It branches over a failing contrast
for each batch, removing only componentwise dominated rows. Numerical LPs
propose exact rational simplex records or rational convex-combination bounds.
Only checked strict inequalities establish a failure record. A convex
combination of selected failure rows bounded above by one half in every
coordinate proves that branch infeasible. A complete tree therefore proves
a continuum cover. Matching feasible adversarial distributions prove the
upper bound. All inequalities and final probabilities are rational.

Primary standalone reproduction (from repository root)
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/complete_precision.py --selection all --output-dir outputs/precision_completion_replay
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/check_completion.py --results outputs/precision_completion_replay
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/test_rejection.py --results outputs/precision_completion_replay

The first command uses the bundled catalog by default. --plans can select
another pinned catalog. --seconds-per-case is a computation limit, not a
scientific tolerance. A time-limited or uncertified case remains UNRESOLVED
and retains the old policy/lower guarantee; no favored value is substituted.
The checker enforces the complete declared ID selection, checks all 1,024
failure masks for each mixture, and rejects incomplete branch covers.
The producer needs NumPy/SciPy; the verifier needs only Python's standard
library. LP feasibility tolerances are 1e-9, but certificate acceptance has
zero tolerance. Eight bounded corruption tests exercise rejection behavior.

Full-panel objective-matched challenger
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/refine_secondary.py --completed outputs/precision_completion_replay/report.json --output-dir outputs/precision_refined_replay
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/check_completion.py --results outputs/precision_refined_replay --completed outputs/precision_completion_replay/report.json

The primary precision value stays fixed. A coefficient-only secondary LP
minimizes worst expected joint width; since joint width is convex in the
record, its worst expectation on the simplex is attained at a pure profile.
Numerical lexicographic minimization of mixture coordinates uses a 1e-10
width-face allowance. Projection onto active precision equalities makes the
candidate probabilities rational, and the full-domain cover oracle verifies
precision again. Any new violating profile becomes another LP constraint.
At precision value zero, all mixtures are primary-optimal; the existing
coefficient-only mean-width policy is retained. Safe fallback, if needed,
retains the proved primary policy and is reported explicitly.
Primary precision optimality is exact. Secondary width optimality remains a
numerical LP refinement; no exact secondary-optimality theorem is asserted.

Only after the full policy file is frozen and its exact verifier passes:
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/replay_completed.py --results outputs/precision_refined_replay
python work/risk_adaptivity_revision/joint_certification/precision_completion_probe/check_recorded_replay.py --results outputs/precision_refined_replay

Recorded batch widths are used solely for evaluation, never mixture selection.
The replay records the frozen policy hash before reading those widths. It
reports exact expected success and paired outcome counts, strict and existing
1e-8 conventions, per-system results, and descriptive paired bootstrap
intervals using the unchanged 2,000 synchronized seven-day draws. An optimal
worst-record precision mixture need not maximize observed success.

Artifacts
all_418/report.json: complete rational primary witnesses for formerly open cases.
all_418/independent_check.json: source-coefficient and full-cover verification.
all_418/summary.json: full distributions, runtime/size diagnostics and join to
  all 225 adaptive-two/fixed-three blocks, including the three one-third cases.
refined_all/report.json: frozen 1,098-case refined policies and exact witnesses.
refined_all/independent_check.json: solver-free verification of every policy.
refined_all/recorded_replay_cases.json: inspectable per-block expected outcomes.
refined_all/recorded_replay_summary.json and recorded_replay_check.json:
  aggregate, paired and descriptive uncertainty results and their verification.

The new computation closes a comparator gap; it does not establish a new
field deployment, alter forecast accuracy, change the half-width requirement,
or convert reading counts into measured network or financial savings.
