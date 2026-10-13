"""Run the evaluator-only JSON audit interface on an existing snapshot."""
import argparse
import json
from pathlib import Path
from audit_api import audit_snapshot

parser = argparse.ArgumentParser()
parser.add_argument("snapshot", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
result = audit_snapshot(json.loads(args.snapshot.read_text(encoding="utf-8")))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({k: result[k] for k in ("meter", "day", "free_copy_count", "remaining_missing_count", "paid_queries", "certified_best_model")}))
