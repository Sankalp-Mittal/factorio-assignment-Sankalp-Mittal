# pytest test: belts

import json
import subprocess
import sys
from pathlib import Path

def run_cli(main_rel_path: str, stdin_json: str):
    """
    Run a CLI Python script relative to this file's directory,
    pass it JSON on stdin, and parse JSON from stdout.
    """
    root = Path(__file__).resolve().parent.parent
    main = (root / main_rel_path).resolve()

    proc = subprocess.run(
        [sys.executable, str(main)],
        input=stdin_json,
        text=True,
        capture_output=True,
        cwd=str(root),
    )

    assert proc.returncode == 0, f"Process failed.\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Output was not valid JSON.\nSTDOUT:\n{proc.stdout}") from e


INPUT_JSON = r"""
{
  "nodes": ["s", "a", "b", "c", "sink"],
  "edges": [
    {"from": "s", "to": "a", "lo": 0,   "hi": 1500},
    {"from": "a", "to": "b", "lo": 0,   "hi": 800},
    {"from": "b", "to": "sink", "lo": 200, "hi": 800},
    {"from": "a", "to": "c", "lo": 0,   "hi": 500},
    {"from": "c", "to": "sink", "lo": 0,   "hi": 500}
  ],
  "node_caps": { "a": 1500, "b": 800, "c": 500 },
  "sources": { "s": 1500 },
  "sink": "sink",
  "tolerance": 1e-9
}
"""

# Expected structure as shared earlier (order-sensitive lists kept the same)
EXPECTED_JSON = r"""
{
  "status": "infeasible",
  "cut_reachable": ["a", "s"],
  "deficit": {
    "demand_balance": 200.0,
    "tight_nodes": [],
    "tight_edges": [
      {"from": "a", "to": "b", "flow_needed": 100.0},
      {"from": "a", "to": "c", "flow_needed": 100.0}
    ]
  }
}
"""

def test_belts_matches_expected_exactly():
    actual = run_cli("belts/main.py", INPUT_JSON)
    expected = json.loads(EXPECTED_JSON)
    assert actual == expected, f"Mismatch.\\nExpected:\\n{expected}\\nActual:\\n{actual}"

if __name__ == "__main__":
    # Allow running directly for quick checks
    test_belts_matches_expected_exactly()
    print("test_belts.py OK")
