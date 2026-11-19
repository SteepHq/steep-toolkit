# Capabilities and limits

What can be defined in code vs. the UI, what an AI agent can observe and do
programmatically, and when syncs fire. This scopes what the **Build** and
**Debug** modes can realistically achieve.

## Code vs. UI vs. MCP-visible

| Thing | Definable in code? | MCP-visible (read)? |
| --- | --- | --- |
| Modules | yes | `list_modules` |
| Dimensions | yes | via `get_metric` / module data |
| Metrics (`sum`, `count`, `count-distinct`, `ratio`, `custom-value`, `custom-ratio`, `derived-ratio`) | yes | `list_metrics`, `search_metrics`, `get_metric`, `query_metric` |
| Join paths | yes | indirectly (affects query results) |
| Slices | yes | via metric data |
| Filters | yes | via metric data |
| Access policies (row-level security) | yes, when the user asks, see `row-level-security.md` | not directly |
| Entities | yes | `list_entities` |
| Cohorts | yes (`metric.cohort`, not on `derived-ratio`) | via metric data |
| **Targets** | **yes**, via a `targets:` root in its own file (one per workspace) | `list_targets`, `query_target` |
| **Reports** | **no, UI only** | not available |
| Metric *advanced* settings (cache time, team permissions) | **no, UI only** | not directly |
| Slice **inside** a derived-ratio | yes (via `{ metric, slice }`) | via metric data |

### Mixing code and UI

A module can hold both code-defined and app-defined items. A sync only creates,
patches, or deletes items owned by the **same source** as the sync. Exception:
if a module, metric or join path in code has the **same identifier** as an
app-defined one, **code overwrites the app-defined one** (help center). Check for
identifier clashes before migrating. Teams commonly prototype a metric in the UI, then move
its definition into code. (Removing a code item with surviving dependents can
convert it to app-defined instead of deleting it, see `remove.md`.)

## What the Steep MCP exposes (read-only analytics)

- `list_metrics`, `search_metrics` (keyword search), `get_metric`, `query_metric`
- `list_modules`
- `list_entities`
- `list_targets`, `query_target`
- `list_workspace_members`, `list_workspace_teams`

Your workspace may expose a different set. Trust the tools your MCP client
actually lists over this list.

Use these to **verify** what actually landed in the workspace against what the
YAML intends, the third leg of debugging.

## Reading sync results

With your API key (scope `code-syncs:read`), an agent can read sync
results:

- `GET https://api.steep.app/v1/code/syncs?datasourceId=<id>&limit=1`: the
  datasource's last sync, with `outcome` (queued, running, completed, failed),
  created, updated and removed items, `errors` and `warnings`.
- `GET https://api.steep.app/v1/code/syncs/{id}`: one sync by its `id` (from
  the list above).

To find the datasource ID, first call
`GET https://api.steep.app/v1/workspace/datasources`: each datasource's `id` is
the `datasourceId` (scope `datasources:read`; admins only). If that is not
possible, it is the last part of the URL after opening Settings, Data Source,
and clicking edit on the data source. Otherwise, Steep support sends it on
request.

Consequences for the Debug mode:

- Never claim you "checked the sync logs" unless you fetched them or the user
  pasted them.
- To debug: **predict** outcomes from the YAML (`debugging.md`), **interpret**
  the last sync's errors and warnings (or a pasted log), and **verify** the
  resulting state with the read-only MCP tools above.
- If a sync genuinely failed for a reason you can't reproduce from the YAML, that
  is a `handoff-report.md` situation.

## Sync triggers

- **Automatic:** **any push** to the connected branch. Merging a PR triggers a
  sync because the merge is itself a push, and a direct commit triggers one
  too. There is no draft state.
- **Manual:** Settings, Define in Code, Sync now, to re-run the current state
  of the branch. This needs admin rights (the permission to manage metrics;
  ordinary members lack it). If "sync now" is missing or refused for someone,
  that is the reason, not a broken connection.

So the first question when "I changed the YAML and nothing updated" is: did the
change land on the **connected branch**, and is Steep pointed at that branch?
After a successful sync the app's catalog refreshes for everyone without a page
reload; a failed sync changes nothing.

## Preview before merging: the dry run

The dry run previews exactly what a sync would change, without changing
anything: `POST https://api.steep.app/v1/code/syncs` with header
`Authorization: ApiKey <key>` (your own key, from Settings, API) and
`{ "datasourceId": "<id>", "dryRun": true, "files": [...] }`. It lists the
identifiers that would be created, updated, removed and left unchanged, plus
errors and warnings. When the preview completes it also lists `accessPolicies`
grouped as `created`, `updated`, `removed` and `unchanged` (null when the
preview fails); it does not check that a policy is correct. Full steps:
SKILL.md, Build step 4. Some teams also keep a separate workspace on a dev
branch and dev warehouse schemas; that is a workflow pattern, not a Steep
feature.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
