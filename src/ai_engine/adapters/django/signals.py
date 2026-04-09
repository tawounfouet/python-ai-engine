"""
AI Engine Django Adapter — Signals bridge.

Connecte les signaux Django (post_save, post_delete) des ORM models
ai_engine vers le EventBus interne, permettant aux composants
de reagir aux changements de donnees sans couplage direct a Django.

Ce module est importe automatiquement par AiEngineConfig.ready()
quand AI_ENGINE["EVENT_BUS_ENABLED"] est True (defaut).

Exemple d'abonnement :
    from ai_engine.events import get_event_bus
    from ai_engine.types import EventType

    bus = get_event_bus()

    @bus.on(EventType.AGENT_CREATED)
    def on_agent_created(event):
        print(f"Agent created: {event.agent_name}")
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ai_engine.events import get_event_bus


# -- Provider signals ---------------------------------------------------------
# No dedicated ProviderCreated/Updated event type in the bus.
# Extend by registering custom handlers on the EventBus.


@receiver(post_save, sender="ai_engine.ProviderRecord")
def on_provider_saved(sender, instance, created: bool, **kwargs) -> None:  # type: ignore[misc]
    pass  # Hook point - add custom bus.emit() calls here if needed.


@receiver(post_delete, sender="ai_engine.ProviderRecord")
def on_provider_deleted(sender, instance, **kwargs) -> None:  # type: ignore[misc]
    pass


# -- Agent signals ------------------------------------------------------------


@receiver(post_save, sender="ai_engine.AgentRecord")
def on_agent_saved(sender, instance, created: bool, **kwargs) -> None:  # type: ignore[misc]
    try:
        from ai_engine.events.events import AgentCreatedEvent, AgentUpdatedEvent

        bus = get_event_bus()
        if created:
            bus.emit(
                AgentCreatedEvent(
                    agent_id=instance.id,
                    agent_name=instance.name,
                    agent_role=instance.role,
                )
            )
        else:
            bus.emit(
                AgentUpdatedEvent(
                    agent_id=instance.id,
                )
            )
    except Exception:
        pass  # Never let the bus crash a Django save


@receiver(post_delete, sender="ai_engine.AgentRecord")
def on_agent_deleted(sender, instance, **kwargs) -> None:  # type: ignore[misc]
    try:
        from ai_engine.events.events import AgentDeletedEvent

        get_event_bus().emit(AgentDeletedEvent(agent_id=instance.id))
    except Exception:
        pass


# -- Conversation signals ------------------------------------------------------


@receiver(post_save, sender="ai_engine.ConversationRecord")
def on_conversation_saved(sender, instance, created: bool, **kwargs) -> None:  # type: ignore[misc]
    if not created:
        return
    try:
        from ai_engine.events.events import ConversationStartedEvent

        get_event_bus().emit(
            ConversationStartedEvent(
                agent_id=instance.agent_id,
                conversation_id=instance.id,
                title=instance.title or "",
            )
        )
    except Exception:
        pass


@receiver(post_delete, sender="ai_engine.ConversationRecord")
def on_conversation_deleted(sender, instance, **kwargs) -> None:  # type: ignore[misc]
    try:
        from ai_engine.events.events import ConversationEndedEvent

        get_event_bus().emit(
            ConversationEndedEvent(
                agent_id=instance.agent_id,
                conversation_id=instance.id,
            )
        )
    except Exception:
        pass


# -- Message signals ----------------------------------------------------------


@receiver(post_save, sender="ai_engine.MessageRecord")
def on_message_saved(sender, instance, created: bool, **kwargs) -> None:  # type: ignore[misc]
    if not created:
        return
    try:
        from ai_engine.events.events import MessageSentEvent

        content = instance.data.get("content", "") if isinstance(instance.data, dict) else ""
        get_event_bus().emit(
            MessageSentEvent(
                conversation_id=instance.conversation_id,
                message_id=instance.id,
                content_preview=content[:200],
            )
        )
    except Exception:
        pass
