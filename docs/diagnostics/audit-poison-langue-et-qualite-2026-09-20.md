# La Goutte de Poison : langue, scénario et raisonnement enregistré

Audit demandé le 20 septembre 2026. Aucun code, scénario enregistré, modèle ou service modifié ; aucun test ou appel de génération lancé.

## Périmètre

Projet `story-5915c5e742274dada03708420fb3c261`, titre du projet **La Goutte de Poison**, titre du scénario **La Boisson de la Confiance**, version de stockage 494, révision narrative 6. Fabrication `episode-165c6e56266c46aaae08063e1d0760b4`, langue `French`.

Examen des entrées et sorties des sept appels narratifs, des versions avant/après correction, du contrat et des intentions transférées en Fabrication. Pour le raisonnement enregistré : lecture intégrale des deux traces courtes du rédacteur, examen des débuts, fins et passages pertinents des cinq longues traces Qwen, avec comptages sur les textes complets. Il ne s’agit pas d’un accès garanti au mécanisme interne du modèle : on examine le texte de raisonnement exposé par le serveur, ses répétitions et sa relation aux résultats.

Les entrées, sorties et mesures sélectionnées sont conservées dans [evidence.json](D:/Code/panelforge/workspace/experiments/audit-poison-francais-2026-09-20/evidence.json). Les textes de raisonnement originaux restent dans les traces `workspace/video_llm_traces/calls/`, identifiées ci-dessous. Cet audit ne mesure pas la fidélité audiovisuelle des rendus.

## Pourquoi une phrase est restée en anglais

Le sélecteur est bien `French`. Le brief fourni précédemment par l’assistant impose cependant une « courte réplique en anglais » et la citation **Once she drinks this, we can be together.**, puis autorise à nouveau quelques paroles en anglais. Cette contradiction a été introduite par l’association du brief proposé et du réglage français ; elle n’est pas un symptôme de perte aléatoire de la langue par le rédacteur.

Dans sa trace de développement, Gemma identifie le conflit et choisit de conserver la citation particulière. Sa réponse finale annonce également qu’il l’a intégrée. À la correction, il fait le même choix en parlant d’une exception. Le contrat demeure pourtant inchangé : aucune exception structurée n’y est ajoutée. Le résultat mélange cinq répliques françaises et cette citation anglaise.

La politique d’écriture demande le français pour les nouvelles répliques, tandis que le brief et les consignes d’adaptation demandent de préserver les éléments fournis. Les instructions de révision protègent aussi les dialogues validés. Cette hiérarchie insuffisamment claire occupe longuement Qwen. Le fait que son raisonnement enregistré soit souvent en anglais n’implique pas à lui seul que la vidéo doive parler anglais ; le problème est le contenu réellement écrit dans `dialogue.text`.

Pour une version française, il faut conserver Français dans le sélecteur et employer un brief entièrement français, sans exception anglaise ni citation anglaise à préserver. Remplacement proposé : **« Quand elle aura bu ça, on pourra enfin être ensemble. »** Le [brief français complet](../essai-poison-francais-2026-09-20.md) supprime les deux demandes d’anglais.

## Valeur des appels et coût constaté

| Étape | Modèle | Durée | Plafond | Raisonnement / JSON, en caractères |
|---|---|---:|---:|---:|
| Conception | Qwen | 179,178 s | 24 000 | 51 190 / 8 182 |
| Édition-relecture de l’arc | Qwen | 111,404 s | 24 000 | 31 909 / 8 442 |
| Développement | Gemma | 97,311 s | 24 000 | 4 289 / 8 923 |
| Relecture tronquée | Qwen | 167,779 s | 8 000 | 32 819 / 0 |
| Relecture relancée | Qwen | 91,222 s | 80 000 | 36 020 / 2 738 |
| Correction du scénario | Gemma | 93,963 s | 80 000 | 3 355 / 9 270 |
| Relecture après correction | Qwen | 142,146 s | 80 000 | 47 555 / 3 073 |

Total : **883,003 secondes, soit 14 min 43 s de temps d’appels cumulé**, hors pauses entre les étapes. Six appels ont abouti, un a été tronqué. Les compteurs de tokens réellement consommés sont absents des traces ; les tailles de texte ci-dessus ne sont donc pas des mesures de tokens ou de coût financier.

Qwen est la variante `HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF`, Gemma la variante `HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP`. Il ne faut pas les confondre avec les variantes Unsloth employées dans L’eau qu’on donne.

La hausse à 80 000 est effectivement utilisée par les trois derniers appels, terminés avec `finish_reason=stop`. Elle a permis de dépasser la limite antérieure ; elle ne signifie pas qu’ils ont consommé 80 000 tokens et ne démontre pas à elle seule une amélioration éditoriale.

## Qualité du raisonnement enregistré

**La conception identifie correctement la cible.** Les responsabilités, la confiance de Rose et la réussite finale du complot restent en place. Les gouttes ne déclenchent plus une mythologie de fusion ou d’évaporation. C’est un progrès de fidélité par rapport aux histoires précédentes, sans invalider leur qualité propre.

**Le raisonnement Qwen est disproportionné pour certaines décisions.** Il revient sur la priorité entre citation anglaise et langue française, reformule ses futures remarques, puis revérifie plusieurs fois le format JSON. Dans la trace tronquée, des propositions censées être françaises réintroduisent un mot anglais, provoquant de nouvelles tentatives de reformulation. Les passages examinés montrent donc un coût de résolution d’instructions et des répétitions, pas seulement de l’analyse dramatique.

À titre de repère, 19 des 46 paragraphes de la relecture tronquée mentionnent English, French ou language ; ces paragraphes peuvent aussi traiter d’autres sujets. Ce comptage ne mesure pas une fraction exacte du temps ou des tokens imputable au conflit. La cause quantifiable de l’arrêt reste `max_tokens=8000` avec `finish_reason=length`.

**Gemma développe efficacement, mais accepte une solution non formalisée.** Ses deux traces courtes organisent les six scènes et les modifications utiles. La correction améliore réellement le baiser caché, la feinte d’Azur et l’ellipse des secours. Elle conserve pourtant la citation anglaise comme exception de sa propre initiative, sans lever explicitement la contradiction du projet.

**L’édition de l’arc introduit une régression de langue.** Le contrat de la première conception est français. Après `edit_outline`, il contient notamment « Rose wants to soigner Azur and preserve their foyer ». Cela figure dans la réponse JSON brute du modèle et dans le document sauvegardé, pas seulement dans son raisonnement. Le même appel se déclare conforme et ne laisse aucune remarque. La fonction de relecture ne garantit donc pas une amélioration nette de chaque champ.

## Qualité et stabilité des relectures

La relecture relancée après la troncature classe le conflit de langue en **blocking**. Elle propose une traduction ou une exception explicite dans le contrat. Gemma conserve l’anglais, ne change pas le contrat, et annonce une exception dans sa réponse explicative. La relecture suivante considère alors cette même phrase comme imposée par le brief et ne la bloque plus.

Cette oscillation est observable entre versions. Les requêtes de relecture reçoivent le brief, l’arc et le scénario, mais ne reçoivent pas une liste explicite des anciens problèmes bloquants à confirmer comme résolus. Elles ne réalisent donc pas une vérification ciblée de clôture du défaut précédent. Cela peut contribuer au changement d’arbitrage ; les traces ne permettent pas d’en quantifier l’effet indépendamment de la variabilité du modèle.

Certaines remarques restantes ont une valeur limitée. La dernière relecture réclame que Rose boive dans `action`, alors que `opening_state` dit déjà qu’elle boit d’un trait et que cette phrase est transmise au générateur dans « Situation initiale ». Il peut être utile de mieux articuler ce geste, mais son absence de la seule propriété `action` ne prouve pas son absence de la scène. De même, une ellipse hôpital/maison est normale dans ce format : montrer tout le trajet n’est pas nécessaire pour comprendre les soins.

## Qualité du scénario retenu

Le récit remplit désormais la cible : liaison cachée, soin sincère, remise du flacon, faux geste attentionné, effondrement et bonheur final des complices. La soupe offerte par Rose puis la boisson offerte par Azur créent un écho visuel utile. La réplique finale « Enfin. » renforce la cruauté. La médecin reste complice et le mari responsable.

Les points concrets à améliorer sont les suivants :

1. **Préparation du verre hors de la vue de Rose.** La scène 4 annonce son retour avant qu’Azur verse le contenu du flacon. Rien ne précise qu’elle ne voit pas le geste. Cette ambiguïté peut faire perdre la tromperie à l’image. Il faut montrer la préparation pendant son absence, puis son entrée et l’offre du verre. Aucune des deux relectures réussies n’a retenu ce point dans ses remarques finales.
2. **Absence de Rose suffisamment claire.** « A quitté la pièce pour un instant » laisse Rubis entrer dans une maison où Rose se trouve encore tout près. Une sortie du domicile, suivie du départ de Rubis avant le retour de Rose, suffit à rendre l’intimité du pacte plus crédible.
3. **Cruauté et culpabilité d’Azur.** « Gratitude teintée de culpabilité » atténue légèrement la froideur de la référence. Ce choix ne détruit pas le récit ; pour une adaptation plus proche, rendre sa gratitude manifestement feinte et réserver la tendresse sincère à Rose.
4. **Charge du clip de l’effondrement.** Boire, commenter, lâcher le verre, tomber et montrer l’évacuation restent denses pour dix secondes. L’ellipse ajoutée est une amélioration ; un aperçu des secours après la chute peut suffire. Ce jugement reste une estimation textuelle.

Le diagnostic est donc : **bonne fidélité dramatique, contrôle éditorial irrégulier, dépense de raisonnement trop élevée sur un conflit évitable**. Un seul essai ne permet pas de classer globalement les variantes de modèles ni d’affirmer qu’un prompt français résoudra toutes leurs difficultés.

## Suite proposée, sans code

Essayer le brief français cohérent avec les mêmes modèles et les mêmes budgets pour isoler l’effet des instructions. Conserver 80 000 comme plafond disponible. L’objectif de l’essai est un scénario français, un contrat français et des relectures stables sur les responsabilités et les raccords ; le volume du raisonnement n’est pas un critère de qualité en soi.

Les réglages et le texte complet sont dans [Essai français](../essai-poison-francais-2026-09-20.md). Aucune nouvelle génération n’a été déclenchée pendant cet audit.
