"""Structural fixture only; writes no manuscript or result-bearing document."""
from pathlib import Path
import hashlib
import json
from integrate_external import integrate_external, audit_preservation, DECISION_COROLLARY

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    source = ROOT/'outputs/revised_manuscript.tex'
    baseline = source.read_text(encoding='utf-8')
    design = r'\subsection{Synthetic structural fixture: design} No empirical evidence is asserted.'
    results = r'\subsection{Synthetic structural fixture: results} No empirical evidence is asserted.'
    integrated = integrate_external(baseline, design, results, {'verified': True})
    report = audit_preservation(baseline, integrated)
    assert integrated == integrate_external(baseline, design, results, {'verified': True})
    assert DECISION_COROLLARY.strip() == (ROOT/'work/external_deadline/review/decision_corollary.tex').read_text(encoding='utf-8').strip()
    refused = False
    try:
        integrate_external(baseline, design, results, {'verified': False})
    except ValueError:
        refused = True
    assert refused
    refused = False
    try:
        integrate_external(integrated, design, results, {'verified': True})
    except ValueError:
        refused = True
    assert refused
    report.update(test_kind='Structural integration of explicit synthetic non-result placeholders; no output manuscript written.',
                  unverified_results_rejected=True, reintegration_rejected=True, pure_repeated_output_identical=True,
                  decision_corollary_exact_copy=True,
                  helper_sha256=hashlib.sha256((HERE/'integrate_external.py').read_bytes()).hexdigest())
    (HERE/'structural_check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
