# Row-level security (access policies)

Row-level security decides which rows each member sees in a module. Write or
change it only when you ask for it; never add, change or remove a policy
as a side effect of other work. Because omission deletes, dropping the
`accessPolicies:` block removes the protection on the next sync and silently
exposes rows. Canonical page: https://help.steep.app/setup-and-manage/row-level-security

## Warning before any policy change (mandatory)

Whenever a change adds, edits or removes any line inside an `accessPolicies:`
block, including a block deleted with its module, stop before committing or
pushing and show the user this, filled in, at the top of your reply:

> **ROW-LEVEL SECURITY CHANGE: confirm before merging**
> Module: `<identifier>` (`<schema>.<table>`)
> Before: `<policy lines, or "no policy">`
> After: `<policy lines, or "no policy">`
> What this means: `<plain words, e.g. "Every member will see all countries,
> not only their own" or "Members with no row in the user attributes table
> will see no data">`
> Dry run `accessPolicies`: `<created / updated / removed entries for this
> module, or "no change">`. The dry run does not check that the policy is
> correct. Once merged it applies on the next sync for every member.
> Reply **yes** to keep it, or tell me to undo it.

Do not commit or push until the user replies yes to this specific warning. A
removal or a loosened policy (fewer policies, a broader attribute) exposes
rows: say so in those words.

## 1. Prepare the user attributes table (warehouse)

Skip this step if you only filter by the member's email.

- A flat table or view with a `user_email` column: the member's Steep login email.
- One column per attribute to filter on, for example `region`, `cost_center`,
  `account`. Each column becomes a user attribute named `user.<column>`.
- **One row per member per value.** A manager covering SE and NO gets two rows.
  Do not put comma-separated values in one cell.
- **Each row holds one attribute value; the other attribute columns are null.**
  Example (help center):

  | user_email | manager_of | market |
  |---|---|---|
  | sophie@example.com | alex@example.com | null |
  | sophie@example.com | null | SE |
  | sophie@example.com | null | US |
- Build it in dbt like any other model, so it is reviewed and versioned.
- The values must match the data exactly (same spelling and casing as the
  column the policy filters, `SE` is not `se`).

The user connects it once in Steep under **Model, User attributes**. That is a
UI step, not YAML; ask the user to do it.

## 2. Write the policy on the module

```yaml
module:
  identifier: orders
  schema: MARTS
  table: FCT_ORDERS
  accessPolicies:
    - column: COUNTRY            # column whose value must match
      attribute: user.region     # user.email or user.<attribute column>
    - schema: MARTS              # optional: a column on a joined table
      table: DIM_STORES
      column: COST_CENTER
      attribute: user.cost_center
```

- `column` and `attribute` are required; `schema`/`table` only when the column
  lives on another table. That table must be reachable through a join path.
- Several policies on one module combine with **AND**: a row must pass all of them.
- The policy applies to every metric, target and entity built on the module.
- A derived ratio has no module of its own; it inherits the policies of the
  metrics it is built from. Check both sides.
- Physically separate restricted and unrestricted views of the same table need
  a second database view, since one table allows only one module.

## 3. Check it

1. **Read `accessPolicies` in the dry run.** When the dry run completes, its
   response has `accessPolicies` grouped as `created`, `updated`, `removed`
   and `unchanged`, each entry `{ module, policy }` (null when the preview
   fails). Stop on any policy change you did not ask for.
2. **Validate and dry run do not check that a policy is correct.** A wrong or
   missing attribute (`country` instead of `user.country`) passes both. So
   check the policy yourself: `git diff` every `accessPolicies:` block and
   confirm no existing policy was removed or altered unless you asked; confirm
   each `attribute` is `user.email` or `user.<column>` where that column exists
   in the user attributes table; confirm the filtered column exists on the
   module's table or a joined one.
3. **Test as a real member.** The only real test is you logging in as a
   **member** (a test account with known attribute rows works well) and
   comparing a metric against what that member should see. The agent asks you
   to do this and report the result; never claim a policy works without it.
   Also note that Slack subscription PDFs show "Could not load data" for
   protected charts.
4. A member with no matching rows sees **no** data from that module. Check
   that every member who should see data has rows in the attributes table.
