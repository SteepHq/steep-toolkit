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

**Claude Code:**

```
/plugin marketplace add SteepHq/steep-toolkit
/plugin install steep@steephq
```

**Other agents** (Codex, Cursor, GitHub Copilot and more):

```
npx skills add SteepHq/steep-toolkit
```

Any agent that reads Markdown can also simply be pointed at `SKILL.md`.

## How to talk to it

The skill loads whenever the conversation is about Steep YAML. For example:

- "Build revenue and order metrics for Steep from our dbt marts." Run it from
  the repo that has your dbt models, so the agent reads real table and column
  names instead of guessing.
- "Add a `refund_rate` metric to the orders module as a ratio of refunds to
  orders."
- "Why does Steep show 12 metrics when my repo defines 14?"
- "My Steep sync failed with this log: ..." and paste the log from Steep's sync
  history. The agent tells you the cause, what got affected, and the fix.
- "Remove the `legacy_orders` module without breaking the reports built on
  it." The agent tells you what will be deleted before you merge.
- "Write up what went wrong so I can send it to Steep." Send that report and
  we can usually act immediately instead of asking questions.

One thing worth knowing: **the agent cannot read your sync logs.** It can see
whether a sync completed or failed, but not why. It diagnoses from your YAML,
and if you paste the log from the Steep UI (sync history) it interprets that
too.

## Check your YAML before you push

Every push to the connected branch syncs, so the agent checks first with
Steep's validate and dry run (see `SKILL.md`, Build step 4). The dry run needs
a Steep API key (Settings, API, with only the scopes needed and a short expiry)
and your datasource ID: keep the key in an environment variable
(`STEEP_API_KEY`), never in chat or a file.

## What to have ready

- The repo with your **dbt models** (or any warehouse schema listing).
- Which **schema and table** each metric is calculated on.
- The **business questions** the metrics need to answer, and any definitions
  with edge cases (what counts as an active customer, which statuses count as
  revenue).
- Any **columns that must never be exposed** as dimensions (personal data,
  internal IDs).

## One thing that trips people up

**Steep reads every `.yaml` file in the connected repo**, not just one folder. A
broken or empty YAML file anywhere in that repo fails the whole sync. A
dedicated repo is the safest setup.

## Starting before Steep is connected

You can. Nothing syncs until the Steep GitHub app is pointed at a repo and
branch, so write the YAML now, review it in pull requests, connect later. `references/examples/` has
known-good files to copy.

## What's inside

```
steep-semantic-model/
├── SKILL.md                     # start here: the rules, then routes by intent
└── references/
    ├── yaml-schema.md           # field and enum reference (the help center page is canonical)
    ├── debugging.md             # how a sync runs, the error tiers, and the exact sync messages
    ├── capabilities-and-limits.md
    ├── remove.md
    ├── row-level-security.md    # prepare user attributes, write and test access policies
    ├── handoff-report.md
    └── examples/                # known-good YAML
```

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
