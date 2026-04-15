#!/usr/bin/env python3
"""
run_agent_test.py

Calls a specified AI agent API with the benchmark task description,
parses the response into a valid Ansible role structure, and writes
it to the roles/ directory for Molecule to test.

Usage:
    python run_agent_test.py --agent claude-sonnet
    python run_agent_test.py --agent gpt-4o
    python run_agent_test.py --agent gemini-pro
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

TASK_DESCRIPTION = """
Create an Ansible role called 'webserver' that performs the following tasks:
1. Install the nginx package
2. Ensure the nginx service is started and enabled on boot
3. Create the file /var/www/html/index.html with the content: 'Automated by Ansible'
4. Ensure the directory /var/www/html exists with appropriate permissions

The role must be compatible with Debian/Ubuntu systems (using apt).

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{
  "tasks": "<full YAML content of tasks/main.yml>",
  "handlers": "<full YAML content of handlers/main.yml>",
  "defaults": "<full YAML content of defaults/main.yml>"
}
"""

SYSTEM_PROMPT = """You are an expert Ansible automation engineer. When given a task description,
you return ONLY valid Ansible YAML role content as a JSON object with keys: tasks, handlers, defaults.
No markdown code fences, no explanation text — only the raw JSON object."""


def call_claude(task: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    start = time.time()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": task}],
    )
    elapsed = time.time() - start
    raw = message.content[0].text.strip()
    return {"raw": raw, "elapsed": elapsed}


def call_openai(task: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    start = time.time()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ],
        max_tokens=2048,
    )
    elapsed = time.time() - start
    raw = response.choices[0].message.content.strip()
    return {"raw": raw, "elapsed": elapsed}


AGENT_CALLERS = {
    "claude-sonnet": call_claude,
    "gpt-4o": call_openai,
}


def clean_json_response(raw: str) -> str:
    """Strip markdown fences if the model wrapped output anyway."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    return raw.strip()


def write_role(role_data: dict, role_dir: Path) -> None:
    """Write parsed role YAML files to the role directory."""
    tasks_dir = role_dir / "tasks"
    handlers_dir = role_dir / "handlers"
    defaults_dir = role_dir / "defaults"
    for d in [tasks_dir, handlers_dir, defaults_dir]:
        d.mkdir(parents=True, exist_ok=True)

    (tasks_dir / "main.yml").write_text(role_data.get("tasks", "---\n# No tasks generated\n"))
    (handlers_dir / "main.yml").write_text(role_data.get("handlers", "---\n# No handlers\n"))
    (defaults_dir / "main.yml").write_text(role_data.get("defaults", "---\n# No defaults\n"))
    print(f"[✓] Role written to {role_dir}")


def main():
    parser = argparse.ArgumentParser(description="Run AI agent Ansible generation test")
    parser.add_argument("--agent", required=True, choices=list(AGENT_CALLERS.keys()),
                        help="Which AI agent to test")
    parser.add_argument("--output-meta", default="agent_meta.json",
                        help="Path to write generation metadata JSON")
    args = parser.parse_args()

    caller = AGENT_CALLERS[args.agent]

    print(f"[→] Calling agent: {args.agent}")
    try:
        result = caller(TASK_DESCRIPTION)
    except Exception as e:
        print(f"[✗] API call failed: {e}", file=sys.stderr)
        meta = {
            "agent": args.agent,
            "status": "api_error",
            "error": str(e),
            "elapsed_generation": 0,
            "raw_response": "",
        }
        Path(args.output_meta).write_text(json.dumps(meta, indent=2))
        sys.exit(1)

    raw = result["raw"]
    elapsed = result["elapsed"]
    print(f"[✓] Response received in {elapsed:.2f}s")

    try:
        cleaned = clean_json_response(raw)
        role_data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[✗] Failed to parse JSON response: {e}", file=sys.stderr)
        print(f"    Raw (first 500 chars): {raw[:500]}", file=sys.stderr)
        meta = {
            "agent": args.agent,
            "status": "parse_error",
            "error": f"JSON parse error: {e}",
            "elapsed_generation": elapsed,
            "raw_response": raw[:2000],
        }
        Path(args.output_meta).write_text(json.dumps(meta, indent=2))
        sys.exit(1)

    # Write the role for molecule to test
    role_dir = Path("roles/webserver")
    write_role(role_data, role_dir)

    meta = {
        "agent": args.agent,
        "status": "generated",
        "elapsed_generation": round(elapsed, 2),
        "raw_response": raw[:2000],
        "tasks_preview": role_data.get("tasks", "")[:500],
    }
    Path(args.output_meta).write_text(json.dumps(meta, indent=2))
    print(f"[✓] Metadata written to {args.output_meta}")


if __name__ == "__main__":
    main()
