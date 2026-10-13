BOUNDED-UNCERTAINTY THEORY INVESTIGATION

Scope: theoretical extension, constructed prototype verification, and
illustrative cap sensitivity using frozen forecast coefficients. No
external person was contacted. No human validation or physical meter
specification validation is claimed by these files.

Files
  helly_precision_theorem.tex: rigorous proposed two-stage guarantee and
      sharpness connection to the manuscript's existing K-family.
  measurement_model.txt: convex fixed-error lifting, relative increment
      model, quantization caveats, numerical sizes and replay scope.
  HELly_REFERENCE.txt: verified classical finite-Helly ingredient.
  robust_two_query.py: reusable small-polytope LP prototype.
  prototype_checks.json: actual constructed-run outputs.

Executed command from the project root
  work/review-env/Scripts/python.exe work/risk_adaptivity_revision/external_validation/math/robust_two_query.py

The executed checks cover 18 constructed cases: the known three-coordinate
example, five exact/noisy meter sensitivities, and twelve coupled boxes with
arbitrary scalar linear readouts (seed 20261012). The known exact cases
recover A=rho=0.5 and D=1. The best pair/singleton of successor actions agrees
with the full successor family on all 18 cases, with maximum discrepancy
3.9968028886505635e-15. LP feasibility tolerances are 1e-9; comparisons use
2e-8. These are floating-point checks, not exact rational certificates.

The prototype exports feasible hardest-record LP solutions and numerical
batch multipliers, and recomputes each batch's width at the hardest record.
It does not independently reconstruct a symbolic proof from those floats.
Generic polytope theorem proofs supply the mathematical guarantee.

Important conclusions
  - The two-query 1/2 batch floor does not depend on the exact-total segment
    formula. Convex conditional failure sets and finite Helly extend it to
    any compact convex latent model with scalar exact readouts.
  - The first-stage answer-dimension r version gives 1/(r+1), sharp by the
    already proved K-family. The first stage must be a fixed linear map.
  - Bounded fixed stored errors can be latent coordinates. This is not a
    theorem for an adversary choosing new errors after seeing query seeds.
  - Class1 is not a bound on lifetime cumulative error. Its applicability
    to interval errors must be sourced or called a conditional sensitivity.
  - Exact float quantization is nonconvex; a bounded-error model is a
    conservative convex relaxation with a corresponding scope of optimality.
  - Coefficient centering is invalid when totals are uncertain. Preserve
    original c coefficients; positive scalar rescaling is permitted.
  - Nonzero uncertainty destroys the half-width guarantee in the exact
    boundary example; no claim that all old data cases survive is justified.
    External cases must be evaluated under their fixed uncertainty protocol.

ILLUSTRATIVE CAP SENSITIVITY

All 290 original feedback-required cases were frozen before cap outcomes;
the protocol, selection IDs and source hashes are in
CAP_SENSITIVITY_PROTOCOL.txt and cap_sensitivity_manifest.json. The cap
scenarios E/2 and E/3 are assumptions, not inferred physical specifications.
The absolute target 0.5 old W0 is distinguished from the different target
0.5 new capped W0. No case is dropped based on cap compatibility.

Recommended bundled entry command (standard-library Python only):
  python work/risk_adaptivity_revision/external_validation/math/check_cap_package.py

This uses cap_sensitivity_coefficients.json (290 frozen contrast vectors,
exact binary64 fractions), cap_sensitivity_bundled_cases.csv and
cap_sensitivity_witnesses.json. It needs no private geometry or raw meter
files. Positive E cancels in the relative-cap calculation. It recomputes
all 1,740 case/scenario/threshold rows, 23,780 feasible-profile checks,
finite-game primal/dual bounds, and all-record lower-cover certificates.
The executed run took 53.45 seconds and passed. Output:
cap_bundled_check.json, containing input/source hashes and check scope.
This is coefficient replay, not raw-data recovery or forecast refitting.

Full LP comparison command (requires original geometry files identified
and hashed by the manifest; NumPy and SciPy):
  python work/risk_adaptivity_revision/external_validation/math/run_cap_sensitivity.py

The executed run took 134.45 seconds. It independently compares exact
oracles against all ten batch and all five first-query generic LPs for
each case/scenario. Maximum discrepancies: batch 6.11e-16, adaptive
4.45e-16, selected terminal fibers 1.39e-16. It also checks 91 arbitrary-n
rational instances, with 16 independently checked via general LPs.
Results: cap_sensitivity_report.json and cap_sensitivity_boundaries.json.
No tolerance-near threshold classifications arose; classifications are
exact rational. Finite adverse-profile upper bounds are not asserted to
be exact full-continuum optima without the separate matching lower cover.

Raw recorded-trace compatibility command (requires original BLEM files):
  python work/risk_adaptivity_revision/external_validation/math/check_cap_trace_compatibility.py --data-dir work

This separate post-geometry check reads exact integer-register increments,
retains all 290 cases, and exports compatibility flags, not raw increments.
Run time 3.73 seconds; cap_trace_compatibility.json and
cap_trace_compatibility_cases.csv. E/2 excludes 8/290 recorded cases
(meter counts 1/0/7); E/3 excludes 57/290 (11/8/38). The corresponding
distinct-block counts are 8/228 and 48/228. Capped guarantees do not cover
an excluded trace. This diagnostic does not validate either cap as a
physical operating bound.

With the fixed absolute target, feedback remains necessary in 8 cases
under E/2 and zero under E/3. With half the new initial width it remains
necessary in 33 cases under E/2 and zero under E/3. All asserted half
optima have independently checked continuum lower and finite upper
certificates. Full counts and exact cases remain in the ledgers.

Distributed-package note: cap_sensitivity_bundled_cases.csv omits the E,
old_W0 and new_W0 fields from the full local ledger. All dimensionless
exact results are retained. The full cap_sensitivity_cases.csv and original
geometry files belong only to the raw-source regeneration route.

After full raw-route regeneration, refresh the distributable inputs with:
  python work/risk_adaptivity_revision/external_validation/math/export_cap_bundle.py
This verifies original geometry source hashes, exports the 290 contrast
vectors and removes raw-total fields from the dimensionless ledger.
