Independent verifier for the constructed two-target boundary family
=================================================================

From the repository workspace, run the full exact-rational plus SciPy check:

  python work/risk_adaptivity_revision/two_target_boundary/verify_boundary.py --output outputs/two_target_lp.json

Run the standard-library-only Fraction certificates:

  python -S work/risk_adaptivity_revision/two_target_boundary/verify_boundary.py --solver-free --output outputs/two_target_exact.json

The optional --m argument accepts family sizes >=3; defaults are 3 5 10.
The --output argument is required. Exact fractions are numerator/denominator
strings in JSON. Both modes write status: PASS only after every assertion has
passed. They include source_sha256 and proof_input_sha256; the complete proof
input and its canonical JSON hash encoding are included for audit/replay.

The exact mode enumerates rational vertices of each observed (t,u,v) fiber,
then adds independent cube-coordinate extrema. For every adverse record it
checks all query sets of sizes zero, one, and two, for all three targets.
It checks initial widths, the adaptive branch formulas, both scalar half-width
guarantees, the stronger scalar guarantees throughout the threshold band, and
both three-query fixed guarantees. An exact interval sweep proves continuum
coverage at the included lower threshold endpoint. A sparse batch mixture
strictly beats 1/m at the excluded upper endpoint, verifying the necessity
of the open upper boundary.

The full mode independently optimizes all m+3 coordinates with SciPy/HiGHS.
Each adverse fiber has separate minimum and maximum LPs for every target.
Whole-branch and whole-interval LPs duplicate the endpoint vector and impose
equality of queried answers, maximizing the target difference across the
entire answer interval. These maxima are not obtained by sampling a grid.

For m=3,5,10 the full run solves 7,131 LPs: 18 initial endpoint LPs, 7,026
adverse-fiber endpoint LPs, 54 whole-branch width LPs, and 33 whole-interval
fixed-query width LPs. Counts in the report are recorded from actual calls.
Absolute comparison tolerance is 1e-7; HiGHS primal and dual feasibility
tolerances are each 1e-9. The report records maximum observed discrepancies.

This verifies a mathematical construction. It does not validate empirical
application claims, and the construction should not be presented as an
empirical application study.

Generate the standalone SVG summary without third-party dependencies:
  python -S work/risk_adaptivity_revision/two_target_boundary/make_summary_svg.py --output outputs/precision_boundary_summary.svg
The visual separates the constructed family from the existing meter instance
certificates and preserves their different scopes.
