General scalar-certificate LP verification
Author: Jishan Kapoor, independent researcher, Toronto, Canada
Corresponding email: kapoorjishan19@gmail.com

From the project/supplement root:
  python work/risk_adaptivity_revision/general/check_general_lp.py

Requirements: Python3.12, NumPy2.5.3, SciPy1.18.1 (tested versions).
Output: work/risk_adaptivity_revision/general/verification.json
Runtime: approximately1second of solver work on the development host, plus
Python/SciPy startup. Timings are a single run, not a speed benchmark.

The code defines six constructed compact polytopes and all legal two-coordinate
batches. It produces common hardest records, verifies every batch's sharp width
at those records, extracts dual batch weights, and verifies their worst mean
width with a separate LP. It also computes and checks the deterministic
two-query LP for every first coordinate. The triangle has expected-width value
0.5 and first-coordinate deterministic worst-width values0.5,1,1.

Checks are floating-point with explicit1e-8 assertion tolerance. Numerical
agreement does not replace the proofs. No real forecasting data, training run,
or operational acquisition benefit is claimed by these constructed examples.
The output includes execution time, which is naturally nondeterministic; compare
scientific values and residual checks rather than requiring a new run's JSON
to have the identical byte hash.
