REFIT SOURCE PREPARATION FOR THE EXTERNAL DEADLINE AUDIT

This directory contains only source acquisition, quality screening, and reference construction. It does not fit predictors, inspect model comparisons, or evaluate recovery outcomes.

Source and attribution
Murray, D., Stankovic, L., and Stankovic, V. REFIT: Electrical Load Measurements. University of Strathclyde, raw 081116 release. DOI:10.15129/31da3ece-f902-4e95-a093-e0a9536983c4. Licensed CC BY4.0 by the official dataset record and raw readme. The corresponding source paper is An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study, Scientific Data4,160122 (2017), DOI:10.1038/sdata.2016.122.

Official dataset record:
https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements/
Raw readme:
https://pure.strath.ac.uk/ws/portalfiles/portal/62090176/RAW_READ_ME_081116.txt
Raw archive:
https://pure.strath.ac.uk/ws/portalfiles/portal/62090177/REFIT_RAW_081116.7z
License:
https://creativecommons.org/licenses/by/4.0/

Important source limitations
The raw release already contains intermediate expansion of load-change records. Part1 encodes unavailable sensor values as zero; it is excluded. Part2 marks unavailable sensors with NaN. The separate cleaned release fills small missing gaps and zeros larger ones; it is not used here. The retained reference is a defined integral of sampled/source-expanded power, not exact physical energy or interpolation-free measured truth. The source paper identifies solar effects in houses3,11,21; these are retained under the same screening rule and marked in the inventory. Whole-house Aggregate is a cross-appliance power channel, not an independently surviving six-hour energy register.

Reproduction
1. python work/external_deadline/source/download_refit.py
2. Extract REFIT_RAW_081116.7z using a standard 7-Zip-compatible tool into work/external_deadline/source/raw. This yields40 CSVs,8,312,269,294 uncompressed bytes. The optional local7zr.exe came from the official https://www.7-zip.org/download.html download link; it need not be bundled with the scientific supplement.
3. python work/external_deadline/source/prepare_refit.py --raw-dir work/external_deadline/source/raw --archive work/external_deadline/source/REFIT_RAW_081116.7z
Self-test only: python work/external_deadline/source/prepare_refit.py --self-test

Runtime dependencies: Python, NumPy and pandas, as pinned by the research supplement environment. The script reads only Unix and Aggregate. It retains every source household in the quality inventory and applies the same fixed eligibility thresholds. Household IDs are1–13 and15–21; there is no House14.

Protocols
Read source_protocol.txt, then source_protocol_amendment.txt (raw metadata), then source_dates_amendment.txt (Part2 availability). These preserve the original proposal and the reasons for source-only changes, all made before fitting and policy outcomes.

Output schema
hourly.csv: household_id (integer source ID), timestamp_utc (start of hour in ISO UTC), energy_kwh (finite only when eligible), eligible (0/1), coverage_seconds (0–3600), largest_gap_seconds (maximum offending source interval touching hour), long_gap_seconds, invalid_power_seconds, quarantined_seconds. Reasons can overlap. No power or energy is imputed for an ineligible hour.
daily_quality.csv: every household and date in the prepared grid, eligible_hours, coverage and reason counts, complete (24 valid hours), chronological split.
household_inventory.json: source row quality, duplicates, clock order, solar flag, complete-day counts, exclusions and source eligibility.
manifest.json: completion status, input/output hashes and selected source households. A partial hourly.csv during processing is not an approved training input; require passed manifest.json.

Scientific use
When these references are used to construct six-hour totals, label those totals as controlled benchmark inputs. Do not infer natural outage recovery, actual target arrival times, or retrieval price from this source.
