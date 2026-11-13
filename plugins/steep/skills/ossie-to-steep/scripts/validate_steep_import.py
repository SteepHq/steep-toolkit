#!/usr/bin/env python3
"""Validate Steep semantic model YAML produced by an import, before it reaches a sync.

The first pass checks each module file against the bundled JSON Schema of a Steep
module, which is generated from Steep's own schema. The second pass checks the
rules the schema cannot express, across all files, because Steep validates the
whole repo at once. Findings use the tiers Steep's sync reports:

  FATAL    the whole sync fails and nothing lands
  ERROR    that one definition (or part of it) is left out
  WARNING  the sync completes, but the import probably means something else

The checker cannot see the warehouse, so it never confirms that a schema, table
or column exists. Pass the whole Steep folder so duplicates across files show up.

Usage: validate_steep_import.py PATH [PATH ...] [--schema PATH]
Exit:  0 when there is no FATAL or ERROR, 1 otherwise
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

try:
    import jsonschema
    import yaml
except ImportError:
    sys.exit("Missing dependencies. Install them with:  python3 -m pip install pyyaml jsonschema")

DEFAULT_SCHEMA = (
    pathlib.Path(__file__).resolve().parent.parent / "references" / "steep-module-schema.json"
)
SKIPPED_DIRS = {".git", "node_modules", "target", "dbt_packages", ".venv", "__pycache__"}
ROOT_KEYS = {"module", "targets"}
SCHEMA_COMMENT = "# yaml-language-server: $schema=https://api.steep.app/v1/code/schema"
SCHEMA_LINE = re.compile(r"^#\s*yaml-language-server:\s*\$schema=https://api\.steep\.app/v1/code/schema\s*$", re.M)
TARGETS_FIELDS = ("schema", "table")
METRIC_DEFINITIONS = {
    "sum": "Steep.SumMetric",
    "count": "Steep.CountMetric",
    "count-distinct": "Steep.CountDistinctMetric",
    "ratio": "Steep.RatioMetric",
    "custom-value": "Steep.CustomValueMetric",
    "custom-ratio": "Steep.CustomRatioMetric",
    "derived-ratio": "Steep.DerivedRatioMetric",
}
RATIO_TYPES = {"ratio", "custom-ratio", "derived-ratio"}
# Steep stores names, labels and identifiers in varchar(255) columns.
MAX_TEXT_LENGTH = 255
LITERALS = re.compile(r"'(?:[^']|'')*'")
# An unquoted column reference with its table: table.column, schema.table.column or
# database.schema.table.column. A function call such as SAFE.DIVIDE( is not one.
QUALIFIED = re.compile(r'(?<![\w."`])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){1,3})(?![\w."`(])')
FILTER_CLAUSE = re.compile(r"\bFILTER\s*\(\s*WHERE\b", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    schema = load_schema(args.schema)
    findings: list[tuple[str, str, str]] = []
    modules, targets = read_documents(steep_files(args.paths), schema, findings)
    check_model(modules, targets, findings)

    for tier in ("FATAL", "ERROR", "WARNING"):
        for found_tier, where, message in findings:
            if found_tier == tier:
                print(f"{tier} {where}: {message}")
    blocking = sum(1 for tier, _, _ in findings if tier != "WARNING")
    if blocking:
        print(f"{blocking} blocking finding(s)")
        return 1
    print(f"OK {summary(modules, targets)}")
    return 0


def load_schema(location) -> dict:
    with open(location, encoding="utf-8") as f:
        return json.load(f)


def steep_files(paths: list[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for path in map(pathlib.Path, paths):
        if path.is_file():
            files.append(path)
            continue
        for candidate in sorted(path.rglob("*")):
            if candidate.suffix in (".yml", ".yaml") and not SKIPPED_DIRS & set(candidate.parts):
                files.append(candidate)
    return files


def read_documents(files, schema, findings):
    """Parses each file, keeps those with a Steep root, and checks them against the schema."""
    modules: list[tuple[str, dict]] = []
    targets: list[str] = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            document = yaml.safe_load(text)
        except yaml.YAMLError as error:
            findings.append(("FATAL", str(path), f"YAML does not parse: {error}"))
            continue
        # Steep skips a file with no Steep root without a word, as it would any other YAML.
        if not isinstance(document, dict) or not ROOT_KEYS & set(document):
            continue
        if not SCHEMA_LINE.search(text):
            findings.append(("WARNING", str(path), f"no schema line; put '{SCHEMA_COMMENT}' on the "
                             "first line so editors check the file against Steep's schema"))
        if "targets" in document:
            for error in targets_errors(document):
                findings.append(("FATAL", str(path), error))
            targets.append(str(path))
            continue
        errors, module = checked_module(document, schema)
        for error in errors:
            findings.append(("FATAL", str(path), error))
        if module is not None:
            modules.append((str(path), module))
    return modules, targets


def targets_errors(document: dict) -> list[str]:
    """The module schema does not cover targets, so the targets root is checked here."""
    errors = [
        f"(root): '{key}' is not allowed next to 'targets'; a targets file holds only targets"
        for key in document
        if key != "targets"
    ]
    targets = document["targets"]
    if not isinstance(targets, dict):
        return errors + [f"targets: expected an object with {' and '.join(TARGETS_FIELDS)}"]
    for field in TARGETS_FIELDS:
        value = targets.get(field)
        if field not in targets:
            errors.append(f"targets: '{field}' is a required property")
        elif not isinstance(value, str) or not value.strip():
            errors.append(f"targets/{field}: expected a non-empty string, got {value!r}")
    for key in targets:
        if key not in TARGETS_FIELDS:
            errors.append(f"targets: additional property '{key}' is not allowed")
    return errors


def checked_module(document: dict, schema: dict) -> tuple[list[str], dict | None]:
    """Checks the module, then each metric against its own type, so an error names the field.

    Returns the module without its invalid metrics, so the cross-file checks still see the
    rest of it, or None when the module itself does not match the schema.
    """
    module = document.get("module")
    metrics = module.get("metrics") if isinstance(module, dict) else None
    if isinstance(metrics, list):
        document = {**document, "module": {**module, "metrics": []}}
    module_errors = validation_errors(document, schema, [])
    errors = list(module_errors)
    valid_metrics = []
    for index, metric in enumerate(metrics if isinstance(metrics, list) else []):
        path = ["module", "metrics", index]
        kind = metric.get("type") if isinstance(metric, dict) else None
        if kind not in METRIC_DEFINITIONS:
            errors.append(
                f"{format_path(path)}: 'type' is {kind!r}; expected one of "
                f"{', '.join(METRIC_DEFINITIONS)}"
            )
            continue
        variant = {"$defs": schema["$defs"], "$ref": f"#/$defs/{METRIC_DEFINITIONS[kind]}"}
        metric_errors = validation_errors(metric, variant, path)
        errors += metric_errors
        if not metric_errors:
            valid_metrics.append(metric)
    if module_errors:
        return errors, None
    return errors, {**module, "metrics": valid_metrics}


def validation_errors(instance, schema: dict, prefix: list) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{format_path(prefix + list(error.absolute_path))}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    ]


def format_path(path: list) -> str:
    return "/".join(str(part) for part in path) or "(root)"


def check_model(modules, targets, findings) -> None:
    """Checks what Steep validates across files: names, duplicates and references."""
    if len(targets) > 1:
        findings.append(("FATAL", ", ".join(targets), "more than one targets file; Steep allows one"))

    # A table can only have one module; the first one keeps it, as in the check below.
    tables: dict[tuple, dict] = {}
    for _, module in modules:
        tables.setdefault(table_key(module), module)
    metrics: dict[str, tuple[str, dict, dict]] = {}
    all_metrics: list[tuple[str, dict, dict]] = []
    entities: dict[str, str] = {}
    seen_modules: dict[str, str] = {}
    seen_tables: dict[tuple, str] = {}
    join_pairs: dict[tuple, str] = {}

    for path, module in modules:
        identifier = module["identifier"]
        where = f"{path} module {identifier}"
        check_identifier(identifier, where, findings)
        if re.search(r"[/\\]|^\.", identifier):
            findings.append(("FATAL", where, "a module identifier can't contain / or \\, or start with ."))
        check_lengths({"identifier": identifier, "label": module.get("label")}, where, findings)
        if identifier in seen_modules:
            findings.append(("FATAL", where, f"identifier also used in {seen_modules[identifier]}"))
        seen_modules[identifier] = path
        key = table_key(module)
        if key in seen_tables:
            findings.append(
                ("FATAL", where, f"table {'.'.join(key)} already has a module, in "
                 f"{seen_tables[key]}; a table can only be referenced by one module")
            )
        seen_tables[key] = path
        for name in (module["schema"], module["table"]):
            if name != name.strip():
                findings.append(("FATAL", where, f"'{name}' has surrounding whitespace"))

        check_dimensions(module, where, findings)
        check_join_paths(module, where, tables, join_pairs, findings)

        for metric in module.get("metrics", []):
            metric_where = f"{path} metric {metric['identifier']}"
            check_identifier(metric["identifier"], metric_where, findings)
            check_lengths(
                {k: metric.get(k) for k in ("identifier", "name", "category")}, metric_where, findings
            )
            if metric["identifier"] in metrics:
                findings.append(
                    ("FATAL", metric_where, f"identifier also used in {metrics[metric['identifier']][0]}")
                )
            metrics.setdefault(metric["identifier"], (path, module, metric))
            all_metrics.append((path, module, metric))
            check_slices(metric, metric_where, findings)
            check_currency_and_unit(metric, metric_where, findings)

        for entity in module.get("entities", []):
            entity_where = f"{path} entity {entity['identifier']}"
            if entity["identifier"] in entities:
                findings.append(("FATAL", entity_where, f"identifier also used in {entities[entity['identifier']]}"))
            entities[entity["identifier"]] = path
            if not entity.get("properties"):
                findings.append(("ERROR", entity_where, "an entity needs at least one property; it is skipped"))

    join_edges: dict[tuple, set] = {}
    for _, module in modules:
        for join_path in module.get("joinPaths", []):
            to = (join_path["to"].get("schema") or module["schema"], join_path["to"]["table"])
            join_edges.setdefault(table_key(module), set()).add(to)
            join_edges.setdefault(to, set()).add(table_key(module))

    for path, module, metric in all_metrics:
        where = f"{path} metric {metric['identifier']}"
        check_breakdowns(metric, module, tables, where, findings)
        check_cohort(metric, module, where, findings)
        check_operands(metric, metrics, where, findings)
        check_import(metric, module, reachable_tables(table_key(module), join_edges), where, findings)


def table_key(module: dict) -> tuple:
    return (module["schema"], module["table"])


def check_identifier(identifier: str, where: str, findings) -> None:
    if not identifier.strip():
        findings.append(("FATAL", where, "identifier is blank"))
    elif re.search(r"\s", identifier):
        findings.append(("FATAL", where, f"identifier '{identifier}' contains whitespace"))


def check_lengths(texts: dict, where: str, findings) -> None:
    for field, text in texts.items():
        if isinstance(text, str) and len(text) > MAX_TEXT_LENGTH:
            findings.append(("FATAL", where, f"'{field}' is {len(text)} characters; at most {MAX_TEXT_LENGTH}"))


def check_dimensions(module: dict, where: str, findings) -> None:
    identifiers: set[str] = set()
    columns: set[str] = set()
    for dimension in module.get("dimensions", []):
        identifier = dimension.get("identifier", dimension["column"])
        if identifier in identifiers:
            findings.append(("FATAL", where, f"dimension identifier '{identifier}' is declared twice"))
        if dimension["column"] in columns:
            findings.append(("FATAL", where, f"column '{dimension['column']}' has more than one dimension"))
        identifiers.add(identifier)
        columns.add(dimension["column"])


def check_join_paths(module: dict, where: str, tables: dict, join_pairs: dict, findings) -> None:
    """Steep keeps one join path per pair of tables, in either direction."""
    for join_path in module.get("joinPaths", []):
        to = (join_path["to"].get("schema") or module["schema"], join_path["to"]["table"])
        pair = tuple(sorted([table_key(module), to]))
        label = f"join path to {'.'.join(to)}"
        if to == table_key(module):
            findings.append(("WARNING", where, f"{label} joins the module to itself"))
        if pair in join_pairs:
            findings.append(
                ("FATAL", where, f"{label} duplicates one declared in {join_pairs[pair]}; "
                 "declare one join path per pair of tables")
            )
        join_pairs[pair] = where
        if to not in tables:
            findings.append(
                ("WARNING", where, f"{label}: no module in these files is on that table, so Steep "
                 "cannot create the join unless the module exists in the workspace")
            )


def check_slices(metric: dict, where: str, findings) -> None:
    identifiers: set[str] = set()
    for slice_ in metric.get("slices", []):
        identifier = slice_identifier(slice_)
        if identifier in identifiers:
            findings.append(("FATAL", where, f"slice identifier '{identifier}' is declared twice"))
        identifiers.add(identifier)


def check_currency_and_unit(metric: dict, where: str, findings) -> None:
    """Flags a currency or unit that Steep drops because the format or the other one rules it out."""
    currency, unit = metric.get("currency"), metric.get("unit")
    default = "percentage" if metric["type"] in RATIO_TYPES else "number"
    if metric.get("format", default) == "percentage":
        if currency:
            findings.append(
                ("ERROR", where, f"shown as a percentage, so Steep drops currency '{currency}'. "
                 "Write format: number to show it in that currency (ratios default to percentage)")
            )
        if unit:
            findings.append(("ERROR", where, f"shown as a percentage, so Steep drops unit '{unit}'"))
    elif currency and unit:
        findings.append(("ERROR", where, f"has currency '{currency}', so Steep drops unit '{unit}'; keep one"))


def slice_identifier(slice_: dict) -> str:
    """Steep generates a missing slice identifier from the name in snake_case."""
    if slice_.get("identifier"):
        return slice_["identifier"]
    return re.sub(r"[^a-z0-9]+", "_", slice_["name"].lower()).strip("_")


def check_breakdowns(metric: dict, module: dict, tables: dict, where: str, findings) -> None:
    for path in metric.get("dimensions", []):
        parts = path.split(".")
        if parts == ["this", "*"]:
            continue
        if len(parts) > 3:
            findings.append(("ERROR", where, f"dimension '{path}' is not column, table.column or schema.table.column"))
            continue
        column = parts[-1]
        table = parts[-2] if len(parts) > 1 else module["table"]
        schema = parts[-3] if len(parts) > 2 else module["schema"]
        # A path on the metric's own table resolves to its own module, even when another
        # module claims the same table (that conflict is reported on its own).
        target = module if (schema, table) == table_key(module) else tables.get((schema, table))
        if target is None:
            findings.append(("ERROR", where, f"dimension '{path}': no module on {schema}.{table}; it is left out"))
        elif column != "*" and column not in {d["column"] for d in target.get("dimensions", [])}:
            findings.append(
                ("ERROR", where, f"dimension '{path}' is not declared in module "
                 f"{target['identifier']}; it is left out")
            )


def check_cohort(metric: dict, module: dict, where: str, findings) -> None:
    cohort = metric.get("cohort")
    if not cohort:
        if metric.get("cohorts_only"):
            findings.append(("ERROR", where, "'cohorts_only' without a cohort"))
        return
    column = cohort["time_dimension"].split(".")[-1]
    types = {d["column"]: d["type"] for d in module.get("dimensions", [])}
    if column not in types:
        findings.append(("ERROR", where, f"cohort time_dimension '{column}' is not a dimension of the module"))
    elif types[column] != "time":
        findings.append(("ERROR", where, f"cohort time_dimension '{column}' is not a dimension of type time"))


def check_operands(metric: dict, metrics: dict, where: str, findings) -> None:
    if metric["type"] != "derived-ratio":
        return
    for side in ("numerator", "denominator"):
        operand = metric[side]
        identifier = operand if isinstance(operand, str) else operand["metric"]
        if identifier == metric["identifier"]:
            findings.append(("ERROR", where, f"{side} references the metric itself"))
            continue
        if identifier not in metrics:
            findings.append(("ERROR", where, f"{side} metric '{identifier}' is not defined in these files"))
            continue
        slice_ = None if isinstance(operand, str) else operand.get("slice")
        target = metrics[identifier][2]
        if slice_ and slice_ not in {slice_identifier(s) for s in target.get("slices", [])}:
            findings.append(("ERROR", where, f"{side} slice '{slice_}' is not a slice of '{identifier}'"))


def check_import(metric: dict, module: dict, reachable: set, where: str, findings) -> None:
    """Flags what an import typically gets wrong: formats, FILTER clauses and tables out of reach.

    Steep quotes the table of a column path, so paths must match a table exactly; unquoted
    custom SQL folds case, so it is compared case-insensitively.
    """
    if metric["type"] in RATIO_TYPES and "format" not in metric:
        findings.append(
            ("WARNING", where, "no 'format'; Steep shows it as a percentage. "
             "Write format: number unless the source metric multiplied by 100")
        )
    if metric["type"] == "derived-ratio":
        return
    reach = "is not this module's table or joined to it by join paths in these files"
    names = {table for _, table in reachable}
    for field in ("time", "value", "distinct_on", "numerator", "denominator"):
        path = metric.get(field)
        if not isinstance(path, str):
            continue
        table = path.split(".")[-2] if "." in path else module["table"]
        if table not in names:
            findings.append(("WARNING", where, f"{field} '{path}': table '{table}' {reach} (names are case-sensitive)"))
    for filter_ in metric.get("filters", []):
        table = filter_.get("table")
        if table and table != "this" and table not in names:
            findings.append(("WARNING", where, f"filter on '{table}.{filter_['column']}': table {reach}"))
    folded = {(schema.lower(), table.lower()) for schema, table in reachable}
    for field in ("sql_expression", "numerator_sql", "denominator_sql"):
        sql = metric.get(field)
        if not isinstance(sql, str):
            continue
        code = LITERALS.sub("''", sql)
        if FILTER_CLAUSE.search(code):
            findings.append(
                ("WARNING", where, f"{field} uses FILTER (WHERE …), which Snowflake, BigQuery, "
                 "Redshift and MySQL reject; write CASE WHEN … THEN … END")
            )
        for reference in QUALIFIED.findall(code):
            if not sql_reaches(reference.split("."), folded):
                findings.append(
                    ("WARNING", where, f"{field} references '{reference}': table "
                     f"'{'.'.join(reference.split('.')[-3:-1])}' {reach}")
                )


def sql_reaches(parts: list[str], folded: set) -> bool:
    """Matches [database.][schema.]table.column against the reachable (schema, table) pairs.

    The database part is not checked; the schema part, when present, must match too.
    """
    table = parts[-2].lower()
    if len(parts) == 2:
        return any(table == name for _, name in folded)
    return (parts[-3].lower(), table) in folded


def reachable_tables(start: tuple, join_edges: dict) -> set:
    """Returns the (schema, table) pairs reachable from start.

    Steep follows a join path in both directions, so reach is undirected.
    """
    seen, todo = {start}, [start]
    while todo:
        for neighbour in join_edges.get(todo.pop(), ()):
            if neighbour not in seen:
                seen.add(neighbour)
                todo.append(neighbour)
    return seen


def summary(modules, targets) -> str:
    metrics = [m for _, module in modules for m in module.get("metrics", [])]
    dimensions = sum(len(module.get("dimensions", [])) for _, module in modules)
    join_paths = sum(len(module.get("joinPaths", [])) for _, module in modules)
    return (
        f"{len(modules)} modules, {dimensions} dimensions, {len(metrics)} metrics, "
        f"{join_paths} join paths, {len(targets)} targets files"
    )


if __name__ == "__main__":
    sys.exit(main())
