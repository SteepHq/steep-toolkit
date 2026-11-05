# Agent instructions

This repo contains Agent Skills for working with Steep. Read the skill that
matches the task:

| Task | Skill |
| --- | --- |
| Exporting or converting a Steep semantic model (modules, metrics, dimensions, join paths) to Apache Ossie / OSI, or producing an `.ossie.yaml` file from Steep (experimental) | [`plugins/steep/skills/steep-to-ossie/SKILL.md`](plugins/steep/skills/steep-to-ossie/SKILL.md) |
| Importing or converting an Apache Ossie / OSI semantic model (an `.ossie.yaml` file, or a model exported from another tool through Ossie) into Steep semantic model YAML, or restoring a Steep model from an Ossie export (experimental) | [`plugins/steep/skills/ossie-to-steep/SKILL.md`](plugins/steep/skills/ossie-to-steep/SKILL.md) |
| Exporting or converting a Steep semantic model (modules, metrics, dimensions, join paths) to a Snowflake semantic view, Cortex Analyst or Snowflake Intelligence, or producing `CREATE SEMANTIC VIEW` DDL from Steep (experimental) | [`plugins/steep/skills/steep-to-snowflake/SKILL.md`](plugins/steep/skills/steep-to-snowflake/SKILL.md) |
| Importing or converting a Snowflake semantic view (YAML from `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`, `CREATE SEMANTIC VIEW` DDL, or a Cortex Analyst semantic model) into Steep semantic model YAML, or restoring a Steep model from a `steep-to-snowflake` export (experimental) | [`plugins/steep/skills/snowflake-to-steep/SKILL.md`](plugins/steep/skills/snowflake-to-steep/SKILL.md) |
| Importing or converting a dbt Semantic Layer / MetricFlow project (semantic models, measures and metrics in the latest or the legacy YAML spec, or a `semantic_manifest.json`) into Steep semantic model YAML (experimental) | [`plugins/steep/skills/dbt-to-steep/SKILL.md`](plugins/steep/skills/dbt-to-steep/SKILL.md) |
| Importing or converting a Looker project's LookML (views, explores, joins, dimensions and measures in `.lkml` files) into Steep semantic model YAML (experimental) | [`plugins/steep/skills/lookml-to-steep/SKILL.md`](plugins/steep/skills/lookml-to-steep/SKILL.md) |

Each skill's `SKILL.md` routes to supporting material in its `references/`
folder. Read referenced files as needed. The canonical YAML contract is
<https://help.steep.app/setup-and-manage/code-reference>; on any conflict about
fields, that page wins over anything in this repository.
