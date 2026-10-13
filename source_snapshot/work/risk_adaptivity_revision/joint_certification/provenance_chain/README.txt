SOURCE-TO-TABLE VERIFICATION FOR THE SHARED-QUERY RESULTS

Run from the extracted supplemental-file root. Use the study's Python
environment and requirements. No command here fits a forecasting model.

Fast public checks (offline; no original BLEM records required)
  python work/risk_adaptivity_revision/joint_certification/provenance_chain/check_source_guards.py --output source_guards.json
  python work/risk_adaptivity_revision/joint_certification/provenance_chain/check_source_chain.py --cohort external --output external_source_chain.json

The first deliberately supplies changed temporary bytes to the actual
original-data preparer and original-forecast geometry entry, and verifies
their checksum rejection. It also checks the external forecast identity gate.
The second verifies the attributed external cached provider responses, all
exported decimal counter records, the frozen forecast identity, its causal
persistence values, and all 1,674 contrasts for 279 blocks. It runs before
external geometry regeneration in the default release workflow.

Complete bundled external source-to-table chain
  python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort external --output-dir external_chain_new

Complete original plus external source-to-table chain
  python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --raw-dir PATH_TO_PINNED_BLEM_CACHE --output-dir all_chain_new

Output directories must not already exist. If --raw-dir is omitted in all
mode, the original wrapper downloads only its three pinned public source
files into the new output tree. Raw BLEM records, regenerated coefficients
and fine-reading answers stay local: do not add that raw-dependent output
tree to a public supplement. Their original redistribution permission has
not been established. The public executed records below contain counts,
case identifiers, source/script hashes and commands rather than those data.

What each stage verifies
1. Original: QuantLet/BLEM commit 756b2c1265f964b70f72625a95d98413cdfb78bd,
   three mandatory source SHA-256 values in work/data_prepare_blem.py.
   Integer subtraction precedes division by 10^10 to kWh. Every valid hourly
   endpoint agrees with original snapshots and its 21 nondecreasing samples.
2. Original frozen forecasts: the lossless export hash is pinned. Rebuilding
   its 6,552 omitted BLEM target/persistence rows restores the complete
   89,496-row historical forecast CSV to SHA-256
   c1f6d2663d228aeeb8073226488ea8f2fca6b14b308e4a4f62ce38482c93f8e6.
   Other CSV fields are preserved. This focused chain does not recheck the
   unrelated UCI raw targets and does not refit learned forecasts.
3. External: six cached API response files are checked against the exact
   decimal hourly export; July response hashes and the complete export/
   forecast hashes are checked. The data represent stored API-grid cumulative
   kWh samples, not independently calibrated physical meter measurements.
4. All saved forecasts, initial totals and coefficients are joined, covering
   4,914 original plus 1,674 external contrasts. Units, issue/cutoff times,
   six model pairs and six-hour block lengths are checked before policy replay.
5. Shared policies are generated from those coefficients before fine answers
   are loaded. Exact rational batch coverings and feasible adverse weights
   are verified, then the adaptive policy is checked over its complete
   first-answer domain. This yields the 165/57 matched-half subsets.
6. All ten batches are replayed, with independently calculated exact widths,
   MSE model-ordering signs and expected outcomes. Every one of the 819/279
   block rows is compared with the archived complete-panel ledger before
   either matched subset is summarized. Table totals and rounding are checked.

Current executed evidence
See executed/record_manifest.json, source_chain.json, table_chain.json,
source_guards.json, original_raw_execution.json and chain_execution.json.
The complete original raw wrapper, shared planner and precision producer
were freshly run on 13 October 2026. The final orchestration explicitly
reused those three newly generated directories, then freshly ran the
source joins, guards, exact certificates, adaptive linkage, direct replay,
independent replay and table comparisons. Reuse is recorded, not described
as a second regeneration. run_chain.py without those optional reuse flags
executes the full sequence from the stated inputs in one invocation.

Interpretation
This is same-study, frozen-predictor execution and independently written
checking. It is not external human validation, independent model training,
an untouched data experiment, a device specification, or a numerical proof
of the universal mathematical theorem. The theorem has its own analytic
proof; these records establish correspondence of the reported computations.
