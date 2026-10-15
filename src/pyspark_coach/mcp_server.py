"""Remote MCP service. Deploy only to infrastructure under recipe owner's control."""

import os

from mcp.server import MCPServer

from pyspark_coach.contracts import NotebookSignals
from pyspark_coach.engine import Recipe, load_recipe, request_refactoring_plan, validate_refactoring


def create_mcp_server(recipe: Recipe) -> MCPServer:
    server = MCPServer("PySpark Coach")

    @server.tool(name="get_refactoring_plan")
    def get_refactoring_plan(signals: NotebookSignals) -> dict:
        """Use aggregated notebook signals to return actionable PySpark refactoring guidance."""
        return request_refactoring_plan(recipe, signals)

    @server.tool(name="validate_refactoring")
    def compare_before_after(before: NotebookSignals, after: NotebookSignals) -> dict:
        """Compare local static metrics after refactoring; no source code transmitted."""
        return validate_refactoring(recipe, before, after)

    return server


def main() -> None:
    recipe_path = os.environ.get("PYSPARK_COACH_RECIPE_PATH")
    if not recipe_path:
        raise SystemExit("Set PYSPARK_COACH_RECIPE_PATH to a private server-only YAML file")
    recipe = load_recipe(recipe_path)
    server = create_mcp_server(recipe)
    transport = os.environ.get("PYSPARK_COACH_TRANSPORT", "stdio")
    if transport not in {"streamable-http", "stdio"}:
        raise SystemExit("PYSPARK_COACH_TRANSPORT must be streamable-http or stdio")
    # IMPORTANT: HTTP must sit behind TLS + auth (e.g. OAuth-capable API gateway)
    # BEFORE the endpoint is accessible to customers. This MVP has no built-in auth.
    if transport == "streamable-http":
        if os.environ.get("PYSPARK_COACH_GATEWAY_AUTH_CONFIRMED") != "YES":
            raise SystemExit(
                "HTTP mode refused: deploy behind authenticated TLS gateway and set "
                "PYSPARK_COACH_GATEWAY_AUTH_CONFIRMED=YES"
            )
        server.run(transport="streamable-http", stateless_http=True, json_response=True)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
