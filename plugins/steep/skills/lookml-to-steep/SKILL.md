---
name: lookml-to-steep
description: >-
  Experimental. Import a Looker project's LookML (views, explores, joins,
  dimensions and measures in `.lkml` files) into Steep semantic model YAML:
  `module:` files with dimensions, metrics, filters and join paths that Steep
  syncs from GitHub. Use this skill whenever someone wants to import, convert,
  migrate or translate LookML, a Looker model or Looker measures into Steep.
  It encodes how Steep computes metrics, filters, joins and time, so each
  imported metric means what the Looker measure meant instead of a guess from
  names.
---

# Import a LookML project into Steep

**Experimental.** Tell the user that the import needs human review before it is
merged, because merging to the connected branch syncs it straight into their
workspace.

Converts the views and measures of one Looker project into Steep semantic model
YAML files (one `module:` YAML file per view on a table). The field-by-field
mapping is in [`references/mapping.md`](references/mapping.md). Read it before
writing any output.

## Sources

- **LookML:** the reference pages under
  <https://cloud.google.com/looker/docs/reference/lookml-quick-reference>,
  in particular measure types, dimension types, `dimension_group`, measure
  `filters`, join `relationship`, and
  <https://cloud.google.com/looker/docs/filter-expressions>.
- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Bundled schema:** `references/steep-module-schema.json` is the JSON Schema of
  a Steep `module:` file, generated from Steep's schema source on 2026-10-29. On
  any conflict, the code reference page wins.

## Workflow

### 1. Collect the input

1. Find the Looker project: a folder with `*.model.lkml` and `*.view.lkml`
   files, usually its own git repository. If the user has only a Looker
   instance, ask for the project's repository; failing that, read the
   explores through the Looker API (mapping: "Reading the input").
2. Resolve `include`s, `@{constants}`, `extends` and refinements (`+view`)
   before mapping anything (mapping: "Reading the input"). The `lkml` Python
   package parses the files; install it if you can.
3. If the project has several models, ask which ones to import. Import the
   views their explores use.
4. Look for an existing Steep repo: `*.yml` / `*.yaml` files whose root key is
   `module` or `targets`. If there is one, the import adds to it (step 3).
5. Ask only for what the project cannot tell you, with these defaults:
   - **Warehouse** behind the model's `connection`. It decides the case of
     physical names and the SQL dialect. Confirm the Steep workspace runs on
     the same warehouse; if not, custom SQL needs translating.
   - **Database**: confirm the Steep connection points at the views'
     database, since Steep modules cannot name one.
   - **Time column** of each view with more than one candidate (mapping:
     "Metric `time`"). Ask once, listing every such view and its candidates.
   - **Column types** of dimensions, if you cannot query `information_schema`.
     Otherwise trust the LookML type and say so.
   - **Time zone conversion**: whether the Looker connection converts to a
     query time zone.
   - **Output folder**: the folder the existing Steep files are in, else
     `modules/`.

### 2. Build the modules

Follow `references/mapping.md` in this order:

1. **Modules**: one per view on a table. Views on derived tables are skipped.
2. **Resolve** every field to a physical column, or mark it computed.
3. **Dimensions**: visible text and boolean column fields only. List the
   others.
4. **Time columns**: candidates per view, then each measure's `time`.
5. **Join paths** from the explores' joins, declared once per table pair, in
   the module on the one side.
6. **Measures**: type from the measure type table, filters from the filter
   expression tables, `dimensions` (`this.*` plus the modules reachable from
   many to one).
7. **Number measures**: ratios become `ratio`, `derived-ratio` (with a
   filtered operand as a slice) or `custom-ratio`; single-view expressions
   become `custom-value`. Skip the rest.
8. **Skip** post-SQL measures (`percent_of_total`, `percent_of_previous`,
   `running_total`), `period_over_period`, and non-numeric measures. Report
   each.

Rules that are easy to get wrong:

- LookML measures do not name a time field. Every Steep metric except a
  derived ratio needs one. Use the view's only candidate, or a
  `period_over_period`'s `based_on_time`; otherwise ask. Never pick one
  silently.
- A measure's identifier is its name only when no other imported measure has
  it. `count` in two views becomes `orders_count` and `users_count`.
- `relationship` defaults to `many_to_one` and describes the view on the
  other side of `sql_on` → the joined view, not always the explore's base
  view.
- `filters:` on a measure is a Looker filter expression, not SQL: `,` is OR,
  `-` negates strings, `NOT` negates numbers, `%` is a wildcard, and dates
  are phrases. Map only what the tables in the mapping list.
- `${users.count}` inside an `orders` measure counts users among the orders
  in the query. Rewrite it as `COUNT(DISTINCT ORDERS.USER_ID)`, not as a
  separate users metric.
- Steep has no computed columns. A computed dimension, `yesno` condition or
  `sql` can only appear inside custom SQL. It can never be a dimension,
  `time`, `value`, filter column or join column.
- Steep quotes every identifier, so physical names keep the case the warehouse
  stored them in: an unquoted `amount` on Snowflake is `AMOUNT`.
- Custom SQL runs verbatim. Replace `${TABLE}` and `${field}` with columns
  qualified by their physical table name, not the view name.
- Write `format` on every ratio. Steep defaults to `percentage`.
- One join path per pair of tables, single-column keys only. A duplicate fails
  the whole sync.
- Never write `accessPolicies`, even when explores have `access_filter`.

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
  that, when they are the same name after sanitizing (`total_revenue` and
  `total-revenue`). On a match, compare the two definitions: identical means
  skip it, different means ask. Never add a second metric for the same thing
  under a sanitized identifier.

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

- Which models were imported, and whether the input was the repository or the
  Looker API.
- Counts: modules, dimensions, metrics by `type`, slices, join paths.
- **Needs a decision**: time columns you asked about or inferred, ratio
  formats you guessed, dimension types you could not read, `country` types.
- **Not imported**, each with the LookML name and why. This covers everything
  under "Not representable in Steep" in the mapping that the project uses,
  derived-table views first.
- **Changed meaning**:
  - Derived ratios whose operands use different time columns.
  - Explore-level filters (`sql_always_where`, `always_filter`,
    `access_filter`) that Steep metrics do not apply.
  - String filters of a `case_sensitive: no` model, `yesno` dimensions
    imported as booleans, time zone conversion, `week_start_day`.
  - Filtered metrics: a group with no matching rows is absent rather than `0`.
    Say this once.
- Dimensions left out, so the user can add the ones they want.
- Assumptions you made (warehouse, database, schema names, output folder).
- A reminder that the import is experimental, and that merging it to the
  connected branch syncs it into Steep.

Do not commit or push unless the user asks. When they do, use a branch and a
pull request so the import is reviewed before it syncs.
