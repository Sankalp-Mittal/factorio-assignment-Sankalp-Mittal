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
        "id": "feasible_generation",
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
    {
        "id": "limited_ore_supply",
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
            "raw_supply_per_min": {"iron_ore": 500, "copper_ore": 500},
            "max_machines": {"assembler_1": 300, "chemical": 300}
          },
          "target": {"item": "green_circuit", "rate_per_min": 1800}
        }
        """ ,
        "expected": r"""
        {
          "bottleneck_hint": [
            "copper_ore supply",
            "iron_ore supply"
          ],
          "status": "infeasible"
        }
        """
    },
    {
        "id": "catalyst_case",
        "input": r"""
        {
          "machines": { "assembler": { "crafts_per_min": 60 } },
          "modules": {},
          "recipes": {
              "blue_chip":{
                "machine": "assembler",
                "time_s": 1,
                "in": { "iron_ore": 1, "catalyst": 1 },
                "out": { "blue_chip": 1, "catalyst": 1 }
              }
          },
          "limits": {
            "raw_supply_per_min": {"iron_ore": 301},
            "max_machines": {"assembler": 10}
          },
          "target": { "item": "blue_chip", "rate_per_min": 300 }
        }
        """ ,
        "expected": r"""
        {
          "per_machine_counts": {
            "assembler": 1
          },
          "per_recipe_crafts_per_min": {
            "blue_chip": 300.00000000000017
          },
          "raw_consumption_per_min": {
            "iron_ore": 300.0000000000003
          },
          "status": "ok"
        }
        """
    },
    {
        "id": "unrelated_chain_exists",
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
            },
            "red_circuit": {
                "machine": "assembler_1",
                "time_s": 1,
                "in": {"iron_plate": 100, "copper_plate": 300},
                "out": {"red_circuit": 1}
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
            "copper_plate": 4090.9090909090905,
            "green_circuit": 1636.363636363636,
            "iron_plate": 1363.6363636363662,
            "red_circuit": 0.0
          },
          "raw_consumption_per_min": {
            "copper_ore": 4090.9090909090924,
            "iron_ore": 1363.636363636365
          },
          "status": "ok"
        }
        """
    },
    {
        "id": "cycle_exists",
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
            },
            "potion" : {
                "machine": "assembler_1",
                "time_s": 0.5,
                "in": {"green_circuit": 2},
                "out": {"potion":1, "iron_plate": 1}
            }
            },
            "modules": {
            "assembler_1": {"prod": 0.1, "speed": 0.15},
            "chemical": {"prod": 0.2, "speed": 0.1}
            },
            "limits": {
            "raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 10000},
            "max_machines": {"assembler_1": 300, "chemical": 300}
            },
            "target": {"item": "potion", "rate_per_min": 1800}
        }
        """ ,
        "expected": r"""
        {
          "per_machine_counts": {
            "assembler_1": 2,
            "chemical": 7
          },
          "per_recipe_crafts_per_min": {
            "copper_plate": 7438.0165289256265,
            "green_circuit": 2975.206611570251,
            "iron_plate": 979.338842975204,
            "potion": 1636.3636363636383
          },
          "raw_consumption_per_min": {
            "copper_ore": 7438.016528925625,
            "iron_ore": 979.3388429752094
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
