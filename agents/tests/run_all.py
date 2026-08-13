"""Runs every live, per-agent test under agents/tests/ and prints a summary.

Each test_*.py here is a real end-to-end run against real APIs (Gemini, and
for account_research_agent a real Pub/Sub emulator), not a mock. Together
they can burn a meaningful chunk of a free-tier daily quota, so this is
meant to be run deliberately, not on every save.

Auto-discovers test_*.py files in this directory, so a new agent's live
test just needs to be dropped in here, nothing to register by hand.

Run: cd agents && uv run python tests/run_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_AGENTS_DIR = _TESTS_DIR.parent


def main() -> int:
    test_files = sorted(
        p for p in _TESTS_DIR.glob("test_*.py") if p.name != Path(__file__).name
    )
    if not test_files:
        print("No test_*.py files found under agents/tests/.")
        return 1

    results: list[tuple[str, bool, bool]] = []  # (name, passed, skipped)

    for test_file in test_files:
        print(f"\n=== {test_file.name} ===")
        proc = subprocess.run(
            [sys.executable, str(test_file)],
            cwd=_AGENTS_DIR,
            capture_output=True,
            text=True,
        )
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)

        passed = proc.returncode == 0
        skipped = "SKIP:" in proc.stdout
        results.append((test_file.name, passed, skipped))

    print("\n=== Summary ===")
    failed = False
    for name, passed, skipped in results:
        if not passed:
            failed = True
            status = "FAIL"
        elif skipped:
            status = "SKIP"
        else:
            status = "PASS"
        print(f"{status:5} {name}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
