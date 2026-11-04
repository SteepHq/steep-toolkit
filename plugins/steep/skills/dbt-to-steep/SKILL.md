---
name: dbt-to-steep
description: >-
  Experimental. Import a dbt Semantic Layer (MetricFlow) project, in the latest
  YAML spec or the legacy `semantic_models` / `measures` spec, into Steep
  semantic model YAML: `module:` files with dimensions, metrics, filters and
  join paths that Steep syncs from GitHub. Use this skill whenever someone
  wants to import, convert, migrate or translate dbt semantic models, dbt
  metrics, MetricFlow definitions or a `semantic_manifest.json` into Steep. It
  encodes how Steep computes metrics, filters, joins and snapshots, so each
  imported metric means what the dbt metric meant instead of a guess from
  names.
---

# Import a dbt Semantic Layer project into Steep

**Experimental.** Tell the user that the import needs human review before it is
merged, because merging to the connected branch syncs it straight into their
workspace.

Converts the semantic models and metrics of one dbt project into Steep semantic
model YAML files (one `module:` YAML file per semantic model). Both dbt specs
are supported: the latest spec (`semantic_model:` and `metrics:` inside each
model) and the legacy spec (top-level `semantic_models:` with `measures`). The
field-by-field mapping is in [`references/mapping.md`](references/mapping.md).
Read it before writing any output.

## Sources

- **dbt:** the latest spec and its differences from the legacy one,
  <https://docs.getdbt.com/docs/build/latest-metrics-spec>, and the metric
  pages under <https://docs.getdbt.com/docs/build/metrics-overview>.
- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Bundled schema:** `references/steep-module-schema.json` is the JSON Schema of
  a Steep `module:` file, generated from Steep's schema source on 2026-10-29. On
  any conflict, the code reference page wins.

## Workflow

### 1. Collect the input

1. Find the dbt project (`dbt_project.yml`). Prefer
   `target/semantic_manifest.json`: it has refs, docs blocks and Jinja
   resolved, the physical table of each semantic model, and one shape for
   both specs. If `target/` is missing or stale and you can run dbt, run
   `dbt parse`. Otherwise read the YAML files (mapping: "Reading the input").
2. Tell the specs apart: a model with `semantic_model:` is the latest spec; a
   top-level `semantic_models:` key, or metrics with `type_params`, is the
   legacy spec. A project can mix both while it migrates. Read legacy YAML
   through "Reading the legacy spec" in the mapping.
3. Never import from `target/osi_document.json`, the Ossie / OSI document dbt
   also writes. It drops offsets (a week-over-week metric becomes `a - a`),
   cumulative windows, non-additive dimensions, each metric's time dimension
   and labels. Its filters use dbt names (`order__status`), not columns. Ask
   for the dbt project or `semantic_manifest.json` instead. If the user has
   only the OSI document, use the `ossie-to-steep` skill. First tell them
   these losses mean every metric needs checking against its dbt definition.
4. Look for an existing Steep repo: `*.yml` / `*.yaml` files whose root key is
   `module` or `targets`. If there is one, the import adds to it (step 3).
5. Ask only for what the project cannot tell you, with these defaults:
   - **Warehouse**: `metadata.adapter_type` in `target/manifest.json`, or the
     profile's `type`. It decides the case of physical names. Confirm the Steep
     workspace runs on the same warehouse; if not, custom SQL needs
     translating.
   - **Database**: confirm the Steep connection points at the models'
     database, since Steep modules cannot name one.
   - **Column types** of categorical dimensions, which dbt usually does not
     record: read them from `target/catalog.json` (`dbt docs generate`),
     `data_type` in the YAML, or `information_schema` if you can query the
     warehouse. Otherwise ask once, listing the columns.
   - **Output folder**: the folder the existing Steep files are in, else
     `modules/`.

### 2. Build the modules

Follow `references/mapping.md` in this order:

1. **Modules**: one per semantic model, on the model's physical table.
2. **Resolve** every entity and dimension to a physical column, or mark it
   computed.
3. **Dimensions**: text and boolean categorical columns only. List the others.
4. **Join paths** from entities shared between models, declared once per table
   pair, in the module on the one side.
5. **Simple metrics**: type from the aggregation table, `time` from
   `agg_time_dimension`, `time_grains` from its granularity, filters,
   snapshots (`non_additive_dimension` with `max` → `last-date`), and
   `dimensions` (`this.*` plus the modules reachable from many to one).
6. **Ratio and derived metrics**: same-module sums become `ratio`; other
   ratios and `a / b` derived metrics become `derived-ratio`, with filtered
   inputs as slices. Single-module expressions are inlined. Skip the rest.
7. **Skip** cumulative and conversion metrics, and derived metrics with
   offsets. Report each.

Rules that are easy to get wrong:

- In legacy YAML, a measure is not a metric. Import a measure only through
  the simple metric that wraps it (or `create_metric: true`), with that
  metric's name, label and filter.
- Every Steep metric except a derived ratio needs a time column. dbt always
  names one (`agg_time_dimension`, or the semantic model's default). Use it;
  never pick another.
- `{{ Dimension('customer__segment') }}` names a column through an entity. Use
  the entity to find the model, and write `table` on the filter when it is not
  the metric's own module.
- Steep has no computed columns. A computed dimension, entity or `expr` can
  only appear inside custom SQL. It can never be a dimension, `time`, `value`,
  filter or join column.
- Steep dimensions are string or boolean columns. dbt categorical dimensions
  can be numbers: check the type.
- Steep quotes every identifier, so physical names keep the case the warehouse
  stored them in: an unquoted `amount` on Snowflake is `AMOUNT`.
- Custom SQL runs verbatim. Qualify every column with its physical table name,
  not the semantic model name.
- dbt ratios are fractions. Write `format` on every ratio. Steep defaults to
  `percentage`.
- One join path per pair of tables, single-column keys only. A duplicate fails
  the whole sync.
- Never write `accessPolicies`. dbt has no row-level security of its own.

### 3. Write into the repo

- One module per file, named `<module identifier>.yaml`, in block-style YAML.
  Key order follows `references/mapping.md`. `joinPaths` and `accessPolicies`
  are camelCase; everything else is snake_case.
- Start every file you write, module or `targets:`, with this line, so editors
  check it against Steep's schema as people edit it:
  `# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`.
  Add it to an existing file you change if it is missing.
- **Existing repo:** never remove or rewrite what is there. Removing a field
  from Steep YAML deletes it in Steep on the next sync. Add new dimensions,
  metrics and join paths to the module already on that table. An imported
  metric matches an existing one when the identifiers are equal, or, failing
  that, when they are the same name after sanitizing (`smb_orders` and
  `smb-orders`). On a match, compare the two definitions: identical means skip
  it, different means ask. Never add a second metric for the same thing under
  a sanitized identifier.

### 4. Validate

```bash
python3 <path-to-this-skill>/scripts/validate_steep_import.py <output-folder>
```

Pass the whole Steep folder, not just the new files, so it can find duplicates
across files.

- **First pass:** every module file is checked against the bundled JSON Schema.
- **Second pass:** the rules that fail a Steep sync:
  - duplicate module, metric, entity, slice and dimension identifiers;
  - two modules on one table, and duplicate join paths;
  - derived-ratio operands and metric dimensions that do not resolve.
  - a `targets:` file that is not exactly one `{schema, table}` object.
- **Warnings** for likely import mistakes:
  - a file without the schema line;
  - a ratio without `format`;
  - `FILTER (WHERE` in custom SQL;
  - a column on a table the module cannot reach through join paths.

It needs PyYAML and jsonschema (`python3 -m pip install pyyaml jsonschema`). If
you cannot install them, check the files by hand against
`references/mapping.md` and say so in the report.

Fix every `FATAL` and `ERROR` and rerun until it passes. Read every `WARNING`.
The checker cannot see the warehouse, so it never confirms that a table or
column exists.

### 5. Report

End with a short import report:

- Which spec the input used (latest, legacy or both), and whether it was read
  from `semantic_manifest.json` or the YAML files.
- Counts: modules, dimensions, metrics by `type`, slices, join paths.
- **Needs a decision**: ratio formats you guessed, dimension types you could
  not read, time dimensions that are computed.
- **Not imported**, each with the dbt name and why. This covers everything
  under "Not representable in Steep" in the mapping that the project uses.
- **Changed meaning**:
  - Derived ratios whose operands use different time columns.
  - Metrics that used `join_to_timespine` or `fill_nulls_with`.
  - Metric filters: a group with no matching rows is absent rather than `0`.
    Say this once.
- Dimensions left out, so the user can add the ones they want.
- Assumptions you made (warehouse, database, schema names, output folder).
- A reminder that the import is experimental, and that merging it to the
  connected branch syncs it into Steep.

Do not commit or push unless the user asks. When they do, use a branch and a
pull request so the import is reviewed before it syncs.
