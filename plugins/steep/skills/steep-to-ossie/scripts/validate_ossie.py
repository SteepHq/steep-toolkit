#!/usr/bin/env python3
"""Validate an Apache Ossie semantic model against the JSON Schema and the spec's reference rules.

The JSON Schema cannot check that names resolve, so the second pass covers
keys, relationships and metric references from the spec's Name Resolution section,
and checks that every STEEP custom extension carries valid JSON.

The schema is bundled in references/, pinned to the Ossie commit named in SKILL.md,
so validation works offline and does not change under you. Pass --schema to
validate against another copy, for example a newer one you downloaded.

Usage: validate_ossie.py MODEL.yaml [--schema PATH]
"""

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

DEFAULT_SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "references" / "ossie-schema.json"

# String literals are blanked before scanning for references, so 'a.b' inside a
# literal is not mistaken for dataset.field. Double-quoted identifiers are not
# parsed; they only trigger a warning, since sanitized field names need no quotes.
LITERALS = re.compile(r"'(?:[^']|'')*'")
QUALIFIED = re.compile(r'(?<![\w."])([A-Za-z_]\w*)\.([A-Za-z_]\w*)(?![\w"(])')
BARE = re.compile(r'(?<![\w."])([A-Za-z_]\w*)(?![\w".])(?!\s*\()')
COUNT_STAR = re.compile(r"COUNT\s*\(\s*\*\s*\)", re.IGNORECASE)
QUOTED = re.compile(r'"(?:[^"]|"")*"')

# Words that may appear bare in an expression without being a field. Function
# names are recognized by the parenthesis that follows them, so they are not listed.
SQL_WORDS = {
    "all", "and", "any", "as", "asc", "asymmetric", "at", "between", "bigint", "boolean",
    "both", "by", "case", "char", "current", "current_date", "current_time",
    "current_timestamp", "date", "day", "dec", "decimal", "desc", "distinct", "double",
    "else", "end", "escape", "exists", "false", "filter", "first", "float", "following",
    "for", "from", "group", "hour", "ignore", "ilike", "in", "int", "integer", "interval",
    "is", "last", "leading", "like", "localtime", "localtimestamp", "minute", "month", "not",
    "null", "nulls", "numeric", "or", "order", "over", "partition", "preceding", "precision",
    "quarter", "range", "real", "respect", "row", "rows", "second", "similar", "smallint",
    "some", "string", "symmetric", "text", "then", "time", "timestamp", "to", "trailing",
    "true", "unbounded", "unknown", "varchar", "week", "when", "where", "within", "year",
    "zone",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    with open(args.model, encoding="utf-8") as f:
        model = yaml.safe_load(f)

    errors = schema_errors(model, load_schema(args.schema))
    warnings: list[str] = []
    if not errors:
        errors = reference_errors(model) + extension_errors(model)
        warnings = model_metric_warnings(model) + quoted_identifier_warnings(model)

    for error in errors:
        print(f"ERROR {error}")
    for warning in warnings:
        print(f"WARNING {warning}")
    if errors:
        print(f"{len(errors)} error(s)")
        return 1
    print(f"OK {summary(model)}")
    return 0


def load_schema(location: str) -> dict:
    with open(location, encoding="utf-8") as f:
        return json.load(f)


def schema_errors(model: object, schema: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '(root)'}: {error.message}"
        for error in sorted(validator.iter_errors(model), key=lambda e: list(e.absolute_path))
    ]


def reference_errors(model: dict) -> list[str]:
    errors: list[str] = []
    datasets = model.get("datasets", [])
    # Unquoted Ossie names are case-insensitive, so lookups use lower case.
    fields_by_dataset: dict[str, set[str]] = {
        d["name"].lower(): {f["name"].lower() for f in d.get("fields", [])} for d in datasets
    }
    model_metrics = {m["name"].lower() for m in model.get("metrics", [])}

    for name in duplicates(d["name"] for d in datasets):
        errors.append(f"datasets: duplicate dataset name '{name}'")

    for dataset in datasets:
        name = dataset["name"]
        fields = [f["name"] for f in dataset.get("fields", [])]
        metrics = [m["name"] for m in dataset.get("metrics", [])]
        for dup in duplicates(fields + metrics):
            errors.append(f"{name}: '{dup}' is declared more than once among fields and metrics")
        for key in [dataset.get("primary_key", [])] + dataset.get("unique_keys", []):
            for column in key:
                if column.lower() not in fields_by_dataset[name.lower()]:
                    errors.append(f"{name}: key column '{column}' is not a declared field")
        metric_names = {m.lower() for m in metrics} | model_metrics
        for metric in dataset.get("metrics", []):
            errors += dataset_metric_errors(
                name, metric, fields_by_dataset[name.lower()], metric_names
            )

    for name in duplicates(r["name"] for r in model.get("relationships", [])):
        errors.append(f"relationships: duplicate relationship name '{name}'")
    for relationship in model.get("relationships", []):
        errors += relationship_errors(relationship, fields_by_dataset)

    for name in duplicates(m["name"] for m in model.get("metrics", [])):
        errors.append(f"metrics: duplicate metric name '{name}'")
    all_fields = set().union(*fields_by_dataset.values())
    all_metrics = model_metrics | {
        m["name"].lower() for d in datasets for m in d.get("metrics", [])
    }
    for metric in model.get("metrics", []):
        errors += model_metric_errors(metric, fields_by_dataset, all_fields, all_metrics)

    return errors


def duplicates(names) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for name in names:
        if name in seen and name not in repeated:
            repeated.append(name)
        seen.add(name)
    return repeated


def code_of(expression: str) -> str:
    """Blanks string literals and quoted identifiers, which are not scanned for names."""
    return QUOTED.sub('""', LITERALS.sub("''", expression))


def bare_names(code: str) -> list[str]:
    """Unqualified names that are not SQL keywords, function names or parts of a.b."""
    names = []
    for name in BARE.findall(QUALIFIED.sub(" ", code)):
        if name.lower() not in SQL_WORDS and name not in names:
            names.append(name)
    return names


def dataset_metric_errors(
    dataset: str, metric: dict, fields: set[str], metric_names: set[str]
) -> list[str]:
    """Dataset-scoped metrics reference their own fields, unqualified, and never a metric."""
    errors = []
    where = f"{dataset}.{metric['name']}"
    for expression in expressions(metric):
        code = code_of(expression)
        for table, column in QUALIFIED.findall(code):
            errors.append(
                f"{where}: '{table}.{column}' is qualified; "
                "dataset metrics reference their own fields unqualified"
            )
        for name in bare_names(code):
            if name.lower() in fields:
                continue
            if name.lower() in metric_names:
                errors.append(f"{where}: '{name}' is a metric; a metric cannot reference another metric")
            else:
                errors.append(f"{where}: '{name}' is not a field of '{dataset}'")
    return errors


def relationship_errors(relationship: dict, fields_by_dataset: dict[str, set[str]]) -> list[str]:
    name = relationship["name"]
    errors = []
    if len(relationship["from_columns"]) != len(relationship["to_columns"]):
        errors.append(f"relationship {name}: from_columns and to_columns differ in length")
    for side in ("from", "to"):
        dataset = relationship[side]
        if dataset not in fields_by_dataset:
            errors.append(f"relationship {name}: {side} dataset '{dataset}' does not exist")
            continue
        for column in relationship[f"{side}_columns"]:
            if column not in fields_by_dataset[dataset]:
                errors.append(
                    f"relationship {name}: '{column}' is not a field of '{dataset}'"
                )
    return errors


def model_metric_errors(
    metric: dict, fields_by_dataset: dict[str, set[str]], all_fields: set[str], all_metrics: set[str]
) -> list[str]:
    """Model-scoped metrics must reference dataset.field pairs that exist, and no metric.

    A bare name that matches a field only gets a warning (see model_metric_warnings).
    """
    errors = []
    for expression in expressions(metric):
        code = code_of(expression)
        for dataset, field in QUALIFIED.findall(code):
            if dataset.lower() not in fields_by_dataset:
                errors.append(f"metric {metric['name']}: unknown dataset '{dataset}'")
            elif field.lower() not in fields_by_dataset[dataset.lower()]:
                errors.append(f"metric {metric['name']}: '{field}' is not a field of '{dataset}'")
        for name in bare_names(code):
            if name.lower() in all_fields:
                continue
            if name.lower() in all_metrics:
                errors.append(
                    f"metric {metric['name']}: '{name}' is a metric; a metric cannot reference another metric"
                )
            else:
                errors.append(f"metric {metric['name']}: unknown name '{name}'; write dataset.field")
    return errors


def extension_errors(model: dict) -> list[str]:
    """STEEP extensions carry a JSON object as a string; an importer cannot read anything else."""
    errors = []
    for where, extension in custom_extensions(model, "(root)"):
        if extension["vendor_name"] != "STEEP":
            continue
        try:
            data = json.loads(extension["data"])
        except json.JSONDecodeError as error:
            errors.append(f"{where}: STEEP extension data is not valid JSON ({error})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{where}: STEEP extension data must be a JSON object")
    return errors


def custom_extensions(item, where: str):
    """Yields (location, extension) for every custom extension in the document."""
    if isinstance(item, dict):
        for extension in item.get("custom_extensions") or []:
            yield where, extension
        for key, value in item.items():
            if key != "custom_extensions":
                yield from custom_extensions(value, where)
    elif isinstance(item, list):
        for child in item:
            name = child.get("name") if isinstance(child, dict) else None
            if name:
                yield from custom_extensions(child, name if where == "(root)" else f"{where}.{name}")
            else:
                yield from custom_extensions(child, where)


def model_metric_warnings(model: dict) -> list[str]:
    """Flags model-scoped metric expressions that likely mean something other than intended.

    Bare names matching a field are only warnings, since they may be SQL keywords such as DATE.
    """
    field_names = {
        f["name"].lower() for d in model.get("datasets", []) for f in d.get("fields", [])
    }
    warnings = []
    for metric in model.get("metrics", []):
        for expression in expressions(metric):
            code = LITERALS.sub("''", expression)
            if COUNT_STAR.search(code):
                warnings.append(
                    f"metric {metric['name']}: COUNT(*) counts joined rows in a model-scoped "
                    "metric; count DISTINCT primary keys instead"
                )
            unqualified = sorted(
                {name for name in bare_names(QUOTED.sub('""', code)) if name.lower() in field_names}
            )
            if unqualified:
                warnings.append(
                    f"metric {metric['name']}: {', '.join(unqualified)} looks like an "
                    "unqualified field; model metrics must write dataset.field"
                )
    return warnings


def quoted_identifier_warnings(model: dict) -> list[str]:
    """Flags quoted identifiers in metrics, which the reference checks cannot resolve."""
    metrics = model.get("metrics", []) + [
        m for d in model.get("datasets", []) for m in d.get("metrics", [])
    ]
    return [
        f"metric {metric['name']}: {quoted} is quoted and was not checked; "
        "reference the sanitized field name instead"
        for metric in metrics
        for expression in expressions(metric)
        for quoted in QUOTED.findall(LITERALS.sub("''", expression))
    ]


def expressions(item: dict) -> list[str]:
    """Only the OSSIE_SQL_2026 forms are checked; other dialects are opaque by spec."""
    expression = item["expression"]
    if "sql" in expression:
        return [expression["sql"]]
    return [
        d["expression"] for d in expression.get("dialects", []) if d["dialect"] == "OSSIE_SQL_2026"
    ]


def summary(model: dict) -> str:
    datasets = model.get("datasets", [])
    fields = sum(len(d.get("fields", [])) for d in datasets)
    metrics = sum(len(d.get("metrics", [])) for d in datasets) + len(model.get("metrics", []))
    relationships = len(model.get("relationships", []))
    return (
        f"{len(datasets)} datasets, {fields} fields, {metrics} metrics, "
        f"{relationships} relationships"
    )


if __name__ == "__main__":
    sys.exit(main())
