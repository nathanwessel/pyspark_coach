"""Smoke-check the real MCP SDK when the optional runtime is installed."""

import pytest

mcp = pytest.importorskip("mcp")

from pyspark_coach.engine import load_recipe  # noqa: E402
from pyspark_coach.mcp_server import create_mcp_server  # noqa: E402


def test_mcp_server_instantiation():
    server = create_mcp_server(load_recipe("config/recipe.example.yaml"))
    assert server is not None
