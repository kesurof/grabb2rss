Contexte

Le projet Grabb2RSS vient de livrer une release stable avec :

UI multi-pages (sidebar + drawer)

Suppression complète du legacy (dashboard.html, style.css, JS tabs, RSS/Admin legacy)

app.js page-aware, audité, sans fonctions mortes

Setup sans JS inline, UX robuste

Zéro erreur console sur les pages actives

👉 Cette release est figée et ne doit plus être modifiée.

Objectif de la Phase 2

Améliorations non critiques, orientées maintenabilité et qualité, sans régression fonctionnelle.

⚠️ Cette phase est indépendante de la release précédente.

Règles fondamentales (obligatoires)

❌ Ne pas modifier le comportement fonctionnel existant

❌ Ne pas re-refactoriser ce qui vient d’être stabilisé

❌ Pas de suppression sans audit explicite

✅ Une amélioration = un axe précis

✅ Chaque étape doit être isolable et réversible

✅ Toujours zéro erreur console

Axes possibles (à choisir un par un)
AXE 1 — Suppression des derniers onclick / handlers inline

Objectif

Remplacer progressivement les derniers attributs inline par des handlers JS basés sur data-*.

Contraintes

Pas de changement UX

Même logique événementielle

Un seul type de composant à la fois (ex: Grabs uniquement)

Critère de validation

Aucun onclick, onchange, onsubmit restant sur les pages ciblées

Comportement strictement identique

AXE 2 — Modularisation interne de app.js (sans build complexe)

Objectif

Structurer app.js par sections logiques (Setup, Torrents, Logs, Security, Overview).

Contraintes

Toujours un seul bundle JS

Pas d’introduction de framework

Pas de renommage inutile

Livrable attendu

Sections clairement délimitées

Initialisation par data-page inchangée

AXE 3 — Extraction par feature (option avancée)

Objectif

Extraire certaines features (setup, torrents, logs) dans des fichiers JS dédiés.

Contraintes

Chargement conditionnel uniquement

Partage des helpers communs

Décision documentée avant extraction

⚠️ À faire uniquement après validation des axes 1 ou 2.

AXE 4 — UX polish (non fonctionnel)

Objectif

Améliorer la lisibilité et le confort :

états vides

messages d’erreur

cohérence des labels/actions

Contraintes

Pas de changement de logique

Pas de nouveaux composants non validés

Respect strict du design system existant