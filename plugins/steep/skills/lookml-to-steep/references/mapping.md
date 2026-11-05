# LookML → Steep semantic model YAML mapping

LookML side: the views, explores and joins of a Looker project, read from its
`.lkml` files (<https://cloud.google.com/looker/docs/what-is-lookml>). Steep
side: the `module:` document of Steep as code
(<https://help.steep.app/setup-and-manage/code-reference>), mirrored in
`steep-module-schema.json`. Every LookML parameter is either mapped, ignored on
purpose (listed below), or named in the report. Never drop one silently.

## Contents

- [Conventions](#conventions)
- [Reading the input](#reading-the-input)
- [Project and model](#project-and-model)
- [Module ← view](#module--view)
- [Resolving fields to columns](#resolving-fields-to-columns)
- [Dimension ← dimension](#dimension--dimension)
- [Time columns](#time-columns)
- [Join path ← explore join](#join-path--explore-join)
- [Metric ← measure](#metric--measure)
- [Measure types → metric type](#measure-types--metric-type)
- [Filters](#filters)
- [Filter expressions](#filter-expressions)
- [Number measures and ratios](#number-measures-and-ratios)
- [Explore-level logic](#explore-level-logic)
- [Not representable in Steep (report these)](#not-representable-in-steep-report-these)
- [Example](#example)

## Conventions

- **Identifiers.** LookML field names are unique per view only, and names such
  as `count` repeat across views. A Steep metric identifier is the measure
  name (`total_revenue`) when no other imported measure has that name, else
  `<view>_<measure>` (`orders_count`). A module identifier is the view name.
- **Sanitize** a name: lower-case it, turn runs of characters outside
  `a-z0-9_` into `_`, and trim `_`. **Same name** means equal after sanitizing.
- **Display names.** LookML `label` is the display name: a module or dimension
  `label`, a metric `name`. With no `label`, a metric gets the name Looker
  shows: the field name with `_` as spaces, each word capitalized
  (`average_order_value` → `Average Order Value`). When two imported metrics
  end up with the same name, put the view's label (else its humanized name)
  in front of each (`Orders Count`, `Users Count`). A module and a dimension
  without `label` get none.
- **Physical names** (schema, table, column) must be in the case the warehouse
  stored them in, because Steep quotes every identifier:
  - Prefer the stored names from `information_schema` when you can query it.
  - Otherwise fold unquoted names the way the warehouse does: upper case on
    Snowflake (`amount` → `AMOUNT`), lower case on Postgres, Redshift and
    DuckDB, as written elsewhere (BigQuery, Databricks). A quoted name
    (`"Amount"`, `` `Amount` ``) keeps its exact text.
- **Custom SQL dialect.** LookML `sql:` is already in the warehouse's SQL. Keep
  it when the Steep workspace runs on the same warehouse. If it does not,
  translate only what you are sure of, and skip and report the rest.
- **Key order** in a metric: `identifier`, `name`, `description`, `type`, the
  type's fields (`value`, `distinct_on`, `numerator`, `denominator`,
  `sql_expression`, `numerator_sql`, `denominator_sql`), `format`, `time`,
  `time_aggregation`, `time_grains`, `is_unlisted`, `dimensions`, `filters`,
  `slices`. Modules and dimensions follow the order of the rows in their
  tables below.
- **Report** in the chat, not in a file, unless the user asks for one.

## Reading the input

A Looker project is a git repository of `.lkml` files:

| File | Holds |
| --- | --- |
| `*.model.lkml` | `connection`, `include`, `explore`s with their `join`s, `datagroup`s, `access_grant`s, `week_start_day`, `fiscal_month_offset`, `case_sensitive` |
| `*.view.lkml` | `view`s: `sql_table_name` or `derived_table`, `dimension`, `dimension_group`, `measure`, `filter`, `parameter`, `set` |
| `*.explore.lkml` | `explore`s kept outside the model file, pulled in by `include` |
| `manifest.lkml` | `constant`s (`@{name}`), `local_dependency` / `remote_dependency` imported projects, `localization_settings` |
| `*.dashboard.lookml`, `*.md`, `*.strings.json` | nothing to import |

Parse the files with the `lkml` Python package (`python3 -m pip install lkml`;
`lkml.load(text)` returns a dict) when it is available, else read them by
hand. Then resolve, in this order, before mapping anything:

1. **Includes.** A model sees only the files its `include:` globs match
   (`/views/*.view.lkml`, `//other_project/...` for an imported project). An
   imported project you do not have is a gap: report the views it holds.
2. **Constants.** Replace each `@{name}` with its `value` from
   `manifest.lkml`. A constant whose value is Liquid is unresolvable (see
   [Templating](#templating)).
3. **Extends.** A view or explore with `extends: [base]` starts from a copy of
   `base`, then its own parameters override `base`'s. Fields with the same name
   merge parameter by parameter, the child's winning. A view with
   `extension: required` is only a base: never a module on its own.
4. **Refinements.** `view: +orders { … }` changes `orders` in place, in the
   order the files are included, with the same merge rules. A refinement on a
   view marked `final: yes` is a Looker error: report it.

**Which views.** Import the views that appear in an explore of the models the
user picks (ask when the project has several models). List views that no
explore uses: Looker cannot query them either.

**Looker API.** Without the repository, the API's
`GET /lookml_models/{model}/explores/{explore}` returns every field of an
explore with includes, constants, extends and refinements already resolved:
`name`, `type`, `sql`, `label`, `description`, `hidden`, `primary_key`,
`measure` / `dimension` lists, and the explore's `joins` with `sql_on` and
`relationship`. It drops `filters:` details on some versions and gives no
`sql_table_name` for derived tables. Use it when the user can give you API
access and not the repo, and say so in the report.

### Templating

Liquid (`{% … %}`, `{{ … }}`), `parameter` fields, templated filters
(`{% condition … %}`) and user attributes (`{{ _user_attributes['…'] }}`)
change the SQL per query or per user. Steep has nothing like them. Any field,
`sql_table_name` or join whose SQL holds Liquid cannot be imported: skip it,
along with everything that references it, and report it. `filter:` fields
(filter-only fields) are templating inputs: ignore them.

## Project and model

| LookML | Steep |
| --- | --- |
| each view with a table, used in an explore | one module |
| explore `join`s | `joinPaths` (see [Join path ← explore join](#join-path--explore-join)) |
| measures | metrics on their view's module |
| explores themselves | nothing: Steep has no explores. Their logic: see [Explore-level logic](#explore-level-logic) |
| `connection` | nothing. Ask which warehouse it is, and confirm the Steep workspace uses the same one. |
| `datagroup`, `persist_with`, `aggregate_table`, `access_grant`, dashboards | nothing. Report them once. |
| `week_start_day` other than `monday`, `fiscal_month_offset` | nothing. Report them: weekly and fiscal grains may group differently in Steep. |
| `case_sensitive: no` | nothing. Report it: Steep string filters compare exactly (see [Filter expressions](#filter-expressions)). |

## Module ← view

| Steep | From |
| --- | --- |
| `identifier` | the identifier of the module already on that table in the repo, else the view name |
| `schema`, `table` | parsed from `sql_table_name`, in stored case (Conventions) |
| `label` | view `label` |
| `description` | view `description` |
| `dimensions` | see [Dimension ← dimension](#dimension--dimension) |
| `metrics` | this view's measures, then ratios placed here |
| `joinPaths` | see [Join path ← explore join](#join-path--explore-join) |

- **`sql_table_name`.** Strip the trailing `;;` and quoting, then split on
  dots: `schema.table`; `database.schema.table` (drop the database, and ask
  the user to confirm their Steep connection points at it); on BigQuery
  `project.dataset.table` (dataset → schema, table → table; drop the
  project). A value with Liquid, or one that names another view's
  `${view.SQL_TABLE_NAME}`, is not a table: treat the view as derived.
- **No `sql_table_name` and no `derived_table`.** Looker uses the view's name
  as the table, in the connection's default schema. Ask for the schema.
- **`derived_table`** (`sql:`, `explore_source:`, persisted or not): Steep
  modules sit on tables, and a persisted derived table lives under a
  generated name that changes. Skip the view and everything on it, and report
  it, suggesting a warehouse table (a dbt model, a scheduled view) Steep can
  read. If the user already has such a table, map the view onto it.
- **One table, one module.** Steep fails the whole sync when two modules use
  the same `schema.table`. Two views on one table (often one `extends` the
  other to rename it for a second join) become one module: merge their
  dimensions and measures, and report fields that conflict. If the target repo
  already has a module on that table, add to it instead.
- **`primary_key: yes`** marks the key used by `count`, `foreign_key` joins and
  `_distinct` measures. Steep has no other slot for it unless the user wants a
  Steep entity. Then add one (`identifier` and `name` from the view,
  `primary_key`, and `properties` from the module's dimensions with
  `type: string`), and ask which properties to keep.
- View `tags`, `drill_fields`, `set`s and `suggestions`: report once.

## Resolving fields to columns

A field's SQL is its `sql:`, or `${TABLE}.<field name>` when it has none.
Substitute references until only SQL is left:

- `${TABLE}` is this view's table.
- `${field}` is the SQL of another field in this view, `${view.field}` of a
  field in another view. For a dimension group, `${created_raw}`,
  `${created_time}` and `${created_date}` all stand for the group's SQL.
- `${view.SQL_TABLE_NAME}` is that view's table.

The result is one of:

- **Column item:** a single column of one view's table, optionally quoted and
  prefixed with `${TABLE}.` or the table name. It maps to that physical
  column.
- **Computed item:** anything else (`${amount} > 100`, `CASE …`,
  `CONCAT(…)`, a `case:` parameter, `tier` bins). Steep has no computed
  columns, so it can only appear inside custom SQL. It cannot be a dimension,
  a metric `time`, a `sum` value, a filter column or a join column.
  Exception: `DATE_TRUNC('<part>', col)` and `CAST(col AS DATE)` /
  `col::date` resolve to `col` when used as a time column, because Steep
  truncates time itself.

## Dimension ← dimension

A LookML `dimension` becomes a Steep dimension when all of these hold:

- it is a column item;
- its `type` is `string` (the default), `yesno` or `zipcode`;
- its column is text, or boolean for `yesno`. LookML `type` does not prove the
  column's type (a number column typed `string` works in Looker). Read the
  type from `information_schema` when you can. Otherwise trust the LookML type
  and say so in the report;
- it is not `hidden: yes` and not the `primary_key`. Hidden fields are
  usually building blocks, and keys are not useful to group by. List both so
  the user can add the ones they want.

| Steep | From |
| --- | --- |
| `column` | the physical column |
| `identifier` | the dimension name when it differs from the column compared case-insensitively; else omit it |
| `label` | `label`, else none. `group_label` and `view_label` have no Steep slot. |
| `description` | `description` |
| `type` | `categorical`. Use `country` when `map_layer_name: countries`, and `city` only when the user confirms the values are city names. Ask before using `country` for a field without it. |

**`yesno` on a boolean column** (`sql: ${TABLE}.is_active ;;`) imports as a
dimension on that column. Looker shows `Yes` / `No`, with NULL as `No`; Steep
shows the column's `true`, `false` and NULL. Say this once in the report. A
`yesno` on a condition (`${amount} > 100`) is computed: it is no dimension, but
it can still be a filter (see [Filters](#filters)).

These have no Steep dimension form: `number`, `tier` / `bin`, `location`,
`distance`, `duration` dimension groups, `type: duration_*`, computed
dimensions, and dimensions with `case:`. List them in the report, and suggest
exposing a useful one as a text column in the warehouse.

Time fields are time column candidates instead (see
[Time columns](#time-columns)). The import makes no `type: time` dimensions:
Steep uses those only for cohorts, which LookML does not have.

Ignore, and say once in the report that they were not carried: `html`, `link`,
`drill_fields`, `suggestions`, `suggest_dimension`, `allowed_value`,
`order_by_field`, `can_filter`, `required_fields`, `required_access_grants`,
`value_format`, `tags`, `alias`, `group_label`, `group_item_label`.

## Time columns

**Candidates.** A field is a time column candidate when it is a column item
and either:

- a `dimension_group` with `type: time` and a `datatype` of `datetime` (the
  default), `timestamp` or `date`; or
- a `dimension` with `type: date`, `date_time`, or another single `date_*`
  timeframe type.

`datatype: epoch` and `datatype: yyyymmdd` columns are numbers or text, which
Steep cannot use as `time`. Report them, and suggest a date column in the
warehouse.

### Metric `time`

LookML measures do not say which time field they are measured over: in Looker,
the user picks one at query time. Every Steep metric except `derived-ratio`
needs exactly one. Pick it per measure, taking the first that applies:

1. A `period_over_period` measure whose `based_on` is this measure names a
   time field in `based_on_time`. Use that group's column.
2. The measure's view has exactly one time column candidate. Use it.
3. Otherwise **ask**, once per view, listing its candidates. Suggest, in this
   order: a field in an `always_filter` or `conditionally_filter` of the
   explore whose base view this is, then a group named `created`. Never pick
   one without asking.

A view with no candidate cannot carry metrics. Report its measures, and ask
whether a joined view's date should be added as a column of its table in the
warehouse.

### Metric `time_grains`

A dimension group's `timeframes` list what Looker offers. Take the finest:

| Finest timeframe | `time_grains` |
| --- | --- |
| `raw`, `time`, `date`, `hour*`, `minute*`, `second`, or no `timeframes` | omit |
| `week` | `[weekly, monthly, quarterly, yearly]` |
| `month` | `[monthly, quarterly, yearly]` |
| `quarter` | `[quarterly, yearly]` |
| `year` | `[yearly]` |

Grains named `fiscal_*` follow `fiscal_month_offset`: report them. Ignore
`day_of_week`, `month_name` and other timeframes that are not a period.

**Time zones.** Looker converts timestamps to the query time zone unless the
group has `convert_tz: no` or the connection has conversion turned off (a
Looker admin setting, not in LookML). Ask the user whether conversion is on.
If it is, report that days and weeks can start at different hours in Steep.

## Join path ← explore join

Steep joins two tables through one join path. Build them from the joins of
every explore the import covers. In a join, the **parent** is the view on the
other side of its `sql_on` (the explore's base view, or a view joined before
it), and the **joined view** is the join's own view (its `from:` view when it
has one).

`relationship` describes parent → joined view and defaults to `many_to_one`:

| `relationship` | Declared in | `from.column` | `to` | `type` |
| --- | --- | --- | --- | --- |
| `many_to_one` (default) | the joined view, the one side | its key column | the parent's `table`, `schema` if it differs, `column`: the parent's key column | `one-to-many` |
| `one_to_many` | the parent, the one side | its key column | the joined view's table and key column | `one-to-many` |
| `one_to_one` | the parent | its key column | the joined view's table and key column | `one-to-one` |
| `many_to_many` | nothing: skip and report | | | |

**Keys.** `sql_on` must be one equality between two column items, one on each
view (`${orders.user_id} = ${users.id}`). `foreign_key: user_id` means
`${parent.user_id} = ${joined.<primary key>}`. Steep cannot represent:

- **an `sql_on` with more than one condition** (`AND`), a non-equality, a
  computed side, or `sql:` / `sql_where:` joins: drop the join and report it;
- **a second join between the same two tables** (another explore with other
  keys, or a view joined twice under two names with `from:`, such as `buyers`
  and `sellers` on `users`): Steep fails the sync on a duplicate. Keep the
  first and report the others. The same join in several explores is one join:
  declare it once. If two explores give it different relationships, ask;
- **a join of a table to itself**: drop and report.

`type:` (`left_outer` by default, `inner`, `full_outer`, `cross`): Steep joins
are not typed this way. Report non-default types once. `fields:`,
`view_label`, `required_joins` and `relationship` checks on Looker's side
have no Steep slot.

## Metric ← measure

The module is the measure's view. A measure on a view that did not become a
module (derived table, no time column) is not imported.

| Steep | From |
| --- | --- |
| `identifier` | see Conventions. Avoid identifiers already in the repo, unless it is the same metric (see SKILL.md, "Write into the repo"). |
| `name` | `label`, else the Looker display name (Conventions) |
| `description` | `description` |
| `type` and its fields | see [Measure types → metric type](#measure-types--metric-type) |
| `time` | see [Metric `time`](#metric-time) |
| `time_grains` | see [Metric `time_grains`](#metric-time_grains) |
| `is_unlisted` | `true` for a `hidden: yes` measure that is imported (see below) |
| `dimensions` | `this.*` when the module has dimensions, then `<schema>.<table>.*` for each module the view reaches by joins from many to one (transitively, and both ways across a one-to-one), when that module has dimensions. Omit when empty. |
| `filters` | see [Filters](#filters) |

**Hidden measures** are usually inputs to `number` measures. Import one only
when an imported metric refers to it as an operand, with `is_unlisted: true`,
or when it becomes a slice (see
[Number measures and ratios](#number-measures-and-ratios)). List the others.

Ignore, and say once in the report: `drill_fields`, `html`, `link`, `tags`,
`group_label`, `view_label`, `required_access_grants`, `can_filter`,
`approximate`, `approximate_threshold`, `allow_approximate_optimization`. Say
which measures had `value_format` / `value_format_name` other than a percent
format: Steep formats non-ratio metrics itself.

## Measure types → metric type

`e` is the measure's resolved SQL; `x` is a column item. Take the first row
that matches:

| LookML `type` | Steep `type` | Steep fields |
| --- | --- | --- |
| `count` | `count` | (`count` has no `sql`; it counts the primary key) |
| `count_distinct`, `x` | `count-distinct` | `distinct_on: <TABLE>.<X>` |
| `sum`, `x` | `sum` | `value: <TABLE>.<X>` |
| `sum_distinct`, `average_distinct`, `median_distinct`, `percentile_distinct` whose `sql_distinct_key` resolves to the view's primary key column (`median_` and `percentile_distinct` default to it) | as the type without `_distinct` | |
| other `_distinct` measures | nothing: skip and report | |
| `count_distinct`, `sum` with a computed `e`; `average`, `min`, `max`, `median`, `percentile` | `custom-value` | `sql_expression`, see below |
| `number` | see [Number measures and ratios](#number-measures-and-ratios) | |
| `string` (the default when `type` is missing), with an `e` that is a numeric aggregate (`SUM(…)`, `COUNT(…)`) | `custom-value` | `sql_expression: e` |
| `percent_of_total`, `percent_of_previous`, `running_total` | nothing: Looker computes them after the query, over the rows shown. Skip and report. | |
| `period_over_period` | nothing: Steep compares periods itself in reports. Skip and report; use its `based_on_time` (see [Metric `time`](#metric-time)). | |
| `list`, `date`, `yesno`, other `string` | nothing: not a number. Skip and report. | |

**`_distinct` measures** fix double counting when a join repeats rows. Steep
computes a metric on its own table, where that does not happen, so with the
view's own primary key as `sql_distinct_key` they are plain aggregates.

**Measures on another view's columns.** When `e` uses columns of another view
(`sum` of `${users.lifetime_value}` on `orders`), put them in custom SQL only
when that view is reached from many to one, where the value repeats per row as
it does in Looker's SQL. Looker's symmetric aggregates would deduplicate it;
Steep would not. Skip the measure and report it, unless it is a
`count_distinct`, which repeats harmlessly.

**Custom SQL.** Steep runs `sql_expression`, `numerator_sql` and
`denominator_sql` as written, inside a query where each table is aliased by its
bare physical table name. So write `${TABLE}.amount` and `${amount}` as
`ORDERS.AMOUNT`, and wrap the aggregation:

| LookML `type` | `sql_expression` |
| --- | --- |
| `count` with filters that need SQL | `COUNT(CASE WHEN P THEN <TABLE>.<PK> END)`, or `COUNT(CASE WHEN P THEN 1 END)` without a primary key |
| `count_distinct` | `COUNT(DISTINCT e)` |
| `sum`, `min`, `max` | `SUM(e)`, `MIN(e)`, `MAX(e)` |
| `average` | `AVG(e)` |
| `median` | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY e)`, or the warehouse's `MEDIAN(e)` |
| `percentile` with `percentile: p` | `PERCENTILE_CONT(p / 100) WITHIN GROUP (ORDER BY e)`: write `95` as `0.95` |

If the warehouse has no aggregate form (exact percentiles on BigQuery), skip
the measure and report it.

## Filters

A measure's `filters: [field: "expression", …]` restricts what it aggregates.
Looker applies it only to `count`, `count_distinct`, `sum` and `average`
measures. On any other type it has no effect in Looker: do not import it, and
report it.

Each entry names a field and a [filter expression](#filter-expressions).
Entries are ANDed. Resolve the field:

- **A column item** on the measure's view, or on a view it reaches from many
  to one: the filter `column`, with `table` (and `schema` if it differs) for
  another view.
- **A dimension group timeframe** (`created_date`, `created_month`): the
  group's column, with a [date expression](#dates).
- **A `yesno` dimension on a condition** (`is_large: "yes"`, with
  `sql: ${amount} > 100 ;;`): the condition. `yes` maps it with the SQL table
  below; `no` is the negated condition OR NULL in Looker, which has no Steep
  filter form, so use custom SQL.
- **Anything else** (a computed field, a view reached from one to many,
  Liquid): custom SQL, or skip (below).

A condition in SQL maps to Steep filters when it is an `AND` of these forms,
where `f` is a column:

| SQL | Steep `operator` | Steep `expression` |
| --- | --- | --- |
| `f = v`, `f <> v`, `f != v` | `equals`, `not-equals` | `v` |
| `f < v`, `<=`, `>`, `>=` | `less-than`, `less-than-or-equal`, `greater-than`, `greater-than-or-equal` | `v` |
| `f IN (v1, v2)`, `f NOT IN (…)` | `in`, `not-in` | `v1,v2` |
| `f IS NULL`, `f IS NOT NULL` | `is`, `is-not` | `null` |
| `f` (boolean column), `NOT f` | `equals` | `true`, `false` |

Steep renders `expression` by splitting it on commas. For each part, `TRUE`,
`FALSE`, `NULL` and anything that parses as JSON (numbers, `true`, `false`,
`null`) pass through unchanged. Anything else becomes a single-quoted string
literal, after stripping one pair of surrounding single quotes. So write a
value as:

- a number: as is, `100`;
- a string: without quotes, `paid`;
- a string that would parse as JSON or a keyword (`123` on a text column,
  `true`, `null`), or that starts or ends with a space: in single quotes,
  `'123'`.

**When it cannot be Steep filters.** Put the condition inside the aggregate
as custom SQL (`SUM(CASE WHEN P THEN e END)`, and the `count` row above), with
physical columns, when every column is on the measure's own table. Otherwise
skip the measure and report it.

Steep `filters` are a `WHERE` on the metric query, which matches Looker's
filtered measures (`CASE WHEN` inside the aggregate) for every group that has
matching rows. A group with none shows no value in Steep and `0` or NULL in
Looker. Say this once in the report.

## Filter expressions

Looker filter expressions
(<https://cloud.google.com/looker/docs/filter-expressions>) depend on the
field's type. Inside an expression, `,` separates values and is an OR, except
that negated string values are ANDed. Trim spaces around each value. `^`
escapes the next character (`^,`, `^%`, `^_`, `^-`, `^^`).

### Strings

| Expression | Steep `operator` | Steep `expression` |
| --- | --- | --- |
| `FOO` | `equals` | `FOO` |
| `FOO,BAR` | `in` | `FOO,BAR` |
| `-FOO` | `not-equals` | `FOO` |
| `-FOO,-BAR` | `not-in` | `FOO,BAR` |
| one value with `%` or `_` (`%FOO%`, `FOO%`, `F%OD`, `_UF`) | `like` | the pattern |
| one negated pattern (`-%FOO%`) | `not-like` | the pattern |
| `NULL`, `-NULL` | `is`, `is-not` | `null` |

No Steep filter form: `EMPTY` and `-EMPTY` (empty string or NULL), a mix of
operators (`FOO%,BAR`, `FOO%,-FOOD`, `FOO,NULL`), and a value with an escaped
comma (`Santa Cruz^, CA`), because Steep splits values on commas.

**Case.** Looker matches strings case-insensitively when the model sets
`case_sensitive: no` on a warehouse that supports it. Steep compares exactly.
Report every imported string filter of such a model.

### Numbers

| Expression | Steep |
| --- | --- |
| `5` | `equals 5` |
| `1, 3, 5` | `in 1,3,5` |
| `NOT 5`, `<>5`, `!=5` | `not-equals 5` |
| `NOT 66, 99, 4` | `not-in 66,99,4` |
| `>5`, `>=5`, `<5`, `<=5` | `greater-than`, `greater-than-or-equal`, `less-than`, `less-than-or-equal` |
| `>=1 AND <100` | two filters |
| `5 to 10`, `[5, 10]` | `greater-than-or-equal 5` and `less-than-or-equal 10` |
| `(5, 10)`, `(5, 10]`, `[5, 10)` | the strict or inclusive pair to match |
| `1 to`, `(500, inf)`, `(500,)`, `to 10`, `(,10]` | one filter for the closed end |
| `NULL`, `NOT NULL` | `is null`, `is-not null` |

No Steep filter form: anything with an OR (`<25, >65`, `[0,9],[20,29]`,
`>10 AND <=20 OR 90`, `NOT 3 to 80.44`) and mixed negations
(`5, NOT 6, NOT 7`).

### Booleans

| Expression | On | Steep |
| --- | --- | --- |
| `yes` / `Yes` | a `yesno` dimension | its condition (see [Filters](#filters)) |
| `no` / `No` | a `yesno` dimension | custom SQL (NULL counts as `no` in Looker) |
| `TRUE`, `FALSE` | a boolean column | `equals true`, `equals false` |

### Dates

On a time column (any timeframe of a dimension group: the expression applies
to the group's column):

| Expression | Steep |
| --- | --- |
| `after 2024-01-01` | `greater-than-or-equal 2024-01-01` |
| `before 2024-01-01` | `less-than 2024-01-01` |
| `2024-01-01 to 2024-04-01` | `greater-than-or-equal 2024-01-01` and `less-than 2024-04-01` |
| `2024-01-01` (one day) | `greater-than-or-equal 2024-01-01` and `less-than 2024-01-02` |
| `2024/05`, `2024` (a whole month or year) | the same pair over that period |

Write dates as `YYYY-MM-DD` (Looker also accepts `/`). Relative dates (`7 days`,
`this month`, `3 days ago for 2 days`, `today`, `before 3 days ago`,
`next week`), fiscal periods (`FY2024-Q1`) and weekdays have no Steep form:
use custom SQL with the warehouse's date functions when you are sure of the
meaning, else skip the measure and report it.

## Number measures and ratios

A `type: number` measure computes over other measures (`${a}`, `${view.b}`)
and SQL. Resolve each `${…}` to the measure it names, then match its `sql`,
ignoring a leading `1.0 *` or `CAST(… AS FLOAT)` that only forces decimal
division:

| `sql` | Steep |
| --- | --- |
| `${a} / ${b}`, `${a} / NULLIF(${b}, 0)`, optionally `* 100` or `100.0 *` | a ratio of `a` and `b` (below). A factor of 100 means `format: percentage`; drop it. |
| any other expression over measures of one view | inline each operand's custom SQL into one `custom-value` on that view, when they share a `time` column |
| plain aggregate SQL, no `${measure}` (`SUM(${TABLE}.x) / COUNT(*)`) | `custom-value`, or `custom-ratio` when it is `AGG / AGG` |
| anything else (operands on views not reached from many to one, post-SQL operands, `CASE` over measures) | nothing: skip and report |

A `number` measure with `filters:` ignores them in Looker: ignore them too, and
report it.

### Ratios

Resolve `a` and `b` to Steep metrics first. Take the first row that matches:

| Case | Steep |
| --- | --- |
| Both are `sum` metrics on the same module, with the same `time` and the same filters | `ratio`, `numerator: <TABLE>.<A>`, `denominator: <TABLE>.<B>`, those `filters`, and their `time` |
| One is the other with exactly one more Steep filter (often a hidden measure such as `web_revenue` next to `total_revenue`) | `derived-ratio`, with the wider one as a metric and the narrower as a slice of it (below) |
| `b` is a `count` of a view the measure's view reaches from many to one (`${users.count}` on `orders`) | `custom-ratio` on the measure's module, `denominator_sql: COUNT(DISTINCT <TABLE>.<FOREIGN KEY>)`, `numerator_sql` from `a`'s custom SQL with its filters inside the aggregate, and `a`'s `time` |
| Both on the same module with the same `time`, otherwise | `custom-ratio`, `numerator_sql` and `denominator_sql` from each operand's custom SQL, with its filters inside the aggregate |
| Both are imported metrics, on any modules | `derived-ratio`, `numerator` and `denominator` as identifiers; no `time` |
| Otherwise | nothing: skip and report |

**Why the `count` row.** In Looker, `${users.count}` inside an `orders` measure
counts the distinct users among the orders in the query, on the orders' time
field. A `derived-ratio` over a Steep users count would count users by their
own time column instead: users created in the period, not users who ordered
in it. Counting the foreign key on the measure's own table keeps Looker's
meaning.

**Slices.** For the second row, the operand is `{ metric, slice }`: add a slice
to the wider metric with the one extra filter, unless one with the same filter
is already there. The narrower measure is then not imported on its own unless
it is visible (not `hidden`); if it is visible, import it too and report the
overlap.

| Slice | From |
| --- | --- |
| `name` | the filter value humanized (`web` → `Web`) |
| `identifier` | omit it when the name in snake_case is what Steep generates; else the sanitized name |
| `filter` | the one filter |

**`format`**, on every `ratio`, `custom-ratio` and `derived-ratio`: Steep
renders `percentage` as the fraction × 100. Use `percentage` when the measure
has `value_format_name: percent_*` (or a `value_format` with `%`), or the
`sql` multiplies by 100; else `number`. Steep defaults to `percentage`, so
always write it, and list every ratio whose format came from neither under
"Needs a decision".

Place a ratio on the numerator's module, after that module's other metrics. A
`derived-ratio` computes each operand on its own module and time column, then
divides. Report every derived ratio whose operands' `time` columns differ.

## Explore-level logic

Steep metrics carry their own filters; there is no explore around them. Report
each of these with its explore, and never copy it onto metrics without asking,
because it would change every metric on the view in every report:

| LookML | Steep |
| --- | --- |
| `sql_always_where`, `sql_always_having` | nothing. If the user wants it, add it as filters on every metric of the base view (when it maps to Steep filters) and say so. |
| `always_filter`, `conditionally_filter` | nothing: defaults the user can change in Looker. Use as a hint for [Metric `time`](#metric-time). |
| `access_filter`, `required_access_grants` | nothing. Never write `accessPolicies`: Looker row-level security keys on user attributes Steep does not have. Tell the user which views were restricted. |
| `fields`, `hidden`, `group_label`, `always_join`, `cancel_grouping_fields`, `persist_with`, `aggregate_table` | nothing |

## Not representable in Steep (report these)

- Views on derived tables (`derived_table`, persisted or not) and everything
  on them; imported projects you do not have.
- Liquid, `parameter` fields, templated filters and user attributes.
- `percent_of_total`, `percent_of_previous`, `running_total`,
  `period_over_period`, `list`, `date`, `yesno` and non-numeric `string`
  measures; `_distinct` measures keyed on something other than the primary
  key; measures on columns of views reached from one to many.
- `number` measures that are not ratios or single-view expressions.
- Filters with OR across operators, `EMPTY`, relative or fiscal dates,
  escaped commas, or on computed fields of other views; `no` on a `yesno`
  condition outside custom SQL.
- `many_to_many` joins, joins with more than one condition or a computed key,
  views joined twice under two names, self joins.
- `number`, `tier`, `bin`, `location`, `distance` and computed dimensions;
  `duration` and `custom_calendar` groups; `epoch` and `yyyymmdd` time
  columns.
- Explore filters, `access_filter`, access grants, datagroups, aggregate
  tables, `week_start_day`, `fiscal_month_offset`, time zone conversion.
- Presentation: `html`, `link`, `drill_fields`, `value_format`s outside ratios,
  `group_label`, `tags`, sets, dashboards.

Steep features LookML does not carry, which stay empty: access policies,
cohorts, time resampling, categories, owners, synonyms, agent instructions,
examples, `is_private`, entities (unless asked), entity links, targets.

## Example

A Snowflake project, `ecommerce.model.lkml`:

```lookml
connection: "snowflake_prod"
include: "/views/*.view.lkml"

explore: orders {
  join: users {
    sql_on: ${orders.user_id} = ${users.id} ;;
    relationship: many_to_one
  }
}
```

`views/orders.view.lkml`:

```lookml
view: orders {
  sql_table_name: analytics.orders ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }
  dimension: user_id {
    type: number
    hidden: yes
    sql: ${TABLE}.user_id ;;
  }
  dimension: status {
    sql: ${TABLE}.status ;;
  }
  dimension: channel {
    label: "Sales channel"
    sql: ${TABLE}.channel ;;
  }
  dimension: amount {
    type: number
    hidden: yes
    sql: ${TABLE}.amount ;;
  }
  dimension: is_large {
    type: yesno
    sql: ${amount} > 100 ;;
  }
  dimension_group: created {
    type: time
    timeframes: [raw, date, week, month, year]
    sql: ${TABLE}.created_at ;;
  }

  measure: count {
    type: count
  }
  measure: total_revenue {
    type: sum
    sql: ${amount} ;;
    filters: [status: "complete, shipped"]
    value_format_name: usd
  }
  measure: web_revenue {
    type: sum
    hidden: yes
    sql: ${amount} ;;
    filters: [status: "complete, shipped", channel: "web"]
  }
  measure: web_revenue_share {
    type: number
    sql: ${web_revenue} / NULLIF(${total_revenue}, 0) ;;
    value_format_name: percent_1
  }
  measure: average_order_value {
    type: average
    sql: ${amount} ;;
  }
  measure: large_orders {
    type: count
    filters: [is_large: "yes"]
  }
  measure: revenue_per_user {
    type: number
    sql: 1.0 * ${total_revenue} / NULLIF(${users.count}, 0) ;;
  }
  measure: revenue_percent_of_total {
    type: percent_of_total
    sql: ${total_revenue} ;;
  }
}
```

`views/users.view.lkml`:

```lookml
view: users {
  sql_table_name: analytics.users ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }
  dimension: segment {
    sql: ${TABLE}.segment ;;
  }
  dimension: country {
    map_layer_name: countries
    sql: ${TABLE}.country ;;
  }
  dimension: age {
    type: number
    sql: ${TABLE}.age ;;
  }
  dimension_group: created {
    type: time
    timeframes: [date, month, year]
    sql: ${TABLE}.created_at ;;
  }

  measure: count {
    type: count
  }
}
```

The warehouse is Snowflake, so physical names are upper case.
`information_schema` says `STATUS`, `CHANNEL`, `SEGMENT` and `COUNTRY` are
text.

Steep, `modules/orders.yaml`:

- `count` is a name in both views, so the identifiers are `orders_count` and
  `users_count`, and the names `Orders Count` and `Users Count`.
- Each view has one time column candidate, `created`, so it is every metric's
  `time`.
- `large_orders` filters on `is_large`, a `yesno` condition: `AMOUNT > 100`.
- `web_revenue` is `total_revenue` with one more filter, and hidden: it becomes
  the `Web` slice of `total_revenue`, and `web_revenue_share` a
  `derived-ratio` on it. `percent_1` gives `format: percentage`.
- `revenue_per_user` divides by `${users.count}`, a view `orders` reaches from
  many to one: a `custom-ratio` counting distinct `USER_ID` on `ORDERS`, with
  `total_revenue`'s filter inside the numerator. Its format is `number`, from
  neither a percent format nor `* 100`.
- `revenue_percent_of_total` is skipped (post-SQL).
- Metric `dimensions` are this module's and those of `users`, which `orders`
  reaches from many to one.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: orders
  schema: ANALYTICS
  table: ORDERS
  dimensions:
    - column: STATUS
      type: categorical
    - column: CHANNEL
      label: Sales channel
      type: categorical
  metrics:
    - identifier: orders_count
      name: Orders Count
      type: count
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - ANALYTICS.USERS.*
    - identifier: total_revenue
      name: Total Revenue
      type: sum
      value: ORDERS.AMOUNT
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - ANALYTICS.USERS.*
      filters:
        - column: STATUS
          operator: in
          expression: complete,shipped
      slices:
        - name: Web
          filter:
            column: CHANNEL
            operator: equals
            expression: web
    - identifier: average_order_value
      name: Average Order Value
      type: custom-value
      sql_expression: AVG(ORDERS.AMOUNT)
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - ANALYTICS.USERS.*
    - identifier: large_orders
      name: Large Orders
      type: count
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - ANALYTICS.USERS.*
      filters:
        - column: AMOUNT
          operator: greater-than
          expression: "100"
    - identifier: web_revenue_share
      name: Web Revenue Share
      type: derived-ratio
      numerator:
        metric: total_revenue
        slice: web
      denominator: total_revenue
      format: percentage
    - identifier: revenue_per_user
      name: Revenue Per User
      type: custom-ratio
      numerator_sql: SUM(CASE WHEN ORDERS.STATUS IN ('complete', 'shipped') THEN ORDERS.AMOUNT END)
      denominator_sql: COUNT(DISTINCT ORDERS.USER_ID)
      format: number
      time: ORDERS.CREATED_AT
      dimensions:
        - this.*
        - ANALYTICS.USERS.*
```

`modules/users.yaml`:

- `orders → users` is `many_to_one`, so the join path is declared here, on the
  one side.
- `COUNTRY` has `map_layer_name: countries`: `type: country`.
- `AGE` is a number and `ID` the primary key: no dimensions.
- `timeframes` go down to `date`, so `time_grains` is omitted.

```yaml
# yaml-language-server: $schema=https://api.steep.app/v1/code/schema
module:
  identifier: users
  schema: ANALYTICS
  table: USERS
  dimensions:
    - column: SEGMENT
      type: categorical
    - column: COUNTRY
      type: country
  metrics:
    - identifier: users_count
      name: Users Count
      type: count
      time: USERS.CREATED_AT
      dimensions:
        - this.*
  joinPaths:
    - from:
        column: ID
      to:
        table: ORDERS
        column: USER_ID
      type: one-to-many
```

Report items for this example:

- Database: none in `sql_table_name`; confirm the Steep connection points at
  the one `snowflake_prod` uses.
- Not imported: `revenue_percent_of_total` (post-SQL).
- `web_revenue` became the `Web` slice of `total_revenue`.
- Formats: `web_revenue_share` → `percentage` (from `percent_1`);
  `revenue_per_user` → `number`, guessed. `total_revenue`'s `usd` format is
  not carried.
- Dimensions left out: `orders.is_large` (computed), `users.age` (number),
  the primary keys and hidden fields.
- `COUNTRY` is `type: country` from `map_layer_name`; confirm it holds
  country codes or names Steep recognizes.
- Filtered metrics: a group with no matching rows is absent rather than `0`.
- Time zones: ask whether `snowflake_prod` converts to a query time zone.
