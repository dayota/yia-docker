---
name: update-project-docs
description: Maintenir la connaissance durable du projet après une tâche qui crée, modifie ou invalide une décision, une contrainte, une convention, une règle métier ou un élément d'architecture.
---

# Mise à jour de la documentation projet

Utiliser ce skill lorsqu'une tâche crée, modifie ou invalide une connaissance
durable utile à de futures tâches.

## Workflow obligatoire

1. Chercher si la connaissance est déjà documentée.
2. Mettre à jour le document existant lorsque c'est possible.
3. Sinon, choisir la catégorie adaptée dans `.agents/docs/`.
4. Créer un document seulement si nécessaire.
5. Mettre à jour `INDEX.md` si la découvrabilité change.
6. Vérifier la cohérence et l'absence de duplication.

## Règles

- Préférer la mise à jour d'un document existant à la création d'un doublon.
- Créer un ADR uniquement pour un choix structurant entre plusieurs
  alternatives raisonnables.
- Ne pas documenter les éléments triviaux, temporaires, propres à une machine
  ou à une branche.
- Ne jamais documenter de secret, token, mot de passe ou clé privée.
