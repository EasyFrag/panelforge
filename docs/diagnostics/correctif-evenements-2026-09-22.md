# Dépendances omises lors de la relecture de l’arc

Projet : `story-9ddd34b57dc549d2bc959d9c735ac0ec`, « Jus de trahison ».

## Diagnostic

La conception a été acceptée (`llm-2a4067718f57481a9f2ab1fb01cf3d43`). La relecture `edit_outline` a ensuite échoué deux fois : `llm-dd37021b04e54376bea3ddd4f5a29209` puis `llm-32da5d473cb0446781a16d586494b19a`, environ 100 et 114 secondes. Chaque réponse omet `depends_on` sur ses six événements. Les unités, identifiants et ordres restent identiques à ceux de l’arc fourni à la relecture.

Le JSON est complet, avec `finish_reason=stop` et un budget de 80 000 tokens. Aucun changement des réglages narratifs ni augmentation du budget ne résout cette omission. Le premier raisonnement mentionne même les dépendances à conserver, sans que le modèle les écrive dans sa réponse finale.

La consigne simple est bien enregistrée. Le projet utilise encore le point de départ `adapt`, deux séquences de cinq clips de dix secondes, narration dialogue et profil mélodrame. Ces choix ne provoquent pas l’erreur de structure.

## Correctif

- Les consignes et le contrat d’entrée explicitent les cinq champs obligatoires de chaque événement, notamment `depends_on`, même si sa valeur est `[]`.
- Lors de `edit_outline` uniquement, une omission de ce seul champ reprend les liens de l’arc enregistré si les unités, les identifiants et l’ordre de tous les événements sont conservés. Le texte édité reste celui reçu ; le graphe existant n’est pas remplacé par des dépendances devinées ou des listes vides systématiques.
- Une valeur explicitement fournie n’est jamais remplacée. Les références inconnues, événements ajoutés/supprimés/réordonnés, autres champs manquants ou champs supplémentaires restent soumis à la validation stricte. La création initiale et la révision libre ne bénéficient pas de cette récupération.
- La récupération est tracée dans les normalisations, avec conservation du brouillon original. Elle ne lance pas de LLM et ne crée pas de boucle.
- Si le contrat reste invalide, le diagnostic indique le chemin de l’événement et les champs manquants/inattendus.

Après redémarrage utilisateur du serveur, une fois les traitements actifs terminés, ouvrir le projet puis utiliser **Revalider la réponse reçue**. Aucune revalidation des données réelles n’a été faite pendant l’implémentation.

La relecture rejetée contient aussi du français mélangé à de l’anglais. Cette récupération structurelle préserve le texte reçu ; elle ne vaut pas validation de sa qualité éditoriale ou de sa langue.

## Vérification

Tests ciblés ajoutés pour la revalidation sans appel LLM, la conservation du texte et de l’original, les dépendances explicites, les erreurs de références et les limites de récupération. **Tests non exécutés**, selon le choix utilisateur. Contrôles limités à la syntaxe Python et au diff.

Commande pour l’utilisateur :

```powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_long_story_response_contracts tests.test_long_stories
```
