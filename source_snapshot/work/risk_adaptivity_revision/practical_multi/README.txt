FOUR-MODEL CERTIFICATE GATE: SECONDARY FROZEN-ARCHIVE ANALYSIS

Default public replay (Portugal and French household):
  python work/risk_adaptivity_revision/practical_multi/evaluate_model_selection.py

Optional full-source replay including the three counter series:
  python work/risk_adaptivity_revision/practical_multi/evaluate_model_selection.py --source full

The full replay requires outputs/study_period_archive_cases.csv, which is
available locally or after the separately documented BLEM raw-source archive
regeneration. The default uses the bundled public endpoint CSV. An alternate
input path and output directory can be provided with --input and --output-dir.
The counter result is not represented as replayable from the public endpoint
CSV alone. Follow the package's existing full/raw restoration instructions.

Requires Python and NumPy. Saved runs used Python3.12.14 and NumPy2.5.3.
Public run: 8.144s, 5,022 scenarios, 70,308 source rows used.
Full run: 8.883s, 5,508 scenarios, 77,112 source rows used.
Runtime depends on the machine; report.json stores the actual runtime and
source/script hashes, so its bytes are not expected to match across runs.
case_ledger.csv and table_rows.tex are deterministic for unchanged input.

Protocol and information flow
-----------------------------
This analysis was added after inspecting the original archive. It is an
exploratory secondary aggregation, not a new independent replication or a
prespecified forecasting experiment. No model is trained, retuned, or replaced.

One scenario groups six unordered model-pair comparisons for the same meter,
gap, pattern, seed, aggregate length, total tolerance and archive regime.
The four models are persistence, ridge, histogram gradient boosting and MLP.
The point proposal is the unique historical-donor-completed MSE winner. Saved
pair differences reconstruct scores up to an irrelevant additive constant.
All six differences are checked for additivity. Selection uses no reference
targets or certificate endpoints. A proposed winner must have all three donor
point differences in its favor with the original numerical sign margin.

The certificate gate requires a favorable interval comparison against EACH of
the other three models, using paired bounds or separate-loss bounds. Both
methods receive the same selected candidate and information. They issue a
certified historical preference or unresolved status; these are not claims of
future prediction superiority or automatic safe production deployment.

The frozen source exports donor point rows only at exact (0%) totals. For 1%
and 5% tolerance, the original candidate is HELD FIXED while its certification
is tested under the saved wider bounds. The script does not recompute or claim
donor imputation under uncertain totals. This distinction appears in both the
JSON report and manuscript fragment.

All scenarios remain in the denominator; a missing unique donor preference
would count as unresolved. In the executed data, all preferences were unique.
Reference truth is checked only after the proposed model and certificate have
been determined. The existing 1e-9*max(1,abs(lower),abs(upper)) sign margin is
recomputed. Other numerical consistency checks use 1e-8 relative to max(1,
the pertinent magnitudes). Interval nesting violations were zero. The largest
scaled donor additivity discrepancy in the public run was1.259e-15.

Portugal exact-total result
--------------------------
1,620 scenarios: paired933/1620(57.59%), separate167/1620(10.31%).
Additional authenticated winners:766; coverage difference47.28percentagepoints.
Unresolved scenarios:1453(separate) to687(paired), a52.72% relative reduction.
This denominator differs from the9,720 PAIR comparison count in the original
grid. Do not reuse the73.86% pair-level unresolved reduction for this analysis.
No selected winner was wrong relative to the reference historical period.
This is not an accuracy gain: the donor already chose the empirical winner.

The uncertainty summary resamples whole consumers (all54 scenarios per
consumer)2,000times withseed20261012. Exact-total paired coverage difference
has descriptive95% interval40.80--53.77percentagepoints. This is convenience-
panel stability, not population inference; shared calendar shocks are not
covered. No such interval is produced for cohorts with fewer than10 consumers.

The minimum certified advantage is the least guaranteed MSE advantage over the
three competitors. Its normalized form divides by the already saved squared
training-period mean kWh. It is NOT a percentage improvement over test MSE.
The historical0.9738064% acquisition result and its denominator are unchanged.

Outputs
-------
results_public/case_ledger.csv, report.json, table_rows.tex
results_full/case_ledger.csv, report.json, table_rows.tex
manuscript_fragment.tex supplies a self-contained interpretation/table.

These are floating-point endpoint replays. They do not independently refit
models or recompute every endpoint from hourly targets; the package's existing
archive-reconstruction path supplies that lower-level reproduction.
