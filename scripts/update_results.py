#!/usr/bin/env python3
"""
update_results.py

Reads agent_meta.json and molecule_result.json produced during a test run
and appends a new run entry to results/results.json.

Usage:
    python update_results.py \
        --agent claude-sonnet \
        --agent-meta agent_meta.json \
        --molecule-result molecule_result.json \
        --run-id ${{ github.run_id }} \
        --commit ${{ github.sha }}
"""

import argparse
import json
import os
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
    parser.add_argument("--agent-meta", default="agent_meta.json")
    parser.add_argument("--molecule-result", default="molecule_result.json")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--results-file", default="results/results.json")
    args = parser.parse_args()

    agent_meta = load_json(args.agent_meta)
    molecule_result = load_json(args.molecule_result)

    # Determine overall status
    gen_status = agent_meta.get("status", "unknown")
    mol_passed = molecule_result.get("passed", False)
    mol_error = molecule_result.get("error", "")

    if gen_status in ("api_error", "parse_error"):
        overall_status = gen_status
    elif mol_passed:
        overall_status = "passed"
    else:
        overall_status = "failed"

    run_entry = {
        "run_id": args.run_id,
        "commit": args.commit[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "elapsed_generation": agent_meta.get("elapsed_generation", 0),
        "elapsed_molecule": molecule_result.get("elapsed_seconds", 0),
        "molecule_output": molecule_result.get("output_tail", "")[-2000:],
        "error": mol_error or agent_meta.get("error", ""),
        "tasks_preview": agent_meta.get("tasks_preview", ""),
    }

    # Load current results
    results_path = Path(args.results_file)
    results = json.loads(results_path.read_text()) if results_path.exists() else {"agents": []}

    # Find or create agent entry
    agent_found = False
    for ag in results.get("agents", []):
        if ag["id"] == args.agent:
            if "runs" not in ag:
                ag["runs"] = []
            ag["runs"].insert(0, run_entry)  # newest first
            ag["runs"] = ag["runs"][:50]     # keep last 50 runs
            agent_found = True
            break

    if not agent_found:
        print(f"[!] Agent '{args.agent}' not found in results.json — skipping.")

    results["last_updated"] = datetime.now(timezone.utc).isoformat()

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2))
    print(f"[✓] Updated {args.results_file} with run {args.run_id} for agent {args.agent}")
    print(f"    Status: {overall_status}")


if __name__ == "__main__":
    main()
