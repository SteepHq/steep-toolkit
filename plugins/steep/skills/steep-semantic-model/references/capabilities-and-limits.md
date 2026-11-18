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

A module can hold both code-defined and UI-defined items. A sync only creates,
patches, or deletes items owned by the **same source** as the sync. Exception:
if a module, metric or join path in code has the **same identifier** as an
app-defined one, **code overwrites the app-defined one** (help center). Check for
identifier clashes before migrating. Teams commonly prototype a metric in the UI, then move
its definition into code. (Removing a code item with UI dependents converts it to
UI rather than deleting, see `remove.md`.)

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

## The hard limit: no sync introspection

There is **no** MCP or customer-API operation for sync **status, history, logs,
or errors**. An agent **cannot fetch why a sync failed.** Triggering a sync is
not exposed through the MCP either.

Consequences for the Debug mode:

- Never claim you "checked the sync logs", you can't read them.
- To debug: **predict** outcomes from the YAML (`debugging.md`), **interpret** a
  log the user pastes from the Steep UI, and **verify** the resulting state with
  the read-only MCP tools above.
- If a sync genuinely failed for a reason you can't reproduce from the YAML, that
  is a `handoff-report.md` situation.

## Sync triggers

- **Automatic:** **any push** to the connected branch. Merging a PR triggers a
  sync because the merge is itself a push to that branch, and a direct commit to
  the connected branch triggers one too.
- **Manual:** a "sync now" action in the Steep UI. Since 2026-09-11 this needs
  admin rights (the permission to manage metrics; ordinary members lack it). If
  "sync now" is missing or refused for someone, that is the reason, not a broken
  connection; pushing to the connected branch still syncs for everyone.

So the reliable question is always "did the change land on the **connected
branch**?", not "was it a PR or a push."

See `sync-behavior.md` for the full pipeline.

## No built-in pre-merge preview (current practical pattern)

Steep has no built-in "preview the result before merging" environment. Teams that
want to see changes before they hit production typically use a **separate
workspace** connected to a **dev branch/repo and dev warehouse schemas**, iterate
there, then promote to the production repo/branch. This is a workflow pattern, not
a Steep feature, mention it when a customer asks "how do I see the result before
merging?" and set expectations accordingly.

## Casing

snake_case everywhere except `joinPaths` and `accessPolicies`, which are
camelCase. Any change will appear on the code reference page first.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
