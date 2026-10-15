"""Lossless notebook I/O: parse .py, Databricks .py and .ipynb files into cells and render them back.

Nothing here executes notebook code. Rendering an unmodified notebook reproduces the original text
(Databricks separators are normalized to the canonical ``# COMMAND ----------`` spelling).
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

NotebookFormat = Literal["databricks_py", "python", "ipynb"]
CellKind = Literal["code", "markdown", "magic", "raw"]

DATABRICKS_HEADER = "# Databricks notebook source"
DATABRICKS_SEPARATOR = "# COMMAND ----------"
MAX_NOTEBOOK_BYTES = 5_000_000

_SEPARATOR_RE = re.compile(r"(?m)^# COMMAND ----------[ \t]*$")
_MAGIC_LINE_RE = re.compile(r"^# MAGIC(?: |$)")
_LEAD_RE = re.compile(r"\A(?:[ \t]*\n)*")
_TRAIL_RE = re.compile(r"(?:\n[ \t]*)*\Z")


@dataclass
class Cell:
    kind: CellKind
    source: str
    # Markdown magic token for Databricks cells ("%md" or "%md-sandbox").
    md_magic: str | None = None
    # 1-based file line of the cell's first body line (.py formats only).
    start_line: int | None = None
    # Whitespace around the body in Databricks exports, preserved for round-tripping.
    lead: str = ""
    trail: str = ""
    raw_ipynb: dict | None = field(default=None, repr=False)

    @property
    def is_empty(self) -> bool:
        return not self.source.strip()

    def content_file_line(self, line: int) -> int | None:
        """File line for a 1-based line of ``source`` (None for ipynb)."""
        if self.start_line is None:
            return None
        offset = 1 if self.md_magic else 0
        return self.start_line + offset + line - 1


@dataclass
class Notebook:
    format: NotebookFormat
    cells: list[Cell]
    ipynb_document: dict | None = field(default=None, repr=False)
    ipynb_indent: int = 1

    def code_cells(self) -> list[tuple[int, Cell]]:
        return [(i, c) for i, c in enumerate(self.cells) if c.kind == "code" and not c.is_empty]

    def render(self) -> str:
        if self.format == "ipynb":
            return _render_ipynb(self)
        if self.format == "databricks_py":
            return _render_databricks(self)
        return self.cells[0].source if self.cells else ""

    def copy(self) -> Notebook:
        return copy.deepcopy(self)


def read_notebook(path: str | Path) -> Notebook:
    file = Path(path)
    if file.suffix.lower() not in (".py", ".ipynb"):
        raise ValueError("Only .py and .ipynb notebook files are supported")
    if file.stat().st_size > MAX_NOTEBOOK_BYTES:
        raise ValueError("Notebook is too large to inspect")
    text = file.read_text(encoding="utf-8")
    return parse_notebook(text, "ipynb" if file.suffix.lower() == ".ipynb" else None)


def write_notebook(notebook: Notebook, path: str | Path) -> None:
    Path(path).write_text(notebook.render(), encoding="utf-8")


def detect_format(text: str) -> NotebookFormat:
    stripped = text.lstrip()
    if stripped.startswith("{") and '"cells"' in text[:100_000]:
        return "ipynb"
    if text.startswith(DATABRICKS_HEADER):
        return "databricks_py"
    return "python"


def parse_notebook(text: str, fmt: NotebookFormat | None = None) -> Notebook:
    if len(text.encode("utf-8")) > MAX_NOTEBOOK_BYTES:
        raise ValueError("Notebook is too large to inspect")
    fmt = fmt or detect_format(text)
    if fmt == "ipynb":
        return _parse_ipynb(text)
    if fmt == "databricks_py":
        return _parse_databricks(text)
    return Notebook("python", [Cell("code", text, start_line=1)])


# ---------------------------------------------------------------- Databricks .py


def _parse_databricks(text: str) -> Notebook:
    header_end = text.find("\n")
    body_offset = len(text) if header_end == -1 else header_end + 1
    body = text[body_offset:]
    spans = []
    position = 0
    for match in _SEPARATOR_RE.finditer(body):
        spans.append((position, match.start()))
        position = match.end()
    spans.append((position, len(body)))
    cells: list[Cell] = []
    for start, end in spans:
        chunk = body[start:end]
        lead = _LEAD_RE.match(chunk).group(0)
        rest = chunk[len(lead) :]
        trail = _TRAIL_RE.search(rest).group(0) if rest else ""
        content = rest[: len(rest) - len(trail)] if trail else rest
        cell = _classify_databricks_chunk(content)
        cell.lead, cell.trail = lead, trail
        cell.start_line = text.count("\n", 0, body_offset + start + len(lead)) + 1
        cells.append(cell)
    return Notebook("databricks_py", cells)


def _classify_databricks_chunk(content: str) -> Cell:
    lines = content.split("\n")
    nonblank = [line for line in lines if line.strip()]
    if nonblank and all(_MAGIC_LINE_RE.match(line) for line in nonblank):
        stripped = [re.sub(r"^# MAGIC ?", "", line) for line in lines]
        first = stripped[0].strip()
        if first.startswith("%md"):
            token = first.split()[0]
            inline = first[len(token) :].strip()
            md_lines = ([inline] if inline else []) + stripped[1:]
            return Cell("markdown", "\n".join(md_lines), md_magic=token)
        return Cell("magic", "\n".join(stripped))
    return Cell("code", content)


def _render_databricks(notebook: Notebook) -> str:
    parts = []
    for cell in notebook.cells:
        if cell.kind == "markdown":
            lines = [cell.md_magic or "%md", *cell.source.split("\n")]
            body = "\n".join(f"# MAGIC {line}" if line else "# MAGIC" for line in lines)
        elif cell.kind == "magic":
            body = "\n".join(f"# MAGIC {line}" if line else "# MAGIC" for line in cell.source.split("\n"))
        else:
            body = cell.source
        parts.append(cell.lead + body + cell.trail)
    return DATABRICKS_HEADER + "\n" + DATABRICKS_SEPARATOR.join(parts)


# ---------------------------------------------------------------- ipynb


def _is_magic_only(source: str) -> bool:
    lines = [line.strip() for line in source.split("\n") if line.strip()]
    if not lines:
        return False
    if lines[0].startswith("%%"):
        return True
    return all(line.startswith(("%", "!", "#")) for line in lines) and any(
        line.startswith(("%", "!")) for line in lines
    )


def _parse_ipynb(text: str) -> Notebook:
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
        raise ValueError("Invalid ipynb: missing cells")
    indent_match = re.match(r"\{\s*\n( +)\"", text)
    cells = []
    for raw in data["cells"]:
        if not isinstance(raw, dict):
            raise ValueError("Invalid ipynb cell")
        source = raw.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not isinstance(source, str):
            raise ValueError("Invalid cell source")
        cell_type = raw.get("cell_type")
        if cell_type == "markdown":
            kind: CellKind = "markdown"
        elif cell_type == "code":
            kind = "magic" if _is_magic_only(source) else "code"
        else:
            kind = "raw"
        cells.append(Cell(kind, source, raw_ipynb=raw))
    document = {key: value for key, value in data.items() if key != "cells"}
    indent = len(indent_match.group(1)) if indent_match else 1
    return Notebook("ipynb", cells, ipynb_document=document, ipynb_indent=indent)


def _source_lines(source: str) -> list[str]:
    return source.splitlines(keepends=True)


def _render_ipynb(notebook: Notebook) -> str:
    rendered = []
    for cell in notebook.cells:
        if cell.raw_ipynb is not None:
            raw = dict(cell.raw_ipynb)
            original = raw.get("source", "")
            original_text = "".join(original) if isinstance(original, list) else original
            if original_text != cell.source:
                raw["source"] = _source_lines(cell.source)
            rendered.append(raw)
        elif cell.kind == "markdown":
            rendered.append({"cell_type": "markdown", "metadata": {}, "source": _source_lines(cell.source)})
        else:
            rendered.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": _source_lines(cell.source),
                }
            )
    document = {"cells": rendered, **(notebook.ipynb_document or {})}
    return json.dumps(document, indent=notebook.ipynb_indent, ensure_ascii=False) + "\n"
