# Spécifications Yia

## État d'implémentation

Les phases 0 à 13 du plan d'implémentation fournissent le socle Python, la
validation stricte de `yia.yml`, son modèle interne normalisé et l'état local
reconstructible, un moteur de génération déterministe et la topologie Docker
Compose avec son point d'entrée HTTP Apache, ses runtimes PHP-FPM et ses
runtimes de développement Node/Nuxt, ainsi qu'un service PostgreSQL persistant
initialisé depuis les variables du fichier `.env`, ainsi que l'API Make V1 et
ses primitives de génération, diagnostic et cycle de vie Docker. Le système
documentaire projet installe aussi les skills `project-docs` et
`update-project-docs`, protège la documentation humaine et synchronise la vue
dérivée de `yia.yml`. `make init` assemble ces briques pour initialiser un
projet consommateur sans démarrer Docker. `make update` fait ensuite converger
la documentation, le runtime généré et les services Docker vers `yia.yml`, sans
supprimer les données persistantes et sans recréer les services inchangés. Pour
préparer le dépôt puis exécuter les contrôles :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
make version
make test
make validate CONFIG=tests/projects/minimal/yia.yml
make validate CONFIG=tests/projects/minimal/yia.yml FORMAT=json
make generate CONFIG=tests/projects/minimal/yia.yml
```

Dans un projet consommateur contenant `.yia/` et `yia.yml`, l'initialisation
nominale est :

```bash
make init
make validate
make doctor
make update
```

La commande `validate` est sans effet de bord. Une configuration invalide
retourne le code de sortie `2` et le code stable `YIA_CONFIG_INVALID`.

Ce répertoire contient les spécifications normatives de Yia.

L'objectif est de conserver une **spécification racine courte et transversale** et de déléguer les contrats détaillés à des sous-spécifications par domaine.  
Un humain ou un agent ne doit charger que les documents nécessaires à la tâche en cours.

---

## Structure documentaire du dépôt

```text
Yia/
├── README.md
└── docs/
    ├── yia-spec.md
    ├── documentation.md
    ├── configuration.md
    ├── state.md
    ├── generation.md
    ├── docker.md
    └── make-api.md
```

`README.md` est le point d'entrée humain et agent du dépôt.

Les spécifications normatives et techniques sont stockées dans `docs/`.

---

## Ordre de lecture

Pour toute modification de Yia :

1. lire `docs/yia-spec.md` ;
2. identifier dans le présent index les sous-spécifications concernées ;
3. lire uniquement ces sous-spécifications ;
4. implémenter sans contredire les invariants globaux ;
5. mettre à jour la ou les spécifications si un contrat change.

Pour une tâche ciblée, il n'est pas nécessaire de charger toutes les sous-spécifications.

---

## Hiérarchie normative

```text
README.md
    │
    └── docs/
        ├── yia-spec.md              ← spécification racine
        ├── documentation.md         ← système documentaire / agents
        ├── configuration.md         ← contrat yia.yml
        ├── state.md                 ← état interne reconstructible
        ├── generation.md            ← génération déterministe
        ├── docker.md                ← Docker, réseaux, volumes, runtimes
        └── make-api.md              ← API publique Make
```

`docs/yia-spec.md` définit :

- la vision ;
- les objectifs ;
- le périmètre ;
- les concepts communs ;
- les invariants globaux ;
- les frontières entre sous-systèmes ;
- le cycle de vie général ;
- les règles générales de compatibilité ;
- les Definition of Done globales.

Les sous-spécifications définissent les contrats détaillés propres à leur domaine.

En cas de contradiction :

1. un invariant explicite de `docs/yia-spec.md` est prioritaire ;
2. pour les détails d'un sous-système, sa sous-spécification fait autorité ;
3. une contradiction doit être résolue dans la documentation, jamais masquée dans l'implémentation.

---

## Spécification principale

### [`docs/yia-spec.md`](./docs/yia-spec.md)

**Statut : normative**

Spécification fonctionnelle et technique globale de Yia.

**Lire lorsque :**

- une modification touche plusieurs sous-systèmes ;
- un invariant global est concerné ;
- une nouvelle capacité Yia est ajoutée ;
- une décision modifie le cycle `init / validate / update / doctor` ;
- une modification peut introduire un breaking change ;
- le périmètre d'une sous-spécification n'est pas clair.

---

## Sous-spécifications

### [`docs/documentation.md`](./docs/documentation.md)

**Identifiant :** `YIA-SPEC-DOCS`  
**Statut : normative**

Définit le système documentaire installé dans les projets Yia.

Couvre notamment :

- `.agents/docs/` ;
- `.agents/docs/INDEX.md` ;
- `project-docs` ;
- `update-project-docs` ;
- ADR et catégories documentaires ;
- documentation dérivée ;
- intégration `AGENTS.md` ;
- migrations documentaires ;
- protection des fichiers humains ;
- règles documentaires pour Codex.

**Lire lorsque :**

- `make init` ou `make update` touche `.agents/` ;
- un skill documentaire est modifié ;
- une documentation est générée depuis `yia.yml` ;
- `AGENTS.md` est généré ou fusionné ;
- le comportement de Codex vis-à-vis de la documentation change.

---

### [`docs/configuration.md`](./docs/configuration.md)

**Identifiant :** `YIA-SPEC-CONFIG`  
**Statut : normative**

Doit devenir la référence du format `yia.yml`.

Périmètre prévu :

- version du schéma ;
- sections et propriétés ;
- valeurs par défaut ;
- validation ;
- normalisation ;
- compatibilité ;
- migrations de schéma ;
- erreurs de configuration ;
- exemples valides et invalides.

**Lire lorsque :**

- le schéma `yia.yml` change ;
- une propriété est ajoutée, supprimée ou renommée ;
- les valeurs par défaut évoluent ;
- la validation ou la migration de configuration est modifiée.


---

### [`docs/docker.md`](./docs/docker.md)

**Identifiant :** `YIA-SPEC-DOCKER`  
**Statut : normative**

Doit devenir la référence du modèle d'exécution Docker de Yia.

Périmètre prévu :

- Docker Compose ;
- Apache ;
- PHP-FPM multi-version ;
- Node multi-version ;
- PostgreSQL ;
- services optionnels ;
- réseaux ;
- volumes ;
- ports ;
- DNS / hostnames ;
- healthchecks ;
- build et rebuild ;
- données persistantes ;
- artefacts runtime.

**Lire lorsque :**

- un container ou runtime est ajouté ;
- la topologie réseau change ;
- un volume ou un port est modifié ;
- Apache, PHP, Node ou PostgreSQL sont concernés ;
- la génération Compose évolue.


---

### [`docs/state.md`](./docs/state.md)

**Identifiant :** `YIA-SPEC-STATE`  
**Statut : normative**

Définit le fichier `.yia-runtime/state/yia-state.json`, son schéma, son
écriture atomique, sa reconstruction et la détection des migrations.

**Lire lorsque :**

- le format de l'état interne change ;
- une version ou un hash est ajouté à l'état ;
- la lecture, l'écriture ou la migration de l'état évolue.


---

### [`docs/generation.md`](./docs/generation.md)

**Identifiant :** `YIA-SPEC-GENERATION`

**Statut : normative**

Définit l'abstraction des générateurs, le manifeste des fichiers générés, la
détection de changements et la publication transactionnelle dans
`.yia-runtime/`.

**Lire lorsque :**

- un générateur ou un artefact généré est ajouté ou modifié ;
- le manifeste, le staging ou la publication du runtime évolue ;
- l'idempotence de la génération est concernée.


---

### [`docs/make-api.md`](./docs/make-api.md)

**Identifiant :** `YIA-SPEC-MAKE`  
**Statut : normative**

Doit devenir la référence de l'API publique Make.

Périmètre prévu :

- commandes publiques ;
- paramètres ;
- variables ;
- codes de retour ;
- sortie humaine ;
- sortie machine ;
- idempotence ;
- dépendances entre commandes ;
- commandes destructives ;
- compatibilité de l'API.

**Lire lorsque :**

- une cible Make publique est ajoutée ou modifiée ;
- le comportement de `init`, `update`, `validate` ou `doctor` change ;
- une option CLI/Make est introduite ;
- une sortie machine ou un code de retour change.


---

## Statuts possibles

Chaque sous-spécification doit indiquer son statut :

- **normative** : contrat actif et applicable ;
- **draft** : contrat en cours de conception, non encore garanti ;
- **squelette** : périmètre réservé mais contenu non spécifié ;
- **deprecated** : encore présent pour compatibilité mais destiné à disparaître ;
- **superseded** : remplacé par une autre spécification.

Un document `draft` ou `squelette` ne doit jamais être utilisé pour inventer un comportement absent de la spécification principale.

---

## Règle de découpage

Créer une nouvelle sous-spécification lorsqu'au moins une des conditions suivantes est vraie :

- le domaine possède ses propres invariants ;
- il possède un cycle de vie ou un versioning propre ;
- son contrat dépasse une section raisonnable dans `docs/yia-spec.md` ;
- Codex devrait pouvoir travailler sur ce domaine sans charger toute la spec globale ;
- plusieurs fonctionnalités dépendent du même contrat spécialisé.

Ne pas créer une sous-spécification pour un simple détail d'implémentation.

---

## Convention de lien depuis `docs/yia-spec.md`

La spec racine doit référencer une sous-spécification de façon explicite :

```markdown
Le contrat détaillé du sous-système documentaire est défini dans :

> [`docs/documentation.md`](./docs/documentation.md)
```

La spec racine conserve uniquement :

- les invariants transversaux ;
- l'interface avec les autres sous-systèmes ;
- le lien vers la sous-spécification.

Elle ne doit pas recopier tout le contrat détaillé.

---

## Règle pour Codex

Lorsque Codex travaille sur Yia :

- considérer `docs/yia-spec.md` comme obligatoire ;
- utiliser ce `README.md` comme routeur de spécifications ;
- charger seulement les sous-spécifications pertinentes ;
- ne pas déduire un contrat depuis un document marqué `squelette` ;
- mettre à jour la spécification concernée lorsqu'un comportement contractuel change ;
- signaler toute contradiction entre implémentation et spécification.
