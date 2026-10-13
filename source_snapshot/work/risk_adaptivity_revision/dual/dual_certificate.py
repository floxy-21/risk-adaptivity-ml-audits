"""Expose and check a hardest completion from the unchanged compact LP.

The historical solver/API files are deliberately not modified. The last sum(m_g)
inequalities in that solver are its scenario/epigraph rows; their negative dual
multipliers give nonnegative target masses in sorted-coordinate order. Because
the implementation also bounds epigraph variables below by zero, these masses
can sum to less than E_g. Completing that slack preserves every lower bound.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOLVER_PATH = ROOT / "work/randomized_recovery_root/compact_randomized.py"
ORACLE_PATH = ROOT / "work/new_direction_randomized/randomized_recovery_screen.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _solver():
    spec = importlib.util.spec_from_file_location("unchanged_compact_for_dual", SOLVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    """Execute the existing function verbatim, without its unrelated data imports."""
    source = ORACLE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ORACLE_PATH))
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "pricing_oracle"]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one historical weighted pricing oracle")
    module = ast.Module(body=matches, type_ignores=[])
    namespace = {}
    exec(compile(module, str(ORACLE_PATH), "exec"), namespace)
    return namespace["pricing_oracle"], hashlib.sha256(
        ast.get_source_segment(source, matches[0]).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Block:
    indices: tuple
    coefficients: tuple
    energy: float


def width_at(coefficients, values, query):
    """Independent direct evaluation of the conditional-width identity."""
    query = set(query)
    offset = 0
    answer = 0.0
    for cs, ys in zip(coefficients, values):
        retained = [(float(c), float(y)) for i, (c, y) in enumerate(zip(cs, ys)) if offset + i not in query]
        if len(retained) > 1:
            answer += (max(c for c, _ in retained) - min(c for c, _ in retained)) * math.fsum(y for _, y in retained)
        offset += len(cs)
    return float(answer)


def solve_with_dual_completion(coefficients, energies, budget, tolerance=1e-8):
    """Return a feasible completion, pricing lower bound, and full diagnostics.

    This is a floating-point optimality check, not interval arithmetic. Returned
    indices refer to the original concatenated blocks. Early stopping and
    repeated/redundant queries cannot evade the theoretical lower bound.
    """
    cs = [np.asarray(c, dtype=float) for c in coefficients]
    es = [float(e) for e in energies]
    if len(cs) != len(es) or isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError("Invalid blocks, totals, or integer budget")
    if any(c.ndim != 1 or not np.isfinite(c).all() for c in cs):
        raise ValueError("Coefficients must be finite vectors")
    if any(not math.isfinite(e) or e < 0 or (e > 0 and len(c) == 0) for c, e in zip(cs, es)):
        raise ValueError("Invalid nonnegative residual total")
    active = [g for g, (c, e) in enumerate(zip(cs, es)) if e > 0 and len(c) > 1 and np.ptp(c) > 0]
    raw = [np.zeros(len(c)) for c in cs]
    source_hash_before = sha(SOLVER_PATH)
    captures = []
    if active:
        solver = _solver()
        original_linprog = solver.linprog

        def capture(c, *args, **kw):
            options = dict(kw.get("options", {}))
            options.update(threads=1, primal_feasibility_tolerance=1e-9, dual_feasibility_tolerance=1e-9)
            kw["options"] = options
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Unrecognized options detected.*")
                res = original_linprog(c, *args, **kw)
            if not res.success:
                raise RuntimeError(res.message)
            c = np.asarray(c)
            ae, au = kw["A_eq"], kw["A_ub"]
            be, bu = np.asarray(kw["b_eq"]), np.asarray(kw["b_ub"])
            captures.append((res, {
                "primal_feasibility_absolute": float(max(np.max(np.abs(ae @ res.x - be), initial=0),
                    np.max(au @ res.x - bu, initial=0), np.max(-res.x, initial=0), 0)),
                "dual_sign_violation_absolute": float(max(np.max(res.ineqlin.marginals, initial=0),
                    np.max(-res.lower.marginals, initial=0), 0)),
                "stationarity_absolute": float(np.max(np.abs(c - ae.T @ res.eqlin.marginals
                    - au.T @ res.ineqlin.marginals - res.lower.marginals), initial=0)),
                "dual_objective": float(be @ res.eqlin.marginals + bu @ res.ineqlin.marginals),
                "solver_status": int(res.status),
                "solver_message": str(res.message),
            }))
            return res

        solver.linprog = capture
        try:
            solved = solver.solve_compact([cs[g] for g in active], [es[g] for g in active], budget, return_metadata=True)
        finally:
            solver.linprog = original_linprog
        if len(captures) != 1:
            raise RuntimeError("Expected exactly one compact LP solve")
        res, lp_diagnostics = captures[0]
        n = sum(len(cs[g]) for g in active)
        multipliers = -np.asarray(res.ineqlin.marginals[-n:])
        offset = 0
        for g, order in zip(active, solved["metadata"]["original_index_maps"]):
            raw[g][np.asarray(order, dtype=int)] = multipliers[offset:offset + len(cs[g])]
            offset += len(cs[g])
        primal = float(solved["value"])
        dimensions = {k: solved[k] for k in ("variables", "equalities", "inequalities")}
    else:
        primal = 0.0
        dimensions = {"variables": 0, "equalities": 0, "inequalities": 0}
        lp_diagnostics = {"primal_feasibility_absolute": 0.0, "dual_sign_violation_absolute": 0.0,
            "stationarity_absolute": 0.0, "dual_objective": 0.0, "solver_status": 0,
            "solver_message": "All block widths identically zero; no LP required."}
    if sha(SOLVER_PATH) != source_hash_before:
        raise RuntimeError("Historical solver source changed during check")

    completed, mass_reports = [], []
    for g, (w, energy) in enumerate(zip(raw, es)):
        scale = max(1.0, energy)
        if np.min(w, initial=0) < -tolerance * scale or float(w.sum()) > energy + tolerance * scale:
            raise ArithmeticError("Extracted dual masses violate their simplex inequality")
        y = np.maximum(w, 0.0)
        clipped_l1 = float(np.abs(y - w).sum())
        excess = max(0.0, math.fsum(y) - energy)
        # A tiny numerical excess is removed proportionally and explicitly logged.
        if excess > 0:
            y *= energy / math.fsum(y)
        slack = energy - math.fsum(y)
        if len(y):
            # The lowest-index coordinate is a fixed deterministic completion rule.
            y[0] += slack
        if np.min(y, initial=0) < -tolerance * scale or abs(math.fsum(y) - energy) > tolerance * scale:
            raise ArithmeticError("Mass completion failed")
        completed.append(y.tolist())
        mass_reports.append({"block": g, "raw_sum": float(math.fsum(w)), "required_total": energy,
            "negative_clip_l1": clipped_l1, "roundoff_excess_removed": excess,
            "nonnegative_slack_added": max(0.0, slack), "total_l1_change": float(np.abs(y - w).sum()),
            "completed_sum": float(math.fsum(y)), "completed_minimum": float(np.min(y)) if len(y) else None})

    oracle, oracle_hash = _oracle()
    blocks, weights = [], {}
    offset = 0
    for cs_g, ys_g, energy in zip(cs, completed, es):
        ids = tuple(range(offset, offset + len(cs_g)))
        if len(ids):
            blocks.append(Block(ids, tuple(float(c) for c in cs_g), energy))
            weights.update(zip(ids, ys_g))
        offset += len(cs_g)
    pricing_value, pricing_query = oracle(blocks, weights, budget)
    direct = width_at(cs, completed, pricing_query)
    initial_width = math.fsum(e * float(np.ptp(c)) for c, e in zip(cs, es) if len(c))
    objective_scale = max(1.0, initial_width)
    if abs(pricing_value - primal) > tolerance * objective_scale or abs(direct - pricing_value) > tolerance * objective_scale:
        raise ArithmeticError("Pricing and compact primal do not agree within tolerance")
    return {"primal_value": primal, "dual_completion": completed,
        "raw_scenario_dual_weights": [w.tolist() for w in raw], "mass_completion": mass_reports,
        "pricing_minimum": float(pricing_value), "pricing_query": list(pricing_query),
        "direct_width_at_pricing_query": direct, "initial_width": initial_width,
        "objective_scale": objective_scale, "primal_pricing_absolute_gap": abs(primal - pricing_value),
        "primal_pricing_normalized_gap": abs(primal - pricing_value) / objective_scale,
        "primal_dual_absolute_gap": abs(primal - lp_diagnostics["dual_objective"]),
        "lp_diagnostics": lp_diagnostics, "lp_dimensions": dimensions,
        "active_blocks": active, "solver_sha256": source_hash_before, "oracle_function_sha256": oracle_hash,
        "tolerance": tolerance, "scope": "Floating-point verification; no outward rounding or formal arithmetic certificate."}
