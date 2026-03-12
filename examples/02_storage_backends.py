"""
Exemple 02 : Backends de stockage (InMemoryStorage & SQLiteStorage).

Montre les opérations CRUD sur les deux backends de stockage,
les opérations de recherche et le context manager SQLite.

Aucune clé API nécessaire — tout fonctionne en local.
"""

import tempfile
from pathlib import Path

from ai_engine import (
    Agent,
    AgentConfig,
    AgentMemory,
    AgentRole,
    Conversation,
    InMemoryStorage,
    LLMProviderConfig,
    MemoryType,
    Message,
    MessageRole,
    ProviderType,
    SQLiteStorage,
    ToolDefinition,
    ToolType,
)

# ── 1. InMemoryStorage — prototypage rapide ─────────────────────────────────

print("=" * 60)
print("InMemoryStorage — Prototypage rapide")
print("=" * 60)

storage = InMemoryStorage()

# Créer un provider
provider = LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-demo",
)
storage.save_provider(provider)
print(f"✅ Provider sauvegardé : {provider.name}")

# Créer des agents
agent1 = Agent(
    name="Chercheur",
    role=AgentRole.RESEARCHER,
    provider_id=provider.id,
    system_prompt="Tu es un chercheur.",
    config=AgentConfig(temperature=0.7),
)
agent2 = Agent(
    name="Codeur",
    role=AgentRole.CODER,
    provider_id=provider.id,
    system_prompt="Tu es un développeur Python expert.",
    config=AgentConfig(temperature=0.2),
)
storage.save_agent(agent1)
storage.save_agent(agent2)
print(f"✅ Agents sauvegardés : {agent1.name}, {agent2.name}")

# Lire un agent
found = storage.get_agent(agent1.id)
assert found is not None
print(f"✅ Agent retrouvé : {found.name}")

# Lister par rôle
coders = storage.list_agents(role=AgentRole.CODER)
print(f"✅ Agents codeurs : {[a.name for a in coders]}")

# Créer des conversations et messages
conv = Conversation(agent_id=agent1.id, title="Recherche IA")
storage.save_conversation(conv)

for i, (role, text) in enumerate([
    (MessageRole.USER, "Explique le RAG en 3 lignes."),
    (MessageRole.ASSISTANT, "Le RAG combine recherche documentaire et génération..."),
    (MessageRole.USER, "Et les embeddings ?"),
    (MessageRole.ASSISTANT, "Les embeddings sont des vecteurs denses..."),
]):
    msg = Message(conversation_id=conv.id, role=role, content=text)
    storage.save_message(msg)

messages = storage.get_messages(conv.id)
print(f"✅ Conversation '{conv.title}' : {len(messages)} messages")

# Mémoire d'agent
mem = AgentMemory(
    agent_id=agent1.id,
    key="sujet_actuel",
    content="Recherche sur le RAG",
    memory_type=MemoryType.SHORT_TERM,
)
storage.save_memory(mem)
memories = storage.list_memories(agent1.id)
print(f"✅ Mémoires de {agent1.name} : {len(memories)}")

# Outils
tool = ToolDefinition(
    key="search_arxiv",
    name="Recherche ArXiv",
    description="Recherche de papers sur ArXiv",
    tool_type=ToolType.API,
    parameters_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
storage.save_tool(tool)

# Associer l'outil à l'agent
agent1.tool_ids.append(tool.id)
storage.save_agent(agent1)

agent_tools = storage.list_tools_for_agent(agent1.id)
print(f"✅ Outils de {agent1.name} : {[t.name for t in agent_tools]}")

# Suppression
storage.delete_agent(agent2.id)
agents = storage.list_agents()
print(f"✅ Après suppression : {len(agents)} agent(s) restant(s)")

# ── 2. SQLiteStorage — persistence sur disque ───────────────────────────────

print("\n" + "=" * 60)
print("SQLiteStorage — Persistence sur disque")
print("=" * 60)

# Utiliser un fichier temporaire pour la démo
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = str(Path(tmpdir) / "demo.db")

    # Context manager : la connexion est fermée proprement à la sortie
    with SQLiteStorage(db_path) as db:
        # Sauvegarder les mêmes données
        db.save_provider(provider)
        db.save_agent(agent1)
        db.save_conversation(conv)

        for msg in messages:
            db.save_message(msg)

        print(f"✅ Base SQLite créée : {db_path}")
        print(f"   Providers : {len(db.list_providers())}")
        print(f"   Agents : {len(db.list_agents())}")
        print(f"   Messages : {len(db.get_messages(conv.id))}")

    # Réouvrir pour vérifier la persistence
    with SQLiteStorage(db_path) as db:
        found_agent = db.get_agent(agent1.id)
        assert found_agent is not None
        print(f"✅ Données persistées — agent retrouvé : {found_agent.name}")

        # Statistiques via list
        all_providers = db.list_providers()
        all_agents = db.list_agents()
        print(f"   {len(all_providers)} provider(s), {len(all_agents)} agent(s)")

    print(f"✅ Base nettoyée (dossier temporaire)")

# ── 3. SQLiteStorage :memory: — rapide pour les tests ───────────────────────

print("\n" + "=" * 60)
print("SQLiteStorage :memory: — Pour les tests")
print("=" * 60)

with SQLiteStorage(":memory:") as db:
    db.save_provider(provider)
    db.save_agent(agent1)

    # Recherche par nom / slug
    found_by_name = db.get_provider_by_name("OpenAI GPT-4o")
    print(f"✅ Provider trouvé par nom : {found_by_name.name if found_by_name else 'Non trouvé'}")

    # Filtrage actif/inactif
    agent1.is_active = False
    db.save_agent(agent1)
    active = db.list_agents(is_active=True)
    inactive = db.list_agents(is_active=False)
    print(f"✅ Agents actifs : {len(active)}, inactifs : {len(inactive)}")

print("\n✅ Tous les exemples de stockage fonctionnent correctement !")
