---
name: snowflake-to-steep
description: >-
  Experimental. Import a Snowflake semantic view (its YAML from
  SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW, its CREATE SEMANTIC VIEW DDL, or a
  legacy Cortex Analyst semantic model file) into Steep semantic model YAML:
  `module:` files with dimensions, metrics, filters and join paths that Steep syncs from
  GitHub. Use this skill whenever someone wants to import, convert, migrate or
  translate a Snowflake semantic view, Cortex Analyst model or Snowflake
  Intelligence metrics into Steep, or to restore a Steep model from a
  `steep-to-snowflake` export. It encodes how Steep computes metrics, filters,
  joins and snapshots, so each imported metric means what the Snowflake metric
  meant instead of a guess from names.
---

# Import a Snowflake semantic view into Steep

**Experimental.** Tell the user that the import needs human review before it is
merged, because merging to the connected branch syncs it straight into their
workspace.

Converts one Snowflake semantic view into Steep semantic model YAML files (one `module:`
YAML file per logical table). The field-by-field mapping is in
[`references/mapping.md`](references/mapping.md). Read it before writing any
output.

## Sources

- **Snowflake:** the YAML specification for semantic views,
  <https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec>,
  and [CREATE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
  for DDL input.
- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Bundled schema:** `references/steep-module-schema.json` is the JSON Schema of
  a Steep `module:` file, generated from Steep's schema source on 2026-10-29. On
  any conflict, the code reference page wins.

## Workflow

### 1. Collect the input

1. Get the view definition, preferring YAML because it carries data types:
   - **YAML**: `SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('<db>.<schema>.<view>');`
     (needs any privilege on the view);
   - **DDL**: `SELECT GET_DDL('SEMANTIC_VIEW', '<db>.<schema>.<view>');` (needs
     REFERENCES or OWNERSHIP), or a `.sql` file the user has, such as a
     `steep-to-snowflake` export;
   - **Legacy Cortex Analyst YAML**: a semantic model file from a stage.

   If you can run SQL in Snowflake (Snowflake CLI, a Snowflake MCP server), fetch
   it yourself. Otherwise give the user the statement to run, and ask them to
   paste the result or save it to a file.
2. If the instructions contain a `Time dimension per metric:`,
   `Steep identifiers:`, `Format per metric:` or `Display names:` line, the
   view came from Steep
   (a `steep-to-snowflake` export). The mapping restores time columns,
   identifiers, formats and currencies, display names, slices and join paths from it. Metric
   names that use `<metric>__<slice>` are slice candidates in any view.
3. Look for an existing Steep repo: `*.yml` / `*.yaml` files whose root key is
   `module` or `targets`. If there is one, the import adds to it (step 3).
4. Ask only for what the view cannot tell you, with these defaults:
   - **Does the Steep workspace run on Snowflake?** Default yes. If not, custom
     SQL needs translating, and the case rules for column names differ.
   - **Database**: confirm the Steep connection points at the view's database,
     since Steep modules cannot name one.
   - **Time column** per module, when a table has several date columns and
     nothing in the view names one (mapping: "Metric `time`"). Ask once per
     module.
   - **Output folder**: the folder the existing Steep files are in, else
     `modules/`.

   With DDL input, column types are unknown. Read them from the warehouse
   (`DESCRIBE TABLE`, `information_schema.columns`) if you can, else ask.

### 2. Build the modules

Follow `references/mapping.md` in this order:

1. **Modules**: one per logical table on a physical table. Skip query-based
   tables. Two logical tables on one base table become one module.
2. **Resolve** every fact and dimension to a physical column, or mark it
   computed.
3. **Dimensions**: text and boolean column dimensions only. List the others.
4. **Metrics**: type from the expression table, `time`, filters, snapshots
   (`NON ADDITIVE BY` → `last-date`), `dimensions` (`this.*` plus the joined
   modules on the one side), and slices from `<metric>__<slice>`.
5. **Derived metrics**: ratios become `derived-ratio`. Single-table expressions
   are inlined. Skip the rest.
6. **Join paths** from relationships, declared once per table pair, in the
   module the relationship name starts with when that fits the keys.
7. **Instructions and verified queries** onto modules, metrics and
   dimensions.

Rules that are easy to get wrong:

- Snowflake metrics have no time column, and every Steep metric except a
  derived ratio needs one. Never pick one silently when a table has several.
- Steep has no computed columns. A computed fact or dimension can only appear
  inside custom SQL. It can never be a dimension, `time`, `value`, filter or
  join column.
- Steep dimensions are string or boolean columns. `type: time` dimensions on
  date columns exist only for cohorts, which Snowflake does not have, so the
  import makes none.
- Steep quotes every identifier, so physical names keep the case Snowflake
  stored them in: an unquoted `amount` is `AMOUNT`.
- Custom SQL runs verbatim. Qualify every column with its physical table name,
  not the logical table name.
- Steep applies `filters` to the whole metric. Use them only when the same
  predicate filters every aggregate in the expression.
- Write `format` on every ratio. Steep defaults to `percentage`.
- Write `currency`, `unit` or `decimals` only from a `Format per metric`
  entry, or when the metric's name, comment or synonyms state them. A ratio with a
  `currency` needs `format: number`.
- The marker lines (`Time dimension per metric`, `Steep identifiers`,
  `Format per metric`, `Display names`) fill fields. Never copy them into `agent_instructions`.
- One join path per pair of tables, single-column keys only. A duplicate fails
  the whole sync.
- Private metrics are helpers: import one only as a derived-ratio operand,
  unlisted.
- Never write `accessPolicies`. Snowflake row access policies live on the
  tables, not in the view.

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
  - a `currency` or `unit` that Steep drops: on a percentage, or both together.
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

- Counts: modules, dimensions, metrics by `type`, slices, join paths.
- **Needs a decision**: time columns you could not choose, ratios whose
  `format` you guessed, money metrics whose currency nothing states, dimension
  types you could not read (DDL input).
- **Not imported**, each with the Snowflake name and why. This covers
  everything under "Not representable in Steep" in the mapping that the view
  uses.
- **Changed meaning**:
  - Metric filters: a group with no matching rows is absent rather than `0`.
    Say this once.
  - Derived ratios whose operands use different time columns.
  - Metrics that relied on `USING`.
- **Row-level security**: Snowflake row access and masking policies are not in
  the view, and Steep queries with its own connection role. Call this out when
  the user's tables have such policies, or when you cannot tell.
- Dimensions left out, so the user can add the ones they want.
- Assumptions you made (database, warehouse, output folder).
- A reminder that the import is experimental, and that merging it to the
  connected branch syncs it into Steep.

Do not commit or push unless the user asks. When they do, use a branch and a
pull request so the import is reviewed before it syncs.
