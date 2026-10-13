Frozen randomized holdout audit

Default independent replay (no optimization):
  python work/randomized_holdout_review/verify_holdout.py
This checker uses only Python standard libraries, NumPy and pandas. It
does not import holdout.py or the recovery/LP implementations. It verifies
pinned source/result hashes; reconstructs all masks, forecast copies,
closure, coefficients and totals; rebuilds posterior intervals and strict
certification decisions; checks supported-query eligibility and budgets;
and checks saved primary dual bounds against reconstructed game matrices.
It writes independent_verification.json in the current copied audit tree.
Use an isolated reproduction tree to preserve the archived report.

Additional same-implementation evaluation replay:
  python work/randomized_holdout_review/holdout.py verify
This recomputes all saved CSV evaluations with the original implementation
and writes verification.json. It is not an independent implementation.

Optional full rerun: copy protocol.txt and holdout.py into a fresh tree
under work/randomized_holdout_review/, preserve the source paths listed
in prepared.json and outputs/energy_rank_bounds.py, then run, in order:
  python work/randomized_holdout_review/holdout.py prepare
  python work/randomized_holdout_review/holdout.py select
  python work/randomized_holdout_review/holdout.py evaluate
Each phase refuses to overwrite its frozen output. Python packages for
generation are NumPy, pandas, SciPy, scikit-learn and threadpoolctl.
The optional full rerun will produce different timestamps and timing data;
these are not numerical-result discrepancies. No model training occurs.

Selection: the preparation process reads complete targets only to form
masked observations and the declared exact totals. The selection process
reads the resulting selection-only archive; hidden individual values and
realized outcome metrics are not arguments to solve_game/refine/compact.
The secondary criterion was frozen before outcomes. The cohort's first
schema/row was inspected before freezing, as disclosed in protocol.txt.
The forecast archive was already used in the manuscript's deterministic
consumer replication. Do not describe this audit as a new independent
data source or a prospectively preregistered study.

Main randomized CSV columns denote barycenter-refined policies. Columns
and separate CSV files marked original_primary are contextual results
for the original HiGHS primary optimizer. All 19,260 cases are retained.
Widths in cohort_summary are macro means of each consumer's ratios;
certification and query means also weight each consumer equally. Positive
and all-case strata are both saved. Floating-point checks do not establish
exact arithmetic certification of the LP solutions.
