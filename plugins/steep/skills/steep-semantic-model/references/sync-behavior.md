# Sync behavior

How a Steep Code sync runs and how to reason about its outcome. Read this
before interpreting any sync log or debugging any "my YAML didn't land" report.
For the message catalogue and per-entity fixes, go to `debugging.md`. For what
an agent can observe programmatically, go to `capabilities-and-limits.md`.

---

## 1. Trigger: when a sync runs

A sync runs on **any push to the connected branch**. Steep listens for the GitHub
`push` event and syncs every workspace whose configured repository and branch
match it. Merging a pull request triggers a sync because the merge is itself a
push to that branch, and a direct commit to the connected branch triggers one
just the same. So the reliable question is "did the change land on the
**connected branch**?", never "was it a PR or a push."

A sync can also be started **manually** from the Steep UI (Settings, Define in
Code, Sync now). Use it to re-run the current state of the branch, or when an
expected sync did not happen.

First-line check when a customer says "I changed the YAML and nothing updated":
did the change actually land on the connected branch, and is Steep pointed at
that branch?

---

## 2. Pipeline, what happens during a sync

The sync runs as a single transaction. Steps in order:

1. **Fetch**, Steep fetches **every `.yaml`/`.yml` file in the connected repo**
   (not just `modules/`) at the merge commit.

2. **Parse + validate**, each file is parsed as YAML, then filtered and
   validated:
   - A file that fails to parse, or parses to something that is not a YAML
     mapping (an empty file, a comment-only file, a plain scalar), **aborts the
     entire sync**, even if the file has nothing to do with Steep. Keep the
     connected repo's YAML clean, or use a dedicated repo.
   - A valid YAML mapping with **no recognized root key** (`module:` and
     `targets:` are the only two) is silently skipped: non-Steep YAML is ignored.
   - A file **with** a recognized root is validated against the strict schema. A
     stray extra root or unknown key fails loudly with a clear error.
   - More than one `targets:` definition across the repo is rejected here too,
     before the engine runs.
   Errors at this stage are **Unprocessable** and abort the entire sync
   immediately, nothing is written and the result has no per-item log.

3. **Build candidates**, parsed definitions become in-memory candidates ready
   for the engine.

4. **Engine processes candidates in dependency order:**
   - Modules
   - Join paths
   - Dimensions
   - Metrics (including derived-ratio metrics)
   - Entities
   - Access policies

   This ordering matters: a dimension that references a column in a module that
   failed to process will itself fail with a reference error, not a dimension
   error. When you see a cascade of failures, trace back to the earliest step.

5. **Refinement phase**, candidates that produced errors in step 4 are
   identified. Their existing rows are marked protected-from-deletion.

6. **Deletions**, definitions in the workspace that no longer have a
   corresponding candidate and are not protected are removed. "Remove" can mean
   physical deletion or conversion to UI-owned, depending on whether the
   definition has downstream dependents (see section 4 below and
   `remove.md`).

7. **Commit or rollback**, if there were no fatal problems, the transaction is
   committed. If any fatal condition was raised, the whole transaction is rolled
   back and no changes land.

---

## 3. The 4-tier diagnostic model

The most important concept for reasoning about sync outcomes. Every problem
falls into one of these tiers, and the tier tells you the blast radius.

### Unprocessable (pre-engine)

Caught before the engine runs. Causes: YAML syntax errors, schema validation
failures (unknown keys, wrong types, missing required fields), duplicate module
identifiers, or two modules referencing the same `schema.table`.

**Effect:** the sync **fails immediately**. Nothing is written to the workspace.
The sync log will show the parse/validation error and the file it came from.
All other definitions in the repo are also unprocessed, nothing lands, even
if those files are perfectly valid.

**Fix:** correct the flagged file(s), then merge another PR (or use manual sync).

### fatal

A contradiction that makes the whole result set untrustworthy, even if the
individual file looks fine. Examples: two metrics with the same `identifier`
(across any files), a module candidate that ambiguously matches more than one
existing workspace module.

**Effect:** the transaction **rolls back entirely**. No definition is created,
updated, or deleted. The sync result records every fatal problem so the customer
can see them all at once.

**Fix:** address every fatal error (the log lists all of them), then re-sync.
You cannot partially land a sync that contains a fatal error.

### error

A problem local to one definition. The candidate is **skipped**, not created or
updated, but Steep does something protective: **the existing row for that
definition is shielded from deletion**. A broken YAML edit will not wipe a live
metric. The sync **completes** for all other candidates. The message appears in
the sync log's `errors` section.

**Fix:** correct the definition, merge a fix PR, and the next sync will pick it
up and process the previously-skipped candidate.

State this to the user when it applies: an error does not destroy what was
already there. The old definition survives until the fix lands.

### warning

Informational; the candidate **is still processed** (possibly with an adjustment
or a skipped sub-field). The sync completes. The message appears in the sync
log's `warnings` section. Warnings worth acting on are noted in `debugging.md`;
most indicate a YAML hygiene issue but do not block.

---

## 4. Deletion, with a narrow convert-to-UI-owned safety net

When a code-owned definition is removed from the YAML, the sync deletes it
from the workspace. Deletion is the default. Only if the definition still has **surviving
dependents** does Steep convert it to UI-owned instead, to keep those
dependents working.

Conditions that cause conversion instead of deletion:

- A module is referenced by one or more existing metrics (any metric whose
  `module` field points at it).
- A module is referenced by one or more existing entities.
- A module is the target table in workspace Targets settings.
- A metric is referenced by one or more existing derived-ratio metrics as their
  numerator or denominator.

The sync log shows this as a warning message of the form:

```
Module '<id>' was converted to UI-defined because <reason>
```

or for metrics:

```
Metric '<id>' was converted to UI-defined because it is used in derived metrics
```

This is a safety net, not a way to keep definitions. The definition persists;
it is no longer code-owned. To fully delete it, remove its dependents first,
then re-sync.

For how to remove definitions or stop using code, see `remove.md`.

---

## 5. Where to see sync results

The sync log is visible in the Steep UI under Settings → Define in Code → Sync
history (exact navigation may vary by workspace). It shows:

- The merge commit SHA and timestamp.
- Per-module entries with one of these states: `created`, `patched`, `unchanged`,
  `removed`. Each entry lists the dimensions, metrics, entities, and join paths
  processed under that module and their individual states.
- A top-level `errors` list, messages for each definition that was skipped.
- A top-level `warnings` list, informational messages for definitions that
  processed with a note.
- A top-level failure message if the sync was aborted (Unprocessable) or rolled
  back (fatal).

Two things to read correctly in a sync result:

- **A failed sync's log is a record of intent, not effect.** File-level
  (Unprocessable) failures carry no per-item log at all. Engine-level (fatal)
  failures attach a partial log of everything the sync *attempted*, including
  removals it planned; none of it was applied, because the whole sync is one
  transaction that rolled back.
- **After a successful sync, the app's catalog refreshes automatically** for
  everyone in the workspace; new and renamed metrics/entities appear without a
  page reload. A failed sync changes nothing and triggers no refresh.

**Critical constraint:** sync logs, sync status, and sync errors are **not**
available via the Steep MCP or the Steep customer API. An agent cannot fetch them
programmatically. Debugging therefore relies on three legs: predict from YAML,
interpret a log the user pastes, and verify what landed via read-only MCP. See
`capabilities-and-limits.md` for the full picture of what the MCP exposes, and
`debugging.md` for the full debugging workflow.

---

## 6. Quick reference: "which tier is this?"

| What happened | Tier |
| --- | --- |
| YAML won't parse / schema validation failed / duplicate module id / two modules on same table | Unprocessable |
| Duplicate metric or entity identifier / module candidate ambiguously matches multiple existing modules | fatal |
| One definition skipped; existing row protected; rest of sync completes | error |
| Definition processed with an adjustment or note | warning |
| Definition removed by code removal, with downstream dependents → kept as UI-owned | warning (convert-to-UI) |
| Nothing landed at all, and the YAML looks fine | Check the trigger: did the change land on the connected branch (any push to it syncs)? |

---

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
