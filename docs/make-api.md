# Yia — Spécification de l'API Make

> **Statut :** normative  
> **Document parent :** [`yia-spec.md`](./yia-spec.md)  
> **Identifiant :** `YIA-SPEC-MAKE`  
> **Version API :** 1

## 1. Objet

Cette sous-spécification définit l'API publique Make de Yia.

Le Makefile constitue l'interface humaine stable.

La CLI Python est interne, même si certaines commandes peuvent être exécutées directement à des fins de développement.

---

## 2. Compatibilité

Les noms de cibles Make et leurs codes de retour documentés constituent une API stable en V1.

Une modification incompatible nécessite une décision explicite et une évolution de version appropriée.

---

## 3. Codes de sortie stables

| Code | Signification |
|---:|---|
| 0 | succès |
| 1 | erreur générique |
| 2 | configuration invalide |
| 3 | dépendance système absente |
| 4 | génération impossible |
| 5 | Docker indisponible |
| 6 | migration nécessaire |

Les codes symboliques associés sont notamment :

- `YIA_GENERIC_ERROR`
- `YIA_CONFIG_INVALID`
- `YIA_DEPENDENCY_MISSING`
- `YIA_GENERATION_FAILED`
- `YIA_DOCKER_UNAVAILABLE`
- `YIA_MIGRATION_REQUIRED`

---

## 4. Sorties machine

Les commandes suivantes supportent :

```text
FORMAT=json
```

ou l'équivalent CLI interne :

```text
--json
```

Commandes :

- `version`
- `validate`
- `doctor`
- `status`
- `ps`

Lorsqu'une sortie JSON est demandée :

- stdout contient uniquement le JSON ;
- aucun texte humain parasite ne doit être écrit sur stdout ;
- les erreurs utilisent également une structure JSON stable.

---

## 5. `make help`

Affiche les commandes publiques et leurs options principales.

Doit fonctionner sans Docker.

---

## 6. `make version`

Affiche :

- version Yia ;
- commit Git du moteur lorsqu'il est disponible ;
- version du schéma `yia.yml` ;
- version du schéma documentaire ;
- versions de Python, Git, Make, Docker et Docker Compose lorsqu'ils sont
  détectés.

La détection des versions ne contacte pas le daemon Docker. Un outil absent est
signalé comme indisponible et ne fait pas échouer la commande.

Supporte `FORMAT=json`.

---

## 7. `make install`

### Objectif

Installer les dépendances nécessaires à Yia sur une machine compatible APT.

### Périmètre V1

Uniquement les systèmes disposant de :

```text
apt
```

Yia peut notamment installer ou configurer :

- Docker ;
- Docker Compose plugin ;
- Git ;
- Make ;
- Python et dépendances requises.

L'implémentation V1 affiche d'abord la liste puis utilise `apt-get` pour les
paquets `docker.io`, `docker-compose-v2`, `git`, `make`, `python3` et
`python3-venv`. Elle utilise `sudo` uniquement lorsque le processus n'est pas
déjà exécuté avec les privilèges nécessaires.

### Règle

Sur un système non compatible APT, la commande doit échouer proprement avec une erreur explicite.

Elle ne doit pas tenter une installation adaptée à une autre famille de distribution.

---

## 8. `make check-install`

Vérifie les prérequis sans les modifier.

Doit notamment vérifier :

- Docker ;
- Docker Compose ;
- Git ;
- Make ;
- Python compatible ;
- permissions Docker pertinentes.

---

## 9. `make init`

Initialise un projet consommateur.

Doit notamment :

- valider `yia.yml` ;
- créer les répertoires runtime requis ;
- générer les fichiers ;
- initialiser le système documentaire ;
- préparer Docker.

`make init` ne démarre pas automatiquement les containers.

L'utilisateur utilise ensuite :

```bash
make up
```

En V1, `init` :

- vérifie que le sous-module attendu est disponible dans `.yia/` ;
- valide `yia.yml` et les dépendances applicatives avant toute écriture ;
- crée le Makefile proxy et `.env.example` uniquement lorsqu'ils sont absents ;
- crée `.env` depuis le `.env.example` effectif uniquement lorsqu'il est
  absent, sans jamais remplacer une valeur locale ;
- initialise et valide la documentation projet ;
- génère et valide `.yia-runtime/` sans appeler Docker ;
- ne crée pas `.yia-data/`, la persistance V1 utilisant des volumes nommés ;
- refuse un projet déjà complètement initialisé et recommande `make update`
  plutôt que de réinitialiser silencieusement les fichiers gérés.

En V2, `init` valide d'abord la configuration sans exiger l'existence des
destinations `managed`, puis clone leurs tags Git dans `apps/` avant la
validation des fichiers applicatifs et la génération. Une erreur Git ne publie
pas de dossier partiellement cloné. Les sources `linked` restent intactes.
`init` ne démarre aucun conteneur et n'exécute donc ni SQL PostgreSQL ni
script `initialization.once`.

Le passage d'un état généré V1 à une configuration V2 requiert une migration
explicite : `update` signale `YIA_MIGRATION_REQUIRED` jusqu'à la suppression
volontaire des seuls artefacts reconstructibles par `make clean`.

---

## 10. `make validate`

Valide :

- `yia.yml` ;
- schéma ;
- cohérence sémantique applicable.

Supporte `FORMAT=json`.

Ne doit pas modifier le projet.

Les chemins d'initialisation sont contrôlés sans exécuter leurs fichiers.
Le script d'une application `managed` absente est contrôlé après son clonage.

En V2, une destination `managed` absente est valide sur le plan déclaratif :
`validate` ne clone pas et n'interroge pas le dépôt distant. Les dépendances
applicatives présentes sont contrôlées ; celles d'un clone absent le seront
après acquisition par `init` ou `update`.

---

## 11. `make generate`

Génère les artefacts runtime sans démarrer, reconstruire ni redémarrer Docker.

Cas d'usage :

- inspection ;
- tests ;
- debug ;
- génération en amont d'un lancement.

Doit être idempotent.

`generate` n'acquiert aucune source : les applications `managed` doivent déjà
avoir été récupérées par `init` ou `update`.

En V1, les commandes Docker `up`, `restart`, `build`, `rebuild`, `logs`,
`shell` et `exec` exigent que cette génération soit à jour. Un runtime absent,
modifié ou obsolète produit `YIA_GENERATION_FAILED` et recommande explicitement
`make generate`. `make up` ne régénère donc pas implicitement pendant la phase
10.

---

## 12. `make update`

Fait converger l'environnement courant vers l'état décrit dans `yia.yml`.

Workflow attendu :

```text
valider la configuration
  ↓
normaliser
  ↓
acquérir les sources managed au tag demandé
  ↓
valider les fichiers applicatifs
  ↓
générer
  ↓
déterminer les services affectés
  ↓
build si nécessaire
  ↓
recréer / redémarrer automatiquement les services affectés
  ↓
healthchecks
```

`make update` applique donc automatiquement les changements nécessaires.

Après la convergence et les healthchecks, `update` vérifie l'empreinte du SQL
PostgreSQL éventuellement déclaré puis exécute les scripts
`initialization.once` dépourvus de marqueur. `up`, `restart`, `rebuild` et
`reset` font le même contrôle après démarrage. Ces commandes préservent les
marqueurs de `.yia-data/once/` ; un nouvel identifiant de hook demande une
nouvelle exécution.

Il doit être idempotent.

Il ne doit pas redémarrer inutilement un service non affecté lorsque l'implémentation peut déterminer qu'il n'a pas changé.

En V1, `update` :

- refuse avant toute écriture un état interne dont la version requiert une
  migration ;
- synchronise la documentation dérivée et les artefacts de
  `.yia-runtime/`, sans modifier les fichiers documentaires humains ;
- exécute `docker compose up --detach --wait --remove-orphans --build` lorsque
  la topologie contient au moins un service ; Compose utilise alors son cache
  de build et ne recrée que les containers dont la configuration ou l'image a
  changé ;
- recrée de façon ciblée Apache ou le runtime PHP concerné lorsqu'un fichier de
  configuration généré monté en bind a changé sans modifier le modèle Compose ;
- n'appelle pas Docker lorsque la topologie ne contient aucun service ;
- conserve `.env`, `.yia-data/`, les volumes nommés, les sources et la
  documentation humaine ;
- refuse le changement automatique du nom de projet Compose et retourne
  `YIA_MIGRATION_REQUIRED`, afin de ne pas abandonner silencieusement les
  ressources de l'ancien projet.

Une seconde exécution sur le même `yia.yml` conserve les fichiers générés à
l'identique. Si des services existent, Compose vérifie néanmoins leur
convergence et leurs healthchecks sans recréer les containers inchangés.

---

## 13. `make up`

Démarre l'environnement déjà généré.

Peut effectuer une génération préalable si le contrat d'implémentation le prévoit, mais ne doit pas masquer une configuration invalide.

---

## 14. `make down`

Arrête l'environnement.

Ne supprime pas les données persistantes.

La commande utilise l'identité enregistrée dans le Compose généré et les labels
Docker Compose pour rester utilisable après une modification de `yia.yml`. Elle
arrête proprement puis retire les containers et le réseau du projet, sans
toucher aux volumes.

---

## 15. `make restart`

Redémarre l'environnement sans supprimer les données.

---

## 16. `make build`

Construit les images nécessaires.

Ne démarre pas nécessairement les services.

---

## 17. `make rebuild`

Reconstruit les images et recrée les services nécessaires.

Ne supprime aucune donnée persistante.

La V1 exécute un build sans cache puis recrée les containers avec attente des
healthchecks. Les volumes nommés sont réutilisés.

---

## 18. `make ps`

Affiche les services du projet.

Supporte `FORMAT=json`.

La sortie machine Yia est un objet contenant une liste `services`, triée par
service et nom de container. Chaque entrée expose `name`, `service`, `state`,
`health` et `status`, sans recopier de variable d'environnement.

---

## 19. `make status`

Produit une vue Yia de l'état du projet.

Doit pouvoir distinguer au minimum :

- configuration valide/invalide ;
- génération à jour/obsolète ;
- environnement démarré/arrêté ;
- services sains/non sains.

Supporte `FORMAT=json`.

---

## 20. `make doctor`

Diagnostique l'environnement et les prérequis.

Supporte `FORMAT=json`.

Les checks peuvent inclure :

- système ;
- Docker ;
- Compose ;
- configuration ;
- droits ;
- état runtime ;
- réseau ;
- services.

---

## 21. `make logs`

Par défaut :

```bash
make logs
```

affiche les logs disponibles puis quitte.

Pour une application ou un service :

```bash
make logs SERVICE=api
```

Pour suivre les logs :

```bash
make logs SERVICE=api FOLLOW=1
```

`FOLLOW=1` correspond au comportement de suivi continu.

---

## 22. `make shell`

Ouvre un shell dans la cible demandée :

```bash
make shell SERVICE=api
```

`SERVICE` peut désigner :

- une application ;
- un service d'infrastructure ;
- un runtime lorsque le mapping est non ambigu.

Yia résout la cible vers le container approprié.

---

## 23. `make exec`

Exécute une commande dans une cible :

```bash
make exec SERVICE=api CMD="php artisan migrate"
```

`SERVICE` suit les mêmes règles de résolution que `make shell`.

---

## 24. `make config`

Affiche la configuration normalisée et résolue de Yia.

Cette commande sert à comprendre ce que Yia a réellement interprété après :

- validation ;
- valeurs par défaut ;
- normalisation.

Elle ne doit jamais afficher les secrets issus de `.env`.

---

## 25. `make test`

Exécute les tests Yia lorsque la commande est utilisée dans le repository Yia.

Dans un projet consommateur, son rôle éventuel doit être défini explicitement avant implémentation.

Le comportement V1 est désormais défini ainsi : dans le dépôt Yia, la commande
exécute la suite Pytest du moteur ; dans un projet consommateur, elle exécute
uniquement les validations Yia du projet et ne suppose aucune commande de test
métier.

---

## 26. `make destroy`

Supprime l'environnement Docker généré :

- containers ;
- ressources runtime destructibles ;
- réseau.

Par défaut, les données persistantes doivent être conservées sauf si le contrat exact d'implémentation exige une distinction plus stricte.

La suppression des données utilise une commande séparée.

La V1 supprime les containers et réseaux identifiés par le label Compose exact
du projet, puis `.yia-runtime/`. Elle conserve tous les volumes et `.yia-data/`.

---

## 27. `make destroy-data`

Commande destructive explicite.

Peut supprimer les volumes persistants du projet, notamment PostgreSQL.

Elle doit :

- être explicitement appelée ;
- afficher clairement les données concernées ;
- demander une confirmation interactive sauf option volontaire de mode non interactif explicitement conçue ;
- ne jamais être déclenchée par `update`, `down`, `restart`, `rebuild` ou `destroy`.

Le mode interactif V1 demande de saisir exactement le nom du projet. Le mode
non interactif volontaire est `make destroy-data YES=1`. La commande affiche
les noms exacts des volumes ciblés avant confirmation, supprime d'abord les
containers et réseaux du projet, puis uniquement ses volumes labellisés par
Docker Compose. `.yia-data/` reste conservé.

---

## 28. Installation et droits

Toute commande nécessitant des privilèges système doit le signaler.

Le fonctionnement normal d'un projet ne doit pas exiger `sudo` à chaque commande Docker une fois l'installation correcte.

---

## 29. API humaine vs CLI interne

Exemple :

```text
make update
    ↓
python -m yia update
```

Le contrat public est celui de `make update`.

La CLI Python peut exposer les mêmes primitives afin de simplifier :

- développement ;
- tests ;
- orchestration.

---

## 30. Definition of Done

L'API Make V1 est respectée lorsque :

- `install` ne cible que les systèmes APT ;
- `init` ne lance pas les containers ;
- `update` applique automatiquement les changements ;
- `generate` existe séparément ;
- `logs` ne suit pas par défaut ;
- `FOLLOW=1` active le suivi ;
- `shell` et `exec` résolvent applications et services ;
- `config` affiche le modèle normalisé sans secret ;
- `destroy-data` est explicitement destructif ;
- seuls `doctor`, `validate`, `status`, `ps`, `version` garantissent une sortie JSON ;
- les codes de sortie 0 à 6 sont stables.
