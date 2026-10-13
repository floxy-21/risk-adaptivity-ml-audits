"""Decision gate for an already computed sharp model-comparison interval.

Input gap is loss(model_a)-loss(model_b). This interface consumes evaluator-
visible endpoints and a proposed direction only; it has no reference target.
It does not calculate the endpoints or validate their provenance.
"""
from __future__ import annotations

import json
import math
import sys


def certificate_gate(lower: float, upper: float, proposed_direction: int) -> dict:
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise ValueError("Expected finite ordered interval endpoints")
    if proposed_direction not in (-1, 0, 1):
        raise ValueError("Direction must be -1 (model_a), 1 (model_b), or 0 (tie)")
    margin = 1e-9 * max(1.0, abs(lower), abs(upper))
    certified = 1 if lower > margin else -1 if upper < -margin else 0
    if proposed_direction == 0:
        action = "no_strict_proposal"
    elif certified == proposed_direction:
        action = "allow"
    elif certified == -proposed_direction:
        action = "contradict"
    else:
        action = "hold"
    opposite_endpoint = lower if proposed_direction > 0 else upper if proposed_direction < 0 else None
    opposite_supported = bool(proposed_direction and
        (opposite_endpoint < -margin if proposed_direction > 0 else opposite_endpoint > margin))
    return {"action": action, "certified_direction": certified, "margin": margin,
            "opposite_completion_supported_by_sharp_endpoint": opposite_supported,
            "opposite_endpoint": opposite_endpoint}


if __name__ == "__main__":
    packet = json.load(sys.stdin)
    print(json.dumps(certificate_gate(packet["lower"], packet["upper"],
                                     packet["proposed_direction"]), indent=2))
