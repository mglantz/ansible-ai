#!/usr/bin/env python3
"""
run_molecule.py

Runs `molecule test` and captures timing + output into molecule_result.json.
Must be run from the repo root (where molecule/ lives).
"""

import json
import subprocess
import sys
import time
from pathlib import Path


def main():
    output_file = "molecule_result.json"
    print("[→] Running molecule test …")

    start = time.time()
    try:
        proc = subprocess.run(
            ["molecule", "test"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute hard limit
        )
        elapsed = time.time() - start
        passed = proc.returncode == 0
        combined_output = proc.stdout + "\n" + proc.stderr
        error_msg = "" if passed else f"molecule test exited with code {proc.returncode}"
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        passed = False
        combined_output = "Molecule test timed out after 600 seconds."
        error_msg = "timeout"
    except FileNotFoundError:
        elapsed = time.time() - start
        passed = False
        combined_output = "molecule binary not found — is it installed?"
        error_msg = "molecule_not_found"

    result = {
        "passed": passed,
        "elapsed_seconds": round(elapsed, 2),
        "return_code": proc.returncode if "proc" in dir() else -1,
        "output_tail": combined_output[-4000:],
        "error": error_msg,
    }

    Path(output_file).write_text(json.dumps(result, indent=2))
    status = "PASSED ✓" if passed else "FAILED ✗"
    print(f"[{status}] Molecule finished in {elapsed:.1f}s")
    if not passed:
        print(f"    Last output:\n{combined_output[-800:]}", file=sys.stderr)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
