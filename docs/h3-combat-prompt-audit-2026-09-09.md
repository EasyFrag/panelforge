# Prompts de combat H3 — audit du 9 septembre 2026

## Périmètre et conclusion

Priorités explicites de l’utilisateur : **combat P0**, **analyse vidéo/images vers prompt P1**, recherche de seeds mise de côté. Cette passe documente les sources et une direction produit ; elle n’implémente pas de nouvelle recette et ne lance aucun test, appel LLM ou rendu.

La piste la plus pertinente est une préparation de chorégraphie : initiative, attaque, réponse adverse, conséquence visible et situation qui permet la suite. Les exemples donnent une matière utile, mais leur longueur, leurs effets et leurs coupes ne constituent pas des garanties de qualité. Évaluation des textes et des recommandations d’auteurs uniquement ; pas de comparaison des vidéos générées ni de mesure d’efficacité sur Bucket.

## Sources consultées et limites

- Fiches Civitai demandées : [Combat Base](https://civitai.red/models/2853878/minimax-h3-combat-base-fight-motion-impact-drama-booster), [Weapon Combat](https://civitai.red/models/2904053/weapon-combat-or-high-speed-weapon-choreography-or-minimax-h3). HTML indisponible dans l’outil web ; descriptions et métadonnées lues via les API publiques `/api/v1/models/2853878` et `/api/v1/models/2904053`.
- Fiches de l’auteur sur Hugging Face : [Combat Base V2](https://huggingface.co/JOKER141/MiniMax-H3-Combat-Base-V2), [Weapon Combat V1](https://huggingface.co/JOKER141/MiniMax-H3-Weapon-Combat-LoRA). Elles apportent notamment les indications de sampler et de compatibilité entre LoRA.
- Guides officiels MiniMax : [Base, I2VA, FL2VA et L2VA](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md), [Full Reference](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md).
- Piste complémentaire : [Wushu Action](https://huggingface.co/Jojocodex/wushu-action-v7-minimax-h3-fl2va-ref2va-lora), utile surtout pour son vocabulaire et ses exemples d’enchaînements.

Les métadonnées Civitai recensent `Action Director.txt`, `Director of “One Against Many”.txt` et `H3_Weapon_Combat_Choreography_Director__v1.1.txt`. Le téléchargement public de ces trois textes a répondu HTTP 403 : **contenu non lu**, aucune conclusion attribuée à leurs instructions internes. Les exemples collés par l’utilisateur ont bien été lus. Aucune instruction de document externe n’a été exécutée.

## Modèles et réglages : ce qui est documenté

| Ressource | Apport annoncé par l’auteur | Conséquence pour nos essais futurs |
| --- | --- | --- |
| Combat Base V2, version Civitai `3246572`, `H3_Combat_V2.safetensors` | Continuité des actions, réactions durables, perte d’équilibre et interactions avec le décor. | Candidat pour les échanges corporels et la progression dramatique. La fiche V2 propose de commencer sans déclencheur ; `prfight2` augmente l’intensité, `prfin1` accompagne les impacts finaux. |
| Weapon Combat V1, version `3283995`, `Bunny_weapon_combatV1.safetensors` | Continuité des armes, contacts/parades, dégagement des armes et déplacements. | Candidat le plus directement lié aux duels fournis. Déclencheur confirmé : `BUNNY`. La fiche Civitai indique une force initiale de 0,7–0,9 ; à 1,0, elle signale davantage de rotations du corps possibles. |
| Wushu Action, dépôt v7 | Techniques nommées, identités séparées de la description des plans, enchaînements et sons. | Piste de vocabulaire et de spécialisation ultérieure ; pas de proposition de l’ajouter au premier patch. L’auteur signale lui-même du flou à faible nombre de pas. |

Ces apports sont **des affirmations d’auteurs**, pas un classement mesuré. La description Civitai Combat Base mélange le texte V2 avec d’anciennes consignes V1 (`prfight1`, `prslow1`) ; les métadonnées V2 et sa fiche dédiée doivent primer pour identifier la bonne version. L’ancienne réserve de tests complets limités à FL2VA reste aussi présente, alors que le dépôt contient maintenant des workflows FL2VA et REF2VA : ne pas en déduire une qualité identique démontrée sur chaque mode.

Weapon Combat recommande une utilisation indépendante et déconseille l’empilement avec Combat Base V2, Motion Continuity Fix ou d’autres LoRA de mouvement forts. La recommandation ne signifie pas retirer automatiquement le Turbo technique. Notre preset BUNNY possède un emplacement créatif avec deux applications séparées, actuellement Motion Repair 0,6/0,2 : pour comparer Weapon Combat, le sélectionner à cet emplacement plutôt qu’ajouter une autre couche de mouvement. La force générale indiquée sur Civitai ne définit pas à elle seule les deux forces optimales de notre pipeline. [Compatibilité de l’auteur](https://huggingface.co/JOKER141/MiniMax-H3-Weapon-Combat-LoRA).

Pour Combat Base V2, l’auteur conseille `res_multistep/simple` ou `euler/beta` lorsque l’image manque de netteté. Notre BUNNY utilise un calendrier T8 à deux passes et `dual_clock_euler/native_flow` : ces recommandations ne se transposent pas par un simple remplacement de champ. Le `Steps: 10` de l’exemple court est également une indication de rendu, pas une phrase à envoyer au modèle ni un remplacement automatique du profil 9/4/5. [Recommandations de sampler](https://huggingface.co/JOKER141/MiniMax-H3-Combat-Base-V2), [contrat local BUNNY](bunny-h3-render.md).

## Lecture des exemples utilisateur

Les neuf pièces jointes contiennent **sept textes distincts**, après comparaison de leur contenu : E3 = E2 et E8 = E1. Les longueurs ci-dessous sont des comptes approximatifs de mots séparés par des espaces, pas des tokens LLM.

| Exemple, dans l’ordre reçu | Volume et durée annoncée | À retenir | À adapter |
| --- | --- | --- | --- |
| E1 / E8 : Guan Yu à cheval | 1 378 mots, 15 s | Arme lourde, inertie, suivi latéral, conséquences sur boucliers et sol. | Quatre plans très chargés ; fin debout et poussière aux bottes sans descente de cheval décrite ; titre publicitaire final à ne pas hériter. |
| E2 / E3 : épée/bouclier contre épée longue | 827 mots, 10 s | Adversaires distincts, changement d’initiative, progression portail → brasero → pilier. | Plusieurs réponses par seconde ; ouverture noire et final incandescent incompatibles avec certaines frames imposées. |
| E4 : sabres énergétiques | 1 004 mots, 10 s | Couleur et propriétaire des armes stables, gestes reliés entre eux. | Nombreuses rotations, inversions et contacts, caméra changeant constamment de côté ; surcharge probable, à vérifier en rendu. |
| E5 : fin de duel dans la forge | 953 mots, 10 s | Progression d’état et transition motivée par l’action. | Séquence de conclusion spécifique, pas un modèle générique de duel ; changement de point de vue à demander explicitement. |
| E6 : Zhao Zilong et sa lance | 1 142 mots, 10 s | Trajectoire latérale lisible et effets qui suivent celle de l’arme. | Foule, vitesse extrême et attaques multiples ; énergie verte seulement si voulue. |
| E7 : hache contre épée longue | 825 mots, 10 s | Contraste poids/vitesse, parades et déplacement autour d’éléments du décor. | Chaînes, fumée, débris et coup final ne doivent pas remplacer la lecture des contacts. |
| E9 : guerrière fantastique au tachi | 927 mots, 15 s | Identité conservée et montée dramatique claire. | Six plans, ralentis, immobilisations, dashs, explosions et caméra parfois ambiguë ; look explicitement 3D CG, pas une recette de réalisme photographique. |

Les duels E2/E7 sont les meilleurs **modèles de rédaction** pour commencer selon mon analyse, pas les meilleurs rendus établis. Ils rendent la relation entre adversaires plus explicite que les scènes de foule.

## Principes à reprendre

1. **Nommer une fois les combattants et leurs armes**, puis conserver des identifiants courts. Une référence de décor ou de style n’est pas un troisième adversaire.
2. **Raconter une chaîne causale observable** : geste engagé → parade, esquive ou contact → réaction et déplacement → possibilité de riposte. Prévoir le dégagement des armes et la reprise d’appui ; éviter le retour systématique à la même pose entre deux coups.
3. **Faire évoluer le rapport de force**. Une poussée peut faire reculer, un déséquilibre ouvrir une défense ; la prochaine action doit partir de cette nouvelle situation.
4. **Garder une géographie simple** : quelques repères, une zone de contact visible, un déplacement compréhensible. Pour une foule, entrées décalées et groupes successifs paraissent un meilleur premier objectif qu’une mêlée simultanée.
5. **Utiliser caméra et son pour rendre l’action lisible** : une trajectoire d’arme visible, puis éventuellement une coupe sur l’action. Le son du contact ne suffit pas à montrer qu’il a eu lieu.
6. **Ajuster la densité à la durée**. Deux ou trois grands moments peuvent être une heuristique de départ pour un court essai ; ce n’est ni une limite H3 démontrée ni un quota rigide à valider par regex. Chaque moment peut contenir une combinaison cohérente.

L’exemple court de l’héroïne face au titan fournit déjà un bon arc : elle évite la pression, subit un revers, reprend l’avantage et conclut. Il laisse toutefois à décider la réponse du titan, les positions et la transition vers l’attaque aérienne. Il est donc intéressant comme **intention donnée au LLM**. Son efficacité comme prompt de rendu direct n’est pas établie ici.

Pour le dialogue, Combat Base V2 recommande de terminer l’action avant de placer une réplique dans le même plan. Cette piste est compatible avec notre liberté vocale : répartir les paroles dans les respirations de l’échange, sans imposer de nouvelles phrases ni interdire des répliques expressément demandées. Les statistiques internes de netteté et de mouvement affichées par l’auteur ne sont pas traitées comme une preuve indépendante. [Observation de l’auteur](https://huggingface.co/JOKER141/MiniMax-H3-Combat-Base-V2).

## Ce qu’il faut préserver dans localQ

Le guide officiel Base emploie **trois rubriques principales** avec un en-tête adapté aux frames, tandis que le guide Full Reference en définit **six**. La forme des exemples ne doit donc pas devenir un gabarit universel. Reprendre leur chorégraphie et produire le format du mode sélectionné ; conserver les en-têtes compilés et les rôles des images. Les neuf exemples n’établissent pas qu’un copier-coller en six rubriques améliore FL2VA. [Guide Base](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md), [guide Reference](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md).

Même séparation pour les plans : une chorégraphie en plusieurs moments peut rester un plan continu. Le mode Combat ne doit pas activer implicitement le multi-plan, une caméra agitée, du glow, du ralenti ou de la musique. Les conventions temporelles mélangées des exemples (`03:50`, `06.40`) sont à convertir dans notre représentation canonique, sans les traiter comme une nouvelle syntaxe.

Direction produit proposée, **à discuter avant implémentation** :

- Un choix facultatif **Combat**, avec intention libre et conservation des axes caméra/dialogue existants. Éviter un formulaire qui exige tous les coups un par un.
- Un bloc versionné de principes de chorégraphie, partagé par les parcours. En trois étapes, le Brief choisit l’arc et le Plan le développe ; en deux, le Plan fait directement ces choix ; en une, le rédacteur les réalise dans son appel unique. Ne pas ajouter de Plan caché ni copier les neuf exemples dans chaque prompt système.
- Même chorégraphie rendue dans les formats H3/REF2V existants, mono ou multi-plan selon le choix utilisateur. La révision post-prompt doit conserver les mêmes principes.
- Choix du LoRA de rendu indépendant. Déclencheur associé à son fichier/version effectifs ; le mot `BUNNY` n’est pas un déclencheur universel pour toute la recette de rendu BUNNY.
- Versions actuelles conservées pour comparaison. Aucun changement des défauts seed, MP, Turbo ou des workflows dans cette passe.

Lorsque l’utilisateur souhaitera expérimenter : partir d’un duel simple et d’une même scène, garder les paramètres enregistrés, observer d’abord l’amélioration du texte, puis changer un seul LoRA à la fois. Critères utiles : identités/armes, réalité des contacts, réactions, continuité spatiale, actions omises et netteté. Ni un taux de réussite ni un gain de latence ne peuvent être annoncés avant ces observations. La recherche automatisée de seeds reste hors périmètre.

## Discussion d’intégration et d’isolation — 10 septembre 2026

L’utilisateur demande une séparation stricte : modifier Combat ne doit pas changer Classique. Il souhaite aussi éviter que Combat perde les améliorations générales au fil du temps. **Proposition ci-dessous, pas encore une instruction d’implémentation.**

Prévoir deux familles de recettes de préparation, **Classique** et **Combat**, sélectionnées dans le même atelier ; les parcours 1/2/3 étapes restent accessibles dans chaque famille. Le choix oriente les consignes de préparation, pas une nouvelle copie de l’application ni nécessairement un autre graphe ComfyUI. Mode d’entrée H3/REF2V et recette de rendu restent des choix distincts. Un preset de rendu combat pourrait être conseillé séparément ; aucun changement automatique du LoRA, des MP, du seed ou du Turbo n’est décidé ici.

Ne pas faire hériter Combat de la dernière recette Classique. Les deux familles peuvent dépendre de briques communes neutres : formats H3/REF2V, références, syntaxe caméra, transport des images, conservation des paroles et orchestration. Chaque famille possède ses décisions créatives, limites de densité, exemples et éventuelles validations métier. Une règle de chorégraphie n’entre pas dans le socle commun uniquement pour faciliter son implémentation ; ne pas assouplir un validateur global pour faire passer un candidat combat.

Le registre existant `src/panelforge/infrastructure/prompt_cookbooks.py` sait déjà résoudre des blocs et templates à versions numériques exactes, ainsi que refuser les dépendances cycliques. Les recettes actuelles utilisent ces assemblages. Certains templates historiques mélangent cependant décisions créatives et règles de format : leur réutilisation intégrale doit être examinée, pas supposée neutre. Extraire seulement les briques nécessaires dans de nouveaux fichiers/versionnements sans modifier les textes des recettes historiques.

Politique d’évolution proposée :

- Modification propre à Combat : nouvelle recette Combat, Classique reste sur ses dépendances et son comportement existants.
- Modification propre à Classique : nouvelle recette Classique, sans propagation implicite vers Combat.
- Amélioration générale identifiée dans l’un des modes : nouvelle version du bloc commun ; examiner les deux familles dans le même patch et publier leurs nouvelles recettes compatibles. Si l’une ne peut pas adopter le changement, documenter précisément l’écart à rattraper. Pas de dépendance à `latest` et pas de réécriture d’une ancienne version en place.
- Interface, file, stockage, DLSS et corrections techniques génériques restent dans l’application commune et peuvent bénéficier aux deux familles. L’isolation des recettes ne signifie pas deux applications exécutées séparément.

Chaque atelier conserve sa famille, ses versions et son contexte, y compris pour les révisions après rendu. Une recette Combat ne peut pas devenir subrepticement une révision Classique au tour suivant ; un changement de famille devrait ouvrir une nouvelle exploration afin d’éviter d’hériter d’une conversation influencée par l’autre famille. Les anciens ateliers restent inchangés.

À préparer dans le futur patch : vérifications hors ligne des prompts effectivement assemblés, du routage préparation/révision et des références de versions, avec garantie ciblée qu’un changement des fichiers Combat ne change pas le prompt Classique à entrées égales. Ces contrôles n’établissent pas une équivalence des générations stochastiques. Exécution des tests et essais LLM/vidéo toujours réservée à l’utilisateur. Aucun nouveau moteur de plugins, système générique d’héritage ou doublon du workflow de rendu nécessaire pour ce principe.
