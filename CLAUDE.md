# CLAUDE.md

This is a public repository. Everything committed here, including commit
messages, branch names and PR text, is visible to anyone.

- The repo root is the `steephq` marketplace (`.claude-plugin/marketplace.json`).
  It lists one plugin, `steep`, in `plugins/steep/`
  (`plugins/steep/.claude-plugin/plugin.json`); an install copies only that
  folder. Skills live in `plugins/steep/skills/<name>/SKILL.md` and are
  discovered automatically; there are no per-skill manifests.
- Adding a skill: create the folder, then add a row to the Skills table in
  `README.md` and to `AGENTS.md`.
- Bump `version` in `plugins/steep/.claude-plugin/plugin.json` for any change that should
  reach installed copies.
- Keep content customer-facing: no internal URLs, ticket ids, customer names,
  people's names or references to private repos or unreleased features.
- `plugins/steep/skills/ossie-to-steep`,
  `plugins/steep/skills/snowflake-to-steep`,
  `plugins/steep/skills/dbt-to-steep` and
  `plugins/steep/skills/lookml-to-steep` each carry an identical copy of
  `references/steep-module-schema.json` and `scripts/validate_steep_import.py`,
  so each skill works on its own when copied out. Change all copies together;
  `tests/check_repo.py` enforces it.
- Tests: `python3 tests/check_repo.py` and `python3 tests/run.py` (needs
  `pyyaml` and `jsonschema`). CI runs both on every PR. When you fix a
  validator bug, add a fixture under `tests/<suite>/{valid,invalid}/` that
  reproduces it.
- Third-party material and trademarks are listed in `NOTICE`; update it when
  adding copied or summarised external material.
- Validate the manifests with `claude plugin validate .` (marketplace) and
  `claude plugin validate plugins/steep` (plugin).
