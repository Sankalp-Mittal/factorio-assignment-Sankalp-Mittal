import json
import subprocess
import sys
from pathlib import Path

INPUT_JSON = '''
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
'''

OUTPUT_JSON = '''
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
'''

ROOT = Path(__file__).resolve().parents[1]      # .../part2_assignment
MAIN = ROOT / "factory" / "main.py"

def _as_obj(x):  # parse if it's a JSON string
    return json.loads(x) if isinstance(x, str) else x

def test_factory_matches_expected():
    proc = subprocess.run(
        [sys.executable, str(MAIN)],
        input=INPUT_JSON,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"

    actual = json.loads(proc.stdout)
    expected = _as_obj(OUTPUT_JSON)
    assert actual == expected, f"\nExpected:\n{expected}\nActual:\n{actual}\n"

if __name__ == "__main__":
    # Allow running directly without pytest
    test_factory_matches_expected()
    print("OK")