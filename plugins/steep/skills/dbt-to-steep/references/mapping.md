# dbt Semantic Layer → Steep semantic model YAML mapping

dbt side: semantic models, entities, dimensions and metrics of a dbt project,
in the latest YAML spec
(<https://docs.getdbt.com/docs/build/latest-metrics-spec>) or the legacy spec
(top-level `semantic_models:` with `measures`), read from
`target/semantic_manifest.json` or from the project's YAML files. Steep side:
the `module:` document of Steep as code
(<https://help.steep.app/setup-and-manage/code-reference>), mirrored in
`steep-module-schema.json`. Every dbt property is either mapped, ignored on
purpose (listed below), or named in the report. Never drop one silently.

## Contents

- [Conventions](#conventions)
- [Reading the input](#reading-the-input)
- [Reading the legacy spec](#reading-the-legacy-spec)
- [Project (root)](#project-root)
- [Module ← semantic model](#module--semantic-model)
- [Resolving names to columns](#resolving-names-to-columns)
- [Dimension ← dimension](#dimension--dimension)
- [Join path ← entities](#join-path--entities)
- [Metric ← simple metric](#metric--simple-metric)
- [Aggregations → metric type](#aggregations--metric-type)
- [Filters](#filters)
- [Ratio metrics](#ratio-metrics)
- [Derived metrics](#derived-metrics)
- [Cumulative and conversion metrics](#cumulative-and-conversion-metrics)
- [Not representable in Steep (report these)](#not-representable-in-steep-report-these)
- [Example](#example)

## Conventions

- **Identifiers.** A Steep identifier is the dbt `name` as written
  (`smb_orders`). dbt names are already lower snake_case.
- **Sanitize** a name: lower-case it, turn runs of characters outside
  `a-z0-9_` into `_`, and trim `_`. **Same name** means equal after sanitizing.
- **Display names.** dbt `label` is the display name: a module or dimension
  `label`, a metric `name`. With no `label`, a module and a dimension get none,
  and a metric gets its humanized identifier: `_` and `-` become spaces, first
  letter upper case (`avg_order_value` → `Avg order value`).
- **Physical names** (schema, table, column) must be in the case the warehouse
  stored them in, because Steep quotes every identifier:
  - Prefer the stored names from `target/catalog.json` or `information_schema`.
  - Otherwise fold unquoted names the way the warehouse does: upper case on
    Snowflake (`amount` → `AMOUNT`), lower case on Postgres, Redshift and
    DuckDB, as written elsewhere. A quoted name keeps its exact text.
- **Custom SQL dialect.** dbt `expr` values are already in the warehouse's SQL.
  Keep them when the Steep workspace runs on the same warehouse. If it does
  not, translate only what you are sure of, and skip and report the rest.
- **Key order** in a metric: `identifier`, `name`, `description`, `type`, the
  type's fields (`value`, `distinct_on`, `numerator`, `denominator`,
  `sql_expression`, `numerator_sql`, `denominator_sql`), `format`, `time`,
  `time_aggregation`, `time_grains`, `dimensions`, `filters`, `slices`. Modules
  and dimensions follow the order of the rows in their tables below.
- **Report** in the chat, not in a file, unless the user asks for one.

## Reading the input

Prefer `target/semantic_manifest.json`, written by `dbt parse`. It has
`ref()`, `{{ doc() }}` and Jinja resolved, carries each semantic model's
physical relation, and has the same shape for both YAML specs except for
simple metrics. Its parts:

| `semantic_manifest.json` | Holds |
| --- | --- |
| `semantic_models[]` | `name`, `label`, `description`, `node_relation` (`database`, `schema_name`, `alias`, `relation_name`), `defaults.agg_time_dimension`, `primary_entity`, `entities[]`, `dimensions[]`, `measures[]` (legacy only) |
| `entities[]`, `dimensions[]` | `name`, `type`, `expr` (`null` when the column has the same name), `label`, `description`, `type_params.time_granularity` on time dimensions |
| `metrics[]` | `name`, `label`, `description`, `type`, `filter.where_filters[].where_sql_template`, `type_params` |
| `saved_queries[]`, `project_configuration` | nothing to import (see [Project](#project-root)) |

A simple metric's aggregation is read from one of two places:

- **Latest spec:** `type_params.expr` and
  `type_params.metric_aggregation_params` (`semantic_model`, `agg`,
  `agg_params`, `agg_time_dimension`, `non_additive_dimension`).
- **Legacy spec:** `type_params.measure.name` names a measure in
  `semantic_models[].measures[]`, which holds `agg`, `expr`, `agg_params`,
  `agg_time_dimension` and `non_additive_dimension`. The measure's semantic
  model is the metric's semantic model. `type_params.measure.filter`,
  `join_to_timespine` and `fill_nulls_with` belong to the metric.

From `target/manifest.json`, read `metadata.adapter_type` (the warehouse) and,
per model node, `columns.<name>.data_type` when the YAML declares it.

**YAML files.** Without `target/`, read the YAML files under the project's
model paths. A file is in the latest spec when a model has `semantic_model:`,
and in the legacy spec when it has a top-level `semantic_models:`, or metrics
with `type_params`. Convert legacy YAML with the next section. Then:

- **Table:** resolve the physical table of `ref('<model>')` yourself. Use the
  model's `alias` (default: the model name), and its `schema` config from the
  YAML, the model's `config()` block or `dbt_project.yml`. dbt's default
  `generate_schema_name` writes `<target schema>_<custom schema>`; a project
  macro of that name can change this. When unsure, ask.
- **Jinja:** resolve `{{ doc('…') }}` from the project's `.md` files. Report any
  other Jinja you cannot resolve.

A project in the middle of a migration can mix both specs, and installed
packages under `dbt_packages/` can still use the legacy spec. Read them all.
Two semantic models on the same dbt model are a dbt error: report them and
import the first.

## Reading the legacy spec

Legacy YAML converts to the latest spec with this table, then follows the rest
of this file:

| Legacy | Latest |
| --- | --- |
| `semantic_models[]` with `model: ref('x')` | `models[x].semantic_model`, with its `name` |
| `defaults.agg_time_dimension` | `agg_time_dimension` on the model |
| `entities[]` with `expr: <column>` (default: the entity name) | `columns[<column>].entity` |
| `dimensions[]` with `expr: <column>` (default: the dimension name) | `columns[<column>].dimension`, with `name` when it differs from the column |
| `dimensions[]` with a computed `expr` | a derived dimension (`derived_semantics`) |
| `type_params.time_granularity` | `granularity` on the column |
| `measures[]` (`agg`, `expr` default the measure name, `agg_params`, `agg_time_dimension`, `non_additive_dimension`) | read through the simple metric that wraps it |
| a metric `type: simple` with `type_params.measure` | `type: simple` metric on the measure's model, with the measure's `agg`, `expr`, `agg_time_dimension` and `non_additive_dimension`, and the metric's `filter` and `label` |
| a measure with `create_metric: true` | a simple metric with the measure's name |
| a measure no metric wraps | nothing. Report it. |
| `agg_params.percentile`, `use_discrete_percentile` | `percentile`, `percentile_type: discrete` |
| `non_additive_dimension.window_choice`, `window_groupings` | `window_agg`, `group_by` |
| `type_params.numerator`, `type_params.denominator` | `numerator`, `denominator` |
| `type_params.expr`, `type_params.metrics` | `expr`, `input_metrics` |
| `type_params.measure` with `cumulative_type_params` | `input_metric`, `window`, `grain_to_date`, `period_agg` |
| `type_params.conversion_type_params` | `entity`, `calculation`, `base_metric`, `conversion_metric`, `constant_properties` |

The semantic manifest also keeps legacy names (`window_choice`,
`window_groupings`), whatever the spec. Below, `max` / `min` means
`window_agg` or `window_choice`, and `group_by` means `group_by` or
`window_groupings`.

## Project (root)

| dbt | Steep |
| --- | --- |
| each semantic model | one module |
| entities across semantic models | `joinPaths` (see [Join path ← entities](#join-path--entities)) |
| simple metrics | metrics on their semantic model's module |
| ratio and derived metrics | see [Ratio metrics](#ratio-metrics), [Derived metrics](#derived-metrics) |
| cumulative and conversion metrics | nothing. Report them. |
| `saved_queries`, `exports` | nothing. Report them. |
| time spine models, `project_configuration` | nothing: Steep builds its own date series. Ignore them. |

## Module ← semantic model

| Steep | From |
| --- | --- |
| `identifier` | the identifier of the module already on that table in the repo, else the semantic model `name` |
| `schema`, `table` | `node_relation.schema_name`, `node_relation.alias`, in stored case (Conventions) |
| `label` | semantic model `label` |
| `description` | semantic model `description`, else the dbt model's `description` |
| `dimensions` | see [Dimension ← dimension](#dimension--dimension) |
| `metrics` | this semantic model's simple metrics, then ratio and derived metrics placed here |
| `joinPaths` | see [Join path ← entities](#join-path--entities) |

- **Database.** Steep modules cannot name one; the Steep connection fixes it.
  Drop `node_relation.database`, and ask the user to confirm their Steep
  connection points at it. When models are in different databases, only one
  can be imported as is: ask which. On BigQuery the database is the project
  and the schema is the dataset.
- **One table, one module.** Steep fails the whole sync when two modules use
  the same `schema.table`. If the target repo already has a module on that
  table, add to it instead.
- **Primary entity.** Used to recognize `count` of the primary key and joins.
  Steep has no other slot for it unless the user wants a Steep entity. Then add
  one (`identifier` and `name` from the entity, `primary_key`, and `properties`
  from the module's dimensions with `type: string`), and ask which properties
  to keep.
- Semantic model `config.meta` and the dbt model's `tags`: report once.

## Resolving names to columns

Every dimension and entity is one of:

- **Column item:** `expr` is `null` (the column has the item's name) or a
  single column, optionally quoted. It maps to that physical column.
- **Computed item:** anything else (`amount > 100`, `date_trunc('month',
  created_at)`, a `derived_semantics` entry). Steep has no computed columns, so
  it can only appear inside custom SQL. It cannot be a dimension, a metric
  `time`, a `sum` value, a filter column or a join column. Exception:
  `date_trunc('<part>', col)` and `cast(col as date)` / `col::date` resolve to
  `col` when used as a time column, because Steep truncates time itself.

A metric `expr` resolves the same way: a single column is a column item;
anything else is custom SQL.

## Dimension ← dimension

A dbt categorical dimension becomes a Steep dimension when all of these hold:

- it is a column item;
- its column is text or boolean. Read the type from `target/catalog.json`
  (written by `dbt docs generate`), `data_type` in the YAML, or
  `information_schema`. Otherwise ask, listing every dimension whose type is
  unknown, in one question. Steep dimensions are string or boolean columns.

Time dimensions are time column candidates instead (see
[Metric `time`](#metric-time)). The import makes no `type: time` dimensions:
Steep uses those only for cohorts, which dbt does not have. Numeric and
computed categorical dimensions have no Steep form: list them in the report,
and suggest exposing a computed one as a text column in the dbt model.

| Steep | From |
| --- | --- |
| `column` | the physical column |
| `identifier` | the dimension `name` when it differs from the column compared case-insensitively; else omit it |
| `label` | `label` |
| `description` | `description` |
| `type` | `categorical`. Use `country` or `city` only when the user confirms the values are country codes or city names. |

`is_partition`, `config.meta` and `validity_params` have no Steep slot. Say once
in the report that they were not carried.

## Join path ← entities

dbt joins two semantic models that share an entity name. The side whose entity
is `primary`, `unique` or `natural` holds one row per value. A `foreign` entity
holds many. MetricFlow only joins from many to one (or one to one).

| Entities with the same name | Declared in | `from.column` | `to` | `type` |
| --- | --- | --- | --- | --- |
| `primary` or `unique` in A, `foreign` in B | A, the one side | A's entity column | B's `table`, `schema` if it differs, `column`: B's entity column | `one-to-many` |
| `primary` or `unique` in both A and B | the model whose entity is `primary`; if both are, the first in the manifest | its entity column | the other model and its entity column | `one-to-one` |
| `foreign` in both | nothing: dbt does not join them | | | |

Columns are physical column names. Steep cannot represent:

- **an entity whose `expr` is computed** (`concat(a, b)`) or composite: drop
  the join, report it, and suggest a single key column in the dbt model;
- **a `natural` entity** (slowly changing dimension with `validity_params`):
  its join depends on the time range. Drop and report it;
- **a second join between the same two tables** (another entity, either
  direction): Steep fails the sync on a duplicate. Keep the first and report
  the others;
- **a join of a model to itself**: drop and report.

## Metric ← simple metric

The module is the metric's semantic model.

| Steep | From |
| --- | --- |
| `identifier` | the metric `name`. Avoid identifiers already in the repo, unless it is the same metric (see SKILL.md, "Write into the repo"). |
| `name` | `label`, else the humanized identifier |
| `description` | `description` |
| `type` and its fields | see [Aggregations → metric type](#aggregations--metric-type) |
| `time` | see below |
| `time_aggregation` | `last-date` from `non_additive_dimension` (see the aggregation table) |
| `time_grains` | from the time dimension's `granularity` (see below) |
| `dimensions` | `this.*` when the module has dimensions, then `<schema>.<table>.*` for each module the metric's model reaches by joins from many to one (foreign → primary/unique, transitively, and both ways across a one-to-one), when that module has dimensions. These are the group-bys dbt allows. Omit when empty. |
| `filters` | see [Filters](#filters) |

A metric with `config.enabled: false` is not imported. `config.meta` on a
metric: report once.

### Metric `time`

Every Steep metric except `derived-ratio` needs `time: <TABLE>.<COLUMN>`. It is
the column behind the metric's `agg_time_dimension`, else the semantic model's
default `agg_time_dimension`. dbt requires one of them, so the import never
guesses. When that time dimension is computed and not a `date_trunc` or date
cast of a column, ask the user for a column, or skip the metric and report it.

### Metric `time_grains`

A time dimension's `granularity` is the finest grain it holds. Steep shows all
grains by default; limit them when the data is coarser:

| `granularity` | `time_grains` |
| --- | --- |
| `day` or finer, or none | omit |
| `week` | `[weekly, monthly, quarterly, yearly]` |
| `month` | `[monthly, quarterly, yearly]` |
| `quarter` | `[quarterly, yearly]` |
| `year` | `[yearly]` |

## Aggregations → metric type

`x` is a column item. `P` is a predicate. `AGG(CASE WHEN P THEN x END)` (or
with `ELSE NULL`) is "`AGG(x)` filtered by `P`", and its `P` joins the metric's
`filter` (see [Filters](#filters)). Take the first row that matches:

| dbt `agg`, `expr` | Steep `type` | Steep fields |
| --- | --- | --- |
| `sum`, `x` [filtered by `P`] | `sum` | `value: <TABLE>.<X>` |
| `count`, `1`, `*` or the primary entity's column | `count` | |
| `count`, `CASE WHEN P THEN 1 END` | `count` | `filters` from `P` |
| `count`, another `x` [filtered by `P`] | `count` | `filters`: `P` plus `x is-not null` |
| `count_distinct`, `x` [filtered by `P`] | `count-distinct` | `distinct_on: <TABLE>.<X>` |
| `sum_boolean`, a boolean column `x` | `count` | `filters`: `x equals true` |
| `sum_boolean`, a predicate `P` that maps to filters | `count` | `filters` from `P` |
| `average`, `min`, `max`, `median`, `percentile`, or any other `expr` | `custom-value` | `sql_expression`, see below |

**Custom SQL.** Steep runs `sql_expression`, `numerator_sql` and
`denominator_sql` as written, inside a query where each table is aliased by its
bare physical table name. So qualify every column with that table name
(`amount` → `ORDERS.AMOUNT`), and wrap the aggregation:

| dbt `agg` | `sql_expression` |
| --- | --- |
| `sum`, `count`, `min`, `max` | `SUM(e)`, `COUNT(e)`, `MIN(e)`, `MAX(e)` |
| `count_distinct` | `COUNT(DISTINCT e)` |
| `sum_boolean` | `SUM(CASE WHEN e THEN 1 ELSE 0 END)` |
| `average` | `AVG(e)` |
| `median` | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY e)`, or the warehouse's `MEDIAN(e)` |
| `percentile` `p` | `PERCENTILE_CONT(p) WITHIN GROUP (ORDER BY e)`; `PERCENTILE_DISC` when `percentile_type: discrete`; the warehouse's approximate function (`APPROX_PERCENTILE` on Snowflake) when `use_approximate_percentile` |

`p` is a fraction: write `95` as `0.95`. If the warehouse has no aggregate form
(exact percentiles on BigQuery), skip the metric and report it. A filter `P`
that cannot become Steep filters goes inside the aggregate as
`CASE WHEN P THEN e END`.

**Snapshots.** `non_additive_dimension` with `max`, no `group_by`, on the
metric's own time dimension → `time_aggregation: last-date`. Steep takes each
group's latest day, which is what dbt's `max` keeps. Anything else (`min`,
`group_by`, a dimension other than the metric's time dimension) has no Steep
form: skip the metric and report it, since summing the snapshots would
overcount.

**Time spine options.** `join_to_timespine` and `fill_nulls_with` fill empty
periods. Import the metric without them and report it: in Steep an empty
period has no value.

## Filters

A metric `filter` (a string or a list, which are ANDed) holds Jinja
references. Resolve each:

- `{{ Dimension('<entity>__<dimension>') }}`: the `<entity>` names the semantic
  model whose `primary` or `unique` entity it is (the metric's own model when
  it is its primary entity). `<dimension>` is a dimension of that model. Use
  its column. A longer path (`<entity>__<entity>__<dimension>`) follows the
  joins in order.
- `{{ Entity('<entity>') }}`: that entity's column on the metric's model.
- `{{ TimeDimension('<entity>__<dimension>', '<grain>') }}`: the time column,
  only when the grain is `day` or omitted and the comparison is to a literal
  date.

`{{ Metric(…) }}` filters, and references to a model the metric's model cannot
reach, have no Steep form: skip the metric and report it.

The result maps to Steep filters when it is an `AND` of conditions of these
forms, where `f` is a column on the module or on a joined module. For a joined
module, add its `table`, and its `schema` if it differs.

| dbt (SQL) | Steep `operator` | Steep `expression` |
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
functions on the column (`lower(f) = …`), two columns compared, a computed
item, date arithmetic (`f >= current_date - 30`), and string values containing
a comma. For those, use custom SQL with the predicate inside the aggregate,
rewritten with physical columns, when every column is on the metric's own
table. Otherwise skip the metric and report it.

Steep `filters` are a `WHERE` on the metric query, as dbt's metric filters are.
Mention once in the report that a group with no matching rows is absent rather
than `0`, which matches dbt unless the metric fills nulls.

## Ratio metrics

A dbt ratio divides two metrics, each optionally with its own `filter` and
`alias`. Resolve each input to a Steep metric first. An input's extra filter
is its input `filter` plus the ratio's own `filter`. Take the first row that
matches:

| Case | Steep |
| --- | --- |
| Both inputs are `sum` metrics on the same module, with the same `time` and the same filters, and neither has an extra filter | `ratio`, `numerator: <TABLE>.<A>`, `denominator: <TABLE>.<B>`, those `filters`, and the inputs' `time` |
| Each input has no extra filter, or one that is exactly one Steep filter | `derived-ratio`, `numerator` and `denominator` as references (see below); no `time` |
| Both inputs on the same module, with the same `time`, otherwise | `custom-ratio`, `numerator_sql` and `denominator_sql` from each input's custom SQL, with its filters inside the aggregate |
| Otherwise | nothing: skip and report |

Prefer `derived-ratio` to `custom-ratio`, even on one module: its operands
stay Steep metrics, and an extra filter stays a structured slice rather than
SQL.

A `derived-ratio` operand is the input metric's identifier. When the input has
an extra filter, the operand is `{ metric, slice }`: add a slice to the input
metric with that one filter, unless one with the same filter is already
there.

| Slice | From |
| --- | --- |
| `name` | the input's `alias` humanized, else the filter value humanized (`web` → `Web`) |
| `identifier` | omit it when the name in snake_case is what Steep generates; else the sanitized name |
| `filter` | the one filter |

**`format`**, on every `ratio`, `custom-ratio` and `derived-ratio`: dbt ratios
are fractions, and Steep renders `percentage` as the fraction × 100. Use
`percentage` when the name, label or description says rate, share, percent,
`%`, conversion or churn, else `number`. Steep defaults to `percentage`, so
always write it, and list every ratio under "Needs a decision".

Place a ratio on the numerator's module, after that module's other metrics. A
derived ratio computes each operand on its own module and time column, then
divides. Report every derived ratio whose operands' `time` columns differ.

## Derived metrics

`expr` over `input_metrics` (each with an optional `alias`, `filter`,
`offset_window` and `offset_to_grain`). Resolve aliases to their inputs.

| dbt | Steep |
| --- | --- |
| any input with `offset_window` or `offset_to_grain` | nothing: skip and report. Steep compares periods itself in reports. |
| `a / b`, `a / nullif(b, 0)`, optionally `* 100` | as a [ratio](#ratio-metrics) of `a` and `b`. A factor of 100 means `format: percentage`; drop it. |
| any other `expr` whose inputs are all on one module, with the same `time` | inline each input's custom SQL into one `custom-value` on that module |
| anything else (`a + b` across modules, nested derived metrics that do not reduce) | skip and report |

## Cumulative and conversion metrics

Steep has no running-total or funnel metric type. Skip every `cumulative` and
`conversion` metric and report it with its input metrics, which are imported
on their own when they are simple metrics.

## Not representable in Steep (report these)

- Cumulative and conversion metrics; derived metrics with offsets or across
  modules (other than ratios).
- Simple metrics with `non_additive_dimension` other than `max` on their own
  time dimension, or with `group_by`; percentiles the warehouse cannot
  aggregate; metrics filtered by `{{ Metric(…) }}`.
- `join_to_timespine` and `fill_nulls_with` (imported without them).
- Numeric, computed and `derived_semantics` dimensions; `natural` entities;
  computed or composite entity keys; duplicate and self joins.
- Measures no metric wraps (legacy).
- `saved_queries` and `exports`, `config.meta`, tags, `is_partition`,
  `validity_params`.
- Cross-project (dbt Mesh) references the import cannot resolve.

Steep features dbt does not carry, which stay empty: access policies, cohorts,
time resampling, categories, owners, synonyms, agent instructions, examples,
`is_private`, `is_unlisted`, entities (unless asked), entity links, targets.

## Example

A Snowflake project with two models in schema `sales`, in the latest spec:

```yaml
models:
  - name: orders
    description: One row per order.
    semantic_model:
      enabled: true
    agg_time_dimension: ordered_at
    columns:
      - name: order_id
        entity: { type: primary, name: order }
      - name: customer_id
        entity: { type: foreign, name: customer }
      - name: ordered_at
        granularity: day
        dimension: { type: time }
      - name: status
        dimension: { type: categorical }
      - name: channel
        dimension: { type: categorical, label: Sales channel }
    metrics:
      - name: revenue
        label: Revenue
        type: simple
        agg: sum
        expr: amount
        filter: "{{ Dimension('order__status') }} in ('paid', 'refunded')"
      - name: smb_orders
        label: SMB orders
        type: simple
        agg: count
        expr: 1
        filter: "{{ Dimension('customer__segment') }} = 'smb'"
  - name: customers
    semantic_model:
      enabled: true
    agg_time_dimension: created_at
    columns:
      - name: customer_id
        entity: { type: primary, name: customer }
      - name: segment
        dimension: { type: categorical }
      - name: created_at
        granularity: day
        dimension: { type: time }
      - name: snapshot_date
        granularity: day
        dimension: { type: time }
    metrics:
      - name: new_customers
        label: New customers
        type: simple
        agg: count
        expr: customer_id
      - name: total_balance
        label: Total balance
        type: simple
        agg: sum
        expr: balance
        agg_time_dimension: snapshot_date
        non_additive_dimension: { name: snapshot_date, window_agg: max }

metrics:
  - name: revenue_per_customer
    label: Revenue per customer
    type: ratio
    numerator: revenue
    denominator: new_customers
  - name: web_revenue_share
    label: Web revenue share
    type: ratio
    numerator:
      name: revenue
      filter: "{{ Dimension('order__channel') }} = 'web'"
    denominator: revenue
  - name: revenue_wow
    label: Revenue WoW
    type: derived
    expr: revenue - revenue_last_week
    input_metrics:
      - { name: revenue }
      - { name: revenue, offset_window: 7 days, alias: revenue_last_week }
  - name: revenue_mtd
    label: Revenue MTD
    type: cumulative
    input_metric: revenue
    grain_to_date: month
```

The same project in the legacy spec reads to the same result:

```yaml
semantic_models:
  - name: orders
    description: One row per order.
    model: ref('orders')
    defaults:
      agg_time_dimension: ordered_at
    entities:
      - { name: order, type: primary, expr: order_id }
      - { name: customer, type: foreign, expr: customer_id }
    dimensions:
      - name: ordered_at
        type: time
        type_params: { time_granularity: day }
      - { name: status, type: categorical }
      - { name: channel, type: categorical, label: Sales channel }
    measures:
      - { name: revenue, agg: sum, expr: amount }
      - { name: order_count, agg: count, expr: 1 }
  - name: customers
    model: ref('customers')
    defaults:
      agg_time_dimension: created_at
    entities:
      - { name: customer, type: primary, expr: customer_id }
    dimensions:
      - { name: segment, type: categorical }
      - name: created_at
        type: time
        type_params: { time_granularity: day }
      - name: snapshot_date
        type: time
        type_params: { time_granularity: day }
    measures:
      - { name: new_customers, agg: count, expr: customer_id }
      - name: total_balance
        agg: sum
        expr: balance
        agg_time_dimension: snapshot_date
        non_additive_dimension: { name: snapshot_date, window_choice: max }

metrics:
  - name: revenue
    label: Revenue
    type: simple
    type_params: { measure: revenue }
    filter: "{{ Dimension('order__status') }} in ('paid', 'refunded')"
  - name: smb_orders
    label: SMB orders
    type: simple
    type_params: { measure: order_count }
    filter: "{{ Dimension('customer__segment') }} = 'smb'"
  - name: new_customers
    label: New customers
    type: simple
    type_params: { measure: new_customers }
  - name: total_balance
    label: Total balance
    type: simple
    type_params: { measure: total_balance }
  - name: revenue_per_customer
    label: Revenue per customer
    type: ratio
    type_params: { numerator: revenue, denominator: new_customers }
  - name: web_revenue_share
    label: Web revenue share
    type: ratio
    type_params:
      numerator:
        name: revenue
        filter: "{{ Dimension('order__channel') }} = 'web'"
      denominator: revenue
  - name: revenue_wow
    label: Revenue WoW
    type: derived
    type_params:
      expr: revenue - revenue_last_week
      metrics:
        - { name: revenue }
        - { name: revenue, offset_window: 7 days, alias: revenue_last_week }
  - name: revenue_mtd
    label: Revenue MTD
    type: cumulative
    type_params:
      measure: revenue
      cumulative_type_params: { grain_to_date: month }
```

`catalog.json` says `status`, `channel` and `segment` are text. The warehouse
is Snowflake, so physical names are upper case.

Steep, `modules/orders.yaml`:

- `revenue`'s filter is on its own model (`order` is its primary entity).
  `smb_orders`' filter reaches `customers` through the `customer` entity, so it
  names the table.
- Metric `dimensions` are this module's and those of `customers`, which
  `orders` reaches through its foreign entity.
- `revenue_per_customer` divides metrics on two modules: a `derived-ratio`.
  Its label has no rate word, so `format: number`.
- `web_revenue_share` has a filter on its numerator that is one Steep filter:
  a `derived-ratio` on a `Web` slice of `revenue`, not a `custom-ratio`. Its
  label says share, so `format: percentage`.
- `revenue_wow` (offset) and `revenue_mtd` (cumulative) are skipped.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: orders
  schema: SALES
  table: ORDERS
  description: One row per order.
  dimensions:
    - column: STATUS
      type: categorical
    - column: CHANNEL
      label: Sales channel
      type: categorical
  metrics:
    - identifier: revenue
      name: Revenue
      type: sum
      value: ORDERS.AMOUNT
      time: ORDERS.ORDERED_AT
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
    - identifier: smb_orders
      name: SMB orders
      type: count
      time: ORDERS.ORDERED_AT
      dimensions:
        - this.*
        - SALES.CUSTOMERS.*
      filters:
        - table: CUSTOMERS
          column: SEGMENT
          operator: equals
          expression: smb
    - identifier: revenue_per_customer
      name: Revenue per customer
      type: derived-ratio
      numerator: revenue
      denominator: new_customers
      format: number
    - identifier: web_revenue_share
      name: Web revenue share
      type: derived-ratio
      numerator:
        metric: revenue
        slice: web
      denominator: revenue
      format: percentage
```

`modules/customers.yaml`:

- `new_customers` counts the primary entity's column: a plain `count`.
- `total_balance` keeps the latest snapshot per period: `last-date` on
  `SNAPSHOT_DATE`, its `agg_time_dimension`.
- The `customer` entity is primary here and foreign in `orders`, so the
  `one-to-many` join is declared here, on the one side.
- `customers` reaches no other model, so its metrics have only `this.*`.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: customers
  schema: SALES
  table: CUSTOMERS
  dimensions:
    - column: SEGMENT
      type: categorical
  metrics:
    - identifier: new_customers
      name: New customers
      type: count
      time: CUSTOMERS.CREATED_AT
      dimensions:
        - this.*
    - identifier: total_balance
      name: Total balance
      type: sum
      value: CUSTOMERS.BALANCE
      time: CUSTOMERS.SNAPSHOT_DATE
      time_aggregation: last-date
      dimensions:
        - this.*
  joinPaths:
    - from:
        column: CUSTOMER_ID
      to:
        table: ORDERS
        column: CUSTOMER_ID
      type: one-to-many
```

Report items for this example:

- Database dropped; confirm the Steep connection points at it.
- Not imported: `revenue_wow` (offset window), `revenue_mtd` (cumulative).
- `revenue_per_customer` is approximate: its operands use different time
  columns.
- Formats guessed: `revenue_per_customer` → `number`, `web_revenue_share` →
  `percentage`.
- `revenue` keeps a `CHANNEL` group only if it has paid or refunded orders.
- `STATUS`, `CHANNEL` and `SEGMENT` are `categorical`; confirm if one holds
  country codes.
- `customers` has primary entity `customer`, but no Steep entity was made:
  offer to add one.
