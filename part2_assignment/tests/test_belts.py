# pytest test: belts

import json
import subprocess
import sys
from pathlib import Path
import pytest

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

CASES = [
    {
        "id": "infeasible_cut_example",
        "input": r"""
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
        """,
        "expected": r"""
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
    },
    {
        "id": "feasible_cut_example",
        "input": r"""
        {
          "nodes": ["s", "a", "b", "c", "sink"],
          "edges": [
            {"from": "s", "to": "a", "lo": 0,   "hi": 1500},
            {"from": "a", "to": "b", "lo": 0,   "hi": 900},
            {"from": "b", "to": "sink", "lo": 200, "hi": 1200},
            {"from": "a", "to": "c", "lo": 0,   "hi": 600},
            {"from": "c", "to": "sink", "lo": 0,   "hi": 800}
          ],
          "node_caps": { "a": 1500, "b": 900, "c": 1500 },
          "sources": { "s": 1500 },
          "sink": "sink",
          "tolerance": 1e-9
        }
        """,
        "expected": r"""
        {
          "status": "ok",
          "max_flow_per_min": 1500.0,
          "flows": [
            {"from": "a", "to": "b", "flow": 900.0},
            {"from": "a", "to": "c", "flow": 600.0},
            {"from": "b", "to": "sink", "flow": 900.0},
            {"from": "c", "to": "sink", "flow": 600.0},
            {"from": "s", "to": "a", "flow": 1500.0}
          ]
        }
        """
    },
]


@pytest.mark.parametrize("case", CASES, ids=[c.get("id", f"case_{i}") for i, c in enumerate(CASES)])
def test_belts_cases(case):
    actual = run_cli("belts/main.py", case["input"])
    expected = json.loads(case["expected"])
    assert actual == expected, f"\n[{case.get('id','case')}] Expected:\n{json.dumps(expected,indent=2)}\nActual:\n{json.dumps(actual,indent=2)}"