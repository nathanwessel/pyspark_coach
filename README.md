# 🧠 PySpark Coach — Private Recipe MCP Prototype

**MVP goal:** give Claude Code, GitHub Copilot, or Databricks Genie Code actionable PySpark notebook guidance using a **private YAML rules file** without uploading customer notebook source. A customer-side inspector sends **aggregated, fixed-schema metrics only** to an MCP server. The model applies edits locally; the server never receives full code.

> **Prototype, not production ready.** No server authentication is implemented. HTTP mode refuses to start without an explicit acknowledgement that an authenticated TLS gateway is configured. Deploy behind HTTPS with auth before permitting external clients. The private recipe is not committed or distributed. A response can reveal the particular recommendation being applied—**no design can promise absolute rule secrecy**.

## ⚡ Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q

# Demo: inspect the two example notebooks and compare static violations
python scripts/demo_local.py

# Customer-side, entirely local; no network request
pyspark-coach-inspect examples/messy_notebook.py --pretty
pyspark-coach-inspect examples/improved_notebook.py --pretty
```

The server code targets the current MCP Python SDK v2 (`mcp>=2.3,<3`). The MCP transport could not be exercised in the offline build environment; verify tool discovery and invocation after installing dependencies.

For a **server-side development demo only**, create a copy of the **public example rules** in a private location, not in the customer-released package:

```bash
mkdir -p /tmp/pyspark-coach-private
cp config/recipe.example.yaml /tmp/pyspark-coach-private/recipe.yaml
export PYSPARK_COACH_RECIPE_PATH=/tmp/pyspark-coach-private/recipe.yaml
# Local-process demo; do not distribute the recipe to customers.
export PYSPARK_COACH_TRANSPORT=stdio
pyspark-coach-mcp
```

The server MCP tools are `get_refactoring_plan(signals)` and `validate_refactoring(before, after)`. For a remotely hosted service, configure a trusted authenticated TLS gateway, then set `PYSPARK_COACH_TRANSPORT=streamable-http` and `PYSPARK_COACH_GATEWAY_AUTH_CONFIRMED=YES`. HTTP mode deliberately refuses to start without the opt-in. The environment flag **does not implement authentication**; it only prevents accidental exposure. Never point an MCP client at the local private recipe server in a customer's workspace.

## 🧩 Conceptual workflow

```text
Customer's notebook (.py or .ipynb)
      │ (local only)
      ▼
Local static analyzer — outputs fixed JSON counts
      │ (no source code, names, paths or literals)
      ▼
Authenticated remote MCP endpoint (production requirement)
      │
      ├── Private YAML recipe (server only)
      └── Private rules engine
      │
      ▼
Relevant recommendation(s) only
      │
      ▼
Claude/Copilot/Genie Code edits notebook in customer's environment
      │
      ▼
Local inspector reruns → MCP validation → static before/after report
```

## 🔎 Demo rule signals

The local inspector currently measures: DataFrame `_df` suffixes, dictionary `_dict` suffixes, explicit join aliasing, statically detectable reversed join predicates, Markdown sections/subsections and emoji prefixes, shared-utility import ordering (heuristic), aliased Spark SQL function imports, late `%pip` commands, and parse failures. These checks are **conservative heuristics**; absent findings are not proof of compliance. `join_operand_order_unverifiable` distinguishes cases where the local analyzer cannot establish join ordering.

Your actual proprietary YAML is **not included**. `config/recipe.example.yaml` is a public, intentionally non-secret demo to verify the transport. You can add private rules when deploying behind your own infrastructure.

## 🔒 Security, customer privacy, and product limitations

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for trust boundaries, deployment protections, and what this prototype intentionally does not solve. No customer production notebook should be shared with an unauthenticated demonstration endpoint.

## ✅ Acceptance criteria for this MVP

- A customer can inspect an example notebook without Spark, Databricks, or notebook execution.
- The strict JSON record contains no source strings or identifiers, and unknown source-related fields are rejected.
- The server filters a private rule set and returns actionable findings **only when triggered**.
- Before/after counts show actionable static changes without claiming performance improvements or behavioral equivalence.
- Tests cover obvious formatting, rule contract enforcement, reversed join operands, the source-text privacy boundary, and no code execution.

## 🌱 Next iterations

Secure remote deployment, Claude Code connector demonstration, Databricks/VS Code workflows, a robust Python CST refactoring adapter, dynamic Spark verification, and optional server-private RAG for difficult architectural decisions.
