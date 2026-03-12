"""
Exemple 04 : Système de tools — ToolRegistry & ToolExecutor.

Montre comment :
  - Enregistrer des fonctions Python comme tools
  - Définir des ToolDefinition avec schema JSON
  - Exécuter des tool calls manuellement
  - Comprendre la boucle tool-calling avec un LLM

Aucune clé API nécessaire — fonctionne entièrement en local.
"""

import json
import math

from ai_engine import (
    ToolCall,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
    ToolType,
)

# ── 1. Créer des fonctions tools ────────────────────────────────────────────

def calculer(expression: str) -> str:
    """Évalue une expression mathématique simple."""
    # Seules les opérations mathématiques sont autorisées
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return f"Erreur : expression invalide '{expression}'"
    result = eval(expression, {"__builtins__": {}}, {"math": math})  # noqa: S307
    return str(result)


def rechercher_utilisateur(nom: str) -> dict:
    """Simule une recherche dans une base de données."""
    db = {
        "alice": {"id": 1, "nom": "Alice Dupont", "email": "alice@example.com"},
        "bob": {"id": 2, "nom": "Bob Martin", "email": "bob@example.com"},
        "charlie": {"id": 3, "nom": "Charlie Durand", "email": "charlie@example.com"},
    }
    user = db.get(nom.lower())
    if user:
        return user
    return {"erreur": f"Utilisateur '{nom}' non trouvé"}


def meteo(ville: str) -> dict:
    """Simule une API météo."""
    villes = {
        "paris": {"temp": 18, "condition": "nuageux", "humidité": 65},
        "lyon": {"temp": 22, "condition": "ensoleillé", "humidité": 45},
        "marseille": {"temp": 25, "condition": "ensoleillé", "humidité": 55},
    }
    data = villes.get(ville.lower())
    if data:
        return {"ville": ville, **data}
    return {"ville": ville, "erreur": "Ville non trouvée"}


# ── 2. ToolRegistry — enregistrement ────────────────────────────────────────

print("=" * 60)
print("ToolRegistry — Enregistrement de tools")
print("=" * 60)

registry = ToolRegistry()

# Méthode 1 : enregistrement simple (clé + fonction)
registry.register("calculer", calculer)
print(f"✅ Tool enregistré : calculer")

# Méthode 2 : enregistrement avec ToolDefinition (schéma pour le LLM)
tool_user = ToolDefinition(
    key="rechercher_utilisateur",
    name="Recherche Utilisateur",
    description="Recherche un utilisateur par son nom dans la base de données",
    tool_type=ToolType.DATABASE,
    parameters_schema={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom de l'utilisateur à rechercher",
            },
        },
        "required": ["nom"],
    },
)
registry.register_tool(tool_user, rechercher_utilisateur)
print(f"✅ Tool enregistré : {tool_user.name} (avec schéma)")

tool_meteo = ToolDefinition(
    key="meteo",
    name="Météo",
    description="Récupère la météo actuelle pour une ville",
    tool_type=ToolType.API,
    parameters_schema={
        "type": "object",
        "properties": {
            "ville": {
                "type": "string",
                "description": "Nom de la ville",
            },
        },
        "required": ["ville"],
    },
)
registry.register_tool(tool_meteo, meteo)
print(f"✅ Tool enregistré : {tool_meteo.name} (avec schéma)")

# Inspecter le registry
print(f"\n📋 Tools enregistrés : {registry.keys()}")
print(f"   Nombre total : {len(registry)}")
print(f"   'calculer' existe ? {'calculer' in registry}")
print(f"   'inconnu' existe ? {'inconnu' in registry}")

# Récupérer le schéma OpenAI d'un tool
definition = registry.get_definition("meteo")
if definition:
    schema = definition.get_function_schema()
    print(f"\n📝 Schéma OpenAI pour 'meteo' :")
    print(json.dumps(schema, indent=2, ensure_ascii=False))

# ── 3. ToolExecutor — exécution de tool calls ───────────────────────────────

print("\n" + "=" * 60)
print("ToolExecutor — Exécution de tool calls")
print("=" * 60)

executor = ToolExecutor(registry)

# Simuler des tool calls comme ceux qu'un LLM retournerait
call_calc = ToolCall(
    id="call_001",
    name="calculer",
    arguments={"expression": "3.14 * 2.5 * 2.5"},
)
result = executor.execute_call(call_calc)
print(f"\n🔧 Tool: calculer('3.14 * 2.5 * 2.5')")
print(f"   Résultat : {result.output}")
print(f"   Erreur ? {result.is_error}")

call_user = ToolCall(
    id="call_002",
    name="rechercher_utilisateur",
    arguments={"nom": "alice"},
)
result = executor.execute_call(call_user)
print(f"\n🔧 Tool: rechercher_utilisateur('alice')")
print(f"   Résultat : {result.output}")
print(f"   Erreur ? {result.is_error}")

call_meteo = ToolCall(
    id="call_003",
    name="meteo",
    arguments={"ville": "Lyon"},
)
result = executor.execute_call(call_meteo)
print(f"\n🔧 Tool: meteo('Lyon')")
print(f"   Résultat : {result.output}")
print(f"   Erreur ? {result.is_error}")

# Gestion des erreurs : tool inexistant
call_bad = ToolCall(
    id="call_004",
    name="tool_inexistant",
    arguments={},
)
result = executor.execute_call(call_bad)
print(f"\n🔧 Tool: tool_inexistant()")
print(f"   Résultat : {result.output}")
print(f"   Erreur ? {result.is_error}")

# ── 4. Intégration avec AgentService (aperçu) ───────────────────────────────

print("\n" + "=" * 60)
print("Intégration avec AgentService")
print("=" * 60)

print("""
Quand un AgentService est initialisé avec un ToolRegistry,
la boucle tool-calling est automatique durant le chat :

    from ai_engine import InMemoryStorage, ToolRegistry
    from ai_engine.services import AgentService

    registry = ToolRegistry()
    registry.register("calculer", calculer)
    registry.register("meteo", meteo)

    storage = InMemoryStorage()
    service = AgentService(storage, tool_registry=registry)

    # Le LLM peut maintenant appeler les tools automatiquement :
    # response, conv = service.chat(agent_id, "Quelle est la météo à Paris ?")
    # → Le LLM appelle meteo("Paris") → reçoit le résultat → formule sa réponse

Le flux est :
  1. L'utilisateur envoie un message
  2. Le LLM reçoit le message + les schémas des tools disponibles
  3. Si le LLM veut utiliser un tool → il retourne un tool_call
  4. ToolExecutor exécute le tool_call et retourne le résultat au LLM
  5. Répéter 3-4 jusqu'à max_iterations ou réponse finale
  6. La réponse finale est retournée à l'utilisateur
""")

print("✅ Exemple du système de tools terminé !")
