"""Independent rational check of the two-target family's batch support.

Only the Python standard library is used. No manuscript producer or existing
checker is imported. This checks explicit finite witnesses, not an exhaustive
literature search or a numerical proof of the universal theorem.

At an adverse record, queried u, v, and z coordinates are all zero. The core
polytope can therefore be optimized by choosing t at an allowed endpoint,
and u and v at their allowed endpoints. This avoids the vertex-LP machinery
in the existing checker. Independent box extrema complete each target width.
"""
from fractions import Fraction as Q
from itertools import combinations, product
from pathlib import Path
import argparse
import hashlib
import json
import time


def core_points(t_value, batch):
    for t in ((t_value,) if 0 in batch else (Q(0), Q(1))):
        us = (Q(0),) if 1 in batch else (Q(0), t)
        vs = (Q(0),) if 2 in batch else (Q(0), 1-t)
        for u, v in product(us, vs):
            yield t, u, v


def width(core, box, t_value, batch):
    values = [sum(a*x for a, x in zip(core, p))
              for p in core_points(t_value, batch)]
    return max(values)-min(values)+sum(abs(a) for j, a in enumerate(box, 3)
                                      if j not in batch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(Path(__file__).with_name('support_report.json')))
    args = ap.parse_args()
    started = time.perf_counter()
    rows = []
    evaluations = 0
    for m in (3, 4, 5, 8, 10, 16, 24):
        h = Q(m*(2*m+3), 4)
        big_m = h-m
        a = [Q(j)+Q(1, 4) for j in range(1, m+1)]
        b = [Q(m+1-j)+Q(1, 4) for j in range(1, m+1)]
        d = [x-y for x, y in zip(a, b)]
        coeffs = (((big_m, Q(m), Q(0)), a),
                  ((-big_m, Q(0), Q(m)), b),
                  ((2*big_m, Q(m), -Q(m)), d))
        initial = [width(core, box, Q(0), ()) for core, box in coeffs]
        assert initial[:2] == [2*h, 2*h]
        assert initial[2] == 2*(h+sum(x for x in d if x>0))
        batches = [batch for n in range(3) for batch in combinations(range(m+3), n)]
        # Strict upper end is excluded analytically. Values below it test
        # the boundary convention independently of the nominal half threshold.
        thresholds = (Q(1, 2)-1/(8*h), Q(1, 2), Q(1, 2)+Q(249,1000)/(2*h))
        matrices = []
        for tau in thresholds:
            successes = []
            for i in range(1, m+1):
                t = Q(2*i-1, 2*m)
                pair_success, triple_success = [], []
                for batch in batches:
                    widths = [width(core, box, t, batch) for core, box in coeffs]
                    evaluations += 3
                    if all(w<=tau*w0 for w, w0 in zip(widths[:2], initial[:2])):
                        pair_success.append(batch)
                    if all(w<=tau*w0 for w, w0 in zip(widths, initial)):
                        triple_success.append(batch)
                assert pair_success == [(0, i+2)], (m, i, tau, pair_success)
                assert triple_success == pair_success
                successes.append([0, i+2])
            matrices.append({'threshold':str(tau), 'unique_successful_batches':successes})
        # At the lowest admissible threshold, the closed intervals
        # [(j-1)/m,j/m] cover [0,1]. Exact endpoint checks establish that
        # their two scalar widths meet that threshold. Third width after t
        # is constant. Affinity extends the endpoint checks across each cell.
        tau = thresholds[0]
        for j in range(1, m+1):
            for t in (Q(j-1,m), Q(j,m)):
                ws = [width(core, box, t, (0,j+2)) for core,box in coeffs]
                evaluations += 3
                assert all(w<=tau*w0 for w,w0 in zip(ws,initial))
        rows.append({'m':m, 'batches_including_empty_and_singletons':len(batches),
                     'adverse_record_count':m, 'minimum_support_for_positive_success':m,
                     'optimal_batch_mass':str(Q(1,m)), 'checks':matrices})
    report = {'status':'PASS', 'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'arithmetic':'exact fractions; no solver, tolerance, or producer imports',
              'actual_width_evaluations':evaluations, 'families':rows,
              'proof_scope':'Adverse identity matrix forces all m branches for positive success and unique uniform optimum; full continuum lower guarantee follows from closed-cell coverage and affine endpoint bounds.',
              'limitations':'Finite executable instances corroborate the printed all-m proof; no historical-priority or empirical-tie claim.',
              'seconds':time.perf_counter()-started}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status':'PASS','families':len(rows),'width_evaluations':evaluations,
                      'seconds':report['seconds']}))


if __name__=='__main__':
    main()
