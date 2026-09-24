# Préparer l’épisode suivant — 24 septembre 2026

## Utilisation

Après redémarrage du Lab puis Ctrl+F5, ouvrir une histoire avec un scénario écrit et cliquer sur **Créer l’épisode suivant**, en haut de l’atelier Histoires.

Le panneau **Préparer la suite** charge l’épisode de départ sans appel LLM. Qwen est proposé depuis le catalogue (local en priorité) ; le choix reste interchangeable et mémorisé. Si Qwen manque, choisir explicitement un autre modèle. Les modèles de conception/rédaction restent ceux de l’histoire et sont accessibles dans les réglages repliés.

Trois entrées : discuter, demander **Propose-moi une suite** (une seule piste), ou remplir directement la direction. Point de départ, moments importants, fin et contraintes sont éditables et sauvegardés. Une question demande une explication sans mise à jour implicite de la direction. Chaque échange produit sa réponse et l’éventuelle direction en un seul appel.

Le bouton **Écrire cet épisode** lance le parcours habituel : épisode suivant de l’arc, ou nouvelle histoire liée au parent. Un épisode suivant déjà écrit s’ouvre sans être réécrit. Une nouvelle suite longue constitue un seul épisode continu ; les références compatibles sont reprises par les mécanismes de fabrication existants.

Fermer le panneau enregistre les modifications. Le chat actif continue côté serveur et se retrouve en rouvrant le panneau. Le message non envoyé est conservé localement dans le navigateur. Une erreur conserve la dernière direction et expose le brouillon reçu. Aucun mécanisme de réparation/retry LLM automatique n’est ajouté.

## Portée technique

- Contrat de direction et instantané de continuité : `domain/story_followup.py`.
- Discussion asynchrone, sauvegarde, cancellation, reprise et validation : `application/story_followup.py`.
- Brouillons isolés dans `workspace/stories/followups/followup-*.json`, sans modification du scénario source pendant la préparation.
- Origine explicite : histoire, unité, version et empreinte de contenu. Faits écrits arrêtés à l’unité choisie ; arc futur transmis séparément. Les changements de sélection seuls ne changent pas le canon.
- État physique final transmis à la suite. Les images restent celles des références compatibles choisies dans le parcours de fabrication ; aucun nouveau rendu au stade de préparation.
- Direction d’une unité existante transmise au rédacteur et aux relectures. Empreinte de dépendance inchangée pour les histoires sans direction et pour les unités précédentes.
- Destination déterministe et résultat sauvegardé avant lancement. Double clic/retry : une seule suite. Après une interruption entre création et lancement, ouvrir la destination et reprendre via le parcours habituel.
- Révision optimiste du brouillon et vérification du contexte source avant échange/validation. **Actualiser le contexte** conserve la direction et demande sa relecture.
- Réponse de chat bornée à 8 000 tokens, JSON court, sans appel supplémentaire de synthèse. L’arc et le scénario conservent leurs budgets existants. Les échanges utilisent le gateway et les traces habituels.
- Aucun changement de recette vidéo, prompt de rendu, production, DLSS, dépendance ou service système.

## Vérification

16 nouveaux tests préparés (service/API et navigateur), plus adaptation de l’ancien test d’ouverture de suite. **Non exécutés**, conformément aux consignes du worktree. Contrôles réalisés : AST de dix fichiers Python, compilation syntaxique de douze scripts JavaScript (application et fixtures, sans exécuter leur contenu), unicité des IDs HTML, diff-check.

Dans `D:\Code\panelforge-krea2-flux` :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_story_followup*.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_stories_browser.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_long_stories.py"
```

À observer au premier essai réel : qualité de la proposition Qwen, durée de réponse, respect de la direction dans l’écriture et reprise des références. Aucun LLM, rendu, modification de runtime, redémarrage ou publication n’a été effectué pendant le patch.

## Limites conservées

La direction d’un épisode prévu complète son arc existant ; une refonte de cet arc passe par les outils de modification habituels. L’historique transmis à une nouvelle histoire respecte la limite existante de 60 000 caractères : un dépassement est explicite, sans troncature silencieuse de faits. Une histoire source modifiée doit être réactualisée avant lancement. Les tests fonctionnels et l’essai utilisateur restent à effectuer.


## Correctif ciblé — portée des identifiants des suites

Le nouveau projet peut utiliser `episode-1` / `event-1` même si le récit précédent possède ces mêmes IDs locaux. Le contexte `story_id_scope` distingue désormais le projet courant, sa source lorsqu'elle est connue, les unités autorisées et les champs historiques externes. Les consignes expliquent cette portée à la conception, à l'édition, à la relecture de l'arc, à la correction, à la rédaction et au chat. Les IDs déjà établis dans le nouvel arc restent stables : aucune renumérotation automatique, même si une précédente correction a commencé à `event-7`.

Les faits, relations, connaissances, états visuels et identités des personnages/objets hérités sont conservés. Les références aux événements doivent toujours viser l'arc courant ; le validateur, les contrats de sortie, l'interface, le budget d'appels et les données enregistrées restent inchangés. La relecture spectateur conserve sa projection limitée au récit visible. Aucun champ supplémentaire pour les histoires sans contexte historique externe.

Quatre régressions ciblées préparées dans `tests/test_story_identifier_scope.py` : portée dans huit opérations, historique collé ou instantané seul, absence d'effet sur les histoires sans historique et sur la relecture spectateur, maintien du rejet des IDs locaux/dependances invalides. Tests non exécutés ; syntaxe Python et diff vérifiés statiquement.

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_story_identifier_scope.py"
```

Pour l'histoire déjà bloquée : une fois les traitements terminés, redémarrer le Lab pour charger le correctif, rouvrir l'histoire puis **Détails de continuité et de vérification → Relire l'arc**. Cette action appelle le LLM pour remplacer le diagnostic avec les nouvelles consignes, sans réécriture de l'arc. Si la relecture lève les remarques bloquantes, reprendre **Continuer le parcours**. Le correctif ne supprime pas automatiquement un diagnostic sauvegardé et n'a pas été essayé avec le LLM réel. La simplification de l'interface reste à aligner séparément.
