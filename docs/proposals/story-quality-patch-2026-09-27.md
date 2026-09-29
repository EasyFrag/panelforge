# Histoires — qualité, débit et directions d’auteur · 2026-09-27

Patch implémenté après l’audit Fraisette / Piccolo. Point de retour local avant intervention : `8499ecccf78faa441015a235463bea574dc199d9`, branche `snapshots/pre-story-quality-2026-09-27-095510`. Aucun push supplémentaire.

## Parcours

Les nouvelles histoires longues enregistrent `story_quality_version=1` et `writing_direction`. Les projets sans cette version gardent leurs consignes et leur parcours antérieur ; aucune histoire sauvegardée ni génération en cours n’est modifiée.

Pour une séquence sans blocage : conception → rédaction → relecture finale, soit trois appels. Plusieurs séquences demandent chacune une rédaction et restent relues par blocs. L’édition d’arc est conditionnelle : blocage actuel, exigence exacte non attribuée à une unité, ou relecture demandée par l’auteur. Aucune relecture LLM fictive n’est enregistrée pour l’arc. Le mode manuel garde la validation de la direction puis celle des séquences. Une difficulté narrative persistante n’autorise toujours qu’une correction automatique ; les questions ne changent pas ce mécanisme.

La nouvelle interface propose Qwen dans les deux rôles de rédaction longue, à partir du catalogue disponible. L’architecte assure conception et relecture séparée ; le rédacteur assure écriture et corrections. Gemma reste sélectionnable comme rédacteur. Les choix explicites pour ce parcours sont mémorisés, indépendamment des anciennes valeurs par défaut ; ouvrir un projet conserve ses modèles. Aucun appel de conversion JSON ou de polissage n’est ajouté.

## Intention : Dialogues et rendu

- **Style des dialogues** : naturel, jeune / argot de quartier, personnalisé. Notes et exemples facultatifs ; le curseur Vocabulaire reste indépendant.
- **Débit** : rapide par défaut, naturel disponible. Repères empiriques respectifs 4,8 et 2,4 mots/s ; ce ne sont pas des capacités H3 mesurées. Même cadence transmise aux consignes d’écriture, aux diagnostics, à la relecture et aux indications vocales REF2V.
- **Rendu visuel** : selon le récit, animation 3D, prises de vues réelles, personnalisé. Le rendu ne change pas l’espèce des personnages. Pour Piccolo et le cireur : univers « Humains réalistes », rendu « Prises de vues réelles », style « Jeune · argot de quartier », puis précision visuelle si utile.
- **Répliques exactes à conserver** : champ facultatif, une réplique par ligne, sans nom de locuteur. Le brief précise qui parle et à quel moment. Ces lignes sont distinctes des exemples de ton.

La direction visuelle initialise le style commun lors de la création de la fabrication. Les modifications ultérieures du style dans Fabrication restent prioritaires. Les directions sont reprises dans les suites ; les anciennes répliques exactes ne deviennent pas des obligations du nouvel épisode. Les interfaces Références / Scènes / Multilangue sont conservées. Les copies multilingues continuent d’utiliser leurs entrées gelées.

## Qualité et prompts

Les rôles existants sont complétés par cinq consignes versionnées `quality-*.txt`, chargées seulement pour cette politique. Le package passe à la révision 7 ; les anciens rôles restent disponibles.

La conception organise les moments sans préécrire des dialogues inventés que le rédacteur serait obligé de copier. Elle place les paroles explicitement imposées dans la preuve publique de leur événement. La relecture reçoit les preuves attendues de l’unité courante et les répliques exactes qui lui sont attribuées, ainsi que le ton et le débit ; elle ne reçoit ni bible, ni texte des secrets futurs, ni brief global. Une exigence n’est jamais une preuve que le scénario la montre effectivement.

Les répliques du champ exact sont aussi contrôlées localement. Leur absence peut déclencher la correction ciblée existante, puis une vraie relecture. Les autres demandes du brief sont vérifiées par les modèles ; leur fidélité sémantique reste à observer dans les prochains essais, sans garantie automatique de perfection.

Les estimations de débit des nouveaux projets sont informatives. Les remarques LLM portent une catégorie ; `speech_estimate` et `style` sont ramenées à `warning`, même si le modèle les déclare bloquantes. Les vrais défauts de fidélité, compréhension ou continuité peuvent toujours arrêter le parcours. `action_seconds` ne compte que les gestes/pauses réellement successifs à la parole, sans compter deux fois les gestes simultanés.

Les consignes demandent d’exploiter les clips disponibles et de répartir les moments avant de supprimer un gag ou une parole imposée. Elles demandent aussi une référence unique pour un objet important à reconnaître entre scènes, sans imposer une image pour tous les accessoires. La possession et la présence visible restent distinctes. La déduplication des variantes visuelles précédente est conservée.

Les champs de pitch court et les consignes fruitées inutiles disparaissent du contexte d’un univers humain explicite. Sans univers demandé, la famille fruits conserve son défaut. L’édition conditionnelle doit omettre les changements identiques et les retouches purement stylistiques. Aucun détecteur de répétition, filtre lexical ou réduction du budget de 80 000 tokens n’a été ajouté.

## Vérification

17 régressions ciblées ajoutées dans `tests/test_story_quality_policy.py` et `tests/test_story_quality_browser.py` : trois appels, validations manuelles, ancien parcours, Qwen/Gemma, limitation des corrections, débit, fidélité sans secrets futurs, propagation du rendu et saisie UI. Les fixtures historiques restent explicitement sur la politique antérieure.

Contrôles statiques Python, JSON et JavaScript effectués. Tests non exécutés, conformément à AGENTS.md et au choix de l’utilisateur ; aucun appel LLM, rendu ou redémarrage de service.

Commande ciblée à lancer par l’utilisateur depuis le checkout actif :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_quality_policy tests.test_story_quality_browser tests.test_story_workflow tests.test_long_stories tests.test_story_sparse_states
```

Pour comparer les prochains essais : créer une **nouvelle** histoire avec la même intention, durée, nombre de clips et débit ; essayer Qwen pour les deux rôles, puis changer uniquement le rédacteur pour Gemma. Juger d’abord les moments conservés, la qualité des réparties, les paroles effectivement audibles et les réactions visibles. Un gain de durée ou de qualité n’est pas encore mesuré.
