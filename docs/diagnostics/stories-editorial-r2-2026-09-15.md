# Histoires — recadrage éditorial r2 et correction de révision

Retour utilisateur du 15 septembre 2026 : les propositions s'éloignent des
exemples vidéo. Projet examiné en lecture seule :
`story-2ed759b21bef4e348389fa67eae9dc16`, « Le Drama du Sport ».
Modèle effectif : Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP, endpoint local.

## Constats issus des traces

- Les appels de propositions et de développement utilisent la recette d'origine
  r1. Le modèle assimile explicitement brainrot à du jargon et à des réactions
  comiques. Les humains génériques, les excuses de sport et la chute en plaisanterie
  suivent cette interprétation. Les exemples d'origine écrits par l'agent poussent
  aussi vers des gags ; « anthropomorphe » ne suffit pas à fixer des fruits.
- Le brief demande une morale simple et des personnages manichéens. L'ancienne
  instruction qui déconseille la morale peut affaiblir cette préférence malgré
  la priorité générale donnée au brief.
- Trois micro-scènes répètent presque le même soupçon sur l'absence de sueur.
  La révélation mélange les relations et la présence des personnages ; la fin
  crée une solidarité entre une épouse trompée et la femme qui trompe son conjoint,
  sans motif narratif.
- La dernière demande « Les personnages sont des fruits, je veux une histoire de
  tromperie » a produit un objet `reply + scenario + concepts + selected_id`.
  L'application attendait exclusivement `reply + scenario` : la correction a donc
  été rejetée et le scénario humain est resté actif. Le contenu reçu est conservé
  dans le brouillon et l'archive des échanges.

## Correctif livré

Les trois consignes éditoriales r2 sont dans
`prompt_sources/story.brainrot/1.0.0/editorial-r2/`. Elles précisent le mélo frontal,
les fruits adultes à échelle humaine par défaut, les actes odieux et leurs
conséquences, les liens entre couples, la provenance des preuves et la progression
réelle entre scènes. Le registre direct est distinct du jargon adolescent ; les
demandes de morale simple, d'une fin cruelle ou d'un épisode ouvert font foi.
Les exemples sont désormais des intrigues de trahison, injustice et sacrifice
exploité. Aucun ajout de caméra, de plan imposé ou d'appel LLM.

La première lecture de la recette avec le nouveau code crée et active r2 seulement
si r1 est encore la version initiale intacte. Les personnalisations et retours de
version explicites sont conservés. r1 reste consultable et réactivable dans
l'éditeur. Les trois champs actifs de ce projet correspondent bien aux sources
initiales : ce cas recevra la mise à jour après redémarrage puis lecture de la
recette. Aucun fichier de son workspace n'a été modifié pendant l'intervention.

« 3 nouvelles pistes » repart désormais du brief et des demandes de l'auteur.
Les anciennes propositions servent de rappel pour éviter les répétitions ; le
scénario et les messages générés précédemment ne sont plus réinjectés comme
document à imiter pour cette action. Le développement et la révision continuent
à recevoir le document courant et la conversation.

Le parseur accepte en révision de scénario les deux champs supplémentaires
observés, uniquement si leurs données sont valides. `selected_id` ne peut pas
changer le choix de l'utilisateur ; `concepts` doit rester une liste complète
valide. Concepts et scénario sont appliqués dans une même version, sans effacer
le scénario. Les autres extensions inconnues, les références invalides et les
réponses tronquées restent rejetées.

Le brouillon rejeté de ce projet n'a pas été appliqué automatiquement : corriger
son format ne suffit pas à corriger son ton ou sa logique. Pour évaluer r2,
redémarrer le Lab puis demander **3 nouvelles pistes**. La conversation permet
aussi une refonte explicite du scénario existant.

## Vérification

AST Python des quatre fichiers concernés, lecture UTF-8 des trois consignes,
contrôle de la recette existante en lecture seule et `git diff --check` OK.
Tests de régression ajoutés dans `tests/test_stories.py` : enveloppe complète
acceptée sans perte du scénario, refus du changement de sélection et des champs
invalides, nouveau départ des propositions, mise à jour initiale, retour à r1 et
conservation des personnalisations. Tests non exécutés conformément à AGENTS.
Aucun LLM, rendu ou redémarrage lancé ; qualité éditoriale à valider par l'auteur.
