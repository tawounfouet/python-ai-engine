"""
Exemple 06 : Intégration de pyconnectors dans ai_engine.

Montre comment utiliser le package local `pyconnectors` depuis `ai_engine` :

  1. Utilisation directe de BaseConnector pour créer un connecteur personnalisé
  2. Utilisation du ConnectorFactory avec le registre de connecteurs built-in
  3. Création d'un connecteur REST pour interroger une API publique
  4. Interprétation des ConnectorResult (succès / erreur)
  5. Ajout de hooks (logging middleware)

Aucune clé API réelle nécessaire — l'exemple utilise une API publique gratuite.

Prérequis :
    uv add --editable ../pyconnectors
    # ou : pip install -e ../pyconnectors
"""

import json
import logging
import importlib

from pyconnectors import (
    BaseConnector,
    ConnectorFactory,
    ConnectorRegistry,
    ConnectorResult,
    connector,
)
from pyconnectors.config import AuthMethod, ConnectorConfig, ConnectorStatus
from pyconnectors.exceptions import ConnectorConnectionError, ConnectorNotFoundError

# ── Configuration du logging ─────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ai_engine.examples.pyconnectors")

SEPARATOR = "─" * 60


# ══════════════════════════════════════════════════════════════════════════════
# 1. Création d'un connecteur personnalisé avec BaseConnector
# ══════════════════════════════════════════════════════════════════════════════


@connector("joke.api")
class JokeAPIConnector(BaseConnector):
    """
    Connecteur personnalisé vers l'API publique JokeAPI (icanhazdadjoke.com).

    Hérite de BaseConnector : bénéficie automatiquement du système de hooks,
    de la gestion des erreurs via ConnectorResult, et du registre.
    """

    BASE_URL = "https://icanhazdadjoke.com"

    def execute(self, category: str = "any") -> dict:  # type: ignore[override]
        """Récupère une blague aléatoire via l'API publique."""
        import urllib.request

        url = self.BASE_URL
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ai-engine-example/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            raise ConnectorConnectionError(
                f"Échec de la connexion à JokeAPI : {exc}"
            ) from exc

    def test_connection(self) -> tuple[bool, str]:
        try:
            result = self.execute()
            return True, f"Connecté — blague reçue : '{result.get('joke', '')[:40]}...'"
        except Exception as exc:
            return False, str(exc)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Connecteur REST générique via ConnectorFactory (built-in http.rest)
# ══════════════════════════════════════════════════════════════════════════════


def demo_builtin_rest_connector() -> None:
    """Utilisation du connecteur REST built-in de pyconnectors via ConnectorFactory."""

    print(f"\n{SEPARATOR}")
    print("2. ConnectorFactory — connecteur REST built-in (http.rest)")
    print(SEPARATOR)

    config = ConnectorConfig(
        name="JSONPlaceholder API",
        auth_method=AuthMethod.NONE,
        params={
            "base_url": "https://jsonplaceholder.typicode.com",
        },
    )

    try:
        rest = ConnectorFactory.create("http.rest", config)
        # GET /posts/1
        result: ConnectorResult = rest.safe_execute(
            "GET",
            "https://jsonplaceholder.typicode.com/posts/1",
        )

        if result.success:
            # RestConnector retourne {"status": <int>, "body": "<json string>"}
            body = json.loads(result.data.get("body", "{}"))
            print(
                f"  ✅ Succès en {result.duration:.3f}s (HTTP {result.data.get('status')})"
            )
            print(
                f"  📄 Post récupéré : ID={body.get('id')} | Titre: {body.get('title', '')[:50]}"
            )
        else:
            print(f"  ❌ Erreur : {result.error}")

    except ConnectorNotFoundError:
        print("  ⚠️  Connecteur 'http.rest' non disponible.")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Utilisation du connecteur personnalisé JokeAPIConnector
# ══════════════════════════════════════════════════════════════════════════════


def demo_custom_connector() -> None:
    """Démonstration du connecteur personnalisé JokeAPIConnector."""

    print(f"\n{SEPARATOR}")
    print("3. Connecteur personnalisé — JokeAPIConnector")
    print(SEPARATOR)

    config = ConnectorConfig(
        name="Dad Jokes API",
        auth_method=AuthMethod.NONE,
        status=ConnectorStatus.ACTIVE,
        tags=["humor", "public-api"],
    )

    joke_connector = JokeAPIConnector(config)

    # Test de connexion
    ok, message = joke_connector.test_connection()
    status_icon = "✅" if ok else "❌"
    print(f"  {status_icon} test_connection() → {message}")

    # Exécution via safe_execute (retourne un ConnectorResult)
    result: ConnectorResult = joke_connector.safe_execute()
    if result.success:
        print(f"\n  😄 Blague du jour :")
        print(f"     {result.data.get('joke', 'N/A')}")
        print(f"\n  ⏱  Durée : {result.duration:.3f}s")
        print(f"  📦 Métadonnées : {result.metadata}")
    else:
        print(f"  ❌ Erreur lors de l'exécution : {result.error}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Hooks — ajout d'un middleware de logging
# ══════════════════════════════════════════════════════════════════════════════


def demo_hooks() -> None:
    """Démonstration des hooks pre/post execute."""

    print(f"\n{SEPARATOR}")
    print("4. Hooks — middleware de logging sur les connecteurs")
    print(SEPARATOR)

    config = ConnectorConfig(name="Joke API avec hooks", auth_method=AuthMethod.NONE)
    joke_connector = JokeAPIConnector(config)

    # Hook pré-exécution — signature : (connector, *args, **kwargs)
    def on_pre_execute(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        log.info("[HOOK pre_execute] Appel du connecteur '%s'", config.name)

    # Hook post-exécution — signature : (connector, result, *args, **kwargs)
    def on_post_execute(connector_instance, result: ConnectorResult, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        status = "OK" if result.success else "ERREUR"
        log.info("[HOOK post_execute] Résultat : %s en %.3fs", status, result.duration)

    # Hook sur erreur — signature : (connector, result, *args, **kwargs)
    def on_error(connector_instance, result: ConnectorResult, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        log.error("[HOOK on_error] Erreur : %s", result.error)

    joke_connector.add_hook("pre_execute", on_pre_execute)
    joke_connector.add_hook("post_execute", on_post_execute)
    joke_connector.add_hook("on_error", on_error)

    print("  Hooks enregistrés. Exécution...")
    result = joke_connector.safe_execute()
    if result.success:
        joke_text = result.data.get("joke", "")
        print(
            f"  ✅ Blague reçue : {joke_text[:70]}{'...' if len(joke_text) > 70 else ''}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Registre — lister les connecteurs disponibles
# ══════════════════════════════════════════════════════════════════════════════


def demo_registry() -> None:
    """Afficher les connecteurs enregistrés dans le registre global."""

    print(f"\n{SEPARATOR}")
    print("5. ConnectorRegistry — connecteurs disponibles")
    print(SEPARATOR)

    # Forcer le chargement des connecteurs built-in via list_types()
    ConnectorFactory.list_types()
    # Charger explicitement les sous-modules de connecteurs built-in
    for mod in [
        "pyconnectors.connectors.http.rest",
        "pyconnectors.connectors.http.oauth2",
    ]:
        try:
            importlib.import_module(mod)
        except ImportError:
            pass

    registered = ConnectorRegistry.list_names()
    print(f"  {len(registered)} connecteur(s) enregistré(s) :\n")
    for name in registered:
        cls = ConnectorRegistry.get(name)
        print(f"  • {name:<25} → {cls.__name__}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Pattern d'intégration dans ai_engine : wrapping d'un connecteur
# ══════════════════════════════════════════════════════════════════════════════


class DataFetcherTool:
    """
    Exemple de wrapping d'un ConnectorFactory dans un outil ai_engine.

    Pattern recommandé : encapsuler pyconnectors dans des classes de service
    propres à ai_engine plutôt que d'appeler ConnectorFactory directement
    dans les agents.
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        auth = AuthMethod.API_KEY if api_key else AuthMethod.NONE
        self._config = ConnectorConfig(
            name="DataFetcher",
            auth_method=auth,
            params={
                "base_url": base_url,
                **(
                    {"api_key": api_key, "api_key_header": "X-API-Key"}
                    if api_key
                    else {}
                ),
            },
        )
        self._connector = ConnectorFactory.create("http.rest", self._config)

    def fetch(self, url: str) -> ConnectorResult:
        return self._connector.safe_execute("GET", url)  # type: ignore[return-value]


def demo_tool_wrapping() -> None:
    """Démonstration du pattern de wrapping recommandé pour ai_engine."""

    print(f"\n{SEPARATOR}")
    print("6. Pattern d'intégration ai_engine — DataFetcherTool")
    print(SEPARATOR)

    try:
        fetcher = DataFetcherTool(base_url="https://jsonplaceholder.typicode.com")
        result = fetcher.fetch("https://jsonplaceholder.typicode.com/users/1")

        if result.success:
            # RestConnector retourne {"status": <int>, "body": "<json string>"}
            user = json.loads(result.data.get("body", "{}"))
            print(f"  ✅ Utilisateur récupéré (HTTP {result.data.get('status')}) :")
            print(f"     Nom    : {user.get('name')}")
            print(f"     Email  : {user.get('email')}")
            print(f"     Ville  : {user.get('address', {}).get('city')}")
            print(f"     Durée  : {result.duration:.3f}s")
        else:
            print(f"  ❌ {result.error}")
    except ConnectorNotFoundError:
        print("  ⚠️  Connecteur 'http.rest' non disponible.")


# ══════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    print("=" * 60)
    print("Exemple 06 — Intégration pyconnectors dans ai_engine")
    print("=" * 60)

    demo_registry()
    demo_custom_connector()
    demo_builtin_rest_connector()
    demo_hooks()
    demo_tool_wrapping()

    print(f"\n{'=' * 60}")
    print("✅ Exemple terminé avec succès.")
    print("=" * 60)


if __name__ == "__main__":
    main()
