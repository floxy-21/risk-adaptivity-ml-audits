MATCHED-INFORMATION WHOLE-PERIOD CERTIFICATE CROSS-TAB

Purpose
This post-review descriptive analysis summarizes the COMPLETE existing original
34-series scenario grid. It does not fit models, generate new endpoints, change
masks, choose favorable scenarios or re-estimate recovery policies. It compares
the saved paired-loss certificate with subtraction of separately bounded model
losses, using the same observed targets and retained aggregate information.
This certificate comparator is not the strongest imputation/acquisition baseline.

Commands (Python with NumPy/Pandas, from the project root)
  python work/certificate_grid_review/summarize_certificates.py --source public
  python work/certificate_grid_review/summarize_certificates.py --source full

The public command requires only the already bundled public saved endpoints and
their provenance manifests. It covers 30 Portugal consumers and one household:
60,264 matched comparisons / 216 scenario cells. The full command additionally
requires outputs/study_period_archive_cases.csv, which includes the three BLEM
counter series; those source-dependent endpoints follow the package's existing
raw-source regeneration path. It covers 66,096 comparisons / 324 scenario cells.
Default --source public always uses public endpoints. Optional --source auto
uses full if that file exists, otherwise public; the JSON states the scope
explicitly. A typical local run takes about 3 seconds.
No network calls or writes to input files occur. Outputs are under results_full
or results_public for the archived run; new executions default to replay_full
or replay_public, preserving the archived reports. --output-dir can select a
separate replay directory. Deterministic report content omits dates and paths.

OPTIONAL FULL ENDPOINT REGENERATION: WINDOWS WITH PINNED RUNTIME
Use Windows, Python 3.12.14 and outputs/requirements-study.txt. The full endpoint
CSV uses the original Windows CRLF line endings. The historical pandas writer
does not force line endings; a regenerated Linux file could contain identical
numbers but fail the required original byte hash. The public saved-file replay
does not regenerate that CSV and does not have this line-ending dependency.

From the extracted package root, use these THREE commands. Substitute the
absolute stage directory printed by command 1 into commands 2 and 3:

1. Reconstruct exact original inputs in a fresh isolated stage, without refits:
  python work/reproduce_review_revision.py --raw --reconstruct-only
   Optional --data-dir <pinned-raw-cache> reuses source files; otherwise missing
   sources are downloaded into that new stage. A completed historical report
   verified this reconstruction step: 89,496 rows, including 6,552 BLEM rows,
   with exactly the original prediction-archive SHA-256.

2. Generate the whole-period endpoints in that stage (single command line):
  python -c "import runpy,sys;from pathlib import Path;p=Path(sys.argv[1]).resolve();sys.argv=[str(p)];sys.path.insert(0,str(p.parent));runpy.run_path(str(p),run_name='__main__')" "<printed-stage-directory>/outputs/study_period_archive.py"
   The bootstrap matches the existing wrapper's sibling-import handling for
   long Windows paths. Scientific input/output paths derive from that script's
   location, so retain the package root as the working directory. In a clean
   public-package stage, the full endpoint CSV is absent after command 1;
   command 2 creates it and writes updated provenance. It retains the original
   public export manifest that records the expected full endpoint byte hash.

3. Cross-tab those full endpoints against the original saved-file checksum:
  python work/certificate_grid_review/summarize_certificates.py --source full --input-root "<printed-stage-directory>"

The three-command chain was checked by source inspection in this revision;
commands 2 and 3 have NOT been freshly executed together after raw rebuilding.
The full archived cross-tab was executed on the existing saved full endpoints.
Do not describe the inspected regeneration chain as a completed fresh raw run.
Use --reconstruct-only as shown: the older standalone --raw end-to-end wrapper
also rebuilds its historical manuscript and would compare that historical TeX
against the current paper. This recipe bypasses that obsolete TeX step.

The current default certificate replay DOES NOT download or regenerate BLEM
endpoints. It reruns the public 60,264 comparisons only; the archived full
66,096-comparison table/report records the local saved-endpoint check. Full
results must not be represented as a fresh default-package BLEM replay.

Files
grid_counts.csv: every cohort/access/gap/mask-pattern/block-size/tolerance cell,
  pooling the three pre-existing mask seeds and all six model pairs.
grid_seed_counts.csv: the same grid with each seed retained separately.
cohort_counts.csv: all 18 full-scope cohort/access/tolerance combinations, or all
  12 public-scope combinations; no pooling of exact and uncertain total results.
table_rows.tex: those cohort rows, columns cohort/access/tolerance/n/both/
  paired-only/neither/separate-only, ready for the manuscript table.
verification.json: scope, source SHA-256 hashes, script hash, output checksums,
  exact counts, numerical rules, assertions and the 540-comparison example.

Information and numerical rules
Source outputs/study_period_archive.py computes both methods from each common
closed daily observation/aggregate snapshot and sums endpoints over eligible
days. All days contain 24 target intervals. The full-period definition, access
boundaries and known-copy reconstruction are documented in the archived
work/period_archive_protocol.txt and study_period_archive_manifest.json.
The new summary joins on cohort, meter, model pair, gap, mask pattern, seed,
block size, total tolerance and access regime. It checks identical reference
contrasts, denominators, observed counts, reconstructed/deduced counts and scale
for each matched pair. This is a summary of the saved endpoint evidence; it does
not independently rerun the historical snapshot reconstruction or prove the
endpoint implementation from scratch. The existing archive replay handles that.

An issued certificate uses the ORIGINAL endpoint-specific numerical margin:
  lower > 1e-9*max(1,abs(lower),abs(upper)), or
  upper < -1e-9*max(1,abs(lower),abs(upper)).
Reference enclosure is checked to 1e-8*max(1,abs(reference)); interval nesting
uses 1e-8*max(1,absolute values of all four endpoints). The script verifies all
saved decisions, zero errors, no separate-only/opposite certificates, and full
Cartesian-grid inclusion for every meter/model pair. These are floating-point
numerical checks, not formal interval-arithmetic certification.

Interpretation
The high-demand mask is an oracle stress and its repeated seeds are retained as
in the frozen design. Repeated model pairs, scenarios and seeds are dependent;
counts are descriptive scenario counts, not independent samples or a new cohort.
The 30-consumer unused-consumer replication and later UK acquisition studies are
different experiments and are not silently pooled into this original grid.
Any headline must keep the comparator and information access explicit. These
results show the value of a joint certificate versus separate-loss bounds. They
do not show a new forecasting accuracy gain, superiority to donor imputation,
paid-query savings or a journal acceptance probability.
