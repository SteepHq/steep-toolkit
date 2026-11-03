# Steep to Ossie (experimental)

**Exports your Steep semantic model to [Apache Ossie](https://github.com/apache/ossie),
the open semantic interchange format, so other BI and AI tools can read the same
metric definitions.**

> **Experimental.** Ossie's spec (`0.2.0.dev0`) is an unreleased draft and may
> change. Review the export before relying on it.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads your Steep semantic model YAML (`module:` files) and writes one
`.ossie.yaml` document:

| Steep | Ossie |
| --- | --- |
| Module | Dataset |
| Columns used by dimensions, metrics, filters, joins and entities | Fields |
| Metric (`sum`, `count`, `count-distinct`, `ratio`, custom SQL, derived ratio) | Metric with an `OSSIE_SQL_2026` expression |
| Metric filters | `FILTER (WHERE …)` on the aggregate |
| Slice | An extra metric per slice |
| Join path | Relationship |
| Synonyms, agent instructions, example questions | `ai_context` |
| Everything else (access policies, entities, cohorts, time grains, owners, …) | A `STEEP` custom extension, so nothing is dropped silently |

It then validates the document and gives you a report of what Ossie could not
represent.

## Get it

This skill ships in the `steep` plugin. See the
[install instructions](../../../../README.md#install).

## How to talk to it

Run it from the repo with your Steep YAML.

- "Export our Steep model to Ossie."
- "Convert the orders and customers modules to an OSI semantic model for
  Snowflake, catalog `ANALYTICS`."

The agent asks only for what the YAML cannot tell it: the model name, the
database or catalog, and the warehouse, which decides identifier quoting and the
SQL dialect for expressions that are not portable.

## Check the output

```bash
python3 <skills-dir>/steep-to-ossie/scripts/validate_ossie.py acme.ossie.yaml
```

(`<skills-dir>` is the folder the skills were installed into.) It needs PyYAML and
jsonschema (`python3 -m pip install pyyaml jsonschema`).

The checker validates against Ossie's JSON Schema, which is bundled so the
check works offline. It also checks the name-resolution rules the schema cannot
express: duplicate names, keys, relationship columns, qualified versus
unqualified metric references, names that are not declared fields, metrics that
reference other metrics, and STEEP extensions whose `data` is not valid JSON.
Warnings flag expressions that probably compute something other than the Steep
metric, such as `COUNT(*)` across a join.

## What does not carry over

- **Access policies (row-level security).** These are kept in the extension, but
  tools reading Ossie will not enforce them. Do not share an export with anyone
  who should only see filtered data.
- **Some derived ratios are approximate.** Steep evaluates each operand on its
  own time axis, but Ossie has one expression, so a ratio whose operands live on
  different tables or time columns can differ.
- **Data types are often missing.** Steep YAML only types dimensions and entity
  properties.
- **Targets, cohorts, time grains, entities and joins to tables that are not
  modules** have no Ossie equivalent. They are kept in the extension and listed
  in the report.
- **Exports built from the Steep API** (no YAML at hand) are marked as such:
  the API does not return everything the YAML holds, so an import cannot
  restore them exactly.

## What's inside

```
steep-to-ossie/
├── SKILL.md                    # start here: the workflow
├── references/
│   ├── mapping.md              # field-by-field Steep → Ossie rules, with an example
│   └── ossie-schema.json       # Ossie JSON Schema, pinned (see below)
└── scripts/
    └── validate_ossie.py       # schema and name-resolution checker
```

`references/ossie-schema.json` is copied unchanged from
[apache/ossie](https://github.com/apache/ossie) at commit `89e2e17f`
(Apache-2.0, © The Apache Software Foundation). This product includes software
developed at The Apache Software Foundation (<https://www.apache.org/>).

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the Ossie spec: **2026-10-27**.
