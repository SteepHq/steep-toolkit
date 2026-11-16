# Ossie → Steep semantic model YAML mapping

Ossie side: core spec `0.2.0.dev0` (flat document: `version`, `name`,
`datasets`, …). Steep side: the `module:` document of the Steep semantic model YAML
(<https://help.steep.app/setup-and-manage/code-reference>), mirrored in
`steep-module-schema.json`. Every Ossie property is either mapped, ignored on
purpose (listed below), or named in the report. Never drop one silently.

## Contents

- [Conventions](#conventions)
- [Round trip: STEEP extensions](#round-trip-steep-extensions)
- [Model (root)](#model-root)
- [Module ← dataset](#module--dataset)
- [Resolving fields to columns](#resolving-fields-to-columns)
- [Dimension ← field](#dimension--field)
- [Metric ← metric](#metric--metric)
- [Expressions → metric type](#expressions--metric-type)
- [Predicates → filters](#predicates--filters)
- [Custom SQL](#custom-sql)
- [Join path ← relationship](#join-path--relationship)
- [Not representable in Steep (report these)](#not-representable-in-steep-report-these)
- [Example](#example)

## Conventions

- **Expression form.** Read an expression's top-level `sql`. Without it, read the
  `dialects` entry `OSSIE_SQL_2026`, then the entry for the user's warehouse,
  then `ANSI_SQL`. A metric with only other dialects is skipped and reported.
- **Field reference.** In a dataset-scoped metric, a bare name is a field of the
  same dataset. In a model-scoped metric, `dataset.field`. Ossie unquoted names
  are case-insensitive: `Amount` and `amount` are the same field.
- **Identifiers.** Steep identifiers cannot contain whitespace, `/` or `\`, and
  are at most 255 characters. Ossie names already satisfy this; keep them as is.
- **Display names.** Ossie metrics have no label. Unless a STEEP extension gives
  one, the Steep `name` is the metric name humanized: `_` becomes a space and
  the first letter is upper case (`total_revenue` → `Total revenue`).
- **Key order** follows the order of the rows in the tables below, for restored
  objects too ("verbatim" means the content, not the key order). A metric's keys
  go: `identifier`, `name`, `description`, `synonyms`, `agent_instructions`,
  `examples`, `type`, the type's fields (`value`, `distinct_on`, `numerator`,
  `denominator`, `sql_expression`, `numerator_sql`, `denominator_sql`),
  `format`, `currency`, `unit`, `decimals`, `time`, `dimensions`, `filters`,
  `slices`, then any other restored keys.
- **Report** in the chat, not in a file, unless the user asks for one.

## Round trip: STEEP extensions

A document exported by the `steep-to-ossie` skill carries `custom_extensions`
entries with `vendor_name: STEEP`. Their `data` is a JSON string holding the
original Steep objects, with Steep paths unchanged. Restore from them first:

| Extension on | Keys in `data` | Restore as |
| --- | --- | --- |
| root | `targets: {schema, table}` | one `targets:` file (Steep allows only one) |
| root | `source: "api"` | nothing. The export was built from the Steep API, so the extensions are not verbatim YAML: run the drift check on every object, and report that the restore may differ from the original files. |
| dataset | `identifier`, `label` | module `identifier` (default: the dataset name), `label`. Drop a module synonym equal to `label`: the export adds the label to `ai_context.synonyms`. |
| dataset | `schema`, `table` | module `schema` and `table`, verbatim (no case folding). Without them, parse `source`. |
| dataset | `joinPaths` | join paths to tables that are not in the document, verbatim, in this module |
| dataset | `accessPolicies` | `accessPolicies`, verbatim, **only after the user confirms** (see SKILL.md) |
| dataset | `entities` | `entities`, verbatim |
| field | `dimension` | the dimension, verbatim |
| field | `entity_property` | nothing: it is already inside the dataset's `entities` |
| metric | `module`, `metric` | the metric, verbatim, on the module whose identifier is `module` (without `module`, from older exports: on the module chosen under [Metric ← metric](#metric--metric)), plus `description` from Ossie `description`, and `synonyms`, `agent_instructions`, `examples` from Ossie `ai_context` (drop a synonym equal to `name`) |
| metric | `slice_of`, `slice` | append `slice` to the `slices` of the metric whose identifier is `slice_of`, in document order. Do not create a metric. |
| relationship | `module`, `joinPath` | `joinPath`, verbatim, in the module whose identifier is `module` |

**Drift check.** Another tool may have edited the document after the export.
For each restored metric, rebuild the expression the `steep-to-ossie` skill
would write for the restored definition (its mapping's "Expressions" and
"Filters → SQL condition" sections, every type included: custom SQL with its
references rewritten and `FILTER` added, derived ratios with both operands
inlined). Compare it with the Ossie expression after normalizing both: collapse
whitespace, upper-case keywords and function names, compare unquoted names
case-insensitively, and drop redundant outer parentheses. If they disagree, the
Ossie expression wins: map the metric as if it had no extension, and report it
as "changed after export". Apply the same check to dimensions (column), modules
(`source` against the extension's `schema` and `table`, compared
case-insensitively) and join paths (columns and tables).

A slice metric (`slice_of`) passes the drift check when its expression is the
parent's expression with the slice filter added to `F`. When it fails, or its
parent failed and was mapped from scratch, import it as its own metric.

Restored metrics keep the module their extension names, but their order within
a module can differ from the original files: dataset metrics come first, then
model-scoped ones, in document order.

Objects without a STEEP extension in the same document (added by another tool)
follow the rest of this file, with one exception: **in a document that has STEEP
extensions, a field without a `dimension` extension was not a dimension.** The
export writes every column a metric, filter or join needs as a field, so do not
turn those into dimensions. A restored metric keeps the `dimensions` list of its
extension (none when it had none); do not add the module's dimensions to it.

## Model (root)

| Ossie | Steep |
| --- | --- |
| `version` | check it: `0.2.0.dev0` is the target. For `0.1.x`, see SKILL.md step 1. |
| `name` | nothing. Use it for the output folder name only if the user wants one. |
| `description`, `ai_context` | nothing: Steep has no workspace-level description or context. Report them, and offer to copy `ai_context.instructions` into the `agent_instructions` of the modules it applies to. |
| `datasets` | one module each |
| `relationships` | `joinPaths` |
| `metrics` | metrics on the module chosen under [Metric ← metric](#metric--metric) |
| `custom_extensions` | STEEP: see above. Other vendors: ignored, listed in the report by `vendor_name`. |

## Module ← dataset

| Steep | From |
| --- | --- |
| `identifier` | STEEP extension `identifier`, else the dataset `name` |
| `schema`, `table` | STEEP extension `schema`, `table`, verbatim; else parsed from `source`, see below |
| `label` | STEEP extension `label`; omit otherwise |
| `description` | dataset `description` |
| `synonyms` | `ai_context.synonyms`, without one equal to the extension `label` |
| `agent_instructions` | `ai_context.instructions`, or `ai_context` itself when it is a string |
| `dimensions` | see [Dimension ← field](#dimension--field) |
| `metrics` | this dataset's metrics, then model-scoped metrics placed here |
| `joinPaths` | see [Join path ← relationship](#join-path--relationship), then the extension's `joinPaths` |
| `accessPolicies`, `entities` | STEEP extension only |

`ai_context.examples` on a dataset has no Steep slot: report it.

**`source`.** Split on `.` outside double quotes. Three parts are
`database.schema.table`: drop the database (the Steep connection fixes it),
report it, and ask the user to confirm that their Steep connection points at
that database. When datasets name different databases, only one can be
imported as is: ask which. Two parts are `schema.table`. One
part needs the schema from the user. Strip the double quotes of a quoted part
and keep its case. Fold an unquoted part as the warehouse does (see
[Case](#case)).

A `source` that is a query (it contains whitespace, `SELECT` or parentheses)
cannot be a Steep module, because a module is one table or view. Skip the
dataset, everything that references it, and ask the user to create a view in the
warehouse and rerun the import on it.

**One table, one module.** Steep fails the whole sync when two modules use the
same `schema.table`. If two datasets share a source, ask whether to merge them
into one module (default: merge into the first; rename clashing metrics with a
`<dataset>_` prefix) or to create a view for one of them. If the target repo
already has a module on that table, add to that module instead of creating one.

## Resolving fields to columns

Resolve every field to one of two kinds before writing anything:

- **Column field**: the expression is a single identifier, optionally quoted
  (`amount`, `"Amount"`). It maps to the physical column below.
- **Computed field**: anything else (`amount - discount`,
  `first_name || ' ' || last_name`, `CAST(x AS DATE)`). Steep has no computed
  columns. It can be used only inside [custom SQL](#custom-sql). It cannot be a
  dimension, a metric `time`, a `sum` value, a filter column or a join column.
  When the user needs it as one of those, suggest a view that exposes it as a
  column.

### Case

Steep quotes every identifier it renders, so a Steep column must be written in
the case the warehouse stored it in. A quoted Ossie identifier keeps its exact
text. An unquoted one is folded:

| Warehouse | Unquoted `amount` becomes |
| --- | --- |
| Snowflake | `AMOUNT` |
| Postgres, Redshift, Athena | `amount` (lower case) |
| BigQuery, Databricks, MySQL, SQL Server, Synapse | as written in the Ossie document |

Schema and table parts of `source` are folded the same way, unless a STEEP
extension gives `schema` and `table`: those are already exact. When the user can
reach the warehouse, prefer the real column names from its metadata.

## Dimension ← field

Ossie does not mark which fields users may break down by, so choose. A field
becomes a dimension when all of these hold:

- the document has no STEEP extensions (see the round-trip exception);
- it is a column field;
- its `datatype` is `String` or `Boolean`, or it has no `datatype` and is not
  used as the argument of `SUM`, `AVG`, `MIN`, `MAX`, `COUNT(DISTINCT …)` or a
  ratio;
- it is not in `primary_key`, `unique_keys` or any relationship's columns;
- its name does not mark an identifier or personal data: `id`, `*_id`, `*_key`,
  `*uuid*`, `email`, `phone`, `*address*`, `ip`, `first_name`, `last_name`,
  `full_name`;
- its `is_time` does not resolve to `true` (time fields are handled under
  [`time`](#metric-time)).

List every field you left out, and why, in the report, so the user can add the
ones they want.

| Steep | From |
| --- | --- |
| `column` | the physical column |
| `identifier` | the field `name` when it differs from `column`, compared case-sensitively (on Snowflake, column `STATUS` from field `status` gets `identifier: status`); omit otherwise |
| `label` | field `label` |
| `description` | field `description` |
| `type` | `categorical`. Use `country` or `city` only from a STEEP extension or when the user confirms the values are country codes or city names. |
| `synonyms`, `agent_instructions` | field `ai_context`, as for modules |

A field with `is_time: true` stays out of `dimensions` unless the user wants it
as a time dimension (needed for a cohort); then use `type: time`.

## Metric ← metric

**Module.** A metric whose STEEP extension has `module` goes on that module.
Otherwise, a dataset-scoped metric goes on its dataset's module, and a
model-scoped metric goes on its **base** module:

- every aggregate argument in it is on one dataset: that dataset;
- otherwise, the dataset from which every other referenced dataset is reached by
  following relationships from `from` to `to` (the many side). Steep joins the
  other tables in through the join paths, as an Ossie consumer would.
- if no dataset reaches all the others (two fact tables), and the expression is
  `A / B` where `A` and `B` each aggregate one dataset, write a `derived-ratio`
  (see [below](#expressions--metric-type)). Otherwise skip it and report it.

| Steep | From |
| --- | --- |
| `identifier` | metric `name`. If two metrics get the same identifier (same name on two datasets), prefix both with `<dataset>_`. Also avoid identifiers already in the repo. |
| `name` | humanized metric `name` (see [Conventions](#conventions)) |
| `description` | metric `description` |
| `synonyms` | `ai_context.synonyms` |
| `agent_instructions` | `ai_context.instructions`, or `ai_context` when it is a string |
| `examples` | `ai_context.examples` |
| `type` and its fields | see [Expressions → metric type](#expressions--metric-type) |
| `time` | see [below](#metric-time) |
| `dimensions` | the dimension `column`s (not identifiers) of the base module, listed explicitly; omit when it has none. Dimensions of joined modules are allowed as `table.column` but are not added by default. |
| `filters` | see [Predicates → filters](#predicates--filters) |
| `format` | on new `ratio`, `custom-ratio` and `derived-ratio` metrics, always written (a restored metric keeps its extension as is): `percentage` when the expression multiplies by 100 (drop the factor) or the name, description or `ai_context` says rate, share, percent, `%`, conversion or churn, else `number`. Steep defaults to `percentage`, which would show `0.25` as 25 %. |
| `currency` | on any new metric whose name, description or `ai_context` states the currency, such as `revenue_usd` or "in EUR": its ISO 4217 code. A word like revenue alone does not say which currency: leave it out and report the metric. A ratio with a currency needs `format: number`. |
| `unit` | on a new plain-number metric whose name, description or `ai_context` states a short unit, such as a metric `avg_latency_ms` → `ms`: at most three characters. A column name alone does not count. Never with a `currency` or on a `percentage`. |
| `decimals` | 0 to 6, only when the description or `ai_context` states the decimal places |
| `slices` | STEEP extension only |

`datatype` has no Steep slot (Steep returns every metric as a float). Do not
report it.

### Metric `time`

Every Steep metric except `derived-ratio` needs `time: table.column`; Ossie
metrics have none. The candidates are the column fields of the base module whose
`is_time` resolves to `true`: explicitly, or by default because `datatype` is
`Date`, `DateTime` or `DateTimeTz`. This deliberately deviates from the Ossie
default, which also counts `Time`: a time of day cannot be a time axis. A field
with `is_time: true` and a non-temporal `datatype` (an integer year, a quarter
name) is not a candidate either, because Steep truncates `time` to dates; offer
it to the user only if the warehouse column is a date or timestamp.

- One candidate: use it for every metric on that module.
- Several: ask the user which one, once per module, and offer a per-metric
  override. Do not pick one silently: the time column decides what "revenue in
  March" means.
- None: ask for a column. If there is none, skip the module's metrics and report
  them, with their `ai_context`, which is lost with them. Do not move a metric
  to another module's time column: that changes what it counts.

Write it as `<table>.<column>` with the module's `table`.

## Expressions → metric type

Strip outer parentheses and normalize whitespace first. A factor of `100`
(`100 * A / B`, `(100.0 * A) / B`, `A * 100 / B`) is display scaling: remove it,
match what is left, and write `format: percentage`. `a`, `b`, `x` are field
references resolved to columns; `P` is the predicate of a `FILTER (WHERE P)` on
the aggregate; `NULLIF(e, 0)` around a denominator is the same as `e` (Steep
divides null-safely). Take the first row that matches.

| Ossie expression | Steep `type` | Steep fields |
| --- | --- | --- |
| `SUM(x) [FILTER P]`, `x` a column field | `sum` | `value: <table>.<x>`, `filters` from `P` |
| `COUNT(*) [FILTER P]` | `count` | `filters` from `P` |
| `COUNT(x) [FILTER P]`, `x` the primary key | `count` | `filters` from `P` |
| `COUNT(x) [FILTER P]`, other column | `count` | `filters`: `P` plus `x is-not null` |
| `COUNT(DISTINCT x) [FILTER P]`, `x` a column field | `count-distinct` | `distinct_on: <table>.<x>`, `filters` from `P` |
| `SUM(a) [FILTER P] / SUM(b) [FILTER P]`, same `P` on both | `ratio` | `numerator: <table>.<a>`, `denominator: <table>.<b>`, `filters` from `P`, `format` |
| `A / B`, both aggregates, on the base module | `custom-ratio` | `numerator_sql: A`, `denominator_sql: B`, rewritten as [custom SQL](#custom-sql), `format` |
| `A / B`, `A` and `B` each aggregate a different dataset, no base module | `derived-ratio` | `numerator`, `denominator`: the identifier of an existing metric with the same expression as `A` (or `B`), else of a new helper metric `<name>_numerator` (`_denominator`) with `is_unlisted: true` on that dataset's module. No `time`. `format`. |
| any other expression with an aggregate | `custom-value` | `sql_expression`, rewritten as [custom SQL](#custom-sql) |
| no aggregate, or a window function (`OVER`) | none | skip and report: Steep metrics aggregate |

Filters become Steep `filters` only when `P` can be written as Steep filters.
When it cannot, or when only some aggregates of a ratio carry it, use the
custom-SQL row instead and put `P` inside each aggregate (see
[Custom SQL](#custom-sql)).

Steep `filters` are a `WHERE` on the metric query. For a metric with one
aggregate, or the same `P` on every aggregate, every group gets the same value
as with `FILTER (WHERE P)`. The difference: a breakdown value or time bucket
with no matching row is absent instead of showing `0` or `NULL`. This is the
intended mapping; mention it once in the report, not per metric.

`derived-ratio` caveat: Steep computes each operand on its own module and time
column, then divides. An Ossie consumer would join the two datasets instead.
Report every derived ratio you create.

## Predicates → filters

`P` maps to Steep filters when it is an `AND` of conditions of these forms,
where `f` is a column field (of the base module, or of a module joined to it:
then add its `table`, and its `schema` if it differs):

| Ossie | Steep `operator` | Steep `expression` |
| --- | --- | --- |
| `f = v`, `f <> v`, `f != v` | `equals`, `not-equals` | `v` |
| `f < v`, `<=`, `>`, `>=` | `less-than`, `less-than-or-equal`, `greater-than`, `greater-than-or-equal` | `v` |
| `f BETWEEN v1 AND v2` | two filters: `greater-than-or-equal` `v1`, `less-than-or-equal` `v2` | |
| `f IN (v1, v2)`, `f NOT IN (…)` | `in`, `not-in` | `v1,v2` |
| `f IS NULL`, `f IS NOT NULL` | `is`, `is-not` | `null` |
| `f IS TRUE`, `f IS FALSE`, `f = TRUE` | `is` / `equals` | `true`, `false` |
| `f LIKE 'p'`, `f NOT LIKE 'p'` | `like`, `not-like` | `p` |
| `f` alone (Boolean field), `NOT f` | `equals` | `true`, `false` |

Steep renders `expression` by splitting it on commas, then for each part: `TRUE`,
`FALSE`, `NULL` and anything that parses as JSON (numbers, `true`, `false`,
`null`) pass through unchanged; anything else becomes a single-quoted string
literal, after stripping one pair of surrounding single quotes. So write `v` as:

- a number literal: as is, `100`;
- a string literal `'paid'`: without quotes, `paid`; an embedded `''` becomes a
  single `'` (Steep escapes it again);
- a string that would parse as JSON or a keyword (`'123'`, `'true'`, `'null'`),
  or that starts or ends with a space: keep the single quotes, `'123'`.

These cannot be Steep filters: `OR`, `NOT (…)` around a group, `ILIKE`,
functions on the column (`LOWER(f) = …`), two fields compared, a computed field,
date arithmetic (`f >= CURRENT_DATE - INTERVAL '30' DAY`), and string values
containing a comma. Use custom SQL for those.

## Custom SQL

Steep passes `sql_expression`, `numerator_sql` and `denominator_sql` to the
warehouse unchanged, inside a query where each table is aliased by its bare
table name, **quoted** (`"ORDERS"`, `` `orders` ``), and joined tables come in
through join paths. An unquoted reference resolves only when the warehouse folds
it to that exact name: `ORDERS.AMOUNT` and `orders.amount` both work on
Snowflake for table `ORDERS`, but a Postgres table `Orders` needs `"Orders"`.
So:

1. **References.** Replace each field reference with `<table>.<column>`, `table`
   being the module's `table`. Replace a computed field with its expression,
   prefixing each source column with `<table>.`. Quote a name the way the
   warehouse needs (double quotes on Snowflake, Postgres, Redshift; backticks on
   BigQuery, Databricks, MySQL) when it is not a plain identifier or its case
   would fold differently.
2. **`FILTER`.** Snowflake, BigQuery, Redshift and MySQL do not support
   `FILTER (WHERE …)`. Rewrite every one as a `CASE` with no `ELSE`:
   `SUM(x) FILTER (WHERE P)` → `SUM(CASE WHEN P THEN x END)`, `COUNT(*) FILTER
   (WHERE P)` → `COUNT(CASE WHEN P THEN 1 END)`, `COUNT(DISTINCT x) FILTER
   (WHERE P)` → `COUNT(DISTINCT CASE WHEN P THEN x END)`. Never `ELSE 0`.
3. **Dialect.** Rewrite OSSIE_SQL_2026 functions the warehouse lacks (`IFF`,
   `ZEROIFNULL`, `MEDIAN`, `DATEADD`, …) into the warehouse's form. When you are
   not certain of a rewrite, keep the metric out and report it, rather than
   writing SQL that fails at query time.
4. **Joined tables.** A reference to another dataset needs a join path from the
   base module to that table. If two modules share a bare table name (in
   different schemas), custom SQL cannot tell them apart: report it.

Row-level security (access policies) cannot filter custom SQL. Mention this in
the report when a module that has access policies gets a custom-SQL metric.

## Join path ← relationship

Ossie `from` is the many side, `to` the one side. Steep declares a join once, in
one module:

| Case | Declared in | `from.column` | `to` | `type` |
| --- | --- | --- | --- | --- |
| default | the `to` dataset's module | `to_columns[0]` | `table`, `schema` if it differs, `column: from_columns[0]` of the `from` dataset | `one-to-many` |
| `from_columns` is also the `from` dataset's `primary_key` or one of its `unique_keys` | the `from` dataset's module | `from_columns[0]` | the `to` dataset's table, `column: to_columns[0]` | `one-to-one` |

Columns are physical column names. Steep cannot represent:

- **composite keys** (more than one column): drop the relationship, report it,
  and suggest a view with a single key column;
- **a second relationship between the same two tables** (either direction):
  Steep allows one join path per table pair and fails the sync on a duplicate.
  Keep the first, report the others (a role-playing join such as
  `buyer_id`/`seller_id` needs a second view of the table);
- **a relationship to itself**: drop and report;
- **a relationship to a skipped dataset**: drop and report.

Relationship `name` and `ai_context` have no Steep slot: report `ai_context`.

A restored join path stays where its extension put it, even where this table
would place it elsewhere; both are valid. Join paths in a dataset extension's
`joinPaths` point at tables with no dataset; restore them as they are (the
checker warns that no module is on that table, which is expected). Keep a module with no dimensions or
metrics when a join path needs it.

## Not representable in Steep (report these)

- Dataset `source` that is a query; computed fields used as dimensions, time,
  filters or join keys.
- Model `description`, `ai_context`; dataset and relationship
  `ai_context.examples`; relationship `ai_context`.
- Metrics without an aggregate, with window functions, or with only non-matching
  dialects.
- Composite, duplicate and self relationships.
- `datatype` beyond choosing dimensions and time columns, `unique_keys` beyond
  join cardinality, `primary_key` beyond `count`.
- Custom extensions of other vendors.

Things Steep has that Ossie does not carry, and which therefore stay empty unless
a STEEP extension restores them: entities, access policies, slices, cohorts,
time grains, categories, owners, targets.

## Example

Ossie (warehouse: Postgres):

```yaml
version: 0.2.0.dev0
name: ecommerce
datasets:
  - name: orders
    source: shop.public.orders
    primary_key: [order_id]
    description: One row per order.
    fields:
      - name: order_id
        expression: { sql: order_id }
      - name: customer_id
        expression: { sql: customer_id }
      - name: order_date
        expression: { sql: order_date }
        datatype: Date
      - name: status
        expression: { sql: status }
        datatype: String
      - name: amount
        expression: { sql: amount }
      - name: net_amount
        expression: { sql: amount - discount }
    metrics:
      - name: revenue
        expression:
          sql: SUM(amount) FILTER (WHERE status IN ('paid', 'refunded'))
        ai_context:
          synonyms: [sales]
      - name: net_revenue
        expression: { sql: SUM(net_amount) }
  - name: customers
    source: shop.public.customers
    primary_key: [id]
    fields:
      - name: id
        expression: { sql: id }
      - name: segment
        expression: { sql: segment }
        datatype: String
relationships:
  - name: orders_to_customers
    from: orders
    from_columns: [customer_id]
    to: customers
    to_columns: [id]
metrics:
  - name: revenue_per_customer
    expression:
      sql: SUM(orders.amount) / COUNT(DISTINCT customers.id)
```

Steep, `modules/orders.yaml`. `order_id`, `customer_id` and `amount` are not
dimensions (a key, a join column and a `SUM` argument); `net_revenue` is custom
SQL because `net_amount` is computed; `revenue_per_customer` sits on `orders`
because `orders` reaches `customers`.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: orders
  schema: public
  table: orders
  description: One row per order.
  dimensions:
    - column: status
      type: categorical
  metrics:
    - identifier: revenue
      name: Revenue
      synonyms:
        - sales
      type: sum
      value: orders.amount
      time: orders.order_date
      dimensions:
        - status
      filters:
        - column: status
          operator: in
          expression: paid,refunded
    - identifier: net_revenue
      name: Net revenue
      type: custom-value
      sql_expression: SUM(orders.amount - orders.discount)
      time: orders.order_date
      dimensions:
        - status
    - identifier: revenue_per_customer
      name: Revenue per customer
      type: custom-ratio
      numerator_sql: SUM(orders.amount)
      denominator_sql: COUNT(DISTINCT customers.id)
      format: number
      time: orders.order_date
      dimensions:
        - status
```

`modules/customers.yaml`. The join is declared here, on the one side.
`customers` has no time field, so it gets no metrics; had it any, the import
would ask for a time column.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: customers
  schema: public
  table: customers
  dimensions:
    - column: segment
      type: categorical
  joinPaths:
    - from:
        column: id
      to:
        table: orders
        column: customer_id
      type: one-to-many
```

Report items for this example: database `shop` dropped (confirm the Steep
connection points at it); `revenue` keeps a `status` group only if it has paid
or refunded orders; `net_amount` is computed
and only used in custom SQL; `order_id`, `customer_id`, `amount`, `id` not made
dimensions; `revenue_per_customer` counts customers with orders in the period
(Steep joins from `orders`).

### Round trip

For a model-scoped metric declared on `customers` (Postgres table
`shop.Customers`):

```yaml
datasets:
  - name: customers
    source: shop."Customers"
    ai_context:
      synonyms: [Customer accounts, clients]
    # …fields, metrics…
    custom_extensions:
      - vendor_name: STEEP
        data: '{"label":"Customer accounts","schema":"shop","table":"Customers"}'
metrics:
  - name: customer_revenue
    expression:
      sql: SUM(orders.amount) FILTER (WHERE orders.status = 'paid')
    custom_extensions:
      - vendor_name: STEEP
        data: '{"module":"customers","metric":{"identifier":"customer_revenue","name":"Customer revenue","type":"sum","value":"orders.amount","time":"Customers.signed_up_at","filters":[{"table":"orders","column":"status","operator":"equals","expression":"paid"}]}}'
```

restores as:

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: customers
  schema: shop
  table: Customers
  label: Customer accounts
  synonyms:
    - clients
  metrics:
    - identifier: customer_revenue
      name: Customer revenue
      type: sum
      value: orders.amount
      time: Customers.signed_up_at
      filters:
        - table: orders
          column: status
          operator: equals
          expression: paid
```

The metric stays on `customers` although every aggregate reads `orders`; the
table keeps its case; the label is not repeated as a synonym. The drift check
rebuilds `SUM(orders.amount) FILTER (WHERE orders.status = 'paid')` from the
extension and finds it unchanged.
