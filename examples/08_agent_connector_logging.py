"""
Exemple 08 : Agent IA + Connecteur + Logging — intégration complète.

Combine les trois briques fondamentales de l'écosystème :

  ┌─────────────────────────────────────────────────────────┐
  │  ai_engine.logging  →  get_logger / logged_operation    │
  │  ai_engine (Agent, AgentService, InMemoryStorage)       │
  │  pyconnectors (RestConnector, BaseConnector)            │
  └─────────────────────────────────────────────────────────┘

Scénario : un agent IA "Analyste Financier" reçoit une question,
consulte une API externe via pyconnectors pour enrichir sa réponse,
et chaque étape est tracée via le logging ai_engine.

Utilisation avec le LLM réel :
    export OPENAI_API_KEY=sk-...
    uv run python examples/08_agent_connector_logging.py

Sans variable d'environnement, une réponse simulée est injectée
pour illustrer le pipeline complet sans dépendance réseau vers OpenAI.
"""

from __future__ import annotations

import json
import importlib
import os

# ── Logging ai_engine ────────────────────────────────────────────────────────
from ai_engine.logging import (
    LoggingConfig,
    configure_logging,
    get_logger,
    logged_operation,
    shutdown_logging,
)

# ── AI Engine ────────────────────────────────────────────────────────────────
from ai_engine import (
    Agent,
    AgentConfig,
    AgentRole,
    Conversation,
    InMemoryStorage,
    LLMProviderConfig,
    Message,
    MessageRole,
    ProviderType,
)
from ai_engine.services import AgentService

# ── pyconnectors ─────────────────────────────────────────────────────────────
from pyconnectors import BaseConnector, ConnectorResult, connector
from pyconnectors.config import AuthMethod, ConnectorConfig
from pyconnectors.exceptions import ConnectorConnectionError

# ═════════════════════════════════════════════════════════════════════════════
# Configuration globale du logging
# ═════════════════════════════════════════════════════════════════════════════

configure_logging(
    LoggingConfig(
        level="DEBUG",
        json_output=False,
        extra_fields={"app": "ai-engine-demo", "version": "0.1.0"},
    )
)

# Un logger par couche — namespace hiérarchique pyworkflow_engine.<sous-module>
log_app = get_logger("demo.app")  # orchestration générale
log_agent = get_logger("demo.agent")  # cycle de vie agent
log_conn = get_logger("demo.connector")  # appels pyconnectors

SEPARATOR = "─" * 60

# ═════════════════════════════════════════════════════════════════════════════
# 1. Connecteur pyconnectors — données financières publiques
# ═════════════════════════════════════════════════════════════════════════════


@connector("finance.api")
class FinanceAPIConnector(BaseConnector):
    """
    Connecteur vers JSONPlaceholder simulant une API de données financières.

    En production, pointer vers une vraie API (Alpha Vantage, Yahoo Finance…).
    Ici on utilise JSONPlaceholder pour ne pas nécessiter de clé API.
    """

    BASE_URL = "https://jsonplaceholder.typicode.com"

    def execute(self, endpoint: str = "/posts/1") -> dict:  # type: ignore[override]
        import urllib.request

        # S'assurer que le module rest est chargé dans le registre
        importlib.import_module("pyconnectors.connectors.http.rest")

        url = f"{self.BASE_URL}{endpoint}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "ai-engine/0.1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode())
                return {"status": resp.status, "data": body}
        except Exception as exc:
            raise ConnectorConnectionError(f"Échec API : {exc}") from exc

    def test_connection(self) -> tuple[bool, str]:
        try:
            r = self.execute("/posts/1")
            return True, f"OK — statut HTTP {r['status']}"
        except Exception as exc:
            return False, str(exc)


def build_connector() -> FinanceAPIConnector:
    """Instancie et configure le connecteur avec ses hooks de logging."""

    cfg = ConnectorConfig(
        name="Finance API",
        auth_method=AuthMethod.NONE,
        tags=["finance", "data"],
    )
    conn = FinanceAPIConnector(cfg)

    # ── Hooks → logging ai_engine ────────────────────────────────────────
    def _pre(instance, *a, **kw) -> None:  # type: ignore[no-untyped-def]
        log_conn.debug("→ Appel connecteur", extra={"connector": instance.name})

    def _post(instance, result: ConnectorResult, *a, **kw) -> None:  # type: ignore[no-untyped-def]
        log_conn.info(
            "← Réponse connecteur",
            extra={
                "connector": instance.name,
                "success": result.success,
                "duration_ms": round(result.duration * 1000, 1),
            },
        )

    def _error(instance, result: ConnectorResult, *a, **kw) -> None:  # type: ignore[no-untyped-def]
        log_conn.error(
            "✗ Erreur connecteur",
            extra={"connector": instance.name, "error": result.error},
        )

    conn.add_hook("pre_execute", _pre)
    conn.add_hook("post_execute", _post)
    conn.add_hook("on_error", _error)

    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 2. Couche agent — storage + service
# ═════════════════════════════════════════════════════════════════════════════


def build_agent_service() -> tuple[AgentService, LLMProviderConfig]:
    """Crée le storage, le provider et le service agent.

    La clé OpenAI est lue depuis la variable d'environnement OPENAI_API_KEY.
    Sans clé valide, le chat LLM sera simulé (section 3).
    """

    storage = InMemoryStorage()

    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")

    provider = LLMProviderConfig(
        name="OpenAI GPT-4o",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key=api_key,
    )
    storage.save_provider(provider)

    log_agent.info(
        "Provider enregistré",
        extra={"provider": provider.name, "model": provider.default_model},
    )

    service = AgentService(storage)
    return service, provider


def create_analyst_agent(service: AgentService, provider: LLMProviderConfig) -> Agent:
    """Crée l'agent analyste financier."""

    agent = service.create_agent(
        name="Analyste Financier",
        provider_id=provider.id,
        role=AgentRole.ANALYST,
        system_prompt=(
            "Tu es un analyste financier expert. "
            "Tu analyses les données fournies et produis des synthèses claires et structurées. "
            "Tu indiques toujours la source de tes données et les limites de ton analyse."
        ),
        config=AgentConfig(
            temperature=0.3,  # Déterministe pour l'analyse financière
            max_tokens_per_run=2048,
            enable_tools=False,
            enable_memory=True,
        ),
    )

    log_agent.info(
        "Agent créé",
        extra={
            "agent": agent.name,
            "role": str(agent.role),
            "temperature": agent.config.temperature,
        },
    )
    return agent


# ═════════════════════════════════════════════════════════════════════════════
# 3. Pipeline complet : fetch → enrich → (optionnel) chat
# ═════════════════════════════════════════════════════════════════════════════


def fetch_financial_data(conn: FinanceAPIConnector) -> dict:
    """Étape 1 : récupère les données via pyconnectors."""

    with logged_operation(log_conn, "fetch_financial_data", source="Finance API"):
        # Simule la récupération de plusieurs endpoints
        posts_result = conn.safe_execute(endpoint="/posts/1")
        users_result = conn.safe_execute(endpoint="/users/1")

        if not posts_result.success or not users_result.success:
            log_conn.error("Échec de la récupération des données")
            return {}

        return {
            "report": posts_result.data.get("data", {}),
            "analyst": users_result.data.get("data", {}),
        }


def build_context_message(data: dict) -> str:
    """Étape 2 : formate les données brutes en contexte pour l'agent."""

    report = data.get("report", {})
    analyst = data.get("analyst", {})

    return (
        f"Données financières récupérées :\n"
        f"  Rapport ID    : {report.get('id', 'N/A')}\n"
        f"  Titre         : {report.get('title', 'N/A')}\n"
        f"  Corps         : {str(report.get('body', ''))[:120]}...\n\n"
        f"Analyste responsable : {analyst.get('name', 'N/A')} "
        f"({analyst.get('email', 'N/A')})\n"
        f"  Entreprise    : {analyst.get('company', {}).get('name', 'N/A')}\n"
        f"  Ville         : {analyst.get('address', {}).get('city', 'N/A')}"
    )


def simulate_agent_reasoning(
    service: AgentService,
    agent: Agent,
    context: str,
    user_question: str,
) -> Conversation:
    """
    Étape 3 : crée une conversation titrée, appelle service.chat() (LLM réel).

    Pré-requis : variable d'environnement OPENAI_API_KEY définie.
    Sans clé valide, une réponse simulée est injectée directement dans le storage.
    """

    with logged_operation(
        log_agent,
        "agent_reasoning",
        agent=agent.name,
        question=user_question[:60],
    ):
        # Enrichir la question avec le contexte récupéré par le connecteur
        enriched_prompt = f"{user_question}\n\nContexte (données API) :\n{context}"

        # Créer la conversation avec un titre explicite AVANT le chat
        # (service.chat() n'accepte pas de paramètre title)
        conv = service.create_conversation(agent.id, title="Analyse financière Q1 2026")

        has_real_key = os.environ.get("OPENAI_API_KEY", "").startswith("sk-")

        if has_real_key:
            # ── Chemin LLM réel ──────────────────────────────────────────
            try:
                assistant_msg, conv = service.chat(
                    agent.id,
                    enriched_prompt,
                    conversation_id=conv.id,
                )
                log_agent.info(
                    "Réponse LLM reçue",
                    extra={
                        "conv": conv.id[:8],
                        "length": len(assistant_msg.content),
                    },
                )
            except Exception as exc:
                log_agent.error(
                    "Échec LLM malgré clé valide",
                    extra={"error": type(exc).__name__, "detail": str(exc)[:120]},
                )
                raise
        else:
            # ── Chemin simulation (pas de clé) ───────────────────────────
            log_agent.warning(
                "OPENAI_API_KEY absente — réponse simulée",
                extra={"hint": "export OPENAI_API_KEY=sk-..."},
            )

            user_msg = Message(
                conversation_id=conv.id,
                role=MessageRole.USER,
                content=enriched_prompt,
            )
            service.storage.save_message(user_msg)

            titre_line = next(
                (
                    l.split(":", 1)[1].strip()
                    for l in context.splitlines()
                    if "Titre" in l
                ),
                "N/A",
            )

            simulated_response = (
                "**Synthèse de l'analyse financière**\n\n"
                "Sur la base des données fournies par le connecteur :\n\n"
                f"1. **Source** : Finance API (JSONPlaceholder)\n"
                f"2. **Rapport** : {titre_line[:80]}\n"
                "3. **Recommandation** : Les indicateurs préliminaires suggèrent "
                "une situation stable. Une analyse approfondie des flux de trésorerie "
                "est recommandée avant toute décision d'investissement.\n\n"
                "⚠️ *Réponse simulée — définir OPENAI_API_KEY pour activer le LLM réel.*"
            )

            assistant_msg = Message(
                conversation_id=conv.id,
                role=MessageRole.ASSISTANT,
                content=simulated_response,
            )
            service.storage.save_message(assistant_msg)

            log_agent.info(
                "Réponse simulée enregistrée",
                extra={"conv": conv.id[:8], "length": len(simulated_response)},
            )

        return conv


def display_conversation(service: AgentService, conv: Conversation) -> None:
    """Affiche la conversation de manière lisible."""

    messages = service.get_conversation_history(conv.id)

    print(f"\n{'═' * 60}")
    print(f"  Conversation : {conv.title}")
    print(f"  ID           : {conv.id[:8]}...")
    print(f"{'═' * 60}")

    role_icons = {
        MessageRole.USER: "👤 USER",
        MessageRole.ASSISTANT: "🤖 AGENT",
        MessageRole.SYSTEM: "⚙️  SYSTEM",
    }

    for msg in messages:
        icon = role_icons.get(msg.role, str(msg.role))
        print(f"\n{icon}")
        print(f"{'─' * 40}")
        print(msg.content)

    print(f"\n{'═' * 60}")


# ═════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    print("═" * 60)
    print("  Exemple 08 — Agent + Connecteur + Logging")
    print("═" * 60)

    with logged_operation(
        log_app, "pipeline_complet", scenario="analyse_financiere_q1"
    ):

        # ── Étape 1 : Initialiser le connecteur ──────────────────────────
        log_app.info("Initialisation du connecteur pyconnectors...")
        conn = build_connector()

        ok, msg = conn.test_connection()
        log_conn.info("Test de connexion", extra={"success": ok, "detail": msg})

        if not ok:
            log_app.error("Connecteur indisponible — arrêt du pipeline")
            return

        # ── Étape 2 : Initialiser l'agent ────────────────────────────────
        log_app.info("Initialisation de l'agent IA...")
        service, provider = build_agent_service()
        agent = create_analyst_agent(service, provider)

        # ── Étape 3 : Récupérer les données via pyconnectors ─────────────
        log_app.info("Récupération des données via pyconnectors...")
        raw_data = fetch_financial_data(conn)

        if not raw_data:
            log_app.error("Aucune donnée récupérée — arrêt du pipeline")
            return

        context = build_context_message(raw_data)
        log_app.debug(
            "Contexte construit", extra={"context_lines": len(context.splitlines())}
        )

        # ── Étape 4 : L'agent traite la question enrichie ─────────────────
        user_question = (
            "Analyse le rapport financier fourni et donne-moi une synthèse "
            "avec les points clés et une recommandation."
        )
        log_app.info(
            "Lancement du raisonnement de l'agent...", extra={"agent": agent.name}
        )

        conv = simulate_agent_reasoning(service, agent, context, user_question)

        # ── Étape 5 : Affichage du résultat ──────────────────────────────
        display_conversation(service, conv)

        # ── Résumé des statistiques ───────────────────────────────────────
        stats = service.get_agent_stats(agent.id)
        log_app.info(
            "Pipeline terminé",
            extra={
                "conversations": stats.get("conversation_count", 0),
                "messages": stats.get("total_messages", 0),
                "agent": agent.name,
            },
        )

    print("\n✅ Exemple 08 terminé avec succès.")
    shutdown_logging()


if __name__ == "__main__":
    main()
