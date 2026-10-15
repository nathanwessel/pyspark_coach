import json

import pytest
from pydantic import ValidationError

from pyspark_coach.analyzer import inspect_notebook
from pyspark_coach.engine import Recipe, findings, load_recipe, request_refactoring_plan, validate_refactoring


def test_plan_and_validation():
    recipe = load_recipe("config/recipe.example.yaml")
    before = inspect_notebook("examples/messy_notebook.py")
    after = inspect_notebook("examples/improved_notebook.py")
    plan = request_refactoring_plan(recipe, before)
    assert plan["finding_count"] >= 5
    assert any(row["rule_id"] == "df_suffix" for row in plan["findings"])
    assert not any("rules:" in str(val) for val in plan.values())
    result = validate_refactoring(recipe, before, after)
    assert result["active_findings_after"] < result["active_findings_before"]
    assert result["improved_rule_count"] >= 5
    assert result["regressed_rule_count"] == 0
    assert result["runtime_benchmark_available"] is False
    assert result["semantic_equivalence_proven"] is False
    # No notebook paths, literals, proprietary recipe, or source in transport responses.
    serialized = json.dumps(result)
    assert "demo.orders" not in serialized
    assert "examples/" not in serialized


def test_recipe_rejects_unknown_metric():
    with pytest.raises(ValidationError):
        Recipe.model_validate({"version": 1, "rules": [
            {"id": "unknown", "metric": "original_source_code", "action": "Do something safe", "rationale": "A valid reason"}
        ]})


def test_recipe_duplicate_rule_rejected():
    rule = {"id": "a_rule", "metric": "joins", "action": "Do something safe", "rationale": "A valid reason"}
    with pytest.raises(ValidationError):
        Recipe.model_validate({"version": 1, "rules": [rule, rule]})


def test_no_arbitrary_code_executed(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text('!!python/object/apply:os.system ["touch /tmp/pyspark_coach_was_executed"]')
    with pytest.raises(Exception):
        load_recipe(path)
