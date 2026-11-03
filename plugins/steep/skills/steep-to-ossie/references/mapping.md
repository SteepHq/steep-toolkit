# Steep semantic model YAML → Ossie mapping

Steep side: the `module:` document of the Steep semantic model YAML
(<https://help.steep.app/setup-and-manage/code-reference>). Ossie side: core
spec `0.2.0.dev0`. Every Steep object that Ossie cannot represent goes into
a `custom_extensions` entry with `vendor_name: STEEP` and `data` set to a compact
JSON string (YAML single-quoted). Never drop a Steep property silently: it is
either mapped, carried in the extension, or listed in the report. Extension
values are copied verbatim from the Steep YAML (paths are not rewritten), so an
importer can restore them. An object gets at most one STEEP extension; put all
its keys in that one JSON object. When the export was built from the Steep API
instead of YAML files, the extension values are not verbatim: mark the document
with `"source": "api"` in the root extension (see SKILL.md step 1).

## Conventions

- **Sanitize** a name by lowercasing it, replacing every run of characters
  outside `a-z0-9_` with `_`, trimming `_` from both ends, and prefixing `_` if it
  starts with a digit. `New customers` → `new_customers`, `avg-order-value` →
  `avg_order_value`.
- **Same name** means equal after sanitizing: `Revenue` / `revenue` and
  `New customers` / `new-customers` are the same name; `Orders` / `order-count`
  are not.
- **Key order** inside every object follows the order of the rows in the tables
  below. Within a dataset, list dimension fields first (in Steep order), then the
  other fields in order of first reference.
- **Case.** The warehouse folds unquoted identifiers: Snowflake (and ANSI SQL)
  to upper case, Postgres and Redshift to lower case; BigQuery, Databricks,
  MySQL and SQL Server match them case-insensitively. **Quote** an identifier
  (double quotes) when it does not match `[A-Za-z_][A-Za-z0-9_]*`, is an ANSI SQL
  reserved word (`order`, `group`, `user`, `date`, `time`, `select`, `from`,
  `where`, `end`, …), or has a letter whose case differs from the warehouse's
  folding: any lower-case letter on Snowflake, any upper-case letter on Postgres
  or Redshift, never on the case-insensitive warehouses. Steep names are
  case-sensitive, so this keeps them pointing at the same column. When the
  warehouse is unknown, fold to lower case and say so in the report.
  Non-reserved keywords such as `name` stay unquoted.
- **YAML**: write block style, and single-quote any string that contains `:`,
  `#`, `?`, `{`, `[`, `,` or starts with a quote — or build the document as data
  and dump it with a YAML library.

## Resolving Steep column paths

- Metric `time`, `value`, `numerator`, `denominator`, `distinct_on` are
  `table.column`; the table defaults to the module's own table.
- Dimension paths in `metric.dimensions` and cohort `time_dimension` are
  `schema.table.column`; schema and table default to the module's.
- Filters, slices and access policies use separate `schema` / `table` / `column`
  keys; missing or `this` means the module's own table.
- Custom SQL (`sql_expression`, `numerator_sql`, `denominator_sql`) references
  columns as `table.column` where `table` is the bare table name (Steep aliases
  each table by its name). A bare column means the module's own table.

Resolve every reference to a `(dataset, field)` pair before writing anything.

## Model (root)

| Ossie               | From                                                                     |
| ------------------- | ------------------------------------------------------------------------ |
| `version`           | always `0.2.0.dev0`                                                      |
| `name`              | user-provided model name                                                 |
| `description`       | from the user; omit if none                                              |
| `ai_context`        | from the user; omit if none (Steep has no workspace-level context)       |
| `custom_extensions` | `STEEP`: `{"source": "api"}` when built from the Steep API (omit otherwise), and `"targets": {schema, table}` from the `targets:` file (Steep allows one); omit the extension when both are absent |

## Dataset ← `module`

| Ossie               | From                                                                                                                                                                                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`              | module `table`, sanitized. If two modules share a table name (different schemas), use the sanitized module `identifier` for both and rewrite custom SQL references accordingly. Keeping the table name means custom SQL `orders.amount` maps straight to `orders.amount`. |
| `source`            | `[database.]schema.table`, each part quoted under the **Case** convention                                                                                                                                                                                                 |
| `description`       | module `description`                                                                                                                                                                                                                                                      |
| `ai_context`        | `{instructions: agent_instructions, synonyms: [label if not the same name as the table, …synonyms]}`; omit empty keys, and omit `ai_context` when nothing is left                                                                                                         |
| `primary_key`       | `[<field of entity.primary_key>]` from the first entity on the module, if any                                                                                                                                                                                             |
| `unique_keys`       | each `to_columns` of a relationship pointing at this dataset, unless it equals the `primary_key`                                                                                                                                                                          |
| `fields`            | see below                                                                                                                                                                                                                                                                 |
| `metrics`           | dataset-scoped metrics, see below                                                                                                                                                                                                                                         |
| `custom_extensions` | `STEEP`: `{"identifier", "label", "schema", "table", "accessPolicies", "entities", "joinPaths"}`. `schema` and `table` are always written, exactly as in Steep. Leave out `identifier` when it equals the dataset name exactly (case included), and leave out absent keys. `joinPaths` holds only the join paths that have no relationship (see below).       |

## Field ← column

One field per distinct column the dataset needs (see SKILL.md step 2.2).

| Ossie               | From                                                                                                                                                                                                                                                                                                                                |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`              | the column name, sanitized                                                                                                                                                                                                                                                                                                          |
| `label`             | dimension `label`, else entity property `name`                                                                                                                                                                                                                                                                                      |
| `description`       | dimension `description`                                                                                                                                                                                                                                                                                                             |
| `datatype`          | see table below; omit when unknown                                                                                                                                                                                                                                                                                                  |
| `expression.sql`    | the column as written in Steep, quoted under the **Case** convention (on Postgres, `Amount` → `"Amount"`, `amount` → `amount`; on Snowflake, `AMOUNT` → `AMOUNT`, `amount` → `"amount"`).                                                                                                                                       |
| `dimension.is_time` | `true` for `type: time` dimensions and every metric `time` / cohort `time_dimension` column                                                                                                                                                                                                                                         |
| `ai_context`        | dimension `{instructions: agent_instructions, synonyms}`                                                                                                                                                                                                                                                                            |
| `custom_extensions` | `STEEP`: `{"dimension": <original>, "entity_property": <original>}` with the keys that apply                                                                                                                                                                                                                                        |

When a column is both a dimension and an entity property, the dimension wins for
`label`, the entity property for `datatype`.

| Steep type                                        | Ossie `datatype` |
| ------------------------------------------------- | ---------------- |
| entity `string`, `uuid`                           | `String`         |
| entity `number`                                   | `Decimal`        |
| entity `boolean`                                  | `Boolean`        |
| entity `date`                                     | `Date`           |
| entity `time`                                     | `DateTime`       |
| entity `geography`                                | `Opaque`         |
| dimension `city`, `country`, `h3-cell-index`      | `String`         |
| dimension `categorical`, `time`; any other column | omit             |

Do not add `dimension: {is_time: false}`; it is the default for non-temporal types.

## Metric ← `metrics[]`

**Scope.** Dataset-scoped (under `datasets[].metrics`, unqualified field names)
when every column it touches — value, filters, slice filter, custom SQL — is on
the module's own table. Otherwise model-scoped (root `metrics`): qualify
**every** field reference as `dataset.field`, filter columns included. Derived
ratios are always model-scoped.

| Ossie               | From                                                                                                                                |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `name`              | metric `identifier`, sanitized; suffix `_metric` if it collides with a field of the same dataset                                    |
| `expression`        | see below                                                                                                                           |
| `description`       | metric `description`                                                                                                                |
| `datatype`          | `Integer` for `count` and `count-distinct`, `Float` for everything else (Steep casts results to float)                              |
| `ai_context`        | `{instructions: agent_instructions, synonyms: [name if not the same name as the identifier, …synonyms], examples}`; omit empty keys |
| `custom_extensions` | `STEEP`: `{"module": <declaring module identifier>, "metric": <original metric object without description, synonyms, agent_instructions, examples, slices>}` |

### Expressions

`v`, `n`, `d` are the resolved field references (qualified in model scope).
`F` is the metric's filter condition (all `filters` joined with `AND`, plus the
slice filter for slice metrics). Drop `FILTER (WHERE F)` when there is no filter.

| Steep `type`     | `expression.sql`                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sum`            | `SUM(v) FILTER (WHERE F)`                                                                                                                                 |
| `count`          | dataset scope: `COUNT(*) FILTER (WHERE F)`; model scope: see below                                                                                        |
| `count-distinct` | `COUNT(DISTINCT v) FILTER (WHERE F)`                                                                                                                      |
| `ratio`          | `SUM(n) FILTER (WHERE F) / NULLIF(SUM(d) FILTER (WHERE F), 0)`                                                                                            |
| `custom-value`   | `sql_expression` with references rewritten; add `FILTER (WHERE F)` to each aggregate call                                                                 |
| `custom-ratio`   | `(numerator_sql) / NULLIF((denominator_sql), 0)`, rewritten and filtered like `custom-value`                                                              |
| `derived-ratio`  | `(<numerator expression>) / NULLIF((<denominator expression>), 0)`, each operand inlined from the referenced metric (or slice metric) in model-scope form, with the derived ratio's own filters added to each operand's `F` |

**`count` in model scope** (a model-scoped count, or a count inlined into a
derived ratio): `COUNT(*)` would count rows of the joined result, not rows of
the module. Write `COUNT(DISTINCT <dataset>.<primary key>) FILTER (WHERE F)`.
If the module has no primary key, keep `COUNT(*)` and report the metric as
approximate.

Notes:

- Steep divides with a null-safe division, hence `NULLIF(…, 0)`. A ratio's
  `format: percentage` is display-only; do not multiply by 100. Keep `format` in
  the extension.
- If custom SQL has an aggregate you cannot safely attach `FILTER` to (window
  functions, nested aggregates), or uses warehouse-specific functions you cannot
  rewrite with certainty, keep the original SQL in `dialects` and omit `sql`:

  ```yaml
  expression:
    dialects:
      - dialect: SNOWFLAKE
        expression: "SUM(orders.amount) / NULLIF(DATEDIFF(day, MIN(orders.created_at), MAX(orders.created_at)), 0)"
  ```

- A derived ratio whose operands sit on different datasets or use different
  `time` columns is only approximate in Ossie (Steep evaluates each operand on
  its own time axis, then divides). Write the inlined expression anyway and
  report it.
- A derived ratio's `filters`: this export assumes they apply to both
  operands, so add them to the `F` of the numerator and of the denominator,
  with a filter without `table` resolving against each operand's own module
  table. Steep's documentation does not state this, so treat it as unverified:
  the filters stay in the `metric` extension, and every derived ratio with
  filters goes in the report for a parity check against Steep.

### Filters → SQL condition

`<field> <op> <value>` with:

| Steep `operator`                                                           | SQL                    |
| -------------------------------------------------------------------------- | ---------------------- |
| `equals`, `not-equals`                                                     | `=`, `!=`              |
| `less-than`, `less-than-or-equal`, `greater-than`, `greater-than-or-equal` | `<`, `<=`, `>`, `>=`   |
| `in`, `not-in`                                                             | `IN (…)`, `NOT IN (…)` |
| `is`, `is-not`                                                             | `IS`, `IS NOT`         |
| `like`, `not-like`                                                         | `LIKE`, `NOT LIKE`     |

Steep renders `expression` by splitting it on commas and, for each part:
`true` / `false` / `null` and JSON numbers pass through unchanged; anything else
becomes a single-quoted string literal (one pair of surrounding single quotes is
stripped first, embedded quotes are doubled). A YAML `null`, `true`, `false` or
number in the Steep file counts as that literal. `in` / `not-in` lists are
wrapped in parentheses. Reproduce exactly that, e.g. `status in paid,refunded`
→ `status IN ('paid', 'refunded')`, `deleted_at is null` → `deleted_at IS NULL`.

### Slices

Each slice becomes its own metric next to its parent:

| Ossie               | From                                                                      |
| ------------------- | ------------------------------------------------------------------------- |
| `name`              | `<parent name>__<slice identifier, else sanitized slice name>`            |
| `expression`        | the parent's, with the slice filter added to `F`                          |
| `description`       | `<parent description> Slice: <slice name>.`; omit if the parent has none  |
| `datatype`          | the parent's                                                              |
| `ai_context`        | omit                                                                      |
| `custom_extensions` | `STEEP`: `{"slice_of": "<parent identifier>", "slice": <original slice>}` |

## Relationship ← `joinPaths[]`

Ossie wants `from` on the **many** side and `to` on the **one** side. Which
Steep side that is depends on the join `type`:

- `one-to-many`: one row of the declaring module matches many rows of `to`, so
  `from.column` is unique in the declaring module. Ossie `from` = the `to`
  table, Ossie `to` = the declaring module.
- `one-to-one`: each row of the declaring module matches at most one row of
  `to`, so `to.column` is unique in the `to` table. Ossie `from` = the declaring
  module, Ossie `to` = the `to` table.

| Ossie          | `one-to-many`                                                  | `one-to-one`                 |
| -------------- | -------------------------------------------------------------- | ---------------------------- |
| `from`         | dataset of `to.schema.table` (schema defaults to the module's) | declaring module's dataset   |
| `from_columns` | `[<field of to.column>]`                                       | `[<field of from.column>]`   |
| `to`           | declaring module's dataset                                     | dataset of `to.schema.table` |
| `to_columns`   | `[<field of from.column>]`                                     | `[<field of to.column>]`     |

- `name`: `<from dataset>_to_<to dataset>`; append `_<from column>` if not unique.
- The `to_columns` field is a key of the `to` dataset: add it to that dataset's
  `unique_keys` unless it is already its `primary_key`.
- `custom_extensions`: `STEEP`: `{"module": <declaring module identifier>,
"joinPath": <original>}`, so an importer can restore which module declared it.

If `to` is not the table of any exported module, Ossie has no dataset to point
at. Write no relationship; put the original join path, verbatim, in the
`joinPaths` array of the declaring dataset's extension, and report it. Its
`from` column still becomes a field.

## Carried only in extensions (report these)

- `accessPolicies` — row-level security. Ossie consumers will not apply it. The
  policy column still becomes a field so a consumer can enforce it by hand.
- `entities` (properties, custom links, entity metrics) — keep in the dataset
  extension; their columns still become fields.
- Metric `dimensions` (allowed breakdowns), `category`, `owner_emails`,
  `is_private`, `is_unlisted`, `time`, `time_grains`, `time_resampling`,
  `time_aggregation: last-date`, `cohort`, `cohorts_only`, `format`.
- Module `label`, `identifier`, `schema` and `table`, dimension `identifier` and
  `type`.
- Join paths to tables that are not a module.
- `targets` (root extension).

## Example

Steep:

```yaml
module:
  identifier: orders
  schema: analytics
  table: orders
  description: One row per order.
  dimensions:
    - column: country
      type: country
      label: Country
  metrics:
    - identifier: revenue
      name: Revenue
      type: sum
      value: orders.amount
      time: orders.created_at
      filters:
        - column: status
          operator: in
          expression: paid,refunded
      slices:
        - name: Web
          filter: { column: channel, operator: equals, expression: web }
  joinPaths:
    - from: { column: customer_id }
      to: { table: customers, column: id }
      type: one-to-one
```

Ossie (Postgres, assuming a `customers` module on `analytics.customers`).
`revenue` has no `ai_context` because `Revenue` is the same name as `revenue`;
the `orders` extension has no `identifier` because it equals the dataset name.

```yaml
version: 0.2.0.dev0
name: acme
datasets:
  - name: orders
    source: analytics.orders
    description: One row per order.
    fields:
      - name: country
        label: Country
        datatype: String
        expression:
          sql: country
        custom_extensions:
          - vendor_name: STEEP
            data: '{"dimension":{"column":"country","type":"country","label":"Country"}}'
      - name: amount
        expression:
          sql: amount
      - name: created_at
        expression:
          sql: created_at
        dimension:
          is_time: true
      - name: status
        expression:
          sql: status
      - name: channel
        expression:
          sql: channel
      - name: customer_id
        expression:
          sql: customer_id
    metrics:
      - name: revenue
        expression:
          sql: SUM(amount) FILTER (WHERE status IN ('paid', 'refunded'))
        datatype: Float
        custom_extensions:
          - vendor_name: STEEP
            data: '{"module":"orders","metric":{"identifier":"revenue","name":"Revenue","type":"sum","value":"orders.amount","time":"orders.created_at","filters":[{"column":"status","operator":"in","expression":"paid,refunded"}]}}'
      - name: revenue__web
        expression:
          sql: SUM(amount) FILTER (WHERE status IN ('paid', 'refunded') AND channel = 'web')
        datatype: Float
        custom_extensions:
          - vendor_name: STEEP
            data: '{"slice_of":"revenue","slice":{"name":"Web","filter":{"column":"channel","operator":"equals","expression":"web"}}}'
    custom_extensions:
      - vendor_name: STEEP
        data: '{"schema":"analytics","table":"orders"}'
  - name: customers
    source: analytics.customers
    unique_keys:
      - [id]
    fields:
      - name: id
        expression:
          sql: id
    custom_extensions:
      - vendor_name: STEEP
        data: '{"schema":"analytics","table":"customers"}'
relationships:
  - name: orders_to_customers
    from: orders
    from_columns: [customer_id]
    to: customers
    to_columns: [id]
    custom_extensions:
      - vendor_name: STEEP
        data: '{"module":"orders","joinPath":{"from":{"column":"customer_id"},"to":{"table":"customers","column":"id"},"type":"one-to-one"}}'
```

A derived ratio `revenue / new-customers` declared on `orders`, where
`new-customers` is a `count` on `customers` with primary key `id`. It is always
model-scoped, and its extension names the declaring module:

```yaml
metrics:
  - name: revenue_per_customer
    expression:
      sql: (SUM(orders.amount) FILTER (WHERE orders.status IN ('paid', 'refunded'))) / NULLIF((COUNT(DISTINCT customers.id)), 0)
    datatype: Float
    custom_extensions:
      - vendor_name: STEEP
        data: '{"module":"orders","metric":{"identifier":"revenue-per-customer","name":"Revenue per customer","type":"derived-ratio","numerator":"revenue","denominator":"new-customers","format":"number"}}'
```

A join path from `orders` to `analytics.products`, which no module uses, has no
relationship. It goes into the `orders` extension instead:

```yaml
custom_extensions:
  - vendor_name: STEEP
    data: '{"schema":"analytics","table":"orders","joinPaths":[{"from":{"column":"product_id"},"to":{"table":"products","column":"id"},"type":"one-to-one"}]}'
```
