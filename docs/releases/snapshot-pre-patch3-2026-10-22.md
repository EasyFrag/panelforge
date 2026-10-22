# Sauvegarde avant le patch 3 — 22 octobre 2026

Cette version conserve l’état du projet après le patch 2, avant toute modification
de la préparation des prompts. Elle prolonge le commit
`8bf43a91ed63fb4d5807a1a11805fe532cc778f2` (sauvegarde avant patch 2).

- Les interfaces HTTP sont séparées par atelier, avec injection explicite des services.
- `web.py` passe de 5 394 à 231 lignes ; ses 125 routes restent présentes.
- Les erreurs HTTP et les six transports de progression SSE sont mutualisés.
- Huit réponses principales sont décrites par des contrats de types, sans filtrage
  ou conversion supplémentaire à l’exécution.
- Les originaux et leur manifeste sont conservés dans
  `historique/2026-10-22-patch2-http/`, hors application et suite de tests active.
- Le bilan du code applicatif concerné est de −63 lignes, contrats inclus,
  hors tests, documentation et archives.

Les vérifications statiques du patch 2 ont réussi. Les tests ajoutés et adaptés
n’ont pas été exécutés par l’agent, conformément à `AGENTS.md`. Cette sauvegarde
ne constitue donc pas une validation dynamique du patch 2.

Validation à effectuer par l’utilisateur :

```powershell
python -m unittest discover -s tests -p "test_http_*.py"
python -m unittest discover -s tests
```

Le patch 3 reste au stade de proposition. Il devra préserver les requêtes LLM,
la compilation des réponses, les recettes versionnées et la reprise des historiques,
avec des comparaisons avant/après et une extraction progressive par famille.

Les notes locales privées, secrets, médias et données runtime ne sont pas ajoutés
à cette sauvegarde. Aucun service n’a été redémarré pour la créer.
