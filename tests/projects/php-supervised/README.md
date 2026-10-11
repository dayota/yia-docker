# Fixture PHP supervisé

Ce backend synthétique teste le routage HTTP, un handshake WebSocket et une
trame de test. Ce n'est pas Laravel/Reverb et cela ne valide pas une diffusion
Reverb, les autorisations métier ou la configuration PEPITO.

La fixture ne contient aucun secret et ne requiert aucune installation Composer.
Les deux processus et FPM partagent PHP 8.4, sans port hôte applicatif. Les
délais et versions sont des choix de test, pas une configuration PEPITO.

Sans démarrer Docker :

```sh
make validate CONFIG=tests/projects/php-supervised/yia.yml
make generate CONFIG=tests/projects/php-supervised/yia.yml
```

Après autorisation explicite de construire et démarrer des conteneurs de test :

```sh
YIA_RUN_DOCKER_INTEGRATION=1 .venv/bin/python -m pytest -q tests/integration/test_php_supervision_docker.py
```

La recette matérialise une copie temporaire avec des secrets synthétiques,
sans bind de port hôte Apache. Elle vérifie FPM/CLI, les routes proxy et leurs
erreurs, les métadonnées Docker et l'absence de sentinelle dans les données
et caches inspectés, le remplacement atomique d'un secret puis
`make reload-secrets`, l'état Docker unhealthy sans relance d'un processus sorti
et l'arrêt gracieux du runtime.
Elle supprime à la fin uniquement les conteneurs et volumes du projet de test
à nom unique. La recette réelle Laravel/Reverb demeure séparée.
