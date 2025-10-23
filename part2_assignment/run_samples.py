#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = [ROOT / "tests" / "test_belts.py", ROOT / "tests" / "test_factory.py"]

def run_test(path: Path) -> bool:
    if not path.exists():
        print(f"=== {path.name}: MISSING ===")
        return False
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    ok = proc.returncode == 0
    print(f"\n=== {path.name}: {'PASS' if ok else 'FAIL'} ===")
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if not ok and proc.stderr.strip():
        print("\n[stderr]")
        print(proc.stderr.strip())
    return ok

def main():
    results = {p.name: run_test(p) for p in TESTS}
    print("\n=== SUMMARY ===")
    for name, ok in results.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    # exit 0 only if all tests passed
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()
