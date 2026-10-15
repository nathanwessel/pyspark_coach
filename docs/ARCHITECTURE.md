# 🏗️ Architecture and trust boundaries

## 🔍 Customer-side notebook analysis

`pyspark-coach-inspect` runs on the customer's machine (or in their Databricks/VS Code environment). It reads `.py` Databricks exports and `.ipynb` notebooks without executing the code. Its output is a strictly typed JSON payload of fixed numeric counts and a notebook-format enum. It deliberately does **not** include source lines, variable identifiers, catalog/table names, credentials, notebook paths, or snippets.

> Local static inspection is heuristic. It cannot prove Spark types, full join correctness, performance gains, or output equivalence. Unsupported languages and magics can reduce coverage.

## 🔐 Privately hosted MCP service

A remote MCP server (MCP Python SDK v2, Streamable HTTP) runs in infrastructure operated by the recipe owner. It loads `PYSPARK_COACH_RECIPE_PATH` once from a **private** YAML file. That file is never registered as an MCP resource or exposed as a tool argument or result.

Its tools:

| Tool | Request | Response |
| --- | --- | --- |
| `get_refactoring_plan` | Fixed-schema notebook signals | Relevant, bounded refactoring actions with aggregate counts |
| `validate_refactoring` | Before/after notebook signals | Changes in static counts, improved/regressed rules |

The model/client applies edits locally and runs its own tests. This MVP does **not** rewrite code automatically; Claude Code/Copilot/Genie must be prompted to apply changes. Standup/resume metrics are defensible **static** counts only, never fabricated acceleration or cost savings.

## 🚧 Security work required before production

1. Require HTTPS and authentication/authorization at an API gateway or implement OAuth in the MCP service. **The prototype has no built-in auth. HTTP mode has an explicit gateway-confirmation setting but **the flag is not authentication**. Do not expose it publicly.**
2. Set tenant-specific policy/quotas, request size limits, rate limits, and audit logging with payload redaction at the gateway. Protect authorization tokens and use least-privilege access.
3. Validate privacy policies, retention, network egress, and customer consent; metadata itself can be sensitive in context.
4. Use signed releases and separate private recipe storage from customer-distributed code. CI must never package private rules or print their contents.
5. Test all supported client adapters (Claude Code, VS Code GitHub Copilot, Databricks Genie Code) and their enterprise MCP/network restrictions; integration is **not yet validated** in this MVP.
6. Consider result watermarking, per-tenant rule access, and response rate limiting. Individual returned actions can reveal their associated rule; perfect secrecy is impossible when an assistant must learn and apply the rule.
7. Prevent accidental source-code exfiltration by checking transport payloads and telemetry in a real end-to-end environment.

## 📊 Deliberately deferred

- Stateful auth, deployment, billing and multi-tenancy.
- RAG/vector search for nuanced engineering decisions. The deterministic engine is intentionally first; private RAG can be layered onto the server later.
- Semantic refactoring and Spark execution benchmarking. Require representative execution to justify performance claims.
- `.dbc` archives, SQL/R/Scala notebook language support and robust AST/CST rewrites.
