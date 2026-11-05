# Snowflake to Steep (experimental)

**Imports a [Snowflake semantic view](https://docs.snowflake.com/en/user-guide/views-semantic/overview)
into Steep semantic model YAML, so the metrics defined for Cortex Analyst and Snowflake
Intelligence show up in Steep with the same meaning.**

> **Experimental.** Review the import before merging it: merging to the
> connected branch syncs it straight into your Steep workspace.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads the semantic view and writes one `module:` file per table:

| Snowflake semantic view | Steep |
| --- | --- |
| Logical table | Module |
| Text and boolean dimensions | Dimensions |
| `SUM`, `COUNT`, `COUNT(DISTINCT …)` metrics, with `IFF`/`CASE` filters | `sum`, `count`, `count-distinct` metrics with `filters` |
| `SUM(a) / SUM(b)` and other aggregates | `ratio`, `custom-ratio`, `custom-value` |
| Metric with `NON ADDITIVE BY` a date | Snapshot metric (`time_aggregation: last-date`) |
| Derived metric `m1 / m2` | `derived-ratio` |
| Relationship | Join path |
| Synonyms, descriptions, custom instructions, verified questions | `synonyms`, `description`, `agent_instructions`, `examples` |

It restores a `steep-to-snowflake` export nearly as it was: identifiers,
display names, slices, join paths, and each metric's time column and format,
read from marker lines the export writes. Still lost on that round trip:
access policies, private metrics, cohorts, time grains, owners, categories,
examples, unlisted flags and targets; entities are lost (their property
columns come back as ordinary dimensions, and an entity is built only if you
ask), dimension types come back as `categorical`, allowed dimensions as every reachable one,
and filters on custom SQL stay inside the SQL. It then validates the files
against Steep's schema and sync rules, and reports what Steep cannot
represent.

Every file it writes starts with
`# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`, so
editors such as VS Code (with the Red Hat YAML extension) check it against
Steep's schema as you edit.

## Get it

This skill ships in the `steep` plugin. See the
[install instructions](../../../../README.md#install).

## How to talk to it

Run it from the repo with your Steep YAML (or an empty one).

- "Import the semantic view `ANALYTICS.SEMANTIC.REVENUE` into Steep."
- "Here's the YAML from `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`, turn it into
  Steep modules."

If the agent cannot run SQL in Snowflake, it gives you the statement to run:

```sql
SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('ANALYTICS.SEMANTIC.REVENUE');
```

It asks only for what the view cannot tell it, mostly which date column each
metric is measured on when a table has several.

## Check the output

```bash
python3 <skills-dir>/snowflake-to-steep/scripts/validate_steep_import.py modules/
```

(`<skills-dir>` is the folder the skills were installed into.) It needs PyYAML and
jsonschema (`python3 -m pip install pyyaml jsonschema`).

The checker validates each file against the bundled JSON Schema of a Steep
module. It then checks what fails a Steep sync across files: duplicate
identifiers, two modules on one table, duplicate join paths, and references
that do not resolve. It cannot see your warehouse.

## What does not carry over

- **Row-level security.** Snowflake row access and masking policies live on the
  tables, not in the view, and Steep queries with its own connection role. The
  import never writes Steep access policies.
- **Computed, numeric and date dimensions.** Steep dimensions are text or
  boolean columns (date columns only as cohort time dimensions). Expose a
  computed one through a view.
- **Window function metrics, `USING`, composite / ASOF / range joins,
  query-based tables, variables, tags and Cortex Search services** have no Steep
  equivalent and are listed in the report.

## What's inside

```
snowflake-to-steep/
├── SKILL.md                      # start here: the workflow
├── references/
│   ├── mapping.md                # field-by-field Snowflake → Steep rules, with an example
│   └── steep-module-schema.json  # Steep module JSON Schema, dated (see SKILL.md)
└── scripts/
    └── validate_steep_import.py  # schema and sync-rule checker
```

`steep-module-schema.json` and `validate_steep_import.py` are shared with the
`ossie-to-steep` and `dbt-to-steep` skills. Keep them in sync when any of them
changes.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the Snowflake documentation: **2026-10-29**.
