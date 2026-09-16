# Histoires — trois réponses rejetées à cause de virgules finales

Projet `story-4ae5c19da61a415196ec8d3cf3891fba`, titre « Tromperie », révision
éditoriale r3. Trois appels de propositions :

- `llm-e20cb60712b04d27a08e5ac3fd50164a`, 17:56 UTC, Gemma 4 Hauhau.
- `llm-b30d22edd49a492898db9cac91d4159e`, 17:58 UTC, Gemma 4 Hauhau.
- `llm-653f1565145f4d11bffaf9ce69720e82`, 17:59 UTC, Gemma 4 standard QAT.

Tous terminent normalement (`finish_reason=stop`). Chaque réponse contient trois
virgules en trop, après le champ `ending` et avant la fermeture de chaque concept.
Le premier rejet apparaît ligne 13. La lecture des copies, après retrait de ces
seules virgules et de l'éventuelle clôture Markdown, donne trois propositions
complètes dans chacun des trois appels. Ce n'est pas une troncature.

Le décodeur Histoires tente d'abord `json.loads`, puis une normalisation limitée
aux virgules finales de conteneurs. Il suit les chaînes et leurs échappements pour
laisser intacts les dialogues contenant par exemple `,}` ou `,]`. Les valeurs
manquantes, doubles virgules, objets incomplets, clés mal citées et contenu après
le document restent rejetés. Le contrat métier est ensuite validé comme avant.

Pas de dépendance supplémentaire, de modification du décodeur H3/REF2V, de
nouvelle consigne ou d'appel LLM de réparation. Les traces et brouillons originaux
restent disponibles ; aucun ancien résultat n'est appliqué automatiquement.

Régressions préparées dans `tests.test_stories` : acceptation sans appel en plus,
préservation des caractères dans les chaînes, refus des autres corruptions.
AST et contrôles statiques effectués ; tests applicatifs et générations non lancés.
Le backend doit être redémarré pour charger ce correctif.

Autre observation : le brief du projet est vide. Son titre « Tromperie » n'était
pas une intention envoyée au LLM ; la diversité de sujets dans les propositions
ne constitue donc pas ici un non-respect d'un brief de tromperie.
