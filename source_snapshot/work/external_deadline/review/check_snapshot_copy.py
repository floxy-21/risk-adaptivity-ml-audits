"""Regression fixture: later reveals must not mutate earlier audit snapshots.

Uses only a constructed equal-loss record, not any external data or outcomes.
Imports the current executable trajectory but edits no evaluator/acquisition
implementation. The old aliasing bug would make earlier after snapshots
contain targets revealed in the next stage and fail the assertions below.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
EXTERNAL = HERE.parent
sys.path.insert(0, str(EXTERNAL))
from evaluate import POLICIES, RevealOracle, closure, trajectory


def same(left, right):
    return np.array_equal(np.isnan(left), np.isnan(right)) and np.allclose(left, right, equal_nan=True, rtol=0, atol=1e-14)


def main():
    truth = np.ones(24)
    first = np.ones(24)
    second = np.ones(24)
    offsets = np.array([.1, .2, .3, .4, .5, .6])
    first[:6] -= offsets
    second[:6] += offsets
    totals = truth.reshape(4, 6).sum(axis=1)
    initial = truth.copy()
    initial[:6] = np.nan
    initial, _ = closure(initial, totals)
    records = []
    for policy in POLICIES:
        result = trajectory(policy, first, second, initial, totals, RevealOracle(truth),
                            np.ones(24), .25, ('snapshot-copy-regression',))
        stages = result['stages']
        assert len(stages) >= 2, 'Fixture must exercise subsequent reveals'
        assert result['final_status'] == 'numerical_tie'
        expected = initial.copy()
        transitions = 0
        for index, stage in enumerate(stages):
            assert same(stage['before'], expected), 'Before snapshot differs from prior completed stage'
            expected[stage['batch']] = stage['revealed']
            expected, deductions = closure(expected, totals)
            assert same(stage['after'], expected), 'After snapshot was modified by a subsequent reveal'
            if index+1 < len(stages):
                later = stages[index+1]
                assert all(np.isnan(stage['after'][i]) for i in later['batch']), 'Earlier snapshot knows a later query'
                assert same(stage['after'], later['before']), 'Completed and next-initial snapshots disagree'
                assert not np.shares_memory(stage['after'], later['after']), 'Stage snapshots share mutable storage'
                transitions += 1
        # A caller's mutation of another saved stage must not contaminate the
        # first one either. This catches direct storage aliasing independently
        # of whether the particular queried values happen to match.
        frozen = stages[0]['after'].copy()
        stages[-1]['after'][0] = 12345.
        assert same(stages[0]['after'], frozen)
        assert np.isnan(initial[:6]).all(), 'Initial fixture state was mutated'
        records.append({'policy':policy,'stages':len(stages),'checked_later_reveal_transitions':transitions,
                        'paid_requests':result['paid_requests'],'snapshot_independence':'passed'})
    report = {'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
              'scope':'Synthetic multistage snapshot regression only; no external data read.',
              'policies':records,'evaluator_sha256':hashlib.sha256((EXTERNAL/'evaluate.py').read_bytes()).hexdigest(),
              'fixture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'snapshot_copy_check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
