LOW CARBON LONDON REFERENCE PREPARATION

Official source
UK Power Networks, SmartMeter Energy Consumption Data in London Households, London Datastore. The official record describes half-hour kWh from5,567 households participating in the Low Carbon London project,2011–2014. Its metadata links to Creative Commons Attribution4.0. Credit UK Power Networks and link the source in any redistribution.
https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d
https://creativecommons.org/licenses/by/4.0/

The original full archive is801,674,949 bytes, SHA256:
68a35598cc8e70898a7651c482216fb096a0a6910c2d180c616632dfc7a9b014
Its only member is CC_LCL-FullData.csv,8,542,818,238 bytes. The ZIP uses Deflate64, which Python's built-in zipfile cannot decompress; use a standard7-Zip-compatible extractor. The locally used7-Zip26.04 is a tool dependency, not a scientific data source.

Commands from the project root
python work/external_deadline/source/download_lcl.py
7za x work/external_deadline/source/LCL-FullData.zip -owork/external_deadline/source/lcl_raw
python work/external_deadline/source/prepare_lcl.py
python work/external_deadline/source/verify_lcl_reference.py

Small source-quality fixtures only:
python work/external_deadline/source/prepare_lcl.py --self-test

Inputs, selection and quality
The exact protocol is lcl_protocol.txt with lcl_clock_amendment.txt. Both were frozen before source quality results or model fitting. All source rows are scanned so the100 lowest distinct source IDs are known even if the file were unsorted. The20 lowest IDs with at least90 complete training days are selected. Neither validation/test availability nor any forecasting or acquisition outcome determines the selected IDs. All100 candidates remain in the quality inventory.

The original CSV supplies four fields: LCLid, stdorToU, DateTime, and KWH/hh (per half hour). It has no actual/estimated reading-quality flag. We exclude Null/nonfinite/negative entries, duplicate timestamp groups, off-grid labels, absent half-hours and the two2013 UK daylight-saving transition dates. Physical zero consumption remains valid. An hourly reference requires exactly two valid labels at :00 and :30; its energy is their sum. No missing-target imputation, power integration, rescaling or replacement occurs.

The primary documentation reviewed does not verify UTC or interval-label start/end orientation. Consequently the hourly reference is explicitly the sum of the paired labels, and the day is a provider-label day. timestamp_benchmark preserves that clock; timestamp_utc simply appends Z as the experiment's coordinate convention for downstream code. It is not evidence of physical UTC or a measured arrival timestamp. All noon forecast issuance and audit deadlines are imposed benchmark conditions.

Artifacts in data/lcl
hourly.csv: selected-household reference grid; timestamp_benchmark and timestamp_utc (mapping above), energy_kwh only when eligible, source/valid/invalid/duplicate/off-grid counts and DST-exclusion flag.
daily_quality.csv: all100 candidate households and every prepared date, full-day eligibility, quality counts and split.
household_inventory.json: per-candidate source counts, tariff status, complete days and selection/exclusion reason.
selection.json: all candidate and selected IDs, exact training-only rule, protocol hashes.
selected_halfhour_source.csv.gz: literal source labels and values for the selected households in the prepared window. These are not interpolated hourly outputs; they allow the separate checker to reconstruct reference sums.
manifest.json: full source and output hashes, exact parser hash, checks and reference limitations. Require status passed before model fitting.

Verification scope
verify_lcl_reference.py does not import prepare_lcl.py. It recomputes hourly eligibility and energy sums using scalar CSV parsing and Decimal arithmetic, checks day counts, verifies the training-only selection rule from the100-household quality inventory, and verifies bundled output hashes. This is a separately implemented same-study reference check. It does not claim independent field verification, physical meter accuracy or independent source-row extraction from the full archive.

REFIT attempt retained
The earlier raw REFIT attempt remains in data/ and the source_protocol* files. All20 REFIT houses failed the frozen full-reference-day rule before any model fit;598 individual hours were eligible, but no complete days. No quality rule was loosened to rescue the experiment. The change to LCL was made before inspecting LCL comparison or acquisition outcomes.

Constructed temporal aggregates
Six-hour totals computed from these references are synthetic benchmark retention inputs. The data do not establish that such registers survive actual missing-interval incidents, that single readings are retrievable at a given price, or that the imposed deadline reflects a measured production system.
