# Steep toolkit

Agent skills for working with [Steep](https://steep.app), packaged as the
`steep` plugin for Claude Code. The skills also install into Codex, GitHub
Copilot, Cursor, or any other agent that supports the Agent Skills standard.

## Skills

| Skill | What it does |
| --- | --- |
| [steep-to-ossie](plugins/steep/skills/steep-to-ossie/) | **Experimental.** Export a Steep semantic model to an [Apache Ossie](https://github.com/apache/ossie) document so other tools can read the same metric definitions, with a validator and a report of what does not carry over. |
| [ossie-to-steep](plugins/steep/skills/ossie-to-steep/) | **Experimental.** Import an [Apache Ossie](https://github.com/apache/ossie) semantic model into Steep semantic model YAML: modules, dimensions, metrics and join paths, with a validator and a report of what does not carry over. Restores the original definitions from a `steep-to-ossie` export. |
| [steep-to-snowflake](plugins/steep/skills/steep-to-snowflake/) | **Experimental.** Export a Steep semantic model to a [Snowflake semantic view](https://docs.snowflake.com/en/user-guide/views-semantic/overview) as `CREATE SEMANTIC VIEW` DDL for Cortex Analyst and SQL users, with an offline validator and a report of what does not carry over. |
| [snowflake-to-steep](plugins/steep/skills/snowflake-to-steep/) | **Experimental.** Import a [Snowflake semantic view](https://docs.snowflake.com/en/user-guide/views-semantic/overview) into Steep semantic model YAML: modules, dimensions, metrics and join paths, with a validator and a report of what does not carry over. Restores a `steep-to-snowflake` export. |
| [dbt-to-steep](plugins/steep/skills/dbt-to-steep/) | **Experimental.** Import the [dbt Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl) (MetricFlow) semantic models and metrics of a dbt project, in the latest or the legacy YAML spec, into Steep semantic model YAML: modules, dimensions, metrics and join paths, with a validator and a report of what does not carry over. |

## Install

### Claude Code

```
/plugin marketplace add SteepHq/steep-toolkit
/plugin install steep@steephq
```

The skills then show up as `/steep:<skill>`, for example
`/steep:snowflake-to-steep`. Claude also picks the right skill on its own when
you describe the task.

### Any other agent (Agent Skills standard)

```
npx skills add SteepHq/steep-toolkit
```

The command detects the agents on your machine and installs into each. To
pick, for example, GitHub Copilot inside the current project:

```
npx skills add SteepHq/steep-toolkit -a github-copilot
```

### Codex

Clone the repo; `AGENTS.md` routes Codex to the right skill:

```
git clone https://github.com/SteepHq/steep-toolkit
```

### Manual

Copy the skill folders you want from `plugins/steep/skills/` into your
agent's skills directory, for example `~/.claude/skills/` for Claude Code.

See each skill's README for usage.

## Requirements

The validators need Python 3.10 or later. The Ossie and import validators
also need PyYAML and jsonschema:

```
python3 -m pip install pyyaml jsonschema
```

## Repo layout

```
steep-toolkit/
├── .claude-plugin/
│   └── marketplace.json      # the `steephq` marketplace, lists the plugin
├── plugins/steep/            # the `steep` plugin: what an install copies
│   ├── .claude-plugin/
│   │   ├── plugin.json
│   │   └── icon.png      # listing icon
│   └── skills/
│       └── <skill-name>/
│           ├── SKILL.md      # the entry point an agent reads first
│           ├── README.md     # usage for this skill
│           ├── references/   # supporting material the skill reads on demand
│           └── scripts/      # optional tools the skill runs
├── AGENTS.md                 # Codex / generic agent router
├── LICENSE                   # Apache-2.0
├── NOTICE                    # third-party material and trademarks
└── tests/                    # validator fixtures and repo checks, run in CI
```

## Contributing

Issues and pull requests are welcome. To add a skill, create
`plugins/steep/skills/<skill-name>/` with a `SKILL.md` (YAML frontmatter:
`name` matching the folder, `description` saying when to use it) and a
`README.md`, then add a row to the Skills table above and to `AGENTS.md`. Bump
`version` in `plugins/steep/.claude-plugin/plugin.json` when a change should
reach installed copies.

## Tests

CI runs two checks on every pull request. Run them locally with:

```
python3 -m pip install pyyaml jsonschema
python3 tests/check_repo.py
python3 tests/run.py
```

- `tests/check_repo.py` checks that files copied into several skills are still
  identical, that each skill's `SKILL.md` name matches its folder and is listed
  in this README and `AGENTS.md`, and that the marketplace lists the plugin.
- `tests/run.py` runs each skill's validator over the fixtures in
  `tests/<suite>/valid/` (must pass) and `tests/<suite>/invalid/` (must fail).
  A `<case>.expect` file next to a case lists text the output must contain.

## License

Apache-2.0. See [`LICENSE`](LICENSE). Third-party material and trademarks are
listed in [`NOTICE`](NOTICE).
