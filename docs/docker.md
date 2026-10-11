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

### Exception V2 : Traefik externe

Le bloc `traefik` conserve le réseau privé `yia` et déclare un second réseau
logique `traefik`, avec `external: true` et `name` égal au réseau physique
explicite. Seuls les services autorisés par `containers.<service>.expose: true`
y sont connectés. Tous portent `traefik.enable=true` ou `false` selon cette
autorisation ; les services exposés portent aussi `traefik.docker.network`.
Ces valeurs gérées ne peuvent pas être contredites par les labels explicites.
Les labels utilisateur sont limités à `traefik.*`, triés et conservés comme
chaînes littérales, conformément à `configuration.md`.

Apache reste le point d'entrée HTTP **interne** des applications. Traefik est
le point d'entrée externe ; Apache conserve son port interne 80, ses vhosts,
ses dépendances et son healthcheck mais ne publie plus `80:80`. PHP-FPM,
Node et Python ne rejoignent pas le réseau partagé. Les services d'infrastructure
peuvent y être connectés individuellement par autorisation explicite ; cela
ne publie aucun port hôte et ne désactive aucune authentification.

Yia ne crée ni conteneur Traefik, ni socket Docker, ni configuration statique
du proxy. Le réseau doit déjà exister. `down`, `reset`, `destroy` et
`destroy-data` ne le suppriment pas : Compose le considère externe.
Sans bloc `traefik`, la topologie et les labels existants restent inchangés.

### Réseau privé par défaut

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
`httpd:2.4.69-alpine3.24`. La topologie Compose utilise le contexte relatif
`../../.yia/docker/apache`, résolu depuis
`.yia-runtime/compose/compose.yaml` dans un projet consommateur.

### 4.2. Responsabilités

Apache :

- constitue le point d'entrée HTTP unique ;
- route les hostnames vers les applications ;
- relaie les applications PHP vers PHP-FPM ;
- agit comme reverse proxy vers les applications Node ;
- agit comme reverse proxy vers les API FastAPI ;
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

### 4.7. Applications Python

Pour une API FastAPI, Apache transmet `/` au service logique
`python-3.12-<application>` sur `web.port`. Le header `Host` est préservé.
Aucun port Python n'est publié sur l'hôte.

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
| PHP 8.5 | `php:8.5.11-fpm-alpine3.24` |

Chaque runtime possède son Dockerfile sous `docker/php/<version>/`. Le contexte
de build commun est `docker/php/`.

Les extensions installées sont fixes : `bcmath`, `intl`, `mbstring`,
`opcache`, `pcntl`, `posix`, `pdo_mysql`, `pdo_pgsql`, `xdebug` et `zip`. Elles ne sont
pas configurables dans `yia.yml`. Xdebug est installé avec le seul mode
`debug`, mais le démarrage d'une session est désactivé globalement.
Dans l'image PHP 8.5, OPcache est déjà compilé dans PHP ; le Dockerfile vérifie
sa présence sans tenter de le reconstruire comme extension partagée.

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

## 5 bis. Secrets et supervision PHP en V2

Les références `secret_files` sont des montages bind en lecture seule dans
`/run/yia-secrets/<consommateur>/<variable>`, sans création automatique du
fichier source. Aucun contenu n'est lu par le moteur ni inclus dans `Config.Env`.
Un manifeste généré `php/<version>/applications.json` contient uniquement les
références et les déclarations de processus, jamais les valeurs des fichiers.

Le bootstrap PHP prépare dans le master FPM des variables internes distinctes
par application ; chaque pool injecte uniquement les variables qui lui sont
déclarées, avec `clear_env=yes`. Les commandes Make ciblant une application
et ses scripts `initialization.once` passent par ce bootstrap. Une commande
`docker compose exec` brute ne bénéficie pas de cette injection.
Les valeurs restent en mémoire de processus ; Yia ne génère aucun cache Laravel.
L'application reste responsable de ne pas écrire ses secrets dans ses logs,
son code ou un cache de configuration persistant. Le conteneur et l'utilisateur
partagés ne constituent pas une frontière de sécurité entre applications.

Avec `processes`, le PID 1 supervise FPM et les commandes déclarées. FPM garde
son master root et ses workers `yia` ; les processus applicatifs s'exécutent
comme `yia`, sans installation Composer ni migration automatique. Les sources
et volumes vendor sont ceux du runtime partagé. Les ports des processus restent
privés et ne donnent lieu à aucun conteneur ou label Traefik supplémentaire.

Le superviseur récole les enfants et conserve en tmpfs `/run/yia-php` leur état
et code de sortie. Un enfant sorti n'est jamais relancé, même avec le code 0.
Les autres enfants restent actifs et le healthcheck retourne un échec. Sans
sonde spécifique, seuls les processus vivants sont contrôlés. Une sonde
explicite est exécutée dans le répertoire et l'environnement de l'application,
avec timeout et sorties supprimées. La première readiness exige une réussite ;
les échecs suivants suivent `retries`, après `start_period`, sans relance.

À l'arrêt, les groupes applicatifs reçoivent SIGTERM et leur délai déclaré,
puis SIGKILL si nécessaire. FPM reçoit SIGQUIT avec dix secondes de grâce.
Le délai Compose vaut le maximum de ces délais plus une seconde pour la récolte.
Les dépendances des processus sont agrégées sur le conteneur mutualisé.

Les routes PHP `web.proxy_routes` sont placées avant le fallback FastCGI.
Apache transmet le préfixe inchangé au port privé du processus déclaré,
préserve Host et indique `X-Forwarded-Proto: http`. Une route `websocket: true`
active `upgrade=websocket` de `mod_proxy_http` déjà installé. Ni `/apps/`, ni
autorisation d'origine, ni TLS ne sont ajoutés implicitement.

### Consommateurs PostgreSQL et Redis

En mode fichier, PostgreSQL reçoit uniquement `POSTGRES_PASSWORD_FILE` ; un
adaptateur vérifie le format avant l'entrypoint officiel. Celui-ci initialise
le mot de passe uniquement sur un volume neuf. Recharger le fichier ne modifie
donc pas le mot de passe d'un rôle existant.

Redis reçoit uniquement `REDIS_PASSWORD_FILE`. Le lancement produit son ACL
avec empreinte dans `/tmp`, monté en tmpfs, et retire le mot de passe de son
environnement avant de lancer Redis. Son healthcheck lit le fichier et transmet
le mot de passe via l'environnement éphémère du client, jamais par argument.
La persistance AOF/RDB dans `redis-data` demeure inchangée. Sans fichier déclaré,
les comportements précédents sont conservés.

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

## 6 bis. Python FastAPI

Une application FastAPI utilise un service Compose dédié nommé
`python-3.12-<application>`, construit depuis
`docker/python/3.12/Dockerfile` sur `python:3.12.12-slim-bookworm`.
La source est montée dans `/workspace/<application>`. Le volume nommé
`python-<application>-venv` est monté dans `.venv`, sans écrire de dépendances
sur l'hôte. L'entrypoint aligne l'utilisateur `yia` sur `YIA_UID` et
`YIA_GID` et ne change que le propriétaire de la racine du volume.

Au démarrage, `pip install -r requirements.txt` installe les dépendances
déclarées dans ce volume. Uvicorn lance `main:app` en mode développement,
écoute `0.0.0.0` sur `web.port` et recharge le code modifié. Le healthcheck
contrôle une connexion TCP locale au port déclaré. Le port reste privé ; Apache
est l'unique point d'entrée HTTP. Le service exige `main.py` et
`requirements.txt` dans la racine applicative. `PYTHONDONTWRITEBYTECODE=1`
empêche l'écriture de caches Python dans les sources montées.

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

En V2, `services.postgres.initialization.sql` monte un fichier SQL texte en
lecture seule avec un adaptateur Yia dans `/docker-entrypoint-initdb.d/`.
L'image l'exécute sur un volume neuf ; l'adaptateur écrit son empreinte dans
`PGDATA` uniquement après succès. Sur un volume existant, le SQL n'est pas
rejoué. Marqueur absent ou empreinte différente : `up`, `update` et `doctor`
signalent une erreur, sans recréer le volume. Les archives qui nécessitent
`pg_restore` ne sont pas prises en charge par ce champ.

Les scripts `initialization.once` sont exécutés dans leur conteneur après
les healthchecks ; leurs marqueurs de succès sont conservés dans
`.yia-data/once/`, hors des artefacts runtime générés.

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

## 7 bis. Redis (configuration V2)

Redis est un service optionnel unique nommé `redis`, utilisant l'image
officielle `redis:<version explicite>` (Redis 7 ou plus). Il partage le réseau
privé `yia` et écoute sur `redis:6379`. Aucun port hôte n'est publié par défaut ;
`services.redis.expose: true` publie `127.0.0.1:6379:6379`, sans sélection
automatique d'un autre port en cas de conflit.

Le volume nommé `redis-data` est monté dans `/data`. La persistance AOF est
activée avec `appendfsync everysec` et les snapshots RDB sont explicitement
configurés (`900 1 300 10 60 10000`). AOF peut perdre environ une seconde
d'écritures en cas de panne brutale. Les commandes `down`, `update`, `restart`,
`rebuild`, `reset`, `clean` et `destroy`, ainsi que le retrait du service de
`yia.yml`, conservent ce volume. Seul `destroy-data` peut le supprimer, avec la
confirmation déjà définie par l'API Make. Changer de version ne migre pas le
format des données ; le projet doit vérifier la compatibilité du tag choisi.

Le Compose ne contient que la référence `${REDIS_PASSWORD:?...}`. Un adaptateur
Yia en lecture seule prépare dans le conteneur une ACL temporaire, contenant
uniquement le SHA-256 du mot de passe pour l'utilisateur `default`. Le serveur
est ensuite lancé via l'entrypoint officiel en tant qu'utilisateur `redis`.
Le mot de passe n'est ni un argument du serveur, ni un fichier généré sur
l'hôte, ni une donnée du volume. Un changement de `REDIS_PASSWORD`, suivi de
`make update`, applique l'authentification au conteneur recréé sans effacer les
données. L'accès aux clés, commandes et canaux Pub/Sub est autorisé après
authentification.

Le healthcheck exige une réponse exacte `PONG` à un `PING` authentifié, avec
`REDISCLI_AUTH` plutôt qu'un mot de passe dans les arguments. Il suit les
intervalles et délais communs. `init`, `status`, `doctor`, `logs`, `shell` et
`exec` reconnaissent le service logique `redis` sans nouvelle cible Make.

## 7 ter. OpenBao (configuration V2)

Le service logique `openbao` utilise `openbao/openbao:<version explicite>`
(version majeure 2 ou plus), en mode serveur persistant. Il n'utilise jamais
`-dev`. Le générateur Compose produit également
`.yia-runtime/openbao/server.hcl`, marqué comme généré et monté en lecture
seule dans `/yia/openbao/server.hcl`.

Une instance Raft unique stocke ses données dans `/openbao/file`, monté depuis
le volume nommé `openbao-data`. Son identifiant stable est `openbao`.
L'adresse API est `http://openbao:8200`, l'adresse cluster est
`http://openbao:8201`. Seul le réseau privé `yia` est utilisé ; aucun port
8200 ou 8201 n'est publié, aucun vhost Apache n'est généré. Une autorisation
`traefik.containers.openbao.expose: true` ajoute le réseau partagé et les labels
explicites selon le contrat Traefik V2 ; sans elle, OpenBao reste privé.
HTTP sans TLS est
réservé à ce réseau de développement local. L'interface web est désactivée.
Avec Raft, `disable_mlock: true` évite d'exiger des capacités Docker
supplémentaires. L'entrypoint officiel prépare les permissions du volume et
exécute le serveur sous l'utilisateur `openbao`. `/openbao/logs` est un tmpfs
éphémère ; aucun audit sur fichier n'est configuré par cette intégration.

Le healthcheck effectue une requête locale à `/v1/sys/health` et exige son
succès HTTP normal ; un serveur non initialisé ou verrouillé est unhealthy.
Son intervalle est de 2 secondes, son timeout de 5 secondes, avec 3 tentatives
et un délai initial de 5 secondes. Les diagnostics lisent le JSON de `bao status`
en acceptant son code 2 pour un serveur verrouillé, puis confirment la
disponibilité HTTP d'un serveur déverrouillé. Ils ne parsèment jamais de texte
humain et ne restituent que des booléens et un état contrôlé.

Après déverrouillage, si l'API est prête mais Compose échoue encore, Yia attend
un intervalle de healthcheck et retente une seule fois l'opération. Un nouvel
échec Docker reste une erreur ; aucun état verrouillé n'est accepté.

Le premier `update` démarre le conteneur puis échoue si l'opérateur n'a pas
initialisé et déverrouillé OpenBao. Le conteneur reste démarré pour les
opérations manuelles via Make. Après chaque redémarrage ou recréation,
OpenBao peut nécessiter un nouveau déverrouillage : Yia ne stocke pas les
clés pour le contourner. Un second `update` sur une instance prête conserve
le conteneur et les artefacts inchangés.

`down`, `update`, `restart`, `rebuild`, `reset`, `clean`, `destroy` et le retrait
du service conservent `openbao-data`. Seul `destroy-data` peut le supprimer
avec confirmation. Changer de version ne constitue pas une migration
automatique ou une garantie de compatibilité du format persistant.

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

Les sources PHP, Node et Python sont des bind mounts absolus issus du modèle normalisé.
Les volumes de dépendances imbriqués empêchent leur écriture sur l'hôte.
Une application V2 `linked` peut résider hors de la racine du projet : son
chemin absolu résolu est alors monté tel quel. Yia ne déplace et ne clone pas
ce répertoire. Une application `managed` est montée depuis `apps/<dossier>`.

---

## 9. Ports

Seuls les ports nécessaires à l'accès depuis l'hôte sont publiés.

Par défaut :

- Apache publie `80:80` ;
- Node ne publie aucun port directement ;
- Python ne publie aucun port directement ;
- PHP-FPM ne publie aucun port directement ;
- PostgreSQL ne publie aucun port sauf `expose: true`.

---

## 10. Images Yia

Yia construit ses propres images pour :

- Apache ;
- PHP ;
- Node.
- Python.

PostgreSQL peut s'appuyer sur l'image officielle correspondant à la version demandée.

Les images Yia doivent être déterministes et versionnées par le repository Yia.

Les tags référencés par la topologie V1 sont :

```text
yia/apache:<version-yia>
yia/php:<version-php>-<version-yia>
yia/node:<version-node>-<version-yia>
yia/python:<version-python>-<version-yia>
```

Les runtimes Node, PHP et Python transmettent séparément `${YIA_UID:-1000}` et
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

Les chemins relatifs du document généré sont résolus depuis le répertoire de ce
premier fichier Compose. Les commandes Yia fixent explicitement le nom de
projet et le fichier `.env`, mais ne redéfinissent pas `--project-directory`
vers la racine du projet, afin que les contextes `../../.yia/docker/...`
restent valides dans un projet consommateur.

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
