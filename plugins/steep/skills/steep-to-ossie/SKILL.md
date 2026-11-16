---
name: steep-to-ossie
description: >-
  Experimental. Export a Steep semantic model (its `module:` YAML, or
  the definitions behind a Steep workspace) to an Apache Ossie (Open Semantic
  Interchange, OSI) semantic model document. Use this skill whenever someone
  wants to export, convert, translate or share Steep modules, metrics,
  dimensions, slices or join paths with another tool through Ossie or OSI, or
  asks for an `.ossie.yaml` file from Steep. It encodes how Steep computes
  metrics and filters, so the export means the same thing as the Steep metric
  instead of a guess from field names.
---

# Export a Steep semantic model to Apache Ossie

**Experimental.** Ossie's spec `0.2.0.dev0` is an unreleased draft and may
change. Tell the user that the export needs human review before anyone relies on
it.

Converts Steep semantic model YAML files (YAML documents with a `module:` root) into one
Apache Ossie core-spec document. The field-by-field mapping is in
[`references/mapping.md`](references/mapping.md). Read it before writing any
output.

## Sources

- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Ossie core spec:** <https://github.com/apache/ossie/blob/main/core-spec/spec.md>
  and the expression language in `core-spec/expression_language.md`.
- **Bundled schema:** `references/ossie-schema.json` is the Ossie JSON Schema at
  apache/ossie commit `89e2e17f8249e68f30df7b29ac8852fa9dd24501`, fetched on
  2026-10-27. If the user targets a newer Ossie version, download that version's
  `ossie-schema.json` and pass it to the validator with `--schema`.

## Workflow

### 1. Collect the input

1. Find the Steep files: every `*.yml` / `*.yaml` whose root key is `module`,
   and the `targets:` file if there is one. Ossie has no targets: carry the
   targets object in the root STEEP extension (mapping: "Model (root)").
2. If the user has no files but the Steep MCP server is connected, rebuild the
   model with `list_modules`, `list_metrics`, `get_metric` and `list_entities`.
   The API returns what Steep stored, not the YAML: it may lack access policies,
   join paths, the targets table, metric `currency`, `unit` and `decimals`, and
   column paths exactly as written, and its
   values can differ in form from the files. Extensions built from it are
   therefore not verbatim. Add `"source": "api"` to the root STEEP extension so
   an importer treats them with care, and list in the report what the API did
   not provide.
3. Ask only for what the files cannot tell you, with these defaults:
   - **Model name**: default is the repo or folder name in `snake_case`.
   - **Database / catalog** for `source`: default is none (`schema.table`).
   - **Warehouse** (Snowflake, Postgres, BigQuery, …). It decides which
     identifiers need quotes (mapping: **Case**) and the dialect name for
     non-portable SQL (`SNOWFLAKE`, `BIGQUERY`, `DATABRICKS`, …). Default:
     unknown, which means `ANSI_SQL` and lower-case folding; say so in the report.
   - **Output path**: default is `<model_name>.ossie.yaml` next to the Steep files.

### 2. Build the model

Follow `references/mapping.md` in this order:

1. One **dataset** per module.
2. **Fields**: one per distinct column a dataset needs. That covers dimensions,
   metric `time` columns, metric value / numerator / denominator / distinct
   columns, filter and slice columns, join columns, access-policy columns,
   entity primary keys and properties, and every `table.column` referenced
   inside custom SQL.
3. **Metrics**: dataset-scoped when everything they touch is on their own
   module's table, model-scoped (`dataset.field` references) otherwise. Slices
   become extra metrics. Filters become `FILTER (WHERE …)` clauses.
4. **Relationships** from `joinPaths`, oriented so `from` is the many side.
   Which Steep side that is depends on the join `type`.
5. **`custom_extensions`** with `vendor_name: STEEP` to carry everything Ossie
   has no slot for, so a later Ossie → Steep import can round-trip it.

Rules that are easy to get wrong:

- Ossie expressions resolve in three levels: field expressions reference
  **source columns**, metric expressions reference **fields**, and nothing
  references a metric. Never put a metric name inside another metric.
- Aggregations only appear in metrics. Field expressions are scalar.
- Field names and dataset-scoped metric names share one namespace per dataset.
  On a clash, suffix the metric with `_metric`.
- Names must be sanitized SQL identifiers (see Conventions in the mapping). The
  original Steep identifier stays in the STEEP extension.
- A `count` metric used in model scope counts `DISTINCT` primary keys, never
  `COUNT(*)`, which would count joined rows.
- Put a portable expression in `expression.sql` (OSSIE_SQL_2026). When custom SQL
  uses warehouse-specific functions you cannot rewrite with certainty, put it
  under `expression.dialects` with the warehouse dialect and omit `sql`.
- Leave `datatype` out when you do not know the column type. Steep files only
  type dimensions and entity properties.

### 3. Write and validate

1. Write the document as YAML, in this key order: `version`, `name`,
   `description`, `ai_context`, `datasets`, `relationships`, `metrics`,
   `custom_extensions`.
2. Validate it with the script in this skill's folder:

   ```bash
   python3 <path-to-this-skill>/scripts/validate_ossie.py <output>.ossie.yaml
   ```

   The script checks the bundled Ossie JSON Schema plus the reference rules the
   schema cannot express. It needs PyYAML and jsonschema
   (`python3 -m pip install pyyaml jsonschema`). If you cannot install them,
   check the document by hand against `references/mapping.md` and say so in the
   report.
3. Fix every `ERROR` and rerun until it passes. `WARNING`s do not fail the run,
   but read each one: it usually means a metric does not mean what the Steep
   metric meant.

### 4. Report

End with a short conversion report:

- Counts: datasets, fields, metrics (and how many came from slices), relationships.
- **Lossy items**, each with the Steep identifier and why. Always list:
  - access policies (row-level security). They are carried in the extension
    only and are **not enforced by Ossie consumers**. Call this out first.
  - derived-ratio metrics whose operands are on different datasets or time columns,
  - model-scoped `count` metrics on a module without a primary key,
  - custom SQL kept only as a warehouse dialect,
  - joins to tables that are not a module (carried in the dataset extension
    only, no relationship),
  - derived ratios with `filters` (assumed to apply to both operands; unverified, so check parity),
  - cohorts, time grains, resampling, `last-date` aggregation, entities and
    `targets:` files,
  - metric formats, currencies, units and decimals: Ossie has no display
    settings, so only the STEEP extension keeps them.
- Assumptions you made (model name, database, warehouse).
- When built from the API: that the extensions are not verbatim, and what the
  API did not provide.
- A reminder that the export is experimental and needs review.
