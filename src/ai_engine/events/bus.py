"""
AI Engine — EventBus.

Bus d'événements thread-safe pour le découplage interne des composants.
Remplace les Django signals dans le contexte standalone.

Fonctionnalités :
  - Inscription de handlers sync et async
  - Émission synchrone (emit) et asynchrone (aemit)
  - Wildcard listeners via EventType.CUSTOM ou "on_any"
  - Middleware support (logging, metrics, etc.)
  - Isolation des erreurs : un handler en échec ne bloque pas les autres

Usage:
    bus = EventBus()

    # Handler sync
    @bus.on(EventType.TOOL_SUCCEEDED)
    def log_tool(event: ToolSucceededEvent) -> None:
        print(f"Tool succeeded: {event.tool_name}")

    # Handler async
    @bus.on(EventType.MESSAGE_RECEIVED)
    async def notify(event: MessageReceivedEvent) -> None:
        await send_notification(event.message_id)

    # Émission
    bus.emit(ToolSucceededEvent(tool_name="calculator", tool_call_id="tc-1"))
    await bus.aemit(MessageReceivedEvent(message_id="msg-1", model="gpt-4o"))
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from ai_engine.events.events import BaseEvent
from ai_engine.exceptions import EventHandlerError
from ai_engine.types import EventType

logger = logging.getLogger(__name__)

# Handler types: sync (BaseEvent → None) or async (BaseEvent → Coroutine)
SyncHandler = Callable[[BaseEvent], None]
AsyncHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]
AnyHandler = SyncHandler | AsyncHandler

_WILDCARD = "*"  # Clé interne pour les listeners "on any event"


class EventBus:
    """
    Bus d'événements central pour ai_engine.

    Thread-safe pour l'inscription des handlers ; l'émission
    doit se faire depuis le même thread/loop pour les handlers async.
    """

    def __init__(self, *, raise_on_handler_error: bool = False) -> None:
        """
        Args:
            raise_on_handler_error: Si True, propage les erreurs des handlers.
                                     Par défaut False (log uniquement).
        """
        self._handlers: dict[str, list[AnyHandler]] = defaultdict(list)
        self._middleware: list[Callable[[BaseEvent], None]] = []
        self.raise_on_handler_error = raise_on_handler_error

    # ── Inscription ───────────────────────────────────────────────────────────

    def on(self, event_type: EventType | str) -> Callable[[AnyHandler], AnyHandler]:
        """
        Décorateur pour inscrire un handler pour un type d'événement.

        Args:
            event_type: Type d'événement à écouter

        Returns:
            Décorateur qui enregistre la fonction

        Usage:
            @bus.on(EventType.TOOL_CALLED)
            def handle(event): ...
        """

        def decorator(handler: AnyHandler) -> AnyHandler:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    def subscribe(self, event_type: EventType | str, handler: AnyHandler) -> None:
        """
        Inscrit un handler pour un type d'événement.

        Args:
            event_type: Type d'événement (EventType enum ou string)
            handler: Fonction sync ou async à appeler
        """
        key = str(event_type)
        self._handlers[key].append(handler)
        logger.debug(
            "Subscribed handler '%s' to event '%s'", _handler_name(handler), key
        )

    def subscribe_all(self, handler: AnyHandler) -> None:
        """
        Inscrit un handler qui reçoit TOUS les événements (wildcard).

        Args:
            handler: Fonction sync ou async à appeler pour chaque événement
        """
        self._handlers[_WILDCARD].append(handler)
        logger.debug("Subscribed wildcard handler '%s'", _handler_name(handler))

    def unsubscribe(self, event_type: EventType | str, handler: AnyHandler) -> bool:
        """
        Désinscrit un handler pour un type d'événement.

        Args:
            event_type: Type d'événement
            handler: Handler à retirer

        Returns:
            True si le handler a été trouvé et retiré
        """
        key = str(event_type)
        handlers = self._handlers.get(key, [])
        try:
            handlers.remove(handler)
            return True
        except ValueError:
            return False

    def add_middleware(self, middleware: Callable[[BaseEvent], None]) -> None:
        """
        Ajoute un middleware exécuté avant chaque handler.

        Utile pour le logging, les métriques, le tracing, etc.

        Args:
            middleware: Fonction recevant l'événement (sync uniquement)
        """
        self._middleware.append(middleware)

    # ── Émission synchrone ────────────────────────────────────────────────────

    def emit(self, event: BaseEvent) -> None:
        """
        Émet un événement de manière synchrone.

        Tous les handlers sync enregistrés pour ce type d'événement
        sont appelés dans l'ordre d'inscription.
        Les handlers async sont lancés via asyncio.run_coroutine_threadsafe
        si une boucle existe, sinon ignorés avec un warning.

        Args:
            event: L'événement à émettre
        """
        self._run_middleware(event)
        key = str(event.event_type)
        handlers = list(self._handlers.get(key, [])) + list(
            self._handlers.get(_WILDCARD, [])
        )

        if not handlers:
            logger.debug("No handlers for event '%s'", key)
            return

        for handler in handlers:
            self._call_sync(handler, event)

    def _call_sync(self, handler: AnyHandler, event: BaseEvent) -> None:
        """Appelle un handler (sync ou async) dans un contexte synchrone."""
        name = _handler_name(handler)
        try:
            if asyncio.iscoroutinefunction(handler):
                # Tenter de récupérer la boucle courante
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(handler(event))  # type: ignore[arg-type]
                except RuntimeError:
                    # Pas de boucle active → exécuter dans une nouvelle
                    asyncio.run(handler(event))  # type: ignore[arg-type]
            else:
                handler(event)  # type: ignore[arg-type]
        except Exception as exc:
            logger.error(
                "Handler '%s' failed for event '%s': %s",
                name,
                event.event_type,
                exc,
                exc_info=True,
            )
            if self.raise_on_handler_error:
                raise EventHandlerError(str(event.event_type), str(exc)) from exc

    # ── Émission asynchrone ───────────────────────────────────────────────────

    async def aemit(self, event: BaseEvent) -> None:
        """
        Émet un événement de manière asynchrone.

        Les handlers sync et async sont tous attendus (gathered).
        Les erreurs de handlers individuels sont isolées.

        Args:
            event: L'événement à émettre
        """
        self._run_middleware(event)
        key = str(event.event_type)
        handlers = list(self._handlers.get(key, [])) + list(
            self._handlers.get(_WILDCARD, [])
        )

        if not handlers:
            logger.debug("No handlers for event '%s'", key)
            return

        coros = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                coros.append(self._safe_async_call(handler, event))
            else:
                coros.append(self._run_sync_in_executor(handler, event))

        await asyncio.gather(*coros, return_exceptions=False)

    async def _safe_async_call(self, handler: AnyHandler, event: BaseEvent) -> None:
        """Appelle un handler async en capturant les erreurs."""
        name = _handler_name(handler)
        try:
            await handler(event)  # type: ignore[misc]
        except Exception as exc:
            logger.error(
                "Async handler '%s' failed for event '%s': %s",
                name,
                event.event_type,
                exc,
                exc_info=True,
            )
            if self.raise_on_handler_error:
                raise EventHandlerError(str(event.event_type), str(exc)) from exc

    async def _run_sync_in_executor(
        self, handler: AnyHandler, event: BaseEvent
    ) -> None:
        """Exécute un handler sync dans un thread pool."""
        loop = asyncio.get_event_loop()
        name = _handler_name(handler)
        try:
            await loop.run_in_executor(None, handler, event)  # type: ignore[arg-type]
        except Exception as exc:
            logger.error(
                "Sync handler '%s' (in executor) failed for event '%s': %s",
                name,
                event.event_type,
                exc,
                exc_info=True,
            )
            if self.raise_on_handler_error:
                raise EventHandlerError(str(event.event_type), str(exc)) from exc

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def _run_middleware(self, event: BaseEvent) -> None:
        """Exécute tous les middlewares avant l'émission."""
        for mw in self._middleware:
            try:
                mw(event)
            except Exception as exc:
                logger.error(
                    "Middleware failed for event '%s': %s", event.event_type, exc
                )

    def handler_count(self, event_type: EventType | str | None = None) -> int:
        """
        Retourne le nombre de handlers inscrits.

        Args:
            event_type: Si fourni, compte uniquement pour ce type.
                        Sinon, compte tous les handlers (tous types confondus).
        """
        if event_type is not None:
            return len(self._handlers.get(str(event_type), []))
        return sum(len(v) for v in self._handlers.values())

    def clear(self, event_type: EventType | str | None = None) -> None:
        """
        Supprime tous les handlers.

        Args:
            event_type: Si fourni, supprime uniquement ce type.
                        Sinon, supprime tout.
        """
        if event_type is not None:
            self._handlers.pop(str(event_type), None)
        else:
            self._handlers.clear()

    def __repr__(self) -> str:
        total = self.handler_count()
        return f"<EventBus handlers={total}>"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _handler_name(handler: AnyHandler) -> str:
    """Retourne un nom lisible pour le handler (pour les logs)."""
    return getattr(handler, "__qualname__", None) or getattr(
        handler, "__name__", repr(handler)
    )


# ── Instance globale optionnelle ──────────────────────────────────────────────

_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Retourne l'instance globale de l'EventBus (singleton lazy).

    Usage:
        bus = get_event_bus()
        bus.emit(some_event)
    """
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_event_bus() -> None:
    """Réinitialise l'instance globale (utile pour les tests)."""
    global _default_bus
    _default_bus = None
