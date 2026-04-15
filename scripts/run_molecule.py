#!/usr/bin/env python3
"""
run_molecule.py

Runs `molecule test` inside an agent's directory and writes
timing + output to molecule_result.json.

Usage:
    python scripts/run_molecule.py --agent claude-sonnet
    python scripts/run_molecule.py --agent gpt-4o
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, help="Agent directory name under agents/")
    parser.add_argument("--output", default="molecule_result.json")
    args = parser.parse_args()

    agent_dir = Path(args.agent)
    if not agent_dir.exists():
        print(f"[✗] Agent directory not found: {agent_dir}", file=sys.stderr)
        sys.exit(1)

    # Detect placeholder — skip molecule if tasks.yml hasn't been filled in
    tasks_file = agent_dir / "playbook.yml"
    if tasks_file.exists():
        content = tasks_file.read_text()
        if "PLACEHOLDER" in content:
            print(f"[!] tasks.yml for '{args.agent}' is still a placeholder — skipping molecule.")
            result = {
                "passed": False,
                "skipped": True,
                "elapsed_seconds": 0,
                "return_code": -1,
                "output_tail": "playbook.yml has not been filled in yet.",
                "error": "placeholder",
            }
            Path(args.output).write_text(json.dumps(result, indent=2))
            sys.exit(0)

    print(f"[→] Running molecule test for agent: {args.agent}")
    start = time.time()

    try:
        proc = subprocess.run(
            ["molecule", "test"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(agent_dir),
        )
        elapsed = time.time() - start
        passed = proc.returncode == 0
        combined = proc.stdout + "\n" + proc.stderr
        error_msg = "" if passed else f"molecule exited with code {proc.returncode}"

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        passed = False
        combined = "Molecule timed out after 600 seconds."
        error_msg = "timeout"
        proc = None

    except FileNotFoundError:
        elapsed = time.time() - start
        passed = False
        combined = "molecule binary not found."
        error_msg = "molecule_not_found"
        proc = None

    result = {
        "passed": passed,
        "skipped": False,
        "elapsed_seconds": round(elapsed, 2),
        "return_code": proc.returncode if proc else -1,
        "output_tail": combined[-4000:],
        "error": error_msg,
    }

    Path(args.output).write_text(json.dumps(result, indent=2))
    status = "PASSED ✓" if passed else "FAILED ✗"
    print(f"[{status}] {args.agent} finished in {elapsed:.1f}s")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
