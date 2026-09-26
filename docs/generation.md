# Yia — Spécification de la génération déterministe

> **Statut :** normative
>
> **Document parent :** [`yia-spec.md`](./yia-spec.md)
>
> **Identifiant :** `YIA-SPEC-GENERATION`
>
> **Version du manifeste :** 1

## 1. Objet

Cette sous-spécification définit le moteur qui transforme le modèle normalisé
en snapshot reconstructible sous `.yia-runtime/`.

La génération ne démarre, ne reconstruit et ne redémarre aucun service Docker.

## 2. Entrées et sorties

L'unique entrée fonctionnelle est le modèle de configuration validé et
normalisé. Le moteur construit également l'état interne défini dans
[`state.md`](./state.md).

Un générateur reçoit un contexte immuable contenant :

- le modèle normalisé ;
- l'état interne calculé pour ce modèle.

Il retourne des fichiers en mémoire avec un chemin relatif, un contenu binaire
et un mode contrôlé. Il n'écrit jamais directement dans le projet.

## 3. Chemins générés

Tous les chemins sont relatifs à `.yia-runtime/`.

Sont interdits :

- les chemins absolus ;
- les segments `..` ;
- les collisions entre fichiers et répertoires ;
- les doublons entre générateurs ;
- les chemins réservés à l'état et au manifeste.

Les chemins réservés V1 sont :

```text
state/yia-state.json
state/generation-manifest.json
```

Les modes autorisés V1 sont `0644` et `0755`.

## 4. Manifeste

Le manifeste est écrit dans :

```text
.yia-runtime/state/generation-manifest.json
```

Son schéma exécutable est
[`schemas/yia-generation-manifest.schema.json`](../schemas/yia-generation-manifest.schema.json).

Il contient :

- sa version de format ;
- la version Yia ;
- la version du schéma de configuration ;
- le hash de configuration ;
- la liste triée des générateurs ;
- la liste triée des fichiers avec chemin, SHA-256, taille et mode.

Le manifeste couvre tous les fichiers du snapshot, y compris
`state/yia-state.json`, mais ne s'auto-référence pas.

## 5. Déterminisme

La sortie ne dépend ni de l'ordre d'enregistrement des générateurs, ni de
l'ordre dans lequel ils retournent leurs fichiers.

Les JSON sont sérialisés en UTF-8 avec clés triées et saut de ligne final. Aucun
timestamp volatil n'est généré.

À modèle, version Yia, générateurs et entrées externes identiques, tous les
fichiers, hashes, tailles et modes sont identiques.

## 6. Détection des changements

Avant publication, le moteur compare le snapshot attendu au runtime courant :

- ensemble exact des fichiers ;
- contenu exact ;
- mode exact.

Si tout correspond, aucune écriture ni aucun renommage n'est effectué.

Un fichier modifié, absent, supplémentaire ou possédant un mode différent rend
le runtime obsolète et déclenche une nouvelle publication. Les fichiers non
manifestés sont supprimés avec l'ancien runtime, puisque `.yia-runtime/` est
entièrement reconstructible et ne contient aucune donnée persistante.

## 7. Staging et publication

Le snapshot complet est d'abord écrit dans un répertoire de staging voisin de
`.yia-runtime/`. Chaque fichier est synchronisé avant publication, puis le
snapshot est vérifié contre les contenus attendus.

La publication utilise des renommages atomiques sur le même filesystem :

1. l'ancien runtime est renommé en sauvegarde temporaire ;
2. le staging validé est renommé en `.yia-runtime/` ;
3. l'ancienne sauvegarde est supprimée après succès.

Si l'étape 2 échoue, l'ancien runtime est restauré. Si cette restauration
échoue également, la sauvegarde est conservée et son chemin est fourni dans
l'erreur structurée afin de permettre une récupération.

Les répertoires transitoires utilisent les préfixes :

```text
.yia-runtime.staging-
.yia-runtime.backup-
```

## 8. Erreurs

Une erreur de génération utilise :

```text
YIA_GENERATION_FAILED
```

avec le code de sortie `4`.

Les erreurs identifient le générateur ou le chemin concerné sans recopier le
contenu produit ni le texte arbitraire d'une exception, afin d'éviter toute
fuite de données.

## 9. Sécurité et persistance

Le moteur ne touche jamais :

- `.yia/` ;
- `.yia-data/` ;
- le code applicatif ;
- les volumes persistants.

L'état et le manifeste ne contiennent aucun secret ni copie brute de
`yia.yml`.

## 10. Definition of Done

Le contrat est respecté lorsque :

- les générateurs sont isolés des écritures projet ;
- le snapshot est construit et vérifié dans un staging ;
- une erreur préserve ou restaure le runtime précédent ;
- chaque fichier généré est manifesté ;
- les modifications locales et fichiers obsolètes sont détectés ;
- deux générations identiques produisent exactement le même résultat ;
- une seconde génération identique n'écrit rien ;
- aucun comportement Docker n'est exécuté.
