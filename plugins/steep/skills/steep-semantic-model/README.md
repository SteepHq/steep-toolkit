# Steep semantic model

**Teaches your coding agent how Steep's semantic layer works in code, so it
writes your YAML correctly, works out why a sync failed on its own, and hands
the problem to Steep with everything we need when it really is our side.**

Works in Claude Code, Codex, GitHub Copilot, Cursor, and any agent that reads
Markdown skills.

## What it does

| Mode | What the agent does |
| --- | --- |
| Build | Reads your dbt models and existing YAML, asks only for business context that changes the output, writes the modules, dimensions, metrics, join paths, slices and entities, checks them, pushes a branch. |
| Debug | Explains a sync error or a "Steep does not match my repo" situation from the YAML and any log you paste, including the blast radius: nothing landed, everything rolled back, or one definition skipped. |
| Remove | Removes one definition, or nearly all of them: deleting YAML deletes the definition in Steep, so the agent says what goes and asks before merging. A push with zero metrics is refused (one module with one metric stays). |
| Handoff | Writes one complete report for the Steep team: what you did, the YAML, the log, expected versus actual, what was already ruled out. |

## Install it

The skill is a folder of Markdown files, nothing to build and nothing to run.
Unzip it, then from the folder that now contains `steep-semantic-model/`:

```
npx skills add ./steep-semantic-model
```

That installs it for every agent it finds. Add `-a codex` (or `claude-code`,
`cursor`, `github-copilot`) to pick one. Point the command at the unzipped
folder, not at the zip file.

**Manual**: copy the `steep-semantic-model` folder into your agent's skills folder
(`~/.claude/skills/` for Claude Code, `.agents/skills/` or `.github/skills/` in
your repo for GitHub Copilot). Any agent that reads Markdown can also simply be
pointed at `SKILL.md`.

## How to talk to it

The skill loads whenever the conversation is about Steep YAML. Prompts that
work well:

- "Build revenue and order metrics for Steep from our dbt marts." Run it from
  the repo that has your dbt models, so the agent reads real table and column
  names instead of guessing.
- "Add a `refund_rate` metric to the orders module as a ratio of refunds to
  orders."
- "Why does Steep show 12 metrics when my repo defines 14?"
- "My Steep sync failed with this log: ..." and paste the log from Steep's sync
  history. The agent matches it against the catalogue of sync messages and
  tells you the cause, what got affected, and the fix.
- "Remove the `legacy_orders` module without breaking the reports built on
  it." The agent tells you what will be deleted before you merge.
- "Write up what went wrong so I can send it to Steep." One complete report:
  what you were doing, the YAML, the sync log, expected versus actual, what you
  already ruled out, every fix you tried. Send that and we can usually act
  immediately instead of asking questions.

One thing worth knowing: **the agent cannot read your sync logs.** Steep's API
does not expose them. It diagnoses from your YAML, and if you paste the log
from the Steep UI (sync history) it interprets that too.

## Check your YAML before you push

Every push to the connected branch syncs, so check first. Two tools from Steep:

- **Typing help.** Put this line on top of any Steep YAML file and your editor
  flags mistakes as you type:
  `# yaml-language-server: $schema=https://api.steep.app/v1/code/schema`
- **Validate.** Send your YAML files to Steep's free validate endpoint and it
  tells you what is wrong (structure and cross references). No key needed and
  it touches nothing, so the agent runs it after every change.
- **Dry run.** With a Steep API key (Settings, API) and your datasource ID, the agent sends your
  YAML to Steep with `dryRun: true`. Steep runs the real sync without changing
  anything and lists what would be created, updated and removed, plus any
  errors. Keep the key in an environment variable (`STEEP_API_KEY`), never in a
  file. To find the datasource ID: Settings, Data Source, click edit on your
  data source (change nothing), and copy the last part of the URL, after
  `/settings/data-sources/`.

## What to have ready

- The repo with your **dbt models** (or any warehouse schema listing). The
  agent should never invent physical table or column names.
- Which **schema and table** each metric is calculated on.
- The **business questions** the metrics need to answer, and any definitions
  with edge cases (what counts as an active customer, which statuses count as
  revenue).
- Any **columns that must never be exposed** as dimensions (personal data,
  internal IDs).

## Five things that trip people up

1. **One physical table, one module.** Two modules pointing at the same table
   fail the entire sync before anything is written.
2. **Every push to the connected branch syncs.** There is no draft state. Once a
   change lands on that branch, it has already applied.
3. **Code is the source of truth, so omission deletes.** Removing a `filters:`
   block or a `category` clears it on the next sync. Do not tidy up a file by
   deleting fields you meant to keep.
4. **Changing a module's identifier and its table in the same commit** makes the
   change ambiguous and can recreate metrics, which detaches reports and
   targets. Change one at a time.
5. **Steep reads every `.yaml` file in the connected repo**, not just one
   folder. A broken or empty YAML file anywhere in that repo fails the whole
   sync. A dedicated repo is the safest setup.

## Starting before Steep is connected

You can. The definitions are just YAML files in Git, and nothing syncs until the
Steep GitHub app is installed and pointed at a repo and branch. Write them now,
review them in pull requests, connect later. `references/examples/` has
known-good files to copy.

## What's inside

```
steep-semantic-model/
├── SKILL.md                     # start here: the rules, then routes by intent
└── references/
    ├── yaml-schema.md           # field and enum reference (the help center page is canonical)
    ├── sync-behavior.md         # how a sync runs; warning / error / fatal model
    ├── debugging.md             # symptom, cause, fix catalogue with the exact sync messages
    ├── capabilities-and-limits.md
    ├── remove.md
    ├── row-level-security.md    # prepare user attributes, write and test access policies
    ├── handoff-report.md
    └── examples/                # known-good YAML plus a worked debug walkthrough
```

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
Last verified against Steep's sync behavior: **2026-09-18**.
