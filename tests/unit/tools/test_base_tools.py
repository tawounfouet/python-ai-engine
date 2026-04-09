"""
Tests pour BaseTool et les outils concrets intégrés.

Couvre :
  - BaseTool : contrat ABC, définition, __call__
  - CalculatorTool : expressions valides, invalides, sécurité
  - DuckDuckGoSearchTool : comportement offline / erreurs réseau
  - HttpGetTool / HttpPostTool : comportement offline / erreurs
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ai_engine.tools import (
    BaseTool,
    CalculatorTool,
    DuckDuckGoSearchTool,
    HttpGetTool,
    HttpPostTool,
    SerperSearchTool,
)
from ai_engine.types import SkillCategory, ToolType


# ══════════════════════════════════════════════
# BaseTool tests
# ══════════════════════════════════════════════


class TestBaseTool:
    """Tests pour BaseTool ABC."""

    def test_abstract_key_required(self) -> None:
        with pytest.raises(TypeError, match="must define a non-empty 'key'"):

            class NoKey(BaseTool):
                key = ""

                def run(self, **kwargs: Any) -> str:
                    return ""  # noqa: E704

    def test_concrete_tool_instantiable(self) -> None:
        calc = CalculatorTool()
        assert calc.key == "calculator"

    def test_definition_property(self) -> None:
        calc = CalculatorTool()
        defn = calc.definition
        assert defn.key == "calculator"
        assert defn.name == "Calculator"
        assert defn.tool_type == ToolType.FUNCTION
        assert "properties" in defn.parameters_schema
        assert "expression" in defn.parameters_schema["properties"]

    def test_get_function_schema(self) -> None:
        calc = CalculatorTool()
        schema = calc.get_function_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculator"
        assert "parameters" in schema["function"]

    def test_call_syntax(self) -> None:
        calc = CalculatorTool()
        result = calc(expression="1+1")
        assert result == "2"

    def test_repr(self) -> None:
        calc = CalculatorTool()
        assert "calculator" in repr(calc)

    async def test_arun_delegates_to_run(self) -> None:
        calc = CalculatorTool()
        result = await calc.arun(expression="3*3")
        assert result == "9"


# ══════════════════════════════════════════════
# CalculatorTool tests
# ══════════════════════════════════════════════


class TestCalculatorTool:
    """Tests pour CalculatorTool."""

    @pytest.fixture
    def calc(self) -> CalculatorTool:
        return CalculatorTool()

    def test_basic_addition(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="1 + 1") == "2"

    def test_basic_subtraction(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="10 - 4") == "6"

    def test_multiplication(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="3 * 7") == "21"

    def test_division(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="10 / 4") == "2.5"

    def test_power(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="2 ** 10") == "1024"

    def test_sqrt(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="sqrt(144)") == "12"

    def test_pi_constant(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="round(pi, 4)")
        assert result == "3.1416"

    def test_float_result(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="1 / 3")
        assert "0.333" in result

    def test_integer_result_no_decimal(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="sqrt(4)")
        assert result == "2"

    def test_zero_division(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="1 / 0")
        assert "Error" in result
        assert "zero" in result.lower()

    def test_empty_expression(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="")
        assert "Error" in result

    def test_forbidden_characters(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="__import__('os')")
        assert "Error" in result

    def test_forbidden_builtins_blocked(self, calc: CalculatorTool) -> None:
        # open() n'est pas dans la liste blanche
        result = calc.run(expression="open('file')")
        assert "Error" in result

    def test_nested_expressions(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="(2 + 3) * (4 - 1)")
        assert result == "15"

    def test_log(self, calc: CalculatorTool) -> None:
        result = calc.run(expression="log10(1000)")
        assert result == "3"

    def test_min_max(self, calc: CalculatorTool) -> None:
        assert calc.run(expression="min(5, 3, 8)") == "3"
        assert calc.run(expression="max(5, 3, 8)") == "8"


# ══════════════════════════════════════════════
# DuckDuckGoSearchTool tests
# ══════════════════════════════════════════════


class TestDuckDuckGoSearchTool:
    """Tests pour DuckDuckGoSearchTool (mock réseau)."""

    @pytest.fixture
    def tool(self) -> DuckDuckGoSearchTool:
        return DuckDuckGoSearchTool(max_results=3)

    def test_key_and_type(self, tool: DuckDuckGoSearchTool) -> None:
        assert tool.key == "web_search"
        assert tool.tool_type == ToolType.API

    def test_returns_results_on_success(self, tool: DuckDuckGoSearchTool) -> None:
        mock_response = {
            "AbstractText": "Python is a programming language.",
            "AbstractURL": "https://python.org",
            "RelatedTopics": [
                {"Text": "Python 3 tutorial", "FirstURL": "https://docs.python.org"},
                {"Text": "Python packages", "FirstURL": "https://pypi.org"},
            ],
        }
        mock_read = MagicMock()
        mock_read.read.return_value = json.dumps(mock_response).encode()
        mock_read.status = 200
        mock_read.__enter__ = lambda s: s
        mock_read.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_read):
            result = tool.run(query="Python")

        assert "Python is a programming language" in result
        assert "python.org" in result

    def test_no_results_returns_message(self, tool: DuckDuckGoSearchTool) -> None:
        empty_response = {"AbstractText": "", "RelatedTopics": []}
        mock_read = MagicMock()
        mock_read.read.return_value = json.dumps(empty_response).encode()
        mock_read.status = 200
        mock_read.__enter__ = lambda s: s
        mock_read.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_read):
            result = tool.run(query="xyzzy_nonexistent")

        assert "No results found" in result

    def test_network_error_returns_error_message(
        self, tool: DuckDuckGoSearchTool
    ) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
        ):
            result = tool.run(query="Python")
        assert "Error" in result


# ══════════════════════════════════════════════
# SerperSearchTool tests
# ══════════════════════════════════════════════


class TestSerperSearchTool:
    def test_missing_api_key_returns_error(self) -> None:
        # S'assurer qu'aucune clé n'est dans l'env
        with patch.dict("os.environ", {}, clear=True):
            tool = SerperSearchTool(api_key="")
            result = tool.run(query="test")
        assert "Error" in result
        assert "Serper API key" in result

    def test_returns_results_with_api_key(self) -> None:
        tool = SerperSearchTool(api_key="fake-key")
        mock_response = {
            "organic": [
                {
                    "title": "Python docs",
                    "snippet": "Official Python docs.",
                    "link": "https://python.org",
                },
            ]
        }
        mock_read = MagicMock()
        mock_read.read.return_value = json.dumps(mock_response).encode()
        mock_read.status = 200
        mock_read.__enter__ = lambda s: s
        mock_read.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_read):
            result = tool.run(query="Python")

        assert "Python docs" in result
        assert "python.org" in result


# ══════════════════════════════════════════════
# HttpGetTool tests
# ══════════════════════════════════════════════


class TestHttpGetTool:
    @pytest.fixture
    def tool(self) -> HttpGetTool:
        return HttpGetTool()

    def test_key(self, tool: HttpGetTool) -> None:
        assert tool.key == "http_get"

    def test_successful_get(self, tool: HttpGetTool) -> None:
        body = b'{"status": "ok"}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = tool.run(url="https://example.com/api")

        assert "[HTTP 200]" in result
        assert "status" in result

    def test_http_error(self, tool: HttpGetTool) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://example.com",
                code=404,
                msg="Not Found",
                hdrs=MagicMock(),
                fp=None,
            ),
        ):
            result = tool.run(url="https://example.com/missing")

        assert "HTTP Error 404" in result

    def test_url_error(self, tool: HttpGetTool) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("name resolution failed"),
        ):
            result = tool.run(url="https://invalid.domain")

        assert "URL Error" in result


# ══════════════════════════════════════════════
# HttpPostTool tests
# ══════════════════════════════════════════════


class TestHttpPostTool:
    @pytest.fixture
    def tool(self) -> HttpPostTool:
        return HttpPostTool()

    def test_key(self, tool: HttpPostTool) -> None:
        assert tool.key == "http_post"

    def test_successful_post(self, tool: HttpPostTool) -> None:
        response_body = b'{"result": "created"}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.status = 201
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = tool.run(
                url="https://api.example.com/items",
                body={"name": "test"},
            )

        assert "[HTTP 201]" in result
        assert "created" in result

    def test_post_with_empty_body(self, tool: HttpPostTool) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = tool.run(url="https://api.example.com/ping")

        assert "[HTTP 200]" in result

    def test_http_error(self, tool: HttpPostTool) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://api.example.com",
                code=400,
                msg="Bad Request",
                hdrs=MagicMock(),
                fp=None,
            ),
        ):
            result = tool.run(url="https://api.example.com/fail", body={})

        assert "HTTP Error 400" in result
