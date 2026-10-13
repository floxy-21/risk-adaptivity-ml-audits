HARDEST COMPLETIONS FOR THE EXISTING COMPACT RANDOMIZED RECOVERY LP

Run from the repository/supplement root:
  python work/risk_adaptivity_revision/dual/verify_dual.py

Optional output location, without replacing archived numerical reports:
  python work/risk_adaptivity_revision/dual/verify_dual.py --output-dir work/dual_recheck

Dependencies: NumPy and SciPy; recorded versions appear in results/verification.json.
No forecasts are fitted, no hidden empirical targets are consulted, and no
historical scientific source file or empirical result is modified.

Inputs are the existing 42 compact-verification instances, four archived sharp
examples, and all 28 frozen scaling instances, plus six declared edge cases.
The scaling archive's existing enumeration-eligibility rule is retained for
the 12 small scaling instances. All 42 small cases, four sharp cases, and six
edge cases are also independently enumerated. Enumeration includes every
coordinate subset from size zero to the hard budget, even full-block/redundant
queries. This deliberately differs from the production oracle's reduced set.

dual_certificate.py exposes solve_with_dual_completion(coefficients, energies,
budget). It captures scenario-row dual multipliers from the historical compact
LP without editing that solver. The existing pricing_oracle function is loaded
verbatim by its Python syntax tree, avoiding unrelated empirical-data imports;
both its containing file and exact function source are hashed in the outputs.
Only that named top-level function is executed. No new pricing rule is used.

The implementation's redundant nonnegativity bounds on block epigraphs permit
dual mass deficits. These are completed at the lowest-index coordinate. Any
tiny negative multiplier or excess caused by floating-point arithmetic is
recorded before correction. The returned record has nonnegative coordinates
and each exact residual total, to the stated numerical tolerance.

The LP feasibility tolerances are 1e-9. Verification accepts discrepancies up
to 1e-8 times max(1, initial worst-case width) for objectives, and 1e-8 times
max(1, block total) for mass constraints. Raw discrepancies and corrections are
reported; these are floating-point checks, not outward-rounded proof objects.

Outputs:
  results/dual_completions.json: full original-order y*, raw dual multipliers,
    residual totals, explicit correction trace, pricing minimizer, LP residuals,
    and exhaustive minima where enumerated.
  results/summary.csv: one numerical summary per case.
  results/verification.json: counts, maxima, versions, source/output hashes.
  adaptive_dual_proof.tex: theorem, transcript proof, and numerical explanation.

To reproduce the paired computational comparison from the existing saved runs:
  python work/risk_adaptivity_revision/dual/summarize_solver_comparison.py
This checks the CSV against the underlying JSON reports, and produces all 12
compact/finite pairs in solver_comparison/paired_solver_results.csv and a TeX
table. The measurements are not rerun or selected by which method was faster.
Compact includes compilation of its executable policy; finite does not.
Absolute peak memory includes Python and dependencies. Each timing is a single
archived run, so these data should not be treated as a stable speedup estimate.

The theorem concerns minimax expected terminal sharp width under a hard budget.
It does not optimize expected requests until a winner is certified, and it
does not change or reinterpret any empirical acquisition-saving percentage.
