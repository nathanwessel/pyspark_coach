import json

import pytest
from pydantic import ValidationError

from pyspark_coach.analyzer import inspect_notebook
from pyspark_coach.contracts import NotebookSignals


def test_messy_vs_improved_examples():
    before = inspect_notebook("examples/messy_notebook.py")
    after = inspect_notebook("examples/improved_notebook.py")
    assert before.notebook_format == "databricks_py"
    assert before.dataframe_bad_suffix >= 3
    assert after.dataframe_bad_suffix == 0
    assert before.dictionary_bad_suffix == 1
    assert after.dictionary_bad_suffix == 0
    assert before.joins_missing_alias == 1
    assert after.joins_missing_alias == 0
    assert after.join_operand_order_reversed == 0
    assert after.join_operand_order_unverifiable == 0
    assert before.headings_missing_emoji == 4
    assert after.headings_missing_emoji == 0
    assert before.functions_imported_without_safe_alias == 3
    assert after.functions_imported_without_safe_alias == 0
    assert before.late_pip_installs == 1
    assert after.late_pip_installs == 0


def test_reversed_join_operands(tmp_path):
    file = tmp_path / "join.py"
    file.write_text(
        'left_df = spark.table("l")\n'
        'right_df = spark.table("r")\n'
        'result_df = left_df.alias("l").join(right_df.alias("r"), '
        'F.col("r.id") == F.col("l.id"), "inner")\n'
    )
    result = inspect_notebook(file)
    assert result.joins == 1
    assert result.join_operand_order_reversed == 1


def test_ipynb_and_no_source_leak(tmp_path):
    secret = "ACME_CUSTOMER_SSN_DATABASE"
    path = tmp_path / "secret.ipynb"
    path.write_text(json.dumps({"cells": [
        {"cell_type": "markdown", "source": ["# 🚀 Intro\n", "## 🧰 Work"]},
        {"cell_type": "code", "source": [f'{secret}_df = spark.table("private.db")']},
    ]}))
    output = inspect_notebook(path).model_dump_json()
    assert "ACME" not in output
    assert "private" not in output
    assert "secret" not in output
    assert "🚀" not in output


def test_strict_rejects_source_fields():
    raw = inspect_notebook("examples/messy_notebook.py").model_dump()
    raw["source_code"] = "print('something secret')"
    with pytest.raises(ValidationError):
        NotebookSignals.model_validate(raw)


def test_consistency_validation():
    raw = inspect_notebook("examples/messy_notebook.py").model_dump()
    raw["joins_missing_alias"] = 100
    with pytest.raises(ValidationError):
        NotebookSignals.model_validate(raw)


def test_never_executes_notebook(tmp_path):
    path = tmp_path / "unsafe.py"
    marker = tmp_path / "should_not_exist"
    path.write_text(f'open("{marker}", "w").write("executed")\norders_df = spark.table("demo.orders")')
    assert inspect_notebook(path).dataframe_assignments == 1
    assert not marker.exists()


def test_subsection_required_and_shared_import_order(tmp_path):
    file = tmp_path / "order.py"
    file.write_text('import os\nfrom shared.utils import load_df\norders_df = spark.table("orders")')
    result = inspect_notebook(file)
    assert result.missing_section_structure == 1
    assert result.missing_subsection_structure == 1
    assert result.shared_utilities_imported_late == 1


def test_spark_no_reference_spurious_dataframe(tmp_path):
    file = tmp_path / "nonspark.py"
    file.write_text('metadata = object()\nresult = metadata.select("x")')
    result = inspect_notebook(file)
    assert result.dataframe_assignments == 0
