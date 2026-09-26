# Yia — Plan d'implémentation

## Principes

L'implémentation doit progresser par phases courtes et testables.

Chaque phase doit :

- respecter `docs/yia-spec.md` ;
- respecter les sous-spécifications concernées ;
- ajouter les tests correspondant aux nouveaux contrats ;
- préserver les invariants existants ;
- éviter d'introduire prématurément des fonctionnalités appartenant aux phases suivantes.

---

## Phase 0 — Skeleton du repository

### Objectif

Créer une base de dépôt exploitable par Codex et les développeurs.

### Livrables

- `AGENTS.md` ;
- `README.md` ;
- `Makefile` ;
- `pyproject.toml` ;
- package `src/yia/` ;
- `schemas/` ;
- `templates/` ;
- `docker/` ;
- `tests/` ;
- `.gitignore` ;
- `.editorconfig`.

### Definition of Done

- `python -m yia version` fonctionne ;
- `make version` fonctionne ;
- le package Python est importable ;
- les tests unitaires peuvent être exécutés.

---

## Phase 1 — Configuration et validation

### Objectif

Charger et valider `yia.yml`.

### Livrables

- loader YAML ;
- `schemas/yia.schema.json` ;
- erreurs structurées ;
- fixtures valides et invalides ;
- commande `validate` ;
- sortie JSON.

### Definition of Done

- toutes les fixtures valides passent ;
- la fixture invalide échoue avec `YIA_CONFIG_INVALID` ;
- `yia validate --json` ne produit que du JSON sur stdout ;
- aucun comportement Docker n'est encore nécessaire.

---

## Phase 2 — Modèle interne normalisé

### Objectif

Transformer `yia.yml` validé en représentation interne déterministe.

### À implémenter

- dataclasses / modèles internes ;
- valeurs par défaut ;
- résolution des chemins ;
- résolution des noms ;
- normalisation services/applications ;
- calcul d'un hash de configuration.

### Definition of Done

- deux configurations sémantiquement équivalentes produisent le même modèle normalisé ;
- le modèle est testable indépendamment de Docker ;
- le hash est stable.

---

## Phase 3 — État interne

### Objectif

Introduire `.yia-runtime/state/yia-state.json`.

### À implémenter

- lecture / écriture atomique ;
- schema de l'état ;
- versions Yia / configuration / documentation ;
- hash de configuration ;
- détection de migration nécessaire.

### Definition of Done

- l'état est reconstructible ;
- sa suppression ne détruit aucune donnée importante ;
- il ne contient aucun secret ;
- il ne remplace jamais `yia.yml`.

---

## Phase 4 — Génération déterministe

### Objectif

Créer le moteur de génération sans démarrer Docker.

### À implémenter

- abstraction des générateurs ;
- répertoire de staging ;
- génération atomique vers `.yia-runtime/` ;
- manifeste des fichiers générés ;
- détection des changements ;
- idempotence.

### Definition of Done

Deux générations successives sans changement de configuration produisent exactement le même résultat.

---

## Phase 5 — Docker Compose

### Objectif

Générer la topologie Docker déclarée.

### Prérequis

`docs/docker.md` est normative.

### À implémenter

- réseau projet ;
- conventions de noms ;
- volumes ;
- services ;
- healthchecks ;
- fichier Compose généré.

### Definition of Done

Les fixtures applicables génèrent des fichiers Compose valides et déterministes.

---

## Phase 6 — Apache

### Objectif

Implémenter Apache comme point d'entrée HTTP unique.

### À définir avant implémentation

- image de base ;
- stratégie HTTP/HTTPS locale ;
- génération des vhosts ;
- résolution des hostnames ;
- proxy vers Node ;
- liaison avec PHP-FPM.

---

## Phase 7 — PHP

### Objectif

Supporter les runtimes PHP déclarés.

### À définir avant implémentation

- container par runtime ou par application ;
- extensions ;
- Composer ;
- UID/GID ;
- Xdebug ;
- volumes ;
- FPM pools.

---

## Phase 8 — Node

### Objectif

Supporter les applications Node/Nuxt.

### À définir avant implémentation

- container par runtime ou par application ;
- npm/pnpm/yarn ;
- stratégie `node_modules` ;
- mode dev ;
- HMR ;
- UID/GID.

---

## Phase 9 — PostgreSQL

### Objectif

Supporter PostgreSQL comme service d'infrastructure.

### À définir avant implémentation

- version par défaut ;
- un serveur par projet ou configuration avancée ;
- bases/utilisateurs ;
- exposition vers l'hôte ;
- volume persistant ;
- reset/destruction.

### Décisions V1

- aucune version par défaut : le tag est obligatoire dans `yia.yml` ;
- une seule instance mutualisée par projet ;
- une base et un superutilisateur initialisés par l'image officielle, avec
  `postgres` comme valeur par défaut et `POSTGRES_PASSWORD` requis dans `.env` ;
- aucun port hôte par défaut, mapping fixe `5432:5432` avec `expose: true` ;
- volume nommé `postgres-data`, monté selon le layout de la version majeure ;
- `reset`, `down`, `restart`, `rebuild`, `update` et `destroy` préservent les
  données ; seule la commande explicite `destroy-data` peut les supprimer.

---

## Phase 10 — API Make complète

### Objectif

Stabiliser l'API publique.

### Prérequis

`docs/make-api.md` est normative.

### Commandes principales

- `help`
- `install`
- `check-install`
- `version`
- `init`
- `validate`
- `update`
- `up`
- `down`
- `restart`
- `ps`
- `status`
- `doctor`
- `logs`
- `shell`
- `build`
- `rebuild`
- `test`

### Décisions d'implémentation

- toutes les cibles publiques V1 de `make-api.md` sont présentes dans le
  Makefile et routées vers la CLI interne ;
- `generate` constitue l'étape explicite de génération pendant cette phase ;
- les commandes Docker refusent un runtime absent ou obsolète au lieu de le
  régénérer silencieusement ;
- les noms d'applications, services et runtimes sont résolus vers les services
  Compose sans exposer les noms physiques des containers ;
- `destroy` conserve les volumes et `destroy-data` exige une confirmation ou
  `YES=1` ;
- dans un projet consommateur, `test` valide Yia sans inventer une commande de
  test métier ;
- `init` et `update` possèdent leur cible stable mais leur orchestration reste
  explicitement réservée aux phases 12 et 13, après la phase documentaire.

---

## Phase 11 — Documentation projet

### Objectif

Implémenter `docs/documentation.md`.

### À implémenter

- installation de `project-docs` ;
- installation de `update-project-docs` ;
- création de `.agents/docs/` ;
- génération de `INDEX.md` ;
- génération de `development-environment.md` ;
- fusion contrôlée d'`AGENTS.md` ;
- version du schéma documentaire.

### Décisions d'implémentation

- les primitives `install_documentation` et `update_documentation` convergent
  vers la même structure déterministe ; leur orchestration par les cibles Make
  reste réservée aux phases 12 et 13 ;
- `INDEX.md`, le glossaire, le guide des décisions et les deux skills sont
  créés uniquement lorsqu'ils sont absents, puis appartiennent au projet ;
- `architecture/development-environment.md` est le seul document intégralement
  régénéré par Yia pendant cette phase ;
- les règles documentaires d'`AGENTS.md` sont contenues dans une section gérée
  bornée par `YIA:DOCUMENTATION:START` et `YIA:DOCUMENTATION:END` ; tout contenu
  extérieur à cette section est préservé ;
- la version de schéma documentaire reste enregistrée dans l'état interne
  reconstructible et la validation détecte une version incompatible ;
- les écritures refusent les liens symboliques afin de ne jamais sortir de la
  racine du projet consommateur.

---

## Phase 12 — `make init`

### Objectif

Assembler les briques précédentes pour initialiser un projet consommateur.

### Definition of Done

À partir d'un projet vide possédant `.yia/` et `yia.yml` :

```bash
make init
make validate
make doctor
```

fonctionnent conformément aux specs.

### Décisions d'implémentation

- la présence du sous-module `.yia/` correspondant au moteur exécuté est
  vérifiée avant toute écriture dans le projet ;
- `yia.yml` et les dépendances applicatives sont validés avant le bootstrap ;
- le Makefile proxy, `.env.example` puis `.env` sont créés uniquement s'ils
  sont absents et tout fichier local existant est préservé ;
- une variable obligatoire absente, telle que `POSTGRES_PASSWORD`, est signalée
  après création du squelette `.env`, mais avant documentation et génération ;
- l'initialisation installe et valide la documentation, puis publie le runtime
  déterministe sans démarrer Docker ;
- `.yia-data/` n'est pas créé en V1 puisque les données persistantes utilisent
  des volumes Docker nommés ;
- une seconde initialisation complète est refusée sans réécriture et renvoie
  vers `make update` ;
- `make doctor` contrôle désormais la cohérence documentaire du projet.

---

## Phase 13 — `make update`

### Objectif

Faire converger l'environnement courant vers `yia.yml`.

### Definition of Done

```text
état courant + yia.yml -> état cible
```

et :

```bash
make update
make update
```

ne produit aucun changement supplémentaire.

### Décisions d'implémentation

- la compatibilité de l'état interne et la stabilité du nom de projet Compose
  sont contrôlées avant toute écriture ;
- la documentation dérivée et `.yia-runtime/` sont synchronisés de manière
  idempotente, sans écraser les fichiers humains ni `.env` ;
- une topologie contenant des services converge avec Compose en reconstruisant
  les images avec le cache, en retirant les services orphelins et en attendant
  les healthchecks ;
- Compose décide des services dont l'image ou la configuration nécessite une
  recréation ; Apache et les runtimes PHP sont en plus recréés de façon ciblée
  lorsque leurs configurations générées montées en bind changent seules ;
- une topologie vide ne requiert pas Docker ;
- les volumes nommés, `.yia-data/`, les sources applicatives et la
  documentation humaine sont toujours préservés ;
- un changement de nom de projet exige une migration explicite afin de ne pas
  laisser silencieusement des ressources Docker sous l'ancienne identité.

---

## Phase 14 — Tests end-to-end

### Objectif

Tester Yia sur les fixtures principales.

### Scénarios

- minimal ;
- PHP seul ;
- Node seul ;
- PHP + Node ;
- multi-PHP ;
- PostgreSQL ;
- full ;
- configuration invalide.

Aucune CI distante n'est requise à ce stade du projet.

### Décisions d'implémentation

- les sept fixtures valides passent le workflow public `init`, `validate`,
  `test` et `generate`, avec vérification de l'idempotence exacte du runtime ;
- la fixture invalide retourne `YIA_CONFIG_INVALID` et ne crée ni Makefile,
  ni documentation, ni runtime ;
- les fixtures PHP et Node contiennent des sondes HTTP minimales sans
  dépendance externe, afin de tester les images et le routage sans introduire
  de code métier ;
- les six topologies Docker non vides sont testées en mode opt-in via
  `YIA_RUN_DOCKER_INTEGRATION=1`, avec des noms de projet uniques et un
  nettoyage explicite des ressources temporaires ;
- les E2E Docker vérifient les healthchecks, les hostnames PHP et Node, la
  préservation des sources et l'absence de recréation au second passage ;
- le harness retire uniquement la publication du port HTTP au moyen d'un
  override Compose de test, afin de cohabiter avec un port 80 local déjà
  occupé sans modifier le Compose généré ni arrêter un environnement externe ;
- les E2E ont confirmé que les contextes de build doivent rester relatifs au
  fichier Compose généré ; le runner ne force donc plus un
  `--project-directory` incompatible avec `../../.yia/docker/...`.

---

## Phase 15 — Stabilisation 0.1.0

### Objectif

Disposer d'une première version utilisable pour créer de vrais projets.

### Definition of Done

- specs cohérentes ;
- API Make documentée ;
- schéma `yia.yml` versionné ;
- système documentaire fonctionnel ;
- Docker fonctionnel sur les fixtures retenues ;
- tests locaux verts ;
- absence de destruction implicite de données ;
- migration de schéma prévue architecturalement.

### Décisions de stabilisation

- la version `0.1.0`, les versions de schémas exécutables et les ressources
  déclarées pour la distribution sont protégées par des tests de cohérence ;
- `make version` expose le commit, les schémas et les versions de Python, Git,
  Make, Docker et Docker Compose sans contacter le daemon Docker ;
- le contrat de destruction distingue explicitement `destroy`, qui conserve
  les données, de `destroy-data`, qui exige une confirmation ;
- les E2E peuvent conserver leur isolation par défaut ou valider le chemin
  public complet sur le port 80 avec `YIA_E2E_PUBLISH_HTTP=1` ; ce second mode
  couvre `make update`, `make doctor`, le routage HTTP et l'idempotence ;
- une version de schéma incompatible reste arrêtée avant mutation avec
  `YIA_MIGRATION_REQUIRED` et le code de sortie 6, ce qui réserve un point
  d'extension explicite aux futures migrations sans en inventer le contenu.
