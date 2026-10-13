BOUNDED EDITORIAL INTEGRATION

This folder does not edit the current manuscript or regenerate old results.
Root applies its pure helper once to a separately saved pre-external TeX
baseline, after external results and independent verification are complete:

 from integrate_external import integrate_external, audit_preservation
 revised = integrate_external(baseline_text, design_fragment, results_fragment,
                               result_summary)
 report = audit_preservation(baseline_text, revised)

result_summary must have verified=True. Optional strings are:
- abstract_latex: replacement full abstract body (root checks 150-250 words).
- introduction_result_latex: concise verified external outcome, appended to
  the new practical question before the manuscript roadmap.
- external_interpretation_latex: first Discussion paragraph(s), directly
  reporting practical criterion attainment/failure and its limitations.
- conclusion_latex: replacement full Conclusion body.
- bibliography_latex: complete additional bibitems for the external source.
- supplementary_latex: additional reproducibility paragraph(s).

The design/results fragments should supply their subsection headings and
their complete verified tables/figures. A document preamble, appendix or
document environment is rejected. External reference keys must be supplied
in bibliography_latex if absent from the existing bibliography.

Editorial changes
1. Exact copy of review/decision_corollary.tex is promoted before Budgeted
   Recovery in Sharp Comparisons and Decision Guarantees. The existing regret
   identity and proof stay in their original appendix.
2. Main Experimental Design is replaced by Decision Workflow and External
   Evaluation with the supplied new design, followed by concise historical
   information/measurement/reproducibility boundaries.
3. Results start with the supplied external experiment. Historical main
   evidence retains the unchanged attribution table, adverse randomized
   table, full 28-instance scaling table and concise natural-case outcomes.
4. The entire historical Experimental Design is moved, with content and
   labels intact, to a new appendix after the existing appendices.
5. Supporting Historical Results preserves every original Results paragraph,
   table and figure. Its three tables retained in the main text appear only
   once; the original discussion still points to those same table labels.
   The worked illustration, full natural provenance and nine-case table,
   historical period grids, forecast performance grid, sensitivities,
   numerical replay history and post-review replication details are retained.
6. Main operational/limitations wording distinguishes the new stopping
   benchmark from prior nonadaptive cost conventions. No monetary/deployment
   benefit or favorable external effect is inferred by the helper.
7. Verified AISTATS2025 Okanovic et al. related work is added, explicitly
   distinguishing classifier selection from the regression certificate.
   Bibliography is reordered by first citation, with existing entry content
   unchanged.

Preservation checks
Exact full environment bodies for all existing theorem/proof/equation/align,
table and figure environments must remain. Every original label must remain
exactly once; new references must resolve. All existing bibliography entry
content must remain. The baseline currently has 25 tables, three figures,
87 labels and 34 bibliography entries. The synthetic structural fixture
preserves all 65 checked named environments, rejects unverified integration,
and rejects applying the helper a second time to an already integrated file.
No real external result is in that fixture, and no fixture manuscript is
written to outputs.

Numbering and follow-up checks
- Existing label identities remain stable; moved equations/tables/figures,
  new sections and the new corollary automatically change rendered numbers.
  Update external review/readiness reports using final labels/numbers rather
  than carrying historical numeric references forward.
- Main summaries avoid first-citing appendix-only table numbers prematurely.
  Root must run the existing citation/cross-reference check after inserting
  the actual external fragments, then verify all final float placements.
- Rendered main-text page count is not inferred from word count. The
  structural fixture cuts the old main evidence substantially; actual new
  design/results determine whether 22-26 main pages is achievable. Keep the
  existing 12pt type and table readability rather than shrinking to force it.
- Preserve the immutable earlier builder. A new wrapper should pin the saved
  baseline TeX, actual fragments, helper and verified result hashes.
- Update Data/Code Availability to identify the new wrapper, external source
  redistribution limits and exact final supplement command. The old baseline
  reproduction description remains historically accurate but no longer
  reconstructs the entire external revision by itself.

Primary literature source inspected:
https://proceedings.mlr.press/v258/okanovic25a.html
Okanovic, Kirsch, Kasper, Hoefler, Krause and Gurel, All models are wrong,
some are useful: Model Selection with Limited Labels, AISTATS2025,
PMLR258:2035-2043. The added paragraph uses its classification scope and
label-acquisition problem, not its empirical effect sizes or any unsupported
claim that its method is unsuitable for all regression settings.

Structural check (no PDF compilation and no manuscript mutation):
 python work/external_deadline/editorial/check_integration.py
VERIFIED RESULT RENDERING

make_results.py exposes generate(repository_root), which returns
(results_fragment, result_summary) without writing a file. It expects fitted/,
validation/ and test/ under work/external_deadline. Both evaluator runs,
headlines and independent verification reports must have passed, their
verified summary-file hashes must match, and their independent curves,
counts and primary criterion must agree. It never executes fitting,
acquisition or outcome selection. The wrapper owned by the root agent is
responsible for applying these strings and adding the source bibliography
and supplementary entry points to the existing manuscript.

check_make_results.py uses isolated synthetic artifacts only. It verifies
favorable, unfavorable and unreached-B80 prose; independently gated hashes;
rejection of an unfinished review or changed cost summary; and the abstract
word range. It does not inspect external outcomes or create a manuscript.
The empirical execution remains gated on completed independent verification.

