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
YAML (the **Code** page in Steep) in a GitHub repo; Steep syncs the configured
repo and branch into the workspace. This file is your operating procedure.

## Authority and freshness

**Canonical schema:** <https://help.steep.app/setup-and-manage/code-reference>

- That page is the source of truth for **the YAML contract** (root keys,
  fields, required, allowed values). Fetch it before authoring an unfamiliar
  construct, when a field is rejected, or when this skill disagrees; once per
  session is enough. On any conflict about the contract, **the page wins.**
- `references/yaml-schema.md` is a local cache of the page that may lag.
- This skill adds **sync and reconciliation behavior** (how definitions are
  matched, what warnings/errors/fatals mean, what deletion does) that the page
  does not document.

Related pages: `/setup-and-manage/define-in-code` (GitHub connection, sync),
`/setup-and-manage/app-to-code-migration-guide`, `/using-steep/targets`,
`/setup-and-manage/row-level-security`.

## Route by intent

| Intent | Read | Mode |
| --- | --- | --- |
| Author or edit definitions | `references/yaml-schema.md`, `references/examples/` | Build |
| A sync failed, or Steep does not match the repo | `references/debugging.md` | Debug |
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
   only one of them per sync keeps the match. Changing **both at once** can lose
   the match, so metrics may be recreated or the sync may fail. Run the dry run
   (Build step 4b) to see which.

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
3. Generate YAML per `references/yaml-schema.md`. One module per file.
   snake_case except `joinPaths` and `accessPolicies`. Do not add dimensions on
   IDs, join keys, or personal data such as email without asking. Keep existing
   dimensions and flag them instead of removing them (omission deletes). List a
   metric's dimensions explicitly; `this.*` also exposes dimensions added later.
   Whenever you add or change metrics, keep these up to date:
   - **Entity metrics.** Each entity's `metrics:` list holds every metric on its
     table or reachable through a join path. Add, remove, or rename there too.
   - **Display.** `currency` on money, `unit` on measured values, `decimals`
     where it helps; money ratios also need `format: number`.
   - **Descriptions.** Markdown, explaining the logic (`yaml-schema.md`, Metric
     description).
   - **AI context.** `synonyms`, `agent_instructions` and `examples` on every
     metric. Business rules ("plain sales means net sales", "gift cards are
     not sales") go in `agent_instructions`.
   - **Repo README.** If the repo has one, update its metric guide (which
     metric answers which question, conventions, open points).
4. **Right after generating, run both checks. This is mandatory.** Do not
   report the work as done, commit, or push until validate returns
   `valid: true` and the dry run shows no errors and no unexpected removals.
   If you cannot run one, say which. Both take the same `files` list: every
   Steep YAML file in the repo, not only the changed ones, each as `{ "path": "<path from repo root>", "content":
   "<file text>" }` (forward slashes, `.yml` or `.yaml`, each path once, 10 MB
   total).

   a. **Validate, after every change (fast, no key, touches nothing).**
      `POST https://api.steep.app/v1/code/validate` with `{ "files": [...] }`.
      It returns `{ "valid": true|false, "problems": [...] }` (each with
      `severity`, `message`, file). Fix until `valid` is true. Put
      `# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`
      on top of each file so editors flag mistakes as you type; that URL also
      returns the full schema.

   b. **Dry run, before merging (needs the client's API key).**
      `POST https://api.steep.app/v1/code/syncs` with header
      `Authorization: ApiKey <key>` and body
      `{ "datasourceId": "<id>", "dryRun": true, "files": [...] }`.
      Always send `"dryRun": true`. It previews exactly what the sync would
      change (identifiers created, updated, removed, unchanged), plus errors
      and warnings. Anything in
      **removed** the user did not ask to delete is a mistake: stop and fix it.

      **API key note.** The dry run needs the client's own Steep API key and
      their datasource ID: ask for both at the start of the task, not at the
      end. The user creates the key under Settings, API, Create API key, with
      only the scopes needed and a short expiry (it is shown once and can be
      revoked there). A key reads like a workspace admin, so keep it out of
      chat, files, commits and logs: ask the user to set it as `STEEP_API_KEY`
      and send `Authorization: ApiKey $STEEP_API_KEY`. With no key, still run
      validate and tell the user plainly the dry run was skipped, so the change
      is not fully checked. The datasource ID is the last part of the URL after
      opening Settings, Data Source, and clicking edit on the data source;
      Steep support sends it on request.

   Neither check proves a column holds the right data, so confirm tables and
   columns from dbt or warehouse metadata. If the API is unreachable, use the
   offline fallback in `references/yaml-schema.md`.
5. Branch, commit, push. Report the branch, the assumptions you made, and that
   the sync happens when the change lands on the connected branch.

## Useful API calls

Base `https://api.steep.app`, header `Authorization: ApiKey $STEEP_API_KEY`.

- `/v1/modules`, `/v1/metrics`, `/v1/entities`: list what exists before
  building, so you do not create duplicates.
- `/v1/metrics/{metricId}/query`: aggregated results plus the SQL, to
  check a metric after a sync.
- `GET /v1/code/syncs/{id}`: whether a sync completed or failed.
- `/semantic-layer-syncs` is deprecated; use `/v1/code/syncs`.

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
    the client already trusts (`/v1/metrics/{metricId}/query`). Write every
    assumption in the description and the README. A silent choice is a hidden bug.

## Debug

**Constraint: you cannot fetch the sync log.** `GET /v1/code/syncs/{id}` tells
you whether a sync with a known id completed or failed; the help center lists
no way to list syncs, so the messages still come from the log the user pastes.
Never claim you read a log you did not see.

1. **Predict.** Validate the repo's files (Build step 4a), then dry run the
   branch's files (4b): it returns the errors and warnings the sync would.
2. **Interpret.** Ask the user to paste the sync log from the Steep UI (sync
   history), then match each message in `references/debugging.md`.
3. **Verify.** Use the read-only MCP (`list_modules`, `list_metrics`,
   `search_metrics`, `list_entities`, `get_metric`, `query_metric`) to compare
   what landed against what the YAML intends.

Follow the procedure in `references/debugging.md`. Keep a running log of each
attempt and its result; it becomes the handoff if you escalate. State which leg
your conclusion rests on and what you could not verify.

## Remove

Deleting YAML deletes in Steep (invariant 9). Follow `references/remove.md`,
and get an explicit yes on what will be deleted before merging.

## Handoff

When the cause is on Steep's side, or the user wants Steep to take over, produce
the filled report in `references/handoff-report.md`. Fill every section
yourself. Never include credentials, tokens, or personal data.

## Safety

- Confirm before irreversible or outward-facing steps: deleting or detaching
  live assets, force-pushing, anything that triggers a production sync.
- Keep diffs surgical. One concern per sync makes the next debug tractable.
- Report honestly: state what you verified, at what level, and what you did not.
