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
