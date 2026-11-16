---
name: ossie-to-steep
description: >-
  Experimental. Import an Apache Ossie (Open Semantic Interchange, OSI) semantic
  model document into Steep semantic model YAML: `module:` files with dimensions,
  metrics, filters and join paths that Steep syncs from GitHub. Use this skill
  whenever someone wants to import, convert or translate an `.ossie.yaml` / OSI
  model, or a semantic model exported from another BI or AI tool through Ossie,
  into Steep, or to restore a Steep model from an Ossie export. It encodes how
  Steep computes metrics, filters and joins, so each imported metric means what
  the Ossie expression meant instead of a guess from names.
---

# Import an Apache Ossie semantic model into Steep

**Experimental.** Ossie's spec `0.2.0.dev0` is an unreleased draft and may
change. Tell the user that the import needs human review before it is merged,
because merging to the connected branch syncs straight into their workspace.

Converts one Ossie core-spec document into Steep semantic model YAML files (one `module:`
YAML file per dataset). The field-by-field mapping is in
[`references/mapping.md`](references/mapping.md). Read it before writing any
output.

## Sources

- **Ossie core spec:** <https://github.com/apache/ossie/blob/main/core-spec/spec.md>
  and the expression language in `core-spec/expression_language.md`.
- **Steep semantic model YAML:** <https://help.steep.app/setup-and-manage/code-reference> is
  canonical for the Steep YAML.
- **Bundled schema:** `references/steep-module-schema.json` is the JSON Schema of
  a Steep `module:` file, generated from Steep's schema source on 2026-10-29. On
  any conflict, the code reference page wins. When the page is unreachable, work
  from the bundled schema and say so in the report.

## Workflow

### 1. Collect the input

1. Read the Ossie document (YAML or JSON). If it has a `semantic_model` array, it
   is the pre-`0.2.0` shape: import one model at a time and ask which one when
   there are several. In `0.1.x` documents, names in metrics and relationships
   may be source columns rather than fields; resolve each against the fields
   first, then the source columns, and say so in the report.
2. If any object has a `custom_extensions` entry with `vendor_name: STEEP`, the
   document came from Steep (the `steep-to-ossie` skill). Restore from those
   extensions as the mapping's round-trip section says. A root extension with
   `"source": "api"` means the export was built from the Steep API, not YAML:
   its extensions are not verbatim, so drift-check everything and say so in the
   report.
3. Look for an existing Steep repo: `*.yml` / `*.yaml` files whose root key is
   `module` or `targets`. If there is one, the import adds to it (step 3).
4. Ask only for what the document cannot tell you, with these defaults:
   - **Warehouse** (Snowflake, BigQuery, Postgres, Redshift, Databricks, …). It
     decides the case of column names and the SQL of custom metrics. There is no
     default: ask.
   - **Schema** for a `source` without one. There is no default: ask.
   - **Database**: when `source` names one, confirm the Steep connection points
     at it, since Steep modules cannot name a database.
   - **Time column** per module, when a dataset has none or several
     (mapping: "Metric `time`"). Ask once per module.
   - **Output folder**: the folder the existing Steep files are in, else
     `modules/`.

   If the user can reach the warehouse (dbt docs, `information_schema`, a
   warehouse MCP), check the tables and columns there instead of trusting the
   document's names.

### 2. Build the modules

Follow `references/mapping.md` in this order:

1. **Modules**: one per dataset, from `source`. A query `source` cannot be a
   module; two datasets on one table must become one module.
2. **Fields**: resolve each to a physical column, or mark it computed.
3. **Dimensions**: only the fields the mapping's rules select. List the others.
4. **Metrics**: choose each metric's module, its `type` from the expression
   table, its `time` column, and its filters.
5. **Join paths** from `relationships`, declared once per table pair, on the
   module the mapping names (or where a STEEP extension put it).

Rules that are easy to get wrong:

- Ossie metrics have no time column, and every Steep metric except a derived
  ratio needs one. Never pick one silently when a dataset has several.
- Steep has no computed columns. A computed field can only appear inside custom
  SQL; it can never be a dimension, `time`, `value`, filter or join column.
- Steep quotes every identifier, so column names must be in the case the
  warehouse stored them in: `AMOUNT` on Snowflake for an unquoted `amount`.
- Custom SQL runs verbatim on the warehouse. Prefix every column with its table
  name and rewrite `FILTER (WHERE …)` as `CASE WHEN … THEN … END`, which most
  warehouses need.
- Steep applies `filters` to the whole metric. Use them only when the same
  predicate filters every aggregate in the expression.
- Restored metrics are copied verbatim from their extension, `format` included
  or not; the checker's "no 'format'" warning is expected for them. Write
  `format` explicitly on every ratio you build from an expression: Steep
  defaults to `percentage`.
- Ossie has no currency or unit. Write `currency`, `unit` or `decimals` on a new
  metric only when its name, description or `ai_context` states them. A ratio
  with a `currency` needs `format: number`.
- One join path per pair of tables, single-column keys only. A duplicate fails
  the whole sync.
- Never write `accessPolicies` (row-level security) except by restoring a STEEP
  extension, and only after showing the policies to the user and getting a yes.
  The document may have been edited by anyone who handled it.

### 3. Write into the repo

- One module per file, named `<module identifier>.yaml`, in block-style YAML.
  Key order follows `references/mapping.md`; `joinPaths` and `accessPolicies` are
  camelCase, everything else snake_case.
- Start every file you write, module or `targets:`, with this line, so editors
  check it against Steep's schema as people edit it:
  `# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`.
  Add it to an existing file you change if it is missing.
- **Existing repo:** never remove or rewrite what is there. Removing a field
  from Steep YAML deletes it in Steep on the next sync. Add new dimensions,
  metrics and join paths to the module already on that table. When an imported
  metric's identifier is already taken, compare the two definitions: identical
  means skip it, different means ask.
- A `targets:` file only comes from the root STEEP extension's `targets`
  object, and only when the repo has none (Steep allows one).

### 4. Validate

```bash
python3 <path-to-this-skill>/scripts/validate_steep_import.py <output-folder>
```

Pass the whole Steep folder, not just the new files, so it can find duplicates
across files. The checker validates every module file against the bundled JSON
Schema, then checks the rules that fail a Steep sync: duplicate module, metric,
entity, slice and dimension identifiers, two modules on one table, duplicate join
paths, derived-ratio operands and metric dimensions that do not resolve, a
`currency` or `unit` that Steep drops (on a percentage, or both together), and
a `targets:` file that is not exactly one `{schema, table}` object. It also
warns about likely import mistakes: a file without the schema line, a ratio
without `format` (expected for a
restored metric that had none), `FILTER (WHERE` in custom SQL, or a column on a
table the module cannot reach through join paths (table names in column paths
are case-sensitive). It needs PyYAML and jsonschema
(`python3 -m pip install pyyaml jsonschema`). If you cannot install them, check
the files by hand against `references/mapping.md` and say so in the report.

Fix every `FATAL` and `ERROR` and rerun until it passes. Read every `WARNING`.
The checker cannot see the warehouse: it never confirms that a table or column
exists.

### 5. Report

End with a short import report:

- Counts: modules, dimensions, metrics by `type`, join paths, and how many came
  back from STEEP extensions.
- **Needs a decision**: time columns you could not choose, ratios whose `format`
  you guessed, money metrics whose currency the source does not state, access
  policies waiting for approval.
- **Not imported**, each with the Ossie name and why: query sources, metrics
  without an aggregate or with only other dialects, composite or duplicate
  relationships, dropped databases, model-level `description` and `ai_context`,
  other vendors' extensions.
- **Changed meaning**: metric filters (a group with no matching rows is
  absent rather than `0`; say it once), derived ratios (Steep evaluates each operand on its own
  module and time column), custom SQL on a module with access policies, metrics
  restored from an extension that was changed after export.
- Fields left out of `dimensions`, so the user can add the ones they want.
- Assumptions you made (warehouse, schema, output folder).
- A reminder that the import is experimental, and that merging it to the
  connected branch syncs it into Steep.

Do not commit or push unless the user asks. When they do, use a branch and a
pull request so the import is reviewed before it syncs.
