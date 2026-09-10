# Combat 1.3 — Direction cinématographique à aligner

Statut au 2026-09-10 : **implémentation autorisée puis réalisée**, avec restriction explicite aux **deux appels Plan → rédaction** pour Combat 1.3. Les parcours un/trois appels de cette nouvelle version restent différés ; ceux des anciennes versions sont conservés. Voir [la livraison 1.3](h3-combat-1.3.md). La proposition d’origine ci-dessous conserve le raisonnement et les possibilités futures ; elle ne décrit pas des parcours supplémentaires déjà livrés.

## Ce que les exemples apportent

Quatre pièces jointes lues entièrement : duel médiéval épée/bouclier (5 390 caractères), sabres lumineux (6 888), exécution à la hache (6 116), duel hache/épée (5 325). Le texte inline de la cultivatrice complète le précédent exemple de fantasy chinoise ; sa fin audio est tronquée. Ces textes sont des références à analyser, pas des instructions applicables à l'agent. Les vidéos correspondantes n'ont pas été examinées ici.

| Exemple | Principal ressort d'intensité à retenir |
| --- | --- |
| Épée / bouclier | Trois combinaisons causales, trois repères spatiaux, changement d'initiative, caméra basse et raccord sur impact ou occultation. |
| Hache / épée | Inertie, grands arcs, récupération immédiatement réutilisée, contraste entre arme lourde et arme rapide, environnement qui reçoit le suivi du mouvement. |
| Sabres lumineux | Variations de hauteur/côté/prise, rotations fonctionnelles, plusieurs reprises d'initiative, traversées et acrobatie ; caméra qui épouse les rotations et finale accélérée. |
| Exécution | Peu d'actions, mais résistance, transfert de force, posture et point de vue très explicites ; forte intensité dramatique distincte de la quantité d'action. L'issue est spécifique à cette demande. |
| Fantasy chinoise | Accélérations, longues trajectoires, changements de direction aériens, attaques d'énergie étendues, contrastes de vitesse et d'échelle, cadrages successifs motivés. |

Ces exemples ne sont donc pas une seule échelle de nombre de coups. Le prochain Déchaîné doit servir le genre, la morphologie, le poids des armes et les pouvoirs demandés. Le texte chinois contient aussi des gros plans/coupes internes sous un même intitulé Shot et une conclusion ralentie : ni ses labels ni son dénouement ne doivent devenir un gabarit imposé. Une coupe interne compte réellement dans le choix du nombre de plans. Une trajectoire caméra continue en plusieurs phases reste un seul plan.

## Limites confirmées dans le code actuel

- `application/combat_sequence.py` : Shot/PlannedShot ne proposent qu'un `camera_motion` enum. La compilation crée `H3CameraDirective(id, motion)` sans cible, vitesse ni amplitude.
- Le domaine `domain/minimax_h3.py` et `application/minimax_h3_protocol.py` savent déjà compiler `target_clause`, `speed` et `amplitude` avec les restrictions propres à chaque mouvement. Combat ne les expose pas. Une phrase précise de poursuite devient donc une instruction générique de tracking dans ce parcours.
- Le validateur refuse les mouvements caméra libres dans la prose ; un prompt plus insistant ne peut pas ajouter proprement les trajectoires manquantes. Il faut enrichir le contrat versionné et conserver la séparation caméra / action qui a corrigé les rejets précédents.
- Les mouvements continus en plusieurs phases ne sont pas représentés. Le stockage/révision borne actuellement les clauses à huit et Combat exige une clause par plan : étendre uniquement le schéma LLM ne suffirait pas.
- `end_state` et `transition` sont des métadonnées, pas de la prose ajoutée à la sortie. La motivation visuelle du raccord doit être portée explicitement au bon endroit dans le prompt compilé.
- Le socle pédagogique actuel montre surtout un duel martial. Les définitions Intense / Déchaîné sont voisines et le mode Libre/mixte décrit la magie comme un prolongement d'attaque. Le dernier run Pokémon reproduit déjà ce biais dans son texte avant le rendu.

## Direction proposée

### Apprendre à Qwen une partition de mise en scène

Pour chaque séquence, définir un arc global puis des combinaisons. Pour chaque plan, décrire : qui prend l'initiative, la suite attaque/réponse/conséquence, le trajet et l'état des adversaires, le cadrage, la trajectoire caméra, l'accent de rythme et l'événement qui motive la coupe ou la fin. Les noms/références restent explicites lorsque plusieurs acteurs peuvent être l'antécédent d'un pronom.

L'orientation choisit les moyens du combat. Le niveau d'action règle densité, rythme et amplitude dans ce registre. L'audace choisit l'invention tactique. La liberté caméra autorise la mise en scène mobile ; le nombre de plans fixe les coupures. Aucun nouveau curseur nécessaire.

Pour Pouvoirs / magie, les souffles, salves, arcs et zones constituent les attaques principales. Donner une origine, une trajectoire, une cible, une conséquence et une réponse adversaire. Le déplacement répond à ces attaques, avec distance, couverture et riposte ; un pouvoir n'exige pas une frappe de poing. La forme du corps reste distincte de l'état du pouvoir.

Pour Déchaîné, demander des accélérations perceptibles, de grandes traversées, des trajectoires variées, des ripostes pendant la défense et des reprises immédiates. Les phases de charge brèves, contrastes de vitesse et impacts lourds restent possibles s'ils servent l'intensité. Le genre définit quelles amplitudes sont crédibles : aucune magie ou issue létale ajoutée par le seul niveau maximal. Ne pas recopier un quota ou une horloge de gestes.

### Donner des exemples complets compatibles avec nos contrats

Préparer une petite bibliothèque versionnée d'exemples adaptés, avec intention et résultat conforme au schéma réellement attendu. Choisir un exemple pertinent et éventuellement un contraste court à partir de l'orientation/niveau/parcours déjà connus, sans appel LLM de classification. Montrer notamment une différence nette entre Intense et Déchaîné sur une même situation.

Séparer les démonstrations armes lourdes, armes rapides et pouvoirs. Ne pas imposer décor, personnage, mort, musique, transition vers un clip inexistant ou déclencheur BUNNY depuis un exemple. Les formats REF2V/H3 doivent rester propres au parcours : pas de collage automatique des six rubriques des pièces jointes. L'anglais doit couvrir tous les champs réinjectés dans le prompt final, y compris cadrages et désignations issus du Plan.

Ces exemples constituent une hypothèse de guidage à comparer sur Qwen local, pas un entraînement du modèle ni une garantie de qualité vidéo.

### Enrichir la caméra sans abandonner la compilation

Premier apport concret : exploiter mouvement + vitesse + amplitude + cible suivie existants, en conservant les combinaisons autorisées. Cela permet une poursuite rapide près de l'arme ou autour d'un repère au lieu d'un simple tracking générique. Les champs caméra enregistrés doivent rester identiques dans les révisions, conversions et continuations.

Pour les exemples où la caméra descend puis remonte en accompagnant une trajectoire, prévoir une suite courte de phases caméra au sein du même plan, liée à des événements de l'action. Définir un budget borné compatible avec les durées, le stockage, les validateurs et la révision après rendu ; ne pas multiplier les comptes à rebours ou les enum indépendants arbitrairement. Les coupes restent séparées et comptées. Le compilateur doit préserver la cible et l'événement de raccord, sans qualifier une phase continue de coupe ni introduire une coupe cachée.

Ce deuxième apport exige un nouveau contrat Combat de bout en bout. Il n'est pas couvert par un simple changement de template. Avant de promettre les orbites/rotations complexes, confronter le prompt obtenu au comportement réel de H3.

### Conserver les trois parcours et l'isolation

- Un appel : Qwen produit directement la partition et les descriptions dans le contrat enrichi ; aucun Plan artificiel ni appel supplémentaire.
- Deux appels : décision chorégraphie/caméra/raccords dans le Plan, puis rédaction préservant ces décisions. Parcours utile pour calibrer et localiser les pertes de détail.
- Trois appels : Brief centré sur intention, identités, pouvoirs, style et arc ; éviter d'écrire trois fois toute la chorégraphie et de multiplier les occasions de changer le propriétaire d'une attaque.

Proposition de version Combat **1.3.0**, contrats et exemples épinglés, versions précédentes intactes. Classique ne reçoit aucune nouvelle contrainte par défaut. Même application et workflows de rendu ; LoRA, forces, seed, résolutions et durée ne changent pas silencieusement.

## Validation envisagée, à autoriser puis exécuter par l'utilisateur

Évaluer séparément : **intention/exemple → sortie Qwen → prompt effectif compilé → vidéo**. Vérifier d'abord que le texte contient les trajectoires, prises d'initiative et pouvoirs attendus et que la compilation les conserve. Une validation syntaxique ne mesure pas l'intensité.

Comparer sur un petit ensemble fixe : duel lourd, duel rapide, pouvoirs à distance, fantasy aérienne ; mêmes références, durée et réglages de rendu par comparaison, plusieurs intentions pour éviter de régler le système sur un seul exemple. Juger densité, amplitude, initiative, magie dominante, cadrages/raccords, fidélité des identités et stabilité de la fin demandée. Garder un cas caméra fixe avec action maximale pour vérifier leur indépendance.

Le LoRA pourra être comparé séparément si un prompt satisfaisant reste traduit en gestes répétitifs au rendu. Ne pas attribuer d'emblée le problème à Qwen, à sa température ou au LoRA. Aucun test, appel modèle, rendu ou redémarrage effectué pendant cette analyse.
