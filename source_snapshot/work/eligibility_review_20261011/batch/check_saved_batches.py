"""Independent read-only accounting of every archived two-reading stage."""
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect(name):
    path = ROOT / 'work/external_deadline' / name / 'trajectories.jsonl'
    counts = defaultdict(Counter)
    issues = []
    undersized = []
    cases = 0
    with path.open(encoding='utf-8') as f:
        for line in f:
            case = json.loads(line)
            cases += 1
            coeff = [2 * (b - a) / len(case['a']) for a, b in zip(case['a'], case['b'])]
            for policy, trajectory in case['policies'].items():
                c = counts[policy]
                c['cases'] += 1
                paid = 0
                seen = set()
                for stage in trajectory['stages']:
                    c['stages'] += 1
                    before, query = stage['before'], stage['batch']
                    c['queries'] += len(query)
                    c[f'batch_size_{len(query)}'] += 1
                    c['two_unknown_block_stages'] += int(any(sum(x is None for x in before[g:g+6]) == 2 for g in range(0, len(before), 6)))
                    bad = []
                    if len(query) != len(set(query)) or seen.intersection(query):
                        bad.append('duplicate_query')
                    if any(before[i] is not None for i in query):
                        bad.append('query_already_known')
                    stage_limit = min(2, 6-paid)
                    if len(query) > stage_limit:
                        bad.append('stage_or_total_cap')
                    active_capacity = 0
                    active = []
                    for g in range(0, len(before), 6):
                        unknown = [i for i in range(g, g+6) if before[i] is None]
                        qg = [i for i in query if g <= i < g+6]
                        if qg and len(qg) > len(unknown)-1:
                            bad.append(f'redundant_final_record_block_{g//6}')
                        energy = case['totals'][g//6] - math.fsum(x for x in before[g:g+6] if x is not None)
                        cs = [coeff[i] for i in unknown]
                        if energy > 0 and len(cs) >= 2 and max(cs) > min(cs):
                            active_capacity += len(unknown)-1
                            active.extend(unknown)
                        if len(unknown) == 1:
                            bad.append(f'unclosed_singleton_block_{g//6}')
                    maximum_size = min(stage_limit, active_capacity)
                    if len(query) < maximum_size:
                        c['smaller_than_initial_active_capacity'] += 1
                        if len(undersized) < 12:
                            undersized.append({'case': case['case_id'], 'policy': policy, 'query': query,
                                              'initial_active_capacity': active_capacity, 'stage_limit': stage_limit})
                    if set(query)-set(active):
                        bad.append('query_outside_positive_nonconstant_block')
                    paid += len(query)
                    seen.update(query)
                    if stage['cost'] != paid:
                        bad.append('cumulative_cost_mismatch')
                    if bad:
                        c['invalid_stages'] += 1
                        issues.append({'case': case['case_id'], 'policy': policy, 'query': query, 'issues': bad})
                if paid != trajectory['paid_requests'] or set(trajectory['paid_indices']) != seen:
                    issues.append({'case': case['case_id'], 'policy': policy, 'issues': ['final_cost_or_paid_indices_mismatch']})
    return {'period': name, 'cases': cases, 'source_sha256': sha(path),
            'policies': {k: dict(v) for k, v in counts.items()}, 'issues': issues,
            'undersized_examples': undersized}


if __name__ == '__main__':
    results = [inspect(name) for name in ('validation', 'test')]
    report = {'status': 'passed' if not any(r['issues'] for r in results) else 'failed',
              'scope': 'Every saved prior two-reading policy stage; independent trace accounting, not rerunning acquisition or model fitting.',
              'script_sha256': sha(Path(__file__)), 'periods': results}
    path = OUT / 'saved_batch_accounting.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
