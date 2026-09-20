# Échec de conception : règles fournies en texte

## Diagnostic sur les deux runs réelles

Le 20 septembre 2026, les deux dernières conceptions ont terminé leur génération puis échoué à l’application de la réponse : `world_rules doit contenir exactement : id rule limits.`

| Projet | Appel | Brouillon |
|---|---|---|
| `story-d4e196f9bc014e9f84e5cf62c5f40d7e` | `llm-2a15b266a8444dbbbbbb34d5d0a21089` | La Flaque, 6 524 caractères, trois règles en texte |
| `story-35b5ac1255cd44749d064308680d30d9` | `llm-d5f3cf0a13e842e8b43c6e6e08ccb69b` | Le prix doux, 6 577 caractères, deux règles en texte |

Les deux appels utilisent Qwen3.8-27B local, opération `story.long.compose@2.0.0`, avec `finish_reason=stop`. Les objets JSON sont complets. Le défaut vient du contrat fourni au modèle : pour éviter de forcer règles et secrets, le dernier changement avait laissé ces tableaux vides dans l’exemple, sans décrire la structure de leurs éléments facultatifs. Le validateur attendait pourtant des objets stricts. Le modèle a produit des listes de phrases, format raisonnable au vu des informations reçues, que le backend a rejetées.

Un second défaut est visible dans La Flaque : la réponse dit avoir conservé les options social/dialogue/reversal « du contrat », alors que les trois préférences de l’auteur étaient `auto`. Ces valeurs concrètes d’exemple imposaient un biais involontaire au choix automatique.

## Correctif

- Les requêtes d’arc décrivent maintenant `outline_entry_contracts` pour les règles et les secrets, même lorsque leurs listes sont vides. Le prompt distingue un schéma d’élément de l’obligation d’en inventer un.
- Une règle reçue en phrase est conservée intégralement dans `rule`, avec un identifiant déterministe sans collision. Ses limites non fournies restent `null` : cela signifie « non précisées », jamais « illimitées ». L’édition de l’arc pourra les examiner. Le contrôle narratif reste distinct de cette récupération de format.
- Sur un arc déjà écrit, une règle en texte ne récupère un ancien identifiant et ses limites que par correspondance unique avec le texte existant. Une révision ambiguë est refusée ; aucun rattachement par position ni abandon silencieux des limites existantes.
- Les secrets ne sont pas reconstruits depuis une phrase : le savoir des personnages et le moment de révélation ne peuvent pas être devinés. Les objets incomplets ou avec des champs inconnus et les mauvaises dépendances restent rejetés.
- Le brut demeure inchangé. La normalisation est enregistrée dans le job et affichée. La revalidation remet le parcours en pause avec un message de récupération ; elle ne lance aucun LLM et ne considère pas l’arc comme relu.
- Les valeurs Auto ne sont plus remplacées par social/dialogue/reversal dans l’exemple. Des emplacements `CHOISIR_*` demandent explicitement une sélection parmi les valeurs autorisées ; les préférences explicites restent inscrites telles quelles.

Le JavaScript Histoires passe à `20260920.4` pour afficher les limites non précisées et les normalisations. Le correctif Python nécessite un redémarrage du serveur par l’utilisateur ; aucun service n’a été redémarré pendant l’intervention.

## Récupération

Après redémarrage et `Ctrl+F5`, ouvrir chacun des deux projets en échec et cliquer **Revalider la réponse reçue**. Cela réutilise la réponse déjà payée en temps de génération. Puis **Continuer le parcours** effectue l’édition/relecture de l’arc. Cette étape peut encore relever des problèmes narratifs, par exemple la causalité d’une goutte qui fend une vitre ou une chute dépendant d’une inscription lisible.

Ne pas recréer une histoire pour cette erreur de format. Les projets réels et leurs brouillons n’ont pas été modifiés pendant le correctif.

## Vérifications

Deux fixtures reproduisent exactement les brouillons enregistrés dans `tests/fixtures/long_stories`. `tests/test_long_story_response_contracts.py` couvre leur revalidation sans gateway, la préservation du brut, les limites inconnues, les identifiants, le refus de données ambiguës ou incohérentes, la description des éléments facultatifs et l’absence de préférence automatique imposée par l’exemple.

Syntaxe Python/JavaScript, JSON des fixtures, identité des brouillons et `git diff --check` vérifiés statiquement. **Tests non exécutés : l’utilisateur a explicitement répondu « Non, je les lancerai » à la proposition de les lancer localement.** Aucun appel LLM ni rendu n’a été lancé. Les tests de rejeu constituent une vérification à effectuer, pas une réussite déjà constatée.

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_long_story_response_contracts tests.test_long_stories tests.test_story_workflow
```

Commande à lancer depuis `D:\Code\panelforge-krea2-flux`.
