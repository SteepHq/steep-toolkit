# Snowflake semantic view: the subset this skill emits

Condensed from the Snowflake documentation, fetched on 2026-10-29:

- [CREATE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [How Snowflake validates semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/validation-rules)
- [Using SQL commands to create and manage semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/sql)
- [Reserved and limited keywords](https://docs.snowflake.com/en/sql-reference/reserved-keywords)

This is a summary written for this skill, not a copy of the Snowflake
documentation. On any conflict, the live documentation wins. Only the parts the
export uses are listed here. Range joins, ASOF joins, window function metrics,
verified queries, tags, Cortex Search services and materializations exist but
are not emitted.

## Statement

```sql
CREATE OR ALTER SEMANTIC VIEW <db>.<schema>.<name>
  TABLES ( logicalTable [ , ... ] )
  [ RELATIONSHIPS ( relationshipDef [ , ... ] ) ]
  [ FACTS ( factExpression [ , ... ] ) ]
  [ DIMENSIONS ( dimensionExpression [ , ... ] ) ]
  [ METRICS ( metricExpression [ , ... ] ) ]
  [ COMMENT = '<comment>' ]
  [ AI_SQL_GENERATION '<instructions>' ]
```

- **Clause order is fixed**: TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS,
  COMMENT, AI_SQL_GENERATION. An expression may still refer to an item defined
  in a later clause.
- At least one dimension or metric is required.
- `CREATE OR ALTER` creates the view or changes it to match, keeping grants.
  A property left out of the statement (for example `COMMENT`) is **unset**.
  It needs OWNERSHIP of an existing view. `CREATE OR REPLACE … COPY GRANTS` is
  the alternative.
- The role needs CREATE SEMANTIC VIEW on the schema and SELECT on every table.

## Logical tables

```sql
<alias> AS <db>.<schema>.<table>
  [ PRIMARY KEY ( <col> [ , ... ] ) ]
  [ UNIQUE ( <col> [ , ... ] ) [ ... ] ]
  [ WITH SYNONYMS = ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<comment>' ]
```

- Once an alias is given, every relationship and expression must use it.
- Name the table in full, `<db>.<schema>.<table>`. A one- or two-part name is
  filled in from context (the session's current database and schema), so the
  same statement can point at different tables for different users.
- Do not repeat the primary key columns in a `UNIQUE` clause.
- Key columns must be physical columns, or expressions that directly name one.
- Synonyms are informational only. Nothing can reference a synonym.

## Relationships

```sql
[ <name> AS ] <alias> ( <col> [ , ... ] ) REFERENCES <ref_alias> [ ( <ref_col> [ , ... ] ) ]
```

- Works like a foreign key: `<ref_col>` must be the `PRIMARY KEY` or a `UNIQUE`
  key of `<ref_alias>`. Without the column list, the primary key is used.
- If `<col>` repeats in `<alias>`, the relationship is many-to-one. If it is
  unique, it is one-to-one.
- Relationships are transitive: `line_items → orders → customers` also relates
  `line_items` to `customers`.
- **No cycles**, not even through transitive paths, and **no self-references**.
- Two relationships between the same pair of tables are allowed. However,
  those tables then cannot refer to each other's expressions unless a metric
  picks one with `USING (<relationship>)`.

## Facts, dimensions, metrics

```sql
[ PRIVATE | PUBLIC ] <alias>.<name> AS <sql_expr>
  [ WITH SYNONYMS = ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<comment>' ]

<alias>.<metric>
  [ NON ADDITIVE BY ( <dimension> [ ASC | DESC ] [ NULLS { FIRST | LAST } ] [ , ... ] ) ]
  AS <aggregate_expr>
  [ WITH SYNONYMS = ( ... ) ] [ COMMENT = '...' ]

<derived_metric> AS <scalar expression over metrics>
```

- Facts and dimensions are row-level. Metrics are aggregates.
- `PRIVATE` facts and metrics cannot be queried directly. Dimensions cannot be
  private.
- Every fact, dimension and metric belongs to a table (`alias.name`), except
  derived metrics, which have no table prefix.
- An expression may use **its own table's physical columns** (qualified or
  not) and semantic expressions of its own table. It **cannot** use another
  table's physical columns, only that table's facts, dimensions or metrics, and
  only along a relationship.
- If a semantic expression and a column share a name, a reference resolves to
  the semantic expression. The exception is a self-reference such as
  `t.c_name AS t.c_name`.
- No reference cycles between expressions or between tables.
- Scalar functions are allowed, table functions are not.

### Granularity

`A REFERENCES B` makes `B` lower granularity than `A` (one `B` row per many `A`
rows):

- A row-level expression on `A` may use `B`'s facts and dimensions directly.
  The reverse direction needs an aggregate.
- A metric on `A` uses row-level expressions at its own or lower granularity
  inside **a single aggregate**, for example
  `SUM(IFF(customers.segment = 'smb', orders.AMOUNT, NULL))`. Using a
  higher-granularity table needs nested aggregation.
- A metric may use other metrics at its own or lower granularity without
  aggregating them.
- For one-to-one relationships, both directions count as the same granularity.

### Metrics

- A metric that is not derived must use an aggregate function. `COUNT(*)` is
  valid and counts rows of the metric's table.
- **Derived metrics** (no table prefix) combine metrics from any tables. They
  may use scalar expressions of metrics, other derived metrics, and
  aggregations of facts or dimensions. They may **not** aggregate metrics, use
  window functions, reference physical columns, or reference unaggregated facts
  or dimensions. A derived metric cannot share a name with a regular metric,
  and only derived metrics can reference derived metrics. They cannot take
  `USING`.
- **`NON ADDITIVE BY`** makes a semi-additive metric. At query time the rows are
  sorted by the listed dimensions, and the values from the **last** rows in
  that order are aggregated. With the default `ASC`, a time dimension gives the
  latest snapshot. Snowflake sorts NULLs last under `ASC`, so write
  `NULLS FIRST` to keep null dates from being picked as the latest. Only
  derived metrics can reference a metric that has `NON ADDITIVE BY`.

## Identifiers and literals

- Unquoted identifiers are case-insensitive and stored upper-case.
  Double-quoted identifiers are case-sensitive and exact.
- Reserved keywords cannot be used unquoted: ACCOUNT ALL ALTER AND ANY AS
  BETWEEN BY CASE CAST CHECK COLUMN CONNECT CONNECTION CONSTRAINT CREATE CROSS
  CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER DATABASE
  DELETE DISTINCT DROP ELSE EXISTS FALSE FOLLOWING FOR FROM FULL GRANT GROUP
  GSCLUSTER HAVING ILIKE IN INCREMENT INNER INSERT INTERSECT INTO IS ISSUE JOIN
  LATERAL LEFT LIKE LOCALTIME LOCALTIMESTAMP MINUS NATURAL NOT NULL OF ON OR
  ORDER ORGANIZATION QUALIFY REGEXP REVOKE RIGHT RLIKE ROW ROWS SAMPLE SCHEMA
  SELECT SET SOME START TABLE TABLESAMPLE THEN TO TRIGGER TRUE TRY_CAST UNION
  UNIQUE UPDATE USING VALUES VIEW WHEN WHENEVER WHERE WINDOW WITH
- String literals use single quotes. Snowflake honors backslash escapes inside
  them, so double every `\` and every `'`.

## Querying (for the parity check)

```sql
SELECT * FROM SEMANTIC_VIEW(
  <db>.<schema>.<name>
  DIMENSIONS orders.created_at
  METRICS orders.revenue
  WHERE orders.created_at >= '2026-01-01'
);
```

`DESCRIBE SEMANTIC VIEW <name>` lists what was created.
