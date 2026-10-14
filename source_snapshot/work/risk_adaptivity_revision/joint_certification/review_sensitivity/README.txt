REVIEW-STAGE SENSITIVITY: UNCHANGED SHARED-QUERY POLICIES

Question B: how large are the remaining precision-challenger continuum gaps?
Question C: do recorded success differences depend entirely on target 1/2?

These are exploratory analyses of previously analyzed sources. No model is
refitted and no policy is reoptimized. All 819 original and 279 external blocks
are retained. Query dictionaries and the hard budget of two readings are
unchanged. Primary outcomes remain those of the published half-width design.

From the extracted supplement root:

python work/risk_adaptivity_revision/joint_certification/review_sensitivity/analyze.py
python work/risk_adaptivity_revision/joint_certification/review_sensitivity/check.py

Typical local runtime: approximately 15 seconds for analysis and 15 seconds for
the solver-free checker. NumPy is used for descriptive bootstrap intervals by
analyze.py; check.py requires only Python's standard library. The checker imports
no producer functions and checks all summaries, paired cells, source-ledger joins,
and pointwise intervals using separately implemented calculations.

INPUT AND OUTPUT MAP

frozen_inputs.json contains the 1,098 saved derived width vectors, batch choices,
mixtures, and precision bounds. Source SHA256s are recorded. These are study
results, not raw BLEM records. The default analysis does not access excluded raw
files or private development directories.

results/continuum_gaps.csv/json: all-panel and unresolved-only upper-minus-lower
probability gap distributions, exact histograms, and linear empirical quantiles.
Zero gap means matching continuum guarantees for the original 1/2 target.
An open gap is not an estimated practical effect or a confidence interval.

results/threshold_cases.json/csv and threshold_summary.json/csv: all five target
fractions, unchanged adaptive/fixed/greedy policies and saved randomized mixtures.
Per-case entries preserve exact probability fractions; randomized paired cells
are expected counts. Means and uncertainty summaries are displayed as floats.
The randomized mean policy optimizes worst expected joint width. The precision
challenger was constructed for target 1/2, and remains incompletely optimized on
open-gap instances. Neither is claimed to optimize each new threshold.

results/strict_threshold_cases.json and strict_threshold_summary.json/csv repeat
the same calculation with zero comparison tolerance. No policies are changed.
results/bootstrap_draws.json records the synchronized seven-day circular calendar
block draws: 2,000 PCG64 draws, SeedSequence([20261013, source_id, 7]), source_id 0
original/1 external. Percentile endpoints use linear 2.5/97.5% quantiles. Intervals
are paired, source/system-specific, descriptive and pointwise, not simultaneous
confidence bands or inference to a population of organizations. Each source has
only three systems; all six comparisons in a block use one joint outcome.

NUMERICAL-CONVENTION DIAGNOSTIC

The original general shared replay used J <= target + 1e-8. The old precision
challenger replay used exact rational J <= target. The new main sensitivity uses
the original 1e-8 convention for all policies; strict results are also supplied.
The three deterministic policies' results are identical under both conventions
on every reported threshold. One external block, hpm_1/2025-07-19/00, changes the
mean and half-precision randomized probabilities only at threshold 1/2. The batch
{2,4} has width 2251799813685248/4503599627370495, exceeding 1/2 by
1/9007199254740990 = approximately 1.1102230246251568e-16. These are exact
rationals of normalized binary64 coefficients, not claimed exact physical data.
The block's probability changes by 0.2062857406948184, or0.07393754 percentage
points averaged over 279 external blocks. Common-tolerance mean/challenger rates
are 69.8981%/72.6209%; strict rates are 69.8242%/72.5469%. Historical outputs remain
unchanged. boundary_sensitivity.json lists the complete exact diagnostic.

SOURCE CHECK, DISTINCT FROM DEFAULT REPLAY

source_verification.json records an actual full-source check: 6,588 coefficient
rows joined to the frozen geometry; 10,980 rational batch widths rebuilt from
original/external counters; 720 independently solved endpoint LPs on the first
chronological block per system. Maximum LP discrepancy 2.22e-16; threshold 1e-10.
This check refits no models. Source authentication is provided separately by
joint_certification/provenance_chain, which pins raw versions and hashes.

To recreate source_verification.json, first run the documented both-panel raw
provenance-chain route. Then point the following script at its regenerated
precision plans, geometry and hourly endpoint files:

python work/risk_adaptivity_revision/joint_certification/review_sensitivity/verify_source.py --precision-plans PATH_TO_ALL_PRECISION_PLANS --original-geometry PATH_TO_ORIGINAL_GEOMETRY [SECOND_GEOMETRY_IF_SPLIT] --original-answers PATH_TO_ORIGINAL_HOURLY_ENDPOINTS

Optional --external-geometry and --external-answers override the bundled frozen
external paths. This source mode requires SciPy and NumPy. It fails if the named
inputs are absent; a saved-width replay does not masquerade as raw regeneration.

To recreate frozen_inputs.json from regenerated all-panel shared plans:

python work/risk_adaptivity_revision/joint_certification/review_sensitivity/prepare_inputs.py --shared-plans PATH_TO_ALL_SHARED_PLANS

--ledger and --precision-cases optionally point to freshly regenerated files.
The preparer only extracts existing choices; it does not perform optimization.

The manuscript fragment and compact three-policy table intentionally emphasize
threshold robustness rather than choosing the most favorable new target. This
does not extend the noise/capacity guarantees to the new thresholds, establish
financial savings, or demonstrate a deployed retrieval service.
