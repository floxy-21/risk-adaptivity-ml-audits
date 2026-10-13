Classification and separation audit
===================================

Manuscript-ready proof: theorem_proof.tex
Executable independent examples: check_classification.py
Actual run output: classification_verification.json

From the repository root, run:
  python work/risk_adaptivity_revision/math/check_classification.py

Requires NumPy and SciPy. The recorded run used Python 3.12.14, NumPy 2.5.3,
SciPy 1.18.1, and scipy.optimize.linprog(method='highs'). Runtime was 10.754
seconds on the available host. The command overwrites its verification JSON,
including the actual runtime and source hash for that run; the JSON bytes
therefore are not expected to remain identical across executions.

Recorded result: 1,601 query fibers, obtained with 3,202 separately solved
minimum/maximum endpoint LPs, and 28 finite zero-sum games. All checks passed.
Maximum width discrepancy: 3.3306690738754696e-16.
Maximum endpoint primal residual: 2.220446049250313e-16.
Comparison tolerance: 2e-8 * max(1, abs(analytic width)).
This is floating-point numerical verification, not interval arithmetic.

The universal theorem is proved algebraically. The numerical program checks
the constructed examples and the finite games furnishing their lower bounds.
It does not numerically prove the universal statement or establish real-data
operational gains. It does not train or retune any forecasting model.

Important mathematical corrections to the proposed outline:
1. The nonconcavity converse needs only THREE coordinates, all queryable at
   unit cost, and a hard budget of two. No six-coordinate construction is needed.
2. For the K-family precision upper bound, capacity vertices do not suffice.
   Use the K interior-capacity records in the proof, each with one capacity
   below 1/K and all others above it. The program checks these rational records.
3. Upper semicontinuity of fiber width, not continuity, supplies hardest-record
   attainment. The proof does not assume continuity of the penalty at zero.
4. The risk order is sup_record E_random_seed, not E_random_seed sup_record.
5. The guarantee concerns sharp scalar terminal width under an execution-wise
   hard budget. It does not optimize expected requests until certification,
   point-reconstruction error, or multidimensional information diameter.
6. Compact convex F may include overlapping constraints and fixed heterogeneous
   costs, but the general theorem supplies no polynomial-time large-budget
   solver. The structured compact aggregate LP retains its narrower assumptions.

Historical priority is not established by this audit. Sion minimax, Jensen,
linear-programming duality, and local information diameter are established
tools and concepts requiring attribution in the manuscript.
