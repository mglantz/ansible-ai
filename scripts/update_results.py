#!/usr/bin/env python3
"""
update_results.py

Reads molecule_result.json produced during a test run and appends
a new run entry to results/results.json.

Usage:
    python scripts/update_results.py \
        --agent claude-sonnet \
        --molecule-result molecule_result.json \
        --run-id ${{ github.run_id }} \
        --commit ${{ github.sha }}
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--molecule-result", default="molecule_result.json")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--results-file", default="results/results.json")
    args = parser.parse_args()

    mol = load_json(args.molecule_result)

    skipped = mol.get("skipped", False)
    if skipped:
        overall_status = "pending"
    elif mol.get("passed"):
        overall_status = "passed"
    else:
        overall_status = "failed"

    run_entry = {
        "run_id": args.run_id,
        "commit": args.commit[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "elapsed_molecule": mol.get("elapsed_seconds", 0),
        "molecule_output": mol.get("output_tail", "")[-2000:],
        "error": mol.get("error", ""),
    }

    results_path = Path(args.results_file)
    results = json.loads(results_path.read_text()) if results_path.exists() else {"agents": []}

    for ag in results.get("agents", []):
        if ag["id"] == args.agent:
            ag.setdefault("runs", []).insert(0, run_entry)
            ag["runs"] = ag["runs"][:50]
            break
    else:
        print(f"[!] Agent '{args.agent}' not found in results.json — skipping.")

    results["last_updated"] = datetime.now(timezone.utc).isoformat()
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2))
    print(f"[✓] Updated {args.results_file}: agent={args.agent} status={overall_status}")


if __name__ == "__main__":
    main()
