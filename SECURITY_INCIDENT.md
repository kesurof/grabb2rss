# 🚨 INCIDENT DE SÉCURITÉ - CLÉS API EXPOSÉES

## ⚠️ ACTIONS IMMÉDIATES REQUISES

Le fichier `.env` contenant vos clés API a été accidentellement committé et poussé sur GitHub dans le commit `bccd502776a5db8d80a25e6a8227d9eddbee164a`.

### Clés API exposées publiquement :
- `PROWLARR_API_KEY`: `90b7de97d47745cba81cc9a55909514c`
- `RADARR_API_KEY`: `2b7f06a904c44923a838c3a34bef74e5`
- `SONARR_API_KEY`: `9c90833a4e2543cd9ba2b41b002810a2`

## 🔒 ACTIONS OBLIGATOIRES À FAIRE IMMÉDIATEMENT

### 1. Régénérer TOUTES les clés API

#### Prowlarr
1. Ouvrir Prowlarr → Settings → General
2. Cliquer sur "Regenerate" à côté de API Key
3. Sauvegarder la nouvelle clé

#### Radarr
1. Ouvrir Radarr → Settings → General
2. Cliquer sur "Regenerate" à côté de API Key
3. Sauvegarder la nouvelle clé

#### Sonarr
1. Ouvrir Sonarr → Settings → General
2. Cliquer sur "Regenerate" à côté de API Key
3. Sauvegarder la nouvelle clé

### 2. Mettre à jour votre fichier .env local

Le fichier `.env` existe toujours localement mais n'est plus tracké par Git.
Mettez à jour les nouvelles clés dans ce fichier.

### 3. Nettoyer la branche `dev`

La branche `dev` contient toujours le commit avec les clés exposées. Vous devez la nettoyer :

```bash
# Retourner sur la branche dev
git checkout dev

# Force push pour écraser l'historique (vous avez peut-être besoin de désactiver la protection)
git push --force origin dev
```

Si vous obtenez une erreur 403, vous devrez :
- Soit désactiver temporairement la protection de branche sur GitHub
- Soit supprimer et recréer la branche dev
- Soit contacter le support GitHub pour supprimer l'historique sensible

### 4. Vérifier les accès

Si vos services sont exposés sur Internet, vérifiez les logs pour voir si quelqu'un a utilisé ces clés :
- Logs Prowlarr : Settings → Logs
- Logs Radarr : System → Logs
- Logs Sonarr : System → Logs

## ✅ Ce qui a été fait

1. ✅ Le fichier `.env` a été ajouté au `.gitignore`
2. ✅ Le fichier `.env` a été supprimé du tracking Git
3. ✅ L'historique Git a été nettoyé avec `git filter-branch`
4. ✅ La branche `claude/fix-radarr-sonarr-script-lO4f9` a été force pushed
5. ⚠️ La branche `dev` nécessite un force push manuel (erreur 403)

## 📚 Prévention future

Le fichier `.env` est maintenant correctement exclu du Git via `.gitignore`.

**Vérifiez toujours avant de commit :**
```bash
git status
git diff
```

## 🔗 Ressources

- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [Rotating API keys](https://docs.github.com/en/rest/guides/best-practices-for-integrators#rotating-api-keys)

---

**Date de l'incident**: 2026-01-20
**Commit exposé**: bccd502776a5db8d80a25e6a8227d9eddbee164a
**Statut**: En cours de résolution - CLÉS À RÉGÉNÉRER IMMÉDIATEMENT
