#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    # Run pytest directly on the two files we maintain.
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/test_belts.py", "tests/test_factory.py"]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
