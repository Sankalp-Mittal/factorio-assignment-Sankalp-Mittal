# pytest test: factory

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
          "machines": {
            "assembler_1": {"crafts_per_min": 30},
            "chemical": {"crafts_per_min": 60}
          },
          "recipes": {
            "iron_plate": {
              "machine": "chemical",
              "time_s": 3.2,
              "in": {"iron_ore": 1},
              "out": {"iron_plate": 1}
            },
            "copper_plate": {
              "machine": "chemical",
              "time_s": 3.2,
              "in": {"copper_ore": 1},
              "out": {"copper_plate": 1}
            },
            "green_circuit": {
              "machine": "assembler_1",
              "time_s": 0.5,
              "in": {"iron_plate": 1, "copper_plate": 3},
              "out": {"green_circuit": 1}
            }
          },
          "modules": {
            "assembler_1": {"prod": 0.1, "speed": 0.15},
            "chemical": {"prod": 0.2, "speed": 0.1}
          },
          "limits": {
            "raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 5000},
            "max_machines": {"assembler_1": 300, "chemical": 300}
          },
          "target": {"item": "green_circuit", "rate_per_min": 1800}
        }
        """ ,
        "expected": r"""
        {
          "per_machine_counts": {
            "assembler_1": 1,
            "chemical": 5
          },
          "per_recipe_crafts_per_min": {
            "copper_plate": 4090.909090909089,
            "green_circuit": 1636.3636363636356,
            "iron_plate": 1363.6363636363658
          },
          "raw_consumption_per_min": {
            "copper_ore": 4090.90909090909,
            "iron_ore": 1363.636363636364
          },
          "status": "ok"
        }
        """
    },
]

@pytest.mark.parametrize("case", CASES, ids=[c.get("id", f"case_{i}") for i, c in enumerate(CASES)])
def test_belts_cases(case):
    actual = run_cli("factory/main.py", case["input"])
    expected = json.loads(case["expected"])
    assert actual == expected, f"\n[{case.get('id','case')}] Expected:\n{json.dumps(expected,indent=2)}\nActual:\n{json.dumps(actual,indent=2)}"
