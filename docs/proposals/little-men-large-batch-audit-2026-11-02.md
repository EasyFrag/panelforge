# Audit du preset « Petits hommes experimental » — 2 novembre 2026

Le gros lot confirme deux choses : le choix des accessoires est varié et plusieurs opérations produisent une aide très lisible. La faiblesse principale reste le lien entre le besoin de départ, le geste effectué et le bénéfice obtenu. Certains défauts viennent du Plan ; d’autres apparaissent au rendu malgré un prompt explicite. Aucun défaut général de transmission H3 n’est établi.

Audit uniquement : aucune modification de l’intention, de H3, du catalogue, des fiches ou des paramètres.

## Périmètre et méthode

Snapshot local du 2 novembre 2026 à **18:43:49 Paris**, révision 164599. Les derniers rendus disponibles pour cette version datent du **31 octobre à 07:31 Paris** ; pas de nouvelle vidéo de cette intention datée du 1er ou du 2 novembre dans cet état.

- **131 Plans, 131 Prompts et 131 vidéos terminés** avec la dernière intention, empreinte `4a935785ee19…`.
- **115 nouveaux rendus** depuis le précédent audit, en plus des 16 déjà examinés ; 111 nouveaux Plans.
- Revue des 115 nouvelles images sources et de leurs cinq images de contrôle : **690 images**, confrontées aux intentions sources et aux Plans.
- **140 images supplémentaires**, à une image par seconde sur 14 vidéos, pour préciser les prises, transferts, attaches et usages.
- Vérification détaillée de la transmission sur **10 cas**, depuis le Prompt Usine jusqu’à la tentative réellement rendue.
- Pas de lecture continue ni d’écoute audio : le placement exact à la sous-seconde et le merci prononcé ne sont pas évalués.

Le tableau joint contient une ligne par nouveau rendu, avec nom de fiche, objet déclaré, observations positives, limites, distinction Plan/rendu et chemins vers les médias. Il ne constitue pas un classement automatique en réussites/échecs.

Les 131 fiches comprennent 100 scènes L200, 24 V2 et 7 V2B. Elles représentent 109 titres mais 131 images sources distinctes : deux variantes d’un titre ne sont pas nécessairement une comparaison sur la même image. Les changements de scènes et de contexte empêchent d’attribuer une amélioration globale au seul dernier texte d’intention.

## Ce qui fonctionne

### La variété des objets est réelle

Sur les 131 Plans, 103 déclarent un accessoire et 28 n’en ajoutent aucun dans le champ dédié. Ce dernier nombre ne signifie pas « 28 vidéos sans aucun objet » : la main peut manipuler un élément existant, voire apporter une pièce sans la déclarer comme accessoire.

**63 objets du catalogue et cinq objets extérieurs sont choisis**, soit 68 noms distincts. Aucun n’est choisi plus de trois fois. Les 95 objets du catalogue ont tous été proposés au moins une fois ; les dix familles de mécanismes sont représentées dans les déclarations.

Quelques choix demandés auparavant : fermeture éclair une fois, sèche-cheveux deux fois, scotch une fois. Le tube de colle a été proposé 25 fois sans être retenu. Ce n’est pas, à lui seul, un motif pour imposer cet objet.

Le catalogue remplit donc son rôle de diversification. Il ne garantit pas que chaque objet garde son mécanisme distinctif au rendu.

### Des chaînes d’action complètes deviennent lisibles

| Cas | Ce qui est visible | Réserve |
| --- | --- | --- |
| Sénégal V2-013, pêche, pelle (95) | Pelle vide → ramassage des poissons → transport → versement sur le séchoir → habitants autour du résultat. Séquence confirmée à 1 image/seconde. | Un petit panier est emporté avec les poissons ; défaut secondaire. |
| Irak L198, réservoir, main seule (80) | Prise du montant déformé, redressement de la structure et cuve remise à niveau. | Régularisation globale du métal et rapprochement de caméra. |
| Égypte L199, roseaux, vaporisateur (81) | Gâchette utilisée, jet sur le bord pertinent du feu, bande mouillée et réduction locale des flammes. Les habitants continuent de travailler. | Le reste du feu demeure, sans annuler ce bénéfice. |
| France V2B-006, brouillard cousu, plumet (111) | La membrane de brouillard est déplacée comme du tissu et les bacs sont dégagés. | Le problème n’est traité que localement, ce qui suffit ici. |
| Maroc V2-024, grenade, bassine (106) | La bassine posée est réellement remplie par les habitants. | La simple pose est adaptée à ce besoin ; inutile de la complexifier. |
| Pérou L156, pont, planche (26) | Pose entre appuis puis franchissement. | Accessoire conventionnel, mais bénéfice immédiat. |

Autres cas convaincants : écluse actionnée à la main (15), neige balayée (17), rocher déplacé (20), seaux remplis par pulvérisateur (29), auvent coupé puis morceau traité au sable (35), arche serrée (44), terre compactée pour fermer un débordement (68), bassin refermé par pince à linge (72).

La fermeture éclair du Maroc L148 (18) est réellement tirée : ce n’est pas uniquement un objet déposé. La fermeture est mieux démontrée que la protection thermique. Le sèche-cheveux de l’Inde L161 (32) provoque un dégel visible, mais le trajet de l’eau et la situation des figurants restent moins réussis. Ces cas valident le potentiel du détournement sans justifier de les compter comme parfaits.

### Les scènes calmes et fantastiques sont une bonne direction

Le modèle peut aider une activité en cours sans inventer une catastrophe : retrait de bardane sur les câbles, déblocage d’un métier, collecte de poissons, service d’un repas réchauffé. La main peut également aider l’animal plutôt que le combattre.

Le singe de l’Inde L137 (3/4) interagit avec la main et change sa prise. Le problème initial d’un animal simplement présent sans interaction n’est donc pas systématique.

La bonne contrainte est de conserver le rôle et les propriétés de la scène. Ni tous les animaux ni toutes les activités n’ont besoin de devenir dangereux.

## Les faiblesses prioritaires

### 1. Le Plan choisit parfois le mauvais problème ou le mauvais sens d’action

C’est la priorité la plus directement accessible à l’intention.

- **Égypte L176, rigole/poche à douille (50)** : l’intention source indique un passage bouché. Le Plan décide de colmater une fuite. Le rendu montre une belle extrusion, mais ajoute un gros amas au milieu de la rigole. Le geste est réussi, le diagnostic ne l’est pas.
- **Pérou V2-003, bac déséquilibré (85)** : la source demande de déplacer les charges vers le bord opposé. Le Plan les déplace vers le côté bas tout en affirmant que ce côté remonte. Le rendu déplace bien les sacs ; la cause du rééquilibrage reste incohérente.
- **Égypte V2-008, eau qui remonte (90)** : la source explique que l’eau s’élève spontanément et que les habitants referment leurs bidons. Le Plan laisse un bocal ouvert, censé retenir cette eau grâce à ses parois et à la gravité. Il oublie précisément la propriété qui créait le besoin.

Pour 50 et 90, j’ai vérifié les **requêtes Plan sauvegardées et réellement liées aux tentatives** : intention d’image complète, prompt canonique et image source sont présents. Le problème ne vient pas d’une métadonnée manquante. Ajouter une nouvelle couche de contexte ne traiterait pas directement cette mauvaise exploitation de l’information disponible.

L’intention doit aider à choisir un changement qui résout le besoin, pas seulement à produire un changement quelconque sur l’objet le plus facile à manipuler.

### 2. L’étape qui justifie le résultat est souvent escamotée

On distingue trois cas :

- **Prélèvement absent** : Éthiopie L172, pinces (46), le rocher arrive déjà saisi. Égypte V2-008 (90), le bocal arrive déjà rempli. Mali V2-016 (98), la passoire arrive chargée puis verse sur le sol déjà mélangé au lieu de filtrer dans une jarre.
- **Mauvaise destination ou mauvaise cible** : Éthiopie L144 (14), la glace ramassée est déposée sur le pont ; Chine L157 (27), la neige retombe dans le camp. Inde L180, seringue (55), le jet vise le centre du camp plutôt que l’ouverture en feu. Dans ces cas, les Plans demandaient bien une autre destination/cible.
- **Liaison ou mise en fonctionnement absente** : Iran V2B-003 (109), une bande entoure les racines mais ne rejoint pas clairement le lest ; France L175, bigoudi (114), le jet apparaît sans pompage humain lisible, alors que cette action était demandée.

Les séquences détaillées confirment les observations sur 14, 27, 46, 90, 98, 109 et 114. Pour les autres cas examinés seulement sur cinq points de contrôle, une étape très brève peut avoir échappé à l’échantillonnage.

Une opération simple n’est pas automatiquement sûre : en Italie V2B-004 (110), le cale-porte est posé devant le poteau, sans contact porteur clair. Ajouter seulement « montrer le geste » ne suffira probablement pas, puisque cette consigne figure déjà dans l’intention.

### 3. Le bénéfice annoncé est parfois annulé par la scène qui continue

Plusieurs protections contre les vagues montrent surtout la pose d’un objet puis des habitants submergés qui remercient : Égypte L169/haltère (42), Mexique L174/éventail et corde (48/49), Inde L197/élastique (78). La petite consolidation peut exister, mais la protection promise n’est pas démontrée.

**Suisse L195, écran pare-feu (76)** est particulièrement net : après la pose, les flammes gagnent la cour et la façade que le Plan promettait de protéger, tandis que les habitants lèvent les bras.

Cela ne signifie pas qu’il faille supprimer toute menace ou tout incendie. Une aide locale suffit lorsqu’elle change effectivement ce que le bénéficiaire peut faire : passer, boire, récupérer quelque chose, reprendre son travail. Le vaporisateur 81 et les seaux 29 le montrent bien.

Le défaut est de remercier pour un résultat seulement déclaré, ou de simplifier l’intervention au point de perdre l’enjeu principal.

### 4. La variété des noms dépasse parfois celle des mécanismes

Des objets différents reviennent à « poser une forme devant le problème » :

- rouleau à pâtisserie (36) utilisé comme barrage, sans rouler ;
- pince double clip (37) devenue barrage noir, sans prise effective ;
- agrafeuse (64) choisie comme pont dès le Plan, sans agrafage ;
- cale-porte (56) transformé en grand panneau ;
- divers bacs, couvercles et plaques servant d’écrans.

Il faut conserver la liberté de détourner les objets. L’agrafeuse-pont n’est pas interdite par principe ; elle est peu convaincante ici parce que le passage n’est pas utilisé. À l’inverse, la bassine 106 et la charnière-passerelle 115 montrent qu’une pose peut être la bonne action.

Réduire le catalogue maintenant risquerait de réduire les choix sans corriger ce raisonnement. Le problème est davantage la sélection d’une opération utile et distincte que le nombre d’objets disponibles.

### 5. La gratitude fonctionne mieux que la preuve du bénéfice

Les bras levés sont fréquemment visibles. La demande de réaction des habitants est donc largement représentée visuellement. Certains cas gardent des réactions discrètes, mais ce n’est plus la priorité.

En revanche, le merci apparaît parfois avant une véritable reprise d’activité, voire pendant l’aggravation du problème. Dans les meilleurs exemples, les habitants utilisent ou constatent le changement avant de remercier. Il faut préserver cette petite preuve plutôt qu’ajouter de nouveaux gestes de célébration.

L’audio n’ayant pas été écouté, cet audit ne valide pas le nombre exact de mercis prononcés.

## Où se situe le problème dans la chaîne ?

Sur dix cas (18, 32, 50, 65, 85, 90, 95, 98, 103, 111), le **Prompt Usine, le prompt du projet H3 et celui de la tentative rendue sont identiques**. Le prompt effectif n’ajoute qu’un retour à la ligne. Les assets vidéo, les cinq images de contrôle et les paramètres concordent.

Les 64 actions examinées restent présentes ou reformulées ; 30 sont reprises mot pour mot. Les gestes décisifs ne disparaissent pas globalement lors du passage Plan → Prompt.

La séparation utile est donc :

| Niveau | Exemples | Levier raisonnable |
| --- | --- | --- |
| Mauvaise conception du Plan | Rigole colmatée au lieu d’être débouchée ; bocal ouvert pour eau ascendante ; charges déplacées du mauvais côté. | Mieux hiérarchiser le choix du besoin et du changement dans l’intention. |
| Plan cohérent, exécution différente | Glace redéposée sur le pont ; pinces déjà chargées ; attache sans lest ; pompage absent. | Favoriser une chaîne plus facile à rendre, avec une étape décisive lisible. L’intention n’offre pas de garantie. |
| Objet original, résultat insuffisant | Agrafeuse-pont inutilisée ; écran posé avec habitants encore submergés. | Choisir d’abord une preuve du bénéfice, puis les moyens. |

Les paramètres enregistrés sont identiques sur les 131 lancements : même modèle Plan, même Writer, recette, durée, résolution, nombre de steps et seed verrouillée. Il n’y a pas de panne actuellement affichée sur ces fiches. Les historiques vides ne permettent pas de conclure à une réussite au premier essai ou à une absence totale de retries.

Je ne recommande ni un retour arrière H3 ni une modification de son prompter à partir de cet audit.

## Évolution d’intention préconisée, sans implémentation

L’intention actuelle fait 2 319 caractères et contient déjà l’essentiel des principes : besoin principal, propriétés de l’univers, opération avant objet, partie utile, geste, maintien et bénéfice. **Empiler encore des formulations proches serait un changement peu ciblé.**

Je privilégie une réécriture plus courte et plus ordonnée du choix de l’aide :

1. **Fixer le changement utile à partir de l’image et de son contexte.** Identifier ce qui empêche réellement le bénéficiaire d’avancer. Le résultat recherché doit répondre à ce besoin, au bon endroit et dans le bon sens. L’opération doit fonctionner avec les propriétés établies du monde, ou montrer ce qui les contraint localement : les préserver ne signifie pas seulement conserver le décor.
2. **Choisir une intervention dont l’étape décisive peut être montrée dans les dix secondes.** Simplifier la manipulation, sans remplacer le besoin principal par une amélioration secondaire plus facile. Une aide locale reste valable si son résultat tient face à ce qui continue dans la scène.
3. **Faire dépendre le résultat de l’action montrée.** On distingue la cible avant l’opération, le contact qui la change et son état après. Le contact, la transformation, la liaison ou le transfert indispensable doit relier l’état initial à l’état final. Une étape nécessaire ne peut pas être supposée déjà accomplie.
4. **Consacrer un bref moment à la preuve du bénéfice, puis au merci.** Le résultat est utilisé ou sa valeur est directement visible ; les bras levés et l’unique merci restent courts.

Ce sont des priorités de formulation, pas quatre nouveaux blocs à ajouter ni un schéma de Plan supplémentaire. La nouveauté utile porte surtout sur le choix du résultat et l’interdiction de sauter l’étape qui le produit. Les autres principes doivent remplacer les répétitions existantes.

À conserver : dix secondes, accessoires facultatifs, choix varié, détournements insolites, main seule possible, aide aux animaux et aux activités calmes, propriétés fantastiques, parapluies/parasol/ombrelles exclus, remerciement bref avec bras levés. Aucun exemple objet-problème à injecter dans le texte.

Je ne recommande pas de multiplier les actions. Les Plans contiennent déjà quatre à neuf actions, médiane six, et les Prompts 289 à 619 mots, médiane 431, pour dix secondes. Ces nombres ne prouvent pas une surcharge causale, mais les étapes escamotées invitent à choisir plus soigneusement les actions indispensables.

## Comment juger une prochaine évolution

Comparer les versions sur les mêmes images sources et avec la même configuration, en distinguant scènes dangereuses, activités calmes et univers à propriété particulière. Quelques titres voisins ne constituent pas une comparaison contrôlée si l’asset initial diffère.

Quatre questions suffisent pour noter chaque rendu :

- Le besoin traité correspond-il au besoin source ?
- Voit-on l’étape qui produit réellement le changement ?
- Le résultat reste-t-il utile quand la main se retire et que le monde continue ?
- Le bénéficiaire en profite-t-il avant la gratitude ?

Suivre séparément l’originalité de l’objet, l’identité de son mécanisme et la qualité du résultat. Un objet différent n’est pas une réussite supplémentaire ; un secours simple sans accessoire peut être excellent.

## Fichiers de l’audit

- [Tableau des 115 nouveaux rendus](little-men-large-batch-audit-2026-11-02.csv).
- [Manifeste avec Plans, Prompts et contexte source](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/new-manifest.json).
- [Statistiques](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/stats-notes.txt).
- [Contrôle de transmission et des métadonnées](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/transmission-notes.txt).
- [Pelle et poissons — séquence détaillée](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/root-detail-095.jpg).
- [Eau ascendante — séquence détaillée](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/root-detail-090.jpg).
- [Rigole et poche à douille](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/contact-050.jpg).
- [Écran pare-feu et aggravation](../../.agent/diagnostics/petit-homme-large-batch-20261102-174349/contact-076.jpg).

Aucun test, appel LLM, génération, import applicatif ni redémarrage effectué. Écritures limitées aux diagnostics, à ce rapport, au tableau et à la continuité du projet.

