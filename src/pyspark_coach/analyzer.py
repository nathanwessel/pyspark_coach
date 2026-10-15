"""Conservative static notebook inspection. Never executes notebook code."""

import ast
import json
import re
from pathlib import Path

from pyspark_coach.contracts import NotebookSignals

DATAFRAME_METHODS = frozenset(
    {
        "select", "selectExpr", "filter", "where", "join", "withColumn",
        "withColumnRenamed", "groupBy", "agg", "orderBy", "sort", "drop",
        "dropDuplicates", "distinct", "limit", "union", "unionByName",
        "repartition", "coalesce", "cache", "persist", "alias", "transform",
        "withColumns", "fillna", "na", "toDF",
    }
)
DATAFRAME_SOURCE_METHODS = frozenset({"sql", "table", "range", "createDataFrame", "read", "readStream"})
REQUIRED_FUNCTION_ALIASES = frozenset({"min", "max", "avg", "mean", "sum", "abs", "round", "filter"})
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
# Conservative test for common emoji glyphs; deliberately does not claim full Unicode coverage.
EMOJI_RE = re.compile(r"^[\U0001F000-\U0001FAFF\u2600-\u27BF\u00a9\u00ae]")
PIP_RE = re.compile(r"^\s*(?:#\s*MAGIC\s*)?%pip\s+", re.IGNORECASE)
SHARED_MODULE_RE = re.compile(r"(?:^|[._])(?:shared|common|utils|utilities)(?:$|[._])", re.IGNORECASE)


def _is_call(node: ast.AST, method: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method


def _name_targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for part in node.elts for name in _name_targets(part)]
    return []


def _spark_source(node: ast.AST) -> bool:
    if not isinstance(node, (ast.Call, ast.Attribute)):
        return False
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in DATAFRAME_SOURCE_METHODS:
            base = node.func.value
            while isinstance(base, (ast.Call, ast.Attribute)):
                base = base.func.value if isinstance(base, ast.Call) and isinstance(base.func, ast.Attribute) else (base.value if isinstance(base, ast.Attribute) else base.func)
            if isinstance(base, ast.Name) and base.id == "spark":
                return True
        return _spark_source(node.func)
    return _spark_source(node.value)


def _derived_df(node: ast.AST, known: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return (
            _spark_source(node)
            or node.func.attr in DATAFRAME_METHODS
            and _derived_df(node.func.value, known)
        )
    return False


def _is_dictionary(node: ast.AST) -> bool:
    return isinstance(node, (ast.Dict, ast.DictComp)) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict"
    )


def _alias_id(node: ast.AST, known_aliases: dict[str, str]) -> str | None:
    if _is_call(node, "alias") and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    if isinstance(node, ast.Name):
        return known_aliases.get(node.id)
    return None


def _comparison_root(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        cur = node
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        return cur.id if isinstance(cur, ast.Name) else None
    if _is_call(node, "col") and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        name = node.args[0].value
        return name.split(".", 1)[0] if "." in name else None
    return None


def _find_comparisons(node: ast.AST) -> list[ast.Compare]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Eq)]


def _join_order(node: ast.Call, alias_names: dict[str, str]) -> str:
    left = _alias_id(node.func.value, alias_names)
    right = _alias_id(node.args[0], alias_names) if node.args else None
    cond = next((v for keyword in node.keywords if keyword.arg == "on" for v in [keyword.value]), None)
    if cond is None and len(node.args) > 1:
        cond = node.args[1]
    if not left or not right or cond is None or left == right:
        return "unverifiable"
    orientations = []
    for compare in _find_comparisons(cond):
        lhs, rhs = _comparison_root(compare.left), _comparison_root(compare.comparators[0])
        if lhs == left and rhs == right:
            orientations.append("correct")
        elif lhs == right and rhs == left:
            orientations.append("reversed")
    if not orientations:
        return "unverifiable"
    return "reversed" if "reversed" in orientations else "correct"


def _is_pip(line: str) -> bool:
    return bool(PIP_RE.match(line))


def _sanitize(code: str) -> str:
    """Replace notebook magics with no-op lines, preserving relative Python line locations."""
    sanitized = []
    cell_magic = False
    for line in code.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("%%"):
            cell_magic = True
        if cell_magic or stripped.startswith(("%", "!")) or _is_pip(line):
            sanitized.append("pass")
        else:
            sanitized.append(line)
    return "\n".join(sanitized)


def _split_databricks_python(source: str) -> list[tuple[str, str]]:
    chunks = re.split(r"(?m)^# COMMAND ----------\s*$", source)
    result = []
    for chunk in chunks:
        magic_lines = re.findall(r"(?m)^\s*# MAGIC\s?(.*)$", chunk)
        if magic_lines and all(not line.strip() or line.lstrip().startswith(("%md", "#")) for line in magic_lines):
            markdown = "\n".join(line for line in magic_lines if not line.lstrip().startswith("%md"))
            result.append(("markdown", markdown))
        else:
            # Strip lines representing foreign-language cells; not valid Python.
            code_lines = []
            for line in chunk.splitlines():
                if line.lstrip().startswith("# MAGIC"):
                    magic = re.sub(r"^\s*# MAGIC\s?", "", line)
                    code_lines.append(magic if _is_pip(magic) else "# " + magic)
                else:
                    code_lines.append(line)
            result.append(("code", "\n".join(code_lines)))
    return [(kind, content) for kind, content in result if content.strip()]


def _read_notebook(path: Path) -> tuple[str, list[tuple[str, str]]]:
    if path.suffix.lower() == ".ipynb":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
            raise ValueError("Invalid ipynb: missing cells")
        cells = []
        for cell in data["cells"]:
            if cell.get("cell_type") not in ("code", "markdown"):
                continue
            content = cell.get("source", "")
            if isinstance(content, list):
                content = "".join(content)
            if not isinstance(content, str):
                raise ValueError("Invalid cell source")
            cells.append((cell["cell_type"], content))
        return "ipynb", cells
    if path.suffix.lower() != ".py":
        raise ValueError("Only .py and .ipynb notebook files are supported")
    source = path.read_text(encoding="utf-8")
    if "Databricks notebook source" in source[:200]:
        return "databricks_py", _split_databricks_python(source)
    return "python", [("code", source)]


def inspect_notebook(path: str | Path) -> NotebookSignals:
    """Inspect code locally and return only a safe, fixed-shape aggregate record."""
    notebook_path = Path(path)
    fmt, cells = _read_notebook(notebook_path)
    code_cells = [content for kind, content in cells if kind == "code"]
    markdown_cells = [content for kind, content in cells if kind == "markdown"]
    headings: list[tuple[int, str]] = []
    for content in markdown_cells:
        for line in content.splitlines():
            match = HEADING_RE.match(line)
            if match:
                headings.append((len(match.group(1)), match.group(2)))

    parsed: list[ast.AST] = []
    parse_errors = 0
    late_pip = 0
    seen_non_setup = False
    for content in code_cells:
        for line in content.splitlines():
            stripped = line.strip()
            if _is_pip(line):
                if seen_non_setup:
                    late_pip += 1
            elif stripped and not stripped.startswith(("#", "%", "!")):
                if not (stripped.startswith(("import ", "from "))):
                    seen_non_setup = True
        try:
            parsed.append(ast.parse(_sanitize(content)))
        except SyntaxError:
            parse_errors += 1

    assignments: list[tuple[list[str], ast.AST]] = []
    alias_names: dict[str, str] = {}
    imports_without_alias = 0
    shared_imports_late = 0
    encountered_other_import = False
    joins: list[ast.Call] = []
    for tree in parsed:
        ordered_imports = sorted(
            (n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))),
            key=lambda n: n.lineno,
        )
        for import_node in ordered_imports:
            module_names = (
                [alias.name for alias in import_node.names]
                if isinstance(import_node, ast.Import)
                else [import_node.module or ""]
            )
            is_shared = any(SHARED_MODULE_RE.search(name) for name in module_names)
            if is_shared and encountered_other_import:
                shared_imports_late += 1
            if not is_shared:
                encountered_other_import = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                assignments.append(([name for target in node.targets for name in _name_targets(target)], node.value))
            elif isinstance(node, ast.AnnAssign):
                assignments.append((_name_targets(node.target), node.value))
            elif isinstance(node, ast.ImportFrom) and node.module == "pyspark.sql.functions":
                imports_without_alias += sum(
                    1 for imported in node.names
                    if imported.name in REQUIRED_FUNCTION_ALIASES and imported.asname is None
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join":
                joins.append(node)

    known_df: set[str] = set()
    for _ in range(len(assignments) + 1):
        previous = len(known_df)
        for names, value in assignments:
            if value is not None and _derived_df(value, known_df):
                known_df.update(names)
            alias = _alias_id(value, alias_names) if value is not None else None
            if alias:
                alias_names.update({name: alias for name in names})
        if len(known_df) == previous:
            break

    dict_vars = {name for names, value in assignments if value is not None and _is_dictionary(value) for name in names}
    missing_alias = 0
    reversed_joins = 0
    unverifiable = 0
    for join in joins:
        if not _alias_id(join.func.value, alias_names) or not join.args or not _alias_id(join.args[0], alias_names):
            missing_alias += 1
        order = _join_order(join, alias_names)
        if order == "reversed":
            reversed_joins += 1
        if order == "unverifiable":
            unverifiable += 1

    return NotebookSignals(
        notebook_format=fmt,
        code_cells=len(code_cells),
        markdown_cells=len(markdown_cells),
        dataframe_assignments=len(known_df),
        dataframe_bad_suffix=sum(not name.endswith("_df") for name in known_df),
        dictionary_assignments=len(dict_vars),
        dictionary_bad_suffix=sum(not name.endswith("_dict") for name in dict_vars),
        joins=len(joins),
        joins_missing_alias=missing_alias,
        join_operand_order_reversed=reversed_joins,
        join_operand_order_unverifiable=unverifiable,
        headings=len(headings),
        headings_missing_emoji=sum(not EMOJI_RE.match(title) for _, title in headings),
        sections=sum(level == 1 for level, _ in headings),
        subsections=sum(level >= 2 for level, _ in headings),
        missing_section_structure=int(bool(code_cells) and not any(level == 1 for level, _ in headings)),
        missing_subsection_structure=int(bool(code_cells) and not any(level >= 2 for level, _ in headings)),
        shared_utilities_imported_late=shared_imports_late,
        functions_imported_without_safe_alias=imports_without_alias,
        late_pip_installs=late_pip,
        parse_errors=parse_errors,
    )
