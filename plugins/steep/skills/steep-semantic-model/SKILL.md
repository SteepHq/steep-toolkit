---
name: steep-semantic-model
description: >-
  Build, debug, safely remove, or hand off a Steep semantic model written as
  YAML and synced from GitHub: modules, dimensions, metrics, join paths,
  slices, filters, cohorts, entities, targets and row-level security. Use it
  when authoring, reviewing, migrating or removing Steep YAML, even if the user
  never says "code" or "YAML". Triggers: editing `modules/*.yaml`, a sync that
  failed or did something unexpected ("code in Steep doesn't match my repo", a
  metric that disappeared, a join path conflict, "module already exists"),
  renaming or deleting modules or metrics, moving definitions between code and
  the Steep UI, the Steep GitHub integration, generating a semantic layer from
  dbt models, or a report for the Steep team. Not for reading reports or
  interpreting a metric. Wrong definitions silently break live dashboards, so
  consult this skill before editing Steep YAML.
---

# Steep semantic model

Steep is a metrics / semantic-layer product. The semantic model can be written as
YAML (the **Code** page in Steep) in a GitHub repo; Steep reads the configured repo and branch and
syncs those definitions into the workspace.

You are the agent doing the work. This file is your operating procedure.

## Authority and freshness

**Canonical schema:** <https://help.steep.app/setup-and-manage/code-reference>

- That page is the source of truth for **the YAML contract**: which root keys
  and fields exist, which are required, and their allowed values.
- **Fetch it when correctness matters**: before authoring an unfamiliar
  construct, when a field is rejected, or when this skill and the page disagree.
  On any conflict about the contract, **the page wins over this skill.**
- `references/yaml-schema.md` is a local mirror, checked against the page on
  2026-11-02, for speed and for agents without network access. Treat it as a
  cache that may lag, not as authority. The page changes slowly; fetching it
  once per session is enough.
- This skill additionally encodes **sync and reconciliation behavior** (how
  definitions are matched, what warnings/errors/fatals mean, what deletion does)
  that the page does not document. That part is this skill's unique value; the
  page does not override it.

Related pages: `/setup-and-manage/define-in-code` (GitHub connection, sync),
`/setup-and-manage/app-to-code-migration-guide`, `/using-steep/targets`,
`/setup-and-manage/row-level-security`.

## Route by intent

| Intent | Read | Mode |
| --- | --- | --- |
| Author or edit definitions | `references/yaml-schema.md`, `references/examples/` | Build |
| A sync failed, or Steep does not match the repo | `references/debugging.md`, `references/sync-behavior.md` | Debug |
| Stop managing in code, or remove a definition | `references/remove.md` | Remove |
| Escalate to Steep | `references/handoff-report.md` | Handoff |
| Decide what is possible in code vs UI, or what you can observe | `references/capabilities-and-limits.md` | any |

Read the reference before acting. It carries exact field names, enums, verbatim
sync messages, and fixes.

## Invariants

Violating any of these is what actually breaks customer workspaces. Check them
before you write or diagnose. When one is in play, name it explicitly in your
answer; naming the rule is usually most of the fix.

1. **One physical table, exactly one module.** Two modules on the same
   `schema.table` fail the whole sync before anything is written.

2. **A module is matched by `identifier` OR by `(schema, table)`.** Changing
   `identifier` while `table` stays the same is a patch in place; metrics,
   dimensions, joins, reports, and targets survive. Changing **both in one
   commit** makes the match ambiguous and aborts the sync. Change one anchor per
   sync.

3. **Identifiers are the stable handle.** Duplicate metric or entity identifiers
   anywhere in the repo are fatal and roll back the entire sync; duplicate slice
   identifiers within one metric do the same. Renaming an identifier can
   recreate the object and detach reports and targets. Treat identifier changes
   as high risk.

4. **Two root keys exist: `module:` and `targets:`.** Everything else nests
   inside `module:`. `targets:` needs its own file and is limited to one per
   workspace. A file whose root is neither is **skipped silently, with no
   error**, so its definitions never appear. Check root keys first when
   definitions "did not show up". A recognized root plus a stray second root
   fails loudly instead.

5. **Set metric kind with `type:`, never `calculation:`.** `calculation:` is
   legacy, warns, and cannot express `derived-ratio`. Write `type:` on every
   metric you create or edit. Do not rewrite the other existing metrics from
   `calculation:` to `type:` unless asked; a sweep across metrics the user did
   not mention is a change they did not ask for.

6. **Join paths are `one-to-one` or `one-to-many`.** `many-to-one` is rejected.
   Declare from the "one" side, usually dimension to fact as `one-to-many`.

7. **Omission deletes.** Code is the source of truth: dropping a `filters:`
   block, a `category`, or `slices:` clears them on the next sync. Never remove
   a field you intend to keep.

8. **Errors protect, they do not destroy.** A broken definition is skipped and
   its existing row is shielded from deletion. The rest of the sync completes.

9. **Removing a definition from code deletes it in Steep.** Two narrow safety
   nets exist, never a plan: a metric a surviving derived metric
   still uses, and a module that still has a surviving metric, entity, or
   Targets table on it, are converted to app-defined with a warning instead.
   A push with zero valid metrics is refused outright, so nothing changes; to
   remove nearly everything, keep one module with one metric.

10. **Any push to the connected branch syncs.** Merging a PR counts, because a
    merge is a push. There is no draft state.

11. **`accessPolicies:` is row-level security. Write or change it only when
    the user asks, never as a side effect.** Because omission deletes, dropping
    the block removes the protection silently. Follow
    `references/row-level-security.md`, and never claim a policy works until
    the user has tested it as a member. **Any added, changed or removed
    policy line triggers the row-level security warning** in that file: stop,
    show it, and get an explicit yes before committing or pushing. Steep's
    validate and dry run do not report policy changes, so this warning is the
    only safeguard.

## Build

1. Inspect before asking. Read existing `*.yaml`, dbt models (`schema.yml`,
   model SQL, `sources.yml`), and warehouse metadata if reachable. Never invent
   physical table or column names.
2. Ask only for business context that changes the output: the questions the
   metrics must answer, definitions with edge cases, default breakdowns, the
   time column and grains, and columns that must not be exposed.
3. Generate YAML per `references/yaml-schema.md`, fetching the canonical page
   for anything unfamiliar. One module per file. snake_case except `joinPaths`
   and `accessPolicies`. Do not add dimensions on IDs, join keys, or personal
   data such as email without asking; which columns members may filter by is
   the user's call. Keep dimensions that already exist in the YAML and flag
   them instead of removing them (omission deletes). List a metric's
   dimensions explicitly; `this.*` is accepted but exposes every dimension on
   the module, including ones added later.
   Every time you add or change metrics, also keep these up to date:
   - **Entity metrics.** Each entity's `metrics:` list holds the metrics
     calculated on its table or reachable from it through a join path. When you
     add a metric, add it to every entity it belongs to; when you remove or
     rename one, update the lists.
   - **Display.** `currency` on money metrics, `unit` on measured values,
     `decimals` where it helps; money ratios also need `format: number`
     (see `yaml-schema.md`, Display fields).
   - **Descriptions.** Markdown, explaining the logic behind the metric (format
     in `yaml-schema.md`, Metric description).
   - **AI context.** `synonyms`, `agent_instructions` and `examples` on every
     metric (see `yaml-schema.md`, AI context). Business rules ("plain sales
     means net sales", "gift cards are not sales") go in `agent_instructions`.
   - **Repo README.** If the repo has one, update its metric guide (which
     metric answers which question, conventions, open points).
4. **Right after generating, run both checks. This is mandatory.** Do not
   report the work as done, commit, or push until validate returns
   `valid: true` and the dry run shows no errors and no unexpected removals.
   If you cannot run one (no network, no API key), say so plainly and name
   which check is missing. Check with Steep's own engine, in two steps. Both take the same
   `files` list: every Steep YAML file in the repo, not only the changed ones,
   each as `{ "path": "<path from repo root>", "content": "<file text>" }`
   (forward slashes, `.yml` or `.yaml`, each path once, 10 MB total).

   a. **While editing, validate (fast, no key, touches nothing).**
      `POST https://api.steep.app/v1/code/validate` with `{ "files": [...] }`.
      It returns `{ "valid": true|false, "problems": [...] }`; each problem has
      a `severity`, a `message` and the file it is in. It checks structure and
      cross references. Run it after every change and fix every problem until
      `valid` is true. Put
      `# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`
      on top of each file so editors flag mistakes as you type; the same URL
      returns the full schema when you need the exact fields.

   b. **Before merging, dry-run (slower, needs an API key).**
      `POST /v1/code/syncs` with
      `{ "datasourceId": "<id>", "dryRun": true, "files": [...] }`.
      Always send `"dryRun": true`. It shows the exact changes the sync would
      make: identifiers to be created, updated, removed and left unchanged,
      plus errors and warnings; `outcome: failed` comes with the reason.
      Anything in **removed** that the user did not ask to delete is a
      mistake: stop and fix it. Ask the user for the datasource ID and to set
      `STEEP_API_KEY` themselves; never write a key into a file or the chat.
      The datasource ID is the last part of the URL when they open Settings,
      Data Source, and click edit on their data source; if they cannot find it,
      Steep support sends it on request. The API key is under Settings, API.

   Neither step can tell you a column holds the right data, so still confirm
   tables and columns from dbt or warehouse metadata. If the API is
   unreachable, fall back to the checklist in `references/yaml-schema.md`.
5. Branch, commit, push. Report the branch, the assumptions you made, and that
   the sync happens when the change lands on the connected branch.

## Metric rules

Validate and dry run check structure only. These rules keep the numbers right.

1. Look at real rows before you use a table or column. A name does not prove
   what it holds.
2. Write what one row means in the module description.
3. Check that a key is unique before you declare a join. A wrong join counts
   rows twice, and a `sum` on the "one" side split by a "many" side dimension
   is inflated.
4. Give each concept one home table and say why you picked it.
5. For a "right now" number (stock, active subscribers, balance), set
   `time_aggregation: last-date`. Never add it up over time.
6. Count an event once. Use `count-distinct` on the event ID, not a flag that
   stays on after the event.
7. Build a rate as numerator divided by denominator (`ratio`, `custom-ratio`,
   `derived-ratio`). Never sum or average a stored rate column. Use `ELSE 0`
   in a `CASE` numerator so an empty period shows 0, not blank.
8. Use the same filters and the same date for both sides of a ratio.
9. Choose the `time` column on purpose (order date, ship date, return date)
   and write which one it is. Two dates means two metrics.
10. Never add different units or currencies together. Check nulls and negative
    values (returns) first. `not-equals` and `not-in` filters also drop nulls.
11. Before you add a filter, count what it removes and report it. Keep a filter
    only when it defines the metric (cancelled orders are not revenue) and say
    so in the description. Offer other cuts as a dimension or slice.
12. Build the numbers people decide with (rates, averages, values), tied to the
    client's questions, not only counts.
13. After the sync, compare each key metric for one closed period with a number
    the client already trusts. Write every assumption in the description and
    the README. A silent choice is a hidden bug.

## Debug

**Constraint: you cannot fetch sync logs, status, or errors.** No MCP or API
operation exposes them. Never claim you read them.

1. **Predict.** Validate the repo's files (Build step 4a), then dry-run without `files`
   (4b) to replay the linked branch: it returns the errors and warnings the
   sync would.
   Then work the symptom against `references/debugging.md`. If the user pasted a
   message, match it in the Message index; the tier gives you the blast radius.
2. **Interpret.** Ask the user to paste the sync log from the Steep UI (sync
   history) if they have not, then map its messages to the catalogue.
3. **Verify.** Use the read-only MCP (`list_modules`, `list_metrics`,
   `search_metrics`, `list_entities`, `get_metric`, `query_metric`) to compare
   what landed against what the YAML intends.

Start from the most recent change on the connected branch. Request dbt models or
a warehouse schema listing whenever physical names are involved. Keep a running
log of each attempt and its result; it becomes the handoff if you escalate.
State which leg your conclusion rests on and what you could not verify.

## Remove

Follow `references/remove.md`. Deleting YAML deletes in Steep (invariant 9).
Before merging a removal, say what will be deleted and get an explicit yes. Do not count on conversion to app-defined; it is
a safety net for two narrow cases, not a way to keep things. A push with zero
valid metrics is refused, so to remove nearly everything keep one module with
one metric. Stopping the code workflow for a whole workspace is a workspace
setting, not a YAML change: hand off to Steep rather than changing settings.

## Handoff

When the cause is on Steep's side, or the user wants Steep to take over, produce
the filled report in `references/handoff-report.md`. Fill every section
yourself. Never include credentials, tokens, or personal data.

## Safety

- Confirm before irreversible or outward-facing steps: deleting or detaching
  live assets, force-pushing, anything that triggers a production sync.
- Keep diffs surgical. One concern per sync makes the next debug tractable.
- Report honestly: state what you verified, at what level, and what you did not.
