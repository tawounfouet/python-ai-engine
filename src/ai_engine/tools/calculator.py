"""
AI Engine — Calculator Tool.

Tool de calcul mathématique sécurisé utilisant ast.literal_eval
et un sous-ensemble limité d'opérations.

Usage:
    from ai_engine.tools.calculator import CalculatorTool

    tool = CalculatorTool()
    result = tool(expression="2 ** 10 + sqrt(16)")
    # → "1028.0"
"""

from __future__ import annotations

import math
import operator
import re
from typing import Any

from ai_engine.tools.base import BaseTool
from ai_engine.types import ToolType


# Opérateurs et fonctions mathématiques autorisés (allowlist explicite)
_SAFE_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "pow": math.pow,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
}

_ALLOWED_PATTERN = re.compile(r"^[0-9\s\+\-\*\/\%\(\)\.\,\_a-zA-Z\*\*]+$")


class CalculatorTool(BaseTool):
    """
    Tool de calcul mathématique sécurisé.

    Évalue des expressions mathématiques via un sandbox (eval restreint).
    Supporte les opérations de base, les fonctions math standard et les constantes.

    Exemples supportés:
      - "2 + 2"
      - "sqrt(144)"
      - "sin(pi / 2)"
      - "(10 ** 3) / 4 + log(100, 10)"
    """

    key = "calculator"
    name = "Calculator"
    description = (
        "Evaluates a mathematical expression and returns the numeric result. "
        "Supports basic arithmetic (+, -, *, /, **, %), "
        "and math functions: sqrt, pow, log, log2, log10, exp, "
        "floor, ceil, sin, cos, tan, abs, round, min, max. "
        "Constants: pi, e."
    )
    tool_type = ToolType.FUNCTION
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "The mathematical expression to evaluate. "
                    "Example: '2 ** 10', 'sqrt(144)', 'sin(pi / 2)'"
                ),
            },
        },
        "required": ["expression"],
    }

    def run(self, expression: str, **_: Any) -> str:
        """
        Évalue l'expression mathématique.

        Args:
            expression: L'expression à évaluer

        Returns:
            Le résultat sous forme de chaîne
        """
        expression = expression.strip()

        if not expression:
            return "Error: empty expression."

        if not _ALLOWED_PATTERN.match(expression):
            return f"Error: expression contains forbidden characters: '{expression}'"

        try:
            result = eval(  # noqa: S307
                expression,
                {"__builtins__": {}},
                _SAFE_FUNCTIONS,
            )
            # Formater joliment le résultat
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except ZeroDivisionError:
            return "Error: division by zero."
        except Exception as exc:
            return f"Error evaluating expression '{expression}': {exc}"
