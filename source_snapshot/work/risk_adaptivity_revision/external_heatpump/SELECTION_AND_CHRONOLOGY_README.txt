External HeatpumpMonitor selection, qualification and chronology map

This document maps existing frozen evidence; it does not alter the selector, protocols, input files, model specifications, outputs or exclusions. All times below are UTC on 12 October 2026. The logs and hashes are an internal audit trail, not an external preregistration service or independent execution claim.

Selection rule and complete stopping-prefix ledger
source_selection_protocol.json fixed the January-June 2025 training calendar and July 2025 test calendar at 02:12:05.103909. Sort the public system list by ascending numeric ID. Require MID metadata true, an electrical-meter description explicitly identifying Class 1, and a heatpump_elec_kwh feed with metadata start no later than 1 January 2025 and metadata end no earlier than 1 August 2025. Stop at the first three qualifying IDs. No held-out performance or July completeness enters source selection.
metadata/public_systems.json contains 817 public systems. selection_ledger.json records every candidate reached before the third qualifier:
ID 1: selected; Class 1/MID and feed covers the calendar.
ID 2: selected; Class 1/MID and feed covers the calendar.
ID 3: excluded because mid_metering=0.
ID 4: excluded because feed metadata ends 20 March 2025 at 11:49:50 UTC, before the required end.
ID 5: excluded because feed metadata ends 17 April 2025 at 03:29:50 UTC, before the required end.
ID 6: excluded because mid_metering=0.
ID 7: selected; Class 1/MID and feed covers the calendar. Selection stops here.
Thus selected_systems.json contains 1,2,7. IDs above 7 are not additional exclusions from a full-population experiment: the fixed rule had already reached its required three systems. The evidence for IDs 3 and 6 is in metadata/public_systems.json. For 1,2,4,5,7, inspect metadata/system_ID_feeds.json under the top-level feeds object; selected-system detail records are metadata/system_1_metadata.json, system_2_metadata.json and system_7_metadata.json.

Documented metadata-parser correction
The first metadata loader initially overlooked the feeds envelope and retrieved extra metadata. The correction happened before any hourly requests, model fitting or outcomes. Source inventory and request logs retain this history; metadata caches above ID7 must not be misdescribed as discarded low-performing systems. The final selector's ascending-prefix decisions can be reconstructed solely from the saved public list and feed metadata, and match all seven rows of selection_ledger.json. No hourly data were requested for an excluded or beyond-stop system.

Training availability versus feature eligibility
The training responses were cached at 02:15:19.153844 (ID 1), 02:15:22.290411 (ID2), and 02:15:25.018368 (ID7).
The detailed operational protocol lock at ../external_validation/operational/protocol_lock.json was written at 02:20:03.969830, after training-only inspection and before July retrieval, fitting and evaluation. Its training gates are at least 95% valid hourly training intervals and 90 complete eligible training days; failed locked IDs would be reported, not replaced. Do not describe these detailed gates as frozen before the first training values were accessed.
training_availability.json reports: IDs 1/2 each 4344/4344 valid hourly intervals and 181 complete raw training days; ID 7 has 4338/4344 valid intervals (99.861878%) and 178 complete raw days. All pass. No interpolation, clipping or system replacement is used.
The model design additionally requires lagged features: the actual fit uses 174, 174, 167 eligible training days, respectively, as reported in ../external_validation/operational/fresh_fits_20261012/training_report.json. Raw complete days and feature-eligible fit days are different counts. All 93 July issue-days are listed in calendar_ledger.csv beside that report; current target availability is separate from forecast eligibility.

Held-out access and results chronology
July raw retrieval begins only at 02:27:39.430552 (ID 1), followed by 02:27:42.256366 (ID2),02:27:44.731292 (ID7). These events are in request_log.jsonl; july_cache_manifest.json pins the three raw files, shared-boundary equality and canonical CSV hash. These three files contain 745 hourly endpoints each. The combined train/test CSV has 15,267 rows after identical shared July 1 boundaries are deduplicated.
The frozen forecast artifact is ../external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv (2232 rows; SHA256 04dc64193fbcf00879e4f7ba5224d5626def79a8caad474fb3242d3d8d69b12f). The fresh fitting report pins the operational lock and adapter, and records no retuning, retries or replacements. It reports elapsed fitting time rather than a wall-clock start timestamp; do not invent one.
../external_validation/replay/geometry.json has a 02:33:50.747657 creation timestamp and pins forecast/data/protocol hashes. initial_intake.csv covers 279 blocks; replay_attrition.csv covers all 1,674 planned pairwise tasks, all eligible. The 29 half-separation cases are a geometry-defined subset, not the overall study denominator.
../external_validation/operational/http_benchmark_20261012/benchmark_plan.json records the three earliest eligible positive-width daily-versus-MLP timing cases and randomized balanced orders before timed responses. Its status says frozen_before_timed_responses but it has no independent wall-clock creation field; actual requests are timestamped in request_log.json in that directory. No timestamp should be inferred from an absent field.

Timestamp and physical provenance boundary
TIMESTAMP_INTERFACE_NOTE.txt and ../external_validation/operational/IMPLEMENTATION_NOTE.txt explain requested API-grid timestamps versus unobserved native measurement times. ID 1's irregular88.17 s feed metadata is retained. Exact native day-start availability, original device-register provenance and absence of upstream interpolation are not established. Class 1 metadata is a selection condition, not a deterministic per-hour or lifetime-counter error bound. All original source files remain unchanged.

Offline documentary audit performed for the latest reviewer
The complete seven-row selection was independently recomputed from cached metadata and matched exactly. Every one of the 41 cached response bodies matches the SHA256 recorded in request_log.jsonl. These checks were read-only and used no provider calls. The default reproducibility entry can replay saved forecasts/cached source; optional model-refitting and live API timing are different evidence levels and must remain distinct.

Key fixed hashes
source_selection_protocol.json: ed1985ed81448de60582344ae83dae0999fc0a7267d27ff12a8d857dd3a51cc8
selected_systems.json: 536d90046d069cabb888aa0a1be9083cca12c29ce89f7996f9f91e987e5158e9
selection_ledger.json: 45fecb188fe7f6f0f84b611742efcfab68e9faaa994daa0249cd44b8a14dbee8
metadata/public_systems.json: 4478df97793b8c032aec71461bf8c7657965259891d01de00913e3684d0296c2
operational/protocol_lock.json: abae34c65056b019ac01b443fa8ef880db50d80509f0a4827885f02b17b8da13

Executable qualification check added for the current revision
From the supplement root, run:
  python external_validation/operational/check_source_qualification.py
The optional --output argument selects the JSON report path. The default is external_validation/operational/source_qualification_check.json. It uses only the Python standard library and the cached files: no network, refitting, or policy replay. The completed check independently reproduces the seven-row selection, all 41 cached body hashes and byte counts, all three raw and lag-complete training-eligibility summaries, and the stated internal chronology. It passed in 0.16 seconds.
