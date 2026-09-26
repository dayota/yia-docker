---
name: project-docs
description: Consulter la documentation ciblée du projet avant une tâche influencée par son architecture, ses décisions, ses conventions ou ses règles métier.
---

# Documentation projet

Utiliser ce skill avant ou pendant une tâche lorsqu'une connaissance existante
du projet peut influencer l'implémentation.

## Workflow obligatoire

1. Lire `.agents/docs/INDEX.md`.
2. Identifier les seuls documents pertinents pour la tâche.
3. Lire ces documents.
4. Appliquer les décisions, contraintes et conventions trouvées.
5. Réaliser la tâche.

## Règles

- Ne pas modifier la documentation avec ce skill.
- Ne pas charger toute la documentation par défaut.
- Ne pas inventer une règle absente.
- Signaler toute contradiction entre documentation, code, `yia.yml`, ADR ou
  autre document, puis la résoudre selon les sources normatives applicables.
