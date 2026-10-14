ASSURANCE FEASIBILITY WITH TWO EXACT PREFIX READINGS

This is an elementary finite-action consequence of the existing model.
It upgrades an exact failure of deterministic two-query certainty to a
checkable failure of randomized adaptive certainty. It is not a new claimed
optimized randomized-adaptive value or an empirically validated deployment
benefit. The complete finite-witness argument is in proof.txt.

PUBLIC EXTERNAL CHECK (Python standard library only)
From the supplement/workspace root:

  python -S work/risk_adaptivity_revision/joint_certification/assurance_feasibility/verify_assurance.py --output-dir external_assurance_new

This reconstructs the 279 external instances from bundled source-linked
geometry, independently verifies all 1,674 exact coefficient normalizations,
classifies every first-query interval cover, and constructs/directly checks
twenty failing endpoint witnesses on each of the 94 excluded instances.
The default does not claim to check original coefficients.

BOTH-SOURCE CHECK
First complete the documented raw-source route:

  python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --raw-dir PATH_TO_PINNED_BLEM_CACHE --output-dir all_chain_new

Then run:

  python -S work/risk_adaptivity_revision/joint_certification/assurance_feasibility/verify_assurance.py --chain-dir all_chain_new --output-dir all_assurance_new

The checker verifies the fresh chain's PASS/no-reuse records, source and
driver identities, all source input hashes, geometry hashes, precision-plan
hash, and shared-plan linkage. It independently normalizes each of the 6,588
source coefficient vectors with Fraction arithmetic and checks exact equality
to the serialized plan coefficients. Original coefficients remain local.

Only identifiers, cohort labels, pair identifiers, affine coefficients and
source hashes drive the new calculation. Stored meter increments, retained
totals, recorded query answers and replay outcomes are not used. Unit-sum
normalization removes the total from the witness construction. No model is
fitted, no network request is made, and no existing scientific script is
imported or changed.

OUTPUTS
report.json: actual case/check counts, exact minimum strict margins, complete
  source provenance, source/witness hashes, runtime and scope.
synthetic_witnesses.json: one coefficient digest and twenty constructed
  endpoint pairs per excluded case. It contains no original coefficient
  vectors or recorded BLEM values. For each first query, all four adverse
  records give the same first answer. Each pair has identical first/second
  readings and a contrast difference strictly above one half. The lower
  endpoint serves as the synthetic hidden record; each ordered witness has
  mass 1/20, independently of the policy seed.

The generator's direct checker verifies nonnegativity, unit mass, common
first answers, both query equalities, the exact endpoint contrast difference,
and strictly positive failure margin. This endpoint check does not call the
conditional-width/interval routine used to construct witnesses.

EXECUTED EVIDENCE
executed_external/ holds the actually executed public external check.
executed_all/ holds the actually executed both-source check, tied to the fresh
single-invocation source chain via hashes. The 819 original instances split
162 fixed-guaranteed, 168 adaptive-only-guaranteed and 489 excluded from
certainty. External counts are 128, 57 and 94. The excluded cases satisfy
the non-tight randomized-adaptive upper bound 19/20, in the uncapped exact-
total/noiseless prefix model. Equality at the half-width threshold is success.

These certificates are exact for the stored binary64-derived coefficients.
They are not calibrated bounds on physical measurement or forecast estimation
error, model-winner certificates, prevalence estimates, or a claim that the
public API imposes a two-reading limit. Bulk and one-extra-reading alternatives
remain separate protocol choices and need their own admissible certificates.
