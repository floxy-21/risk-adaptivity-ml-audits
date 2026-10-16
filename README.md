# Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data

> **Submission status, 16 October 2026:** Submitted to **PeerJ Computer Science**, manuscript **151201**. The verified portal status is **Checking**; acceptance or publication has not been claimed. See the [sanitized receipt](verification/submission_151201/submission_receipt.json) and [reviewer-PDF validation](verification/submission_151201/publisher_pdf_validation.json).
>
> This documentation-only update preserves scientific release `peerj-cs-2026-10-16-retrieval-gate` at commit `5fbeb4ca5b0619e6eff4598d3cca3f9cabe50f26`, including all release assets, checksums and source-snapshot files. Earlier records stating “not submitted” document their original pre-submission state and are retained unchanged.

Jishan Kapoor Â· Independent Researcher Â· Toronto, Canada

Research manuscript prepared for PeerJ Computer Science. This private repository
stores the author's submission materials; it does not indicate journal acceptance.

## Start here

- [Read the paper](manuscript/revised_manuscript.pdf).
- [Editable LaTeX source](manuscript/revised_manuscript.tex).
- [Complete reproducibility release](https://github.com/floxy-21/risk-adaptivity-ml-audits/releases/tag/peerj-cs-2026-10-16-retrieval-gate).
- [Table-to-command map](source_snapshot/work/risk_adaptivity_revision/CURRENT_RESULTS_MAP.txt).
- [Source-bound scientific execution record](verification/current_clean_package_replay.json).
- [Earlier five-point review, retained with its original scope](verification/peerj_five_point_audit.txt).
- [Current compiled-source review](verification/latest_compiled_review.txt).
- [Current practical-claim review](verification/final_gate_empirical_review.txt).
- [Current claim-to-ledger check](verification/current_claims_review/final_claims_report.json).
- [Earlier first-reader prose review](verification/first_reader_prose_review.txt).
- [Hash-bound upload-hygiene scan](verification/final_upload_hygiene.json).
- [Acquisition geometry and replay figure](figures/practical_guarantee_replay.pdf).
- [Fixed two-query proof review](verification/two_target_boundary/proof_review_memo.txt).
- [Precise prior-art comparison](verification/two_target_boundary/novelty_review.txt).
- [Assurance-feasibility proof](verification/assurance_feasibility/proof.txt).
- [Full source-derived assurance evidence](verification/assurance_feasibility/full_source_report.json).
- [Unique optimal-mixture argument](verification/budget_revision/two_target_boundary/optimal_mixture.tex).
- [Minimum fixed-budget proof](verification/budget_revision/reading_budget/proof.txt).
- [Both-panel reading-budget results](verification/budget_revision/reading_budget/executed_all/report.json).
- [Independent minimum-budget check](verification/budget_revision/reading_budget/executed_all/independent_check.json).
- [Joint mechanism and absolute floors](verification/empirical_review_revision/review_mechanism/executed/report.json).
- [Certified threshold stability](verification/empirical_review_revision/review_thresholds/executed/report.json).
- [Paired capacity attribution](verification/empirical_review_revision/review_capacity/executed_all/report.json).

The current diagnostics isolate the shared-budget mechanism on 191 of 225
baseline saving blocks (137 original and 54 external); 34 include a scalar
obstruction. At the declared training-scale absolute floor, all 57 baseline
external blocks remain assured. Thirty-nine need no feedback, and the unchanged
cohort uses 70 readings versus 88 minimum fixed readings. The complete external
panel uses 358 versus 378 readings: 18 retained and two new feedback-saving cases.
These are different denominators; the floor is a sensitivity model, not a
calibrated model-choice threshold.
All 222 matched-half certificates have nonzero sufficient threshold intervals.
Entire bands [0.49,0.51], [0.475,0.525] and [0.45,0.55] preserve adaptive certainty
and randomized-batch worst-record success one half in 179, 119 and 53 cases.
The frozen-certificate interval is closed below and open above; outside is
inconclusive, not a failure claim.
For the 225 baseline saving cases, the E/2 cap excludes 25, makes 191 fixed-
certifiable and leaves nine requiring feedback. The E/3 cap excludes 75 and
makes all 150 retained cases fixed-certifiable. Paired transition tables
separate additional information from cohort selection.
Eleven new jobs reproduce these diagnostics. Both-panel bundled derived-input
checks remain distinct from original raw-source and training reconstruction;
external source checks run by default. Scripts, ledgers and exact certificates
are in verification/empirical_review_revision/.

The fixed-budget result uses two affine targets and two coordinate queries:
adaptation guarantees joint precision, while the best randomized fixed batch
has worst-case success exactly `1/m` for every `m >= 3`. Each target separately
has a fixed two-query guarantee. The same separation holds for all three paired
contrasts of three constructed nonnegative forecast vectors. Its dictionary
grows with `m`, its normalized margin shrinks, and three fixed queries suffice.
It proves a boundary for shared assurance, not an empirical or financial gain.

The new corollary shows that all m specific batches are necessary for any
positive worst-record success; the unique optimum weights each by 1/m.
The exact support checker evaluates 126,195 widths across seven family sizes.

For the application, an exact linear scan computes how many fixed readings
the assurance requirement needs. On 225 blocks across all six systems, the
minimum is three fixed readings versus two adaptive readings. This is one
third fewer reserved scalar readings, with one additional feedback round.
Over the complete original and external panels, using the certified adaptive
plan and a minimum fixed fallback requires 2,457 instead of 2,625 and 686
instead of 743 readings (6.40% and 7.67%). Optional answers are not used to
derive these retrospective guarantees. They concern the exact uncapped
noiseless model, not HTTP requests or measured deployment costs. Fixed budgets
are globally minimal, including randomized policies with sure success;
adaptive budgets above two are not optimized. The actual API bulk result,
capacity/error controls and external greedy model-selection result remain.

The accompanying assurance-feasibility consequence identifies when the declared
two-reading protocol cannot provide certainty even with randomized feedback.
On 489 original and 94 external blocks, every randomized adaptive policy has
worst-record success at most `19/20`. This elementary finite-action bound is
not claimed optimal. Source-derived exact witnesses use no recorded answers.
Together with the fixed and adaptive guarantee certificates, it supports a
choice among fixed, adaptive and extended acquisition under the specified model.

The 28-page paper centers these two results and a worked
source-derived joint certificate. Scalar classification and mean-risk developments
remain in the supplement. Recorded outcomes retain the limits: exact adaptation
certifies a best model on 207 external blocks and greedy adaptation on 208,
despite exact adaptation's higher joint-precision success. Capacity information
reduces the precision advantage, and measured public-API retrieval favors bulk.
The query contract is declared; no deployed selective interface, privacy/compliance
benefit, financial saving or improved model choice is established.

## Reproduce the complete current paper

Download `Supplemental_Data_S1.zip` and `Supplemental_Data_S2.zip` from the release,
verify their SHA-256 values against `RELEASE_SHA256.txt`, and extract both into
the same empty directory. These publisher-sized files contain the current
reproduction package. Use the documented Python 3.12 environment:

```sh
python -m pip install -r requirements.txt
python work/risk_adaptivity_revision/reproduce.py
```

Run these commands from the extracted package root. The default entry point
checks all manifested files, creates a new isolated stage, blocks network access
during scientific replay, executes 101 checks, compares saved
scientific results and reconstructs the current manuscript byte-for-byte.
The tested environment and exact scope appear in the verification record.
The recorded full scientific run took about 21.7 minutes on
the study host, plus extraction/copy time; allow several GB of free disk.

The new `two_target_exact` and `two_target_lp` jobs check the constructed family
at `m=3,5,10` with rational arithmetic and
7,131 actual LPs, respectively.
The maximum recorded width discrepancy is
`7.105427357601002e-15` under a
`1e-7` comparison tolerance and `1e-9` primal/dual solver tolerances.
Both reports include the checker SHA-256 and canonical mathematical-input hash.
The all-size theorem rests on its proof; these finite checks test the implementation.

The `joint_assurance_feasibility` job independently regenerates exact adverse
distributions for 94 external no-certainty cases and checks 1,880 failing fibers.
The separately executed source-bound report covers both panels: 583 distributions
and 11,660 fibers. The full report, witnesses, current checker and proof are
hash-bound in the delivery record. Default replay does not recheck original raw
coefficients; the documented pinned-source route supplies that separate evidence.
The result concerns the uncapped exact-total noiseless prefix model and does not
transfer automatically to noisy or capacity-constrained interfaces.

Default replay uses frozen forecasts; it does not refit models, download source
data or repeat the archived API/timing measurements. Separate regeneration and
fresh-fitting commands are documented in the package. BLEM-derived raw traces are
regenerated locally rather than redistributed; attributed public-source caches
and constructed instances are bundled as documented.

A separate completed source-to-table run checked pinned original counters,
restored the exact frozen forecast archive, regenerated both panels' policies
and exact certificates, and reproduced all 1,098 outcome rows. Its commands,
scope and execution records are in `joint_certification/provenance_chain/`.
That run uses frozen models; it is not fresh fitting or external human review.

The final precision calculation closes all 418 previously open batch games and
supplies matching rational certificates for all 1,098 instances. Its secondary
width refinement uses coefficients before recorded-answer replay. Adaptive versus
precision-optimal batch replay succeeds on 78.27% versus 54.15% of original blocks
and 90.32% versus 71.83% externally. The unchanged-policy decision-tolerance
diagnostic reports adaptive/greedy/fixed counts of 189/186/188 and 277/277/263
at 1% of training mean squared hourly energy; the external greedy tie remains.
The 28-page main text separates
the mathematical optima, exact instance guarantees, recorded outcomes and API
costs. Complete controls remain in the supplement. The current full replay uses
an isolated Python environment with all 11 runtime packages pinned.
The assurance consequence completes the exact three-way feasibility decision,
including all randomized adaptive policies in the no-certainty branch. The saved
greedy first-query limitation and stronger fixed-fallback control remain visible.
These are source-derived results rather than a new independent experiment.
The main figure is generated from exact source coefficients and case counts;
its standalone PDF/PNG and independent check are available in `figures/`.
An introductory workflow now explains the choice among bulk, fixed, adaptive
and extended acquisition under the declared exact-total noiseless model.
The policy and status tables distinguish optimization objectives, guaranteed
success and recorded outcomes; fallback is an overlapping label rather than
another status-partition cell. The final compiled-source review also records
the workflow and displayed-equation rendering checks. The completion and
decision-diagnostic programs extend the earlier checks; the earlier producer
outputs and their original provenance remain separately available.

## Repository and release contents

`manuscript/` contains the final PDF, editable source and local cover letter.
`source_snapshot/` provides browsable code, methods, documentation and small
fixtures from the exact release. Large frozen inputs remain in the complete ZIP
release asset rather than Git history. Run the full package, not this intentionally
partial source snapshot. `verification/` contains the final execution and review
records. SHA-256 checksums identify the precise manuscript and supplement.
`verification/delivery_scripts/` contains the final post-replay publishing gates,
bound by hashes in the delivery record. They were updated separately from the
scientific package, whose exact manifested snapshot remains preserved.
Earlier internal review files are kept with their original source hashes;
they are not represented as fresh assessments of the final revision.
`verification/latest_compiled_review.txt` identifies the current artifact review.
`verification/first_reader_prose_review.txt` records the earlier fragment-level
clarity edits; it is not a separate final-PDF or external human review.
The `pre_workflow_*` files preserve the preceding successful replay at its
own source hash. The upload-hygiene record matches the current manuscript and three archives.
The `pre_two_target_*` files likewise retain the preceding successful release
as history, not as a substitute for the two new jobs or current source replay.
The `pre_budget_*` files preserve the published assurance manuscript, PDF and
verification history. The private release `peerj-cs-2026-10-14-assurance` remains available;
`peerj-cs-2026-10-16-retrieval-gate` identifies this focused revision.
Recorded host-native process failures and subsequent complete successful runs
remain separate execution history, rather than silently discarded failures.
The failed current-revision attempt at step83 is preserved in
`verification/pre_dependency_fix_20261016/`: its error log, preservation manifest,
selection records and exact old journal-part hashes are distinct from the fresh
corrected-package replay. The original failed ZIPs remain local. Older successful
records retained inside that history do not prove the failed attempt succeeded.

The larger `research_supplement.zip` preserves historical development records.
Its `EXCLUDED_EDITORIAL_NOTES.json` explicitly identifies three internal notes
omitted from scientific assets. The inherited notes remain in the previous private
release/local originals and are excluded from the current recoverability count.
The retained `work/randomized_tie_review/theory_review.txt` provides substantive
historical mathematical rationale used as a hash-pinned checker input. It is
internal AI-assisted review, not external validation of the current manuscript.
The publisher package omits unused historical caches and lists those omissions;
its 101-step execution uses the same scientific files and driver. No browser
sessions, account credentials, registration forms or private outreach drafts are
part of this repository.

## Attribution and status

Author contributions and supervised generative-AI assistance are disclosed in the
manuscript. Internal checks are not external human peer review. Third-party source
and data notices remain in the supplement; no blanket relicensing is asserted.
This repository is private. The manuscript has not been submitted or accepted.
PeerJ sign-in and draft preparation have been recorded. The author has authorized
submission after the final verification. Preparing or verifying this release
performs no fresh portal check and does not submit the manuscript.
