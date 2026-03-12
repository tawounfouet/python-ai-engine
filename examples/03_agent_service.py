"""
Exemple 03 : AgentService — gestion complète d'agents.

Montre le workflow complet du service haut-niveau :
  - Création de providers et agents
  - Création de conversations
  - Envoi de messages (simulation sans API réelle)
  - Mise à jour, filtrage et statistiques

Aucune clé API réelle nécessaire — le chat est commenté.
"""

from ai_engine import (
    Agent,
    AgentConfig,
    AgentRole,
    InMemoryStorage,
    LLMProviderConfig,
    ProviderType,
)
from ai_engine.services import AgentService

# ── 1. Initialisation ───────────────────────────────────────────────────────

storage = InMemoryStorage()

# Créer le provider
provider = LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-demo-key",  # Remplacer par votre clé pour un chat réel
)
storage.save_provider(provider)

# Créer le service
agent_service = AgentService(storage)

print("=" * 60)
print("AgentService — Gestion complète d'agents")
print("=" * 60)

# ── 2. Créer plusieurs agents ───────────────────────────────────────────────

researcher = agent_service.create_agent(
    name="Assistant Recherche",
    provider_id=provider.id,
    system_prompt="Tu es un chercheur expert. Tu fournis des réponses sourcées et détaillées.",
    role=AgentRole.RESEARCHER,
    config=AgentConfig(temperature=0.7, max_tokens_per_run=8000),
)
print(f"✅ Agent créé : {researcher.name} (rôle={researcher.role})")

coder = agent_service.create_agent(
    name="Dev Python",
    provider_id=provider.id,
    system_prompt="Tu es un développeur Python senior. Code propre, testé, documenté.",
    role=AgentRole.CODER,
    config=AgentConfig(temperature=0.2, max_tokens_per_run=4000),
)
print(f"✅ Agent créé : {coder.name} (rôle={coder.role})")

reviewer = agent_service.create_agent(
    name="Code Reviewer",
    provider_id=provider.id,
    system_prompt="Tu fais des revues de code précises et constructives.",
    role=AgentRole.REVIEWER,
    config=AgentConfig(temperature=0.3),
)
print(f"✅ Agent créé : {reviewer.name} (rôle={reviewer.role})")

# ── 3. Lister et filtrer ────────────────────────────────────────────────────

all_agents = agent_service.list_agents()
print(f"\n📋 Total agents : {len(all_agents)}")

coders = agent_service.list_agents(role=AgentRole.CODER)
print(f"   Codeurs : {[a.name for a in coders]}")

researchers = agent_service.list_agents(role=AgentRole.RESEARCHER)
print(f"   Chercheurs : {[a.name for a in researchers]}")

# ── 4. Mettre à jour un agent ───────────────────────────────────────────────

updated = agent_service.update_agent(
    coder.id,
    system_prompt="Tu es un développeur Python/TypeScript senior. Clean code, tests, CI/CD.",
    description="Agent de développement polyglotte",
)
print(f"\n✏️  Agent mis à jour : {updated.name}")
print(f"   Nouveau prompt : {updated.system_prompt[:60]}...")

# ── 5. Conversations ────────────────────────────────────────────────────────

conv1 = agent_service.create_conversation(
    agent_id=researcher.id,
    title="Recherche sur les LLMs",
)
print(f"\n💬 Conversation créée : '{conv1.title}' (agent: {researcher.name})")

conv2 = agent_service.create_conversation(
    agent_id=coder.id,
    title="Implémentation FastAPI",
)
print(f"💬 Conversation créée : '{conv2.title}' (agent: {coder.name})")

# ── 6. Chat (nécessite une clé API réelle) ──────────────────────────────────

print("\n📝 Pour utiliser le chat, remplacez 'sk-demo-key' par votre clé API :")
print("""
    # Envoyer un message — la réponse et la conversation sont retournées
    response, conversation = agent_service.chat(
        agent_id=researcher.id,
        message="Quels sont les derniers progrès en RAG ?",
        conversation_id=conv1.id,
    )
    print(f"Réponse : {response.content}")

    # Le chat crée automatiquement une conversation si aucun ID n'est fourni
    response, new_conv = agent_service.chat(
        agent_id=coder.id,
        message="Écris un endpoint FastAPI pour un CRUD utilisateurs.",
    )

    # Historique de la conversation
    history = agent_service.get_conversation_history(new_conv.id)
    for msg in history:
        print(f"  [{msg.role}] {msg.content[:80]}...")
""")

# ── 7. Statistiques ─────────────────────────────────────────────────────────

stats = agent_service.get_agent_stats(researcher.id)
print(f"📊 Stats de {researcher.name} :")
for key, value in stats.items():
    print(f"   {key}: {value}")

# ── 8. Suppression ──────────────────────────────────────────────────────────

agent_service.delete_agent(reviewer.id)
remaining = agent_service.list_agents()
print(f"\n🗑️  Après suppression : {len(remaining)} agent(s) restant(s)")

print("\n✅ Exemple AgentService terminé !")
