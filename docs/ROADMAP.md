# 🗺️ PySpark Coach roadmap (next session)

Status: prototype imported and verified (13 tests pass against mcp 2.3.0; in-process MCP
discovery + `get_refactoring_plan` call confirmed). `src/pyspark_coach/notebook.py` added:
lossless Databricks `.py` / `.ipynb` / `.py` reader + renderer with file-line mapping.
A draft v2 signals contract (16 new PySpark metrics) is parked outside the repo pending the analyzer.

## Next tasks (~3.5h)
1. **Analyzer v2** (60m): line-level local findings (cell, line, file line, symbol, suggestion),
   signals derived from findings; new detectors: wildcard/direct `functions` imports, joins
   missing `how`, cross joins, `collect`/`toPandas`, debug `display/show/print`, Python UDFs,
   `withColumn` chains/loops, backslash continuations, long lines, `.rdd`, `count()==0`,
   `repartition(1)`/`coalesce(1)`, `inferSchema`, unreleased caches, f-string `spark.sql`.
   Fix: `", ".join(...)` currently counted as a DataFrame join.
2. **Auto-fixer** (60m): idempotent, parse-checked rewrites: `_df`/`_dict` renames (scope-safe),
   `from pyspark.sql import functions as F` + `F.x` calls, aliased/qualified/ordered joins with
   explicit `how`, emoji headings, hoist `%pip` to top, `count()==0` → `isEmpty()`.
3. **Local MCP server any AI can connect to** (45m, stdio): `inspect_notebook`, `get_refactoring_plan`
   (with exact locations), `apply_safe_fixes` (diff first), `validate_refactoring`; prompt
   `clean_up_notebook`; resource `pyspark-coach://style-guide`. Rules backend: packaged public
   recipe, local private recipe, or remote rules server (counts only leave the machine).
4. **Rules server hardening** (30m): bearer-token auth middleware (replaces the "YES" flag),
   64 KB body limit, allowed hosts, tool annotations, `metric` in findings, HTTP end-to-end test.
5. **Connect-any-AI docs** (20m): `.mcp.json`, configs for Claude Code/Desktop, VS Code Copilot,
   Cursor, Codex, Gemini CLI; update README/ARCHITECTURE/AGENTS; fix 78 ruff errors.
6. **Finale demo** (25m): new messy notebook → script launches the MCP server over stdio, calls
   the tools, saves the cleaned notebook to `examples/`; GitHub Actions CI (ruff + pytest).
