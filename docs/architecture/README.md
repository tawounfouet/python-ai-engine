# Documentation Architecture — AI Engine

> Analyse approfondie de l'architecture du package `ai-engine` (v0.1.0)
> Date : Mars 2026

## Table des matières

| Fichier | Description |
|---|---|
| [01-vue-ensemble.md](01-vue-ensemble.md) | Vue d'ensemble, principes directeurs et diagramme global |
| [02-couche-modeles.md](02-couche-modeles.md) | Couche Modèles — entités Pydantic et domaine métier |
| [03-couche-services.md](03-couche-services.md) | Couche Services — logique métier et clients LLM |
| [04-couche-stockage.md](04-couche-stockage.md) | Couche Stockage — persistence abstraite et implémentations |
| [05-configuration-exceptions.md](05-configuration-exceptions.md) | Configuration, types partagés et gestion des erreurs |
| [06-flux-donnees.md](06-flux-donnees.md) | Flux de données, cycle de vie et interactions entre couches |
| [07-extensibilite.md](07-extensibilite.md) | Points d'extension, phases futures et guide de contribution |

## Contexte du projet

`ai-engine` est un package Python standalone conçu pour orchestrer des agents LLM de façon
framework-agnostique. Il est issu d'une extraction de l'application Django `django-ai-app` pour
permettre son utilisation dans tout contexte : scripts, notebooks Jupyter, FastAPI, CLI, AWS Lambda.

Le package gère actuellement les **3 premières phases** de son développement :
- **Phase 1** ✅ — Structure & Modèles Pydantic
- **Phase 2** ✅ — Storage Layer (persistence abstraite)
- **Phase 3** ✅ — Services Layer (logique métier + clients LLM)
