# Yia development instructions

Yia est un environnement de développement Docker composable, versionné, modulaire, auto-documenté et agent-friendly.

## Source de vérité

Avant toute modification :

1. lire `README.md` ;
2. lire `docs/yia-spec.md` ;
3. utiliser `README.md` pour identifier les sous-spécifications concernées ;
4. lire uniquement les sous-spécifications nécessaires à la tâche.

Les spécifications sont normatives.

L'implémentation doit suivre les spécifications et non l'inverse.

Lorsqu'une règle manque ou que deux interprétations raisonnables sont possibles, ne pas inventer silencieusement un contrat. Identifier le point comme décision à prendre ou documenter explicitement l'hypothèse temporaire.

## Invariants essentiels

- `.yia/` est en lecture seule dans un projet consommateur.
- Aucune donnée spécifique au projet n'est écrite dans le sous-module Yia.
- `yia.yml` décrit l'état cible de l'environnement.
- `make update` doit être idempotent.
- Le Makefile constitue l'API publique humaine stable de Yia.
- La CLI Python interne et les scripts sont des détails d'implémentation tant qu'une spécification ne les déclare pas publics.
- Aucune commande ne détruit silencieusement des données persistantes.
- Les fichiers humains ne sont jamais écrasés silencieusement.
- Les fichiers générés doivent être identifiables et reconstructibles.
- Toute évolution contractuelle doit mettre à jour la spécification concernée.
- Une sous-spécification marquée `squelette` ou `draft` ne doit pas être utilisée pour inventer un comportement absent de la spécification racine.
- Aucun secret ne doit être écrit dans la documentation, l'état interne ou les sorties machine.

## Architecture du repository

Le moteur Python est stocké dans :

    src/yia/

Les templates sont stockés séparément dans :

    templates/

Les schémas sont stockés dans :

    schemas/

Les images et ressources Docker sont stockées dans :

    docker/

Les fixtures de projets sont stockées dans :

    tests/projects/

Les spécifications sont stockées dans :

    docs/

## Workflow de développement

Avant de coder :

1. identifier le contrat concerné ;
2. lire les spécifications concernées ;
3. vérifier si le comportement est déjà défini ;
4. ajouter ou modifier les tests correspondant au contrat ;
5. éviter d'élargir le périmètre de la tâche sans justification.

Pendant l'implémentation :

- préférer les composants déterministes ;
- isoler les effets de bord ;
- garder la configuration déclarative ;
- conserver la compatibilité de l'API Make ;
- produire des erreurs structurées ;
- préserver l'idempotence.

Après modification :

1. exécuter les tests concernés ;
2. exécuter `make validate` lorsque la configuration est concernée ;
3. exécuter `make doctor` lorsque l'environnement ou les dépendances sont concernés ;
4. vérifier l'idempotence lorsque concernée ;
5. mettre à jour la documentation et les spécifications si un contrat change ;
6. vérifier qu'aucun invariant n'est violé.

## Documentation projet

Lorsqu'une connaissance existante peut influencer une tâche, utiliser le système documentaire décrit dans `docs/documentation.md`.

Les projets consommateurs de Yia doivent recevoir les skills :

- `project-docs` ;
- `update-project-docs`.

Ces skills sont des templates fournis par Yia, puis appartiennent au projet consommateur après initialisation.

## Gestion des erreurs

Les erreurs doivent utiliser la convention définie par le moteur Yia :

- code stable ;
- message humain ;
- contexte structuré optionnel ;
- code de sortie cohérent.

Ne pas parser une erreur à partir de texte humain lorsqu'une représentation structurée existe.

## Sorties machine

Lorsqu'une commande supporte une sortie machine, le JSON doit rester stable, déterministe et sans texte parasite sur stdout.

Les messages humains peuvent être envoyés sur stderr si nécessaire.

## Definition of Done

Une tâche n'est terminée que lorsque :

- l'implémentation correspond aux specs ;
- les tests concernés passent ;
- les nouveaux comportements sont testés ;
- les erreurs sont explicites et structurées ;
- l'idempotence est préservée lorsqu'elle s'applique ;
- les fichiers utilisateurs sont préservés ;
- la documentation est cohérente ;
- aucun secret n'est introduit dans les sorties, fixtures ou artefacts.
