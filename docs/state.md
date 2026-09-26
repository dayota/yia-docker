# Yia — Spécification de l'état interne

> **Statut :** normative  
> **Document parent :** [`yia-spec.md`](./yia-spec.md)  
> **Identifiant :** `YIA-SPEC-STATE`  
> **Version du schéma :** 1

## 1. Objet

Cette sous-spécification définit le contrat de l'état interne reconstructible de
Yia.

L'état accélère la détection des changements et des migrations. Il ne remplace
jamais `yia.yml`, qui reste l'unique source de vérité déclarative.

## 2. Emplacement

L'unique fichier d'état V1 est stocké dans le projet consommateur :

```text
.yia-runtime/state/yia-state.json
```

Aucun état spécifique au projet ne doit être écrit dans `.yia/`.

## 3. Contenu V1

Le document contient exclusivement :

- `state_schema_version` : version du format de l'état ;
- `yia_version` : version du moteur ayant construit l'état ;
- `configuration_schema_version` : version du `yia.yml` normalisé ;
- `documentation_schema_version` : version du système documentaire ;
- `configuration_hash` : SHA-256 du modèle normalisé.

Le schéma exécutable est [`schemas/yia-state.schema.json`](../schemas/yia-state.schema.json).

L'état ne contient notamment ni configuration brute, ni variable
d'environnement, ni secret, ni timestamp volatil.

## 4. Reconstruction

L'état est construit uniquement depuis :

- le modèle normalisé issu de `yia.yml` ;
- les versions connues du moteur et des schémas.

Un fichier absent signifie qu'aucun état antérieur n'est disponible. Ce cas
n'est pas une erreur : l'état doit pouvoir être recréé sans perte à partir de
la configuration validée.

La suppression de `.yia-runtime/state/yia-state.json` ne doit supprimer aucune
donnée fonctionnelle ou persistante.

## 5. Lecture et validation

Avant utilisation, l'état doit être :

1. lu comme JSON UTF-8 ;
2. validé contre le schéma d'état actif ;
3. transformé en modèle interne immuable.

Un JSON illisible ou non conforme est une erreur structurée. Yia ne doit pas
extraire un état partiel d'un document invalide.

## 6. Écriture atomique et idempotence

L'écriture suit le protocole suivant :

1. validation du nouvel état ;
2. sérialisation JSON déterministe ;
3. écriture et synchronisation dans un fichier temporaire placé dans le même
   répertoire ;
4. remplacement atomique de `yia-state.json`.

Une erreur avant le remplacement doit préserver l'ancien fichier et supprimer
le fichier temporaire.

Deux écritures du même état produisent les mêmes octets. Lorsque le contenu est
déjà identique, le fichier existant n'est pas remplacé.

## 7. Migrations

Une version de schéma d'état différente de la version supportée produit :

```text
YIA_MIGRATION_REQUIRED
```

avec le code de sortie `6`.

Après lecture, Yia compare également les versions de schéma de configuration
et de documentation avec celles attendues. Toute différence est signalée comme
une migration requise avec le composant, la version courante et la version
attendue.

Une différence de `yia_version` est conservée comme métadonnée mais ne suffit
pas, à elle seule, à exiger une migration en l'absence de règle de compatibilité
plus précise.

## 8. Sécurité

Le schéma est fermé avec `additionalProperties: false`.

Ni les erreurs, ni l'état sérialisé ne doivent contenir de valeur provenant de
`.env` ou une copie de `yia.yml`.

## 9. Definition of Done

Le contrat est respecté lorsque :

- l'emplacement est stable ;
- lecture et écriture sont testées ;
- le remplacement est atomique ;
- une écriture identique est idempotente ;
- le fichier est validé par son schéma ;
- les migrations de schéma sont détectées explicitement ;
- la suppression de l'état est sans perte et permet sa reconstruction ;
- aucun secret ou contenu de configuration brute n'est conservé.
