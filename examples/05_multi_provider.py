"""
Exemple 05 : Configuration multi-provider.

Montre comment configurer et basculer entre différents providers LLM :
  - OpenAI (GPT-4o, GPT-4o-mini)
  - Anthropic (Claude 3.5 Sonnet)
  - Ollama (modèles locaux gratuits)
  - Groq (inférence rapide)
  - Gemini (Google)

Aucune clé API réelle nécessaire pour cet exemple.
Les appels LLM sont commentés — seule la configuration est démontrée.
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

# ── 1. Configurer plusieurs providers ────────────────────────────────────────

print("=" * 60)
print("Configuration multi-provider")
print("=" * 60)

storage = InMemoryStorage()

# OpenAI — modèle phare pour la qualité
openai_provider = LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-your-openai-key",
)
storage.save_provider(openai_provider)
print(f"✅ {openai_provider.name} ({openai_provider.provider_type})")

# OpenAI — modèle économique
openai_mini = LLMProviderConfig(
    name="OpenAI GPT-4o-mini",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o-mini",
    api_key="sk-your-openai-key",
)
storage.save_provider(openai_mini)
print(f"✅ {openai_mini.name} ({openai_mini.provider_type})")

# Anthropic — Claude pour le raisonnement
anthropic_provider = LLMProviderConfig(
    name="Anthropic Claude Sonnet",
    provider_type=ProviderType.ANTHROPIC,
    default_model="claude-sonnet-4-20250514",
    api_key="sk-ant-your-anthropic-key",
)
storage.save_provider(anthropic_provider)
print(f"✅ {anthropic_provider.name} ({anthropic_provider.provider_type})")

# Ollama — modèles locaux sans clé API
ollama_provider = LLMProviderConfig(
    name="Ollama Llama 3",
    provider_type=ProviderType.OLLAMA,
    default_model="llama3:8b",
    api_base_url="http://localhost:11434",
)
storage.save_provider(ollama_provider)
print(f"✅ {ollama_provider.name} ({ollama_provider.provider_type})")

# Groq — inférence ultra-rapide
groq_provider = LLMProviderConfig(
    name="Groq Llama 3",
    provider_type=ProviderType.GROQ,
    default_model="llama3-70b-8192",
    api_key="gsk-your-groq-key",
)
storage.save_provider(groq_provider)
print(f"✅ {groq_provider.name} ({groq_provider.provider_type})")

# Gemini — Google
gemini_provider = LLMProviderConfig(
    name="Google Gemini Pro",
    provider_type=ProviderType.GEMINI,
    default_model="gemini-pro",
    api_key="your-google-api-key",
)
storage.save_provider(gemini_provider)
print(f"✅ {gemini_provider.name} ({gemini_provider.provider_type})")

# ── 2. Lister les providers disponibles ──────────────────────────────────────

print(f"\n📋 Providers configurés : {len(storage.list_providers())}")
for p in storage.list_providers():
    print(f"   [{p.provider_type.upper():>10}] {p.name} — modèle: {p.default_model}")

# ── 3. Créer des agents spécialisés par provider ────────────────────────────

print("\n" + "=" * 60)
print("Agents spécialisés par provider")
print("=" * 60)

service = AgentService(storage)

# Agent qualité → GPT-4o
agent_quality = service.create_agent(
    name="Expert Rédaction",
    provider_id=openai_provider.id,
    system_prompt="Tu es un rédacteur expert. Contenu de haute qualité, structuré et sourced.",
    role=AgentRole.ASSISTANT,
    config=AgentConfig(temperature=0.8, max_tokens_per_run=8000),
)
print(f"✅ {agent_quality.name} → {openai_provider.name}")

# Agent rapide → GPT-4o-mini (moins cher, plus rapide)
agent_fast = service.create_agent(
    name="Trieur de tickets",
    provider_id=openai_mini.id,
    system_prompt="Tu tries et catégorises les tickets de support. Réponses courtes et précises.",
    role=AgentRole.ASSISTANT,
    config=AgentConfig(temperature=0.1, max_tokens_per_run=1000),
)
print(f"✅ {agent_fast.name} → {openai_mini.name}")

# Agent code → Claude (excellent en code)
agent_code = service.create_agent(
    name="Dev Senior",
    provider_id=anthropic_provider.id,
    system_prompt="Tu es un développeur senior Python/TypeScript. Code propre, testé, documenté.",
    role=AgentRole.CODER,
    config=AgentConfig(temperature=0.2),
)
print(f"✅ {agent_code.name} → {anthropic_provider.name}")

# Agent local → Ollama (gratuit, données privées)
agent_local = service.create_agent(
    name="Assistant Local",
    provider_id=ollama_provider.id,
    system_prompt="Tu es un assistant utile. Tes données restent en local.",
    role=AgentRole.ASSISTANT,
    config=AgentConfig(temperature=0.5),
)
print(f"✅ {agent_local.name} → {ollama_provider.name}")

# Agent speed → Groq (latence minimale)
agent_speed = service.create_agent(
    name="Répondeur Rapide",
    provider_id=groq_provider.id,
    system_prompt="Tu réponds rapidement et avec précision.",
    role=AgentRole.ASSISTANT,
    config=AgentConfig(temperature=0.3),
)
print(f"✅ {agent_speed.name} → {groq_provider.name}")

# ── 4. Résumé ────────────────────────────────────────────────────────────────

print(f"\n📊 Résumé")
print(f"   Providers : {len(storage.list_providers())}")
print(f"   Agents : {len(service.list_agents())}")

print("\n💡 Cas d'usage par provider :")
print("   OpenAI GPT-4o      → Qualité maximale, raisonnement complexe")
print("   OpenAI GPT-4o-mini → Tâches simples, volume élevé, coût réduit")
print("   Anthropic Claude   → Code, analyse, instructions longues")
print("   Ollama             → Données sensibles, hors-ligne, gratuit")
print("   Groq               → Latence minimale, temps réel")
print("   Gemini             → Écosystème Google, multimodal")

print("\n📝 Pour tester avec une vraie clé API :")
print("""
    # Remplacer api_key par votre clé réelle, puis :
    response, conv = service.chat(
        agent_id=agent_code.id,
        message="Écris une fonction Python qui merge deux dicts récursivement.",
    )
    print(response.content)
""")

print("✅ Exemple multi-provider terminé !")
