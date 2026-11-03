# Steep semantic model YAML → Snowflake semantic view mapping

Steep side: the `module:` document of the Steep semantic model YAML
(<https://help.steep.app/setup-and-manage/code-reference>). Snowflake side: the
`CREATE SEMANTIC VIEW` subset in [`semantic-view-syntax.md`](semantic-view-syntax.md).
Snowflake has no vendor-extension slot. Three structured lines in
`AI_SQL_GENERATION` carry what the `snowflake-to-steep` skill needs to restore
each metric's time column, identifier and format, so the round trip is close
but not exact: see [Round trip](#round-trip). Never drop a Steep property
silently: it is either mapped or listed in the report.

## Conventions

- **Sanitize** a name: lowercase it, replace every run of characters outside
  `a-z0-9_` with `_`, trim `_` from both ends, and prefix `_` if it starts with a
  digit. `New customers` → `new_customers`, `avg-order-value` →
  `avg_order_value`.
- **Same name** means equal after sanitizing.
- **Semantic names** (aliases, facts, dimensions, metrics, relationships) are
  sanitized and written unquoted. If one is a Snowflake reserved keyword, append
  `_dim`, `_fact`, `_metric` or `_tbl` according to its kind.
- **Physical names** (database, schema, table, column) must keep their exact
  case. Steep quotes every identifier on Snowflake, so `amount` in a Steep file
  is the column `"amount"`, not `AMOUNT`. Write a physical name unquoted only
  when it matches `^[A-Z_][A-Z0-9_$]*$` and is not a reserved keyword.
  Otherwise double-quote it exactly as written: `AMOUNT` → `AMOUNT`,
  `amount` → `"amount"`, `Order Date` → `"Order Date"`, `ORDER` → `"ORDER"`.
- **Display names** (a module or dimension `label`, a metric `name`) go in the
  `Display names` marker line (see [AI instructions](#ai-instructions)), not in
  `WITH SYNONYMS`, which holds only the Steep `synonyms`. Snowflake has no
  label field, and a marker line keeps them apart from real synonyms. List:
  - every module and dimension `label` that is set;
  - a metric's `name` when it differs from its humanized identifier (`-` and
    `_` become spaces, first letter upper case: `new-customers` →
    `New customers`), because the import derives that name by default.
    `SMB orders` is listed (`smb-orders` humanizes to `Smb orders`),
    `Revenue` is not. Slice names go in `COMMENT` instead.
- **String literals** (`COMMENT`, synonyms, `AI_SQL_GENERATION`, filter values):
  single-quote them, doubling every `\` and then every `'`.
- **Layout**: one item per line, continuation modifiers indented below it, and
  items separated by a trailing comma. Within each clause, order items by
  module order, then by Steep order inside the module.

## Resolving Steep column paths

- Metric `time`, `value`, `numerator`, `denominator` and `distinct_on` are
  `table.column`. The table defaults to the module's own table.
- Dimension paths in `metric.dimensions` and cohort `time_dimension` are
  `schema.table.column`. Schema and table default to the module's.
- Filters, slices and access policies use separate `schema` / `table` / `column`
  keys. A missing table, or `this`, means the module's own table.
- Custom SQL (`sql_expression`, `numerator_sql`, `denominator_sql`) references
  columns as `table.column`, where `table` is the bare table name. A bare column
  means the module's own table.

Resolve every reference to a `(logical table, column)` pair before writing
anything. A reference to a table that is not an exported module cannot be
represented. Report the metric that needs it and leave the metric out.

## How a metric reaches a column

Inside a metric on logical table `T`, write a column of:

- **`T` itself** as the qualified physical column `T.<column>`.
- **Another table `U`** as a semantic name on `U`. Use `U`'s dimension for
  that column if one exists. Otherwise add `PRIVATE U.<sanitized column> AS
  U.<column>` to `FACTS`. `U` must be reachable from `T` by following
  `REFERENCES` (the one side, see [Relationships](#relationships)), or joined
  `one-to-one`. If it isn't, Snowflake needs nested aggregation, which changes the meaning. Leave
  the metric out and report it.

## View

| Snowflake           | From                                                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------------------- |
| statement           | `CREATE OR ALTER SEMANTIC VIEW`                                                                                 |
| name                | `<database>.<schema>.<view name>` from the user                                                                 |
| `COMMENT`           | from the user, or `Exported from Steep on <date>.`; always present, since `CREATE OR ALTER` unsets a missing one |
| `AI_SQL_GENERATION` | see [AI instructions](#ai-instructions); omit only when it would be empty                                      |

## Logical table ← `module`

| Snowflake       | From                                                                                                                                          |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| alias           | module `table`, sanitized. If two exported modules share a table name, use the sanitized module `identifier` for both.                        |
| table           | `database.schema.table`, always all three parts, each quoted per Conventions. The database is the source database. A two-part name resolves against the session's database, which differs per user. |
| `PRIMARY KEY`   | `(<entity.primary_key>)` from the first entity on the module, if any                                                                          |
| `UNIQUE`        | each column a relationship references on this table, and the `from` column of each `one-to-one` join declared on this module, unless it is the primary key; one `UNIQUE (…)` per distinct column |
| `WITH SYNONYMS` | module `synonyms`; omit when empty                                                                                                            |
| `COMMENT`       | module `description`                                                                                                                          |

## Relationships

Snowflake's `<alias>(<col>) REFERENCES <ref_alias>(<ref_col>)` puts the many
side first, and `<ref_col>` must be unique. Which Steep side that is depends on
the join `type`:

- `one-to-many`: `from.column` is unique in the declaring module, so the
  declaring module is the referenced side.
  `<to table>(<to.column>) REFERENCES <declaring module>(<from.column>)`.
- `one-to-one`: both columns are unique.
  `<declaring module>(<from.column>) REFERENCES <to table>(<to.column>)`, and
  `UNIQUE (<from.column>)` on the declaring module. The `UNIQUE` key tells
  Snowflake the relationship is one-to-one, and tells the import to keep the
  `one-to-one` type.

- Name: `<declaring alias>_to_<other alias>`. The import reads the declaring
  module back from it. Append `_<from column>` if that name is not unique.
- The referenced column needs a key on its table: add `UNIQUE (<ref_col>)` there
  unless it is the `PRIMARY KEY`.
- A `one-to-one` whose `from.column` is not the module's entity primary key may
  really be a many-to-one lookup (many orders, one customer). Steep expects
  that as `one-to-many` declared in the other module. The export still writes
  `UNIQUE (<from.column>)`, which is false if values repeat: say in the report
  that it assumes the column is unique.
- Drop and report:
  - a join to a table that is not an exported module;
  - a join from a module to itself;
  - a join that closes a cycle, even through other tables. Keep joins in module
    order and drop the one that closes the loop.
- Two joins between the same two tables are allowed. Snowflake then only lets
  a metric cross between those tables with `USING (<relationship>)`, and Steep
  has nothing to pick one. Keep both and report every metric that crosses
  between them.

## Dimensions

One dimension per distinct column in this list, named after the sanitized
column:

1. Steep `dimensions` (in Steep order).
2. Every metric `time` column and cohort `time_dimension` column.
3. Every entity `properties` column.

| Snowflake       | From                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| name            | `<alias>.<sanitized column>`                                                                                  |
| expression      | `<alias>.<column>`                                                                                            |
| `WITH SYNONYMS` | dimension `synonyms`; omit when empty                                                                         |
| `COMMENT`       | dimension `description`                                                                                       |

A Steep dimension's `type` (`city`, `country`, …) has no slot. Its
`identifier`, when set and not identical text to the Snowflake name, goes in
the `Steep identifiers` line (see [AI instructions](#ai-instructions)).

**Snapshot day dimension.** For each metric with `time_aggregation: last-date`,
also add `<alias>.<sanitized time column>_day AS DATE_TRUNC('DAY',
<alias>.<time column>)`. It must sit on the same table as the time column. See
the `last-date` row under [Expressions](#expressions).

## Facts

Only the `PRIVATE` facts that [How a metric reaches a column](#how-a-metric-reaches-a-column)
requires. Nothing else. Same-table columns are referenced directly.

## Metric ← `metrics[]`

Skip `is_private: true` metrics unless the user asked to include them. A Steep
private metric is visible only to some members, but anyone who can query the
semantic view would see it. List skipped metrics in the report.

| Snowflake       | From                                                                                                                                                 |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| name            | `<alias>.<sanitized identifier>`. Add `_metric` if it clashes with a fact or dimension on the same table, or with any column a metric reads from that table: Snowflake resolves names to semantic expressions first. When the name is not identical text to the Steep identifier, add it to the `Steep identifiers` line. |
| table           | the module the metric is declared in                                                                                                                 |
| expression      | see below                                                                                                                                            |
| `WITH SYNONYMS` | metric `synonyms`; omit when empty                                                                                                                   |
| `COMMENT`       | metric `description`                                                                                                                                 |

### Expressions

`v`, `n`, `d` are the resolved column references. `F` is the metric's filter
condition: all `filters` joined with `AND`, plus the slice filter for slice
metrics. Snowflake has no `FILTER (WHERE …)`, so each aggregate's input is made
null when `F` is false. This matches Steep, which applies the filters in
`WHERE`. With no filter, drop the `IFF`.

| Steep `type`     | Snowflake expression                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------- |
| `sum`            | `SUM(IFF(F, v, NULL))`                                                                       |
| `count`          | `COUNT_IF(F)`; without a filter `COUNT(*)`                                                   |
| `count-distinct` | `COUNT(DISTINCT IFF(F, v, NULL))`                                                            |
| `ratio`          | `SUM(IFF(F, n, NULL)) / NULLIF(SUM(IFF(F, d, NULL)), 0)`                                     |
| `custom-value`   | `sql_expression`, rewritten (below)                                                          |
| `custom-ratio`   | `(numerator_sql) / NULLIF((denominator_sql), 0)`, each rewritten                             |
| `derived-ratio`  | a **derived metric**, see below                                                              |

- `format: percentage` is display only. Do not multiply by 100. The format of
  every ratio goes in the `Format per metric` line instead.
- **`time_aggregation: last-date`** → add
  `NON ADDITIVE BY (<alias>.<time column>_day ASC NULLS FIRST)` before `AS`.
  Steep takes each group's value on its latest day, and Snowflake's
  `NON ADDITIVE BY` keeps the last rows in that sort order. `NULLS FIRST` keeps
  rows without a date from being taken as the latest. Report these metrics for
  a parity check: the docs do not say whether "latest" is per breakdown group,
  as it is in Steep.

**Rewriting custom SQL.**

1. Replace each table qualifier with its alias.
2. Turn references to other tables into semantic names, as in
   [How a metric reaches a column](#how-a-metric-reaches-a-column).
3. Leave column spelling exactly as written. Steep passes custom SQL through
   unchanged, so it already resolves the way Snowflake resolves it.
4. Apply `F` to every aggregate:
   - `AGG(x)` → `AGG(IFF(F, x, NULL))`, for `SUM`, `AVG`, `MIN`, `MAX`,
     `MEDIAN`, `COUNT(x)` and the first argument of other aggregates;
   - `COUNT(*)` → `COUNT_IF(F)`;
   - `COUNT(DISTINCT x)` → `COUNT(DISTINCT IFF(F, x, NULL))`.

   If the SQL has a window function or a nested aggregate, or you cannot tell
   which calls are aggregates, leave the metric out and report it.

If the Steep workspace does not run on Snowflake, its custom SQL is in another
dialect. Translate only what you are sure of, and report every custom metric as
needing review.

### Slices

Each slice becomes a metric on the same table, right after its parent:

| Snowflake | From                                                                      |
| --------- | ------------------------------------------------------------------------- |
| name      | `<alias>.<parent name>__<slice identifier, else sanitized slice name>`    |
| expression | the parent's, with the slice filter added to `F`                         |
| `NON ADDITIVE BY` | the parent's                                                      |
| `WITH SYNONYMS` | none. Slices have no synonyms, and the import reads the name from `COMMENT`. |
| `COMMENT` | `<parent description> Slice: <slice name>.`, else `Slice: <slice name>.`  |

When the slice has an `identifier` that is not identical text to the suffix,
add `<slice metric> → <slice identifier>` to the `Steep identifiers` line.

### Derived ratios

A derived metric with no table prefix:

```sql
<name> AS <numerator metric> / NULLIF(<denominator metric>, 0)
```

- Each operand is the qualified Snowflake name of the referenced metric, or of
  its slice metric when the operand names a `slice`.
- An operand that was skipped (private, or left out) means the derived ratio is
  left out too. Report it.
- Its name must not equal any table-scoped metric name. Add `_ratio` on a clash.
- It sits in `METRICS` with the metrics of the module it is declared in. The
  import puts it back on its numerator's module.
- Steep evaluates each operand on its own `time` column. A Snowflake query
  groups both by the one time dimension it asks for. When the operands' `time`
  columns differ, report the metric as approximate.

### Filters → SQL condition

`<column> <op> <value>`, where `<column>` is resolved as in
[How a metric reaches a column](#how-a-metric-reaches-a-column):

| Steep `operator`                                                           | SQL                    |
| -------------------------------------------------------------------------- | ---------------------- |
| `equals`, `not-equals`                                                     | `=`, `!=`              |
| `less-than`, `less-than-or-equal`, `greater-than`, `greater-than-or-equal` | `<`, `<=`, `>`, `>=`   |
| `in`, `not-in`                                                             | `IN (…)`, `NOT IN (…)` |
| `is`, `is-not`                                                             | `IS`, `IS NOT`         |
| `like`, `not-like`                                                         | `LIKE`, `NOT LIKE`     |

Steep renders `expression` by splitting it on commas. For each part:

- `true`, `false`, `null` (any case) and JSON numbers pass through unchanged;
- anything else becomes a string literal: one pair of surrounding single quotes
  is stripped first, then it is quoted per Conventions.

A YAML `null`, `true`, `false` or number counts as that literal. `in` and
`not-in` lists are wrapped in parentheses. For example:

- `status in paid,refunded` → `orders.STATUS IN ('paid', 'refunded')`
- `deleted_at is null` → `orders.DELETED_AT IS NULL`

## AI instructions

`AI_SQL_GENERATION` is the only place for agent guidance, and it is view-wide.
Build it as plain lines, in this order, leaving out empty parts:

1. `<module alias>: <module agent_instructions>` per module.
2. `<qualified metric name>: <metric agent_instructions>` per metric.
3. `<qualified dimension name>: <dimension agent_instructions>` per dimension.
4. `Time dimension per metric: <metric> → <time dimension>; …` for every
   metric and slice metric that is not derived. Snowflake has no per-metric
   time column. This tells Cortex Analyst which date each Steep metric is
   measured on.
5. `Steep identifiers: <Snowflake name> → <Steep identifier>; …` for every
   module, metric, slice and dimension whose Steep identifier is not identical
   text to its Snowflake name (sanitizing, `_metric`, `_ratio` or a module
   identifier that differs from its table). Write a module as
   `table <alias> → <module identifier>`; everything else by its qualified
   Snowflake name (`orders.smb_orders`, or the bare name of a derived metric).
   Leave the line out when it would be empty.
6. `Format per metric: <metric> → <format>; …` for every `ratio`,
   `custom-ratio` and `derived-ratio`: its Steep `format`, else `percentage`
   (Steep's default). Slices inherit their parent's. Leave the line out when
   there is no ratio.
7. `Display names: <Snowflake name> → <display name>; …` for the display names
   listed in Conventions. Write a module as `table <alias> → <label>`. A display
   name containing `;` or `→` cannot be written here: leave it out and report
   it. Leave the line out when it would be empty.

Lines 4 to 7 are markers for the import: each name is the exact Snowflake name
written in this statement, and each pair is separated by `; `. Write them in
this order, after all text lines.

## Round trip

The `snowflake-to-steep` skill restores an export from its DDL or YAML: modules,
dimensions, metrics with their identifiers, names, time columns, formats,
filters and snapshots, slices, derived ratios, and join paths with their type
and declaring module. What still comes back different:

- **Entities** are lost. The export writes the entity's primary key as
  `PRIMARY KEY` and its property columns as dimensions; its identifier, name,
  property names, icon, metrics and custom links have no Snowflake slot. The
  import makes an ordinary dimension of each text property column, and an
  entity only if the user asks.
- **Lost entirely:** `accessPolicies`, skipped private metrics, `is_unlisted`,
  `cohort`, `cohorts_only`, `time_grains`, `time_resampling`, `category`,
  `owner_emails`, `examples`, entity custom links and entity metrics, and
  `targets:` documents.
- **Dimension `type`** comes back as `categorical`, unless the user confirms
  `country` or `city`. Dimensions on numeric or date columns, such as cohort
  `type: time` dimensions, are not restored.
- **Metric `dimensions`** come back as every reachable dimension (`this.*`
  plus each joined module on the one side).
- **Filters on custom SQL** stay folded into the SQL (`IFF` inside each
  aggregate).
- **Derived ratios** come back on their numerator's module.
- **Labels** identical to Steep's default (a dimension's column, a module's
  identifier) come back omitted.
- Joins dropped on export (non-module, self, cyclic) and metrics left out.

## Not carried over (report these)

- **`accessPolicies`** (row-level security). Report these first. Anyone who can
  query the view sees every row their Snowflake role can read. Steep's
  per-member filtering is gone unless the team adds Snowflake row access
  policies on the base tables.
- **Private metrics** that were skipped.
- **Derived ratios** with operands on different `time` columns (approximate).
- **`last-date` metrics** (verify with the parity check).
- Metrics left out because they need a higher-granularity table, a join that
  was dropped, or custom SQL that could not be filtered.
- Custom SQL from a non-Snowflake workspace.
- Joins dropped as non-module, self-referencing or cyclic, and duplicate joins.
- `one-to-one` joins whose `from` column is assumed unique.
- Metric `dimensions` (allowed breakdowns): Snowflake allows any reachable
  dimension.
- `cohort`, `cohorts_only`, `time_grains`, `time_resampling`, `category`,
  `owner_emails`, `is_unlisted`, `examples`.
- Entity custom links and entity metrics.
- Dimension `type`.
- `targets:` documents.

## Example

The same model is the worked example in the `snowflake-to-steep` mapping, which
restores it. Steep (two files):

```yaml
module:
  identifier: orders
  schema: SALES
  table: ORDERS
  description: One row per order.
  dimensions:
    - column: COUNTRY
      label: Country
      type: categorical
      synonyms: [market]
  metrics:
    - identifier: revenue
      name: Revenue
      synonyms: [sales]
      agent_instructions: Excludes cancelled orders.
      type: sum
      value: ORDERS.AMOUNT
      time: ORDERS.CREATED_AT
      dimensions: [this.*, SALES.CUSTOMERS.*]
      filters:
        - column: STATUS
          operator: in
          expression: paid,refunded
      slices:
        - name: Web
          filter: { column: CHANNEL, operator: equals, expression: web }
    - identifier: smb-orders
      name: SMB orders
      type: count
      time: ORDERS.CREATED_AT
      dimensions: [this.*, SALES.CUSTOMERS.*]
      filters:
        - table: CUSTOMERS
          column: SEGMENT
          operator: equals
          expression: smb
    - identifier: revenue-per-customer
      name: Revenue per customer
      type: derived-ratio
      numerator: revenue
      denominator: new-customers
      format: number
```

```yaml
module:
  identifier: customers
  schema: SALES
  table: CUSTOMERS
  label: Customers
  synonyms: [clients]
  dimensions:
    - column: SEGMENT
      description: Sales segment.
      type: categorical
  metrics:
    - identifier: new-customers
      name: New customers
      type: count
      time: CUSTOMERS.CREATED_AT
      dimensions: [this.*]
    - identifier: total-balance
      name: Total balance
      type: sum
      value: CUSTOMERS.BALANCE
      time: CUSTOMERS.SNAPSHOT_DATE
      time_aggregation: last-date
      dimensions: [this.*]
  joinPaths:
    - from: { column: ID }
      to: { table: ORDERS, column: CUSTOMER_ID }
      type: one-to-many
  entities:
    - identifier: customer
      name: Customer
      primary_key: ID
      properties:
        - { column: SEGMENT, name: Segment, type: string }
      metrics: [new-customers, total-balance, revenue, smb-orders, revenue-per-customer]
```

Snowflake, with the view in `ANALYTICS.SEMANTIC` and the tables in database
`ANALYTICS`:

- The join is declared in `customers` and is `one-to-many`, so `orders` holds
  the reference, and the relationship is named `customers_to_orders` after the
  declaring module. `ID` is the `customer` entity's primary key, so it is the
  table's `PRIMARY KEY`, which also serves as the key the relationship
  references (no `UNIQUE` needed).
- The entity's property `SEGMENT` is already a dimension. Everything else about
  the entity (its identifier, name, property names and metrics) has no
  Snowflake slot: report the entity as not carried over.
- `Display names` lists the `customers` and `country` labels, and
  `SMB orders`, the only metric name that is not its humanized identifier.
  `WITH SYNONYMS` holds only Steep `synonyms`.
- `orders.smb_orders` reaches the `customers.segment` dimension through
  `customers_to_orders`. No `FACTS` clause is needed, because every
  cross-table column already has a dimension.
- `Steep identifiers` lists the metrics whose identifiers have a `-`, and
  `Format per metric` the one ratio.

```sql
CREATE OR ALTER SEMANTIC VIEW ANALYTICS.SEMANTIC.ACME
  TABLES (
    orders AS ANALYTICS.SALES.ORDERS
      COMMENT = 'One row per order.',
    customers AS ANALYTICS.SALES.CUSTOMERS
      PRIMARY KEY (ID)
      WITH SYNONYMS = ('clients')
  )
  RELATIONSHIPS (
    customers_to_orders AS orders (CUSTOMER_ID) REFERENCES customers (ID)
  )
  DIMENSIONS (
    orders.country AS orders.COUNTRY
      WITH SYNONYMS = ('market'),
    orders.created_at AS orders.CREATED_AT,
    customers.segment AS customers.SEGMENT
      COMMENT = 'Sales segment.',
    customers.created_at AS customers.CREATED_AT,
    customers.snapshot_date AS customers.SNAPSHOT_DATE,
    customers.snapshot_date_day AS DATE_TRUNC('DAY', customers.SNAPSHOT_DATE)
  )
  METRICS (
    orders.revenue AS SUM(IFF(orders.STATUS IN ('paid', 'refunded'), orders.AMOUNT, NULL))
      WITH SYNONYMS = ('sales'),
    orders.revenue__web AS SUM(IFF(orders.STATUS IN ('paid', 'refunded') AND orders.CHANNEL = 'web', orders.AMOUNT, NULL))
      COMMENT = 'Slice: Web.',
    orders.smb_orders AS COUNT_IF(customers.segment = 'smb'),
    revenue_per_customer AS orders.revenue / NULLIF(customers.new_customers, 0),
    customers.new_customers AS COUNT(*),
    customers.total_balance NON ADDITIVE BY (customers.snapshot_date_day ASC NULLS FIRST) AS SUM(customers.BALANCE)
  )
  COMMENT = 'Exported from Steep on 2026-10-29.'
  AI_SQL_GENERATION 'orders.revenue: Excludes cancelled orders.
Time dimension per metric: orders.revenue → orders.created_at; orders.revenue__web → orders.created_at; orders.smb_orders → orders.created_at; customers.new_customers → customers.created_at; customers.total_balance → customers.snapshot_date
Steep identifiers: orders.smb_orders → smb-orders; revenue_per_customer → revenue-per-customer; customers.new_customers → new-customers; customers.total_balance → total-balance
Format per metric: revenue_per_customer → number
Display names: table customers → Customers; orders.country → Country; orders.smb_orders → SMB orders';
```

`revenue_per_customer` is approximate: `revenue` is measured on
`orders.created_at`, `new_customers` on `customers.created_at`.
