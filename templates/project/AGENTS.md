# Projet utilisant Yia

Ce projet utilise Yia comme sous-module Git dans `.yia/`.

- Ne jamais modifier `.yia/` depuis le projet consommateur.
- Modifier `yia.yml` pour décrire l'environnement cible.
- Utiliser le Makefile racine comme interface publique.
- Consulter `.agents/docs/INDEX.md` via le skill `project-docs` lorsque la documentation peut influencer une tâche.
- Utiliser `update-project-docs` lorsqu'une tâche introduit ou modifie une connaissance durable.
