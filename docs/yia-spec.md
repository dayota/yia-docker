# Yia — Spécification fonctionnelle et technique

## 1. Vision

Yia est un environnement de développement Docker composable, versionné, modulaire, auto-documenté et agent-friendly.

Yia est installé comme sous-module Git d'un projet consommateur. Le projet décrit l'état attendu de son environnement dans `yia.yml`, tandis que Yia fournit l'ensemble des opérations de validation, génération, démarrage, diagnostic, mise à jour et maintenance via une API Make stable.

Yia doit permettre à un développeur humain ou à un agent tel que Codex de créer, modifier et maintenir des projets PHP et/ou Node/Nuxt sans devoir réapprendre l'architecture de l'environnement à chaque session.

Le principe fondamental est déclaratif :

```text
état courant + yia.yml -> état cible
```

`yia.yml` décrit l'état voulu. Yia est responsable de converger vers cet état de façon déterministe et idempotente.

---

## 2. Objectifs

Yia doit fournir :

- un environnement Docker reproductible ;
- un reverse proxy Apache unique ;
- plusieurs versions de PHP-FPM simultanément ;
- plusieurs versions de Node simultanément ;
- PostgreSQL comme base de données par défaut ;
- des services d'infrastructure optionnels et composables ;
- une interface Make stable pour toutes les opérations courantes ;
- un fichier `yia.yml` machine-readable comme source de vérité ;
- une documentation exploitable par les humains et les agents ;
- des commandes de diagnostic et de validation ;
- une stratégie explicite de versioning et de migration ;
- une séparation stricte entre moteur Yia, configuration projet, données persistantes et artefacts générés.

---

## 3. Hors périmètre initial

Sauf décision explicite ultérieure, Yia n'a pas pour objectif de :

- remplacer Docker ou Docker Compose ;
- remplacer les outils propres aux frameworks (`artisan`, `composer`, `npm`, `pnpm`, etc.) ;
- gérer la production ou le déploiement de production ;
- modifier automatiquement le code métier des applications ;
- imposer Laravel, Symfony ou Nuxt lorsqu'un simple runtime PHP ou Node suffit ;
- stocker des secrets dans Git ;
- devenir un orchestrateur multi-hôtes ;
- gérer Kubernetes dans la première version.

Yia est avant tout un environnement de développement local reproductible.

---

## 4. Séparation des responsabilités

| Yia | Projet consommateur |
|---|---|
| Comment faire | Quoi faire |
| Dockerfiles | Applications |
| Compose générique | `yia.yml` |
| Scripts | Variables `.env` |
| Templates | Documentation projet |
| Makefile Yia | Code métier |
| Validation | Décisions / ADR |
| Schémas | Configuration projet |
| Générateurs | Données applicatives |

### 4.1. Principe de propriété

Yia possède le moteur et les templates génériques.

Le projet possède :

- son code ;
- sa configuration `yia.yml` ;
- ses variables locales ;
- sa documentation ;
- ses données persistantes ;
- ses décisions d'architecture.

Un projet consommateur ne modifie jamais directement le contenu du sous-module `.yia/`.

---

## 5. Concepts

### 5.1. Projet

Un projet est le dépôt Git consommateur de Yia.

Il contient les applications, la configuration et la documentation propres au produit développé.

### 5.2. Service

Un service est une brique d'infrastructure mutualisable.

Exemples :

- PostgreSQL ;
- Redis ;
- Mailpit ;
- MinIO ;
- RabbitMQ.

Un service n'est pas considéré comme du code métier du projet.

### 5.3. Application

Une application correspond à du code appartenant au projet.

Exemples :

- API Laravel ;
- application Symfony ;
- application PHP legacy ;
- frontend Nuxt ;
- worker Node.

### 5.4. Runtime

Un runtime est un environnement d'exécution partagé par une ou plusieurs applications compatibles.

Exemples :

- PHP 8.4 ;
- PHP 8.2 ;
- Node 24 ;
- Node 22.

Plusieurs applications peuvent utiliser le même runtime lorsque leur configuration est compatible.

### 5.5. Artefact généré

Un artefact généré est un fichier dérivé de `yia.yml` et des templates Yia.

Il doit pouvoir être supprimé puis régénéré sans perte de données fonctionnelles.

### 5.6. Donnée persistante

Une donnée persistante est une donnée locale qui ne doit pas être détruite lors d'une simple régénération de l'environnement.

Exemples :

- volume PostgreSQL ;
- données Redis persistantes si activées ;
- fichiers MinIO ;
- caches explicitement déclarés persistants.

---

## 6. Invariants de Yia

Les règles suivantes sont impératives.

1. `.yia/` est un sous-module Git en lecture seule depuis le projet consommateur.
2. Aucun fichier généré ou spécifique au projet ne doit être écrit dans `.yia/`.
3. Tous les artefacts générés sont écrits dans `.yia-runtime/` à la racine du projet.
4. Toutes les données persistantes gérées localement par Yia sont stockées dans des volumes Docker nommés ou, lorsque nécessaire, dans `.yia-data/` à la racine du projet.
5. `yia.yml` est la source de vérité de la configuration de l'environnement.
6. Le Makefile racine du projet ne contient aucune logique métier Yia.
7. Toute opération d'infrastructure exposée à l'utilisateur passe par le Makefile.
8. Les fichiers Docker/Compose générés ne doivent jamais être modifiés manuellement.
9. Une modification de `yia.yml` suivie de `make update` doit converger vers l'état décrit.
10. `make update` doit être idempotent.
11. Une mise à jour Yia ne doit pas modifier le code métier des applications sans demande explicite.
12. Toute destruction de données persistantes doit nécessiter une commande explicitement destructive.
13. Une erreur de validation doit empêcher la génération ou le démarrage d'un état partiellement incohérent.
14. Les secrets ne doivent jamais être écrits dans `yia.yml` ni dans un fichier versionné par défaut.
15. Une commande Yia doit produire le même résultat pour un même `yia.yml`, une même version de Yia et un même ensemble d'entrées externes.

---

## 7. Structure d'un projet initialisé

```text
mon-projet/
├── .git/
├── .gitmodules
│
├── .yia/                    # sous-module Git Yia, lecture seule
│   ├── Makefile
│   ├── docker/
│   ├── compose/
│   ├── scripts/
│   ├── templates/
│   ├── schemas/
│   ├── docs/
│   └── ...
│
├── .yia-runtime/            # généré, jetable, ignoré par Git
│   ├── compose/
│   ├── apache/
│   ├── php/
│   ├── node/
│   ├── env/
│   ├── state/
│   └── logs/
│
├── .yia-data/               # optionnel, persistant local, ignoré par Git
│   └── ...
│
├── .agents/
│   ├── skills/
│   ├── docs/
│   └── ...
│
├── apps/
│   ├── frontend/
│   └── api/
│
├── yia.yml                  # configuration déclarative du projet
├── .env                     # valeurs locales / secrets, non versionné
├── .env.example             # variables attendues, versionné
├── AGENTS.md
├── Makefile                 # proxy vers .yia/Makefile
└── README.md
```

### 7.1. Contrat `.yia/`

`.yia/` est immuable depuis un projet consommateur.

Yia ne doit jamais y créer :

- de cache ;
- de logs ;
- d'état ;
- de fichiers Compose générés ;
- de volumes bind ;
- de données propres au projet.

### 7.2. Contrat `.yia-runtime/`

`.yia-runtime/` contient exclusivement des artefacts générés ou temporaires.

Son contenu doit pouvoir être entièrement supprimé puis reconstruit avec :

```bash
rm -rf .yia-runtime
make update
```

Si cette opération entraîne une perte fonctionnelle irréversible, le fichier concerné n'avait pas sa place dans `.yia-runtime/`.

### 7.3. Contrat `.yia-data/`

`.yia-data/` est réservé aux données locales persistantes qui ne peuvent ou ne doivent pas être stockées dans un volume Docker nommé.

Il ne doit pas contenir de configuration générable.

Par défaut, Yia doit préférer les volumes Docker nommés aux bind mounts persistants.

---

## 8. Workflow de démarrage d'un projet

```bash
mkdir my-project
cd my-project

git init

git submodule add git@github.com:xxx/yia.git .yia

cp .yia/templates/yia.yml ./yia.yml
cp .yia/templates/Makefile ./Makefile

make init
```

`make init` peut également créer les fichiers manquants à partir des templates si le contrat de la commande le prévoit.

---

## 9. Workflow de modification du besoin

Le besoin utilisateur peut être exprimé de trois manières :

1. modification manuelle de `yia.yml` ;
2. utilisation d'une CLI Yia qui modifie `yia.yml` ;
3. intervention d'un agent tel que Codex qui modifie `yia.yml` conformément au schéma et aux règles du projet.

Le workflow nominal est ensuite :

```text
besoin utilisateur
      ↓
yia.yml
      ↓
make validate
      ↓
make update
      ↓
artefacts générés
      ↓
Docker Compose
      ↓
make doctor
```

L'utilisateur ou Codex ne doit pas modifier directement les fichiers générés pour exprimer le besoin.

---

## 10. Contrat de `yia.yml`

### 10.1. Rôle

`yia.yml` décrit l'état attendu de l'environnement de développement.

Il ne décrit pas l'état courant de Docker et ne doit pas contenir de données dérivées pouvant être recalculées par Yia.

### 10.2. Version de schéma

Le schéma de `yia.yml` est versionné.

```yaml
version: 1
```

Le champ `version` correspond à la version du format de configuration Yia, et non à la version du projet ni à la version du moteur Yia.

### 10.3. Exemple normatif minimal

```yaml
version: 1

project:
  name: my-project

environment:
  domain: my-project.localhost

services:
  postgres:
    enabled: true
    version: "18"

applications:
  api:
    type: php
    path: apps/api

    runtime:
      php: "8.4"

    framework:
      name: laravel
      version: 13

    web:
      hostname: api.my-project.localhost
      public_directory: public

  frontend:
    type: node
    path: apps/frontend

    runtime:
      node: "24"

    framework:
      name: nuxt
      version: 4

    web:
      hostname: my-project.localhost
      port: 3000
```

### 10.4. Règles de validation

Yia doit refuser un `yia.yml` invalide avant toute modification d'infrastructure.

La validation doit au minimum contrôler :

- la version de schéma ;
- les champs obligatoires ;
- les types de valeurs ;
- l'unicité des noms d'applications ;
- l'unicité des hostnames ;
- les chemins applicatifs ;
- les versions de runtime supportées ;
- la cohérence entre type d'application et runtime ;
- la cohérence entre options web et type d'application ;
- les ports internes lorsqu'ils sont configurés ;
- les références vers des services existants.

Les erreurs doivent identifier :

- le chemin YAML concerné ;
- la valeur reçue ;
- la contrainte attendue ;
- une suggestion corrective lorsque cela est possible.

### 10.5. Valeurs par défaut

Les valeurs par défaut doivent être documentées dans le schéma.

Yia peut appliquer des valeurs par défaut, mais les valeurs calculées doivent être inspectables avec une commande telle que :

```bash
make config
```

Cette commande doit afficher la configuration effective après validation et résolution des valeurs par défaut, sans modifier le projet.

### 10.6. Extensions

Les futures versions du schéma doivent privilégier l'ajout de champs optionnels compatibles plutôt que la modification sémantique silencieuse de champs existants.

---

## 11. Modèle Docker

### 11.1. Point d'entrée HTTP

Apache est le point d'entrée HTTP unique de l'environnement.

Par défaut, les applications ne publient pas directement leur port applicatif sur l'hôte.

### 11.2. Applications PHP

Les applications PHP sont servies via PHP-FPM.

Apache assure le routage HTTP vers le runtime PHP concerné.

Les applications PHP d'une même version peuvent partager un runtime lorsque la conception du runtime le permet et que leurs dépendances système sont compatibles.

Le choix entre un runtime partagé par version et un runtime dédié par application doit être déterministe et documenté par Yia. La première implémentation doit privilégier un runtime partagé par version afin de correspondre à l'objectif de mutualisation de Yia.

### 11.3. Applications Node

Les applications Node exposent leur port uniquement sur le réseau Docker privé.

Apache assure le reverse proxy vers ce port.

Une publication directe sur l'hôte n'est autorisée que lorsqu'elle est explicitement demandée dans `yia.yml`.

### 11.4. PostgreSQL

PostgreSQL est accessible aux applications via le réseau Docker privé.

Il n'est accessible depuis l'hôte que si cette exposition est explicitement activée dans `yia.yml`.

### 11.5. Réseau

Chaque projet Yia possède au minimum un réseau Docker privé propre au projet.

Le nom Docker réel doit être dérivé du nom de projet de façon déterministe et éviter les collisions avec d'autres projets Yia.

Les noms logiques dans `yia.yml` ne doivent pas dépendre des noms de containers générés.

### 11.6. Nommage des containers et ressources

Yia doit utiliser un project name Docker Compose stable dérivé de `project.name`.

Les ressources Docker doivent être nommées de manière prévisible :

```text
<project>_<service>
<project>_<runtime>
<project>_<volume>
<project>_<network>
```

Le code applicatif ne doit jamais dépendre directement du nom physique d'un container lorsque le nom de service Docker suffit.

### 11.7. Volumes

Les données persistantes doivent utiliser des volumes nommés par défaut.

Une mise à jour ou reconstruction d'image ne doit pas supprimer ces volumes.

La suppression des volumes nécessite une commande explicitement destructive telle que :

```bash
make destroy
```

ou une option explicitement nommée indiquant la perte de données.

### 11.8. Healthchecks

Les services pouvant exposer un état de santé doivent posséder un healthcheck.

`make doctor` doit distinguer au minimum :

- container non démarré ;
- container démarré mais unhealthy ;
- service accessible ;
- dépendance manquante ;
- configuration invalide.

---

## 12. Génération

### 12.1. Principe

Les générateurs Yia transforment la configuration effective en artefacts Docker et applicatifs d'infrastructure.

```text
yia.yml
   ↓
validation
   ↓
normalisation / defaults
   ↓
modèle interne
   ↓
générateurs
   ├── compose
   ├── apache
   ├── php
   ├── node
   └── env runtime
```

### 12.2. Déterminisme

À configuration identique, version Yia identique et entrées identiques, la génération doit produire les mêmes fichiers.

Les fichiers générés ne doivent pas contenir de données volatiles inutiles telles que des timestamps si elles empêchent de vérifier l'idempotence.

### 12.3. Écriture atomique

Lorsque possible, Yia doit générer les nouveaux fichiers dans une zone temporaire, valider l'ensemble puis remplacer l'ancien runtime.

Une erreur de génération ne doit pas laisser `.yia-runtime/` dans un état partiellement mis à jour pouvant être confondu avec un état valide.

### 12.4. État interne

Si Yia a besoin de mémoriser un état interne, celui-ci doit être stocké dans `.yia-runtime/state/` et être reconstruisible.

Il ne doit jamais devenir une seconde source de vérité concurrente de `yia.yml`.

---

## 13. API Make

Le Makefile Yia constitue l'API publique stable de Yia.

Les scripts de `.yia/scripts/` sont des détails d'implémentation et ne doivent pas être invoqués directement par un utilisateur ou Codex dans un projet consommateur.

### 13.1. Makefile racine du projet

Le Makefile du projet est un proxy sans logique métier :

```make
%:
	@$(MAKE) -C .yia $@
```

Si des variables ou arguments doivent être transmis, le proxy doit les transmettre sans réinterpréter la commande.

### 13.2. Commandes publiques minimales

```text
make help
make install
make check-install
make init
make validate
make config
make update
make up
make down
make restart
make ps
make status
make doctor
make logs
make logs SERVICE=xxx
make shell SERVICE=xxx
make build
make rebuild
make test
make clean
make reset
make destroy
make version
```

---

## 14. Contrats des commandes Make

### 14.1. `make help`

Affiche les commandes publiques, leurs paramètres principaux et les commandes destructives clairement identifiées.

Ne modifie aucun fichier.

### 14.2. `make install`

Installe ou guide l'installation des dépendances système nécessaires à Yia.

Contrat :

- détecter le système supporté ;
- ne pas masquer les opérations nécessitant des privilèges ;
- afficher les composants qui seront installés ;
- ne pas modifier le projet applicatif ;
- être relançable sans provoquer d'installation incohérente.

### 14.3. `make check-install`

Vérifie les prérequis nécessaires à l'exécution de Yia.

Doit notamment vérifier :

- Docker ;
- Docker Compose ;
- Git ;
- Make ;
- droits d'accès au daemon Docker ;
- présence et état du submodule `.yia/` ;
- compatibilité minimale des versions.

Ne doit rien installer.

### 14.4. `make init`

Initialise Yia pour un nouveau projet.

Doit notamment :

- vérifier que Yia est exécuté depuis un projet valide ;
- vérifier ou créer les fichiers projet attendus selon le contrat d'initialisation ;
- vérifier la présence de `yia.yml` ;
- valider `yia.yml` contre son schéma ;
- créer `.yia-runtime/` ;
- créer `.yia-data/` uniquement si nécessaire ;
- générer Docker Compose ;
- générer la configuration Apache ;
- générer les configurations PHP/Node nécessaires ;
- créer `.env` depuis `.env.example` uniquement s'il n'existe pas ;
- ne jamais écraser une valeur locale `.env` existante ;
- créer ou mettre à jour les fichiers de documentation explicitement gérés par Yia ;
- effectuer les validations finales ;
- afficher un résumé de l'environnement créé.

`make init` ne doit pas écraser silencieusement un projet déjà initialisé.

Une réinitialisation forcée doit nécessiter une option explicite ou une commande distincte.

### 14.5. `make validate`

Valide sans effet de bord :

- `yia.yml` ;
- les chemins référencés ;
- les conflits de hostnames ;
- les versions supportées ;
- les variables obligatoires ;
- les dépendances déclarées.

Retourne un code de sortie non nul en cas d'erreur.

### 14.6. `make config`

Affiche la configuration effective résolue :

- configuration déclarée ;
- valeurs par défaut ;
- noms Docker calculés ;
- hostnames ;
- runtimes ;
- services activés.

Ne modifie rien.

Les secrets doivent être masqués.

### 14.7. `make update`

Synchronise l'environnement avec l'état déclaré dans `yia.yml`.

Le résultat attendu est :

```text
état courant + yia.yml -> état cible
```

La commande doit être idempotente.

Elle peut :

- ajouter un service ;
- retirer un service non persistant ;
- changer une version ;
- ajouter ou retirer une application de la configuration générée ;
- régénérer Apache ;
- régénérer Docker Compose ;
- régénérer les configurations runtime ;
- mettre à jour les artefacts `.yia-runtime/`.

Elle ne doit pas :

- modifier le code métier ;
- supprimer des volumes contenant des données ;
- supprimer `.yia-data/` ;
- modifier `.yia/` ;
- changer silencieusement le schéma `yia.yml` ;
- appliquer une migration destructive sans consentement explicite.

### 14.8. `make up`

Démarre l'environnement généré.

Doit échouer si la configuration n'est pas valide.

Peut déclencher automatiquement une régénération uniquement si cette politique est documentée et déterministe. La stratégie recommandée est : validation puis génération si nécessaire, puis démarrage.

### 14.9. `make down`

Arrête les containers du projet sans supprimer les données persistantes.

### 14.10. `make restart`

Effectue un arrêt puis un redémarrage sans suppression de données.

### 14.11. `make ps`

Affiche l'état Docker brut ou synthétique des containers appartenant au projet.

### 14.12. `make status`

Affiche une vue fonctionnelle de l'environnement :

- applications ;
- services ;
- runtimes ;
- URLs ;
- état de santé ;
- versions.

### 14.13. `make doctor`

Effectue un diagnostic complet sans opération destructive.

Doit vérifier au minimum :

- prérequis système ;
- configuration ;
- génération ;
- réseau ;
- état des containers ;
- healthchecks ;
- résolution des services ;
- accessibilité Apache ;
- dépendances applicatives essentielles déclarées.

Le diagnostic doit distinguer erreur, avertissement et information.

### 14.14. `make logs`

Sans paramètre, affiche les logs de l'environnement ou une vue agrégée raisonnable.

Avec :

```bash
make logs SERVICE=xxx
```

la commande doit cibler uniquement le service logique demandé.

### 14.15. `make shell SERVICE=xxx`

Ouvre un shell dans le service logique demandé.

Le nom attendu est le nom logique Yia et non le nom physique du container.

### 14.16. `make build`

Construit les images nécessaires sans supprimer les volumes.

### 14.17. `make rebuild`

Force la reconstruction des images et la recréation des containers sans supprimer les données persistantes par défaut.

### 14.18. `make test`

Exécute les tests propres au moteur Yia lorsqu'il est exécuté dans le dépôt Yia, ou les validations/tests d'intégration Yia applicables au projet consommateur.

Il ne doit pas supposer automatiquement la commande de test métier de chaque framework sans configuration explicite.

### 14.19. `make clean`

Supprime uniquement les artefacts régénérables de `.yia-runtime/` et les ressources temporaires documentées.

Ne supprime aucune donnée persistante.

### 14.20. `make reset`

Reconstruit l'environnement local à partir de `yia.yml` sans supprimer les données persistantes par défaut.

Un reset avec perte de données doit utiliser une option explicitement destructive ou `make destroy`.

### 14.21. `make destroy`

Commande destructive explicite.

Peut supprimer :

- containers ;
- réseaux ;
- volumes persistants Yia ;
- `.yia-runtime/` ;
- `.yia-data/` si explicitement inclus dans le contrat.

Doit afficher clairement ce qui sera détruit avant l'opération.

### 14.22. `make version`

Affiche :

- version Yia ;
- commit Git du submodule ;
- version du schéma `yia.yml` ;
- versions des principaux outils détectés.

---

## 15. Gestion de `.env` et des secrets

### 15.1. `.env.example`

`.env.example` est versionné et documente les variables attendues sans secret réel.

### 15.2. `.env`

`.env` contient les valeurs locales et doit être ignoré par Git par défaut.

Yia peut ajouter de nouvelles clés manquantes de manière sûre, mais ne doit jamais remplacer silencieusement une valeur existante.

### 15.3. Secrets

Les secrets ne doivent pas être inscrits dans :

- `yia.yml` ;
- `.env.example` ;
- `.yia-runtime/` dans un fichier destiné à être affiché ou partagé ;
- la documentation générée.

Les commandes `make config`, `make status` et `make doctor` doivent masquer les valeurs sensibles.

---

## 16. Versioning de Yia

### 16.1. Version du moteur

Yia doit posséder une version propre, idéalement suivant Semantic Versioning.

Exemple :

```text
Yia 1.4.0
```

### 16.2. Version du projet consommateur

Le projet référence un commit précis du submodule `.yia/`.

La mise à jour de Yia dans un projet doit être une modification Git explicite et réversible.

### 16.3. Compatibilité

Une version Yia doit déclarer les versions de schéma `yia.yml` qu'elle supporte.

Une incompatibilité doit être détectée avant génération.

---

## 17. Migration de schéma

Les changements incompatibles du format `yia.yml` nécessitent une nouvelle version de schéma.

Exemple :

```yaml
version: 2
```

Yia doit pouvoir :

- détecter qu'un schéma est ancien ;
- expliquer la migration nécessaire ;
- fournir, lorsque possible, une commande ou un outil de migration ;
- ne jamais migrer silencieusement un fichier versionné sans montrer les changements.

Une commande future peut être :

```bash
make migrate-config
```

La migration doit être idempotente et produire un diff inspectable.

---

## 18. Compatibilité et changements cassants

Sont considérés comme potentiellement cassants :

- suppression ou renommage d'une commande Make publique ;
- changement de sémantique d'une commande existante ;
- changement incompatible de `yia.yml` ;
- changement du nom ou de l'emplacement d'un fichier projet public ;
- suppression d'un runtime supporté ;
- modification de la stratégie de persistance pouvant provoquer une perte de données.

Ces changements doivent être :

- documentés ;
- versionnés ;
- accompagnés d'une migration lorsque raisonnablement possible.

---

## 19. Gestion des erreurs

Yia doit échouer explicitement et le plus tôt possible.

Un message d'erreur doit préciser :

1. ce qui a échoué ;
2. où se situe l'erreur ;
3. pourquoi Yia considère cet état invalide ;
4. comment la corriger lorsque Yia peut le déterminer.

Les commandes doivent retourner des codes de sortie cohérents afin d'être utilisées par Codex et par la CI.

Yia ne doit pas transformer une erreur critique en simple avertissement si l'environnement obtenu serait incohérent.

---

## 20. Observabilité locale

Les commandes Yia doivent produire des sorties lisibles par un humain et suffisamment structurées pour être interprétables par un agent.

À terme, les commandes critiques peuvent supporter un format machine-readable :

```bash
make status FORMAT=json
make doctor FORMAT=json
make config FORMAT=json
```

Le format texte reste le format humain par défaut.

---

## 21. Système de documentation projet

Yia initialise et maintient un système de documentation destiné aux humains et aux agents.

Ce système comprend notamment :

- `.agents/docs/` ;
- `.agents/docs/INDEX.md` ;
- le skill `project-docs` ;
- le skill `update-project-docs` ;
- l'intégration des règles documentaires dans `AGENTS.md` ;
- la documentation dérivée de `yia.yml`.

Le contrat détaillé du sous-système documentaire est défini dans :

> [`documentation.md`](./documentation.md)

La présente spécification reste normative pour les invariants généraux de Yia.

Pour tout comportement spécifique au système documentaire, `documentation.md` constitue la référence normative tant qu'elle ne contredit pas un invariant global de Yia.

Les invariants documentaires globaux sont :

1. la documentation projet n'est jamais stockée dans `.yia/` ;
2. `make init` initialise le système documentaire ;
3. `make update` préserve la documentation humaine ;
4. les opérations documentaires doivent être idempotentes ;
5. les secrets ne doivent jamais être copiés dans la documentation ;
6. la documentation dérivée ne remplace jamais sa source de vérité ;
7. `project-docs` et `update-project-docs` font partie des capacités de base d'un projet Yia.

---

## 22. Intégration Codex et agents

### 22.1. Mode développement Yia

Lorsque Codex travaille dans le dépôt Yia lui-même :

- il peut modifier les sources Yia ;
- il doit maintenir la compatibilité de l'API Make publique ;
- il doit ajouter ou adapter les tests ;
- il doit mettre à jour la documentation ;
- il doit éviter les breaking changes sans changement de version ou de schéma ;
- il doit considérer cette spécification comme normative ;
- il doit signaler toute contradiction entre le code et la spécification.

### 22.2. Mode projet consommateur

Lorsque Codex travaille dans un projet utilisant Yia :

- `.yia/` est en lecture seule ;
- Codex lit `yia.yml` avant toute modification d'infrastructure ;
- Codex modifie `yia.yml` pour exprimer l'état souhaité ;
- Codex utilise les commandes Make publiques ;
- Codex ne modifie jamais les artefacts générés dans `.yia-runtime/` ;
- Codex ne contourne pas Yia avec un `docker compose` direct sauf diagnostic explicitement justifié ;
- Codex ne supprime jamais de données persistantes sans demande explicite ;
- Codex met à jour la documentation projet lorsque la modification change l'architecture fonctionnelle ou technique.

### 22.3. Ordre de lecture recommandé pour Codex

Avant une tâche d'infrastructure dans un projet consommateur :

1. lire `AGENTS.md` ;
2. lire `yia.yml` ;
3. lire la documentation projet pertinente ;
4. consulter la documentation Yia uniquement si nécessaire ;
5. modifier la source de vérité ;
6. lancer `make validate` ;
7. lancer `make update` ;
8. lancer `make doctor` ;
9. exécuter les tests pertinents.

---

## 23. AGENTS.md minimal recommandé

```markdown
# Environnement de développement

Ce projet utilise Yia comme environnement de développement.

Yia est installé comme sous-module Git dans `.yia/`.

## Règles impératives

- Ne jamais modifier `.yia/` depuis ce projet.
- Lire `yia.yml` avant toute modification d'infrastructure.
- `yia.yml` est la source de vérité de l'environnement.
- Ne jamais modifier directement `.yia-runtime/`.
- Utiliser les commandes Make de Yia.
- Ne pas appeler directement Docker Compose pour modifier l'état de l'environnement.
- Ne jamais supprimer les données persistantes sans demande explicite.
- Utiliser `project-docs` lorsqu'une connaissance existante du projet peut influencer la tâche.
- Utiliser `update-project-docs` lorsqu'une tâche introduit, modifie ou invalide une connaissance durable.

## Workflow infrastructure

1. Modifier `yia.yml`.
2. Exécuter `make validate`.
3. Exécuter `make update`.
4. Exécuter `make doctor`.
5. Exécuter les tests pertinents.

## Definition of Done

Une évolution d'infrastructure est terminée lorsque :

- `make validate` réussit ;
- `make doctor` réussit ;
- `make update` peut être exécuté deux fois sans changement supplémentaire ;
- les services attendus démarrent ;
- les healthchecks passent ;
- les tests pertinents passent ;
- la documentation concernée est mise à jour ;
- le système documentaire respecte [`documentation.md`](./documentation.md) lorsqu'il est concerné ;
- la documentation dérivée est synchronisée avec `yia.yml` lorsqu'elle est concernée ;
- aucun fichier spécifique au projet n'a été créé dans `.yia/`.
```

---

## 24. Briques fonctionnelles initiales

| Brique | Rôle |
|---|---|
| Docker Compose | Orchestration |
| Apache | Reverse proxy unique |
| PHP-FPM multi-version | Laravel / Symfony / PHP legacy |
| Node multi-version | Nuxt / applications Node |
| PostgreSQL | Base de données par défaut |
| Xdebug optionnel | Debug PHP |
| Makefile | Interface humaine + Codex |
| `yia.yml` | Description machine-readable |
| `AGENTS.md` | Règles principales Codex |
| `.agents/docs` | Connaissance projet |
| `.agents/skills` | Workflows Codex |
| Healthchecks | Vérification automatique |
| `make doctor` | Diagnostic environnement |
| `.env.example` | Configuration reproductible |

Les briques comme Redis, RabbitMQ, Mailpit, MinIO ou OpenSearch doivent être ajoutées comme modules optionnels et ne pas devenir des dépendances obligatoires du cœur Yia.

---

## 25. Tests

Yia doit disposer de plusieurs niveaux de tests.

### 25.1. Tests de schéma

Vérifier :

- configurations valides ;
- configurations invalides ;
- defaults ;
- erreurs de type ;
- conflits de noms ;
- compatibilité de version.

### 25.2. Tests de génération

À partir d'un `yia.yml` donné, vérifier les artefacts générés attendus.

### 25.3. Tests d'idempotence

Le scénario suivant doit produire zéro modification au second passage :

```bash
make update
make update
```

### 25.4. Tests d'intégration Docker

Pour des fixtures représentatives :

- construire ;
- démarrer ;
- attendre les healthchecks ;
- tester les URLs ;
- tester la résolution inter-services ;
- arrêter proprement.

### 25.5. Tests de non-régression

Les commandes Make publiques doivent disposer d'une couverture empêchant les changements de contrat accidentels.

---

## 26. Definition of Done — développement de Yia

Une évolution du moteur Yia est terminée lorsque :

- les fichiers modifiés respectent cette architecture ;
- le schéma est mis à jour si nécessaire ;
- `make validate` réussit sur les fixtures prévues ;
- `make doctor` réussit sur un environnement de référence ;
- `make update` est idempotent ;
- `make up` démarre les services attendus ;
- tous les healthchecks passent ;
- les tests automatisés passent ;
- les erreurs importantes disposent d'un message exploitable ;
- les changements cassants sont documentés et versionnés ;
- la documentation concernée est mise à jour ;
- le système documentaire respecte [`documentation.md`](./documentation.md) lorsqu'il est concerné ;
- la documentation dérivée est synchronisée avec `yia.yml` lorsqu'elle est concernée ;
- aucun état spécifique à un projet consommateur n'est écrit dans le dépôt Yia.

---

## 27. Definition of Done — modification d'un projet consommateur

Une modification de l'environnement d'un projet est terminée lorsque :

- `yia.yml` représente l'état attendu ;
- `make validate` réussit ;
- `make update` réussit ;
- un second `make update` ne produit pas de changement ;
- `make doctor` réussit ;
- les applications et services attendus sont accessibles ;
- aucune donnée persistante non ciblée n'a été supprimée ;
- `.yia/` n'a pas été modifié ;
- les modifications versionnées sont limitées aux fichiers appartenant au projet ;
- la documentation projet est cohérente avec le nouvel état.

---

## 28. Principes d'implémentation pour Codex

Lorsqu'une décision d'implémentation n'est pas explicitement couverte par cette spécification, Codex doit privilégier dans cet ordre :

1. la sécurité des données ;
2. la reproductibilité ;
3. l'idempotence ;
4. la compatibilité ascendante ;
5. la simplicité d'utilisation ;
6. la simplicité d'implémentation ;
7. la performance locale.

Codex ne doit pas inventer silencieusement un nouveau contrat public. Lorsqu'une nouvelle décision structurante est nécessaire, elle doit être documentée avant ou avec son implémentation.
