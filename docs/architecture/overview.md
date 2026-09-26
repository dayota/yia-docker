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

Il contient uniquement les versions du moteur et des schémas ainsi que le hash
du modèle normalisé. Son écriture est atomique et idempotente.

Il ne constitue jamais une source de vérité : `yia.yml` reste la configuration déclarative normative.

Le contrat détaillé est défini dans [`docs/state.md`](../state.md).

## Génération

Les générateurs reçoivent le modèle normalisé et retournent des artefacts en
mémoire. Le moteur construit un snapshot complet dans un staging, écrit son
manifeste puis publie l'ensemble sous `.yia-runtime/` avec restauration de
l'ancien snapshot en cas d'échec.

Le contrat détaillé est défini dans
[`docs/generation.md`](../generation.md).

## Topologie Docker Compose

Le générateur Compose produit `compose/compose.yaml` dans le snapshot runtime.
Il matérialise un réseau privé, les services Apache et runtimes nécessaires,
PostgreSQL lorsqu'il est activé et les volumes nommés de dépendances ou de
données. Les noms logiques sont stables et Docker Compose applique le préfixe
du projet aux ressources physiques.

La phase Compose ne démarre aucun container. Les images et configurations de
runtime sont fournies par les phases spécialisées suivantes. Le contrat
détaillé est défini dans [`docs/docker.md`](../docker.md).

## Point d'entrée Apache

Apache est construit depuis l'image officielle épinglée par Yia et reste
l'unique port HTTP publié. Un générateur produit les vhosts depuis le modèle
normalisé : fichiers PHP vers le runtime FPM mutualisé, requêtes Node vers le
service applicatif isolé. Les sources PHP exposées et la configuration générée
sont montées en lecture seule dans Apache.
