#!/usr/bin/env python3
"""Check a CREATE SEMANTIC VIEW statement against Snowflake's semantic view rules, offline.

Snowflake has no dry run for semantic view DDL, so this catches the structural
and reference errors that would otherwise only show up when the statement runs:
clause order, keys behind relationships, relationship cycles, names that do
not resolve, unquoted reserved keywords, cross-table references Snowflake
rejects, metrics that aggregate metrics, and derived metric rules.
It does not type-check SQL or know which physical columns exist.

The rules come from references/semantic-view-syntax.md. Standard library only.

Usage: validate_semantic_view.py VIEW.sql
"""

import argparse
import re
import sys
from dataclasses import dataclass, field

CLAUSES = [
    "TABLES",
    "RELATIONSHIPS",
    "FACTS",
    "DIMENSIONS",
    "METRICS",
    "COMMENT",
    "MAX_STALENESS",
    "AI_SQL_GENERATION",
    "AI_QUESTION_CATEGORIZATION",
    "AI_VERIFIED_QUERIES",
    "TAG",
    "COPY",
]
ITEM_MODIFIERS = {"WITH", "COMMENT", "TAG"}
AGGREGATES = {
    "ANY_VALUE", "APPROX_COUNT_DISTINCT", "APPROX_PERCENTILE", "ARRAY_AGG", "AVG",
    "BITAND_AGG", "BITOR_AGG", "BOOLAND_AGG", "BOOLOR_AGG", "CORR", "COUNT",
    "COUNT_IF", "COVAR_POP", "COVAR_SAMP", "HLL", "KURTOSIS", "LISTAGG", "MAX",
    "MAX_BY", "MEDIAN", "MIN", "MIN_BY", "MODE", "OBJECT_AGG", "PERCENTILE_CONT",
    "PERCENTILE_DISC", "SKEW", "STDDEV", "STDDEV_POP", "STDDEV_SAMP", "SUM",
    "VAR_POP", "VAR_SAMP", "VARIANCE", "VARIANCE_POP", "VARIANCE_SAMP",
}
RESERVED = set("""
    ACCOUNT ALL ALTER AND ANY AS BETWEEN BY CASE CAST CHECK COLUMN CONNECT CONNECTION
    CONSTRAINT CREATE CROSS CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP
    CURRENT_USER DATABASE DELETE DISTINCT DROP ELSE EXISTS FALSE FOLLOWING FOR FROM
    FULL GRANT GROUP GSCLUSTER HAVING ILIKE IN INCREMENT INNER INSERT INTERSECT INTO
    IS ISSUE JOIN LATERAL LEFT LIKE LOCALTIME LOCALTIMESTAMP MINUS NATURAL NOT NULL OF
    ON OR ORDER ORGANIZATION QUALIFY REGEXP REVOKE RIGHT RLIKE ROW ROWS SAMPLE SCHEMA
    SELECT SET SOME START TABLE TABLESAMPLE THEN TO TRIGGER TRUE TRY_CAST UNION UNIQUE
    UPDATE USING VALUES VIEW WHEN WHENEVER WHERE WINDOW WITH
""".split())
TOKEN = re.compile(
    r"""
    (?P<space>\s+|--[^\n]*|/\*.*?\*/)
  | (?P<string>'(?:[^'\\]|\\.|'')*'|\$\$.*?\$\$)
  | (?P<quoted>"(?:[^"]|"")*")
  | (?P<word>[A-Za-z_][A-Za-z0-9_$]*)
  | (?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<punct>[(),.;=])
  | (?P<op>[^\s\w'"(),.;=]+)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class Tok:
    kind: str
    text: str

    @property
    def upper(self) -> str:
        return self.text.upper() if self.kind == "word" else self.text

    @property
    def ident(self) -> str:
        """Identifier as Snowflake stores it: unquoted names upper-cased, quoted ones exact."""
        if self.kind == "quoted":
            return self.text[1:-1].replace('""', '"')
        return self.text.upper()


@dataclass
class Table:
    alias: str
    primary_key: tuple[str, ...] | None = None
    unique: list[tuple[str, ...]] = field(default_factory=list)


@dataclass
class Relationship:
    name: str | None
    left: str
    left_columns: tuple[str, ...]
    right: str
    right_columns: tuple[str, ...] | None


@dataclass
class Item:
    kind: str  # fact, dimension, metric
    table: str | None  # None for derived metrics
    name: str
    private: bool
    expression: list[Tok]
    non_additive_by: list[list[Tok]] = field(default_factory=list)
    using: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.table}.{self.name}" if self.table else self.name


class ParseError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sql")
    args = parser.parse_args()

    with open(args.sql, encoding="utf-8") as f:
        text = f.read()

    try:
        statements = [parse_statement(s) for s in split_statements(tokenize(text))]
    except ParseError as error:
        print(f"ERROR {error}")
        print("1 error(s)")
        return 1
    if not statements:
        print("ERROR no CREATE SEMANTIC VIEW statement found")
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    for view in statements:
        view_errors, view_warnings = check_view(view)
        errors += [f"{view['name']}: {e}" for e in view_errors]
        warnings += [f"{view['name']}: {w}" for w in view_warnings]

    for error in errors:
        print(f"ERROR {error}")
    for warning in warnings:
        print(f"WARNING {warning}")
    if errors:
        print(f"{len(errors)} error(s)")
        return 1
    for view in statements:
        print(f"OK {view['name']}: {summary(view)}")
    return 0


def tokenize(text: str) -> list[Tok]:
    tokens: list[Tok] = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            line = text.count("\n", 0, position) + 1
            raise ParseError(f"line {line}: unterminated string or identifier")
        if match.lastgroup != "space":
            tokens.append(Tok(match.lastgroup, match.group()))
        position = match.end()
    return tokens


def split_statements(tokens: list[Tok]) -> list[list[Tok]]:
    statements: list[list[Tok]] = [[]]
    depth = 0
    for tok in tokens:
        depth += {"(": 1, ")": -1}.get(tok.text, 0) if tok.kind == "punct" else 0
        if tok.text == ";" and depth == 0:
            statements.append([])
        else:
            statements[-1].append(tok)
    return [s for s in statements if s]


def parse_statement(tokens: list[Tok]) -> dict:
    cursor = Cursor(tokens)
    cursor.expect("CREATE")
    if cursor.accept("OR"):
        if not (cursor.accept("REPLACE") or cursor.accept("ALTER")):
            raise ParseError("expected OR REPLACE or OR ALTER")
    cursor.expect("SEMANTIC")
    cursor.expect("VIEW")
    if cursor.accept("IF"):
        cursor.expect("NOT")
        cursor.expect("EXISTS")
    name = cursor.dotted_name()

    view: dict = {
        "name": ".".join(t.text for t in name),
        "tables": [],
        "relationships": [],
        "items": [],
        "clause_errors": [],
        "names": [("view name", t) for t in name],
    }
    last_index = -1
    while not cursor.done():
        keyword = cursor.next()
        clause = "TAG" if keyword.upper in ("WITH", "TAG") else keyword.upper
        if clause not in CLAUSES:
            raise ParseError(f"unexpected '{keyword.text}' where a clause was expected")
        index = CLAUSES.index(clause)
        if index <= last_index:
            view["clause_errors"].append(
                f"clause {clause} is out of order or repeated; the order is "
                "TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS, COMMENT, AI_SQL_GENERATION"
            )
        last_index = max(last_index, index)
        if clause in ("TABLES", "RELATIONSHIPS", "FACTS", "DIMENSIONS", "METRICS"):
            for item in split_top_level(cursor.parenthesized()):
                parse_clause_item(clause, item, view)
        elif clause in ("COMMENT", "MAX_STALENESS"):
            cursor.expect("=")
            cursor.next()
        elif clause in ("AI_SQL_GENERATION", "AI_QUESTION_CATEGORIZATION"):
            cursor.next()
        elif clause == "AI_VERIFIED_QUERIES":
            cursor.parenthesized()
        elif clause == "TAG":
            if keyword.upper == "WITH":
                cursor.expect("TAG")
            cursor.parenthesized()
        elif clause == "COPY":
            cursor.expect("GRANTS")
    return view


class Cursor:
    def __init__(self, tokens: list[Tok]):
        self.tokens = tokens
        self.i = 0

    def done(self) -> bool:
        return self.i >= len(self.tokens)

    def peek(self, offset: int = 0) -> Tok | None:
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else None

    def next(self) -> Tok:
        if self.done():
            raise ParseError("statement ends early")
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def accept(self, text: str) -> bool:
        tok = self.peek()
        if tok and tok.upper == text:
            self.i += 1
            return True
        return False

    def expect(self, text: str) -> None:
        tok = self.next()
        if tok.upper != text:
            raise ParseError(f"expected '{text}', found '{tok.text}'")

    def dotted_name(self) -> list[Tok]:
        parts = [self.next()]
        while self.accept("."):
            parts.append(self.next())
        return parts

    def parenthesized(self) -> list[Tok]:
        """Returns the tokens between a '(' and its matching ')'."""
        self.expect("(")
        start = self.i
        depth = 1
        while depth:
            tok = self.next()
            if tok.kind == "punct":
                depth += {"(": 1, ")": -1}.get(tok.text, 0)
        return self.tokens[start : self.i - 1]


def split_top_level(tokens: list[Tok]) -> list[list[Tok]]:
    parts: list[list[Tok]] = [[]]
    depth = 0
    for tok in tokens:
        if tok.kind == "punct" and tok.text in "()":
            depth += 1 if tok.text == "(" else -1
        if tok.text == "," and depth == 0:
            parts.append([])
        else:
            parts[-1].append(tok)
    return [p for p in parts if p]


def parse_clause_item(clause: str, tokens: list[Tok], view: dict) -> None:
    cursor = Cursor(tokens)
    if clause == "TABLES":
        view["tables"].append(parse_table(cursor, view["names"]))
    elif clause == "RELATIONSHIPS":
        view["relationships"].append(parse_relationship(cursor, view["names"]))
    else:
        kind = {"FACTS": "fact", "DIMENSIONS": "dimension", "METRICS": "metric"}[clause]
        view["items"].append(parse_item(kind, cursor, view["names"]))


def parse_table(cursor: Cursor, names: list) -> Table:
    if cursor.peek(1) and cursor.peek(1).upper == "AS":
        alias_tok = cursor.next()
        cursor.next()
        physical = cursor.dotted_name()
    else:
        physical = cursor.dotted_name()
        alias_tok = physical[-1]
    table = Table(alias_tok.ident)
    names += [(f"table {table.alias}", t) for t in [alias_tok, *physical]]
    while not cursor.done():
        tok = cursor.next()
        if tok.upper in ("PRIMARY", "UNIQUE"):
            if tok.upper == "PRIMARY":
                cursor.expect("KEY")
            tokens = cursor.parenthesized()
            names += [(f"table {table.alias}", t) for t in tokens if t.kind == "word"]
            if tok.upper == "PRIMARY":
                table.primary_key = column_list(tokens)
            else:
                table.unique.append(column_list(tokens))
    return table


def parse_relationship(cursor: Cursor, names: list) -> Relationship:
    start = cursor.i
    name = None
    if cursor.peek(1) and cursor.peek(1).upper == "AS":
        name = cursor.next().ident
        cursor.next()
    left = cursor.next().ident
    left_columns = column_list(cursor.parenthesized())
    cursor.expect("REFERENCES")
    right = cursor.next().ident
    right_columns = column_list(cursor.parenthesized()) if not cursor.done() else None
    label = f"relationship {name or left + '->' + right}"
    names += [
        (label, t) for t in cursor.tokens[start : cursor.i]
        if t.kind == "word" and t.upper not in ("AS", "REFERENCES", "ASOF")
    ]
    return Relationship(name, left, left_columns, right, right_columns)


def column_list(tokens: list[Tok]) -> tuple[str, ...]:
    return tuple(t.ident for t in tokens if t.kind in ("word", "quoted") and t.upper != "ASOF")


def parse_item(kind: str, cursor: Cursor, names: list) -> Item:
    private = False
    if cursor.peek() and cursor.peek().upper in ("PRIVATE", "PUBLIC"):
        private = cursor.next().upper == "PRIVATE"
    name_parts = cursor.dotted_name()
    table = name_parts[0].ident if len(name_parts) == 2 else None
    item = Item(kind, table, name_parts[-1].ident, private, [])
    names += [(item.label, t) for t in name_parts]
    while not cursor.accept("AS"):
        tok = cursor.next()
        if tok.upper == "USING":
            item.using = list(column_list(cursor.parenthesized()))
        elif tok.upper == "NON":
            cursor.expect("ADDITIVE")
            cursor.expect("BY")
            item.non_additive_by = split_top_level(cursor.parenthesized())
        elif tok.upper == "LABELS":
            cursor.expect("=")
            cursor.parenthesized()
        else:
            raise ParseError(f"{item.label}: unexpected '{tok.text}' before AS")
    depth = 0
    while not cursor.done():
        tok = cursor.peek()
        if depth == 0 and tok.upper in ITEM_MODIFIERS:
            break
        if tok.kind == "punct" and tok.text in "()":
            depth += 1 if tok.text == "(" else -1
        item.expression.append(cursor.next())
    if not item.expression:
        raise ParseError(f"{item.label}: empty expression")
    # The part after a dot is always a name, never a keyword.
    names += [
        (item.label, t) for i, t in enumerate(item.expression)
        if i and item.expression[i - 1].text == "." and t.kind == "word"
    ]
    return item


def check_view(view: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = list(view["clause_errors"])
    warnings: list[str] = []
    tables = {t.alias: t for t in view["tables"]}
    items = view["items"]

    if not view["tables"]:
        errors.append("TABLES is required")
    if not any(i.kind in ("dimension", "metric") for i in items):
        errors.append("a semantic view needs at least one dimension or metric")
    for alias in duplicates(t.alias for t in view["tables"]):
        errors.append(f"table alias {alias} is declared more than once")
    for table in view["tables"]:
        if table.primary_key and table.primary_key in table.unique:
            errors.append(f"{table.alias}: UNIQUE repeats the PRIMARY KEY")

    for where, tok in view["names"]:
        if tok.kind == "word" and tok.upper in RESERVED:
            errors.append(
                f"{where}: {tok.text} is a reserved keyword; double-quote it, or rename a "
                "semantic name (add _dim, _fact, _metric or _tbl)"
            )

    errors += relationship_errors(view["relationships"], tables)
    lower = lower_granularity(view["relationships"], tables)

    names_by_table: dict[str, dict[str, Item]] = {alias: {} for alias in tables}
    derived: dict[str, Item] = {}
    for item in items:
        if item.table is None:
            if item.kind != "metric":
                errors.append(f"{item.name}: every {item.kind} needs a table prefix")
            elif item.name in derived:
                errors.append(f"derived metric {item.name} is declared more than once")
            derived[item.name] = item
            continue
        if item.table not in tables:
            errors.append(f"{item.label}: unknown table alias {item.table}")
            continue
        if item.name in names_by_table[item.table]:
            errors.append(f"{item.label} is declared more than once in this table")
        names_by_table[item.table][item.name] = item
        if item.private and item.kind == "dimension":
            errors.append(f"{item.label}: dimensions cannot be PRIVATE")

    metric_names = {i.name for i in items if i.kind == "metric" and i.table}
    for name in derived:
        if name in metric_names:
            errors.append(f"derived metric {name} has the same name as a table metric")

    rel_names = {r.name for r in view["relationships"] if r.name}
    context = Context(tables, names_by_table, derived, lower)
    for item in items:
        if item.table is not None and item.table not in tables:
            continue
        for name in item.using:
            if name not in rel_names:
                errors.append(f"{item.label}: USING names unknown relationship {name}")
        e, w = expression_problems(item, context)
        errors += e
        warnings += w
    return errors, warnings


def duplicates(names) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for name in names:
        if name in seen and name not in repeated:
            repeated.append(name)
        seen.add(name)
    return repeated


def relationship_errors(relationships: list[Relationship], tables: dict[str, Table]) -> list[str]:
    errors = []
    for name in duplicates(r.name for r in relationships if r.name):
        errors.append(f"relationship {name} is declared more than once")
    for rel in relationships:
        label = f"relationship {rel.name or rel.left + '->' + rel.right}"
        if rel.left not in tables or rel.right not in tables:
            missing = rel.left if rel.left not in tables else rel.right
            errors.append(f"{label}: unknown table alias {missing}")
            continue
        if rel.left == rel.right:
            errors.append(f"{label}: a table cannot reference itself")
        target = tables[rel.right]
        ref_columns = rel.right_columns or target.primary_key
        if ref_columns is None:
            errors.append(f"{label}: {rel.right} has no PRIMARY KEY to reference")
            continue
        if len(ref_columns) != len(rel.left_columns):
            errors.append(f"{label}: column counts differ")
        keys = [k for k in [target.primary_key, *target.unique] if k]
        if not any(set(ref_columns) == set(key) for key in keys):
            errors.append(
                f"{label}: {rel.right}({', '.join(ref_columns)}) is not its PRIMARY KEY "
                "or a UNIQUE key"
            )
    cycle = find_cycle(relationships)
    if cycle:
        errors.append(f"relationships form a cycle: {' -> '.join(cycle)}")
    for left, right in duplicates((r.left, r.right) for r in relationships):
        errors.append(
            f"{left} references {right} more than once; metrics crossing them need USING"
        )
    return errors


def find_cycle(relationships: list[Relationship]) -> list[str] | None:
    edges: dict[str, set[str]] = {}
    for rel in relationships:
        edges.setdefault(rel.left, set()).add(rel.right)
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        path.append(node)
        for nxt in sorted(edges.get(node, ())):
            if state.get(nxt) == 1:
                return path[path.index(nxt) :] + [nxt]
            if nxt not in state:
                found = visit(nxt)
                if found:
                    return found
        state[node] = 2
        path.pop()
        return None

    for node in sorted(edges):
        if node not in state:
            found = visit(node)
            if found:
                return found
    return None


def lower_granularity(relationships: list[Relationship], tables: dict[str, Table]) -> dict[str, set[str]]:
    """Tables each table reaches by following REFERENCES, i.e. its own or lower granularity.

    When the referencing columns are also a key of their table, the relationship is
    one-to-one and both tables have the same granularity, so it is followed both ways.
    """
    edges: dict[str, set[str]] = {}
    for rel in relationships:
        edges.setdefault(rel.left, set()).add(rel.right)
        left = tables.get(rel.left)
        keys = [k for k in [left.primary_key, *left.unique] if k] if left else []
        if any(set(rel.left_columns) == set(key) for key in keys):
            edges.setdefault(rel.right, set()).add(rel.left)
    reach: dict[str, set[str]] = {}
    for start in edges:
        seen: set[str] = set()
        stack = [start]
        while stack:
            for nxt in edges.get(stack.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        reach[start] = seen
    return reach


@dataclass
class Context:
    tables: dict[str, Table]
    names_by_table: dict[str, dict[str, Item]]
    derived: dict[str, Item]
    lower: dict[str, set[str]]


def expression_problems(item: Item, ctx: Context) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expr = item.expression
    words = [t.upper for t in expr]

    for i in range(len(expr) - 2):
        if words[i] == "FILTER" and expr[i + 1].text == "(" and words[i + 2] == "WHERE":
            errors.append(f"{item.label}: FILTER (WHERE ...) is not Snowflake SQL; use IFF")

    for dim_tokens in item.non_additive_by:
        ref = qualified_refs(dim_tokens)
        target = ref[0][1:] if ref else None
        if not target or ctx.names_by_table.get(target[0], {}).get(target[1], None) is None or (
            ctx.names_by_table[target[0]][target[1]].kind != "dimension"
        ):
            text = " ".join(t.text for t in dim_tokens)
            errors.append(f"{item.label}: NON ADDITIVE BY {text} is not a qualified dimension")

    in_aggregate = aggregate_positions(expr)
    refs = qualified_refs(expr)
    metric_refs = 0
    for position, table, name in refs:
        if table not in ctx.tables:
            errors.append(f"{item.label}: unknown table alias {table}")
            continue
        target = ctx.names_by_table[table].get(name)
        aggregated = position in in_aggregate
        if target is not None and target.kind == "metric" and target is not item:
            metric_refs += 1
            if aggregated and item.kind == "metric":
                errors.append(
                    f"{item.label}: aggregates the metric {target.label}; "
                    "use metrics without an aggregate around them"
                )
        if item.table is None:
            if target is None:
                errors.append(
                    f"{item.label}: derived metrics cannot reference the physical column "
                    f"{table}.{name}"
                )
            elif target.kind != "metric" and not aggregated:
                errors.append(
                    f"{item.label}: derived metrics cannot use the {target.kind} {target.label} "
                    "without aggregating it"
                )
            continue
        if table == item.table:
            continue
        if target is None:
            errors.append(
                f"{item.label}: {table}.{name} is a physical column of another table; "
                f"define a fact or dimension on {table} and reference that"
            )
            continue
        if target.non_additive_by and target.kind == "metric":
            errors.append(
                f"{item.label}: {target.label} has NON ADDITIVE BY; only derived metrics may use it"
            )
        if table not in ctx.lower.get(item.table, set()) and (item.kind == "metric" or not aggregated):
            errors.append(
                f"{item.label}: {table} is not on the one side of {item.table}, so {target.label} "
                "needs nested aggregation. Reference it from a metric on "
                f"{table}, or make the relationship one-to-one with a UNIQUE key on "
                "its referencing columns if it truly is"
            )

    if item.table is None:
        errors += derived_bare_errors(item, ctx, in_aggregate)
    elif item.kind == "metric":
        own = ctx.names_by_table[item.table]
        for position, name in bare_names(expr):
            target = own.get(name)
            if target is None or target.kind != "metric" or name == item.name:
                continue
            metric_refs += 1
            if position in in_aggregate:
                errors.append(
                    f"{item.label}: aggregates the metric {target.label}; "
                    "use metrics without an aggregate around them"
                )
            if target.non_additive_by:
                errors.append(
                    f"{item.label}: {target.label} has NON ADDITIVE BY; only derived metrics may use it"
                )
        if not any(w in AGGREGATES for w in words) and not metric_refs:
            warnings.append(f"{item.label}: no aggregate function found; table metrics must aggregate")
        for table, name in {(t, n) for _, t, n in refs if t == item.table}:
            if name != item.name and name in own and own[name].kind == "metric":
                if own[name].non_additive_by:
                    errors.append(
                        f"{item.label}: {own[name].label} has NON ADDITIVE BY; "
                        "only derived metrics may use it"
                    )
        if item.name in {name for _, table, name in refs if table == item.table}:
            warnings.append(
                f"{item.label}: its name equals a column it reads; Snowflake resolves the "
                "name to the metric itself. Rename the metric"
            )
    elif any(w in AGGREGATES for w in words) and not refs_other_tables(refs, item.table):
        warnings.append(f"{item.label}: a {item.kind} is row-level; it should not aggregate its own table")
    return errors, warnings


def aggregate_positions(tokens: list[Tok]) -> set[int]:
    """Indexes of the tokens inside the parentheses of an aggregate function call."""
    inside: set[int] = set()
    for i, tok in enumerate(tokens[:-1]):
        if tok.upper not in AGGREGATES or tokens[i + 1].text != "(":
            continue
        if i and tokens[i - 1].text == ".":
            continue
        depth = 0
        for j in range(i + 1, len(tokens)):
            if tokens[j].kind == "punct" and tokens[j].text in "()":
                depth += 1 if tokens[j].text == "(" else -1
                if depth == 0:
                    break
            elif depth:
                inside.add(j)
    return inside


def bare_names(tokens: list[Tok]) -> list[tuple[int, str]]:
    """Unqualified words that are not function calls, qualifiers or SQL keywords."""
    names = []
    for i, tok in enumerate(tokens):
        if tok.kind not in ("word", "quoted") or (tok.kind == "word" and tok.upper in SQL_WORDS):
            continue
        prev = tokens[i - 1] if i else None
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if (prev and prev.text == ".") or (nxt and nxt.text in (".", "(")):
            continue
        names.append((i, tok.ident))
    return names


def qualified_refs(tokens: list[Tok]) -> list[tuple[int, str, str]]:
    """(index of the name part, table, name) for each table.name reference."""
    refs = []
    for i in range(len(tokens) - 2):
        a, dot, b = tokens[i], tokens[i + 1], tokens[i + 2]
        before = tokens[i - 1] if i else None
        if (
            dot.text == "."
            and a.kind in ("word", "quoted")
            and b.kind in ("word", "quoted")
            and not (before and before.text == ".")
        ):
            refs.append((i + 2, a.ident, b.ident))
    return refs


def derived_bare_errors(item: Item, ctx: Context, in_aggregate: set[int]) -> list[str]:
    """Bare names in a derived metric must be derived or unambiguous metric names."""
    errors = []
    expr = item.expression
    unique_metrics: dict[str, int] = {}
    for names in ctx.names_by_table.values():
        for n, it in names.items():
            if it.kind == "metric":
                unique_metrics[n] = unique_metrics.get(n, 0) + 1
    for i, tok in enumerate(expr):
        if tok.kind != "word":
            continue
        prev = expr[i - 1] if i else None
        nxt = expr[i + 1] if i + 1 < len(expr) else None
        if (prev and prev.text == ".") or (nxt and nxt.text in (".", "(")):
            continue
        if tok.upper in SQL_WORDS:
            continue
        name = tok.ident
        if name == item.name:
            errors.append(f"{item.label}: refers to itself")
        elif name in ctx.derived or unique_metrics.get(name) == 1:
            if i in in_aggregate:
                errors.append(f"{item.label}: aggregates the metric {tok.text}; derived metrics cannot")
        elif unique_metrics.get(name, 0) > 1:
            errors.append(f"{item.label}: {tok.text} is ambiguous; qualify it with its table")
        else:
            errors.append(f"{item.label}: {tok.text} is not a metric or derived metric")
    if any(t.upper == "OVER" for t in expr):
        errors.append(f"{item.label}: derived metrics cannot use window functions")
    return errors


SQL_WORDS = {
    "AND", "OR", "NOT", "NULL", "TRUE", "FALSE", "IS", "IN", "CASE", "WHEN", "THEN",
    "ELSE", "END", "DISTINCT", "LIKE", "ILIKE", "BETWEEN", "AS", "INTERVAL", "OVER",
}


def refs_other_tables(refs: list[tuple[int, str, str]], table: str | None) -> bool:
    return any(t != table for _, t, _ in refs)


def summary(view: dict) -> str:
    kinds = [i.kind for i in view["items"]]
    derived = sum(1 for i in view["items"] if i.table is None)
    return (
        f"{len(view['tables'])} tables, {len(view['relationships'])} relationships, "
        f"{kinds.count('fact')} facts, {kinds.count('dimension')} dimensions, "
        f"{kinds.count('metric')} metrics ({derived} derived)"
    )


if __name__ == "__main__":
    sys.exit(main())
