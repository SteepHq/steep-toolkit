#!/usr/bin/env python3
"""Repository consistency checks that need no network.

- Files that are deliberately duplicated across skills (each skill is
  installed on its own) are byte-identical.
- Each skill's SKILL.md frontmatter `name` matches its folder.
- The marketplace lists exactly the plugin in plugins/steep, under the name
  in its .claude-plugin/plugin.json.
- Every skill has a row in README.md and AGENTS.md.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = "plugins/steep"

IMPORT_SKILLS = ["ossie-to-steep", "snowflake-to-steep", "dbt-to-steep",
                 "lookml-to-steep"]
DUPLICATES = [
    tuple(f"plugins/steep/skills/{skill}/{path}" for skill in IMPORT_SKILLS)
    for path in ("scripts/validate_steep_import.py",
                 "references/steep-module-schema.json")
]


def main() -> int:
    errors: list[str] = []

    for first, *others in DUPLICATES:
        for other in others:
            if (ROOT / first).read_bytes() != (ROOT / other).read_bytes():
                errors.append(f"{first} and {other} differ; they must stay identical")

    plugin = json.loads((ROOT / PLUGIN / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    entries = marketplace.get("plugins", [])
    if [(e.get("name"), e.get("source")) for e in entries] != [(plugin.get("name"), f"./{PLUGIN}")]:
        errors.append(f"marketplace.json must list one plugin, {plugin.get('name')!r} "
                      f"with source './{PLUGIN}'")

    readme = (ROOT / "README.md").read_text()
    agents = (ROOT / "AGENTS.md").read_text()
    for skill_dir in sorted((ROOT / PLUGIN / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        skill_md = (skill_dir / "SKILL.md").read_text()
        match = re.search(r"^---\n.*?^name:\s*(\S+)", skill_md, re.S | re.M)
        if not match or match.group(1) != name:
            errors.append(f"{name}/SKILL.md: frontmatter name must be {name!r}")
        if f"({PLUGIN}/skills/{name}/)" not in readme:
            errors.append(f"{name} has no row in the README.md Skills table")
        if f"plugins/steep/skills/{name}/SKILL.md" not in agents:
            errors.append(f"{name} has no row in AGENTS.md")

    for error in errors:
        print(f"ERROR {error}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
