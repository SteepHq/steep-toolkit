# LookML to Steep (experimental)

**Imports the [LookML](https://cloud.google.com/looker/docs/what-is-lookml)
views, explores and measures of a Looker project into Steep semantic model YAML,
so the metrics defined in Looker show up in Steep with the same meaning.**

> **Experimental.** Review the import before merging it: merging to the
> connected branch syncs it straight into your Steep workspace.

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

The agent reads the project's `.lkml` files, resolves includes, constants,
`extends` and refinements, and writes one `module:` file per view on a table.

| LookML | Steep |
| --- | --- |
| View with `sql_table_name` | Module |
| Visible `string` and boolean `yesno` dimensions on a column | Dimensions |
| Explore joins (`sql_on`, `foreign_key`, `relationship`) | Join paths |
| `count`, `count_distinct`, `sum` measures | `count`, `count-distinct`, `sum` metrics |
| `average`, `min`, `max`, `median`, `percentile` measures | `custom-value` metrics |
| `_distinct` measures keyed on the primary key | The same metric without `_distinct` |
| Measure `filters:` (Looker filter expressions) | Metric `filters`, across joins |
| `number` measures dividing two measures | `ratio`, `custom-ratio` or `derived-ratio`, with filtered operands as slices |
| A view's time `dimension_group` | Metric `time` and `time_grains` |
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

Run it from the repo with your Steep YAML (or an empty one), with the Looker
project checked out next to it.

- "Import the LookML in `../looker` into Steep."
- "Convert the `ecommerce` Looker model to Steep modules."

LookML measures do not say which date they are measured over, so it asks for
the time column of every view that has more than one. It also asks for
whatever else the project cannot tell it, such as the warehouse and the
display format of ratios.

## Check the output

```bash
python3 <skills-dir>/lookml-to-steep/scripts/validate_steep_import.py modules/
```

(`<skills-dir>` is the folder the skills were installed into.) It needs PyYAML and
jsonschema (`python3 -m pip install pyyaml jsonschema`).

The checker validates each file against the bundled JSON Schema of a Steep
module. It then checks what fails a Steep sync across files: duplicate
identifiers, two modules on one table, duplicate join paths, and references
that do not resolve. It cannot see your warehouse.

## What does not carry over

- **Views on derived tables**, persisted or not: Steep modules sit on tables.
  Build them as warehouse tables first.
- **Liquid, parameters and templated filters**, which change SQL per query.
- **Post-SQL and comparison measures**: `percent_of_total`,
  `percent_of_previous`, `running_total` and `period_over_period`. Steep
  compares periods in reports instead.
- **Explore-level filters and `access_filter`**: Steep metrics carry their
  own filters, and access is set up in Steep.
- **Relative date filters, OR filters and `many_to_many` joins**.
- **Computed, numeric and location dimensions.** Steep dimensions are text or
  boolean columns. Expose a computed one as a column in the warehouse.

## What's inside

```
lookml-to-steep/
├── SKILL.md                      # start here: the workflow
├── references/
│   ├── mapping.md                # field-by-field LookML → Steep rules, with an example
│   └── steep-module-schema.json  # Steep module JSON Schema, dated (see SKILL.md)
└── scripts/
    └── validate_steep_import.py  # schema and sync-rule checker
```

`steep-module-schema.json` and `validate_steep_import.py` are shared with the
`ossie-to-steep`, `snowflake-to-steep` and `dbt-to-steep` skills. Keep them in
sync when any of them changes.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against the Looker documentation: **2026-11-05**.
