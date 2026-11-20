# Removing definitions

Everything below is what Steep's sync engine does. **The default is deletion,
not conversion.**

## Remove one definition from code

Delete it from the YAML and merge: it is deleted in Steep. Two safety nets
exist; do not plan around them. A metric that a surviving derived metric still
uses, and a module that still has a surviving metric, an entity, or a Targets
table on it, are converted to app-defined instead of deleted, with a warning
naming why. A dimension used in a metric's cohort settings is kept with a
warning until you remove it from those settings. A converted item still
exists but is no longer controlled by code; to delete it fully, remove its
dependents first, then sync again. The warnings are listed in
`debugging.md` ([Global](debugging.md#global), [Metric](debugging.md#metric)).

Before merging, tell the user what will be deleted and get an explicit yes.
Afterwards, check with `list_modules`, `list_metrics`, and `list_entities`
that only the intended things changed.

## Remove nearly everything from code

A push whose YAML yields **zero valid metrics is refused**: the sync aborts and
nothing in Steep changes (this protects a workspace from an accidental wipe).
So the rule is: **keep one module with one metric**, remove the rest, merge,
verify.

## Stopping the code workflow for the whole workspace

That is a workspace setting, not a YAML change. Do not change workspace
settings on the user's behalf; hand off to Steep (support@steep.app) so the
switch is planned together.

Maintained by Steep. Spotted an inaccuracy? Tell support@steep.app.
