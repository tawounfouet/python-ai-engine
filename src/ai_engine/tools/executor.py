"""
AI Engine — Tool Executor.

Exécute les appels de tools (ToolCall) en résolvant les fonctions via le ToolRegistry.
Gère la boucle complète tool-calling avec le LLM.

Usage:
    executor = ToolExecutor(registry)

    # Exécution unitaire
    result = executor.execute_call(tool_call)

    # Boucle complète tool-calling avec un LLM client
    final_response = executor.run_tool_loop(
        client=llm_client,
        request=llm_request,
        max_iterations=10,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from ai_engine.exceptions import ToolExecutionError, ToolNotFoundError
from ai_engine.models.message import Message, ToolResult
from ai_engine.models.message import ToolCall as MessageToolCall
from ai_engine.services.llm.base import LLMClient, LLMRequest, LLMResponse
from ai_engine.tools.registry import ToolRegistry
from ai_engine.types import MessageRole

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Exécuteur de tools avec support de la boucle tool-calling."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute_call(
        self,
        tool_call: MessageToolCall,
    ) -> ToolResult:
        """
        Exécute un appel de tool unique.

        Args:
            tool_call: L'appel de tool à exécuter

        Returns:
            ToolResult avec le résultat ou l'erreur
        """
        try:
            func = self.registry.get(tool_call.name)
        except ToolNotFoundError:
            return ToolResult(
                tool_call_id=tool_call.id,
                output=f"Error: Tool '{tool_call.name}' not found in registry.",
                is_error=True,
            )

        try:
            result = func(**tool_call.arguments)

            # Normaliser le résultat en string
            if isinstance(result, str):
                output = result
            else:
                output = json.dumps(result, default=str, ensure_ascii=False)

            return ToolResult(
                tool_call_id=tool_call.id,
                output=output,
                is_error=False,
            )

        except Exception as e:
            logger.warning("Tool '%s' execution failed: %s", tool_call.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                output=f"Error executing tool '{tool_call.name}': {e}",
                is_error=True,
            )

    async def aexecute_call(
        self,
        tool_call: MessageToolCall,
    ) -> ToolResult:
        """
        Exécute un appel de tool unique (async).

        Si la fonction est async, l'await directement.
        Si elle est sync, la lance dans un executor.
        """
        try:
            func = self.registry.get(tool_call.name)
        except ToolNotFoundError:
            return ToolResult(
                tool_call_id=tool_call.id,
                output=f"Error: Tool '{tool_call.name}' not found in registry.",
                is_error=True,
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**tool_call.arguments)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: func(**tool_call.arguments))

            if isinstance(result, str):
                output = result
            else:
                output = json.dumps(result, default=str, ensure_ascii=False)

            return ToolResult(
                tool_call_id=tool_call.id,
                output=output,
                is_error=False,
            )

        except Exception as e:
            logger.warning("Tool '%s' async execution failed: %s", tool_call.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                output=f"Error executing tool '{tool_call.name}': {e}",
                is_error=True,
            )

    def run_tool_loop(
        self,
        client: LLMClient,
        messages: list[Message],
        *,
        max_iterations: int = 10,
        conversation_id: str = "",
    ) -> LLMResponse:
        """
        Boucle tool-calling : appelle le LLM, exécute les tools, recommence.

        Continue tant que le LLM demande des tool_calls, jusqu'à max_iterations.

        Args:
            client: Client LLM à utiliser
            messages: Messages de contexte (system + historique + user)
            max_iterations: Nombre max de boucles tool-calling
            conversation_id: ID de la conversation (pour les messages créés)

        Returns:
            La réponse finale du LLM (sans tool_calls)

        Raises:
            ToolExecutionError: Si max_iterations est atteint
        """
        working_messages = list(messages)

        for iteration in range(max_iterations):
            # Préparer les schemas de tools pour le LLM
            tools_schema = self._get_tools_schema()

            request = LLMRequest(
                messages=working_messages,
                tools=tools_schema if tools_schema else None,
            )

            response = client.complete(request)

            # Si pas de tool_calls → c'est la réponse finale
            if not response.tool_calls:
                return response

            logger.debug(
                "Tool loop iteration %d: %d tool calls",
                iteration + 1,
                len(response.tool_calls),
            )

            # Ajouter le message assistant avec ses tool_calls
            assistant_tool_calls = [
                MessageToolCall(
                    id=tc.id,
                    name=tc.function_name,
                    arguments=tc.arguments,
                )
                for tc in response.tool_calls
            ]
            assistant_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tool_calls=assistant_tool_calls,
            )
            working_messages.append(assistant_message)

            # Exécuter chaque tool et ajouter le résultat
            for tc in response.tool_calls:
                msg_tool_call = MessageToolCall(
                    id=tc.id,
                    name=tc.function_name,
                    arguments=tc.arguments,
                )
                result = self.execute_call(msg_tool_call)

                tool_message = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.TOOL,
                    content=result.output,
                    tool_result=result,
                )
                working_messages.append(tool_message)

        raise ToolExecutionError(
            tool_name="tool_loop",
            detail=f"Max iterations ({max_iterations}) reached without final response.",
        )

    async def arun_tool_loop(
        self,
        client: LLMClient,
        messages: list[Message],
        *,
        max_iterations: int = 10,
        conversation_id: str = "",
    ) -> LLMResponse:
        """
        Boucle tool-calling asynchrone.

        Identique à run_tool_loop mais utilise acomplete() et aexecute_call().
        """
        working_messages = list(messages)

        for iteration in range(max_iterations):
            tools_schema = self._get_tools_schema()

            request = LLMRequest(
                messages=working_messages,
                tools=tools_schema if tools_schema else None,
            )

            response = await client.acomplete(request)

            if not response.tool_calls:
                return response

            logger.debug(
                "Async tool loop iteration %d: %d tool calls",
                iteration + 1,
                len(response.tool_calls),
            )

            assistant_tool_calls = [
                MessageToolCall(
                    id=tc.id,
                    name=tc.function_name,
                    arguments=tc.arguments,
                )
                for tc in response.tool_calls
            ]
            assistant_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tool_calls=assistant_tool_calls,
            )
            working_messages.append(assistant_message)

            # Exécuter les tools en parallèle
            tasks = []
            for tc in response.tool_calls:
                msg_tool_call = MessageToolCall(
                    id=tc.id,
                    name=tc.function_name,
                    arguments=tc.arguments,
                )
                tasks.append(self.aexecute_call(msg_tool_call))

            results = await asyncio.gather(*tasks)

            for result in results:
                tool_message = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.TOOL,
                    content=result.output,
                    tool_result=result,
                )
                working_messages.append(tool_message)

        raise ToolExecutionError(
            tool_name="tool_loop",
            detail=f"Max iterations ({max_iterations}) reached without final response.",
        )

    def _get_tools_schema(self) -> list[dict[str, Any]]:
        """Retourne les schemas OpenAI function calling pour tous les tools enregistrés."""
        schemas: list[dict[str, Any]] = []
        for key in self.registry.keys():  # noqa: SIM118
            definition = self.registry.get_definition(key)
            if definition:
                schemas.append(definition.get_function_schema())
            else:
                # Schema minimal si pas de ToolDefinition
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": key,
                        "description": f"Tool: {key}",
                        "parameters": {"type": "object", "properties": {}},
                    },
                })
        return schemas
