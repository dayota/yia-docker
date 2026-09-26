# Yia — Spécification du système de documentation projet

> **Statut :** sous-spécification normative de Yia  
> **Document parent :** `yia-spec.md`  
> **Identifiant :** `YIA-SPEC-DOCS`  
> **Version :** 1  
> **Périmètre :** documentation projet, skills `project-docs` et `update-project-docs`, intégration Codex

---

## 1. Objet

Cette spécification définit le système de documentation projet initialisé et maintenu par Yia.

Elle complète la spécification globale `yia-spec.md`.

La spécification globale définit **quand** Yia doit disposer d'un système documentaire et les garanties générales attendues.

Le présent document définit **comment** ce système documentaire est structuré, initialisé, consulté, enrichi, versionné et validé.

Pour tout sujet concernant :

- `.agents/docs/` ;
- `.agents/skills/project-docs/` ;
- `.agents/skills/update-project-docs/` ;
- les règles documentaires ajoutées dans `AGENTS.md` ;
- la documentation dérivée de `yia.yml` ;
- la maintenance documentaire par Codex ;

ce document constitue la référence normative.

En cas d'incompatibilité avec la spécification globale, `yia-spec.md` conserve la priorité pour les invariants généraux de Yia.  
Pour les détails propres au système documentaire, cette sous-spécification fait autorité tant qu'elle ne contredit pas un invariant global.

---

## 2. Objectifs

Le système documentaire Yia doit permettre à un humain ou à un agent tel que Codex :

1. de comprendre rapidement l'architecture du projet ;
2. de retrouver uniquement la documentation pertinente pour une tâche ;
3. de connaître les décisions techniques déjà prises ;
4. de connaître les conventions et règles propres au projet ;
5. de disposer de la connaissance métier durable utile au développement ;
6. de détecter les contradictions entre code, configuration et documentation ;
7. de capitaliser les connaissances durables découvertes pendant une tâche ;
8. d'éviter de réapprendre le projet à chaque nouvelle session ;
9. d'éviter la duplication et l'accumulation de documentation obsolète ;
10. de distinguer clairement la documentation générée de la connaissance humaine.

Le système documentaire fait partie des capacités natives de Yia et doit être initialisé par défaut lors de `make init`.

---

## 3. Hors périmètre

Le système documentaire Yia n'a pas pour objectif de :

- documenter automatiquement chaque ligne de code ;
- générer une documentation utilisateur finale ;
- remplacer les commentaires utiles dans le code ;
- remplacer les README propres aux frameworks ou bibliothèques ;
- conserver des informations temporaires propres à une tâche ;
- stocker des secrets ;
- créer un document pour chaque modification mineure ;
- charger toute la documentation dans le contexte de l'agent à chaque tâche.

Le système vise à conserver de la **connaissance durable et utile au développement**.

---

## 4. Principes fondamentaux

### 4.1. Documentation projet

La documentation appartient au projet consommateur.

Elle est stockée dans :

```text
.agents/docs/
```

Elle est versionnée avec le projet sauf exception explicitement documentée.

Elle ne doit jamais être stockée dans le sous-module `.yia/`.

---

### 4.2. Skills projet

Les skills documentaires sont installés dans :

```text
.agents/skills/
├── project-docs/
│   └── SKILL.md
└── update-project-docs/
    └── SKILL.md
```

Après leur initialisation, ces fichiers appartiennent au projet consommateur.

Une mise à jour de Yia ne doit pas les écraser silencieusement.

---

### 4.3. Documentation ciblée

Un agent ne doit pas charger systématiquement toute la documentation projet.

Il doit utiliser :

```text
.agents/docs/INDEX.md
```

comme routeur documentaire afin de sélectionner les documents pertinents pour la tâche.

---

### 4.4. Source de vérité

La documentation ne doit pas devenir une seconde source de vérité pour une information déjà décrite par une source déclarative.

Par exemple :

```text
yia.yml > documentation générée décrivant l'environnement Yia
```

La documentation générée est une représentation lisible d'une source de vérité et non une source indépendante.

---

### 4.5. Connaissance durable

Une information doit être intégrée à la documentation lorsqu'elle est susceptible d'influencer des tâches futures.

Exemples :

- décision d'architecture ;
- règle métier ;
- convention ;
- contrainte technique ;
- dépendance structurelle ;
- limitation connue ;
- choix de sécurité ;
- convention API ;
- stratégie de tests ;
- procédure importante ;
- raison d'un choix non évident.

Les informations triviales, temporaires ou propres à une tâche ponctuelle ne doivent pas être documentées.

---

## 5. Structure initiale

`make init` doit créer au minimum :

```text
.agents/
├── docs/
│   ├── INDEX.md
│   ├── architecture/
│   │   └── development-environment.md
│   ├── decisions/
│   │   └── README.md
│   ├── standards/
│   ├── domain/
│   └── glossary.md
│
└── skills/
    ├── project-docs/
    │   └── SKILL.md
    └── update-project-docs/
        └── SKILL.md
```

Yia peut créer d'autres fichiers lorsque le projet déclaré dans `yia.yml` le justifie.

---

## 6. Catégories documentaires

### 6.1. `architecture/`

Contient la description durable de l'architecture.

Exemples :

- architecture applicative ;
- topologie Docker ;
- flux entre applications ;
- architecture de données ;
- authentification ;
- organisation des runtimes ;
- dépendances entre composants.

Un document d'architecture décrit principalement **comment le système est organisé**.

---

### 6.2. `decisions/`

Contient les décisions d'architecture et ADR.

Une décision doit être créée lorsqu'au moins deux alternatives raisonnables existent et que le choix retenu a un impact durable.

Une décision doit expliquer au minimum :

- le contexte ;
- le problème ;
- les alternatives significatives ;
- la décision ;
- les conséquences connues ;
- son statut.

Statuts recommandés :

```text
proposed
accepted
deprecated
superseded
rejected
```

Une décision remplacée ne doit pas être supprimée si sa conservation aide à comprendre l'historique du projet.

---

### 6.3. `standards/`

Contient les conventions obligatoires ou recommandées propres au projet.

Exemples :

- PHP ;
- TypeScript ;
- APIs ;
- tests ;
- Git ;
- Docker ;
- SQL ;
- observabilité ;
- sécurité ;
- conventions de nommage.

Un standard décrit principalement **comment contribuer de façon cohérente au projet**.

---

### 6.4. `domain/`

Contient la connaissance métier nécessaire pour modifier correctement le logiciel.

Exemples :

- concepts métier ;
- règles fonctionnelles ;
- états métier ;
- invariants ;
- relations entre entités ;
- vocabulaire fonctionnel.

Une règle métier importante ne doit pas être cachée uniquement dans l'implémentation lorsqu'elle est nécessaire à la compréhension du projet.

---

### 6.5. `glossary.md`

Contient les termes ambigus, métier ou techniques dont le sens est spécifique au projet.

Chaque entrée devrait rester courte et pointer vers un document plus détaillé lorsque nécessaire.

---

## 7. Contrat de `INDEX.md`

### 7.1. Rôle

`INDEX.md` est le point d'entrée principal du système documentaire.

Il ne remplace pas la documentation.

Il permet à un agent de déterminer **quoi lire**.

---

### 7.2. Informations minimales

Chaque document référencé doit fournir au minimum :

- son chemin ;
- une description courte ;
- les situations dans lesquelles il doit être consulté.

Exemple :

```markdown
### `architecture/runtime.md`

**Description :** organisation des runtimes PHP et Node.

**Lire lorsque :**
- une application est ajoutée ;
- une version PHP ou Node change ;
- une topologie Docker est modifiée ;
- un runtime doit être créé, mutualisé ou supprimé.
```

---

### 7.3. Granularité

`INDEX.md` doit rester utilisable rapidement.

Il ne doit pas recopier le contenu des documents.

Il doit permettre une sélection pertinente avec un minimum de lecture.

---

### 7.4. Maintenance

`INDEX.md` doit être mis à jour lorsqu'un changement affecte :

- l'existence d'un document ;
- son emplacement ;
- sa fonction ;
- les situations nécessitant sa lecture.

Une modification interne sans impact sur la découvrabilité du document ne nécessite pas nécessairement une modification de `INDEX.md`.

---

## 8. Skill `project-docs`

### 8.1. Responsabilité

`project-docs` est le skill de consultation documentaire.

Il doit être utilisé avant ou pendant une tâche lorsqu'une connaissance existante du projet peut influencer l'implémentation.

---

### 8.2. Workflow obligatoire

Le skill doit suivre le processus suivant :

```text
tâche
  ↓
lire INDEX.md
  ↓
identifier les documents pertinents
  ↓
lire uniquement ces documents
  ↓
appliquer les contraintes et décisions trouvées
  ↓
réaliser la tâche
```

---

### 8.3. Cas d'utilisation

Il doit notamment être utilisé lorsqu'une tâche concerne :

- l'architecture ;
- Docker ;
- les runtimes ;
- la base de données ;
- une API ;
- une convention de développement ;
- une règle métier ;
- une dépendance structurante ;
- une décision technique existante ;
- une modification transversale.

---

### 8.4. Interdictions

`project-docs` :

- ne modifie pas la documentation ;
- ne lit pas toute la documentation par défaut ;
- n'invente pas une règle absente ;
- ne considère pas une documentation obsolète comme automatiquement supérieure au code ;
- ne résout pas silencieusement une contradiction.

---

### 8.5. Contradiction

Lorsqu'une contradiction est détectée entre :

- documentation et code ;
- documentation et `yia.yml` ;
- deux documents ;
- ADR et documentation d'architecture ;

le conflit doit être identifié explicitement.

L'agent doit déterminer la source normative selon les règles de priorité définies dans cette spécification ou demander une décision lorsqu'aucune résolution sûre n'est possible.

---

## 9. Skill `update-project-docs`

### 9.1. Responsabilité

`update-project-docs` maintient la connaissance durable du projet.

Il doit être utilisé lorsqu'une tâche :

- crée une connaissance durable ;
- modifie une connaissance durable ;
- invalide une connaissance existante ;
- révèle qu'une documentation est obsolète ;
- introduit une décision qui influencera des tâches futures.

---

### 9.2. Workflow obligatoire

Le skill suit le processus :

```text
nouvelle connaissance
      ↓
chercher si elle est déjà documentée
      ↓
mettre à jour le document existant si possible
      ↓
sinon déterminer la catégorie adaptée
      ↓
créer le document seulement si nécessaire
      ↓
mettre à jour INDEX.md si la découvrabilité change
      ↓
vérifier cohérence et absence de duplication
```

---

### 9.3. Mise à jour avant création

Le skill doit préférer :

```text
mettre à jour > créer
```

lorsqu'un document existant traite déjà du même sujet.

La multiplication de petits documents redondants doit être évitée.

---

### 9.4. Création d'un ADR

Un ADR est approprié lorsque :

- plusieurs alternatives raisonnables existaient ;
- le choix retenu est structurant ;
- comprendre la raison du choix sera utile dans le futur.

Un ADR n'est pas nécessaire pour une modification mécanique ou évidente.

---

### 9.5. Informations à ne pas documenter

Ne doivent normalement pas être ajoutés :

- résultats temporaires de debug ;
- chemins propres à une machine ;
- secrets ;
- tokens ;
- mots de passe ;
- détails éphémères d'une branche ;
- todo ponctuel ;
- informations triviales directement évidentes dans le code ;
- journaux exhaustifs d'une session Codex.

---

## 10. Ordre de priorité documentaire

Pour un sujet donné, l'ordre de priorité est :

1. source de vérité déclarative explicitement définie par Yia ou le projet ;
2. ADR ou décision `accepted` applicable au sujet ;
3. documentation d'architecture ;
4. standards ;
5. documentation métier ;
6. documentation générale ;
7. commentaires et notes non normatives.

Exemple :

```text
yia.yml > architecture/development-environment.md
```

pour une information générée à partir de `yia.yml`.

Un ADR n'a priorité que dans son périmètre.

---

## 11. Documentation dérivée

### 11.1. Définition

Une documentation dérivée est générée à partir d'une source structurée déjà normative.

Exemple :

```text
yia.yml
  ↓
architecture/development-environment.md
```

---

### 11.2. Fichier initial

Yia doit générer :

```text
.agents/docs/architecture/development-environment.md
```

à partir de `yia.yml`.

---

### 11.3. Contenu minimal

Le document doit pouvoir présenter :

- nom du projet ;
- version du schéma Yia ;
- version Yia si disponible ;
- applications ;
- types d'applications ;
- frameworks déclarés ;
- runtimes PHP ;
- runtimes Node ;
- services d'infrastructure ;
- hostnames ;
- ports explicitement exposés ;
- reverse proxy ;
- réseau Docker ;
- volumes persistants ;
- dépendances d'infrastructure significatives.

---

### 11.4. Marquage

Une documentation dérivée doit être identifiable comme générée.

Exemple :

```markdown
> Ce document est généré par Yia à partir de `yia.yml`.
> Ne pas le modifier manuellement.
```

---

### 11.5. Régénération

`make update` peut régénérer intégralement un document dérivé.

Toute modification manuelle d'un document explicitement marqué comme généré peut être perdue.

Aucune connaissance humaine unique ne doit donc y être stockée.

---

## 12. Documentation humaine

Les documents non générés dans `.agents/docs/` sont considérés comme appartenant au projet.

Yia ne doit jamais les écraser automatiquement.

Cela inclut notamment :

- ADR ;
- documentation métier ;
- documentation d'architecture spécifique ;
- standards ;
- glossaire enrichi par le projet.

---

## 13. Templates Yia

Les templates initiaux sont stockés dans Yia, par exemple :

```text
.yia/templates/documentation/
├── docs/
│   ├── INDEX.md
│   ├── decisions/
│   │   └── README.md
│   └── glossary.md
│
├── skills/
│   ├── project-docs/
│   │   └── SKILL.md
│   └── update-project-docs/
│       └── SKILL.md
│
└── agents/
    └── AGENTS.fragment.md
```

Le répertoire précis peut évoluer tant que le contrat fonctionnel est respecté.

---

## 14. Contrat de `make init`

Dans le domaine documentaire, `make init` doit :

1. créer `.agents/docs/` si nécessaire ;
2. créer `.agents/skills/` si nécessaire ;
3. installer `project-docs` ;
4. installer `update-project-docs` ;
5. créer `INDEX.md` ;
6. créer la structure documentaire minimale ;
7. générer `architecture/development-environment.md` ;
8. installer ou fusionner les règles documentaires nécessaires dans `AGENTS.md` ;
9. vérifier que les fichiers créés sont cohérents ;
10. enregistrer la version du système documentaire initialisé.

`make init` ne doit pas écraser silencieusement un fichier préexistant contenant des modifications utilisateur.

---

## 15. Contrat de `make update`

Dans le domaine documentaire, `make update` doit :

- régénérer la documentation explicitement dérivée ;
- préserver la documentation humaine ;
- préserver les skills personnalisés du projet ;
- détecter si un template Yia plus récent existe ;
- ne jamais remplacer silencieusement un skill projet modifié ;
- rester idempotent.

L'évolution d'un template Yia n'implique pas automatiquement sa copie sur un projet existant.

---

## 16. Version du système documentaire

Yia doit pouvoir connaître la version du système documentaire installé.

La version peut être stockée dans l'état interne Yia, par exemple :

```yaml
documentation:
  schema: 1
```

Cette information ne doit pas nécessairement être ajoutée à `yia.yml` si elle ne représente pas une intention utilisateur.

La version sert à :

- détecter les anciennes structures ;
- proposer des migrations ;
- appliquer une migration documentaire explicite ;
- assurer la compatibilité des templates.

---

## 17. Migration documentaire

Une modification incompatible du système documentaire doit être traitée comme une migration.

Exemples :

- déplacement de `INDEX.md` ;
- changement de structure obligatoire ;
- nouveau format d'ADR ;
- nouvelle sémantique d'un skill ;
- remplacement d'un mécanisme d'indexation.

Une migration documentaire :

1. ne doit pas supprimer de connaissance humaine ;
2. doit être déterministe ;
3. doit être testable ;
4. doit idéalement être idempotente ;
5. doit produire un résumé des changements ;
6. doit préserver un fichier modifié par le projet lorsque la fusion automatique n'est pas sûre.

---

## 18. Intégration dans `AGENTS.md`

Yia doit intégrer au `AGENTS.md` du projet au minimum les règles suivantes :

```markdown
## Documentation projet

Ce projet utilise le système documentaire Yia.

Avant toute tâche susceptible de dépendre de l'architecture, des décisions, des conventions, des standards ou des règles métier du projet, utiliser le skill `project-docs`.

Le point d'entrée de la documentation est :

    .agents/docs/INDEX.md

Ne pas charger systématiquement toute la documentation.
Utiliser `INDEX.md` pour sélectionner les documents pertinents.

Lorsqu'une tâche introduit, modifie ou invalide une connaissance durable du projet, utiliser `update-project-docs`.

Ne pas documenter les changements triviaux ou temporaires.

Ne jamais stocker de secret dans la documentation.

En cas de contradiction entre documentation et implémentation, ne pas choisir silencieusement une interprétation : identifier le conflit et le résoudre selon les sources normatives applicables.
```

Yia peut utiliser un mécanisme de section gérée afin d'éviter les duplications lors de `make update`.

Exemple :

```markdown
<!-- YIA:DOCUMENTATION:START -->
...
<!-- YIA:DOCUMENTATION:END -->
```

Toute stratégie de fusion doit préserver le contenu utilisateur situé hors des sections gérées.

---

## 19. Idempotence

Les opérations documentaires Yia doivent être idempotentes.

L'exécution successive de :

```bash
make update
make update
```

sans modification des entrées ne doit pas produire de nouveau changement Git.

---

## 20. Git

Par défaut, les éléments suivants doivent être versionnés :

```text
.agents/docs/
.agents/skills/project-docs/
.agents/skills/update-project-docs/
AGENTS.md
```

La documentation dérivée peut être versionnée si Yia choisit ce modèle.

Si elle est versionnée, `make update` doit garantir qu'elle reste synchronisée avec sa source.

Les données temporaires du moteur documentaire ne doivent pas être versionnées.

---

## 21. Sécurité

Le système documentaire ne doit jamais écrire automatiquement :

- mots de passe ;
- tokens ;
- clés privées ;
- secrets applicatifs ;
- valeurs sensibles issues de `.env`.

Lorsqu'un secret est nécessaire à la compréhension, seule sa **variable attendue** peut être documentée.

Exemple acceptable :

```text
DATABASE_PASSWORD est requis.
```

Exemple interdit :

```text
DATABASE_PASSWORD=secret123
```

---

## 22. Validation

Yia doit pouvoir vérifier au minimum :

- présence de `INDEX.md` ;
- présence du skill `project-docs` ;
- présence du skill `update-project-docs` ;
- cohérence de la structure minimale ;
- présence des règles documentaires dans `AGENTS.md` ;
- absence de fichiers documentaires générés dans `.yia/` ;
- cohérence de la documentation dérivée avec `yia.yml` ;
- absence de conflit évident de version du système documentaire.

Ces contrôles doivent pouvoir participer à :

```bash
make validate
```

et/ou :

```bash
make doctor
```

---

## 23. Tests

### 23.1. Initialisation

Tester qu'un projet vide reçoit la structure documentaire attendue après `make init`.

### 23.2. Idempotence

Tester qu'un second `make update` ne modifie aucun fichier si les entrées n'ont pas changé.

### 23.3. Préservation

Tester qu'un document humain personnalisé n'est jamais écrasé.

### 23.4. Skill personnalisé

Tester qu'un `SKILL.md` modifié par le projet n'est pas silencieusement remplacé par une nouvelle version du template Yia.

### 23.5. Documentation dérivée

Tester qu'une modification de `yia.yml` entraîne la modification attendue de `development-environment.md`.

### 23.6. AGENTS.md

Tester qu'une exécution répétée ne duplique pas la section documentaire gérée par Yia.

### 23.7. Secrets

Tester que la génération documentaire ne copie aucune valeur sensible provenant de `.env`.

---

## 24. Definition of Done

Une évolution du système documentaire Yia est terminée lorsque :

- les deux skills de base sont disponibles ;
- `INDEX.md` permet de retrouver la documentation pertinente ;
- `make init` initialise correctement un projet vide ;
- `make update` est idempotent ;
- les documents humains sont préservés ;
- les documents dérivés sont synchronisés avec leur source ;
- aucun secret n'est copié dans la documentation ;
- `AGENTS.md` contient les règles nécessaires sans duplication ;
- les migrations éventuelles sont testées ;
- les tests automatisés passent ;
- la spécification globale reste cohérente avec cette sous-spécification.

---

## 25. Règles pour Codex lors du développement de Yia

Lorsqu'il implémente ou modifie ce système, Codex doit :

1. considérer ce document comme la spécification normative du sous-système documentaire ;
2. consulter également `yia-spec.md` pour les invariants globaux ;
3. ne pas introduire un comportement documentaire contraire à l'idempotence globale de Yia ;
4. ne jamais écrire de donnée projet dans `.yia/` ;
5. préserver les fichiers utilisateurs ;
6. préférer une migration explicite à un remplacement destructif ;
7. ajouter ou mettre à jour les tests pour toute modification de contrat ;
8. mettre à jour cette spécification lorsqu'un contrat documentaire change.

---

## 26. Relation avec la spécification globale

La relation documentaire recommandée est :

```text
yia-spec.md
    │
    ├── définit les invariants globaux
    ├── définit l'API Make
    ├── définit le cycle init/update
    └── référence YIA-SPEC-DOCS
             │
             └── documentation.md
                 ├── structure .agents/
                 ├── project-docs
                 ├── update-project-docs
                 ├── INDEX.md
                 ├── génération documentaire
                 └── migrations documentaires
```

`yia-spec.md` ne doit pas recopier cette sous-spécification.

Il doit seulement :

- déclarer que le système documentaire est obligatoire ;
- définir ses garanties globales ;
- référencer le présent document pour le contrat détaillé.

Cela évite les divergences entre deux descriptions du même comportement.
