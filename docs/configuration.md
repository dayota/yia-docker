# Yia — Spécification de configuration

> **Statut :** normative  
> **Document parent :** [`yia-spec.md`](./yia-spec.md)  
> **Identifiant :** `YIA-SPEC-CONFIG`  
> **Version du schéma :** 1

## 1. Objet

Cette sous-spécification définit le contrat normatif du fichier `yia.yml`.

`yia.yml` est la source de vérité déclarative de l'environnement de développement d'un projet consommateur de Yia.

Toute configuration non conforme au schéma actif doit être rejetée immédiatement.

---

## 2. Principes

- La configuration est déclarative.
- La validation est stricte.
- Le schéma est versionné.
- Les propriétés inconnues sont interdites.
- Les versions PHP, Node et PostgreSQL sont toujours explicites.
- `environment.domain` est obligatoire.
- Les variables d'environnement applicatives sont gérées exclusivement via `.env`.
- Les extensions PHP ne sont pas configurées dans `yia.yml`.
- Les extensions PHP sont définies dans le Dockerfile du runtime correspondant.
- En V1, un seul service PostgreSQL mutualisé est autorisé par projet.
- En V1, PostgreSQL est le seul service d'infrastructure supporté.
- Les frameworks supportés sont explicitement connus de Yia.

---

## 3. Version du schéma

La propriété racine suivante est obligatoire :

```yaml
version: 1
```

Cette version représente le format de `yia.yml`, pas la version de Yia.

Une version inconnue doit provoquer une erreur de configuration.

Yia ne doit jamais interpréter silencieusement une configuration provenant d'une version de schéma différente.

---

## 4. Structure racine

La structure racine V1 est :

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

applications: {}
```

Les propriétés racines autorisées sont exclusivement :

- `version`
- `project`
- `environment`
- `services`
- `applications`

Toute autre propriété doit être rejetée.

---

## 5. `project`

### 5.1. `project.name`

Obligatoire.

```yaml
project:
  name: my-project
```

Le nom :

- identifie le projet Yia ;
- participe au project name Docker Compose ;
- doit être compatible avec les conventions de nommage Docker ;
- doit être stable pour un projet donné.

Format V1 :

```text
^[a-z0-9][a-z0-9-]*$
```

---

## 6. `environment`

### 6.1. `environment.domain`

Obligatoire.

```yaml
environment:
  domain: my-project.localhost
```

Yia ne génère pas automatiquement cette valeur.

Le suffixe `.localhost` est recommandé en V1.

Yia doit supporter l'utilisation de `*.localhost` sans exiger de modification de `/etc/hosts` lorsque l'environnement hôte le permet.

Le domaine utilise des labels DNS ASCII en minuscules, séparés par des points.
Chaque label commence et se termine par une lettre ou un chiffre et peut
contenir des tirets. La longueur maximale est de 253 caractères.

---

## 7. `services`

En V1, seul PostgreSQL est supporté.

### 7.1. PostgreSQL

Exemple :

```yaml
services:
  postgres:
    enabled: true
    version: "18"
    expose: false
```

Propriétés :

- `enabled` : booléen ;
- `version` : chaîne obligatoire lorsque PostgreSQL est activé ;
- `expose` : booléen optionnel, `false` par défaut.

Contraintes :

- un seul service PostgreSQL par projet ;
- PostgreSQL est mutualisé entre les applications du projet ;
- la version doit toujours être explicite ;
- la version commence par un chiffre et ne contient que des caractères
  compatibles avec un tag Docker (`0-9`, `A-Z`, `a-z`, `.`, `_`, `-`) ;
- le port PostgreSQL n'est pas exposé vers l'hôte par défaut ;
- `expose: true` autorise son exposition selon le contrat Docker.

---

## 8. `applications`

`applications` est un objet dont chaque clé représente un identifiant applicatif unique.

Exemple :

```yaml
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
```

Les identifiants doivent respecter :

```text
^[a-z0-9][a-z0-9-]*$
```

---

## 9. Types d'application

Les types V1 sont :

```text
php
node
```

Une application peut être exposée en HTTP ou fonctionner sans exposition HTTP.

Le bloc `web` est donc optionnel.

Cas valides sans `web` :

- worker Laravel ;
- worker Symfony ;
- worker Node ;
- traitement asynchrone ;
- application interne sans point d'entrée HTTP.

---

## 10. Applications PHP

Exemple :

```yaml
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
```

### 10.1. Runtime

La version PHP est obligatoire :

```yaml
runtime:
  php: "8.4"
```

Yia ne fournit pas de version PHP par défaut.

Les versions supportées en V1 sont :

```text
8.2
8.4
```

La valeur doit correspondre exactement à l'une de ces versions mineures.

Xdebug est désactivé par défaut et peut être activé pour une application sans
l'activer pour les autres applications du même runtime :

```yaml
runtime:
  php: "8.4"
  xdebug: true
```

`xdebug` est un booléen réservé aux applications PHP. Sa valeur effective par
défaut est `false`.

### 10.2. Frameworks PHP

En V1, les frameworks PHP reconnus sont :

```text
laravel
symfony
```

Une valeur différente doit être rejetée.

### 10.3. Extensions PHP

Les extensions PHP ne sont pas configurées dans `yia.yml`.

Elles appartiennent à la définition du runtime Yia et sont configurées dans son Dockerfile.

### 10.4. Exposition web

Une application PHP peut omettre `web`.

Lorsqu'il est présent :

```yaml
web:
  hostname: api.my-project.localhost
  public_directory: public
```

`hostname` est unique pour l'application en V1.

Une application ne peut pas déclarer plusieurs hostnames.

Le hostname respecte le même format DNS que `environment.domain`.

Le répertoire public doit exister et rester contenu dans le chemin de
l'application.

---

## 11. Applications Node

Exemple :

```yaml
applications:
  frontend:
    type: node
    path: apps/frontend
    runtime:
      node: "24"
      package_manager: pnpm
    framework:
      name: nuxt
      version: 4
    web:
      hostname: my-project.localhost
      port: 3000
```

### 11.1. Runtime

La version Node est obligatoire :

```yaml
runtime:
  node: "24"
```

Yia ne fournit pas de version Node par défaut.

Les versions supportées en V1 sont :

```text
22
24
```

La valeur doit correspondre exactement à l'une de ces versions majeures.

### 11.2. Gestionnaire de paquets

Le gestionnaire par défaut est :

```text
pnpm
```

Il peut être surchargé explicitement dans `yia.yml` :

```yaml
runtime:
  node: "24"
  package_manager: npm
```

Valeurs V1 autorisées :

```text
pnpm
npm
yarn
```

Le gestionnaire sélectionné doit correspondre aux fichiers de verrouillage du
projet. En mode développement, Yia installe les dépendances sans créer de
fichier de verrouillage lorsqu'il n'en existe pas et exige que le fichier
existant reste inchangé lorsqu'il est présent.

### 11.3. Frameworks Node

En V1, le framework Node reconnu est :

```text
nuxt
```

Une valeur différente doit être rejetée.

### 11.4. Exposition web

Une application Node peut omettre `web`.

Lorsqu'il est présent :

```yaml
web:
  hostname: my-project.localhost
  port: 3000
```

Un seul hostname est supporté par application en V1.

Le hostname respecte le même format DNS que `environment.domain`.

Une application Node doit fournir un script `dev` dans son `package.json`.
Lorsqu'un bloc `web` est présent, Yia transmet au script l'adresse d'écoute
`0.0.0.0` et le port déclaré afin que l'application soit joignable depuis le
réseau Docker privé.

---

## 12. Variables d'environnement

Les variables d'environnement applicatives sont gérées exclusivement via `.env`.

`yia.yml` ne doit pas contenir :

- mots de passe ;
- tokens ;
- clés privées ;
- secrets ;
- valeurs applicatives d'environnement.

Yia peut documenter qu'une variable est requise, mais ne doit pas intégrer sa valeur à la configuration déclarative.

Lorsque PostgreSQL est activé, les variables suivantes sont lues depuis
`.env` par l'orchestration Docker :

- `POSTGRES_PASSWORD` : obligatoire et non vide ;
- `POSTGRES_USER` : optionnelle, `postgres` par défaut ;
- `POSTGRES_DB` : optionnelle, `postgres` par défaut.

Ces valeurs ne font pas partie du modèle normalisé et ne sont jamais copiées
dans les artefacts générés. Le fichier Compose contient uniquement des
références d'interpolation. `POSTGRES_USER`, `POSTGRES_DB` et
`POSTGRES_PASSWORD` initialisent exclusivement un volume vide ; les modifier
ne migre ni un rôle, ni une base, ni un mot de passe déjà persisté.

---

## 13. Validation stricte

Le schéma V1 applique :

```text
additionalProperties: false
```

à chaque niveau contractuel lorsque la structure est connue.

Une propriété inconnue doit produire `YIA_CONFIG_INVALID`.

Yia ne doit pas ignorer silencieusement une propriété inconnue afin de préserver la détection des fautes de frappe et la stabilité du contrat.

---

## 14. Normalisation

Après validation, Yia produit un modèle interne normalisé.

La normalisation peut :

- appliquer `expose: false` lorsque la valeur est absente ;
- appliquer `package_manager: pnpm` pour Node lorsque la valeur est absente ;
- normaliser les chemins ;
- ordonner les structures internes de manière déterministe.

En V1, le modèle normalisé applique les règles suivantes :

- la racine projet et les chemins applicatifs sont résolus en chemins absolus ;
- le répertoire public PHP est résolu depuis le chemin de son application et
  ne peut pas en sortir ;
- les applications sont ordonnées par identifiant ;
- une version de framework entière ou textuelle est représentée par une chaîne ;
- un bloc PostgreSQL sans `enabled` vaut `enabled: true` ;
- un PostgreSQL absent ou désactivé est absent du modèle effectif ;
- `postgres.expose` absent vaut `false` ;
- `runtime.package_manager` absent pour Node vaut `pnpm` ;
- `runtime.xdebug` absent pour PHP vaut `false` ;
- le project name Compose est égal à `project.name` ;
- les noms logiques de runtime sont `php-<version>` et `node-<version>` ;
- le nom logique du service PostgreSQL est `postgres`.

Le modèle est immuable et indépendant de Docker. Sa représentation canonique
est un JSON UTF-8 compact dont les clés sont triées. Le hash de configuration
est le SHA-256 hexadécimal de cette représentation. Les chemins absolus résolus
font partie de la représentation : déplacer un projet change donc son hash,
car ses futurs bind mounts changent également.

La normalisation ne doit jamais :

- inventer une version PHP ;
- inventer une version Node ;
- inventer une version PostgreSQL ;
- inventer `environment.domain`.

---

## 15. Migration

Toute évolution incompatible du format `yia.yml` nécessite :

1. une nouvelle version de schéma ;
2. un schéma dédié ;
3. une migration explicite ;
4. une documentation de migration.

Yia ne doit jamais migrer silencieusement une configuration incompatible.

---

## 16. Erreurs

Une erreur de configuration utilise :

```text
YIA_CONFIG_INVALID
```

avec code de sortie :

```text
2
```

La sortie structurée doit identifier autant que possible :

- le chemin fautif ;
- le message ;
- la version de schéma attendue.

---

## 17. Exemples minimaux

### 17.1. Projet sans application

```yaml
version: 1

project:
  name: minimal

environment:
  domain: minimal.localhost

applications: {}
```

### 17.2. PHP sans exposition HTTP

```yaml
version: 1

project:
  name: worker

environment:
  domain: worker.localhost

applications:
  worker:
    type: php
    path: apps/worker
    runtime:
      php: "8.4"
    framework:
      name: laravel
      version: 13
```

### 17.3. Node avec gestionnaire explicite

```yaml
version: 1

project:
  name: frontend

environment:
  domain: frontend.localhost

applications:
  frontend:
    type: node
    path: apps/frontend
    runtime:
      node: "24"
      package_manager: npm
    framework:
      name: nuxt
      version: 4
    web:
      hostname: frontend.localhost
      port: 3000
```

---

## 18. Definition of Done

Le contrat configuration V1 est respecté lorsque :

- `environment.domain` est obligatoire ;
- toutes les versions de runtime sont explicites ;
- les propriétés inconnues sont rejetées ;
- seuls Laravel, Symfony et Nuxt sont acceptés comme frameworks ;
- seul PostgreSQL est supporté comme service V1 ;
- une application peut ne pas avoir de bloc `web` ;
- un seul hostname est possible par application ;
- les variables d'environnement restent dans `.env` ;
- le gestionnaire Node vaut `pnpm` par défaut ;
- seules les versions Node 22 et 24 sont acceptées en V1 ;
- le schéma JSON et les fixtures reflètent cette spécification.
