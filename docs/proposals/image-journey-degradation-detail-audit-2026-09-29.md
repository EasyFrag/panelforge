# Parcours d’images autonome — diagnostic du 29 septembre 2026

## Périmètre

Demande utilisateur : examiner la dégradation progressive du parcours lancé, puis s’aligner avant correction. Précision reçue : **détails, textures et couleurs**. Aucun changement applicatif, réglage de rendu, appel LLM, génération, test ou redémarrage effectué pendant cet audit. Les planches sont des assemblages locaux d’images existantes, destinés à la comparaison.

## Parcours examiné

- Journal : `D:/Code/panelforge/workspace/image_journeys/journey-323a50895e5f5c72bf755375b6070023.json`.
- Intention : « Ajouter une porte dans le bois, des équipements de bois (deck ou autre) un paneau solaire ».
- Créé le 29 septembre à 09:28, suspendu vers 09:33, heure de Paris. Quatre images produites sur cinq demandées : porte, extension du deck, panneau solaire, lanterne.
- Les deux rôles utilisent `local::unsloth/gemma-4-31B-it-qat-GGUF`.
- Original : `asset-bf2cf354ecc0464bb427772beeeddd7e`, 1120 × 1984, PNG.
- Résultats successifs : `asset-d4ee438c91b349e4a76c0bdeb091ecf7`, `asset-6f66726c62cf46b0bad5148d31e33ae7`, `asset-097d1eb87e91464e8ebd9cd0da0aa755`, `asset-ef1fc02d284f4f7381545ddb5539cf92` ; chacun mesure 2016 × 3584.

## Constat visuel

Les cinq images ont été comparées ensemble, puis un même secteur du tronc a été comparé au départ, après la porte et après la lanterne. Les agrandissements sont ramenés à une échelle commune ; ils ne mesurent pas une perte de résolution native.

La dérive est visible dès la première édition, puis s’accentue : les fissures fines et irrégularités de l’écorce sont remplacées par des reliefs plus simples et réguliers ; les contours et contrastes deviennent plus durs ; la palette prend des accents plus vifs et le rendu paraît plus artificiel. La dernière écorce a un aspect presque sculpté. Les ajouts demandés sont présents et le cadrage global reste proche, ce qui ne suffit pas à préserver la qualité du départ.

Planches : `D:/Code/panelforge/.agent/diagnostics/image-journey-degradation-20260929/sequence.jpg` et `bark-comparison.png`.

## Mécanismes vérifiés

1. **Chaîne de rééditions intégrales.** Chaque projet MiniMax enfant reçoit seulement la dernière image produite comme source. Ses références supplémentaires sont vides et aucun masque/guide n’est fourni. L’original n’est pas transmis au moteur après la première étape. Les altérations d’une édition deviennent donc la matière de la suivante.
2. **Conditionnement visuel réduit.** Le workflow sauvegardé `minimax.h3_still_edit@1.0.0` réduit la référence à 1 mégapixel, avec `nearest-exact`, puis produit 2016 × 3584, soit environ 7,2 mégapixels. Le scheduler utilise 18 steps et `denoise=1`. Il s’agit d’un goulot d’étranglement possible pour les détails, pas d’une baisse des dimensions des sorties. La seule lecture du graphe ne permet pas d’attribuer une part précise du défaut à chaque réglage ni de garantir qu’augmenter la résolution de référence le résoudrait.
3. **Préservation principalement textuelle.** Les prompts demandent de conserver le tronc, la forêt et les éléments précédents. Ils ne préservent pas les pixels hors de la zone à modifier. Le prompt ne demande pas explicitement cette stylisation ; on ne peut pas attribuer la dérive au seul rédacteur de prompt.
4. **Relecture trop centrée sur l’avancement.** Le rôle Progression voit avant/après et, à partir de la deuxième relecture, également l’original. Le problème n’est donc pas une absence totale de référence initiale côté LLM. En revanche, le contrat met l’accent sur les ajouts, le cadrage et l’identité du lieu ; aucune appréciation distincte des textures, nuances, contrastes ou dérive accumulée n’est exigée. Les trois relectures acceptées déclarent les éléments « parfaitement préservés » sans signaler le défaut visible.
5. **Réglages annexes.** Finition `raw`, sorties brutes conservées, pas de passage DLSS dans ce parcours. Chaque enfant MiniMax reçoit une seed différente malgré `reuse_seed=true`, qui ne porte que sur son propre projet. Ce fait ne prouve pas que fixer une seed corrigerait la dérive.

Conclusion étayée : la réédition répétée réinterprète aussi les textures censées rester stables, et la supervision actuelle laisse passer cette dérive. L’importance respective du conditionnement à 1 MP, de l’interpolation et du comportement du moteur reste à qualifier par des essais ultérieurement autorisés.

## Arrêt distinct après la quatrième image

La trace durable `llm-001e6edf21ff4bc786d541f22c19693d` contient une réponse JSON complète, terminée normalement (`finish_reason=stop`). Elle juge le résultat utilisable mais renvoie `next_action=null` alors qu’une image reste à produire. Le contrat exige une transformation suivante et rejette cette décision.

Ensuite, le gestionnaire d’erreur appelle `_call_update(identity, call["id"], ..., call_id=call_id)` alors que son deuxième paramètre s’appelle lui-même `call_id`. Cette collision masque l’erreur de validation par `ImageJourneyService._call_update() got multiple values for argument 'call_id'`. La quatrième relecture reste marquée en cours avec une copie partielle du texte, bien que la trace LLM complète existe. Ce n’est pas une preuve de troncature du modèle et ce n’est pas la cause de la dégradation des images.

Repères code dans `D:/Code/panelforge-krea2-flux` : `application/image_journeys.py:377` et `:382`, `domain/image_journeys.py:106`, sous `src/panelforge/`.

## Direction proposée, non implémentée

- Conserver les deux rôles et la même interface compacte.
- Séparer explicitement la réussite des travaux et la conservation de l’apparence lors de la relecture, en comparant aussi au départ. Un rendu peut avoir ajouté le bon objet tout en dégradant l’image.
- Étudier la transmission permanente de deux références au moteur et au prompter : l’état courant pour les travaux acquis, l’original pour l’apparence et la composition. Le moteur possède déjà un mécanisme de références supplémentaires. Cela reste une hypothèse à qualifier, avec un risque de réintroduire l’état initial à la place de travaux acquis.
- Examiner le prétraitement de référence à 1 MP et son interpolation dans un essai isolé du parcours ; ne pas changer silencieusement le workflow MiniMax partagé ou promettre une amélioration avec davantage de steps.
- Si la dérive reste forte, envisager une édition localisée avec conservation des régions non modifiées. Cela demande un mécanisme de masque/composition adapté ; ajouter seulement une phrase de préservation n’en donne pas la garantie.
- Conserver le comportement déjà aligné pour un résultat trop similaire : poursuivre en adaptant la demande, rejeu futur. Une dérive de qualité marquée est un problème distinct ; proposition de suspension reprenable plutôt que propagation silencieuse.
- Corriger séparément la collision de journalisation et clarifier le traitement d’une décision prématurément finale. Les trois jalons étaient réalisés après trois images ; la quatrième ajoute une lanterne au titre des finitions. Ne pas changer implicitement le contrat « N nouvelles images » en « au plus N ».

Prochain travail : aligner la correction avec l’utilisateur, puis implémenter uniquement le périmètre retenu. La qualification par génération réelle reste à faire avec son autorisation.
