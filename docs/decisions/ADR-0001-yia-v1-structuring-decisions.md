# ADR-0001 — Choix structurants de Yia V1

- **Statut :** accepted
- **Date :** 2026-09-26

## Contexte

Yia doit fournir un environnement de développement Docker composable, versionné et pilotable par Make/Codex.

Plusieurs choix structurants devaient être figés avant l'implémentation Docker et de la configuration.

## Décisions

### Configuration

- versions PHP, Node et PostgreSQL toujours explicites ;
- `environment.domain` obligatoire ;
- validation stricte et versionnée ;
- un seul hostname par application en V1 ;
- applications sans exposition HTTP autorisées ;
- un seul PostgreSQL mutualisé par projet en V1 ;
- PostgreSQL seul service d'infrastructure V1 ;
- frameworks connus : Laravel, Symfony, Nuxt ;
- extensions PHP gérées dans les Dockerfiles des runtimes ;
- variables d'environnement exclusivement via `.env`.

### Docker

- un container PHP-FPM partagé par version PHP ;
- runtime Node partagé par version ;
- Apache uniquement lorsqu'une exposition HTTP est nécessaire ;
- HTTP uniquement en V1 ;
- `.localhost` recommandé ;
- PostgreSQL non exposé par défaut ;
- Composer présent dans les images PHP ;
- `pnpm` par défaut, configurable ;
- `vendor` et `node_modules` en volumes nommés ;
- UID/GID de l'hôte propagés ;
- Xdebug configurable par application ;
- images Apache/PHP/Node construites par Yia ;
- aucun `container_name` explicite ;
- un réseau privé unique par projet.

### API Make

- `make install` cible uniquement APT ;
- sortie JSON garantie pour `doctor`, `validate`, `status`, `ps`, `version` ;
- `make update` applique automatiquement les changements ;
- `make init` ne démarre pas Docker ;
- `make destroy` et `make destroy-data` sont séparés ;
- `shell` et `exec` résolvent applications et services ;
- `logs` ne suit pas par défaut, `FOLLOW=1` active le suivi ;
- `make config` existe ;
- `make generate` existe ;
- codes de sortie 0 à 6 stables en V1.

## Conséquences

Ces choix sont normatifs pour Yia V1 et sont détaillés dans :

- `docs/configuration.md`
- `docs/docker.md`
- `docs/make-api.md`
