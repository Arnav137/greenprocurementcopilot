"""Run the pipeline: text -> structuring -> validation -> calculation."""
import subprocess
import sys
from pathlib import Path

# Remove old outputs so a failed run cannot leave stale results behind.
for name in ("structured.json", "validation_result.json", "calculation_result.json"):
    Path(name).unlink(missing_ok=True)

steps = [
    ("structure.py", "structuring"),
    ("validate.py", "validation"),
    ("calculate.py", "calculation"),
]
for script, label in steps:
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"\nPipeline stopped: {label} step failed (exit code {result.returncode}).")
        raise SystemExit(result.returncode)
    if label == "structuring" and not Path("structured.json").exists():
        print("\nPipeline stopped: structuring did not produce a new structured.json.")
        raise SystemExit(1)
