"""Rebuild the external decision-cost revision from verified, frozen evidence.

--freeze is used once by the authoring workflow after independent checks.
Ordinary reproduction requires the shipped release manifest and exact bytes.
Earlier manuscript builders and their source evidence are not modified.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'work/external_deadline'
BASELINE_SHA = '3d8ece5b7d2af6447e197d9c27cd2edbf5f4c4210dec81b8b423b8cf9ca70845'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    baseline = BASE/'prior_release/revised_manuscript.tex'
    if sha(baseline) != BASELINE_SHA:
        raise AssertionError('Historical manuscript baseline changed')
    for p in [BASE/'source/lcl_reference_verification.json',
              BASE/'validation/independent_verification.json',
              BASE/'test/independent_verification.json']:
        if json.loads(p.read_text())['status'] != 'passed':
            raise AssertionError('Independent verification did not pass: '+str(p))
    sys.path.insert(0, str(BASE/'editorial'))
    from integrate_external import integrate_external, audit_preservation
    from make_results import generate
    result_fragment, summary = generate(ROOT)
    summary['bibliography_latex'] = r'''\bibitem{lcl} UK Power Networks, ``SmartMeter Energy Consumption Data in
London Households,'' London Datastore, dataset, accessed 11 October 2026.
Official full archive, CC BY 4.0.
\url{https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d}.
\bibitem{refitraw} D. Murray, L. Stankovic, and V. Stankovic,
``REFIT: Electrical Load Measurements,'' University of Strathclyde, dataset,
2015. Raw release \texttt{REFIT\_RAW\_081116.7z}, CC BY 4.0.
\url{https://doi.org/10.15129/31da3ece-f902-4e95-a093-e0a9536983c4}.
'''
    summary['supplementary_latex'] = r'''The entry point for the present external revision is
\texttt{python} \path{work/reproduce_external_revision.py}. It checks the bundled
literal LCL source subset, independently replays all validation and test
trajectories and summaries, and reconstructs this manuscript in an isolated
workspace. The \texttt{--small} route runs synthetic checks without reading
the large data. The \texttt{--refit} route reruns all external model fits and
acquisition from bundled hourly references; \texttt{--raw}, with the pinned
official archive and extracted CSV paths, first reconstructs those references
from the complete source. The documentation records commands, source hashes,
measured runtimes and the scope of each check. Saved-trajectory replay does
not imply a fresh fitting run. The original completed 60-model external
fitting execution is separately documented, including an earlier input-date
serialization failure and its unchanged-design correction. No test outcomes
were produced by that failed execution.

The first independent trajectory replay also detected aliasing in saved
intermediate observation snapshots. The logging assignment now copies its
array. The affected snapshots were reconstructed from their saved prior
states, recorded batch answers and totals; query choices, bounds, costs,
decisions and numerical summaries were unchanged. Original compressed
traces, execution metadata and evaluator source are retained. The independent
checker requires each original discrepancy to equal exactly the next
batch's recorded reveals and verifies the corrected state separately.
This disclosed logging repair is not a new policy run.

The supplement contains the selected literal LCL rows with attribution,
all considered household quality counts, model inputs, every issued forecast,
reference targets, archive source traces, acquisition sequences and per-case
and aggregate results. The full 8.54~GB raw CSV and extraction tool are
obtained separately using the documented official URL. Earlier historical
reproduction routes remain included with their original evidence and
redistribution boundaries. A release manifest distinguishes newly executed
external checks from byte-identical historical evidence carried forward.
'''
    design = (BASE/'editorial/external_design.tex').read_text(encoding='utf-8')
    old = baseline.read_text(encoding='utf-8')
    revised = integrate_external(old, design, result_fragment, summary)
    revised = revised.replace(r'\texttt{research\_supplement.zip}',
                              r'\path{research_supplement.zip}')
    revised = revised.replace(
        'The audit operates on saved predictions; it requires neither model gradients\nnor an additional fitted missing-shape model.',
        'The certificate and our robust recovery policies operate on saved predictions;\nthey require neither model gradients nor an additional fitted missing-shape\nmodel. Model-based acquisition comparators may use a fitted surrogate.')
    revised = revised.replace(
        'distributed UCI period traces and interval aggregates and rebuilds the\nmanuscript.',
        'distributed UCI period traces and interval aggregates and rebuilds the\ncorresponding historical manuscript. The external-revision entry point above\nrebuilds the present manuscript.')
    revised = revised.replace(
        '\\cite{uci,portugal,blem}. Reproduction code',
        '\\cite{uci,portugal,blem,lcl}. Reproduction code')
    revised = revised.replace(
        'In the energy audit, permitted direct copies from the saved forecast archive',
        'In the historical energy audits, permitted direct copies from the saved forecast archive')
    revised = revised.replace(
        'Randomization improves worst expected width but does not improve the\nobserved energy-audit outcomes.',
        'In the historical saved-archive experiments, randomization improves worst\nexpected width but worsens the reported realized-width and certification outcomes.')
    revised = revised.replace(
        'retrospectively; UCI totals are constructed from complete traces, and retained',
        'retrospectively; UCI and LCL totals are constructed from reference traces, and retained')
    check = audit_preservation(old, revised)
    abstract = re.search(r'(?s)\\begin\{abstract\}(.*?)\\end\{abstract\}', revised).group(1)
    abstract_words = len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", abstract))
    if not 150 <= abstract_words <= 250:
        raise AssertionError(f'Abstract word count {abstract_words} outside journal range')
    expected_path = ROOT/'outputs/external_release_manifest.json'
    evidence = [baseline, BASE/'editorial/external_design.tex',
                BASE/'editorial/make_results.py', BASE/'editorial/integrate_external.py',
                BASE/'review/decision_corollary.tex', Path(__file__),
                BASE/'fitted/fit_metadata.json', BASE/'fitted/prepared.json',
                BASE/'source/lcl_reference_verification.json']
    for period in ['validation','test']:
        for name in ['headline_summary.json','coverage_curves.csv','cost_summary.csv',
                     'pair_curves.csv','month_curves.csv','household_curves.csv',
                     'independent_verification.json','run_result.json']:
            evidence.append(BASE/period/name)
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in evidence}
    content = revised.encode('utf-8')
    result_sha = hashlib.sha256(content).hexdigest()
    if args.freeze:
        expected_path.write_text(json.dumps({'status':'frozen', 'inputs':pins,
            'manuscript_sha256':result_sha, 'baseline_sha256':BASELINE_SHA,
            'scope':'Exact source composition after source and trajectory checks; does not imply journal acceptance.'}, indent=2)+'\n')
    else:
        expected = json.loads(expected_path.read_text())
        if expected['inputs'] != pins:
            raise AssertionError('Composition inputs differ from the frozen release')
        if expected['manuscript_sha256'] != result_sha:
            raise AssertionError('Reconstructed manuscript differs from frozen release')
    (ROOT/'outputs/revised_manuscript.tex').write_bytes(content)
    report = {'status':'passed', 'expected_source_sha256':result_sha,
              'actual_source_sha256':sha(ROOT/'outputs/revised_manuscript.tex'),
              'exact_manuscript_bytes':True, 'abstract_rough_words':abstract_words,
              'preservation':check, 'inputs':pins}
    (ROOT/'outputs/external_manuscript_reconstruction.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['inputs','preservation']},indent=2))

if __name__ == '__main__':
    main()
