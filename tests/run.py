#!/usr/bin/env python3
"""Run the skill validators against the fixtures in tests/.

Layout: tests/<suite>/{valid,invalid}/<case>, where <case> is a file or a
directory passed to the suite's validator as one argument.

- A case under valid/ must exit 0.
- A case under invalid/ must exit non-zero.
- An optional <case-name>.expect file next to a case (the case's name without
  its extension) lists one substring per line that must appear in the output.
  Blank lines and lines starting with # are ignored.

Usage: python3 tests/run.py [suite ...]
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# Each suite runs one or more validators. Both copies of the import validator
# run against the same fixtures, so they cannot drift apart in behavior.
SUITES = {
    "steep-import": [
        ROOT / "plugins/steep/skills/ossie-to-steep/scripts/validate_steep_import.py",
        ROOT / "plugins/steep/skills/snowflake-to-steep/scripts/validate_steep_import.py",
    ],
    "ossie": [ROOT / "plugins/steep/skills/steep-to-ossie/scripts/validate_ossie.py"],
    "semantic-view": [ROOT / "plugins/steep/skills/steep-to-snowflake/scripts/validate_semantic_view.py"],
}



def cases(suite_dir: pathlib.Path, kind: str):
    folder = suite_dir / kind
    if not folder.is_dir():
        return
    for path in sorted(folder.iterdir()):
        if path.suffix == ".expect":
            continue
        yield path


def expectations(case: pathlib.Path) -> list[str]:
    stem = case.name if case.is_dir() else case.stem
    expect = case.parent / f"{stem}.expect"
    if not expect.exists():
        return []
    lines = expect.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def main(argv: list[str]) -> int:
    selected = argv or sorted(SUITES)
    failures = 0
    total = 0
    for suite in selected:
        suite_dir = TESTS / suite
        for kind in ("valid", "invalid"):
            for case in cases(suite_dir, kind):
                for validator in SUITES[suite]:
                    total += 1
                    proc = subprocess.run(
                        [sys.executable, str(validator), str(case)],
                        capture_output=True, text=True, cwd=ROOT,
                    )
                    output = proc.stdout + proc.stderr
                    problems = []
                    if kind == "valid" and proc.returncode != 0:
                        problems.append(f"expected exit 0, got {proc.returncode}")
                    if kind == "invalid" and proc.returncode == 0:
                        problems.append("expected a non-zero exit, got 0")
                    for needle in expectations(case):
                        if needle not in output:
                            problems.append(f"missing in output: {needle!r}")
                    label = f"{suite}/{kind}/{case.name} [{validator.parent.parent.name}]"
                    if problems:
                        failures += 1
                        print(f"FAIL {label}")
                        for problem in problems:
                            print(f"     {problem}")
                        print("     output:\n" + "\n".join("       " + l for l in output.splitlines()))
                    else:
                        print(f"ok   {label}")
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
