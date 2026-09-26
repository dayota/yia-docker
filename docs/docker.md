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

La phase 5 fournit la topologie Compose et référence des tags d'images Yia
déterministes. La phase 6 fournit l'image et la configuration Apache. La phase
7 fournit les images et configurations PHP-FPM. La phase 8 fournit les images
et l'exécution de développement Node/Nuxt. La phase 9 intègre l'image officielle
PostgreSQL et sa persistance.

---

## 3. Réseau

Chaque projet possède un réseau Docker privé unique.

Tous les services du projet sont connectés à ce réseau lorsqu'ils doivent communiquer entre eux.

En V1, plusieurs réseaux applicatifs ne sont pas supportés.

Le réseau logique Compose s'appelle `yia`. En l'absence de nom physique forcé,
Docker Compose le crée sous la forme `<project>_yia`, où `<project>` est le
champ `name` du document Compose, lui-même égal à `project.name`.

---

## 4. Apache

### 4.1. Présence

Apache est créé lorsqu'au moins une application possède un bloc `web`.

Si aucune application n'est exposée en HTTP, Apache peut être absent.

Le service Compose logique s'appelle `apache`. Il utilise l'image
`yia/apache:<version-yia>` et publie `80:80` en V1. Il dépend avec la condition
`service_healthy` des runtimes portant les applications exposées.

L'image Yia Apache est construite depuis `docker/apache/` sur la base officielle
`httpd:2.4.68-alpine3.24`. La topologie Compose utilise le contexte relatif
`../../.yia/docker/apache`, résolu depuis
`.yia-runtime/compose/compose.yaml` dans un projet consommateur.

### 4.2. Responsabilités

Apache :

- constitue le point d'entrée HTTP unique ;
- route les hostnames vers les applications ;
- relaie les applications PHP vers PHP-FPM ;
- agit comme reverse proxy vers les applications Node ;
- n'utilise pas HTTPS en V1.

La V1 écoute exclusivement en HTTP sur le port interne et hôte `80`. Elle ne
génère ni certificat, ni redirection HTTPS, ni directive TLS. L'ajout de HTTPS
nécessitera un contrat versionné ultérieur.

### 4.3. Hostnames

Le suffixe `.localhost` est recommandé.

Yia ne doit pas gérer `/etc/hosts` par défaut en V1 lorsque les hostnames `.localhost` sont utilisés.

Les hostnames sont des noms DNS ASCII en minuscules. Chaque label commence et
se termine par une lettre minuscule ou un chiffre et peut contenir des tirets.
Un hostname ne peut ni contenir d'espace ou de caractère de contrôle, ni
dépasser 253 caractères.

### 4.4. Vhosts générés

Lorsque Apache est présent, Yia génère un fichier unique :

```text
.yia-runtime/apache/vhosts.conf
```

Il est monté en lecture seule dans
`/usr/local/apache2/conf/extra/yia-vhosts.conf`. Les vhosts sont ordonnés par
identifiant applicatif et contiennent un unique `ServerName` issu du bloc
`web`. Aucun wildcard ni alias implicite n'est généré.

L'image contient un vhost par défaut distinct, limité au endpoint
`/.yia-health`. Un hostname inconnu n'est donc jamais routé implicitement vers
la première application.

### 4.5. Applications PHP

Pour une application PHP exposée, Apache monte sa source en lecture seule au
même chemin `/workspace/<application>` que PHP-FPM. Le `DocumentRoot` est le
`public_directory` normalisé. Les fichiers `*.php` sont transmis avec
`SetHandler` au port du pool associé sur `php-<version>` ; les fichiers
statiques sont servis directement par Apache.

Les fichiers `.htaccess` sont autorisés dans le répertoire public afin de
prendre en charge les front controllers Laravel et Symfony. La connexion
FastCGI reste interne au réseau privé et n'est jamais publiée vers l'hôte.

### 4.6. Applications Node

Pour une application Node exposée, Apache transmet `/` au service logique
`node-<version>-<application>` sur le port déclaré dans `web.port` avec
`ProxyPass` et `ProxyPassReverse`. Le header `Host` d'origine est préservé.

Le paramètre `upgrade=websocket` de `mod_proxy_http` est activé afin de laisser
passer les connexions Upgrade/WebSocket, notamment celles utilisées par le
rechargement à chaud. Aucun port Node n'est publié sur l'hôte.

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

Le service Compose logique est `php-<version>`. Chaque source applicative est
montée dans `/workspace/<application>` et son volume de dépendances dans
`/workspace/<application>/vendor`.

Chaque application dispose de son propre pool FPM dans le container mutualisé.
Les pools sont triés par identifiant applicatif et écoutent, dans cet ordre,
sur les ports privés `9000`, `9001`, etc. Apache calcule le même port depuis le
modèle normalisé. Aucun port FPM n'est publié vers l'hôte.

### 5.2. Images

Yia construit ses propres images PHP. Les versions V1 supportées et leurs bases
officielles épinglées sont :

| Runtime | Image de base |
|---|---|
| PHP 8.2 | `php:8.2.33-fpm-alpine3.24` |
| PHP 8.4 | `php:8.4.25-fpm-alpine3.24` |

Chaque runtime possède son Dockerfile sous `docker/php/<version>/`. Le contexte
de build commun est `docker/php/`.

Les extensions installées sont fixes en V1 : `bcmath`, `intl`, `mbstring`,
`opcache`, `pcntl`, `pdo_mysql`, `pdo_pgsql`, `xdebug` et `zip`. Elles ne sont
pas configurables dans `yia.yml`. Xdebug est installé avec le seul mode
`debug`, mais le démarrage d'une session est désactivé globalement.

### 5.3. Composer

Composer `2.10.3` est copié depuis son image officielle dans toutes les images
PHP Yia. `git`, OpenSSH et `unzip` sont disponibles pour résoudre les
dépendances locales ou privées.

### 5.4. UID/GID

Le service PHP reçoit `${YIA_UID:-1000}` et `${YIA_GID:-1000}`. Son entrypoint,
initialement root, aligne l'utilisateur interne `yia` sur ces identifiants et
attribue uniquement les racines des volumes `vendor` à cet utilisateur. Il ne
modifie jamais les propriétaires des sources applicatives.

Le master FPM conserve les privilèges nécessaires au démarrage puis exécute les
workers des pools avec l'utilisateur `yia`. Les autres commandes du container
sont exécutées comme `yia` par l'entrypoint.

### 5.5. Dépendances Composer

Les répertoires `vendor/` sont stockés dans des volumes Docker nommés lorsque le mode de montage retenu par le runtime l'exige.

La topologie V1 utilise systématiquement un volume logique
`php-<application>-vendor` par application PHP.

La configuration générée est écrite dans
`.yia-runtime/php/<version>/fpm-pools.conf` puis montée en lecture seule dans
`/usr/local/etc/php-fpm.d/yia-pools.conf`. L'image contient un pool de repli
pour rester validable isolément ; le montage généré le remplace dans Compose.

### 5.6. Xdebug

Xdebug est configurable par application avec `runtime.xdebug`, désactivé par
défaut. Chaque pool fixe `xdebug.start_with_request` à `trigger` ou `no`, ce qui
permet des choix différents dans un même container PHP tout en respectant le
fait que `xdebug.mode` est choisi au démarrage du master FPM partagé.

Le démarrage du débogage utilise un trigger, cible
`host.docker.internal:9003` et ne découvre pas automatiquement une adresse
client depuis la requête HTTP. Compose ajoute l'alias `host-gateway` nécessaire
sur Linux.

---

## 6. Node

### 6.1. Mutualisation

Yia utilise un runtime/gestionnaire Node partagé par version Node.

Les applications utilisant la même version Node partagent le même runtime de base.

L'implémentation doit néanmoins préserver l'isolation de leurs processus et dépendances.

La topologie V1 crée donc un service Compose
`node-<version>-<application>` par application. Les services d'une même version
utilisent tous la même image `yia/node:<version-node>-<version-yia>`, mais leurs
processus et volumes restent distincts.

### 6.2. Images

Yia construit ses propres images Node depuis les bases officielles Debian
Bookworm suivantes :

| Runtime | Image de base |
|---|---|
| Node 22 | `node:22.23.3-bookworm` |
| Node 24 | `node:24.21.0-bookworm` |

Les versions supportées en V1 sont exclusivement `22` et `24`. Chaque
Dockerfile est stocké sous `docker/node/<version>/` et utilise le contexte de
build commun `docker/node/`.

### 6.3. Gestionnaire de paquets

Le gestionnaire par défaut est `pnpm`.

Une application peut sélectionner dans `yia.yml` :

- `pnpm`
- `npm`
- `yarn`

Les versions fournies par l'image V1 sont :

- npm : version incluse dans l'image Node officielle épinglée ;
- pnpm `11.27.1` ;
- Yarn Classic `1.22.22`.

Le lancement installe les dépendances avant le script de développement. Un
lockfile présent est traité en mode figé (`pnpm-lock.yaml`, `package-lock.json`,
`npm-shrinkwrap.json` ou `yarn.lock`). En son absence, l'installation désactive
la création d'un lockfile afin de ne pas modifier silencieusement les fichiers
humains du projet.

### 6.4. Dépendances Node

`node_modules` est stocké dans un volume Docker nommé par application afin d'éviter :

- les problèmes de permissions ;
- les incompatibilités hôte/container ;
- la pollution du filesystem hôte.

La source est montée dans `/workspace/<application>` et le volume logique
`node-<application>-modules` dans
`/workspace/<application>/node_modules`.

Le cache du gestionnaire reste interne au container. Il n'est ni déclaré comme
donnée persistante ni écrit dans la source applicative.

### 6.5. UID/GID

Chaque service reçoit `${YIA_UID:-1000}` et `${YIA_GID:-1000}`. Son entrypoint,
initialement root, aligne l'utilisateur interne `node` sur ces identifiants,
attribue uniquement la racine du volume `node_modules` à cet utilisateur puis
exécute toute commande applicative sans privilèges avec `gosu`. Il ne modifie
jamais les propriétaires des sources applicatives.

### 6.6. HTTP

Les applications Node exposent leur port uniquement sur le réseau Docker.

Apache assure l'exposition HTTP vers l'hôte.

### 6.7. Mode développement et HMR

Le processus par défaut exécute le script `dev` déclaré dans `package.json`
avec le gestionnaire configuré. Pour une application HTTP, Yia lui transmet
`--host 0.0.0.0` et `--port <web.port>`. Une application sans bloc `web`
exécute le même script sans arguments réseau.

Apache préserve le header `Host` et relaie les connexions Upgrade/WebSocket.
Le HMR Nuxt reste ainsi accessible via le hostname Yia sans publication directe
du port Node. Aucun mode polling n'est forcé par défaut.

Le healthcheck vérifie une connexion TCP locale sur `web.port` pour une
application HTTP. Pour une application sans exposition HTTP, il vérifie que le
processus principal du container existe encore.

---

## 7. PostgreSQL

### 7.1. Instance

Yia supporte un seul service PostgreSQL mutualisé par projet en V1.

### 7.2. Version

La version PostgreSQL est toujours explicite dans `yia.yml`.

Yia ne choisit aucune version par défaut et transmet le tag validé à l'image
officielle `postgres`. L'existence de ce tag est vérifiée par Docker lors de la
récupération de l'image.

### 7.3. Bases et utilisateurs

La V1 initialise une seule base et un seul superutilisateur via le mécanisme
standard de l'image officielle. Les valeurs viennent exclusivement du fichier
`.env` du projet :

| Variable | Contrat |
|---|---|
| `POSTGRES_PASSWORD` | obligatoire, non vide, sans valeur fournie ou générée par Yia |
| `POSTGRES_USER` | optionnelle, `postgres` par défaut |
| `POSTGRES_DB` | optionnelle, `postgres` par défaut |

Le Compose généré ne contient que les références à ces variables, jamais leur
valeur. Il n'active pas l'authentification `trust`. Les variables sont prises en
compte par l'image uniquement lors de l'initialisation d'un volume vide. Yia V1
ne crée pas de bases, rôles ou permissions supplémentaires et ne migre pas une
instance existante lorsqu'une de ces variables change.

Depuis les autres containers du projet, PostgreSQL est joignable sur
`postgres:5432`.

### 7.4. Exposition

Le port PostgreSQL n'est pas publié vers l'hôte par défaut.

Lorsque :

```yaml
expose: true
```

Yia peut publier PostgreSQL vers l'hôte.

Le service Compose logique s'appelle `postgres`. Lorsque l'exposition est
activée, le mapping V1 est `5432:5432` et l'instance devient joignable depuis
l'hôte sur `localhost:5432`. Yia ne choisit pas automatiquement un autre port
en cas de conflit.

### 7.5. Données

Les données PostgreSQL sont stockées dans un volume Docker nommé persistant.

Le volume logique V1 s'appelle `postgres-data`. Pour respecter le contrat de
l'image officielle, il est monté dans `/var/lib/postgresql/data` jusqu'à
PostgreSQL 17 inclus, puis dans `/var/lib/postgresql` à partir de PostgreSQL
18. La version majeure correspond aux chiffres placés au début du tag.

`make down`, `make update`, `make rebuild` ou `make restart` ne doivent jamais supprimer ce volume.

La suppression des données passe exclusivement par une commande destructive explicite définie dans `make-api.md`.

`make reset` conserve également ce volume. `make destroy` conserve les données
persistantes ; seule la future commande publique `make destroy-data`, appelée
explicitement et avec confirmation selon `make-api.md`, peut supprimer le
volume PostgreSQL.

Cette différence de chemin de montage entre les versions 17 et 18 suit le
[contrat de l'image officielle PostgreSQL](https://hub.docker.com/_/postgres).

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

Les noms logiques sont définis dans les sections précédentes. Docker Compose
préfixe leurs noms physiques avec le project name, par exemple
`<project>_postgres-data`.

Yia ne fixe pas `container_name`.

Les sources PHP et Node sont des bind mounts absolus issus du modèle normalisé.
Les volumes de dépendances imbriqués empêchent leur écriture sur l'hôte.

---

## 9. Ports

Seuls les ports nécessaires à l'accès depuis l'hôte sont publiés.

Par défaut :

- Apache publie `80:80` ;
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

Les tags référencés par la topologie V1 sont :

```text
yia/apache:<version-yia>
yia/php:<version-php>-<version-yia>
yia/node:<version-node>-<version-yia>
```

Les runtimes Node et PHP transmettent séparément `${YIA_UID:-1000}` et
`${YIA_GID:-1000}` à leurs entrypoints afin de préparer leurs volumes avant de
démarrer leurs processus non-root. Ces références sont générées telles quelles
et ne recopient aucune valeur locale dans `.yia-runtime/`.

L'image Apache active uniquement les modules supplémentaires nécessaires en
V1 : `headers`, `proxy`, `proxy_fcgi`, `proxy_http` et `rewrite`. Le forward
proxy reste désactivé avec `ProxyRequests Off`.

---

## 11. Génération Compose

Le fichier Compose est généré dans :

```text
.yia-runtime/compose/compose.yaml
```

Il est dérivé du modèle normalisé de `yia.yml`.

Il doit :

- être déterministe ;
- être reconstructible ;
- ne pas contenir de secret ;
- utiliser les volumes nommés ;
- utiliser le réseau privé du projet ;
- ne pas fixer `container_name`.

Le document contient le project name Compose, une section `services`, le
réseau logique unique `yia` et uniquement les volumes nommés effectivement
utilisés. Les services et ressources sont triés par nom logique.

---

## 12. Build et rebuild

`build` construit les images nécessaires.

`rebuild` reconstruit les images sans détruire les données persistantes.

Les changements de Dockerfile ou de runtime doivent être détectables par `make update`.

En V1, `make update` reconstruit avec le cache puis applique la topologie via
Compose. Compose recrée les services dont l'image ou la configuration a changé
et attend leur état running ou healthy. Les changements des fichiers générés
montés en bind entraînent en complément une recréation ciblée d'Apache ou du
runtime PHP concerné, sans propager cette recréation à ses dépendances.

Cette convergence ne renouvelle pas les volumes et ne supprime jamais les
volumes nommés, `.yia-data/` ou `.env`. Le changement du nom de projet Compose
nécessite une migration explicite.

---

## 13. Healthchecks

Les services structurants doivent disposer de healthchecks lorsque cela est techniquement pertinent.

Au minimum :

- PostgreSQL ;
- Apache ;
- runtimes applicatifs lorsque cela permet de vérifier leur disponibilité réelle.

Le détail doit être défini par l'implémentation sans masquer les échecs.

La topologie V1 configure :

- Apache avec une requête HTTP locale vers `/.yia-health` ;
- PHP avec `php-fpm -t` ;
- Node avec une connexion TCP vers l'application HTTP ou un contrôle du
  processus principal pour une application sans port ;
- PostgreSQL avec `pg_isready` et les variables standard de l'image, sans
  inscrire leur valeur dans le fichier généré. L'expansion des variables est
  effectuée dans le container afin que le healthcheck utilise exactement la
  base et l'utilisateur transmis au serveur.

Chaque healthcheck utilise un intervalle de 10 secondes, un timeout de 5
secondes, 5 tentatives et une période initiale de 5 secondes.

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
- Node partage l'image de runtime par version tout en isolant chaque service
  applicatif ;
- les dépendances utilisent des volumes nommés ;
- UID/GID hôte sont pris en compte ;
- Xdebug est configurable par application ;
- PostgreSQL est unique et mutualisé ;
- PostgreSQL n'est pas exposé par défaut ;
- aucune donnée persistante n'est supprimée implicitement ;
- aucun `container_name` n'est fixé ;
- HTTP uniquement est utilisé en V1 ;
- l'image Apache et sa configuration passent `httpd -t` ;
- les hostnames PHP atteignent PHP-FPM via FastCGI ;
- chaque configuration PHP générée passe `php-fpm -t` ;
- Composer et les extensions PHP documentées sont disponibles ;
- deux applications d'un même runtime peuvent choisir Xdebug indépendamment ;
- npm, pnpm et Yarn sont disponibles dans les versions documentées ;
- les dépendances Node sont installées sans modification silencieuse des
  lockfiles ;
- les processus Node utilisent l'UID/GID hôte sans réattribuer les sources ;
- les hostnames Node atteignent leur service via HTTP et supportent Upgrade.
