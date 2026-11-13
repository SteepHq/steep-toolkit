# Snowflake semantic view → Steep semantic model YAML mapping

Snowflake side: a semantic view, read as YAML
(`SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`, spec at
<https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec>)
or as `CREATE SEMANTIC VIEW` DDL. Steep side: the `module:` document of Steep as
code (<https://help.steep.app/setup-and-manage/code-reference>), mirrored in
`steep-module-schema.json`. Every Snowflake property is either mapped, ignored
on purpose (listed below), or named in the report. Never drop one silently.

## Contents

- [Conventions](#conventions)
- [Views exported from Steep](#views-exported-from-steep)
- [Reading DDL instead of YAML](#reading-ddl-instead-of-yaml)
- [View (root)](#view-root)
- [Module ← logical table](#module--logical-table)
- [Resolving names to columns](#resolving-names-to-columns)
- [Dimension ← dimension](#dimension--dimension)
- [Metric ← table metric](#metric--table-metric)
- [Expressions → metric type](#expressions--metric-type)
- [Predicates → filters](#predicates--filters)
- [Slices](#slices)
- [Derived metrics](#derived-metrics)
- [Join path ← relationship](#join-path--relationship)
- [AI instructions and verified queries](#ai-instructions-and-verified-queries)
- [Not representable in Steep (report these)](#not-representable-in-steep-report-these)
- [Example](#example)

## Conventions

- **Semantic names.** Snowflake stores unquoted names in upper case, and
  references to them are case-insensitive. A Steep identifier is the
  `Steep identifiers` entry for the name (see
  [Views exported from Steep](#views-exported-from-steep)), else the Snowflake
  name in lower case when it is all upper case (`NEW_CUSTOMERS` →
  `new_customers`), else the name as written.
- **Sanitize** a name: lower-case it, turn runs of characters outside
  `a-z0-9_` into `_`, and trim `_`. **Same name** means equal after sanitizing.
- **Display names.** Snowflake has no labels.
  - In a view exported from Steep, the `Display names` marker line holds them
    (see [Views exported from Steep](#views-exported-from-steep)). An object
    with no entry gets no `label` (module, dimension), or its humanized
    identifier as metric `name`. Every synonym stays a synonym.
  - In any other view, the first synonym is the display name only when it is
    the same name as the object: use it and drop it from `synonyms`.
  - Otherwise humanize the Steep identifier for a metric `name`: `-` and `_`
    become spaces, first letter upper case (`avg_order_value` →
    `Avg order value`, `new-customers` → `New customers`).
- **Physical names** (schema, table, column) must be in the case Snowflake
  stored them in, because Steep quotes every identifier. An unquoted name in an
  expression or DDL folds to upper case (`amount` → `AMOUNT`). A quoted name
  keeps its exact text without the quotes. YAML read back from Snowflake
  already has `base_table` parts in stored case.
- **Key order** in a metric: `identifier`, `name`, `description`, `synonyms`,
  `agent_instructions`, `examples`, `type`, the type's fields (`value`,
  `distinct_on`, `numerator`, `denominator`, `sql_expression`, `numerator_sql`,
  `denominator_sql`), `format`, `currency`, `unit`, `decimals`, `time`,
  `time_aggregation`, `dimensions`, `filters`, `slices`, `is_unlisted`. Modules and dimensions follow the order of
  the rows in their tables below.
- **Report** in the chat, not in a file, unless the user asks for one.

## Views exported from Steep

A view written by the `steep-to-snowflake` skill has marker lines in
`module_custom_instructions.sql_generation` (DDL `AI_SQL_GENERATION`). Each is
one line, `<marker>: <name> → <value>; <name> → <value>; …`, and names match
Snowflake names case-insensitively:

| Marker | Restores |
| --- | --- |
| `Time dimension per metric:` | each metric's `time`: the column behind the named dimension |
| `Steep identifiers:` | the identifier of each named metric, slice (by its slice metric), dimension and derived metric; `table <alias> → <identifier>` names a module |
| `Format per metric:` | the `format` of each named metric, and its `currency`, `unit` and `decimals` when the entry lists them (`number, currency USD, decimals 0`). An older export lists only ratios, with the format alone. |
| `Display names:` | the `label` of each named module (`table <alias> → <label>`) and dimension, and the `name` of each named metric |

Any of these lines means the view came from Steep, which also decides how
display names are read (Conventions). Read the markers into those fields. Never
copy them into `agent_instructions`. An object with no `Steep identifiers`
entry keeps the identifier from Conventions.

## Reading DDL instead of YAML

DDL (from `SELECT GET_DDL('SEMANTIC_VIEW', '<db>.<schema>.<view>')` or a `.sql`
file) carries the same objects. Read it with this correspondence:

| DDL | YAML |
| --- | --- |
| `TABLES (alias AS db.schema.table PRIMARY KEY (…) UNIQUE (…) WITH SYNONYMS = (…) COMMENT = '…')` | `tables[]`: `name`, `base_table`, `primary_key`, `unique_keys`, `synonyms`, `description` |
| `RELATIONSHIPS (name AS a (cols) REFERENCES b (cols))` | `relationships[]`: `left_table: a`, `right_table: b`, `relationship_columns` |
| `FACTS (…)`, `DIMENSIONS (…)` | `facts[]`, `dimensions[]` (DDL does not separate `time_dimensions`) |
| `METRICS (t.m … AS expr)` | `tables[t].metrics[]`; `NON ADDITIVE BY` → `non_additive_dimensions`; `USING` → `using_relationships` |
| `METRICS (m AS expr)` without a table prefix | root `metrics[]` (derived) |
| `PRIVATE` | `access_modifier: private_access` |
| `AI_SQL_GENERATION`, `AI_QUESTION_CATEGORIZATION` | `module_custom_instructions.sql_generation`, `.question_categorization` |
| `AI_VERIFIED_QUERIES` | `verified_queries` |

DDL has no `data_type`. Where this file uses a data type, ask the user, or read
the column types from the warehouse (`DESCRIBE TABLE`, `information_schema`), and
say in the report which you did.

**Legacy Cortex Analyst YAML** (a semantic model file on a stage) has the same
shape, with `measures` in place of `facts` and `join_type` /
`relationship_type` on relationships. Read `measures` as facts and ignore the
two relationship keys.

## View (root)

| Snowflake | Steep |
| --- | --- |
| `name` | nothing. Use it for the output folder name only if the user wants one. |
| `description` | nothing: Steep has no workspace-level description. Report it. |
| `tables` | one module each |
| `relationships` | `joinPaths` |
| `metrics` (derived) | see [Derived metrics](#derived-metrics) |
| `module_custom_instructions`, `custom_instructions`, `verified_queries` | see [AI instructions](#ai-instructions-and-verified-queries) |
| `variables`, `tags`, `max_staleness` | nothing. Report them. |

## Module ← logical table

| Steep | From |
| --- | --- |
| `identifier` | the `table <alias>` entry of `Steep identifiers`, else the identifier of the module already on that table in the repo, else the table `name` per Conventions |
| `schema`, `table` | `base_table.schema`, `base_table.table` |
| `label` | the display name (Conventions) |
| `description` | `description` |
| `synonyms` | `synonyms`, minus a first synonym used as the display name |
| `agent_instructions` | the instruction lines addressed to this table (see [AI instructions](#ai-instructions-and-verified-queries)) |
| `dimensions` | see [Dimension ← dimension](#dimension--dimension) |
| `metrics` | this table's metrics, then derived metrics placed here |
| `joinPaths` | see [Join path ← relationship](#join-path--relationship) |

- **Database.** Steep modules cannot name one; the Steep connection fixes it.
  Drop `base_table.database`, and ask the user to confirm their Steep
  connection points at it. When tables name different databases, only one can
  be imported as is: ask which.
- **Query tables.** A `base_table` with `definition` (a SQL query) cannot be a
  Steep module. Skip the table and everything that references it, and suggest a
  view in the warehouse.
- **One table, one module.** Steep fails the whole sync when two modules use
  the same `schema.table`. Two logical tables on one base table (role-playing)
  become one module, the first in the view; report the second and every
  relationship it loses. If the target repo already has a module on that
  table, add to it instead.
- **Primary key.** Used to recognize `COUNT(<primary key>)` and one-to-one
  joins. Steep has no other slot for it unless the user wants an entity. Then
  add one entity (`identifier` and `name` from the table, `primary_key`, and
  `properties` from the module's dimensions with `type: string`), and ask which
  properties to keep.
- `tags` and table `filters` (standalone filters): report.

## Resolving names to columns

Inline facts and dimensions first: a reference to `t.<fact>` or `t.<dimension>`
in an expression is replaced by that item's `expr`, recursively, with its
unqualified columns qualified by `t`. Then every item is one of:

- **Column item**: the `expr` is a single column, optionally qualified or quoted
  (`AMOUNT`, `orders.AMOUNT`, `"Amount"`). It maps to that physical column.
- **Computed item**: anything else (`AMOUNT - DISCOUNT`, `YEAR(CREATED_AT)`).
  Steep has no computed columns, so it can only appear inside custom SQL. It
  cannot be a dimension, a metric `time`, a `sum` value, a filter column or a
  join column. Exception: `DATE_TRUNC('<part>', col)` and `col::DATE` /
  `TO_DATE(col)` resolve to `col` when used as a time column, because Steep
  truncates time itself.

## Dimension ← dimension

A Snowflake dimension becomes a Steep dimension when all of these hold:

- it is a column item on the table itself;
- its `data_type` is text (`VARCHAR`, `STRING`, `TEXT`, `CHAR`) or `BOOLEAN`.
  Steep dimensions are string or boolean columns, plus `type: time`
  dimensions on date columns, which only cohorts use. Snowflake has no
  cohorts, so the import makes no time dimensions;
- it has no `labels: [filter]`.

Dates and timestamps (in `dimensions` or `time_dimensions`) are time column
candidates instead (see [Metric `time`](#metric-time)). Numeric and computed
dimensions have no Steep form: list them in the report, and suggest a view
exposing a computed one as a text column.

| Steep | From |
| --- | --- |
| `column` | the physical column |
| `identifier` | the `Steep identifiers` entry; else the dimension's Steep identifier (Conventions) when it differs from the column compared case-insensitively; else omit it |
| `label` | the display name (Conventions) |
| `description` | `description` |
| `type` | `categorical`. Use `country` or `city` only when the user confirms the values are country codes or city names. |
| `synonyms` | `synonyms`, minus a first synonym used as the display name |
| `agent_instructions` | the instruction lines addressed to this dimension |

`sample_values`, `is_enum`, `cortex_search_service` and `tags` have no Steep
slot. Say once in the report that they were not carried.

## Metric ← table metric

The module is the metric's table.

| Steep | From |
| --- | --- |
| `identifier` | the metric `name`, per Conventions (the `Steep identifiers` entry first). Avoid identifiers already in the repo, unless it is the same metric (see SKILL.md, "Write into the repo"). |
| `name` | the display name (Conventions) |
| `description` | `description` |
| `synonyms` | `synonyms`, minus a first synonym used as the display name |
| `agent_instructions` | the instruction lines addressed to this metric |
| `examples` | verified query questions for this metric |
| `type` and its fields | see [Expressions → metric type](#expressions--metric-type) |
| `time` | see below |
| `time_aggregation` | `last-date` from `non_additive_dimensions`, see the expression table |
| `dimensions` | `this.*` when the module has dimensions, then `<schema>.<table>.*` for each module the metric's table reaches by following relationships from left table to right table (transitively, and both ways across a one-to-one), when that module has dimensions. These are the breakdowns Snowflake allows. Omit when empty. |
| `filters` | see [Predicates → filters](#predicates--filters) |
| `format` | on `ratio`, `custom-ratio` and `derived-ratio`, always written: the `Format per metric` entry, else `percentage` when the expression multiplied by 100 (drop the factor), else `number`. Steep defaults to `percentage`. On other types, write it only when the entry says `percentage`. |
| `currency`, `unit`, `decimals` | from the `Format per metric` entry. Without one, write a `currency` (ISO 4217 code), a `unit` (at most three characters) or `decimals` (0 to 6) only when the metric's name, comment or synonyms state it, such as `REVENUE_USD` or `LATENCY_MS`, and report money metrics whose currency nothing states. A ratio with a currency needs `format: number`; never write a unit with a currency or on a percentage. |
| `is_unlisted` | `true` for a private metric imported only as a derived-ratio operand |

**Private metrics** (`private_access`) are helpers. Import one only when a
derived ratio needs it as an operand, with `is_unlisted: true`. Otherwise skip
it and report it.

`using_relationships`: Steep has one join per pair of tables, so report the
metric. It is imported over whichever join Steep has.

### Metric `time`

Every Steep metric except `derived-ratio` needs `time: <table>.<column>`.
Snowflake metrics have none. In this order:

1. **Export marker.** An instruction line `Time dimension per metric: <metric>
   → <dimension>; …` (written by `steep-to-snowflake`) names it. Use the
   dimension's column.
2. **Snapshot.** For a metric with `non_additive_dimensions`, the time column
   behind that dimension.
3. **Candidates**: column items on the metric's table whose `data_type` is
   `DATE` or `TIMESTAMP*`, from `time_dimensions` and `dimensions`. One
   candidate: use it. Several: ask the user, once per module, and offer a
   per-metric override. None: ask for a column; if there is none, skip the
   module's metrics and report them.

Never pick one silently: the time column decides what "revenue in March" means.

## Expressions → metric type

Inline facts and dimensions first (see
[Resolving names to columns](#resolving-names-to-columns)). Then inline
references to other metrics on the same table, when the result is still one
expression. Strip outer parentheses. A factor of `100` is display scaling:
remove it and write `format: percentage`.

`x`, `a`, `b` are column items. `P` is a predicate. These forms are the same as
"`AGG(x)` filtered by `P`":

- `AGG(IFF(P, x, NULL))`;
- `AGG(CASE WHEN P THEN x END)`, or the same with `ELSE NULL`.

`NULLIF(e, 0)`, `DIV0(n, d)` and `DIV0NULL(n, d)` around a division are the
same as `n / d`, because Steep divides null-safely. Take the first row that
matches:

| Snowflake expression | Steep `type` | Steep fields |
| --- | --- | --- |
| `SUM(x)` [filtered by `P`] | `sum` | `value: <table>.<x>`, `filters` from `P` |
| `COUNT(*)`, `COUNT(1)`, `COUNT(<primary key>)` | `count` | |
| `COUNT_IF(P)`, `COUNT(CASE WHEN P THEN 1 END)`, `SUM(IFF(P, 1, 0))` | `count` | `filters` from `P` |
| `COUNT(x)` [filtered by `P`], other column | `count` | `filters`: `P` plus `x is-not null` |
| `COUNT(DISTINCT x)` [filtered by `P`] | `count-distinct` | `distinct_on: <table>.<x>`, `filters` from `P` |
| `SUM(a) / SUM(b)`, the same `P` (or none) on both | `ratio` | `numerator: <table>.<a>`, `denominator: <table>.<b>`, `filters` from `P`, `format` |
| `A / B`, both aggregates | `custom-ratio` | `numerator_sql: A`, `denominator_sql: B`, rewritten as custom SQL, `format` |
| any other expression with an aggregate (`AVG`, `MEDIAN`, `MAX`, …) | `custom-value` | `sql_expression`, rewritten as custom SQL |
| a window function (`OVER`), or no aggregate | none | skip and report |

**Snapshots.** `non_additive_dimensions` with one dimension, `ascending`, whose
time column is a date or timestamp column item → `time_aggregation:
last-date`, and that column is the metric's `time`. Steep takes each group's
latest day, which is what an ascending sort keeps. Anything else (`descending`,
several or non-time dimensions) has no Steep form: skip the metric and report
it, since summing the snapshots would overcount.

Filters become Steep `filters` only when `P` can be written as Steep filters
(next section). When it cannot, or when only some aggregates carry it, use the
custom-SQL row instead and keep `P` inside each aggregate.

**Custom SQL.** Steep runs `sql_expression`, `numerator_sql` and
`denominator_sql` on Snowflake as written, inside a query where each table is
aliased by its bare table name. So:

1. Replace each logical table qualifier with that table's physical table name
   (`orders.AMOUNT` → `ORDERS.AMOUNT` for base table `ORDERS`), and qualify
   every bare column with its table.
2. Inline computed facts and dimensions.
3. Keep Snowflake functions (`IFF`, `DIV0`, `COUNT_IF`): Steep runs on
   Snowflake. If the Steep workspace does not run on Snowflake, translate only
   what you are sure of, and skip and report the rest.
4. A reference to another table needs a join path from this module to it.

A computed or cross-table `x` in `SUM(x)` also makes it `custom-value`.

Steep `filters` are a `WHERE` on the metric query, while `IFF` in an aggregate
keeps every row. For one aggregate, or the same `P` on every aggregate, each
group gets the same value. The difference: a breakdown value or time bucket
with no matching row is absent instead of showing `0` or `NULL`. Mention this
once in the report.

## Predicates → filters

`P` maps to Steep filters when it is an `AND` of conditions of these forms,
where `f` is a column item of the module, or of a table joined to it. For a
joined table, add its `table`, and its `schema` if it differs.

| Snowflake | Steep `operator` | Steep `expression` |
| --- | --- | --- |
| `f = v`, `f <> v`, `f != v` | `equals`, `not-equals` | `v` |
| `f < v`, `<=`, `>`, `>=` | `less-than`, `less-than-or-equal`, `greater-than`, `greater-than-or-equal` | `v` |
| `f BETWEEN v1 AND v2` | two filters: `greater-than-or-equal` `v1`, `less-than-or-equal` `v2` | |
| `f IN (v1, v2)`, `f NOT IN (…)` | `in`, `not-in` | `v1,v2` |
| `f IS NULL`, `f IS NOT NULL` | `is`, `is-not` | `null` |
| `f = TRUE`, `f IS TRUE`, `f`, `NOT f` (boolean column) | `equals` | `true`, `false` |
| `f LIKE 'p'`, `f NOT LIKE 'p'` | `like`, `not-like` | `p` |

Steep renders `expression` by splitting it on commas. For each part, `TRUE`,
`FALSE`, `NULL` and anything that parses as JSON (numbers, `true`, `false`,
`null`) pass through unchanged. Anything else becomes a single-quoted string
literal, after stripping one pair of surrounding single quotes. So write `v` as:

- a number literal: as is, `100`;
- a string literal `'paid'`: without quotes, `paid`; an embedded `''` becomes a
  single `'` (Steep escapes it again);
- a string that would parse as JSON or a keyword (`'123'`, `'true'`, `'null'`),
  or that starts or ends with a space: keep the single quotes, `'123'`.

These cannot be Steep filters: `OR`, `NOT (…)` around a group, `ILIKE`,
`RLIKE`, functions on the column (`LOWER(f) = …`), two columns compared, a
computed item, date arithmetic (`f >= DATEADD(day, -30, CURRENT_DATE)`), and
string values containing a comma. Use custom SQL for those.

## Slices

Steep slices come back from metrics named `<parent>__<suffix>` on the same table
(the naming `steep-to-snowflake` uses). Map the candidate and `<parent>` to
Steep first, then compare the results, not the SQL text. The candidate is a
slice of `<parent>` when:

- `type`, its fields (`value`, `distinct_on`, `numerator`, …), `time` and
  `time_aggregation` are equal;
- its `filters` are the parent's, in any order, plus exactly one more.

So `SUM(IFF(c, orders.AMOUNT, NULL))` is a slice of `SUM(orders.AMOUNT)`, and
`COUNT_IF(c)` of `COUNT(*)`. Then append to the parent's `slices`:

| Steep | From |
| --- | --- |
| `name` | `<name>` from a `COMMENT` / `description` ending in `Slice: <name>.`, else the display name, else the humanized suffix |
| `identifier` | the `Steep identifiers` entry for the slice metric; else omit it when the suffix is the name in snake_case (Steep generates that); else the suffix in lower case |
| `filter` | the one extra filter |

A `COMMENT` / `description` of `<parent description> Slice: <name>.` (or just
`Slice: <name>.`) was written by the export; drop it. When the condition is not
one Steep filter, or the parent was skipped, import the metric on its own.

## Derived metrics

Root-level `metrics` combine table metrics. Resolve each referenced metric to
its Steep identifier, or to `{ metric, slice }` when it is a slice metric
restored above. The derived metric's own identifier, name and `format` follow
[Metric ← table metric](#metric--table-metric).

| Snowflake expression | Steep |
| --- | --- |
| `m1 / m2`, `m1 / NULLIF(m2, 0)`, `DIV0(m1, m2)`, `DIV0NULL(m1, m2)` [× 100] | `derived-ratio` with `numerator: m1`, `denominator: m2`, `format`; no `time` |
| any other expression whose metrics are all on one table | inline them and map as a table metric on that table (`custom-value` or `custom-ratio`) |
| anything else (`m1 + m2` across tables, aggregations of dimensions) | skip and report |

Place a derived ratio on the numerator's module, after that module's other
metrics. Steep computes each operand on its own module and time column, then
divides. That is what Snowflake does when the operands share a time dimension.
Report every derived ratio whose operands' `time` columns differ.

## Join path ← relationship

Snowflake `left_table` is the many side (it holds the foreign key), and
`right_table` the one side. Steep declares a join once, in one module:

| Case | Declared in | `from.column` | `to` | `type` |
| --- | --- | --- | --- | --- |
| `left_column` is not the left table's primary key or a unique key | the right table's module | `right_column` | the left table: `table`, `schema` if it differs, `column: left_column` | `one-to-many` |
| `left_column` is a key of the left table | the module the relationship name starts with, when the name is `<one alias>_to_<other alias>` (the export's naming, optionally followed by `_<column>`); else the left table's module | that module's column | the other table, and its column | `one-to-one` |

Columns are physical column names. Steep cannot represent:

- **composite keys** (several `relationship_columns`), **ASOF** and **range**
  joins: drop, report, and suggest a view with a single key column;
- **a second relationship between the same two tables** (either direction):
  Steep fails the sync on a duplicate. Keep the first and report the others;
- **a relationship to itself**, or to a skipped table: drop and report.

Relationship `name` has no Steep slot. It only picks the declaring module of
a one-to-one; do not report it.

## AI instructions and verified queries

Read `module_custom_instructions.sql_generation` (or the legacy
`custom_instructions`, or DDL `AI_SQL_GENERATION`) line by line:

- `<table>: <text>` → that module's `agent_instructions`.
- `<table>.<item>: <text>` → that metric's or dimension's `agent_instructions`.
- `Time dimension per metric: …`, `Steep identifiers: …`,
  `Format per metric: …` and `Display names: …` → the fields in
  [Views exported from Steep](#views-exported-from-steep), never text.
- Anything else stays view-wide: report it, and offer to copy it into the
  `agent_instructions` of the modules it applies to.

Names match case-insensitively. Join several lines for the same target with a
newline.

`question_categorization` (DDL `AI_QUESTION_CATEGORIZATION`) has no Steep slot:
report it.

**Verified queries.** When a query's `sql` selects exactly one metric (one name
in `METRICS …` of `SEMANTIC_VIEW(…)`, or one metric column), add its `question`
to that metric's `examples`. Report the others with their question.

## Not representable in Steep (report these)

- Query-based tables, role-playing duplicates of one base table.
- Computed, numeric and filter-labeled dimensions; standalone `filters`;
  computed facts outside custom SQL.
- Metrics with window functions, unsupported `non_additive_dimensions`, or only
  private use; derived metrics other than ratios across tables;
  `using_relationships`.
- Composite, ASOF, range, duplicate and self relationships.
- View `description`, view-wide instructions, `question_categorization`,
  verified queries with no single metric, `variables`, `tags`, `sample_values`,
  `is_enum`, Cortex Search services, `max_staleness` and materializations.
- **Row access and masking policies** live on the Snowflake tables, not in the
  view. Steep queries with its own connection role, and the import never writes
  Steep `accessPolicies`.

Steep features Snowflake does not carry, which stay empty: access policies,
cohorts, time grains, time resampling, categories, owners, `is_private`,
`is_unlisted` (except on private operands), entities (unless asked), entity
links and metrics, targets. Restoring a `steep-to-snowflake` export also loses
dimension `type`, per-metric allowed dimensions (all reachable ones come back),
and filters of custom SQL metrics (they stay inside the SQL). Derived ratios
come back on their numerator's module.

## Example

The view exported in the worked example of the `steep-to-snowflake` mapping,
as `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW` returns it (abridged). Someone added
`ORDER_NUMBER` and `NET_REVENUE` in Snowflake after the export.

```yaml
name: ACME
description: Exported from Steep on 2026-10-29.
tables:
  - name: ORDERS
    description: One row per order.
    base_table: { database: ANALYTICS, schema: SALES, table: ORDERS }
    dimensions:
      - name: COUNTRY
        synonyms: [market]
        expr: ORDERS.COUNTRY
        data_type: VARCHAR(2)
      - name: ORDER_NUMBER
        expr: ORDERS.ORDER_NUMBER
        data_type: NUMBER(38,0)
    time_dimensions:
      - name: CREATED_AT
        expr: ORDERS.CREATED_AT
        data_type: TIMESTAMP_NTZ(9)
    facts:
      - name: NET_AMOUNT
        expr: ORDERS.AMOUNT - ORDERS.DISCOUNT
        data_type: NUMBER(38,2)
        access_modifier: private_access
    metrics:
      - name: REVENUE
        synonyms: [sales]
        expr: SUM(IFF(ORDERS.STATUS IN ('paid', 'refunded'), ORDERS.AMOUNT, NULL))
      - name: REVENUE__WEB
        description: 'Slice: Web.'
        expr: SUM(IFF(ORDERS.STATUS IN ('paid', 'refunded') AND ORDERS.CHANNEL = 'web', ORDERS.AMOUNT, NULL))
      - name: SMB_ORDERS
        expr: COUNT_IF(CUSTOMERS.SEGMENT = 'smb')
      - name: NET_REVENUE
        expr: SUM(ORDERS.NET_AMOUNT)
  - name: CUSTOMERS
    synonyms: [clients]
    base_table: { database: ANALYTICS, schema: SALES, table: CUSTOMERS }
    primary_key: { columns: [ID] }
    dimensions:
      - name: SEGMENT
        description: Sales segment.
        expr: CUSTOMERS.SEGMENT
        data_type: VARCHAR(10)
      - name: SNAPSHOT_DATE_DAY
        expr: DATE_TRUNC('DAY', CUSTOMERS.SNAPSHOT_DATE)
        data_type: DATE
    time_dimensions:
      - name: CREATED_AT
        expr: CUSTOMERS.CREATED_AT
        data_type: TIMESTAMP_NTZ(9)
      - name: SNAPSHOT_DATE
        expr: CUSTOMERS.SNAPSHOT_DATE
        data_type: DATE
    metrics:
      - name: NEW_CUSTOMERS
        expr: COUNT(*)
      - name: TOTAL_BALANCE
        expr: SUM(CUSTOMERS.BALANCE)
        non_additive_dimensions:
          - { table: CUSTOMERS, dimension: SNAPSHOT_DATE_DAY, sort_direction: ascending, null_order: first }
relationships:
  - name: CUSTOMERS_TO_ORDERS
    left_table: ORDERS
    right_table: CUSTOMERS
    relationship_columns:
      - { left_column: CUSTOMER_ID, right_column: ID }
metrics:
  - name: REVENUE_PER_CUSTOMER
    expr: ORDERS.REVENUE / NULLIF(CUSTOMERS.NEW_CUSTOMERS, 0)
module_custom_instructions:
  sql_generation: |-
    orders.revenue: Excludes cancelled orders.
    Time dimension per metric: orders.revenue → orders.created_at; orders.revenue__web → orders.created_at; orders.smb_orders → orders.created_at; customers.new_customers → customers.created_at; customers.total_balance → customers.snapshot_date
    Steep identifiers: orders.smb_orders → smb-orders; revenue_per_customer → revenue-per-customer; customers.new_customers → new-customers; customers.total_balance → total-balance
    Format per metric: orders.revenue → number, currency USD; revenue_per_customer → number, currency USD
    Display names: table customers → Customers; orders.country → Country; orders.smb_orders → SMB orders
```

Steep, `modules/orders.yaml`:

- `Country` and `SMB orders` come from `Display names`. `Revenue` has no
  entry, so it is the humanized identifier.
- `REVENUE__WEB` maps to the parent's `sum` and `value` with one more filter,
  so it comes back as a slice. Its name comes from the comment, and its
  identifier is left out because `web` is what Steep generates from `Web`.
- `SMB_ORDERS`, `REVENUE_PER_CUSTOMER` and the operand `NEW_CUSTOMERS` take
  their identifiers from `Steep identifiers`. `REVENUE` takes its currency,
  and the ratio its `format` and currency, from `Format per metric`.
- Metric `dimensions` are this module's and those of `CUSTOMERS`, which
  `ORDERS` reaches through the relationship.
- `NET_REVENUE` is custom SQL, because `NET_AMOUNT` is computed. It has no time
  marker, so its time column is the table's only date column.
- `ORDER_NUMBER` is not a dimension, because it is numeric.
- `REVENUE_PER_CUSTOMER` sits here, on its numerator's module.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: orders
  schema: SALES
  table: ORDERS
  description: One row per order.
  dimensions:
    - column: COUNTRY
      label: Country
      type: categorical
      synonyms:
        - market
  metrics:
    - identifier: revenue
      name: Revenue
      synonyms:
        - sales
      agent_instructions: Excludes cancelled orders.
      type: sum
      value: ORDERS.AMOUNT
      currency: USD
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - SALES.CUSTOMERS.*
      filters:
        - column: STATUS
          operator: in
          expression: paid,refunded
      slices:
        - name: Web
          filter:
            column: CHANNEL
            operator: equals
            expression: web
    - identifier: smb-orders
      name: SMB orders
      type: count
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - SALES.CUSTOMERS.*
      filters:
        - table: CUSTOMERS
          column: SEGMENT
          operator: equals
          expression: smb
    - identifier: net_revenue
      name: Net revenue
      type: custom-value
      sql_expression: SUM(ORDERS.AMOUNT - ORDERS.DISCOUNT)
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - SALES.CUSTOMERS.*
    - identifier: revenue-per-customer
      name: Revenue per customer
      type: derived-ratio
      numerator: revenue
      denominator: new-customers
      format: number
      currency: USD
```

Without `net_revenue`, this is the `orders` module the export started from.

`modules/customers.yaml`, the module the export started from without its
`customer` entity:

- `ID` is the primary key. Snowflake has no entities, so the import makes none
  unless the user asks (see [Module ← logical table](#module--logical-table));
  the original entity's name, property names and metrics are gone.

- `CUSTOMER_ID` is not a key of `ORDERS`, so the join is `one-to-many`,
  declared in `customers`, the one side, as the name `CUSTOMERS_TO_ORDERS`
  also says.
- `TOTAL_BALANCE` takes its time column from the time marker, which agrees with
  its non-additive dimension.
- Its label `Customers` comes from `Display names`; the metric names are the
  humanized identifiers.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: customers
  schema: SALES
  table: CUSTOMERS
  label: Customers
  synonyms:
    - clients
  dimensions:
    - column: SEGMENT
      description: Sales segment.
      type: categorical
  metrics:
    - identifier: new-customers
      name: New customers
      type: count
      time: CUSTOMERS.CREATED_AT
      dimensions:
        - this.*
    - identifier: total-balance
      name: Total balance
      type: sum
      value: CUSTOMERS.BALANCE
      time: CUSTOMERS.SNAPSHOT_DATE
      time_aggregation: last-date
      dimensions:
        - this.*
  joinPaths:
    - from:
        column: ID
      to:
        table: ORDERS
        column: CUSTOMER_ID
      type: one-to-many
```

Report items for this example:

- Database `ANALYTICS` dropped; confirm the Steep connection points at it.
- `ORDER_NUMBER` was not made a dimension (numeric).
- `NET_REVENUE` had no time marker; its time column is the only date column.
- `revenue-per-customer` is approximate: its operands use different time
  columns.
- `revenue` keeps a `COUNTRY` group only if it has paid or refunded orders.
- `COUNTRY` and `SEGMENT` are `categorical`; confirm if one holds country
  codes.
- The view `description` was not imported.
- `CUSTOMERS` has primary key `ID`, but no entity was made: offer to add one.
