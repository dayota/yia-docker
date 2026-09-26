# Cas d’usage Yia

> **Nature :** guide pratique non normatif
> **Version Yia ciblée :** 0.1.0

Chaque cas est autonome et renvoie vers les variantes ou scénarios de dépannage
pertinents. Le format, la ligne éditoriale et le suivi sont définis dans
[la gestion du guide](../usages-management.md).

## Installation et prise en main

- [U01 — Vérifier les prérequis](./u01.md)
- [U02 — Installer les prérequis sur un système APT](./u02.md)
- [U03 — Ajouter Yia à un nouveau dépôt](./u03.md)
- [U04 — Initialiser un projet consommateur](./u04.md)
- [U05 — Adopter Yia dans un dépôt existant](./u05.md)
- [U06 — Créer un projet minimal sans application ni service](./u06.md)
- [U07 — Valider et inspecter la configuration](./u07.md)

## Applications PHP

- [U08 — Exposer une API Laravel en PHP 8.4](./u08.md)
- [U09 — Exposer une application Symfony en PHP 8.2](./u09.md)
- [U10 — Exécuter un worker ou une commande PHP sans HTTP](./u10.md)
- [U11 — Héberger plusieurs applications sur le même PHP](./u11.md)
- [U12 — Utiliser PHP 8.2 et PHP 8.4 simultanément](./u12.md)
- [U13 — Activer Xdebug pour une seule application](./u13.md)
- [U14 — Gérer les dépendances Composer](./u14.md)
- [U15 — Exécuter les commandes d'un framework PHP](./u15.md)

## Applications Node et Nuxt

- [U16 — Exposer une application Nuxt avec Node 24 et pnpm](./u16.md)
- [U17 — Utiliser Node 22](./u17.md)
- [U18 — Choisir npm, pnpm ou Yarn](./u18.md)
- [U19 — Exécuter un worker Node sans HTTP](./u19.md)
- [U20 — Héberger plusieurs applications Node sur la même version](./u20.md)
- [U21 — Utiliser Node 22 et Node 24 simultanément](./u21.md)
- [U22 — Exécuter une commande de paquet ponctuelle](./u22.md)

## Architectures composées

- [U23 — Associer une API PHP et un frontend Nuxt](./u23.md)
- [U24 — Construire un projet full stack avec PostgreSQL](./u24.md)
- [U25 — Construire un monorepo multi-applications](./u25.md)
- [U26 — Utiliser des sous-domaines `.localhost`](./u26.md)

## PostgreSQL, variables et données

- [U27 — Démarrer PostgreSQL seul](./u27.md)
- [U28 — Partager PostgreSQL entre plusieurs applications](./u28.md)
- [U29 — Exposer PostgreSQL à l'hôte](./u29.md)
- [U30 — Préserver les données PostgreSQL](./u30.md)
- [U31 — Sauvegarder et restaurer PostgreSQL](./u31.md)
- [U32 — Gérer `.env` et `.env.example`](./u32.md)
- [U33 — Supprimer volontairement les données](./u33.md)

## Cycle de développement quotidien

- [U34 — Faire converger le projet avec `make update`](./u34.md)
- [U35 — Ajouter, retirer ou changer une application](./u35.md)
- [U36 — Démarrer, arrêter et redémarrer](./u36.md)
- [U37 — Construire ou reconstruire les images](./u37.md)
- [U38 — Lire les logs](./u38.md)
- [U39 — Ouvrir un shell ou exécuter une commande](./u39.md)
- [U40 — Observer l'environnement](./u40.md)
- [U41 — Tester un projet consommateur](./u41.md)
- [U42 — Nettoyer et reconstruire le runtime généré](./u42.md)
- [U43 — Réinitialiser sans perdre les données](./u43.md)
- [U44 — Détruire l'environnement sans détruire les données](./u44.md)

## Automatisation et versions

- [U45 — Automatiser les contrôles en CI locale](./u45.md)
- [U46 — Vérifier la version de l'environnement](./u46.md)

## Documentation, agents et maintenance

- [U47 — Initialiser la documentation projet](./u47.md)
- [U48 — Consulter la connaissance projet avec `project-docs`](./u48.md)
- [U49 — Mettre à jour la connaissance avec `update-project-docs`](./u49.md)
- [U50 — Préserver une documentation humaine](./u50.md)
- [U51 — Travailler avec Codex dans un projet Yia](./u51.md)
- [U52 — Mettre à jour le sous-module Yia](./u52.md)
- [U53 — Traiter une migration requise](./u53.md)
- [U54 — Traiter un changement de nom de projet](./u54.md)

## Troubleshooting

- [T01 — Dépendance, Docker ou service indisponible](./t01.md)
- [T02 — Port 80 ou hostname indisponible](./t02.md)
- [T03 — Configuration `yia.yml` invalide](./t03.md)
- [T04 — Permissions UID/GID incorrectes](./t04.md)
- [T05 — Runtime généré absent ou obsolète](./t05.md)
- [T06 — Migration de schéma requise](./t06.md)
- [T07 — Changement de nom de projet bloqué](./t07.md)
