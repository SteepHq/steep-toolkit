# dbt to Steep (experimental)

**Imports the [dbt Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)
(MetricFlow) definitions of a dbt project into Steep semantic model YAML, so the
metrics defined in dbt show up in Steep with the same meaning.**

> **Experimental.** Review the import before merging it: merging to the
> connected branch syncs it straight into your Steep workspace.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads the dbt project, preferably `target/semantic_manifest.json`
from `dbt parse`, and writes one `module:` file per semantic model. It reads
both the [latest YAML spec](https://docs.getdbt.com/docs/build/latest-metrics-spec)
and the legacy spec with top-level `semantic_models` and `measures`, including
a project that mixes the two while it migrates.

| dbt Semantic Layer | Steep |
| --- | --- |
| Semantic model | Module |
| Text and boolean categorical dimensions | Dimensions |
| Entities shared between models | Join paths |
| Simple metrics (`sum`, `count`, `count_distinct`, `sum_boolean`) | `sum`, `count`, `count-distinct` metrics |
| Simple metrics (`average`, `min`, `max`, `median`, `percentile`) | `custom-value` metrics |
| `agg_time_dimension` and its granularity | Metric `time` and `time_grains` |
| Metric filters (`{{ Dimension('…') }}`) | Metric `filters`, across joins |
| `non_additive_dimension` with `max` | Snapshot metric (`time_aggregation: last-date`) |
| Ratio metrics, `a / b` derived metrics | `ratio`, `custom-ratio` or `derived-ratio`, with filtered inputs as slices |
| Labels and descriptions | `name` / `label`, `description` |

It then validates the files against Steep's schema and sync rules, and reports
what Steep cannot represent.

Every file it writes starts with
`# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`, so
editors such as VS Code (with the Red Hat YAML extension) check it against
Steep's schema as you edit.

## Get it

This skill ships in the `steep` plugin. See the
[install instructions](../../../../README.md#install).

## How to talk to it

Run it from the repo with your Steep YAML (or an empty one), with the dbt
project checked out next to it.

- "Import the dbt semantic layer in `../analytics` into Steep."
- "Convert our MetricFlow metrics to Steep modules."

For the most faithful import, parse the project first:

```bash
dbt parse
```

and, so it can tell text dimensions from numeric ones:

```bash
dbt docs generate
```

It asks only for what the project cannot tell it, mostly the column types of
dimensions and the display format of ratios.

## Check the output

```bash
python3 <skills-dir>/dbt-to-steep/scripts/validate_steep_import.py modules/
```

(`<skills-dir>` is the folder the skills were installed into.) It needs PyYAML and
jsonschema (`python3 -m pip install pyyaml jsonschema`).

The checker validates each file against the bundled JSON Schema of a Steep
module. It then checks what fails a Steep sync across files: duplicate
identifiers, two modules on one table, duplicate join paths, and references
that do not resolve. It cannot see your warehouse.

## What does not carry over

- **Cumulative and conversion metrics**, and **derived metrics with offsets**
  (`offset_window`, `offset_to_grain`): Steep has no running-total or funnel
  metric, and compares periods in reports instead.
- **`join_to_timespine` and `fill_nulls_with`**: imported without them, so an
  empty period has no value.
- **Computed, numeric and time dimensions.** Steep dimensions are text or
  boolean columns (date columns only as cohort time dimensions). Expose a
  computed one as a column in the dbt model.
- **Natural entities, computed or composite keys, saved queries, exports and
  `meta`** have no Steep equivalent and are listed in the report.

## What's inside

```
dbt-to-steep/
├── SKILL.md                      # start here: the workflow
├── references/
│   ├── mapping.md                # field-by-field dbt → Steep rules, both specs, with an example
│   └── steep-module-schema.json  # Steep module JSON Schema, dated (see SKILL.md)
└── scripts/
    └── validate_steep_import.py  # schema and sync-rule checker
```

`steep-module-schema.json` and `validate_steep_import.py` are shared with the
`ossie-to-steep`, `snowflake-to-steep` and `lookml-to-steep` skills. Keep them in
sync when any of them changes.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the dbt documentation and dbt Core 1.12: **2026-11-04**.
