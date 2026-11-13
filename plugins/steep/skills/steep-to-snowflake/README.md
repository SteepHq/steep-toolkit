# Steep to Snowflake (experimental)

**Exports your Steep semantic model to a
[Snowflake semantic view](https://docs.snowflake.com/en/user-guide/views-semantic/overview),
so Cortex Analyst, Snowflake Intelligence and SQL users in Snowflake work from
the same metric definitions.**

> **Experimental.** Review the statement and run the parity check before
> relying on it.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads your Steep semantic model YAML (`module:` files) and writes one
`CREATE OR ALTER SEMANTIC VIEW` statement:

| Steep | Snowflake semantic view |
| --- | --- |
| Module | Logical table, with the entity's primary key |
| Join path | Relationship (plus a `UNIQUE` key where needed) |
| Dimensions, metric time columns, entity properties | Dimensions |
| Metric (`sum`, `count`, `count-distinct`, `ratio`, custom SQL) | Metric, with filters folded into the aggregate |
| Slice | An extra metric per slice |
| Derived ratio | Derived metric |
| `last-date` (snapshot) metric | Metric with `NON ADDITIVE BY` |
| Synonyms, descriptions | `WITH SYNONYMS`, `COMMENT` |
| Agent instructions, labels and metric names, and each metric's date, Steep identifier, format and currency | `AI_SQL_GENERATION` |

It then validates the statement offline and reports what Snowflake cannot
represent. If you have Snowflake access, it can also create the view in a
scratch schema and compare a few metrics against Steep.

## Get it

This skill ships in the `steep` plugin. See the
[install instructions](../../../../README.md#install).

## How to talk to it

Run it from the repo with your Steep YAML.

- "Export our Steep model to a Snowflake semantic view in `ANALYTICS.SEMANTIC`."
- "Turn the orders and customers modules into semantic view DDL for Cortex
  Analyst."

The agent asks only for what the YAML cannot tell it: the view name, the
database and schema the view goes in, and whether your Steep workspace runs on
Snowflake.

## Check the output

```bash
python3 <skills-dir>/steep-to-snowflake/scripts/validate_semantic_view.py acme.semantic-view.sql
```

(`<skills-dir>` is the folder the skills were installed into.) It needs Python 3.10 or
later and nothing else.

Snowflake has no dry run for semantic view DDL. The checker covers the rules
from Snowflake's documentation that do not need the database:

- clause order and duplicate names;
- unquoted reserved keywords;
- primary or unique keys behind every relationship, and no cycles;
- references to unknown tables, to another table's physical columns, or to the
  many side of a relationship;
- metrics that aggregate metrics, derived metric restrictions and
  `NON ADDITIVE BY` use.

It cannot see your tables, so run the statement in a scratch schema too.

## What does not carry over

- **Access policies (row-level security).** The semantic view does not filter
  rows per Steep member. Anyone who can query it sees every row their Snowflake
  role can read. Add Snowflake row access policies on the tables before you
  grant the view.
- **Private metrics** are left out unless you ask for them.
- **Some derived ratios are approximate.** Steep measures each side on its own
  date, while a Snowflake query groups both by the one time dimension it asks
  for.
- **Cohorts, time grains, resampling, per-metric allowed dimensions, owners,
  categories, unlisted flags, examples, dimension types, entity links and
  targets** have no Snowflake equivalent, and are listed in the report.
- **A near round trip.** The `snowflake-to-steep` skill restores an export,
  using marker lines in `AI_SQL_GENERATION` for each metric's date, Steep
  identifier, format, currency, unit and decimals, and for display names. Still different after the
  round trip: entities are lost (their property columns come back as ordinary
  dimensions, and the primary key is not restored as an entity unless you ask),
  dimension types come back as `categorical`, allowed dimensions as every
  reachable one, filters on custom SQL stay inside the SQL, and everything
  listed above is gone. See "Round trip" in
  `references/mapping.md`.

## What's inside

```
steep-to-snowflake/
├── SKILL.md                         # start here: the workflow
├── references/
│   ├── mapping.md                   # field-by-field Steep → Snowflake rules, with an example
│   └── semantic-view-syntax.md      # the Snowflake grammar and validation rules used
└── scripts/
    └── validate_semantic_view.py    # offline structural and reference checker
```

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the Snowflake documentation: **2026-10-29**.
