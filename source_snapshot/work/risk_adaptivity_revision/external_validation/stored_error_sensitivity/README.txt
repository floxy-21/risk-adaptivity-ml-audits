Bounded stored-readout sensitivity and exact passing certificates

This directory contains two successive levels of evidence. The original frozen LP producer remains unchanged. Subsequent exact-rational certificates validate all 49 positive-allowance passing guarantees; they do not claim exact numerical optimal values or certify the nonpassing cases by themselves.

Commands (from the supplement root; no network or model fitting)
1. Original numerical sensitivity:
   python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/run_sensitivity.py
2. Regenerate the 49 passing rational certificates from the same selected supports:
   python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/build_exact_certificates.py
3. Verify those certificates using rational arithmetic without an LP solver:
   python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/check_exact_certificates.py
4. Separately written verification of their semantic matrices and inherited upper bounds:
   python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/INDEPENDENT_EXACT_CHECK.py
Paths inside these programs resolve relative to the scripts. The first command requires the frozen replay/geometry.json; the package runner therefore executes this stage before any replay command that rewrites that file. Use the package's main reproduction entry for the complete sequence.

Frozen inputs and outputs
Original inputs: ../replay/geometry.json, ../replay/half_witnesses.json, ../math/robust_two_query.py, PROTOCOL.txt and protocol_lock.json. The producer checks their hashes. Outputs: inputs.json (29 original/scaled coefficient vectors), witnesses.json (87 full numerical witnesses), case_ledger.csv and report.json. The original run took 58.68 seconds for 7,482 small LPs. No raw BLEM source, HPM API request, retraining or fine-response replay is required.
The exact follow-up outputs are exact_certificates/certificates.json, generation_report.json, verification.json and proof.tex. INDEPENDENT_EXACT_CHECKS.json records the separate 49-certificate check. The certificate bundle SHA-256 is 935e6c7e75900a012ca44b41955fbd3e28ce094a1479ea925e5300bbc9d235dd.

Model
All 29 previously identified external half-separation cases remain included. This is post-analysis sensitivity conditional on that subset, not a new prospectively selected replication. Normalize the exact retained total E=1. The 11-dimensional compact convex latent record has six nonnegative increments summing to one and five fixed internal readout errors bounded by delta. Query k returns its prefix sum plus its fixed error. Retained start/end errors are zero; relative-increment error alpha=0. Coefficients are positively scaled by their original range, not shifted. Initial width remains W0 at all levels, so the unchanged primary threshold W0/2 and half the new initial width coincide.
The fixed levels delta=0,0.001,0.01 are allowances per internal reading in units of block total. They are not measured device errors, fractions of the lifetime counter, manufacturer-certified physical tolerances, or an allowance for unknown native timestamps.

Results and evidence level
Delta     All cases   Numerically passing adaptive   Rational passing certificates
0         29          29                             Original exact half witnesses
0.001     29          27                             27
0.01      29          22                             22
No deterministic batch passed numerically at any level. All 29 remain in every denominator; no case was dropped or replaced. At delta=0.01 the passing counts for systems 1/2/7 are 2/2,12/14,8/13, and all six model pairs remain represented.
The two cases not certified at 0.001 and seven not certified at 0.01 now have separate exact lower witnesses in failure_diagnostics/. All five legal first queries and all four possible distinct second queries are covered, proving that no deterministic policy with at most two queries can guarantee the unchanged threshold in those cases. This conclusion follows from 180 exactly feasible indistinguishable endpoint pairs, not the absence of a passing certificate or a numerical tolerance. It does not assert randomized-adaptive impossibility. Verify with:
   python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/check_lower_witnesses.py --output lower_verification.json

Why the positive guarantees are now rigorous
The exact generator rebuilds each selected support LP using rational source coefficients. Floating-point LP multipliers are merely proposals. Rational arithmetic then checks their signs and adds an exact bounded-box correction for stationarity residuals. The resulting rational upper bound on the selected support's worst width is at most 1/2 in all 49 cases. The smallest strictly positive certified margin is
62690716363030944789827837795111/16676489784621688173380802655027200,
approximately 0.0037592273417659822 W0.
The separate checker reconstructs the constraint matrices, variable boxes and dual expressions semantically, without importing or running an LP solver. These are rigorous sufficient guarantees for the specified support-defined adaptive policy. They do not prove that its reported floating optimum is the exact optimal objective, nor certify an arbitrary floating-point online branching implementation.
The old exact-rational adverse-profile upper bound 1/2 transfers analytically to the enlarged feasible set: the old zero-error records remain feasible and each old observational fiber is included in its enlarged counterpart. An old failure cannot become success. The support guarantee and the two-successor theorem give the matching batch lower guarantee for every feasible latent record in the 49 passing cases. This establishes the half-success batch optimum there under the declared model.

Original numerical diagnostics (retained, not substituted for the exact checks)
LP primal/dual tolerance 1e-9; comparison tolerance 2e-8. Maximum primal feasibility residual 1.9096e-14, stationarity residual 5.3291e-15, absolute primal-dual gap 6.2172e-15. Zero-error adaptive/batch optima matched original rational values within 3.8858e-16/4.4409e-16. Sparse-support discrepancy was at most 1.8874e-15. The independently written error-eliminated formulation reproduced all 87 evaluations using 2,175 LPs (INDEPENDENT_REVIEW_CHECKS.json).

Interpretation
The passing and failing deterministic two-query cases are both resolved by exact certificates under the declared internal-readout allowances. Exact retained endpoints and no additional hourly cap remain conditions of this study. These findings do not calibrate HPM physical meter accuracy, overcome unknown native sample times, improve the measured bulk-retrieval baseline, establish monetary savings, or modify original replay outcomes.
