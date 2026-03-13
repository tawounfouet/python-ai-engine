"""
Exemple 07 : Système de logging intégré à ai_engine.

Montre les 4 niveaux d'utilisation du module ``ai_engine.logging`` :

  1. Usage basique — get_logger() sans configuration (silencieux par défaut)
  2. Configuration simple — configure_logging() avec format console lisible
  3. Configuration avancée — LoggingConfigBuilder : JSON + fichier + champs extra
  4. logged_operation — context manager pour tracer durée et succès/échec
  5. Logging asynchrone — QueueHandler non-bloquant (prod-ready)
  6. Intégration pyconnectors — brancher le logging ai_engine sur un connecteur

Design du module logging ai_engine :
  - Zero dépendance externe (stdlib uniquement)
  - NullHandler par défaut (PEP 282 — silencieux sans configuration)
  - Namespace hiérarchique : ``pyworkflow_engine.<sous-module>``
  - StructuredFormatter : console colorée lisible
  - JSONFormatter : NDJSON machine-parseable pour fichier / collecteur
  - QueueHandler : async non-bloquant pour production
"""

from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

# ── Import du système de logging ai_engine ───────────────────────────────────
from ai_engine.logging import (
    LoggingConfig,
    LoggingConfigBuilder,
    configure_logging,
    get_logger,
    logged_operation,
    shutdown_logging,
)

SEPARATOR = "─" * 60
DOUBLE_SEP = "═" * 60


# ══════════════════════════════════════════════════════════════════════════════
# 1. Usage basique — NullHandler par défaut (PEP 282)
# ══════════════════════════════════════════════════════════════════════════════

def demo_basic_usage() -> None:
    """
    Sans configure_logging(), les logs sont silencieux (NullHandler).
    C'est le comportement standard des librairies Python (PEP 282) :
    la lib ne pollue pas le logging de l'application consommatrice.
    """
    print(f"\n{SEPARATOR}")
    print("1. Usage basique — NullHandler par défaut (PEP 282)")
    print(SEPARATOR)

    # Logger dans le namespace ai_engine — silencieux sans configuration
    logger = get_logger("demo.basic")
    logger.info("Ce message est silencieux (NullHandler actif)")
    logger.warning("Celui-ci aussi — la lib est silencieuse par défaut")

    print("  ✅ get_logger('demo.basic') créé dans le namespace 'pyworkflow_engine'")
    print(f"  📌 logger.name = '{logger.name}'")
    print("  🔇 Aucune sortie console — NullHandler actif (PEP 282)")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Configuration simple — StructuredFormatter console
# ══════════════════════════════════════════════════════════════════════════════

def demo_simple_config() -> None:
    """Configuration basique : console avec StructuredFormatter coloré."""

    print(f"\n{SEPARATOR}")
    print("2. Configuration simple — StructuredFormatter console")
    print(SEPARATOR)

    configure_logging(LoggingConfig(
        level="DEBUG",
        json_output=False,   # Format lisible humain (avec couleurs ANSI)
    ))

    logger = get_logger("demo.simple")

    print("\n  --- Sortie du logger ---")
    logger.debug("Message DEBUG — détails internes")
    logger.info("Message INFO — opération normale")
    logger.warning("Message WARNING — situation anormale")
    logger.error("Message ERROR — erreur non critique")

    # Extra fields — champs contextuels passés via extra={}
    logger.info(
        "Traitement entité financière",
        extra={"entity_id": 42, "period": "2026-Q1", "currency": "EUR"},
    )
    print("  --- Fin sortie ---\n")


# ══════════════════════════════════════════════════════════════════════════════
# 3. LoggingConfigBuilder — API fluide + JSON + fichier
# ══════════════════════════════════════════════════════════════════════════════

def demo_builder_and_json(log_file: Path) -> None:
    """Utilisation du builder fluide avec sortie JSON + fichier rotatif."""

    print(f"\n{SEPARATOR}")
    print("3. LoggingConfigBuilder — JSON + fichier rotatif + extra fields")
    print(SEPARATOR)

    config = (
        LoggingConfigBuilder()
        .level("INFO")
        .json_output(True)                       # Console en JSON
        .log_file(log_file, max_bytes=1_000_000, backup_count=3)
        .extra_fields(                            # Champs présents dans TOUS les logs
            service="ai-engine",
            environment="development",
            version="0.1.0",
        )
        .build()
    )

    configure_logging(config)

    logger = get_logger("demo.json")

    print(f"\n  Sortie JSON — chaque ligne est un objet JSON valide (NDJSON):")
    print(f"  (Fichier : {log_file})\n")
    print("  --- Sortie du logger ---")
    logger.info("Service démarré")
    logger.info(
        "Calcul de ratio financier",
        extra={"ratio": "net_profit_margin", "value": 0.2142, "entity": "ALPHA SA"},
    )
    logger.warning(
        "Valeur hors plage normale",
        extra={"ratio": "debt_to_equity", "value": 3.5, "threshold": 2.0},
    )
    print("  --- Fin sortie ---")

    # Vérifier le fichier de log
    time.sleep(0.1)  # Laisser le temps d'écrire
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        print(f"\n  📁 Fichier de log : {len(lines)} entrée(s) écrite(s)")
        if lines:
            sample = json.loads(lines[-1])
            print(f"  🔍 Dernière entrée JSON (champs) : {list(sample.keys())}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. logged_operation — context manager durée + succès/échec
# ══════════════════════════════════════════════════════════════════════════════

def demo_logged_operation() -> None:
    """logged_operation trace automatiquement durée et résultat d'une opération."""

    print(f"\n{SEPARATOR}")
    print("4. logged_operation — context manager durée + succès/échec")
    print(SEPARATOR)

    configure_logging(LoggingConfig(level="INFO", json_output=False))

    logger = get_logger("demo.operations")

    print("\n  --- Opération réussie ---")
    with logged_operation(logger, "calcul_ratios_financiers", entity_id=1, period="2026-Q1") as log:
        time.sleep(0.05)  # Simulation du calcul
        log.info("Ratios calculés", extra={"count": 12})

    print("\n  --- Opération échouée (exception capturée et re-raised) ---")
    try:
        with logged_operation(logger, "import_donnees_externes", source="ERP") as log:
            log.info("Connexion à la source de données...")
            time.sleep(0.02)
            raise ValueError("Timeout de connexion après 30s")
    except ValueError:
        pass  # L'exception est loggée puis re-raised — on la récupère ici

    print()


# ══════════════════════════════════════════════════════════════════════════════
# 5. with_overrides — configuration dérivée immuable
# ══════════════════════════════════════════════════════════════════════════════

def demo_config_overrides() -> None:
    """LoggingConfig est immuable (frozen=True) — with_overrides() pour dériver."""

    print(f"\n{SEPARATOR}")
    print("5. with_overrides() — dériver une configuration sans muter l'originale")
    print(SEPARATOR)

    # Config de base pour le développement
    dev_config = LoggingConfig(
        level="DEBUG",
        json_output=False,
        extra_fields={"env": "dev"},
    )

    # Dériver pour la production — sans muter dev_config
    prod_config = dev_config.with_overrides(
        level="WARNING",
        json_output=True,
        extra_fields={"env": "prod", "service": "ai-engine"},
    )

    print(f"  dev_config  : level={dev_config.level!r}, json={dev_config.json_output}, extra={dev_config.extra_fields}")
    print(f"  prod_config : level={prod_config.level!r}, json={prod_config.json_output}, extra={prod_config.extra_fields}")
    print(f"  Immuabilité : dev_config is prod_config → {dev_config is prod_config}")

    # Utilisation de la config prod
    configure_logging(prod_config)
    logger = get_logger("demo.overrides")

    print("\n  --- Sortie prod (WARNING+, JSON) ---")
    logger.debug("Ignoré (niveau DEBUG < WARNING)")
    logger.info("Ignoré (niveau INFO < WARNING)")
    logger.warning("Visible — seuil WARNING atteint", extra={"component": "ratios"})
    print("  --- Fin sortie ---\n")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Intégration pyconnectors — hooks branchés sur le logging ai_engine
# ══════════════════════════════════════════════════════════════════════════════

def demo_pyconnectors_integration() -> None:
    """Brancher le logging ai_engine sur les hooks d'un connecteur pyconnectors."""

    print(f"\n{SEPARATOR}")
    print("6. Intégration pyconnectors — hooks → logging ai_engine")
    print(SEPARATOR)

    try:
        import importlib
        import urllib.request

        from pyconnectors import BaseConnector, ConnectorResult, connector
        from pyconnectors.config import AuthMethod, ConnectorConfig
        from pyconnectors.exceptions import ConnectorConnectionError

        # Reconfigurer en mode console lisible
        configure_logging(LoggingConfig(
            level="DEBUG",
            json_output=False,
            extra_fields={"component": "pyconnectors"},
        ))

        connector_logger = get_logger("connectors.http")

        @connector("demo.posts.api")
        class PostsAPIConnector(BaseConnector):
            """Connecteur vers JSONPlaceholder — branché sur le logging ai_engine."""

            def execute(self, post_id: int = 1) -> dict:  # type: ignore[override]
                importlib.import_module("pyconnectors.connectors.http.rest")
                url = f"https://jsonplaceholder.typicode.com/posts/{post_id}"
                req = urllib.request.Request(
                    url, headers={"Accept": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        body = json.loads(resp.read().decode())
                        return {"status": resp.status, "body": body}
                except Exception as exc:
                    raise ConnectorConnectionError(str(exc)) from exc

        config = ConnectorConfig(name="Posts API", auth_method=AuthMethod.NONE)
        posts = PostsAPIConnector(config)

        # ── Brancher les hooks pyconnectors sur le logger ai_engine ──────────
        def hook_pre(connector_instance, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            connector_logger.debug(
                "Appel connecteur",
                extra={"connector": connector_instance.name, "args": str(args[:2])},
            )

        def hook_post(connector_instance, result: ConnectorResult, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            connector_logger.info(
                "Connecteur terminé",
                extra={
                    "connector": connector_instance.name,
                    "success": result.success,
                    "duration_ms": round(result.duration * 1000, 1),
                },
            )

        def hook_error(connector_instance, result: ConnectorResult, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            connector_logger.error(
                "Erreur connecteur",
                extra={"connector": connector_instance.name, "error": result.error},
            )

        posts.add_hook("pre_execute", hook_pre)
        posts.add_hook("post_execute", hook_post)
        posts.add_hook("on_error", hook_error)

        print("\n  --- logged_operation + hooks connecteur ---")
        with logged_operation(connector_logger, "fetch_posts_batch", batch_size=3):
            for post_id in [1, 2, 3]:
                result = posts.safe_execute(post_id=post_id)
                if result.success:
                    title = result.data.get("body", {}).get("title", "")[:40]
                    connector_logger.debug(
                        "Post reçu",
                        extra={"post_id": post_id, "title": title},
                    )
        print("  --- Fin sortie ---\n")

    except ImportError:
        print("  ⚠️  pyconnectors non installé — ignoré.")
        print("       Lancer : uv add --editable ../pyconnectors")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Logging asynchrone — QueueHandler non-bloquant
# ══════════════════════════════════════════════════════════════════════════════

def demo_async_queue(log_file: Path) -> None:
    """QueueHandler : le thread applicatif n'est jamais bloqué par l'I/O de logging."""

    print(f"\n{SEPARATOR}")
    print("7. Logging asynchrone — QueueHandler (production-ready)")
    print(SEPARATOR)

    config = (
        LoggingConfigBuilder()
        .level("INFO")
        .json_output(False)
        .log_file(log_file)
        .with_queue(True)           # ← async : le thread n'attend pas l'I/O
        .extra_fields(mode="async")
        .build()
    )

    configure_logging(config)
    logger = get_logger("demo.async")

    print(f"\n  QueueHandler actif — logs écrits dans un thread dédié")
    print(f"  Fichier : {log_file}\n")
    print("  --- Sortie du logger ---")

    t0 = time.monotonic()
    for i in range(5):
        logger.info(
            "Traitement lot %d/5", i + 1,
            extra={"lot": i + 1, "total": 5},
        )
    elapsed = time.monotonic() - t0

    shutdown_logging()  # Attendre que le QueueListener vide sa file
    print("  --- Fin sortie ---")
    print(f"\n  ⚡ 5 logs envoyés en {elapsed * 1000:.2f}ms (thread non bloqué)")

    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        print(f"  📁 {len(lines)} lignes écrites dans {log_file.name}")


# ══════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print(DOUBLE_SEP)
    print("Exemple 07 — Système de logging intégré à ai_engine")
    print(DOUBLE_SEP)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        json_log = tmp_path / "ai_engine_json.log"
        async_log = tmp_path / "ai_engine_async.log"

        demo_basic_usage()
        demo_simple_config()
        demo_builder_and_json(json_log)
        demo_logged_operation()
        demo_config_overrides()
        demo_pyconnectors_integration()
        demo_async_queue(async_log)

        shutdown_logging()

    print(f"\n{DOUBLE_SEP}")
    print("✅ Exemple 07 terminé avec succès.")
    print(DOUBLE_SEP)


if __name__ == "__main__":
    main()
