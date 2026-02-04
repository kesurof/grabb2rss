 UI Refonte – Plan Directeur

**Projet : Grabb2RSS**
**Objectif : migration UI vers Tailwind CSS + Alpine.js (sidebar + pages, mini-build verrouillé)**


> ⚠️ RÈGLE FONDAMENTALE – DOCUMENT IMMUTABLE
>
> Ce document est une **source de vérité figée**.
> 
> - Il ne doit **jamais** être réécrit, reformulé, résumé ou répété.
> - Toute demande ultérieure concerne **une étape précise uniquement**.
> - Aucune section hors de l’étape demandée ne doit être reproduite.
> - Si une information est déjà présente dans ce document, elle est considérée comme acquise.

> 📌 INTERPRÉTATION DES ÉTAPES
>
> Une étape cochée signifie uniquement que **la planification est validée**.
> L’exécution d’une étape consiste à **appliquer les changements dans le projet**
> (templates, assets, JS, CSS, structure), et non à modifier ce document.
>
> Toute réponse qui reformule le plan global est considérée comme invalide.

---

## 0. Résumé exécutif

### Objectifs

* Refonte complète de l’UI actuelle vers une interface **sidebar + pages**
* Utilisation de **Tailwind CSS** pour les styles et **Alpine.js** pour les interactions locales
* Aucun changement des endpoints backend existants
* Mise en place d’un **mini build front reproductible**, avec **versions verrouillées**
* Suppression des styles inline, JS inline et duplication UI

### Non-objectifs

* Pas de refonte API ou métier
* Pas de migration SPA
* Pas de refactor backend hors besoins UI stricts

### Bénéfices attendus

* UI cohérente et homogène
* Composants réutilisables
* Maintenance facilitée
* Accessibilité et responsive améliorés
* Dette technique UI fortement réduite

### Risques principaux

* Dérive de scope
* Régressions visuelles
* Coexistence prolongée legacy / nouveau UI
* Fragilité du build front

### Réduction des risques

* Migration progressive par phases
* Critères d’acceptation stricts par page
* Points de non-retour après chaque phase
* Verrouillage strict des versions
* Backlog atomique et validable étape par étape

---

## 1. Audit de l’existant (basé sur le repo)

### 1.1 Inventaire des templates

* Layout principal : `web/templates/base.html`
* Pages :

  * `login.html`
  * `setup.html`
  * `dashboard.html` (onglets multiples)
* Sections actuelles intégrées dans le dashboard :

  * Overview, Grabs, Torrents, Stats, RSS, Logs, Configuration, Security, Admin

### 1.2 Inventaire CSS / JS

* CSS monolithique : `web/static/css/style.css`
* JS principal : `web/static/js/app.js`

  * Navigation par onglets
  * Génération HTML en JS
  * Handlers inline
* JS spécifique RSS : `web/static/js/rss-manager.js`
* Entrées prévues mais inutilisées :

  * `web/assets/css/app.css`
  * `web/assets/js/app.js`

### 1.3 Points douloureux

* Styles inline fréquents
* HTML généré en JS (maintenabilité, XSS potentiel)
* JS global non segmenté
* CSS global non structuré
* Absence de design tokens
* Navigation tabulaire peu scalable
* Chargement Chart.js via CDN sans verrouillage

### 1.4 Comportements UI à préserver

* Login + redirection
* Setup initial et validations
* Tables Grabs / Torrents / Logs
* KPI dashboard
* Gestion API keys + copie
* Notifications utilisateur
* Actions bulk torrents
* Indicateurs d’état de synchronisation

### 1.5 Dette technique UI

* Mélange des responsabilités
* Duplication de logique
* Accessibilité implicite mais non formalisée
* Absence de layout et composants structurants

---

## 2. Cibles UX & Information Architecture

### 2.1 Arborescence sidebar + pages

1. **Overview**
2. **Grabs**
3. **Torrents**
4. **RSS**
5. **Configuration**
6. **Setup**
7. **Security**
8. **Logs / Diagnostics**

### 2.2 Contrat de page (règle globale)

Pour chaque page :

* Données requises clairement identifiées
* États UI définis : loading / empty / error / ready
* Actions principales explicites
* Actions destructrices toujours confirmées
* HTML structurel rendu côté serveur (Jinja)

### 2.3 Parcours utilisateur clés

* Setup initial
* Login
* Consultation RSS
* Gestion des clés API
* Suivi Grabs / Torrents
* Consultation Logs et diagnostics
* Maintenance et nettoyage

### 2.4 Règles de navigation

* Sidebar persistante (desktop)
* Drawer accessible (mobile)
* État actif clair
* Topbar avec actions contextuelles
* Breadcrumbs uniquement si profondeur réelle
* Bouton retour cohérent

### 2.5 Cartographie des onglets existants vers les pages finales

| Onglet actuel (dashboard) | Page finale cible | Notes de migration |
| --- | --- | --- |
| Dashboard | Overview | Conserver KPI, statut sync, actions rapides, dernier grab |
| Stats | Overview | Fusionner charts et stats détaillées dans Overview |
| Grabs | Grabs | Page dédiée avec table, filtre tracker, états loading/empty |
| Torrents | Torrents | Page dédiée avec actions bulk et métriques |
| RSS | RSS | Page dédiée avec API keys + URLs RSS |
| Logs | Logs / Diagnostics | Regrouper logs de sync, filtres et export |
| Configuration | Configuration | Page dédiée avec catégories de paramètres |
| Security | Security | Page dédiée pour compte et API keys |
| Admin | Logs / Diagnostics | Déplacer actions maintenance et stats système ici |

Pages hors onglets existants: Login et Setup restent des pages dédiées et migrent sans passer par la sidebar.

---

## 3. Design System minimal (réutilisable)

### 3.1 Composants obligatoires

* Button
* Input / Select
* Card
* Table
* Badge
* Alert
* Toast
* Modal / Drawer
* Skeleton / Loading
* Empty state
* Pagination
* Dropdown

### 3.2 Règles d’usage

* Primary : action principale
* Secondary : alternative
* Danger : suppression / actions destructrices
* Ghost : actions contextuelles
* Tables : données denses
* Cards : KPI et regroupements
* Toast : feedback non bloquant
* Alert : message persistant

### 3.3 Accessibilité

* Focus visible
* Contrastes suffisants
* Labels explicites
* Navigation clavier complète
* Aria pour drawer, modals, toasts

### 3.4 Tokens de design

* Palette limitée (primary, neutres, success, warning, danger)
* Échelles d’espacement
* Radius standardisés
* Typographie cohérente
* Icônes normalisées

### 3.5 Gouvernance UI (anti-dérive)

* Tout nouveau pattern doit :

  * réutiliser un composant existant
  * ou être ajouté explicitement au design system
* Interdiction des styles “one-off”

### 3.6 Définir tokens et conventions UI (étape 3)

Objectif: établir un socle de tokens et des conventions d’usage avant l’implémentation.

Tokens UI à figer:
1. Couleurs: primaire, neutres, succès, warning, danger, infos, états désactivés.
2. Espacements: échelle simple et limitée, cohérente avec la densité des pages data-heavy.
3. Typographie: titres, sous-titres, corps, monospace pour valeurs techniques.
4. Radius et ombres: niveaux limités pour cards, inputs, dropdowns.
5. Icônes: set unique et cohérent, tailles standardisées.

Conventions d’usage:
1. Boutons: primary pour action principale de page, secondary pour alternatives, danger pour destructive, ghost pour contextuel.
2. Tables: une grille par page data, header sticky si pertinent, états loading/empty définis.
3. Forms: labels explicites, helper text optionnel, erreurs sous champ, focus visible.
4. Alerts/Toasts: alert pour message persistant, toast pour feedback non bloquant et temporaire.
5. Layout: densité uniforme, éviter les sections “full-bleed” sans justification.

Critères d’acceptation:
1. Tokens documentés et utilisés par au moins 2 composants.
2. Conventions applicables sans ambiguïté sur toutes les pages cibles.

---

## 4. Architecture front (templates + assets)

### 4.1 Principe directeur

* HTML structurel rendu **côté serveur**
* Alpine utilisé uniquement pour :

  * états UI
  * interactions locales
  * déclenchement de fetch
* Aucune génération complète de DOM en JS

### 4.2 Layout

* Shell commun :

  * Sidebar
  * Topbar
  * Zone notifications
  * Zone contenu
* Footer optionnel (version)

### 4.3 Définition du shell sidebar + topbar (étape 2)

Objectif: définir clairement les zones, responsabilités et conventions du shell sans implémentation technique.

Zones du shell:
1. Sidebar (desktop): navigation principale, logo, groupes de liens, statut sync synthétique, entrée vers Setup si requis.
2. Drawer (mobile): navigation identique à la sidebar, accessible via un bouton dans la topbar, focus trap et fermeture explicite.
3. Topbar: titre de page, actions contextuelles, zone utilisateur, indicateurs d’état.
4. Content: slot principal, largeur contrôlée, gestion loading/empty/error.
5. Alerts/Toasts: couche dédiée aux messages globaux, visible sans masquer la navigation.
6. Footer minimal: version applicative et liens secondaires si nécessaire.

Conventions de navigation:
1. L’état actif est unique et reflète la page courante.
2. Les actions contextuelles sont alignées à droite dans la topbar.
3. Login et Setup utilisent un layout dédié hors shell.
4. Pages protégées affichent l’utilisateur et l’accès Security.

Critères d’acceptation:
1. Le shell est décrit de façon stable et réutilisable pour toutes les pages.
2. Chaque page cible peut indiquer clairement ses actions topbar.
3. Le drawer mobile est un équivalent fonctionnel de la sidebar.

### 4.4 Organisation templates

* `base.html` : layout racine
* `pages/` : pages finales
* `partials/` :

  * sidebar
  * topbar
  * alerts
  * tables
  * cards
  * formulaires
* Conventions documentées

### 4.5 Organisation assets

* Sources : `web/assets/`
* Build vers : `web/static/`
* CSS final unique
* JS pack minimal
* Politique **zéro inline**

### 4.6 Préparer structure assets et build (étape 4)

Objectif: définir la structure minimale des assets et les règles de build reproductible avant tout code.

Décisions à formaliser:
1. Entrées: un CSS source unique et un JS source unique dans `web/assets/`.
2. Sorties: un CSS compilé et un JS packé dans `web/static/` pour servir l’app.
3. Règles de compilation: build déterministe, aucun ajout automatique non documenté.
4. Chargement: pages migrées doivent uniquement charger les assets buildés, pas d’assets legacy.
5. Versioning: hash ou version explicite si nécessaire pour cache, avec stratégie claire.

Critères d’acceptation:
1. Structure des dossiers claire et documentée.
2. Les futures pages migrées n’ont plus besoin de `style.css`.
3. La stratégie de build est compatible CI et local.

### 4.7 Charts

* Utilisation limitée
* Chargement uniquement sur pages concernées
* Version verrouillée
* CSP compatible

---

## 5. Mini build & verrouillage des versions

### 5.1 Source de vérité

* Une seule source documentée pour :

  * version Node
  * version Tailwind
  * version Alpine

### 5.2 Principes

* Lockfile commité
* Install strict
* Aucune version flottante
* Divergence locale / CI = erreur bloquante

### 5.3 Politique de mise à jour

* Mises à jour planifiées
* PR dédiées
* Validation visuelle et perf obligatoire

---

## 6. Plan de migration progressive (phases)

### Phase 0 – Préparation

* Objectifs : layout, conventions, build
* Livrables : shell, tokens, documentation
* **Point de non-retour** : build reproductible validé

### Phase 1 – Login

* Objectifs : valider design system
* **Point de non-retour** : aucun style inline restant

#### Détail étape 5 – Migrer Login

Objectif: migrer la page Login vers le nouveau design system sans changer le flux d’authentification.

Livrables:
1. Layout Login conforme aux tokens et composants (button, input, alert, loading).
2. Suppression des styles inline spécifiques Login.
3. Chargement unique des assets buildés.

Dépendances:
1. Tokens et conventions UI définis.
2. Structure assets et build définie.

Risques:
1. Régression visuelle ou perte d’accessibilité (focus, erreurs).
2. Incohérence de messages d’erreur.

Critères d’acceptation:
1. Login fonctionnel avec mêmes endpoints et redirection.
2. États erreur et loading clairement visibles.
3. Aucun style inline résiduel sur Login.

### Phase 2 – Setup / Configuration

* Objectifs : formulaires, alerts, loaders
* **Point de non-retour** : suppression scripts dupliqués

### Phase 3 – RSS + Security

* Objectifs : tables, badges, copy
* **Point de non-retour** : plus de HTML généré en JS

### Phase 4 – Grabs / Torrents

* Objectifs : tables denses, filtres, bulk
* **Point de non-retour** : tables unifiées

### Phase 5 – Overview

* Objectifs : KPI, charts conditionnels
* **Point de non-retour** : dashboard legacy supprimé

---

## 7. Checklist Qualité / Sécurité / Perf

* Accessibilité complète
* CSS minimal
* JS chargé par page
* Aucun inline script/style
* CSP compatible
* Erreurs utilisateur lisibles
* Mobile first validé

---

## 8. Definition of Done

* Toutes les pages migrées
* `style.css` supprimé ou archivé
* Aucun inline style / JS
* Design system utilisé partout
* Navigation sidebar fonctionnelle
* Parcours critiques inchangés

---

## 9. Backlog détaillé – Étapes cochables

* [x] **1. Cartographier les onglets existants vers les pages finales**
* [x] **2. Définir le shell sidebar + topbar**
* [x] **3. Définir tokens et conventions UI**
* [x] **4. Préparer structure assets et build**
* [x] **5. Migrer Login**
* [x] **6. Créer composants de formulaires**
* [x] **7. Migrer Setup**
* [x] **8. Créer composants Card & Alert**
* [x] **9. Créer composant Table (loading / empty)**
* [x] **10. Migrer RSS**
* [x] **11. Migrer Security**
* [x] **12. Migrer Grabs**
* [x] **13. Migrer Torrents**
* [x] **14. Migrer Logs / Diagnostics**
* [x] **15. Migrer Configuration**
* [x] **16. Migrer Overview**
* [x] **17. Implémenter navigation sidebar + drawer**
* [x] **18. Centraliser notifications / toasts**
* [x] **19. Supprimer CSS legacy résiduel**
* [x] **20. Audit final & cleanup UI**

---

## 10. Audit final & cleanup UI (exécuté)

### 10.1 Checklist audit

* Routes UI migrées accessibles et alignées sur la navigation sidebar.
* Aucune page active ne charge `style.css`.
* Layout shell, drawer et topbar fonctionnels.
* Composants UI (cards, alerts, tables, forms, toasts) utilisés et cohérents.
* Pages Setup/Login accessibles sans legacy CSS.
* Redirections: `/` et `/dashboard` pointent vers l’UI migrée.

### 10.2 Nettoyages appliqués

* Suppression du lien legacy CSS dans `base.html`.
* Suppression du fichier `web/static/css/style.css`.

### 10.3 Validation visuelle recommandée

* Desktop: Overview, Grabs, Torrents, RSS, Security, Logs, Configuration, Setup, Login.
* Mobile: drawer, tables, boutons et formulaires principaux.
