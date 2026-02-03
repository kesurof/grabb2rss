# Processus de Release

## Versioning (source de vérité = VERSION)

- `VERSION` est la source de vérité unique de la version applicative.
- Format attendu : SemVer `X.Y.Z`.
- Une release stable est créée **uniquement** quand `VERSION` change sur `main`.
- `VERSION` doit être **strictement supérieure** au dernier tag publié (pas de downgrade).

Pourquoi : traçabilité, reproductibilité, auditabilité, et rollback propre via tags immuables.

## Workflow de développement

- Le travail quotidien se fait sur `dev`.
- Push sur `dev` : CI build + tests + publication d’une image GHCR taggée `dev` et `dev-<sha>`.
- PR `dev → main` : CI build + tests, **aucune publication**.
- Merge sur `main` :
  - si `VERSION` a été bumpé : tag Git + images de release + GitHub Release.
  - sinon : aucune release.

## Tags Docker disponibles et recommandés

### Tags de test (dev)
- `dev` : suit le dernier état de la branche `dev` (pratique, non déterministe).
- `dev-<sha>` : tag immuable recommandé pour figer un déploiement de test.

### Tags de release (stables)
- `vX.Y.Z` : recommandé en production (immuable).
- `vX.Y` : suit la dernière release du minor (moins déterministe).
- `vX` : suit la dernière release du major (encore moins déterministe).
- `latest` : tag de confort, déconseillé en production stricte.

Pour une prod stable et auditée, utilisez **`vX.Y.Z`**.

## Git tags et GitHub Releases

- Le tag Git `vX.Y.Z` est créé automatiquement par le workflow de release.
- La GitHub Release est créée automatiquement avec notes générées par GitHub.
- Le workflow ne se déclenche pas sur tags pour éviter doubles builds/boucles.

## Procédure pour publier une nouvelle version

1. Réaliser les changements sur `dev`.
2. Mettre à jour `VERSION` (patch/minor/major selon l’impact).
3. Ouvrir une PR `dev → main`.
4. Vérifier la CI.
5. Merger : la release est créée automatiquement.

### Que faire si…

- **La build release échoue après création du tag** : corriger, bump en patch, remerger.  
  La release suivante sera propre et déterministe.
- **Le tag existe déjà** : incrémenter `VERSION` (patch) puis remerger.

## Déploiement serveur de test

Le serveur de test peut suivre l’intégration via l’image `dev`.  
Pour figer une version pendant une validation, préférer `dev-<sha>`.

## Bonnes pratiques

- Toujours bumper `VERSION` dans la PR qui doit déclencher une release.
- Éviter `latest` en production si vous cherchez du déterminisme.
- Utiliser des tags immuables pour rollback rapide et sûr.
