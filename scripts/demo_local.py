"""Server-side development demo using public example recipe, not a client integration."""

import json

from pyspark_coach.analyzer import inspect_notebook
from pyspark_coach.engine import load_recipe, request_refactoring_plan, validate_refactoring


def main():
    recipe = load_recipe("config/recipe.example.yaml")
    before = inspect_notebook("examples/messy_notebook.py")
    after = inspect_notebook("examples/improved_notebook.py")
    result = {
        "before_signals": before.model_dump(),
        "after_signals": after.model_dump(),
        "plan_before": request_refactoring_plan(recipe, before),
        "static_comparison": validate_refactoring(recipe, before, after),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
