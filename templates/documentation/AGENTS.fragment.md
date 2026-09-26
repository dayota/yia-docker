## Documentation projet

Ce projet utilise le système documentaire Yia.

Avant toute tâche susceptible de dépendre de l'architecture, des décisions, des
conventions, des standards ou des règles métier du projet, utiliser le skill
`project-docs`.

Le point d'entrée de la documentation est :

    .agents/docs/INDEX.md

Ne pas charger systématiquement toute la documentation. Utiliser `INDEX.md`
pour sélectionner les documents pertinents.

Lorsqu'une tâche introduit, modifie ou invalide une connaissance durable du
projet, utiliser `update-project-docs`.

Ne pas documenter les changements triviaux ou temporaires.

Ne jamais stocker de secret dans la documentation.

En cas de contradiction entre documentation et implémentation, ne pas choisir
silencieusement une interprétation : identifier le conflit et le résoudre selon
les sources normatives applicables.
