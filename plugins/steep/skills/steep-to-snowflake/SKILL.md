---
name: steep-to-snowflake
description: >-
  Experimental. Export a Steep semantic model (its `module:` YAML, or
  the definitions behind a Steep workspace) to a Snowflake semantic view, as a
  `CREATE SEMANTIC VIEW` statement. Use this skill whenever someone wants to
  export, convert, translate or publish Steep modules, metrics, dimensions,
  slices or join paths to Snowflake semantic views, Cortex Analyst or Snowflake
  Intelligence, or asks for semantic view DDL from Steep. It encodes how Steep
  computes metrics, filters and snapshots, so the view means the same thing as
  the Steep metric instead of a guess from field names.
---

# Export a Steep semantic model to a Snowflake semantic view

**Experimental.** Tell the user that the export needs human review and a parity
check before anyone relies on it.

Converts Steep semantic model YAML files (YAML documents with a `module:` root) into one
`CREATE OR ALTER SEMANTIC VIEW` statement. The field-by-field mapping is in
[`references/mapping.md`](references/mapping.md), and the Snowflake rules it
targets are in
[`references/semantic-view-syntax.md`](references/semantic-view-syntax.md). Read
both before writing any output.

## Sources

- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Snowflake:** the pages listed at the top of
  `references/semantic-view-syntax.md`, condensed there on 2026-10-29. If
  Snowflake rejects something the reference allows, the live docs win. Say so
  in the report.

## Workflow

### 1. Collect the input

1. Find the Steep files: every `*.yml` / `*.yaml` whose root key is `module`.
   Ignore `targets:` documents and list them in the report. If the user has no
   files but the Steep MCP server is connected, rebuild the same information
   with `list_modules`, `list_metrics`, `get_metric` and `list_entities`. Say in
   the report that the export came from the API. The API returns a metric's
   `format` but not its `currency`, `unit` or `decimals`: report them as not
   carried over.
2. Ask only for what the files cannot tell you, with these defaults:
   - **View name**: default is the repo or folder name, sanitized.
   - **Where the view lives**: `database.schema`. There is no default; ask.
   - **Source database** for the tables: default is the view's database.
   - **Does the Steep workspace run on Snowflake?** Default yes. If not, custom
     SQL needs translating and is reported as unreviewed.
   - **Private metrics**: default is to leave them out.
   - **Output path**: default is `<view name>.semantic-view.sql` next to the
     Steep files.

### 2. Build the view

Follow `references/mapping.md` in this order:

1. **Resolve** every column path to a `(logical table, column)` pair.
2. **TABLES**: one logical table per module, on its `database.schema.table`,
   with the entity's primary key.
3. **RELATIONSHIPS** from `joinPaths`, many side first, named
   `<declaring module>_to_<other>`. Add a `UNIQUE` key for each referenced
   column that is not a primary key, and for the `from` column of a
   `one-to-one`. Drop self-joins, joins to non-modules, and joins that close a
   cycle.
4. **DIMENSIONS**: Steep dimensions, every metric time column, and entity
   properties. Add a `<time>_day` dimension for each `last-date` metric.
5. **FACTS**: only the `PRIVATE` facts a metric needs to reach another table's
   column that has no dimension.
6. **METRICS**: one per metric and one per slice, with filters folded into the
   aggregate. Derived ratios become derived metrics without a table prefix.
7. `COMMENT`, then `AI_SQL_GENERATION` with the agent instructions and three
   marker lines for the import: `Time dimension per metric`, `Steep
   identifiers`, `Format per metric` and `Display names`.

Rules that are easy to get wrong:

- Steep quotes every identifier, so physical names keep their exact case.
  Leave a name unquoted only when it is already upper-case and not reserved.
- Always write tables as `database.schema.table`. A two-part name resolves
  against each user's session database.
- A metric reads its own table's columns directly. Another table's columns
  must go through a dimension or fact on that table. That table must be on the
  one side, reached by following `REFERENCES`, or joined one-to-one.
- Display names (metric `name`, module or dimension `label`) go in the
  `Display names` marker line, never in `WITH SYNONYMS`. Snowflake has no label
  field.
- Snowflake has no `FILTER (WHERE …)`. Use `SUM(IFF(F, v, NULL))`,
  `COUNT_IF(F)` and `COUNT(DISTINCT IFF(F, v, NULL))`.
- Snowflake resolves a name to a semantic expression before a column. A metric
  named like a column it reads breaks, so suffix it with `_metric`.
- `last-date` becomes `NON ADDITIVE BY (<alias>.<time>_day ASC NULLS FIRST)`.
  Only derived metrics may reference such a metric.
- Derived metrics combine metrics with scalar expressions only. They never
  reference physical columns or aggregate a metric.
- Always write `COMMENT`. `CREATE OR ALTER` unsets anything left out.

### 3. Write and validate

1. Write the statement in the layout of the example at the end of
   `references/mapping.md`: one item per line, modifiers indented below it.
2. Validate it with the script in this skill's folder:

   ```bash
   python3 <path-to-this-skill>/scripts/validate_semantic_view.py <output>.semantic-view.sql
   ```

   It checks clause order, keys behind relationships, cycles, duplicate names,
   unquoted reserved keywords, references to unknown tables, physical columns
   of other tables, references to the many side of a relationship, metrics
   that aggregate metrics, derived metric rules and `NON ADDITIVE BY` use. It
   needs only Python 3.10 or later.
3. Fix every `ERROR` and rerun until it passes. `WARNING`s do not fail the run,
   but resolve each one.

### 4. Check it in Snowflake (when the user has access)

Offline validation cannot see the physical tables. If the user can run SQL in
Snowflake (Snowflake CLI, a Snowflake MCP server, or a worksheet they run
themselves), propose this. Never run it against a production schema without
asking:

1. Run the statement in a scratch schema and fix what Snowflake rejects.
2. `DESCRIBE SEMANTIC VIEW <name>` and compare the counts with the validator's.
3. **Parity check**: pick three metrics, including any `last-date` metric and a
   filtered or sliced one. For each, query the same closed period in Snowflake
   (`SELECT * FROM SEMANTIC_VIEW(<name> METRICS … WHERE …)`) and in Steep
   (`query_metric` over the Steep MCP server, or ask the user to read it in
   Steep). Report any difference. Do not adjust the export to hide one.

### 5. Report

End with a short conversion report:

- Counts: tables, relationships, facts, dimensions, metrics (how many from
  slices, how many derived).
- **Lossy items**, each with the Steep identifier and why. Always list, in this
  order:
  - access policies (row-level security). Call this out first: the view does
    **not** filter rows per Steep member,
  - private metrics that were skipped,
  - metrics left out, and why,
  - approximate derived ratios and `last-date` metrics to verify,
  - dropped or duplicate joins, and `one-to-one` joins whose `from` column
    is assumed unique,
  - everything under "Not carried over" in the mapping that the model uses.
- Assumptions (view name and location, source database, warehouse).
- The parity check results, or that it was not run.
- A reminder that the export is experimental and needs review.
