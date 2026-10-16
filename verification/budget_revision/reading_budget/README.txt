LEAST SUFFICIENT READING BUDGET — CURRENT REVISION
================================================
Analysis added 2026-10-14 after the shared-query analyses. This is a
post-analysis resource diagnostic, not an untouched confirmation.
No saved fine-query answers, error outcomes, query timings or model fits
are used. The target remains joint normalized width <=1/2.

Scope
-----
All fixed batches, all readout counts0..5, exact simplex model. The
minimum fixed budget remains exact among randomized fixed policies when
certainty is required. Adaptive minima are identified only at budgets0..2.
For larger budgets the exact minimum fixed batch is a sufficient fallback;
it is not asserted to be the optimal adaptive solution.

The method calculates a sufficient authorization level instead of requiring
that the source enforces a two-reading cap. In225 frozen geometries,
three fixed readouts are necessary and sufficient, whereas two adaptive
readouts are necessary and sufficient. This is an exact information-resource
comparison under the declared interface. It does not establish actual
deployment cost, API latency advantage, or binding source-access restrictions.
Measurement errors and capacity limits were studied elsewhere and remain
outside this exact-resource diagnostic. The measured API permits bulk.

Commands from the supplement root (after promotion to the final location)
------------------------------------------------------------------------
python -S work/risk_adaptivity_revision/joint_certification/reading_budget/reading_budget.py --output-dir outputs/reading_budget_external
python -S work/risk_adaptivity_revision/joint_certification/reading_budget/check_reading_budget.py --results outputs/reading_budget_external
python -S work/risk_adaptivity_revision/joint_certification/reading_budget/check_partition_general.py --output outputs/reading_budget_general.json

The default validates and processes only the279 bundled external blocks.
It must not be described as reproducing the819 original blocks.

For both panels, first complete the existing source-verified raw-data route:
python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --raw-dir PINNED_BLEM_CACHE --output-dir NEW_CHAIN_DIRECTORY

Then:
python -S work/risk_adaptivity_revision/joint_certification/reading_budget/reading_budget.py --chain-dir NEW_CHAIN_DIRECTORY --output-dir outputs/reading_budget_all
python -S work/risk_adaptivity_revision/joint_certification/reading_budget/check_reading_budget.py --chain-dir NEW_CHAIN_DIRECTORY --results outputs/reading_budget_all

Implementation
--------------
reading_budget.py imports the previously verified source-input binding,
not a frozen answer ledger. It recomputes exact coefficient normalizations,
enumerates all32 prefix batches, calculates two-reading covers, and checks
the O(R*n) longest-admissible-segment scan against enumeration.
check_reading_budget.py does not import that producer. It independently
computes a shortest-path partition and checks all32 batch widths from
feasible endpoint records. It verifies adaptive cover endpoint inequalities.
The source binding is shared; mathematical verification is separately
implemented. Independent here means separately written within this study,
not external human validation.
check_partition_general.py separately compares the actual general scan
function against all fixed batches on180 constructed rational instances,
using seed20261014, sizes2..10 and1..5 targets, and thresholds0,1/4,1/2,1.
It checks20440 batches, with constant target rows and repeated coefficients.

Outputs
-------
report.json: source hashes, system/cohort totals, fixed-budget histograms,
  declared protocol counts, code hash and runtime.
ledger.json: each block's coefficient digest, all fixed batch bounds,
  concrete least-cardinality batch, greedy scan batch, adaptive cover.
independent_check.json: exact equality checks, endpoint feasibility,
  source-bound hashes, checked output hashes and runtime.
proof.txt: mathematical justification and boundary conditions.

Original raw coefficient vectors are not exported. Existing source version
checks reject mismatched records. Only source-derived numerical bounds and
policy certificates are exported; the complete original raw source remains
on its documented separate route.
