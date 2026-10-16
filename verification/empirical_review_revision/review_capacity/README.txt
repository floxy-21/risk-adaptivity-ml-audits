PAIRED CAPACITY ATTRIBUTION

Question: separate exclusion by an illustrative capacity rule from the change
in assurance caused by adding that information to the same retained block.
The normalized target remains W_r <= W_r0/2, using the UNCAPPED initial width.
The original 225 reading-saving blocks are retained as the reference cohort.

Full source-bound reproduction (after regenerating the pinned full chain):
python work/risk_adaptivity_revision/joint_certification/empirical_capacity.py --plans CHAIN/shared/empirical_plans.json --cohort all --output-dir capacity_new
python work/risk_adaptivity_revision/joint_certification/reading_budget/reading_budget.py --chain-dir CHAIN --output-dir budgets_new
python work/risk_adaptivity_revision/joint_certification/review_capacity/analyze_capacity.py --chain-dir CHAIN --capacity-dir capacity_new --budget-dir budgets_new --output-dir capacity_attribution_new
python work/risk_adaptivity_revision/joint_certification/empirical_capacity_check.py --results-dir capacity_new --output capacity_endpoint_check.json

The default producer uses the bundled external source inputs and its frozen
capacity and budget results. It writes new outputs without changing inputs:
python work/risk_adaptivity_revision/joint_certification/review_capacity/analyze_capacity.py --output-dir capacity_external_new
The separate checker documents its invocation in its --help output.

Method for a fixed query set
For a segment of length m with ordered coefficients a_1 <= ... <= a_m,
the maximum-minus-minimum contrast at segment mass t has consecutive slopes
  a_m-a_1, a_(m-1)-a_2, ..., a_1-a_m.
Each piece has mass length h, where h is the normalized coordinate cap.
The width is concave in t. To maximize the sum of segment widths subject to
their masses summing to one, take the largest available marginal slopes.
Slopes within each segment are descending, so this allocation respects each
segment's prefix order. For h=1/2 or h=1/3, exactly 1/h pieces are needed.
The width for one contrast is h times their sum. Maximizing over contrasts
gives the worst joint width. Enumerating all32 prefix sets gives the exact
minimum fixed budget, including zero and one readings.

Arithmetic and scope
Fixed bounds use exact fractions of the source binary64 coefficients.
Capped adaptive plans use the existing piecewise-linear floating-point solver
with tolerance1e-8, separately checked by endpoint LPs. Near-threshold cases
are listed; no exact rational adaptive claim is inferred from that tolerance.
Compatibility is joined from recorded profiles only AFTER planning. Cap
values are illustrative information assumptions, not device specifications.

Outputs
ledger.json supplies every block/cap, all32 fixed bounds, minimum fixed batch,
uncapped and capped guarantee classifications, and recorded compatibility.
report.json gives source/system transition tables and budget histograms on
identical compatible subsets. Excluded original savings cases are separate
from compatible cases that become fixed-certifiable. New adaptive-only cases
that were previously unguaranteed are also separate.
