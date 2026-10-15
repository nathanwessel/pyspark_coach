"""Strict, fixed-schema contract: client never sends notebook source or identifiers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NotebookSignals(BaseModel):
    """Aggregated metrics only: no code, paths, names, literals, or comments."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    notebook_format: Literal["databricks_py", "python", "ipynb"]
    code_cells: int = Field(ge=0, le=100_000)
    markdown_cells: int = Field(ge=0, le=100_000)
    dataframe_assignments: int = Field(ge=0, le=100_000)
    dataframe_bad_suffix: int = Field(ge=0, le=100_000)
    dictionary_assignments: int = Field(ge=0, le=100_000)
    dictionary_bad_suffix: int = Field(ge=0, le=100_000)
    joins: int = Field(ge=0, le=100_000)
    joins_missing_alias: int = Field(ge=0, le=100_000)
    join_operand_order_reversed: int = Field(ge=0, le=100_000)
    join_operand_order_unverifiable: int = Field(ge=0, le=100_000)
    headings: int = Field(ge=0, le=100_000)
    headings_missing_emoji: int = Field(ge=0, le=100_000)
    sections: int = Field(ge=0, le=100_000)
    subsections: int = Field(ge=0, le=100_000)
    missing_section_structure: int = Field(ge=0, le=1)
    missing_subsection_structure: int = Field(ge=0, le=1)
    shared_utilities_imported_late: int = Field(ge=0, le=100_000)
    functions_imported_without_safe_alias: int = Field(ge=0, le=100_000)
    late_pip_installs: int = Field(ge=0, le=100_000)
    parse_errors: int = Field(ge=0, le=100_000)

    @model_validator(mode="after")
    def plausible_counts(self):
        comparisons = (
            (self.dataframe_bad_suffix, self.dataframe_assignments),
            (self.dictionary_bad_suffix, self.dictionary_assignments),
            (self.joins_missing_alias, self.joins),
            (self.join_operand_order_reversed + self.join_operand_order_unverifiable, self.joins),
            (self.headings_missing_emoji, self.headings),
            (self.sections + self.subsections, self.headings),
        )
        if any(bad > total for bad, total in comparisons):
            raise ValueError("Inconsistent notebook metric counts")
        return self

    def metric(self, name: str) -> int:
        value = getattr(self, name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("Rule attempted to read a non-count field")
        return value


METRIC_NAMES = frozenset(
    name
    for name, field in NotebookSignals.model_fields.items()
    if field.annotation is int
)
