# YAML schema reference

**Canonical source:** <https://help.steep.app/setup-and-manage/code-reference>

This file is a **local cache** of that page, checked field by field against
it, for fast lookup while authoring `modules/*.yaml` and for agents
that cannot reach the network. It may lag. Fetch the canonical page when
correctness matters: before authoring an unfamiliar construct, when a field is
rejected, or when this file and the page disagree. The page changes slowly, so
fetching it once per session and working from that copy is enough. **On any
conflict about the contract, the page wins.**

The notes here about *sync behavior* (what a violation produces, what omission
deletes, how objects are reconciled) are not on that page; they come from
observed sync behavior and are documented in `debugging.md`.

For working examples see `examples/`.

## Contents

- [Files and root keys](#files-and-root-keys)
- [Casing](#casing)
- [Module](#module)
- [Dimension](#dimension)
- [Metric](#metric) (+ metric `type` and type-specific fields)
- [Filter](#filter)
- [Slice](#slice)
- [Cohort](#cohort)
- [Join path](#join-path)
- [Access policy](#access-policy)
- [Entity](#entity)
- [Targets](#targets)
- [AI context](#ai-context)
- [Offline check](#offline-check)

## Files and root keys

There are exactly **two** recognized root keys:

| Root | What it defines | File convention |
| --- | --- | --- |
| `module:` | A table, plus its dimensions, metrics, slices, filters, cohorts, join paths, access policies, and entities | One module per file |
| `targets:` | Which schema/table Steep reads targets from | Its own dedicated file, **one per workspace** |

Everything except `targets:` nests *inside* a `module:`.

How Steep decides what a file is:

- A file that contains a **recognized root** is treated as Steep YAML and
  validated. If a stray extra root snuck in next to it (for example a
  misindented `entities:` that ended up at the top level), validation **fails
  loudly** with a clear error and the sync aborts; it is not silently ignored.
- A file with **no recognized root at all** (a `metric:`-only file, a CI config,
  any other YAML in the repo) is **silently skipped, no error is raised.** Those
  definitions simply never appear in Steep. If a customer says "I added a metric
  file and it didn't show up," check the root key first.

One module per file is the normal convention. The schema is **strict**: unknown
extra keys cause a validation failure (an `Unprocessable`, see `debugging.md`).

## Casing

Everything is **snake_case** with exactly two exceptions that are **camelCase**:
`joinPaths` and `accessPolicies`.

```yaml
module:
  join_paths:      # ✗ wrong, fails validation today
  joinPaths:       # ✓ correct
```

(These two are camelCase; snake_case for them fails validation. Any change will
appear on the code reference page first.)

`icon_name` is a snake_case key whose **value** is kebab-case (e.g. `bar-chart`).

The JSON Schema lives at `https://api.steep.app/v1/code/schema` (all), with one
per file type at `/v1/code/schema/module` and `/v1/code/schema/targets`.

## Module

| Field | Required | Notes |
| --- | --- | --- |
| `identifier` | yes | Stable handle, unique across all files. Convention is `schema.table`, but it's a free string. Steep reconciles modules by `identifier` **or** by `(schema, table)`. |
| `schema` | yes | Physical DB schema/dataset. |
| `table` | yes | Physical table/view. **One module per `(schema, table)`**, two modules on one table fails the whole sync. |
| `label` | no | Display name. |
| `description` | no | Short grain explanation. |
| `synonyms` | no | List of strings. Other names people use for the data in this module, for example `users` for a customers table. AI agents see them with every metric built on this module, so don't repeat them on each metric. |
| `agent_instructions` | no | String. Guidance for AI agents that applies to every metric built on this module, for example how the data is collected or when it's complete. Put guidance for one metric or dimension on that metric or dimension instead. |
| `dimensions` | no | List of [Dimension](#dimension). |
| `metrics` | no | List of [Metric](#metric). |
| `joinPaths` | no | List of [Join path](#join-path) (camelCase). |
| `accessPolicies` | no | Row-level security. See [Access policy](#access-policy): preserve it, do not author it. |
| `entities` | no | List of [Entity](#entity). |

`identifier` is the stable Steep handle; `table` is the physical warehouse table.
Never assume they're equal, copy physical names from dbt docs / SQL / warehouse.

## Dimension

A user-facing column to filter or break metrics down by.

| Field | Required | Notes |
| --- | --- | --- |
| `column` | yes | DB column name. |
| `identifier` | no | Stable handle, unique within the module. Generated from `column` when omitted. |
| `label` | no | Display label. |
| `description` | no | Copy dbt column docs when available. |
| `type` | yes | One of: `categorical`, `city`, `country`, `h3-cell-index`, `time`. |
| `synonyms` | no | List of strings. Other names people use for this dimension, for example `market` for a country dimension. |
| `agent_instructions` | no | String. Guidance for AI agents on using this dimension, for example when to use another dimension instead. |

Do **not** expose IDs, surrogate/foreign/join keys, PII, lat/long, or free-text
as dimensions.

## Metric

Common fields (every metric):

| Field | Required | Notes |
| --- | --- | --- |
| `identifier` | yes | Unique across the workspace. Spaces become underscores. |
| `name` | yes | Business-readable label. |
| `description` | no | Always write one, in Markdown, explaining the logic. See [Metric description](#metric-description). |
| `synonyms` | no | List of strings. Other names people use for this metric, such as abbreviations or terms in other languages, for example `sales` or `turnover` for revenue. |
| `agent_instructions` | no | String. Guidance for AI agents on using this metric, for example whether a lower number is better, how it's usually split, or when to use another metric instead. |
| `examples` | no | List of strings. Questions this metric answers, phrased the way people ask them. Metrics only, `derived-ratio` included. |
| `dimensions` | no | List of column-path strings: `column`, `table.column`, or `schema.table.column`. Two wildcards exist: `this.*` adds every dimension declared on this module, `schema.table.*` every dimension of a joined code module. Prefer an explicit list; a wildcard also picks up dimensions added to that module later. |
| `time` | yes\* | A `table.column` string. Required for every type **except** `derived-ratio`. |
| `category` | no | One category (folder) in Steep. **Omitting it clears an existing category on the next sync**. |
| `owner_emails` | no | Must match workspace member emails, or they're dropped with a warning. |
| `is_private` | no | Default `false`. |
| `is_unlisted` | no | Default `false`. |
| `time_grains` | no | Subset of `daily`, `weekly`, `monthly`, `quarterly`, `yearly`. Don't default everything to daily. |
| `time_resampling` | no | `sum/divide` or `average/repeat`. |
| `time_aggregation` | no | Only value: `last-date`. Makes the metric a snapshot (point in time) series, such as a balance or a headcount, instead of a standard aggregate over time. Not on `derived-ratio`. |
| `cohorts_only` | no | Boolean. Restricts the metric to cohort analysis and disables the other visualizations. Only meaningful with a `cohort`. Not on `derived-ratio`. |
| `filters` | no | List of [Filter](#filter). **Omitting the block clears existing filters on the next sync.** |
| `slices` | no | List of [Slice](#slice). Not allowed on `derived-ratio` metrics (see below). **Omitting the block deletes stored slices on the next sync** (blocked with a whole-sync failure if a derived metric still references one). |
| `cohort` | no | A [Cohort](#cohort) object. Never on `derived-ratio`. For which other types accept one, check the canonical page's "Applies to" column. |

**Omission semantics (code is the source of truth):** for a code-defined metric,
omitted optional fields reset on the next sync rather than staying as they were:
`filters` clear, `slices` are deleted, `category` clears (simple metrics),
`time_grains` returns to all grains, `is_unlisted` returns to false. Never
"clean up" a YAML file by deleting fields you mean to keep.

### Metric description

Write it in Markdown as a block scalar (`|`). Explain the logic so a business
user can trust the number, using what the YAML and the data actually do:

```yaml
description: |
  **Online revenue**, in EUR excluding VAT.

  **Logic**
  - Sums `amount_eur` per order line.
  - Leaves out cancelled orders and gift card lines.
  - Returns are subtracted on the date of the return.

  **Use it for** online revenue. For all channels use *Total revenue*.
```

- First line: what it measures, unit and currency.
- **Logic**: the column or SQL, every filter, what is excluded and why, how
  time is assigned. For ratios: numerator and denominator.
- **Use it for**: when to pick it, and which metric to use instead.
- Only state logic you can see in the YAML or verified data. Never invent it.

### Metric `type`

Set the metric kind with **`type:`**, not `calculation:`. The legacy
`calculation:` field still parses but emits a warning, and **`derived-ratio` is
impossible via `calculation`**. Always write `type`.

| `type` | Extra required fields | Optional |
| --- | --- | --- |
| `sum` | `value: table.column` | - |
| `count` | *(only `time`)* | - |
| `count-distinct` | `distinct_on: table.column` | - |
| `ratio` | `numerator`, `denominator` | `format` |
| `custom-value` | `sql_expression` | - |
| `custom-ratio` | `numerator_sql`, `denominator_sql` | `format` |
| `derived-ratio` | `numerator`, `denominator` each reference another metric (identifier string, or `{ metric, slice }`); no `time`, `slices`, `cohort`, `cohorts_only` or `time_aggregation`; no module binding | `format` |

`format` is `number` or `percentage` (default `percentage`). Set it explicitly
on every ratio so the display never surprises you.

**Display fields (every metric type):**

| Field | Notes |
| --- | --- |
| `format` | `number` or `percentage`. Ratios default to `percentage`, other types to `number`. |
| `currency` | ISO 4217 code (`USD`, `SEK`, `EUR`). Shows the value as money. Set it on every money metric. |
| `unit` | Short label, max 3 characters (`ms`, `kg`, `pcs`). Plain numbers only; never use it for money. |
| `decimals` | 0 to 6. Omit to let the format and workspace locale decide. |

A money ratio (AOV, revenue per customer) needs `format: number` **and**
`currency`, or it shows as a percentage. Take the currency from the column
name or docs (`amount_eur`, `amount_usd`); if unclear, ask.

```yaml
- identifier: average_order_value
  type: derived-ratio
  numerator: revenue
  denominator: order_volume
  format: number
  currency: EUR
  decimals: 0
```

**Referencing operands:** `numerator` and `denominator` each point at another
metric one of two ways: a metric **identifier string** (the whole metric), or an
object `{ metric, slice }` that references a **specific slice** of that metric.
`metric` is the metric's identifier; `slice` is the **slice's identifier** (not
its display name) as defined on that metric; omit `slice` for the whole metric.
This lets you build ratios like "US orders per active customer" without a
separate sliced metric.

**A derived-ratio cannot define its own `slices:` block.** Slices belong on the
operand metrics; the derived ratio reaches them through `{ metric, slice }`.
Adding `slices:` to a `derived-ratio` fails validation.

**Derived-ratio gotcha:** its `dimensions` must be a subset of the **numerator
metric's** dimensions, and any extras are dropped **silently** (no warning). If
you add a dimension to both the numerator and the derived ratio in the *same*
sync, the derived ratio won't pick it up until the *next* sync. See
`debugging.md`.

## Filter

Used in `metric.filters[]` and inside a slice's `filter`.

| Field | Required | Notes |
| --- | --- | --- |
| `column` | yes | |
| `operator` | yes | See list below. |
| `expression` | yes | The value(s). |
| `schema` | no | Defaults to the module's schema. |
| `table` | no | Defaults to the module's table. |

Operators: `equals`, `not-equals`, `less-than`, `less-than-or-equal`,
`greater-than`, `greater-than-or-equal`, `in`, `not-in`, `is`, `is-not`, `like`,
`not-like`.

For `in` / `not-in`, `expression` is a comma-separated string with no spaces:

```yaml
filters:
  - column: risk_flag
    operator: in
    expression: high_risk,suspicious,aml_review
```

Only use values you've verified (dbt accepted-values, seeds, docs, or the
warehouse). Don't invent enum values.

## Slice

A named, pre-filtered cut of a metric. Lives on `metric.slices[]`; scoped to its
metric. Not allowed on `derived-ratio` metrics.

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Display name. |
| `identifier` | no | Stable handle, unique **within the metric** (not the workspace). If omitted, one is generated from `name` (snake_case, numeric suffix on collision) and the sync logs a warning. **Always write it explicitly**: it is what derived ratios reference, and duplicate slice identifiers within a metric abort the whole sync. |
| `filter` | yes | A [Filter](#filter) object. |

```yaml
slices:
  - name: US
    identifier: us
    filter:
      column: country
      operator: equals
      expression: US
```

> To reference a slice **inside a derived-ratio**, use the `{ metric, slice }`
> form on its `numerator` / `denominator`, where `slice` is the slice's
> `identifier` (see the derived-ratio section above).

## Cohort

On `metric.cohort` (a single object, not a list). A cohort groups the metric's
rows by a start date (signup date, first order) and tracks the value over the
periods that follow.

| Field | Required | Notes |
| --- | --- | --- |
| `time_dimension` | yes | The cohort's start-date column. **Must resolve to a dimension of type `time` that is declared on the module.** |
| `label` | no | Display name of the cohort. |
| `calculate_retention` | no | **Boolean.** Show values as a percentage of the cohort's initial value. |
| `time_grains` | no | Subset of `daily`, `weekly`, `monthly`, `quarterly`, `yearly`. |
| `delta_time_calculation_type` | no | `calendar-periods` (default) or `rolling-periods`. Only these two. |

```yaml
metrics:
  - identifier: transactions
    name: Transactions
    type: count
    time: transactions.created_at
    cohort:
      time_dimension: created_at
      label: Created at
      delta_time_calculation_type: calendar-periods
```

Two rules to check before authoring a cohort:

- **A `derived-ratio` metric can never carry a cohort.** The field is not part of
  its schema, and syncing one clears any cohort left behind from when the metric
  was a simple metric.
- **A dimension used by a cohort cannot be removed.** Deleting it from the module
  while a cohort still points at it produces a warning and Steep keeps the
  dimension rather than dropping it. Remove the cohort first.

Note: write `calculate_retention` as a boolean (`true` / `false`), not as a
quoted string.

## Join path

On `module.joinPaths[]` (camelCase). Declare each path once; Steep can use it
from both sides.

| Field | Required | Notes |
| --- | --- | --- |
| `from.column` | yes | A column on this module's table. |
| `to.table` | yes | Real physical table. |
| `to.column` | yes | Real physical column. |
| `to.schema` | no | Defaults to the module's schema. |
| `type` | yes | **`one-to-one` or `one-to-many` only.** `many-to-one` is rejected. |

Declare from the "one" side: a dimension/lookup table to a fact table is
`one-to-many`. If cardinality is unclear, omit the path until confirmed.

```yaml
# in the customers module (the "one" side)
joinPaths:
  - from:
      column: id
    to:
      schema: steep
      table: fct_transactions
      column: customer_id
    type: one-to-many
```

## Access policy

A module may contain an `accessPolicies:` block. This is **row-level security**:
it controls which rows each person is allowed to see.

Fields per policy: `column` (required), `attribute` (required, `user.email` or
`user.<attribute>`), and `schema`/`table` (optional, for a column on a joined
table). **Do not write, change, or remove it as part of other work.** Deleting
the block deletes the protection on the next sync. When the user asks for
row-level security, follow `references/row-level-security.md`.

## Entity

On `module.entities[]`.

| Field | Required | Notes |
| --- | --- | --- |
| `identifier` | yes | Workspace-unique (across all datasources). |
| `name` | yes | |
| `primary_key` | yes | A column on the module's table. |
| `icon_name` | no | kebab-case (e.g. `bar-chart`); an unknown value warns and renders the default icon. |
| `properties` | yes | **Non-empty.** An entity with no properties is skipped with an error. To remove an entity, delete its whole block. |
| `metrics` | no | Metric identifiers shown on the entity page. **Always fill it**: every metric on this table or joinable to it. Keep it in sync when metrics change. |
| `custom_links` | no | List of custom links. |
| `synonyms` | no | List of strings. Other names people use for this entity, for example `account` or `client` for a customer. |
| `agent_instructions` | no | String. Guidance for AI agents on using this entity, for example how to read its properties. |

EntityProperty: `column` (req), `name` (req), `type` (req: one of `string`,
`number`, `boolean`, `uuid`, `time`, `date`, `geography`), `icon_name` (opt,
kebab-case).

EntityCustomLink: `name` (req), `url_template` (req, with `{column}`
placeholders).

## Targets

`targets:` is a **root key**, not something nested in a module. It tells Steep
which table to read target values from; the table itself must follow Steep's
targets table format below (help center `/using-steep/targets`; the original
format is unsupported since 2026-10-01).

| Field | Required | Notes |
| --- | --- | --- |
| `schema` | yes | Physical schema holding the targets table. |
| `table` | yes | Physical targets table. |

```yaml
# targets.yaml, its own dedicated file
targets:
  schema: steep_demo
  table: targets
```

Two constraints:

- **One targets definition per workspace.** A second one anywhere in the repo
  aborts the whole sync before anything is written (see `debugging.md`).
- **Keep it in its own file.** Steep identifies the file by its `targets:` root,
  so it cannot share a file with a `module:`.

### Targets table format

One row per series, metric, period and dimension combination:

| series | metric | time | country | value | numerator | denominator |
|---|---|---|---|---|---|---|
| Budget 2025 | new_users | 2025-01-01 | null | 1000 | null | null |
| Budget 2025 | new_users | 2025-01-01 | US | 500 | null | null |
| Budget 2025 | activation_rate | 2025-01-01 | US | null | 10 | 100 |

- `series`: target name users switch between ("Budget", "Stretch").
- `metric`: the metric **identifier**, exactly.
- `time`: period start date; Steep infers the grain from the gap between the first two dates.
- Dimension columns: optional, named exactly like the dimension's database column.
  Add every combination you want to aggregate (null = all values).
- `value` for normal metrics; **ratio metrics need `numerator` and `denominator`** instead.
- Columns starting with `_` are ignored.
- With row-level security, the table must include the policy column, or members
  with a policy see no targets.
- Cached 4 hours.

Defining no targets file at all is fine: it produces no candidates and no error,
and a UI-managed targets table is not deleted just because code does not define
one.

## AI context

Modules, dimensions, entities and metrics accept `synonyms` (list of strings) and
`agent_instructions` (string). Metrics also accept `examples` (list of example
questions). Steep AI and the Steep MCP server read them. Fill them for every
metric you generate: synonyms are the words users actually say (abbreviations,
other languages), agent_instructions say when to use or avoid the item.

```yaml
- identifier: net_revenue
  name: Net revenue
  synonyms: [NR, revenue after refunds]
  agent_instructions: Use for revenue questions unless the user asks for gross.
  examples: [What was net revenue last month by country?]
```

## Offline check

Steep's validate endpoint and dry run (SKILL.md, Build step 4) are the real
check. Only when the API is unreachable, check every file by hand: one root per
file (`module:` or `targets:`, at most one `targets:` in the repo); no unknown
keys; required fields present; identifiers unique; join paths `one-to-one` or
`one-to-many`; no empty or unparseable `.yaml` anywhere in the repo; casing as
above. Confirm every schema, table and column from dbt or warehouse metadata.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
