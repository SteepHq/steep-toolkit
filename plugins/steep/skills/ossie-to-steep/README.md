# Ossie to Steep (experimental)

**Imports an [Apache Ossie](https://github.com/apache/ossie) semantic model into
Steep semantic model YAML, so metric definitions from another BI or AI tool become Steep
modules, dimensions, metrics and join paths.**

> **Experimental.** Ossie's spec (`0.2.0.dev0`) is an unreleased draft and may
> change. Review the import before you merge it: merging to the connected
> branch syncs it into your Steep workspace.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads one Ossie document (`.ossie.yaml` or JSON) and writes one Steep
`module:` YAML file per dataset:

| Ossie | Steep |
| --- | --- |
| Dataset | Module (`source` becomes `schema` and `table`) |
| String and Boolean fields that are not keys or personal data | Dimensions |
| `SUM`, `COUNT(*)`, `COUNT(DISTINCT …)`, `SUM / SUM` | `sum`, `count`, `count-distinct`, `ratio` metrics |
| `FILTER (WHERE …)` on the aggregate | Metric filters |
| Any other aggregate expression | `custom-value` or `custom-ratio` metric, with SQL rewritten for your warehouse |
| Relationship | Join path, declared once on the one side |
| `ai_context` (synonyms, instructions, examples) | `synonyms`, `agent_instructions`, `examples` |

A document exported from Steep with the `steep-to-ossie` skill carries a `STEEP`
extension, and the agent restores the original definitions from it: slices,
entities, cohorts, time grains, categories, owners, targets, the module each
metric was declared on, exact table names and joins to tables outside the
export come back as they were. If another tool changed a metric after the
export, the changed expression wins and the report says so.

It then validates the files and gives you a report of what Steep could not take.

Every file it writes starts with
`# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`, so
editors such as VS Code (with the Red Hat YAML extension) check it against
Steep's schema as you edit.

## Get it

This skill ships in the `steep` plugin. See the
[install instructions](../../../../README.md#install).

## How to talk to it

Run it from the repo Steep syncs from, with the Ossie document in reach.

- "Import `sales.ossie.yaml` into Steep."
- "Convert this OSI model to Steep modules. We're on Snowflake, schema
  `ANALYTICS`."

The agent asks only for what the document cannot tell it: your warehouse (it
decides column-name case and custom SQL), a schema when a source has none, and
which time column a dataset's metrics should use when there are several.

## Check the output

```bash
python3 <skills-dir>/ossie-to-steep/scripts/validate_steep_import.py modules/
```

(`<skills-dir>` is the folder the skills were installed into.) It needs PyYAML and
jsonschema (`python3 -m pip install pyyaml jsonschema`).

The checker validates each module against Steep's JSON Schema, which is bundled
so the check works offline. It then checks what fails a Steep sync across files:
duplicate identifiers, two modules on one table, duplicate join paths, and
derived-ratio operands or metric dimensions that do not resolve. Warnings flag
likely import mistakes, such as a ratio without `format` or custom SQL that uses
`FILTER (WHERE …)`, which most warehouses reject.

## What does not carry over

- **Time columns.** Ossie metrics have none and every Steep metric needs one.
  When a dataset has several date fields, the agent asks you.
- **Computed fields.** Steep has no computed columns. They can only be used in
  custom SQL metrics; to filter or break down by one, create a view.
- **Query sources.** A dataset defined by a SQL query cannot be a module. Create
  a view and import that.
- **Composite and repeated joins.** Steep joins on one column, and only once per
  pair of tables.
- **Row-level security.** Ossie has none. Access policies are only restored from
  a Steep export, and only after you confirm them.
- **Model-level description and AI context.** Steep has no workspace-level slot.

## What's inside

```
ossie-to-steep/
├── SKILL.md                      # start here: the workflow
├── references/
│   ├── mapping.md                # field-by-field Ossie → Steep rules, with an example
│   └── steep-module-schema.json  # Steep module JSON Schema, dated (see SKILL.md)
└── scripts/
    └── validate_steep_import.py  # schema and sync-rule checker
```

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the Ossie spec: **2026-10-29**.
