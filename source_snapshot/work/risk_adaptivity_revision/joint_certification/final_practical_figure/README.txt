FIGURE: EXACT ACQUISITION GEOMETRY AND RECORDED PRECISION

This figure uses existing results only. No forecast, policy, query budget,
threshold, dataset or reported outcome changes.

Panel A uses the exact serialized binary64-derived rational coefficients
from precision_external_results/plans.json for external/hpm_1/2025-07-05/12.
It plots all four conditional worst-width envelopes after boundary2 and
their selected minimum. The switch is402983999413455277/771030112647101785
(approximately0.5226566288441445); maximum selected width is approximately
0.4773433711558554. Both agree with the main printed exact certificate.
The producer computes all relevant line intersections in rational arithmetic;
no rounded printed matrix or arbitrary plotting grid determines the curves.

Panel B reads existing threshold_summary.csv and forms percentages directly
from integer adaptive/fixed/greedy success counts, not rounded table entries.
There are30 points: five thresholds, three policies, two source panels.
The underlying replay uses the declared1e-8 comparison tolerance and remains
exploratory. These points are recorded frequencies, not minimax probabilities.

From the supplement root:
  python work/risk_adaptivity_revision/joint_certification/final_practical_figure/check_figure.py --output outputs/final_practical_figure_check.json

This standard-library checker independently rebuilds normalized source
coefficients, derives24 conditional affine lines by segment allocation,
checks every exact envelope breakpoint and all30 replay percentages.
It does not import the producer or trust its numerical plot.

To regenerate exact data and the self-contained inline TikZ figure:
  python work/risk_adaptivity_revision/joint_certification/final_practical_figure/build_figure.py

This overwrites only this figure directory's figure_data.json and
figure_fragment.tex. The manuscript builder inserts the latter literally;
it requires TikZ in the preamble and reads no external image or data files.
Its width is0.98 of the document text width and its text is scriptsize.

Optional standalone PDF/PNG rendering:
Create a separate rendering environment and install requirements-render.txt,
then run the same build_figure.py command with --render. Rendering does not
require or alter the scientific study's pinned numerical environment.
The optional exported PDF/PNG use Matplotlib3.10.7; the scientific figure
coordinates themselves use only Fraction arithmetic and source counts.

Files:
  figure_data.json: exact coordinates, coefficients, provenance and input hashes.
  figure_fragment.tex: self-contained main-manuscript Figure1.
  practical_guarantee_replay.pdf/.png: standalone shareable figure.
  independent_check.json: independent exact verification.
  clarification.tex: scalar-Helly versus joint-objective scope explanation.

The clarification removes a possible misreading; it does not add a theorem.
In particular, loss of the scalar concavity/convex-failure-set premise alone
does not prove an adaptive advantage or a required three/four-action cover.
The original matching certificates establish each stated strict separation.
