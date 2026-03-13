# Intégration de packages locaux dans `ai_engine`

> **Contexte** : Ce document décrit la procédure pour intégrer un package Python local (non publié sur PyPI) comme dépendance d'un autre package dans un workspace mono-repo. Cas concret : intégration de `pyconnectors` dans `ai_engine`.

---

## Problématique

Lorsqu'on développe plusieurs packages Python dans le même workspace et qu'on souhaite qu'un package en utilise un autre **avant publication sur PyPI**, `pip install <nom-du-package>` échoue :

```
ERROR: Could not find a version that satisfies the requirement pyconnectors (from versions: none)
ERROR: No matching distribution found for pyconnectors
```

Les packages concernés :

| Package | Chemin local | Statut PyPI |
|---|---|---|
| `ai-engine` | `python-packages/ai_engine/` | ❌ Non publié |
| `pyconnectors` | `python-packages/pyconnectors/` | ❌ Non publié |

---

## Options disponibles

### ❌ À éviter : copier-coller du code source

Dupliquer le code source de `pyconnectors` dans `ai_engine` entraîne :
- Deux versions divergentes à maintenir
- Corrections de bugs à appliquer deux fois
- Incohérences garanties à terme

### ✅ Solution retenue : dépendance éditable locale avec `uv`

`uv` permet de déclarer un package local comme dépendance éditable (symlink vers le code source). Toute modification dans `pyconnectors/src/` est instantanément disponible dans `ai_engine` sans réinstallation.

---

## Procédure d'installation

### Prérequis

- `uv` installé (`pip install uv` ou via [astral.sh/uv](https://astral.sh/uv))
- Environnement virtuel activé pour `ai_engine`
- Les deux packages présents localement

### Étapes

**1. Activer l'environnement virtuel de `ai_engine` :**

```bash
cd /Users/awf/Projects/software-engineering/python-packages/ai_engine
source .venv/bin/activate
```

**2. Ajouter `pyconnectors` comme dépendance éditable locale :**

```bash
uv add --editable ../pyconnectors
```

**Sortie attendue :**

```
Resolved 142 packages in 432ms
      Built pyconnectors @ file:///Users/awf/.../pyconnectors
      Built ai-engine @ file:///Users/awf/.../ai_engine
Prepared 2 packages in 392ms
Installed 9 packages in 27ms
 ~ ai-engine==0.1.0 (from file:///Users/awf/.../ai_engine)
 + pyconnectors==0.2.0 (from file:///Users/awf/.../pyconnectors)
 + rich==14.3.3
 + typer==0.24.1
 ...
```

---

## Ce que `uv add --editable` modifie

### Dans `pyproject.toml` de `ai_engine`

Deux sections sont ajoutées/modifiées automatiquement :

```toml
# 1. pyconnectors ajouté aux dépendances du projet
[project]
dependencies = [
    "pyconnectors",
    "pydantic>=2.0,<3.0",
    "pydantic-settings>=2.0",
]

# 2. Source locale déclarée (chemin relatif, mode editable)
[tool.uv.sources]
pyconnectors = { path = "../pyconnectors", editable = true }
```

Le `uv.lock` est également mis à jour pour pointer vers le chemin local.

---

## Utilisation dans le code

Une fois installé, `pyconnectors` s'importe normalement :

```python
from pyconnectors import BaseConnector, ConnectorFactory, ConnectorResult
from pyconnectors.config import ConnectorConfig, AuthMethod
from pyconnectors.exceptions import ConnectorConnectionError
```

---

## Comportement en mode éditable

| Action | Effet |
|---|---|
| Modification d'un fichier dans `pyconnectors/src/` | Disponible immédiatement dans `ai_engine` |
| Ajout d'un nouveau module dans `pyconnectors` | Importable sans réinstallation |
| `uv sync` dans `ai_engine` | Resynchronise toutes les dépendances (y compris le lien local) |

---

## Migration future vers PyPI

Lorsque `pyconnectors` sera publié sur PyPI, mettre à jour `pyproject.toml` :

**1. Supprimer la source locale dans `pyproject.toml` :**

```toml
# Supprimer cette section (ou la ligne pyconnectors)
[tool.uv.sources]
pyconnectors = { path = "../pyconnectors", editable = true }
```

**2. Mettre à jour la version dans `dependencies` :**

```toml
dependencies = [
    "pyconnectors>=0.2.0",   # version PyPI
    ...
]
```

**3. Resynchroniser :**

```bash
uv sync
```

---

## Structure du workspace concernée

```
python-packages/
├── ai_engine/           ← package consommateur
│   ├── pyproject.toml   ← déclare pyconnectors comme dépendance
│   ├── uv.lock
│   └── src/ai_engine/
└── pyconnectors/        ← package consommé (editable)
    ├── pyproject.toml
    └── src/pyconnectors/
```

---

## Références

- [Documentation `uv` — Workspace dependencies](https://docs.astral.sh/uv/concepts/dependencies/#local-packages)
- [PEP 660 — Editable installs](https://peps.python.org/pep-0660/)
