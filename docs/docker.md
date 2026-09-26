# Yia — Spécification Docker et runtimes

> **Statut :** normative  
> **Document parent :** [`yia-spec.md`](./yia-spec.md)  
> **Identifiant :** `YIA-SPEC-DOCKER`  
> **Version :** 1

## 1. Objet

Cette sous-spécification définit le modèle d'exécution Docker de Yia V1.

---

## 2. Principes globaux

- Yia construit ses propres images Docker.
- Docker Compose orchestre les services.
- Docker Compose génère les noms de containers à partir du nom de projet.
- Un seul réseau Docker privé est créé par projet en V1.
- HTTP uniquement en V1.
- Apache est le point d'entrée HTTP lorsqu'au moins une application HTTP est déclarée.
- Apache n'est pas obligatoire lorsqu'aucune application n'est exposée en HTTP.
- Les volumes de dépendances sont des volumes Docker nommés.
- Les UID/GID de l'utilisateur hôte sont propagés aux runtimes pour éviter les problèmes de permissions.
- Les données persistantes ne sont jamais supprimées implicitement.

---

## 3. Réseau

Chaque projet possède un réseau Docker privé unique.

Tous les services du projet sont connectés à ce réseau lorsqu'ils doivent communiquer entre eux.

En V1, plusieurs réseaux applicatifs ne sont pas supportés.

Le nom du réseau est dérivé du project name Docker Compose.

---

## 4. Apache

### 4.1. Présence

Apache est créé lorsqu'au moins une application possède un bloc `web`.

Si aucune application n'est exposée en HTTP, Apache peut être absent.

### 4.2. Responsabilités

Apache :

- constitue le point d'entrée HTTP unique ;
- route les hostnames vers les applications ;
- relaie les applications PHP vers PHP-FPM ;
- agit comme reverse proxy vers les applications Node ;
- n'utilise pas HTTPS en V1.

### 4.3. Hostnames

Le suffixe `.localhost` est recommandé.

Yia ne doit pas gérer `/etc/hosts` par défaut en V1 lorsque les hostnames `.localhost` sont utilisés.

---

## 5. PHP-FPM

### 5.1. Mutualisation

Yia crée un container PHP-FPM par version PHP utilisée.

Exemple :

```text
php-8.2
  ├── legacy
  └── backoffice

php-8.4
  ├── api
  └── worker
```

Deux applications utilisant PHP 8.4 partagent donc le même runtime PHP-FPM 8.4.

### 5.2. Images

Yia construit ses propres images PHP.

Chaque runtime versionné possède son Dockerfile.

Les extensions PHP nécessaires sont définies dans ce Dockerfile et non dans `yia.yml`.

### 5.3. Composer

Composer est installé dans les images PHP Yia.

### 5.4. UID/GID

Les images et containers PHP doivent fonctionner avec les UID/GID correspondant à l'utilisateur hôte lorsque cela est nécessaire à l'écriture dans les sources montées.

### 5.5. Dépendances Composer

Les répertoires `vendor/` sont stockés dans des volumes Docker nommés lorsque le mode de montage retenu par le runtime l'exige.

Le contrat final de nommage des volumes doit rester déterministe.

### 5.6. Xdebug

Xdebug est configurable par application.

Le mécanisme d'activation doit permettre à plusieurs applications partageant le même runtime PHP de déclarer des besoins différents.

L'implémentation doit donc éviter de considérer Xdebug comme une simple propriété globale du container partagé.

La solution technique précise peut être définie pendant l'implémentation, mais doit respecter ce contrat fonctionnel.

---

## 6. Node

### 6.1. Mutualisation

Yia utilise un runtime/gestionnaire Node partagé par version Node.

Les applications utilisant la même version Node partagent le même runtime de base.

L'implémentation doit néanmoins préserver l'isolation de leurs processus et dépendances.

### 6.2. Images

Yia construit ses propres images Node.

### 6.3. Gestionnaire de paquets

Le gestionnaire par défaut est `pnpm`.

Une application peut sélectionner dans `yia.yml` :

- `pnpm`
- `npm`
- `yarn`

### 6.4. Dépendances Node

`node_modules` est stocké dans un volume Docker nommé par application afin d'éviter :

- les problèmes de permissions ;
- les incompatibilités hôte/container ;
- la pollution du filesystem hôte.

### 6.5. UID/GID

Les processus Node doivent utiliser l'UID/GID de l'utilisateur hôte lorsque cela est nécessaire pour manipuler les sources montées.

### 6.6. HTTP

Les applications Node exposent leur port uniquement sur le réseau Docker.

Apache assure l'exposition HTTP vers l'hôte.

---

## 7. PostgreSQL

### 7.1. Instance

Yia supporte un seul service PostgreSQL mutualisé par projet en V1.

### 7.2. Version

La version PostgreSQL est toujours explicite dans `yia.yml`.

### 7.3. Exposition

Le port PostgreSQL n'est pas publié vers l'hôte par défaut.

Lorsque :

```yaml
expose: true
```

Yia peut publier PostgreSQL vers l'hôte.

### 7.4. Données

Les données PostgreSQL sont stockées dans un volume Docker nommé persistant.

`make down`, `make update`, `make rebuild` ou `make restart` ne doivent jamais supprimer ce volume.

La suppression des données passe exclusivement par une commande destructive explicite définie dans `make-api.md`.

---

## 8. Volumes

### 8.1. Volumes persistants

Exemples :

- données PostgreSQL.

Ils survivent aux commandes normales de cycle de vie.

### 8.2. Volumes de dépendances

Exemples :

- `vendor/` ;
- `node_modules/`.

Ils sont gérés par Yia afin de préserver les performances et les permissions.

### 8.3. Nommage

Les noms sont dérivés du project name Docker Compose et des identifiants de runtime/application.

Yia ne fixe pas `container_name`.

---

## 9. Ports

Seuls les ports nécessaires à l'accès depuis l'hôte sont publiés.

Par défaut :

- Apache publie le port HTTP requis ;
- Node ne publie aucun port directement ;
- PHP-FPM ne publie aucun port directement ;
- PostgreSQL ne publie aucun port sauf `expose: true`.

---

## 10. Images Yia

Yia construit ses propres images pour :

- Apache ;
- PHP ;
- Node.

PostgreSQL peut s'appuyer sur l'image officielle correspondant à la version demandée.

Les images Yia doivent être déterministes et versionnées par le repository Yia.

---

## 11. Génération Compose

Le fichier Compose est généré dans `.yia-runtime/`.

Il est dérivé du modèle normalisé de `yia.yml`.

Il doit :

- être déterministe ;
- être reconstructible ;
- ne pas contenir de secret ;
- utiliser les volumes nommés ;
- utiliser le réseau privé du projet ;
- ne pas fixer `container_name`.

---

## 12. Build et rebuild

`build` construit les images nécessaires.

`rebuild` reconstruit les images sans détruire les données persistantes.

Les changements de Dockerfile ou de runtime doivent être détectables par `make update`.

---

## 13. Healthchecks

Les services structurants doivent disposer de healthchecks lorsque cela est techniquement pertinent.

Au minimum :

- PostgreSQL ;
- Apache ;
- runtimes applicatifs lorsque cela permet de vérifier leur disponibilité réelle.

Le détail doit être défini par l'implémentation sans masquer les échecs.

---

## 14. Sécurité des données

Aucune commande non explicitement destructive ne peut supprimer :

- volume PostgreSQL ;
- donnée persistante ;
- fichier applicatif ;
- `.env`.

---

## 15. Definition of Done

Le modèle Docker V1 est respecté lorsque :

- un seul réseau privé existe par projet ;
- Apache n'existe que lorsqu'une exposition HTTP est nécessaire ;
- PHP est mutualisé par version ;
- Node utilise un runtime partagé par version ;
- les dépendances utilisent des volumes nommés ;
- UID/GID hôte sont pris en compte ;
- Xdebug est configurable par application ;
- PostgreSQL est unique et mutualisé ;
- PostgreSQL n'est pas exposé par défaut ;
- aucune donnée persistante n'est supprimée implicitement ;
- aucun `container_name` n'est fixé ;
- HTTP uniquement est utilisé en V1.
