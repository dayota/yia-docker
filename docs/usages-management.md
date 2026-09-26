# Yia — Génération et gestion des cas d'usage

> **Statut :** guide publié et validé
> **Nature :** guide pratique non normatif
> **Version Yia ciblée :** 0.1.0

[Consulter l’index des cas d’usage](./usages/index.md).

## 1. Objet

Ce document définit la génération et la gestion éditoriale du guide pratique de
Yia. Il complète les spécifications normatives sans créer de nouveau contrat.
En cas de divergence,
[`yia-spec.md`](./yia-spec.md) et les sous-spécifications concernées restent les
sources de vérité.

Les exemples publiés sont indexés dans
[`usages/index.md`](./usages/index.md).

### 1.1. Organisation des fichiers

- chaque cas fonctionnel `Uxx` est stocké dans `usages/uxx.md` ;
- chaque dépannage `Txx` est stocké dans `usages/txx.md` ;
- `usages/index.md` constitue le point d'entrée et regroupe les liens par thème ;
- un nouveau cas doit mettre à jour simultanément le catalogue, l'index et son
  propre fichier ;
- les liens entre cas sont relatifs afin qu'un fichier reste consultable seul.

L'index reste volontairement court : il décrit la navigation sans recopier le
contenu des cas.

## 2. Format attendu pour chaque exemple

Chaque cas d'usage retenu devrait contenir :

1. l'objectif et les prérequis ;
2. l'arborescence initiale complète ;
3. le fichier `yia.yml` complet ;
4. le fichier `.env.example` et les clés locales attendues, sans secret réel ;
5. les fichiers applicatifs minimaux nécessaires à la démonstration ;
6. toutes les commandes Make, dans leur ordre d'exécution ;
7. les URLs, services, fichiers générés ou sorties attendus ;
8. les commandes de validation et le contrôle d'idempotence ;
9. la procédure de nettoyage et son impact explicite sur les données.

Les exemples doivent utiliser l'API Make publique. Ils ne doivent ni modifier
`.yia/`, ni demander l'édition manuelle de `.yia-runtime/`, ni contenir de
secret.

## 3. Ligne éditoriale

Les blocs peuvent être rédigés et validés indépendamment, sans ordre de
priorité imposé.

Le cas **U24 — projet full stack avec PostgreSQL** sert de fil rouge. Les autres
cas réutilisent autant que possible ses noms, son arborescence et ses choix de
configuration afin de rester cohérents et plus faciles à comparer. Chaque cas
reste néanmoins compréhensible sans devoir lire tous les blocs précédents.

Lorsqu'une capacité possède plusieurs variantes, le guide fournit un exemple
principal complet puis décrit les différences nécessaires pour chaque variante.
Cette règle s'applique notamment aux gestionnaires Node : pnpm constitue
l'exemple principal, complété par les variantes npm et Yarn.

Les opérations PostgreSQL avancées, dont la sauvegarde et la restauration,
restent dans le présent guide.

Tous les scénarios de dépannage sont regroupés dans la section
[Troubleshooting](#5-troubleshooting). Les cas fonctionnels concernés renvoient
vers le scénario de dépannage précis au lieu d'en recopier les étapes.

## 4. Catalogue retenu pour Yia 0.1.0

### 4.1. Installation et prise en main

- **[U01 — Vérifier les prérequis](./usages/u01.md)** : utiliser `make check-install`, comprendre
  les contrôles Python, Git, Make, Docker et Docker Compose, puis corriger une
  dépendance absente ; voir [T01](./usages/t01.md).
- **[U02 — Installer les prérequis sur un système APT](./usages/u02.md)** : présenter
  `make install`, les privilèges nécessaires et la vérification post-installation.
- **[U03 — Ajouter Yia à un nouveau dépôt](./usages/u03.md)** : installer `.yia/` comme sous-module
  Git épinglé et préparer la configuration initiale.
- **[U04 — Initialiser un projet consommateur](./usages/u04.md)** : partir de `yia.yml`, exécuter
  `make init` et expliquer les fichiers humains et documentaires créés sans
  démarrer Docker.
- **[U05 — Adopter Yia dans un dépôt existant](./usages/u05.md)** : préserver le code, le Makefile,
  `.env`, `AGENTS.md` et les documents existants, puis traiter explicitement un
  conflit de fichier humain.
- **[U06 — Créer un projet minimal sans application ni service](./usages/u06.md)** : valider,
  générer et mettre à jour un projet qui ne nécessite pas Docker.
- **[U07 — Valider et inspecter la configuration](./usages/u07.md)** : utiliser `make validate`,
  `make config` et leurs erreurs structurées sans exposer de secret ; voir
  [T03](./usages/t03.md).

### 4.2. Applications PHP

- **[U08 — Exposer une API Laravel en PHP 8.4](./usages/u08.md)** : configurer le hostname, le
  répertoire `public`, Composer et le routage Apache/FastCGI.
- **[U09 — Exposer une application Symfony en PHP 8.2](./usages/u09.md)** : fournir l'équivalent
  complet du scénario Laravel avec le runtime 8.2.
- **[U10 — Exécuter un worker ou une commande PHP sans HTTP](./usages/u10.md)** : omettre `web` et
  utiliser `make exec` ou `make shell`.
- **[U11 — Héberger plusieurs applications sur le même PHP](./usages/u11.md)** : montrer la
  mutualisation du runtime et l'isolation des pools FPM et des volumes
  `vendor`.
- **[U12 — Utiliser PHP 8.2 et PHP 8.4 simultanément](./usages/u12.md)** : router deux applications
  vers deux runtimes dans le même projet.
- **[U13 — Activer Xdebug pour une seule application](./usages/u13.md)** : conserver Xdebug
  désactivé ailleurs, utiliser le trigger et joindre l'IDE sur le port 9003.
- **[U14 — Gérer les dépendances Composer](./usages/u14.md)** : installer ou mettre à jour les
  dépendances dans le container sans écrire `vendor/` sur l'hôte.
- **[U15 — Exécuter les commandes d'un framework PHP](./usages/u15.md)** : illustrer Artisan et la
  console Symfony via une cible logique Yia.

### 4.3. Applications Node et Nuxt

- **[U16 — Exposer une application Nuxt avec Node 24 et pnpm](./usages/u16.md)** : fournir le
  script `dev`, le port privé, le hostname Apache et le HMR WebSocket ; voir
  [T02](./usages/t02.md) en cas de conflit sur le port HTTP.
- **[U17 — Utiliser Node 22](./usages/u17.md)** : montrer le même projet avec une version de runtime
  différente et explicite.
- **[U18 — Choisir npm, pnpm ou Yarn](./usages/u18.md)** : partir d'un exemple principal complet
  avec pnpm, puis présenter les seules variantes nécessaires pour npm et Yarn,
  notamment le gestionnaire déclaré, la commande et le lockfile.
- **[U19 — Exécuter un worker Node sans HTTP](./usages/u19.md)** : omettre `web` tout en conservant
  le script de développement et son healthcheck de processus.
- **[U20 — Héberger plusieurs applications Node sur la même version](./usages/u20.md)** : partager
  l'image tout en isolant processus et volumes `node_modules`.
- **[U21 — Utiliser Node 22 et Node 24 simultanément](./usages/u21.md)** : montrer deux applications
  avec leurs services et dépendances isolés.
- **[U22 — Exécuter une commande de paquet ponctuelle](./usages/u22.md)** : utiliser `make exec`
  pour les scripts npm, pnpm ou Yarn sans contourner Yia.

### 4.4. Architectures composées

- **[U23 — Associer une API PHP et un frontend Nuxt](./usages/u23.md)** : configurer deux
  hostnames, le proxy Apache et le cycle de développement complet.
- **[U24 — Construire un projet full stack avec PostgreSQL](./usages/u24.md)** : combiner
  PHP, Nuxt et la base persistante dans l'exemple de référence utilisé comme
  fil rouge dans l'ensemble du guide ; voir [T01](./usages/t01.md), [T02](./usages/t02.md) et
  [T05](./usages/t05.md).
- **[U25 — Construire un monorepo multi-applications](./usages/u25.md)** : combiner plusieurs
  applications PHP et Node, plusieurs versions de runtimes et des hostnames
  distincts.
- **[U26 — Utiliser des sous-domaines `.localhost`](./usages/u26.md)** : expliquer le routage local
  sans modification de `/etc/hosts` lorsque l'hôte le supporte ; voir
  [T02](./usages/t02.md).

### 4.5. PostgreSQL, variables et données

- **[U27 — Démarrer PostgreSQL seul](./usages/u27.md)** : configurer la version, les variables
  obligatoires de `.env` et vérifier le healthcheck ; voir [T01](./usages/t01.md).
- **[U28 — Partager PostgreSQL entre plusieurs applications](./usages/u28.md)** : utiliser le nom
  logique `postgres` sur le réseau privé sans publier le port.
- **[U29 — Exposer PostgreSQL à l'hôte](./usages/u29.md)** : utiliser `expose: true`, documenter le
  risque et vérifier la connexion locale.
- **[U30 — Préserver les données PostgreSQL](./usages/u30.md)** : démontrer leur survie à
  `down`, `restart`, `update`, `rebuild`, `reset` et `destroy`.
- **[U31 — Sauvegarder et restaurer PostgreSQL](./usages/u31.md)** : utiliser les outils de l'image
  PostgreSQL via l'API Make et conserver la sauvegarde dans un emplacement
  appartenant au projet.
- **[U32 — Gérer `.env` et `.env.example`](./usages/u32.md)** : distinguer valeurs documentées,
  valeurs locales et secrets, puis vérifier leur absence des sorties et
  artefacts générés.
- **[U33 — Supprimer volontairement les données](./usages/u33.md)** : prévisualiser les volumes
  ciblés et utiliser `make destroy-data` avec confirmation explicite.

### 4.6. Cycle de développement quotidien

- **[U34 — Faire converger le projet avec `make update`](./usages/u34.md)** : modifier `yia.yml`,
  appliquer l'état cible puis démontrer qu'un second passage est sans effet ;
  voir [T01](./usages/t01.md) et [T05](./usages/t05.md) en cas d'échec.
- **[U35 — Ajouter, retirer ou changer une application](./usages/u35.md)** : observer la
  régénération ciblée et la conservation des données et sources.
- **[U36 — Démarrer, arrêter et redémarrer](./usages/u36.md)** : comparer `up`, `down` et `restart`
  et expliciter leur impact nul sur les volumes persistants.
- **[U37 — Construire ou reconstruire les images](./usages/u37.md)** : choisir entre `build` et
  `rebuild` sans supprimer les données.
- **[U38 — Lire les logs](./usages/u38.md)** : utiliser les logs agrégés, cibler un service et
  activer volontairement le suivi avec `FOLLOW=1`.
- **[U39 — Ouvrir un shell ou exécuter une commande](./usages/u39.md)** : résoudre une application,
  un service ou un runtime avec `SERVICE` et passer une commande avec `CMD`.
- **[U40 — Observer l'environnement](./usages/u40.md)** : comparer `ps`, `status`, `doctor` et
  leurs sorties JSON lorsque disponibles ; voir [T01](./usages/t01.md) et [T05](./usages/t05.md).
- **[U41 — Tester un projet consommateur](./usages/u41.md)** : expliquer ce que `make test` valide
  et pourquoi il ne devine pas les tests métier du framework.
- **[U42 — Nettoyer et reconstruire le runtime généré](./usages/u42.md)** : utiliser `clean`,
  `generate` puis `update` sans toucher au code ni aux données ; voir
  [T05](./usages/t05.md).
- **[U43 — Réinitialiser sans perdre les données](./usages/u43.md)** : utiliser `reset`, contrôler
  les containers recréés et vérifier la persistance PostgreSQL.
- **[U44 — Détruire l'environnement sans détruire les données](./usages/u44.md)** : utiliser
  `destroy`, vérifier les ressources supprimées et les volumes conservés.

### 4.7. Automatisation et versions

- **[U45 — Automatiser les contrôles en CI locale](./usages/u45.md)** : exploiter `FORMAT=json`,
  stdout propre et les codes de sortie de `validate`, `doctor`, `status`, `ps`
  et `version`.
- **[U46 — Vérifier la version de l'environnement](./usages/u46.md)** : relever la version Yia,
  le commit du sous-module, les versions de schémas et celles des outils.

### 4.8. Documentation, agents et maintenance

- **[U47 — Initialiser la documentation projet](./usages/u47.md)** : découvrir `.agents/docs`,
  l'index, le glossaire, les décisions et les skills installés par Yia.
- **[U48 — Consulter la connaissance projet avec `project-docs`](./usages/u48.md)** : retrouver les
  informations pertinentes avant une tâche sans charger toute la documentation.
- **[U49 — Mettre à jour la connaissance avec `update-project-docs`](./usages/u49.md)** : ajouter
  une décision ou synchroniser une connaissance durable après une évolution.
- **[U50 — Préserver une documentation humaine](./usages/u50.md)** : montrer qu'`init` et `update`
  n'écrasent pas silencieusement un fichier possédé par le projet.
- **[U51 — Travailler avec Codex dans un projet Yia](./usages/u51.md)** : suivre `AGENTS.md`, lire
  les sources de vérité, modifier `yia.yml`, valider, converger et documenter.
- **[U52 — Mettre à jour le sous-module Yia](./usages/u52.md)** : changer explicitement le commit,
  examiner le diff, vérifier les versions puis exécuter le workflow de
  convergence.
- **[U53 — Traiter une migration requise](./usages/u53.md)** : comprendre
  `YIA_MIGRATION_REQUIRED`, préserver les fichiers et attendre ou appliquer une
  migration explicite documentée ; voir [T06](./usages/t06.md).
- **[U54 — Traiter un changement de nom de projet](./usages/u54.md)** : expliquer pourquoi il est
  bloqué comme migration et éviter d'abandonner silencieusement d'anciennes
  ressources Docker ; voir [T07](./usages/t07.md).

## 5. Troubleshooting

Cette section regroupe les parcours de dépannage. Chaque scénario doit partir
d'un symptôme observable, identifier les contrôles non destructifs, expliquer
le code d'erreur éventuel, puis proposer une correction et sa validation. Aucun
scénario ne doit arrêter ou supprimer silencieusement une ressource externe.

- **[T01 — Dépendance ou Docker indisponible, container dégradé](./usages/t01.md)** : interpréter
  `check-install`, `doctor`, les healthchecks et `YIA_DOCKER_UNAVAILABLE`, puis
  distinguer client absent, daemon inaccessible et service unhealthy.

- **[T02 — Port 80 ou hostname indisponible](./usages/t02.md)** : identifier le processus ou le
  container concurrent, vérifier la résolution `.localhost` et le routage
  Apache sans arrêter silencieusement une ressource externe.

- **[T03 — Configuration `yia.yml` invalide](./usages/t03.md)** : partir de
  `YIA_CONFIG_INVALID`, localiser le chemin fautif, corriger la propriété et
  revalider avant toute génération.

- **[T04 — Permissions UID/GID incorrectes](./usages/t04.md)** : vérifier et personnaliser
  `YIA_UID` et `YIA_GID`, puis confirmer que les sources n'ont pas changé de
  propriétaire.

- **[T05 — Runtime généré absent ou obsolète](./usages/t05.md)** : distinguer configuration,
  génération et containers, supprimer seulement les artefacts reconstructibles
  puis retrouver l'état déclaré.

- **[T06 — Migration de schéma requise](./usages/t06.md)** : interpréter
  `YIA_MIGRATION_REQUIRED`, conserver les fichiers versionnés et appliquer
  uniquement une procédure de migration explicite et inspectable.

- **[T07 — Changement de nom de projet bloqué](./usages/t07.md)** : retrouver les ressources sous
  l'ancienne identité Compose et préparer une migration sans abandonner ni
  supprimer implicitement les volumes persistants.

## 6. Cas à réserver pour une version future

Les sujets suivants ne doivent pas recevoir d'exemple opérationnel tant que les
spécifications et l'implémentation correspondantes n'existent pas :

- Redis, Mailpit, MinIO, RabbitMQ, OpenSearch ou un service arbitraire ;
- MySQL, MariaDB ou plusieurs instances PostgreSQL ;
- PHP ou Node générique sans framework reconnu ;
- versions PHP ou Node autres que celles supportées par le schéma V1 ;
- extensions PHP configurables depuis `yia.yml` ;
- plusieurs hostnames par application ;
- HTTPS local, port HTTP Apache configurable ou exposition directe des runtimes ;
- déploiement de production, orchestration multi-hôtes ou Kubernetes ;
- migration automatique et silencieuse de `yia.yml` ;
- installation automatique sur un système non APT.

## 7. Suivi de rédaction

La rédaction avance bloc par bloc, sans priorité globale. Un bloc est terminé
lorsque ses exemples respectent le format de la section 2, ont été exécutés sur
Yia 0.1.0 et renvoient vers les scénarios Troubleshooting pertinents.

Les variantes ne dupliquent pas un exemple complet : elles montrent uniquement
le diff de configuration, de fichiers ou de commandes par rapport à l'exemple
principal. Toute connaissance commune reste portée par le fil rouge U24.

Ordre de rédaction convenu :

1. [x] U24 ;
2. [x] U23, U25 et U26 — reste de la section 4.4 ;
3. [x] section 4.1 — installation et prise en main ;
4. [x] section 4.2 — applications PHP ;
5. [x] section 4.3 — applications Node et Nuxt ;
6. [x] section 4.5 — PostgreSQL, variables et données ;
7. [x] section 4.6 — cycle de développement quotidien ;
8. [x] section 4.7 — automatisation et versions ;
9. [x] section 4.8 — documentation, agents et maintenance ;
10. [x] section 5 — Troubleshooting.

Après chaque bloc, tous les cas déjà documentés sont revérifiés ensemble :
contrats utilisés, fichiers partagés, commandes, liens internes, sécurité des
données, absence de secret et cohérence avec le fil rouge.
