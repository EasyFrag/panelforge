# Petits hommes experimental — audit du batch du 30 octobre 2026

Audit uniquement. Aucun preset, code applicatif, fiche de production ou service modifié. Aucun test, import applicatif, appel LLM ou rendu lancé.

## Périmètre et méthode

État figé le **30 octobre à 09:16:57 Paris / 08:16:57 UTC**, révision 148200. Les productions ont continué indépendamment après ce relevé.

- Ensemble v8 : 150 fiches, 144 Plans et Prompts acceptés, 98 vidéos terminées, 6 rejets au Plan.
- En retirant les quatre préparations examinées la veille : **140 nouveaux Plans/Prompts acceptés, 94 nouvelles vidéos terminées**, six rejets.
- Lecture des choix de variété sur l'ensemble, examen textuel ciblé des préparations récentes et comparaison détaillée de dix productions terminées.
- Inspection visuelle de **50 images de contrôle : cinq par vidéo**, à environ 0 / 2,52 / 5,04 / 7,56 / 10,08 secondes. Pas de lecture exhaustive des vidéos ni d'écoute audio : le timing exact du merci et les transitions entre ces images ne sont pas évalués.
- Les dix exemples constituent un échantillon qualitatif varié, pas une mesure représentative du taux de réussite visuelle du lot.

Les 150 intentions ont la même empreinte que les quatre fiches de la veille : `9426155b32219a0069ba875512aec429083bb6cc5a0e4abe8fc09b7890f42cee`. Les ajustements proposés dans le premier audit **ne sont pas encore appliqués**. Le lot observe donc toujours la même intention v8.

Preuves locales : `.agent/diagnostics/petit-homme-batch-audit-20261030/` contient `snapshot.json`, `statistics.json`, six planches de lecture, `visual-manifest.json` et `render-transmission.json`.

## Variété : un catalogue peu utilisé, mais réellement varié

| Choix déclaré | 144 Plans v8 acceptés | 98 vidéos terminées |
| --- | ---: | ---: |
| Objet du catalogue | 25 (17,4 %) | 16 (16,3 %) |
| Objet hors catalogue | 7 | 3 |
| Liste `objects` vide | 112 | 79 |
| Objets catalogue distincts | 21 | 14 |

Dans le nouveau lot seul : **24 choix catalogue sur 140 Plans**, et 15 sur 94 rendus. Une liste vide ne signifie pas nécessairement une scène sans objet : la main peut utiliser un tuyau, des matériaux ou un équipement préexistant.

Aucun objet catalogue n'est choisi plus de deux fois dans les 144 Plans. Les dix familles sont représentées : redirect 19, support 18, absorb_remove 16, shield 15, move 15, link 15, contain 14, reshape 13, temperature 11, separate 8. Cette répartition ne prouve pas une diversité équivalente des gestes : plusieurs familles peuvent aboutir à une paume posée ou à une simple extraction.

Deux freins ressortent des justifications :

1. **Échelle supposée trop petite.** Au moins 23 raisons écartent explicitement les accessoires comme petits, miniatures ou de taille humaine ; 17 concernent un rendu terminé. Par exemple, Égypte L073 dit que les accessoires sont trop petits pour la main. Cette restriction n'est pas demandée par le preset.
2. **Anachronisme supposé interdit.** Iran L029 et Grèce L045 rejettent des objets parce qu'ils ne correspondraient pas à l'époque du village. Le contraste recherché avec l'accessoire de la main est ainsi limité par une interprétation excessive de la cohérence du décor.

La priorité n'est donc pas d'allonger le catalogue. Il faut expliciter l'échelle des objets et leur indépendance par rapport à l'époque du village, tout en gardant leur utilité et la main seule possibles.

## Dix productions examinées

Les variantes portant le même intitulé peuvent utiliser des images sources différentes ; elles ne constituent pas un essai comparatif contrôlé.

| Exemple | Ce que montrent les images | Ce qui est améliorable |
| --- | --- | --- |
| **Iran L074 — chat**, `660db0…` | Contact main/patte, patte soulevée, toile retendue, résultat encore visible après le départ. | Bonne intervention directe. Le Plan pourrait mieux décrire la prise : « presser sur la patte » puis « soulever » est mécaniquement ambigu. |
| **Égypte L073 — extraction du scarabée**, `6b3dc4…` | L'insecte est saisi puis retiré ; habitants et plateforme chargée avancent dans l'espace libéré. | Exemple convaincant sans accessoire. La justification qui élimine le catalogue pour sa petite taille reste infondée. |
| **Égypte L073 — paniers**, `5747a4…` | Les paniers sont transportés et empilés ; une charrette avance ; le scarabée reste proche. | Le Plan suppose que le scarabée cesse de menacer les réserves parce que les paniers ont bougé. Le rendu multiplie aussi les paniers et place la pile devant la porte, plutôt qu'à côté. |
| **Vietnam L071 — louche et vague**, `e7994f…` | Objet géant, prélèvement et versement visibles ; quais moins submergés. | Le Plan traite l'eau près des quais tout en conservant explicitement la grande vague. Celle-ci s'abat/se réduit sans contact avec l'intervention ; le bassin de rejet n'est pas clairement distinct du même plan d'eau. Originalité présente, sécurité causale fragile. |
| **Pérou L070 — vaporisateur**, `6af510…` | Manipulation et jet très lisibles ; flammes du toit réduites. | Le feu reste nettement actif sous le toit au dernier point de contrôle, alors que le Plan annonce essentiellement des braises et un chemin sûr. La chaîne d'évacuation continue : le bénéfice nouveau pour les habitants est peu joué. |
| **Turquie L067 — conduite**, `8dcfc0…` | La main saisit la conduite ; le débit diminue fortement après le contact. | L'extrémité déchirée reste ouverte. Le Plan imagine deux extrémités à réunir et une réparation par colliers, alors que l'image montre surtout une bouche ouverte. L'arrêt de l'eau ne démontre pas la réparation annoncée. |
| **Espagne L066 — incendie**, `1a0829…` | La main approche ; les grandes flammes baissent, mais un foyer reste près du passage des personnes. | Le Plan fait « souffler » une main qui demeure en suspension, sans décrire un mouvement produisant l'air. Mécanisme mal défini dès le Plan, puis résultat visuel incomplet. |
| **Italie L064 — extraction de glace**, `ca920c…` | Prise et transport d'un bloc, puis passage utilisé par des habitants. | Action plus lisible que la simple chaleur de la paume. Le changement de point de vue et d'échelle du bloc rend cependant la continuité exacte entre la porte initiale et la porte dégagée difficile à établir sur les images échantillonnées. |
| **Italie L064 — chaleur de la paume**, `2ccc49…` | Contact, neige/glace dans la main et écoulement d'eau visibles. | L'arcade entièrement dégagée et sa traversée annoncées dans le Plan ne sont pas clairement démontrées ; l'effet lisible reste local et partiel. |
| **Grèce L068 — sable contre vague**, `57f500…` | La main transforme fortement le terrain et laisse une grande levée de sable. | La levée devient un relief central très différent de la petite digue côtière prévue. De l'eau reste autour des bâtiments et au premier plan : le camping sec annoncé n'est pas démontré. |

Les identifiants complets et assets des six derniers cas sont dans `visual-manifest.json`. Les quatre premiers :

- Iran : `factory-660db0b2214647349e326e35def9fcee`, prise `asset-710143b5225e4571923e24b6da547d46`, résultat `asset-3b312340acc2483997db5b75cebba0f0`.
- Égypte extraction : `factory-6b3dc4ea6b414d989b6f7b13a19f4045`, retrait `asset-6978dc154fc94a92b6a936652f10db98`, résultat `asset-75c7fd7be81a409fb091e61bb061b7bb`.
- Égypte paniers : `factory-5747a45860234d0f8f004801550cd733`, levée `asset-6bf78ef3188c434b99685050988da2b9`, résultat `asset-3836396b8494415ca64bbd0239a599bf`.
- Vietnam : `factory-e7994fce5fbc4e4fbf36e431e99a4afc`, opération `asset-071f292c7d304648a24e14d1980fe691` et `asset-7788cc6b7b2c40d3bd709cd8134c2a55`, résultat `asset-5107e25db02f48ba89dac89d023ce785`.

## Origine des faiblesses

Les interventions des dix Plans sont conservées dans leurs Prompts, avec reformulations. Sur les six cas vérifiés jusqu'à la tentative, le Prompt enregistré est identique au `prompt` et à l'`effective_prompt` de rendu. Au Pérou, les sept actions sont reprises textuellement.

Il faut donc distinguer :

- **Choix ou causalité faibles dès le Plan** : main qui souffle sans opération définie, réparation supposant une autre géométrie, louche ignorant la vague principale, menace censée cesser spontanément.
- **Écarts au rendu** : extincteur improvisé bien utilisé mais feu restant, colliers censés réparer mais conduite toujours ouverte, deux paniers devenant une pile, résultat sec annoncé mais zone encore inondée.

L'intention peut rendre l'action plus concrète et moins ambiguë ; elle ne garantit pas l'exécution de chaque résultat par le modèle vidéo. Ces exemples n'établissent pas une suppression des actions par le Writer H3.

## Préparations suivantes : défauts encore présents, bonnes pistes aussi

Parmi les douze Plans les plus récents, encore sans rendu au relevé : quatre objets catalogue, un hors catalogue, sept listes vides.

- **Éthiopie L107, vent sur les terrasses** : la main presse une toile, se retire, puis la toile reste fixée malgré le vent ; aucune fixation n'explique cet état. Même défaut que la falaise du premier audit.
- **Pérou L104, fuite du réservoir** : une variante détourne le torrent avec la paume puis conserve ce détournement après le retrait, sans transformation persistante. L'autre emploie un entonnoir laissé en place : causalité plus solide sur le papier.
- **Indonésie L110, varan et passerelle** : une règle sert de passage, les habitants la fixent puis traversent. Construction prometteuse, encore non confirmée par le rendu. Le varan peut rester calme si le besoin établi est la passerelle cassée ; il ne faut pas inventer une attaque.
- **Ouzbékistan L109** refuse une règle jugée trop petite pour franchir le passage, alors que L110 accepte précisément une règle adaptée : l'échelle n'est pas stabilisée par les consignes.

## Ajustements recommandés dans l'intention, non appliqués

1. **Échelle et époque des accessoires.** Les objets sont dimensionnés pour la main et son opération. Ils peuvent venir d'une autre époque que le village. Préserver l'identité du décor ne doit pas les rendre minuscules ou historiquement impossibles.
2. **Mécanisme visible.** Décrire comment la main ou l'objet produit le changement : prise/contact, mouvement utile, réaction de la cible. Une présence, un toucher ou une propriété invoquée ne suffisent pas à expliquer un résultat majeur.
3. **Résultat qui tient après le retrait.** Indiquer ce qui reste déplacé, transformé, fixé ou engagé et pourquoi l'aide continue. Écarter les résultats nécessitant une force que la main n'exerce plus.
4. **Besoin principal et résultat compatible avec l'image.** L'opération répond à la géométrie et au problème réellement visibles. Une amélioration locale peut suffire si la menace restante ne l'annule pas. Ne pas calmer un animal ou une vague indépendamment de l'intervention.
5. **Bénéfice perceptible.** Les bénéficiaires utilisent concrètement ce qui a changé, ou adaptent leur activité grâce à l'aide. Continuer exactement la même évacuation ne démontre pas toujours le bénéfice annoncé. Préserver le merci bref en fin d'action.
6. **Dix secondes consacrées à l'intervention.** Entrée et retrait courts, temps principal pour une transformation lisible. Plusieurs gestes liés sont possibles ; choisir un résultat assez simple pour être obtenu puis observé dans le temps disponible.
7. **Variété sans obligation artificielle.** Comparer les moyens pertinents, favoriser le catalogue et les opérations moins récentes lorsqu'ils conviennent ; garder la main seule lorsqu'elle fonctionne, comme le chat et l'extraction du scarabée. Ne pas ajouter de quota ni de correspondance problème/objet.

Ces règles reformulent des obligations déjà partiellement présentes. Pour les rendre plus efficaces, privilégier les critères de preuve concrets ci-dessus plutôt qu'empiler des injonctions générales. Ne pas ajouter ces scènes comme exemples dans l'intention : elles servent uniquement à l'audit.

Conserver le prompter H3 standard. Une future modification de l'intention devra être évaluée sur ses nouveaux Plans puis sur quelques rendus ; l'acceptation du format n'est pas une preuve de réussite visuelle.

## Six rejets de préparation, distincts de la qualité des vidéos

| Cas | Cause vérifiée | Portée |
| --- | --- | --- |
| Japon L017, Argentine L082 | `objects=[]` et `departure_reason=null`, malgré justification obligatoire. | Clarification locale du contrat de sélection ; aucune absence d'action constatée. |
| Chine L024, Sénégal L048 | Le validateur caméra interprète « shot moves steadily/briskly » dans le rythme comme un mouvement caméra libre. Les champs caméra structurés sont corrects. | Deux faux positifs démontrés du validateur, pas une raison de réécrire le prompter partagé. |
| Vietnam L062 | Le Plan conserve des parasols de marché présents dans l'image ; la main utilise une ventouse. | Conflit entre fidélité à la référence et interdiction intégrale. Ce n'est pas un parapluie choisi comme solution. Toute tolérance au décor initial serait un changement de règle à expliciter. |
| Mali L096 | Le texte exclut « a new crisis, umbrella, or threat » ; l'objet choisi est du ruban adhésif. | Faux rejet certain d'une négation coordonnée. |

Trois faux positifs certains, un conflit avec le décor préexistant et deux justifications absentes. Une éventuelle correction des validateurs serait un patch distinct, ciblé et vérifiable, sans modifier les consignes créatives H3.

Autre limite du preset : **Turquie L067 remercie en russe, Grèce L068 en portugais**. Les réglages sont automatiques et les métadonnées source correctes. Le turc et le grec ne figurent pas parmi les onze langues disponibles ; le repli choisit une autre langue. Ce point est indépendant des gestes et n'est pas causé par une mauvaise association d'image.

## Suite

Priorité proposée : préciser l'échelle et l'époque des accessoires, puis renforcer la causalité persistante et le bénéfice joué. Aucun changement appliqué dans cet audit. Les essais futurs restent à lancer par l'utilisateur, sans modifier les productions déjà en cours.
