SHARED-BUDGET CERTIFICATION: CURRENT REPRODUCTION ROUTES

Run commands from the extracted supplement root. Default producers use only
the 279 external blocks and all six pairs per block, with two shared cumulative queries.
Public code defaults do not require original BLEM geometry or register answers.
The package-wide entry point is:
  python work/risk_adaptivity_revision/reproduce.py
Its 66 steps include 24 shared-budget jobs, two final-review dependence checks,
and one printed-certificate check before cached external geometry regeneration.
This order matters: exact provenance checks verify frozen hashes.
Use a disposable extracted copy for manual default commands, which write the
named output subdirectories here. The package wrapper writes fresh outputs into
an isolated stage and compares case-by-case scientific values with this release.

For brevity let JC denote work/risk_adaptivity_revision/joint_certification/.
Replace JC below by that path; it is notation, not a shell environment variable.

1. Exact shared-budget game and deterministic adaptive planning
  python JC/empirical_shared_audit.py
  python JC/empirical_check.py
  python JC/independent_shared_review.py
  python JC/independent_model_coherence.py
Outputs: empirical_external_results/empirical_{plans,cases,report}.*,
empirical_independent_check.json, independent_shared_external.json,
independent_model_coherence_external.json.
The full-panel archived reports/CSV are empirical_all_panel_report.json and
empirical_all_panel_cases.csv. They cover 1,098 blocks; no blocks are selected by
success. The mean-risk formulation is exact for the uncapped simplex, while
its numerical solutions have declared tolerances. Optional LP-face diagnostic:
  python JC/independent_tie_diagnostic.py
Regression cases, including zero-valued games and secondary ties:
  python JC/empirical_regression.py

2. Precision-matched challenger and exact certificates
  python JC/precision_batch.py
  python JC/precision_batch_check.py
  python JC/precision_adaptive_link.py
  python JC/empirical_precision_replay.py
  python JC/independent_precision_replay_check.py
Outputs: precision_external_results/{plans,report,independent_check,
adaptive_half_check}.json and empirical_precision_results/{cases,report}.json.
The first program creates coefficient-only policies before response replay.
The two exact checkers establish full-simplex lower guarantees and adverse
upper bounds, and prove adaptive half-width attainment on the matching subset.
The challenger is not claimed globally precision-optimal where bounds differ.
The all-panel derived replay is in empirical_precision_all_results/.

3. Noiseless capacity controls (original absolute threshold preserved)
  python JC/empirical_capacity.py
  python JC/empirical_capacity_check.py
Outputs: empirical_external_capacity_results/ and
empirical_capacity_independent_check.json. All 279 blocks are retained at caps
E/2 and E/3. Only 200 and 198 actual profiles, respectively, satisfy those caps.
The all-panel derived reports/CSV are empirical_all_capacity_report.json and
empirical_all_capacity_cases.csv. These are illustrative constraints, not
manufacturer specifications. No vertex-only capped randomized optimum is used.

4. Stored-readout and combined capacity/error controls
  python JC/noise_independent_check.py --directory JC/noise_external_results
  python JC/noise_independent_check.py --directory JC/noise_external_capacity_results
These standard-library commands verify exact rational branch/batch certificates,
reported guarantee statuses, source coefficients, and adverse distributions.
The first folder freezes the uncapped planner; the second freezes the E/2
noiseless planner before applying the 1% allowance. It is not asserted optimal
for noisy querying. Endpoints stay exact. Optional robust-LP regeneration:
  python JC/noise_joint_certify.py --scenarios error_1pct cap_half_error_1pct --output-dir outputs/noise_recertify
  python JC/noise_joint_certify.py --capacity-plans JC/empirical_external_capacity_results/empirical_capacity_plans.json --scenarios cap_half_error_1pct --output-dir outputs/capacity_noise_recertify
See noise_joint_certify.py --help for current flags. Further exact batch-upper
and strengthened-profile certificate generation is provided by
noise_export_batch_duals.py and noise_batch_adverse_strengthen.py; default
replay checks their saved outputs rather than claiming a fresh robust-LP run.
Recorded-answer replay and independent two-endpoint LP checks:
  python JC/empirical_noise_replay.py
  python JC/empirical_noise_check.py
  python JC/empirical_noise_replay.py --certification-dir JC/noise_external_capacity_results --output-dir JC/empirical_capacity_noise_results
  python JC/empirical_noise_check.py --results-dir JC/empirical_capacity_noise_results --output JC/empirical_capacity_noise_independent_check.json
Greedy in the combined noisy control remains the original frozen uncapped
policy; the main capacity-aware comparison is against the robust fixed batch.

5. Model-choice outcomes, paired cells and descriptive uncertainty
  python JC/decision_replay.py
  python JC/independent_decision_check.py
  python JC/empirical_pair_summary.py
  python JC/empirical_pair_check.py
The first two programs separately check strict model-winner/ranking decisions.
A narrow interval need not certify a winner. Paired statistics export every
2 x 2 cell and per-system effect in empirical_paired_external_results/.
Use --cohort all --output-dir JC/empirical_paired_all_results for all derived
panels, without raw reconstruction; all required case-level outcome ledgers
are bundled. Intervals use 2,000 draws, base seed 20261013, primary seven-day
circular calendar blocks synchronized across systems, with one-day clusters
as a secondary sensitivity. Only three systems occur in each panel, so these are
descriptive conditional summaries, not organization-population inference.

ORIGINAL-SOURCE MODE (OPTIONAL, SEPARATE FROM PUBLIC DEFAULT)
First follow counter_adaptive/README.txt and reproduce_counter.py to regenerate
the original geometry and hourly endpoints. Then run empirical_shared_audit.py
--cohort all --original-geometry <pilot-geometry> <continuation-geometry>
--original-answers <hourly-endpoints.csv> --output-dir <all-results>.
Provide these explicit regenerated paths and --cohort all to precision_batch.py,
empirical_precision_replay.py and decision_replay.py as well. Do not assume
that a public supplement contains the original raw-dependent paths. Archived
all-panel summaries are derived output, not evidence of a default raw rerun.

No command fits new forecasts or establishes external human validation. The
published effects are retrospective, and unrestricted bulk retrieval remains
a different admissible interface that may dominate selective acquisition.


FINAL-REVIEW SYSTEM EFFECTS AND DEPENDENCE CHECKS
  python work/risk_adaptivity_revision/joint_certification/final_review_analysis.py
  python work/risk_adaptivity_revision/joint_certification/final_review_check.py
Default jobs: final_review_dependence and final_review_independent. These two
checks use the bundled full-panel derived outcome ledgers, without original
raw data, new forecasts, policy changes or retuning. Seven-day intervals remain
primary. The additional fourteen-day synchronized circular-block sensitivity
and leave-one-system-out comparisons retain the declared original precision
threshold and actual capacity-compatibility flags.
Outputs: joint_certification/final_review_results/{report.json,system_effects.csv,
dependence_sensitivity.csv,draws.json,precision_catalog.json,main_system_table.tex,
supporting_dependence_table.tex}; independent report final_review_independent.json.
Fresh wrapper outputs: outputs/final_review_dependence/ and
outputs/final_review_independent.json. The main system table is
tab:joint_system_effects; S8 reports tab:joint_long_dependence.
Full-panel precision counts classify closed-zero, closed-half, closed-one and
open-gap bounds separately from the overlapping fallback-policy classification.
The independent checker recounts all 1,098 derived precision records and checks
116 temporal/system-omission comparisons. Archived full coefficient-only plans
were matched before these derived summaries were frozen; public replay does
not claim to reconstruct original raw-dependent plans.

INSPECTABLE SHARED-QUERY RESULT
The main theorem and worked real-data certificate are verified without an optimizer.
See joint_certification/INSPECTABLE_CERTIFICATES.txt for the four-command chain.
  python work/risk_adaptivity_revision/joint_certification/check_main_inspectable_certificate.py
This default step checks the actual printed real-data coefficients, outward
enclosures, branch coverage, 36 covering multipliers and matching adverse records.
Output: joint_certification/main_inspectable_certificate_check.json.
The existing proof_check_joint.py verifies the constructed mean-risk theorem;
precision_batch_check.py and precision_adaptive_link.py check all 279 external
inputs and recover the 57 exact-half guarantees. Original-panel certification
requires the separately documented raw-source regeneration route.
