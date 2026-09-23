# Échec de conception : joute au restaurant, 22 septembre 2026

Le modèle a répété sa recherche de chute sans commencer la réponse structurée. Augmenter encore la limite de sortie ne traite pas cette cause.

## Preuves enregistrées

- Projet : `story-e47817cb329d4290929b7b7fc18f3048` ; appel : `llm-a360967ded4b4d4fb52a8bf1ad1da601`.
- Demande : dispute autour de l’addition, un restaurant, fruits anthropomorphes, dialogues français, chute ironique. Six clips maximum de dix secondes, une unité continue.
- Opération : `story.long.compose@2.2.0`, recette éditoriale révision 3. Architecte : `local::unsloth/Qwen3.8-27B-GGUF`. Le Rédacteur Gemma n’a pas encore été appelé.
- Début : 15 h 10 min 55 s à Paris ; durée journalisée 531 796 ms, soit environ 8 min 52 s. Un seul appel, aucune réparation automatique ni validation du scénario.
- Réponse : zéro caractère ; raisonnement journalisé : 240 698 caractères. Le projet conserve les premiers 144 000 caractères, conformément à sa limite d’affichage.
- Un paragraphe revient 93 fois ; plusieurs autres reviennent 92 fois. Un cycle exact de 2 396 caractères est reproduit dans `tests/fixtures/long_stories/reasoning_loop_2026_09_22.json` pour la régression.
- Le serveur renvoie `finish_reason=length`. Le budget demandé est 80 000 tokens, mais les compteurs `prompt_tokens` et `completion_tokens` sont absents : le journal ne prouve pas un décompte exact de 80 000 tokens consommés.

## Lecture de la dérive

Le début du raisonnement comprend le brief, le lieu unique, les options et le budget. Il explore des conflits de paiement entre Pêche et Kiwi, puis rejette à répétition sa chute, jugée insuffisamment surprenante. Il reprend les mêmes événements, la même carte refusée, les mêmes alternatives et la même hésitation. Cette répétition est visible jusque dans la fin du journal.

La boucle est établie ; son déclencheur précis ne l’est pas à partir d’un appel unique. L’exigence interprétée d’un retournement supplémentaire semble y contribuer. Aucun rejet JSON local n’a provoqué cet échec : le modèle n’est jamais arrivé au JSON. La présence du schéma contraint dans la requête ne prouve pas qu’il soit responsable. Les états visuels ne sont pas demandés dans cette opération de conception d’arc.

## Correctif implémenté

Mise à jour après retour utilisateur : la détection automatique des répétitions a été retirée, ainsi que l’arrêt qu’elle déclenchait. Un raisonnement répété continue jusqu’à la réponse ou l’arrêt du fournisseur, ou une annulation manuelle. La fixture de répétition sert désormais à vérifier ce comportement.

1. Fermeture explicite de la réponse HTTP du fournisseur à la fermeture du flux. Le document antérieur reste conservé en cas d’échec.
2. Messages séparant une vraie réponse partielle de l’absence totale de scénario. Le budget demandé n’est plus présenté comme un compteur mesuré. Le parcours ne propose plus de revalider un brouillon inexistant.
3. Archivage du raisonnement même quand la tentative ne contient aucun JSON, pour le conserver lors d’une reprise.
4. Recette éditoriale révision 4 : un retournement du rapport de force suffit ; choisir une progression cohérente puis produire l’arc. Budget de 80 000 et contrats de réponse inchangés.

Ces changements clarifient l’échec et la consigne narrative ; ils ne garantissent pas qu’un modèle produira une bonne histoire à chaque appel.

## Validation et reprise

Contrôles statiques Python/JSON/diff effectués. Tests préparés, non exécutés à la demande persistante de l’utilisateur. Aucun appel LLM, génération, redémarrage ou modification du projet runtime pendant l’intervention.

Après la fin des traitements, redémarrer le Lab et reprendre l’étape de l’histoire existante. Son brief est suffisant ; aucun scénario de cet essai n’est récupérable sans nouvelle génération. La modification de consigne s’applique au nouvel appel, sans réécrire les projets existants.

Tests ciblés à la main de l’utilisateur, depuis le worktree actif :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_reasoning tests.test_story_schema_transport tests.test_prompt_lab.OpenAICompatibleGatewayTest
```
