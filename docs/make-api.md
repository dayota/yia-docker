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
- version du schéma `yia.yml` ;
- version du schéma documentaire.

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

---

## 10. `make validate`

Valide :

- `yia.yml` ;
- schéma ;
- cohérence sémantique applicable.

Supporte `FORMAT=json`.

Ne doit pas modifier le projet.

---

## 11. `make generate`

Génère les artefacts runtime sans démarrer, reconstruire ni redémarrer Docker.

Cas d'usage :

- inspection ;
- tests ;
- debug ;
- génération en amont d'un lancement.

Doit être idempotent.

---

## 12. `make update`

Fait converger l'environnement courant vers l'état décrit dans `yia.yml`.

Workflow attendu :

```text
valider
  ↓
normaliser
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

Il doit être idempotent.

Il ne doit pas redémarrer inutilement un service non affecté lorsque l'implémentation peut déterminer qu'il n'a pas changé.

---

## 13. `make up`

Démarre l'environnement déjà généré.

Peut effectuer une génération préalable si le contrat d'implémentation le prévoit, mais ne doit pas masquer une configuration invalide.

---

## 14. `make down`

Arrête l'environnement.

Ne supprime pas les données persistantes.

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

---

## 18. `make ps`

Affiche les services du projet.

Supporte `FORMAT=json`.

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

---

## 26. `make destroy`

Supprime l'environnement Docker généré :

- containers ;
- ressources runtime destructibles ;
- réseau.

Par défaut, les données persistantes doivent être conservées sauf si le contrat exact d'implémentation exige une distinction plus stricte.

La suppression des données utilise une commande séparée.

---

## 27. `make destroy-data`

Commande destructive explicite.

Peut supprimer les volumes persistants du projet, notamment PostgreSQL.

Elle doit :

- être explicitement appelée ;
- afficher clairement les données concernées ;
- demander une confirmation interactive sauf option volontaire de mode non interactif explicitement conçue ;
- ne jamais être déclenchée par `update`, `down`, `restart`, `rebuild` ou `destroy`.

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
