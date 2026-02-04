# Frontend Assets

Ce dossier contient les **sources** front destinées au mini build UI.

Structure:
- `web/assets/css/app.css`: entrée CSS unique.
- `web/assets/js/app.js`: entrée JS unique.

Sorties attendues (build):
- `web/static/css/app.css`: CSS compilé à servir côté app.
- `web/static/js/app-ui.js`: JS compilé/packé à servir côté app.

Règles:
- Aucun style inline dans les templates.
- Aucune logique UI inline dans les templates.
- Les pages migrées ne chargent que les assets buildés.
