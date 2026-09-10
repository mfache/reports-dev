# Index technique `src/web`

Ce dossier regroupe la couche de présentation et le routage de l'application `reports`.

## Architecture des Templates ("Poupée Russe")

L'application utilise un système de templates emboîtés géré par `src/web/templating.py`.

### Concept
Plutôt que d'utiliser la directive `% rebase` de Bottle dans chaque fichier, la logique d'emboîtement est pilotée par le helper `view()`.
1. **La Grande Poupée (Layout)** : `templates/layout.tpl` contient la structure HTML globale, le header et les scripts communs.
2. **La Poupée Moyenne (Page)** : Chaque route rend un template spécifique (ex: `home.tpl`, `chantier.tpl`).
3. **Les Petites Poupées (Fragments)** : Des composants réutilisables inclus via `% include` ou rendus via `render()`.

### Support HTMX
Le helper `view()` détecte automatiquement les requêtes HTMX (header `HX-Request`). Dans ce cas, il ne renvoie que le contenu de la page (la poupée moyenne) sans le layout global, ce qui permet des transitions fluides sans rechargement complet.

## Modules clés

- `ui.py` : Routes de l'interface utilisateur web. Délègue au maximum la logique métier aux `services/`.
- `api.py` : Routes de l'API de flotte utilisée par les boîtiers `rpinode`.
- `stream.py` : Gestion des flux Server-Sent Events (SSE) pour les mises à jour en direct.
- `templating.py` : Wrapper autour de `bottle.template` gérant l'emboîtement et l'injection des variables globales (`BASE_PATH`, `current_user`, etc.).
- `responses.py` : Helpers pour les réponses JSON standardisées (`json_ok`, `json_error`).

## Documentation de proximité
- [SSE & Temps réel](../services/sse.md) (concept partagé avec `rpinode`).
