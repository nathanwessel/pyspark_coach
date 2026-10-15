"""Server-side proprietary rules loader and narrow action-generation engine."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pyspark_coach.contracts import METRIC_NAMES, NotebookSignals


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    metric: str
    threshold: int = Field(default=0, ge=0)
    severity: Literal["info", "warning", "error"] = "warning"
    action: str = Field(min_length=5, max_length=250)
    rationale: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def known_metric(self):
        if self.metric not in METRIC_NAMES:
            raise ValueError("A rule references an unsupported aggregated metric")
        return self


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    rules: list[Rule] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_rules(self):
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate rule IDs in recipe")
        return self


def load_recipe(path: str | Path) -> Recipe:
    """Use ONLY on the private server. Never put the recipe in the customer client."""
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError("Configured private rules file does not exist")
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    return Recipe.model_validate(data)


def findings(recipe: Recipe, signals: NotebookSignals) -> list[dict]:
    """Expose actionable findings, not the recipe text or other rule definitions."""
    priority = {"error": 0, "warning": 1, "info": 2}
    hits = []
    for rule in recipe.rules:
        count = signals.metric(rule.metric)
        if count > rule.threshold:
            hits.append(
                {
                    "rule_id": rule.id,
                    "severity": rule.severity,
                    "observed_count": count,
                    "action": rule.action,
                    "why": rule.rationale,
                }
            )
    return sorted(hits, key=lambda hit: (priority[hit["severity"]], -hit["observed_count"], hit["rule_id"]))


def request_refactoring_plan(recipe: Recipe, signals: NotebookSignals) -> dict:
    found = findings(recipe, signals)
    return {
        "schema_version": 1,
        "disclosure": "Individual applicable recommendations are visible to the MCP client; the full private recipe is not returned.",
        "finding_count": len(found),
        "findings": found,
        "limitations": [
            "Static heuristics are not a proof of runtime behavior or semantic equivalence.",
            "Inspect and test generated edits locally before merging.",
            "No performance improvements are claimed without before/after benchmarks.",
        ],
    }


def validate_refactoring(recipe: Recipe, before: NotebookSignals, after: NotebookSignals) -> dict:
    """Report defensible *static* before/after outcomes, never invented speedups."""
    before_counts = {rule.id: before.metric(rule.metric) for rule in recipe.rules}
    after_counts = {rule.id: after.metric(rule.metric) for rule in recipe.rules}
    comparisons = []
    for rule in recipe.rules:
        b, a = before_counts[rule.id], after_counts[rule.id]
        if b == a:
            continue
        comparisons.append(
            {
                "rule_id": rule.id,
                "before": b,
                "after": a,
                "change": a - b,
                "status": "improved" if a < b else "regressed",
            }
        )
    return {
        "schema_version": 1,
        "metric_type": "static-analysis-only",
        "active_findings_before": len(findings(recipe, before)),
        "active_findings_after": len(findings(recipe, after)),
        "comparisons": comparisons,
        "improved_rule_count": sum(row["status"] == "improved" for row in comparisons),
        "regressed_rule_count": sum(row["status"] == "regressed" for row in comparisons),
        "runtime_benchmark_available": False,
        "semantic_equivalence_proven": False,
    }
