# Debugging the Steep semantic model YAML

How to diagnose and fix a sync problem. You cannot fetch the sync log (only a
sync's completed or failed state by id, see `capabilities-and-limits.md`), so
you work from the YAML, the validate and dry run calls (SKILL.md, Build step
4), a log the user pastes, and the read-only MCP.

## Contents

- [What happens during a sync](#what-happens-during-a-sync)
- [The 4-tier diagnostic model](#the-4-tier-diagnostic-model)
- [Procedure](#procedure)
- [Message index](#message-index)
- [Message catalogue](#message-catalogue): [Global](#global) ·
  [Module](#module) · [Join path](#join-path) · [Dimension](#dimension) ·
  [Metric](#metric) · [Slices](#slices) · [Derived-ratio](#derived-ratio) ·
  [Entity](#entity) · [Cohort](#cohort) · [Targets](#targets) ·
  [Access policy](#access-policy) · [Pre-engine YAML](#pre-engine-yaml)

## What happens during a sync

1. **Read every YAML file.** Steep reads **every `.yaml`/`.yml` file in the
   connected repo** (not just `modules/`) at the pushed commit.
2. **Check each file.**
   A file that does not parse or is not a YAML mapping (empty, comments only)
   **fails the whole sync**, even if it has nothing to do with Steep: keep the
   repo's YAML clean, or use a dedicated repo. A mapping with **no recognized
   root** (`module:` or `targets:`) is silently skipped. A recognized file is
   checked against the strict schema. Any failure here is Unprocessable.
3. **Process definitions in dependency order:** modules, join paths,
   dimensions, metrics (including derived-ratio), entities, access policies. A
   dimension that points at a module that failed will itself fail with a
   reference error, so in a cascade of failures trace back to the earliest one.
4. **Remove what code no longer defines.** Definitions that are gone from the
   YAML are deleted, unless an error protected them (see tier **error**) or
   the safety net in `remove.md` converts them to app-defined.
5. **Apply or roll back.** With no fatal problem, everything applies at once.
   Any fatal problem rolls back the whole sync and nothing changes.

## The 4-tier diagnostic model

Every problem falls into one tier, and the tier tells you the blast radius.
Catalogue entries use the letters.

- **U, Unprocessable.** Caught before processing: YAML syntax, schema
  validation, duplicate module identifiers, two modules on one `schema.table`,
  more than one `targets:`. **Nothing lands**, even from valid files, and there
  is no per-item log.
- **F, fatal.** A contradiction across definitions: duplicate metric or entity
  identifiers, duplicate slice identifiers in one metric, an ambiguous module
  match. **The whole sync rolls back.** The log lists every fatal problem; fix
  all of them.
- **E, error.** A problem in one definition. It is **skipped and its existing
  row is shielded from deletion**, so the old version stays live until the fix
  lands. The rest of the sync completes. Shown under `errors`.
- **W, warning.** Processed, possibly with an adjustment. Shown under
  `warnings`.

A **failed** sync's log records intent, not effect: `removed` there was planned,
never applied. Items made in the Steep app are called
app-defined in this skill; the sync log prints them as "UI-defined".

## Procedure

Work in order; stop when you find the cause.

1. **Diff the last change** on the connected branch; the cause is almost
   always in it. Ask for dbt models or a warehouse schema listing whenever
   physical names are involved.
2. **Did a sync run?** Did the change land on the connected branch, and is
   Steep pointed at it? See `capabilities-and-limits.md`, Sync triggers.
3. **Predict.** Run validate, then the dry run on the branch's files (SKILL.md,
   Build step 4). Check every file's root key: one that is neither `module:`
   nor `targets:` is skipped with no error.
4. **Match the exact message.** Ask the user to paste the sync result from the
   Steep UI (sync history) and find its distinctive words in the
   [Message index](#message-index) (templates are verbatim, with
   `<placeholders>`).
5. **Check the silent cases** when there is no message:
   - An **error** kept a stale old row while you think you changed it.
   - Something removed was **converted to app-defined** (`remove.md`).
   - A **removed field cleared**: omitting `filters:` clears filters, omitting
     `category` clears the category (simple metrics), omitting `slices:`
     deletes stored slices (a fatal if a derived metric still references one).
     "Why did my filter vanish?" is often an omission.
6. **Fix, land on the connected branch, verify** with the read-only MCP
   (`list_modules`, `list_metrics`, `search_metrics`, `list_entities`,
   `get_metric`, `query_metric`). A mismatch nothing above explains, or a
   Steep-side bug, goes to `handoff-report.md`.

## Message index

| The message contains... | Go to |
| --- | --- |
| `Errors were found when parsing the Semantic Layer Definition:` | The failed-sync wrapper. Read what follows it: file/path messages mean pre-engine (U, no per-item log); a `; `-joined list means engine-level fatal (F, the log shows what was *attempted*, none of it applied). |
| `Invalid YAML structure` or a YAML parse error naming a file | [Pre-engine YAML](#pre-engine-yaml) |
| `Unrecognized key: "<key>"` | [Pre-engine YAML](#pre-engine-yaml) |
| `Module identifier "<id>" is duplicated` | [Module](#module) |
| `are referencing table` | [Module](#module) |
| `matches more than one existing module` / `is claimed by more than one` | [Module](#module) |
| `Metric identifier "<id>" is duplicated` | [Metric](#metric) |
| `'calculation' is provided but ignored` | [Metric](#metric) |
| `Slice identifier "<id>" is duplicated in metric` | [Slices](#slices) |
| `has no identifier; one will be generated` | [Slices](#slices) |
| `cannot be deleted because it is used in derived metric` | [Slices](#slices) |
| `Derived metric '<id>': referenced ... not found` / `slice '<slice>' not found on` | [Derived-ratio](#derived-ratio) |
| `was converted to UI-defined` | [Global](#global) |
| `Dimension '<col>' is not defined in module` | [Metric](#metric) |
| `Cannot remove dimension` | [Dimension](#dimension) |
| `Invalid cohort dimension reference` | [Cohort](#cohort) |
| `Multiple targets defined` | [Targets](#targets) |
| `Entity ...` | [Entity](#entity) |
| `No viable metrics were found` | [Global](#global) |

## Message catalogue

### Global

| Message (as shown) | Tier | Meaning & fix |
| --- | --- | --- |
| `No viable metrics were found. Please define at least one metric in your code definition.` | fail | The sync found zero usable metrics; nothing is deleted. Ensure at least one valid metric; if all metrics failed to parse, fix those first. |
| `Errors were found when parsing the Semantic Layer Definition: ...` | U or F | The failed-sync wrapper. Multiple problems are joined by `; `. File-level failures (U) have no per-item log; engine-level failures (F) attach a partial log of what was attempted before rollback. Fix every listed problem, then re-sync. |
| `Module '<id>' was converted to UI-defined because <reason>` (reasons: *it has metrics referencing it* / *it has entities referencing it* / *it is used as a target table in Settings → Targets*) | W | Expected when you remove a module that still has dependents; it becomes app-defined, not deleted. To fully delete, remove the dependents first. See `remove.md`. |

### Module

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Module identifier "<id>" is duplicated. First defined in <file>, also found in <files>. Module identifiers must be unique.` | U | Two files use the same module `identifier`. Rename one. |
| `Modules <ids> are referencing table '<schema.table>'. A table can only be referenced by one module.` | U | Two modules point at one physical table. Keep exactly one module per table. (Very common cause of a "broken" sync.) |
| `Module candidate '<id>' (table <s.t>) matches more than one existing module ... by identifier or table reference ...` / `Existing module '<id>' ... is claimed by more than one module candidate ...` | F | Ambiguous reconciliation, for example a module's `identifier` **and** `table` changed in the same sync, or two candidates colliding. Change only one of them per sync so each candidate maps to at most one existing module. |
| `Module '<id>': Failed to create/update/delete` | F | A write failed. Re-check the module's fields; if the YAML is valid, capture it for handoff. |

> Steep matches a module by `identifier` or by `(schema, table)`. Change only
> one of them per sync; changing both at once can lose the match, so metrics
> may be recreated or the sync may fail. Run the dry run to see which.

### Join path

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Invalid join path definition: missing from.column, to.table, to.column or type` | E | Add the missing field. All four are required. |
| `Failed to create join-path between <a> and <b>` | W | One of the two modules doesn't exist or is being removed this sync. Ensure both modules are present. |
| `Join-path between <a> and <b>: Failed to create/update/delete` | F | A write failed. Verify both columns exist and the cardinality is `one-to-one`/`one-to-many` (never `many-to-one`). |

### Dimension

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Cannot remove dimension '<module.column>': it is used in cohort settings of metric(s) '<ids>'` | W | The dimension is kept (not deleted). Remove it from those metrics' cohort settings first if you really want it gone. |
| `Dimension <id>: Failed to create/update/delete in module <m>` | F | A write failed. Check the column reference. |

### Metric

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Metric identifier "<id>" is duplicated. First defined in <file>, also found in <file>. Metric identifiers must be unique.` | F | Rename one. Duplicate identifiers roll back the whole sync. |
| `'calculation' is provided but ignored because 'type' takes priority. Remove 'calculation' from metric '<id>'.` | W | Delete the `calculation` field; keep `type`. |
| `Invalid dimension reference: ...` / `Metric <id>: Dimension '<col>' is not defined in module '<schema.table>'` | W | That dimension is dropped from the metric. Add the column to the module's `dimensions`, or fix the reference. Valid paths: `column`, `table.column`, `schema.table.column`. |
| `Star-pattern not supported for app-defined modules: <ref>` | W | A `*` dimension reference points at an app-defined module. Enumerate dimensions explicitly, or move that module to code. |
| `Invalid column path: <path>` | E | Fix the column path in the failing metric field (`value` / `numerator` / `denominator` / `time` / `distinct_on` / sql). |
| `No user found for owner email <emails>` | W | `owner_emails` must match workspace members; unmatched emails are dropped. |
| `Metric '<id>' was converted to UI-defined because it is used in derived metrics` | W | Expected on removal: a metric used by a surviving derived metric is detached, not deleted. To delete it, remove the derived metrics first. |
| `Metric <id>: Failed to create/update/delete/transform to UI-defined in module <m>` | F | A write failed. Capture the YAML for handoff if it looks valid. |

### Slices

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Slice identifier "<id>" is duplicated in metric "<metric>". Slice identifiers must be unique within a metric.` | F | Two slices on the same metric declare the same `identifier`. Rename one. This rolls back the **entire** sync, same severity as duplicate metric identifiers. (Same identifier on slices of *different* metrics is fine.) |
| `Slice "<name>" in metric "<metric>" has no identifier; one will be generated from its name. Add an explicit 'identifier' so slice references stay stable if the name changes.` | W | The slice still syncs; an identifier is generated (snake_case of the name, numeric suffix on collision). Add an explicit `identifier` so derived-ratio references never break on rename. |
| `Slice "<identifier>" cannot be deleted because it is used in derived metric "<id>"` (plural: `...used in derived metrics "<a>", "<b>"`) | F | You removed a slice that a derived metric still references. The **whole sync fails and rolls back**. Remove or update the referencing derived metric first, or do both changes in the same sync. |

How slices are matched across syncs (so references survive): by `identifier`
first, then by name (only if the name matches exactly one existing slice), then
by identical filter content (only if unique). A match patches the slice in
place. Changing an identifier-less slice's **name and filter together** orphans
it: it is deleted and recreated with a new generated identifier, and anything
referencing it breaks or fails the sync.

### Derived-ratio

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Derived metric '<id>': referenced numerator metric '<ref>' not found` | E | The referenced base metric must exist and sync successfully in the **same** run. Fix the identifier or the base metric. The derived metric is skipped; an existing row is kept untouched. |
| `Derived metric '<id>': referenced denominator metric '<ref>' not found` | E | Same as above, for the denominator. |
| `Derived metric '<id>': slice '<slice>' not found on numerator metric '<ref>'` | E | The `slice` in `{ metric, slice }` must be a slice **identifier** defined on that metric (not the slice's display name). Check the operand metric's `slices:` block. |
| `Derived metric '<id>': slice '<slice>' not found on denominator metric '<ref>'` | E | Same as above, for the denominator. |
| *(no message, silent)* | - | A derived ratio's `dimensions` are intersected with the **numerator's current dimensions**; extras are dropped silently. A dimension added to both numerator and derived ratio in the same sync only reaches the derived ratio on the **next** sync. This is the usual reason "a breakdown disappeared from my derived metric." |

Also: `slices:` (or `time:`) declared **on** a derived-ratio metric fails
validation before the engine runs; see [Pre-engine YAML](#pre-engine-yaml).
Converting a metric between `custom-ratio` and `derived-ratio` under the same
identifier is safe: it patches in place, nothing downstream breaks.

### Entity

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Entity identifier "<id>" is duplicated...` | F | Make entity identifiers unique. |
| `Entity "<id>" has no properties defined; skipping. To remove this entity, delete its entire block from the module YAML.` | E | Add at least one property, or delete the whole entity block to remove it. |
| `Entity "<id>" uses icon "<x>" which is not a supported icon name (icon names are kebab-case, e.g. "bar-chart")` (also per property) | W | Use a supported kebab-case icon name. |
| `Entity "<id>" declares property column "<col>" more than once.` | E | Remove the duplicate property. |
| `Entity identifier "<id>" is already used by an entity in another datasource in this workspace.` | E | Entity identifiers are workspace-unique across datasources. Pick a different one. |
| `Entity <id> references metric "<m>" which doesn't exist in the workspace` | W | The unresolved metric is dropped from the entity's links. Fix the identifier or ensure the metric synced. |
| `Entity <id>: Failed to create/update/delete...` | F | A write failed. |

Not from the sync (these come from the Steep app/API, not the sync log):
`Entity identifier already exists` (a 400 when creating/renaming an entity in
the UI to a taken identifier) and `Unknown filter property: <id>` (a 400 on an
entity query whose filter doesn't match a property on the entity definition).
If the user pastes one of these, they were using the app, not syncing code.

### Cohort

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Invalid cohort dimension reference: <ref>` | E | `cohort.time_dimension` doesn't resolve. It must point at a dimension **declared on the module** whose `type` is `time`. The metric is skipped and its existing row is protected. |
| `Cannot remove dimension '<module.column>': it is used in cohort settings of metric(s) '<ids>'` | W | See [Dimension](#dimension). The dimension is kept, not deleted. Remove the cohort first. |

Two cohort rules that produce confusion rather than a message:

- A **`derived-ratio` metric cannot carry a cohort.** `cohort` isn't in its
  schema, so putting one there is a pre-engine `Unrecognized key` failure. And if
  a metric that *had* a cohort is changed into a derived-ratio, the cohort is
  cleared.
- Cohort problems are **errors, not warnings**, so a bad cohort silently keeps
  the old version of that metric live while the rest of the sync completes.

### Targets

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `Multiple targets defined: <sources>. A workspace can only have one target.` | U | Two or more files declare a `targets:` root. A workspace gets exactly one. Delete all but the intended file. This aborts the sync before anything is written. |

Defining **no** targets file is not an error: it produces no candidates, and a
UI-managed targets table is not deleted just because code doesn't define one.

### Access policy

Any message mentioning an **access policy** concerns **row-level security**, who
is allowed to see which rows.

Treat these as security items, not YAML hygiene, and do not attempt to fix them
by editing or removing the policy. A message saying a policy was skipped means
the protection was **not applied**, even if the sync itself completed. Report it
to the user in those terms, and escalate via `handoff-report.md` so Steep can
confirm what is actually enforced before anyone relies on it.

### Pre-engine YAML

| Message | Tier | Meaning & fix |
| --- | --- | --- |
| `<path>: Invalid YAML structure` or a YAML parse error naming a file (`bad indentation of a mapping entry at line N`) | U | Fix that file. **Important: Steep reads every `.yaml`/`.yml` in the connected repo.** A broken, empty, or non-mapping YAML file *anywhere* in the repo fails the whole sync, even if it has nothing to do with Steep. Keep the connected repo's YAML clean, or use a dedicated repo. |
| `<file>: (root): Unrecognized key: "<key>"` | U | The file has a recognized `module:` root plus a stray extra root, usually a misindented block that slid to column 0. Re-indent it back inside the module. |
| `<file>: module.metrics.<i>: Unrecognized key: "<key>"` (and similar `<path>: <message>` entries) | U | A field is somewhere the schema doesn't allow it. The path pinpoints the file and item; common cases: `slices` or `time` on a `derived-ratio` metric, a typo'd field name, metric-level fields at module root. Match `yaml-schema.md`. |

Validation messages have the shape `<path>: <message>`, comma-joined when one
file has several issues, and are wrapped in the
`Errors were found when parsing the Semantic Layer Definition:` prefix. Any one
invalid file fails the **whole** sync (all files), with no per-item log.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
