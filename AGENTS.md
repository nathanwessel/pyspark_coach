# 🧭 AI-agent guidance (public, no proprietary rules)

This repository implements PySpark Coach. This file contains no private recipe instructions.

If asked to refactor a customer's Databricks/PySpark notebook:

1. Run `pyspark-coach-inspect path/to/notebook.py` **inside the customer's environment**. Never send full notebook source, source lines, column/table names, local file paths, secrets, or free-form code strings to the remote rules service.
2. Send the resulting **strict numeric JSON** to the remote `get_refactoring_plan` MCP tool. Do not query the private recipe directly.
3. Apply the returned recommendations **locally**, respecting the customer's tests and preserving behavior. If uncertain, request review instead of claiming correctness.
4. Inspect the edited file locally, call `validate_refactoring` with before/after aggregate signals, and report measured static findings only.
5. Run local tests or Databricks output-comparison checks. Never claim performance improvement without representative before/after Spark benchmarks, or semantic equivalence without relevant validation.

When an endpoint, authorization, or dependency is missing, say so clearly rather than fabricating findings. Never configure the prototype's unauthenticated HTTP mode for external access.
