# Exemples AI Engine

Ce dossier contient des exemples progressifs pour découvrir les fonctionnalités de **AI Engine**.

## Pré-requis

```bash
pip install -e .
# ou
uv pip install -e .
```

## Liste des exemples

| Fichier | Description | API requise ? |
|---------|-------------|:---:|
| [01_models_quickstart.py](01_models_quickstart.py) | Création et manipulation des modèles Pydantic (Agent, Provider, Conversation, Message, Tool, Memory, Execution) | Non |
| [02_storage_backends.py](02_storage_backends.py) | Opérations CRUD avec InMemoryStorage et SQLiteStorage, filtrage, persistence | Non |
| [03_agent_service.py](03_agent_service.py) | AgentService : créer des agents, conversations, mise à jour, statistiques | Non |
| [04_tool_system.py](04_tool_system.py) | ToolRegistry + ToolExecutor : enregistrer et exécuter des tools, schémas OpenAI | Non |
| [05_multi_provider.py](05_multi_provider.py) | Configuration de 6 providers (OpenAI, Anthropic, Ollama, Groq, Gemini), agents spécialisés | Non |
| [services_example.py](services_example.py) | Exemple basique avec SQLiteStorage (existant) | Oui (chat) |

## Exécution

Chaque exemple peut être lancé directement :

```bash
python examples/01_models_quickstart.py
python examples/02_storage_backends.py
python examples/03_agent_service.py
python examples/04_tool_system.py
python examples/05_multi_provider.py
```

## Parcours recommandé

1. **Modèles** (`01`) — Comprendre les objets métier de base
2. **Storage** (`02`) — Persister les données avec les backends
3. **AgentService** (`03`) — Utiliser le service haut-niveau pour gérer les agents
4. **Tools** (`04`) — Ajouter des capacités à vos agents (function calling)
5. **Multi-provider** (`05`) — Configurer plusieurs LLMs et choisir le bon pour chaque tâche

## Chat avec une vraie clé API

Pour tester le chat réel, remplacez les clés factices dans les exemples :

```python
provider = LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-VOTRE-VRAIE-CLE",  # ← remplacer ici
)
```

Puis utilisez `AgentService.chat()` :

```python
response, conversation = service.chat(
    agent_id=agent.id,
    message="Bonjour, comment ça va ?",
)
print(response.content)
```
