# Worked debug walkthrough

A realistic case, end to end, using the **predict → interpret → verify** method
from `../debugging.md`.

## The report

> "I renamed one of my modules and now two of my metrics have vanished from
> Steep. Did the sync delete them?"

## Predict (from the YAML)

Look at what changed in the PR. The diff shows the module's `identifier` **and**
`table` both changed in the same commit:

```diff
 module:
-  identifier: orders
-  schema: steep_demo
-  table: fact_orders
+  identifier: sales
+  schema: steep_demo
+  table: fact_sales
   metrics:
     - identifier: order_revenue
       ...
     - identifier: order_count
       ...
```

Apply the reconciliation rule (SKILL.md rule 1 / `../debugging.md` → Module).
Steep matches a module by `identifier` **or** by `(schema, table)`:

- The new candidate `sales` / `steep_demo.fact_sales` matches the old `orders`
  module by **neither** key, so Steep treats it as a **brand-new module** and
  *creates* it.
- The old `orders` module now has **no candidate** in code, so it's removed (and
  its code-owned metrics with it, they're recreated under `sales` with new rows,
  which is why reports/targets pointing at the old metric IDs break and the
  metrics appear to "vanish").

So this isn't a Steep bug, it's the cost of changing two anchors at once. If
there were *also* a leftover module still pointing at `fact_orders`, you'd
instead get a hard failure (see "If the sync failed outright" below).

## Interpret (the pasted sync log)

Ask the user to paste the sync log. You'd expect to see the old module removed
and the new one created, e.g. a module entry `sales: created` and the old
`orders` gone, with the two metrics recreated. If instead the sync **failed**,
the message tells you which variant you hit:

- `Module candidate 'sales' (table steep_demo.fact_sales) matches more than one
  existing module … by identifier or table reference …` → **fatal**, nothing
  landed: the change was ambiguous (e.g. another module already claims that
  identifier or table).
- `Modules orders, sales are referencing table 'steep_demo.fact_orders'. A table
  can only be referenced by one module.` → **Unprocessable**: a stray second
  module still points at the old table.

## The fix

Change **one anchor at a time**, each landing on the connected branch separately
(every push to that branch is its own sync):

1. **To rename the identifier only**, keep the table the same. Steep recognizes
   the same `(schema, table)` and **patches in place**, the two metrics, their
   dimensions, joins, reports, and targets all survive.
   ```diff
    module:
   -  identifier: orders
   +  identifier: sales
      schema: steep_demo
      table: fact_orders        # unchanged → reconciled as the same module
   ```
2. **To move to a new table**, do that in a separate PR, keeping the identifier
   stable so downstream assets follow the module.

If metrics were already recreated/lost by the bad rename, re-merge with the
identifier matching what's now live, or restore the previous table value so Steep
re-reconciles to the existing module.

## Verify (read-only MCP)

Confirm the recovery without guessing:

- `list_modules` → the module exists once, with the intended identifier/table.
- `list_metrics` / `get_metric` → `order_revenue` and `order_count` are present
  and attached to the module.
- `query_metric` on one of them → returns data, proving the join/time still work.

State plainly what you verified (e.g. "confirmed via `list_metrics` that both
metrics exist and are code-owned") and what you couldn't (you can't read the sync
log via MCP, that came from the user's paste).

## When to hand off

If the log shows a fatal/Unprocessable that the YAML doesn't explain, or the
metrics are still missing after the correct rename re-syncs, capture the YAML
diff, the verbatim log, and your verification, and produce a report via
`../handoff-report.md`.
