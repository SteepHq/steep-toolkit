# Handoff report for the Steep team

When a problem with the Steep semantic model YAML is genuinely on Steep's side, or the user just wants
Steep to take it from here, produce a single, complete report the user can paste
to their Steep contact. The goal is **zero back-and-forth**: Steep should be able
to triage from the report alone.

## When to write one

- You've debugged (`debugging.md`) and the YAML is correct, but the sync still
  fails or the workspace state is wrong.
- The behavior contradicts the rules in this skill (a possible Steep bug).
- The user hits a known gap (e.g. needs reports in code, or a metric's advanced
  settings, which are UI-only today) and wants it on Steep's radar.
- Anything only Steep can do (workspace-level fix, GitHub integration issue).

If instead the problem is the user's YAML, fix it, don't write a handoff for
something self-serviceable.

## Fill it in, don't hand over a blank form

Populate every section from what you gathered while debugging. Keep it
copy-pasteable as one message. Use this template:

```markdown
## Steep semantic model handoff

**Summary:** <one sentence, what's wrong>

**Workspace / datasource:** <workspace name> / <datasource>  (repo: <org/repo>, branch: <branch>)

**Goal:** <what the user was trying to do>

**The change (YAML):**
``​`yaml
<the relevant module/metric YAML, or the diff>
``​`

**Sync log (verbatim from Steep UI → sync history):**
``​`
<paste the errors and warnings exactly, sync logs are not available via MCP/API,
so this must be copied from the UI>
``​`

**Expected:** <what the user expected to happen>
**Actual:** <what actually happened, include what `list_metrics`/`list_modules` show now>

**Already ruled out:** <e.g. one module per table confirmed; identifiers unique;
change landed on the connected branch; every file uses a recognized root key
(`module:` / `targets:`); `type` used (not `calculation`); join paths are
one-to-many>

**What was tried, in order:** <every attempt and its result, so Steep doesn't
re-suggest them, e.g. "1) renamed identifier only, re-synced: completed but
metric still missing. 2) manual sync: same. 3) deleted and re-added the module
block: sync failed with <message>">

**Minimal repro (if any):** <smallest YAML + steps that reproduce it>

**Ask of Steep:** <e.g. "is this a known sync-engine issue?", "can you support X in code?">
```

## Good vs. bad handoff

**Bad:** *"Steep is broken, sync keeps failing, please help."* → forces
Steep to ask for everything.

**Good:** includes the exact YAML, the verbatim sync-log message
(`"Modules orders, orders_v2 are referencing table 'shop.orders'. A table can
only be referenced by one module."`), the fact that the user confirmed it's one
table, and a one-line ask. Steep can act immediately, or, in this example, point
out the second module to remove.

Tip: most of the time, writing the handoff reveals the fix (the verbatim message
usually maps to an entry in `debugging.md`). Run the debug pass first; escalate
only what's left.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
