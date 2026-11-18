# Examples

Known-good Steep semantic model YAML and a worked debugging walkthrough. Shapes follow
`../yaml-schema.md`. Adapt the names/columns to the real warehouse, don't ship
these verbatim.

- **`module-with-metrics.yaml`**, a fact module with `sum` (with an `in`
  filter), `count`, and `count-distinct` metrics, dimensions, and a one-to-many
  join path.
- **`derived-and-custom-ratio.yaml`**, a `custom-ratio` (percentage from SQL)
  and a `derived-ratio` (built from two other metrics by identifier).
- **`entity.yaml`**, a module with an `entities` block.
- **`targets.yaml`**, the `targets:` root key in its own dedicated file.
- **`debug-walkthrough.md`**, predict → interpret → verify, on a real "I renamed
  a module and my metrics vanished" case.

Reminders baked into these: exactly two root keys (`module:` and `targets:`, one
per file); `type:` not `calculation:`; one module per physical table; snake_case
except `joinPaths` / `accessPolicies`; join paths are `one-to-one` /
`one-to-many` only.
