import json
import subprocess
import sys
from pathlib import Path

INPUT_JSON = '''
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
'''

OUTPUT_JSON = '''
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
'''

ROOT = Path(__file__).resolve().parents[1]      # .../part2_assignment
MAIN = ROOT / "belts" / "main.py"

def _as_obj(x):  # parse if it's a JSON string
    return json.loads(x) if isinstance(x, str) else x

def test_belts_matches_expected():
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
    test_belts_matches_expected()
    print("OK")