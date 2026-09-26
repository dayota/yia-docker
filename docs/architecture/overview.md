# Architecture Yia

## Principe

Yia sépare quatre catégories :

```text
Makefile                 API publique humaine
    │
    ▼
CLI Python interne       orchestration
    │
    ├── configuration / validation
    ├── génération
    ├── doctor
    ├── documentation
    └── état interne

templates/               données copiées ou rendues
schemas/                 contrats exécutables
docker/                  images et ressources Docker
```

## Moteur

Le moteur est contenu exclusivement dans `src/yia/`.

Il ne doit pas embarquer les templates sous forme de chaînes codées en dur lorsque ceux-ci peuvent rester dans `templates/`.

## Templates

Les templates sont des ressources de Yia.

Lorsqu'ils sont copiés dans un projet consommateur, ils appartiennent ensuite au projet et ne doivent pas être écrasés silencieusement lors d'une mise à jour de Yia.

## État interne

L'état interne doit être stocké dans le projet consommateur sous :

```text
.yia-runtime/state/yia-state.json
```

Il contient des métadonnées de génération et de version.

Il ne constitue jamais une source de vérité : `yia.yml` reste la configuration déclarative normative.
