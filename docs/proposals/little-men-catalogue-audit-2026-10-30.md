# Petits hommes experimental — catalogue et pistes d’amélioration

État des lieux du 30 octobre 2026. Analyse uniquement : aucun changement de catalogue, d’intention, de sélection, de Plan, de prompter H3 ou de production.

Le catalogue contient **80 objets**, répartis en **8 groupes de 10**. Le modèle reçoit **12 objets par Plan**, pas la liste entière. La fermeture éclair et le sèche-cheveux en font déjà partie. L’originalité attendue vient surtout de leur manipulation à grande échelle et de leur détournement dans la scène.

## Liste complète actuelle

Libellés français exacts du catalogue version `1.0.0`. Les noms transmis au modèle sont en anglais et figurent dans le CSV joint.

| Groupe | Les dix objets |
| --- | --- |
| Couture et attaches | Fermeture éclair ; pince à linge ; aiguille à coudre ; bobine de fil ; bouton ; épingle de sûreté ; lacet ; boucle de ceinture ; dé à coudre ; élastique. |
| Cuisine | Entonnoir ; passoire ; fouet de cuisine ; rouleau à pâtisserie ; cuillère en bois ; louche ; pince de cuisine ; spatule ; tire-bouchon ; boule à thé. |
| Bureau et papeterie | Trombone ; pince à dessin ; agrafeuse ; rouleau adhésif ; règle ; crayon ; gomme ; ciseaux ; tampon encreur ; loupe. |
| Toilette et coiffure | Sèche-cheveux ; peigne ; brosse à dents ; pince à cheveux ; bigoudi ; pince à épiler ; lime à ongles ; blaireau de rasage ; savon ; pinceau à maquillage. |
| Maison et entretien | Brosse à vêtements ; plumeau ; pelle à poussière ; balayette ; éponge ; vaporisateur ; bassine ; cale-porte ; cintre ; panier à linge. |
| Atelier | Ressort ; charnière ; poulie ; mousqueton ; serre-joint ; tournevis ; ventouse ; aimant en fer à cheval ; écrou et boulon ; pinceau de peinture. |
| Loisirs | Yoyo ; toupie ; balle de jonglage ; cerf-volant ; moulinet de pêche ; ballon gonflable ; moulin à vent en papier ; éventail ; boîte à musique ; domino. |
| Contenants et emballages | Boîte d’allumettes ; boîte à œufs ; tube en carton ; bouchon en liège ; capsule ; bocal ; filet à provisions ; bac à glaçons ; boîte à biscuits ; gobelet en papier. |

[Liste CSV avec identifiants, noms anglais et statistiques par objet](little-men-catalogue-2026-10-30.csv).

## Ce qui est réellement proposé au Plan

Le sélecteur compose un assortiment de douze objets, avec un ou deux représentants de chaque groupe. Il ne lit pas l’image ni son besoin : la pertinence est décidée ensuite par le modèle. La liste est déterministe par fiche et figée avant l’appel, ce qui permet de conserver le même assortiment pendant la préparation.

Il privilégie d’abord le groupe le moins représenté dans cet assortiment, puis les objets peu utilisés. Le score de répétition est `8 × usages déclarés + expositions provisoires`. Un départage propre à la fiche complète le classement.

La mémoire porte sur les **50 fiches pertinentes les plus récemment mises à jour**, comprenant choix résolus et réservations sans choix. Ce ne sont donc pas exactement les 50 derniers Plans ou rendus. Une liste réservée compte provisoirement ses douze propositions ; après résolution, seuls les objets réellement déclarés comptent. Les objets proposés mais écartés ne gardent pas de pénalité d’exposition.

Les données d’un objet sont limitées à son identifiant, son nom anglais, son libellé français et son groupe. Le Plan reçoit les identifiants et noms anglais, sans description de matière, de mouvement ou de propriétés physiques. Les groupes sont des rayons éditoriaux : ils ne définissent ni problème ni solution.

La diversité des mécanismes est guidée séparément par dix familles : relier/assembler, séparer/couper, déplacer/transporter, dévier/détourner, capter/absorber/extraire, déformer/remodeler, modifier la température, soutenir/stabiliser, confiner/contenir, faire écran. Une onzième valeur sert de repli, « autre opération ». Les moins utilisées sont proposées en priorité, sans obligation de rotation. Main seule et objets extérieurs restent autorisés.

Source : [catalogue, mémoire, sélection et consignes v8](../../src/panelforge/domain/little_men_variety.py).

## Utilisation observée et limites de comparaison

La référence avant patch est le snapshot figé à **09:16:57 Paris**, déjà utilisé dans l’audit précédent : **144 Plans acceptés** sous l’ancienne intention v8. Tous les 80 objets y ont été proposés, pour 1 728 propositions au total.

| Mesure avant patch | Résultat |
| --- | ---: |
| Plans choisissant un objet du catalogue | 25 / 144, soit 17,4 % |
| Objets catalogue distincts choisis | 21 / 80 |
| Plans déclarant un objet extérieur | 7 / 144 |
| Plans avec liste d’accessoires vide | 112 / 144 |
| Maximum de choix d’un même objet catalogue | 2 |

Une liste vide peut néanmoins correspondre à l’utilisation de matériaux ou d’équipements déjà présents dans l’image. Les nombres ci-dessus mesurent les déclarations du Plan, pas la présence ou la qualité de l’objet dans la vidéo.

| Objet | Proposé dans les 144 Plans | Choisi |
| --- | ---: | ---: |
| Fermeture éclair | 26 | 0 |
| Sèche-cheveux | 24 | 0 |
| Boîte à musique | 35 | 0 |
| Écrou et boulon | 38 | 0 |
| Cintre | 41 | 0 |
| Pinceau de peinture | 41 | 0 |
| Bobine de fil | 5 | 0 |
| Bassine | 6 | 2 |
| Serre-joint | 13 | 2 |
| Louche | 17 | 2 |
| Règle | 26 | 2 |

Les objets de toilette/coiffure cumulent **224 propositions d’objets, aucun choix**. Ce n’est pas une preuve qu’ils sont inutiles : l’ancienne intention laissait notamment le modèle considérer les accessoires comme trop petits ou anachroniques. La pertinence dépend aussi des scènes du lot. Un objet proposé cinq fois n’a pas eu la même exposition qu’un autre proposé quarante et une fois.

Le relevé courant est figé à **10:27:28 Paris**, révision 149055. Il contient 108 Plans v8 acceptés encore présents, dont 107 avec l’ancienne intention et **un avec la nouvelle intention**. Les ensembles de fiches ont changé entre les snapshots ; leur différence de total n’est pas un indicateur de performance.

Trois fiches portent la nouvelle intention : une préparée et rendue, deux encore en attente. Le premier Plan choisit un **mousqueton**, décrit sa fixation laissée en place puis les bras levés et un merci unique. C’est cohérent sur le papier avec les nouvelles consignes ; **cet audit n’a pas évalué sa vidéo** et un seul essai ne permet pas de conclure sur l’efficacité du patch.

Les cohortes sont distinguées par empreinte du texte, puisque la version reste v8 : ancienne `9426155b3221…`, nouvelle `5e2594fc113b…`.

## Ce qui fonctionne et ce qui limite la variété

### Les bases à conserver

- Les accessoires choisis sont assez diversifiés : aucun objet n’est choisi plus de deux fois dans la cohorte de référence.
- La liste est libre de correspondances problème/objet. Elle laisse de la place aux détournements.
- Le sous-ensemble de douze garde le contexte plus court qu’une liste complète de quatre-vingts noms.
- La main seule peut produire une bonne scène ; le chat et le scarabée examinés dans l’audit précédent le montrent.
- Plusieurs objets ont une silhouette ou une manipulation distinctive : fermeture éclair, tire-bouchon, ressort, ventouse, aimant, moulinet, sèche-cheveux. Ils méritent de rester disponibles.

### Les limites à traiter

**Diversité de rayons et diversité de gestes sont différentes.** Cinq brosses/pinceaux, avec le plumeau et la balayette, peuvent mener à des balayages proches. Six objets de pince ou serrage peuvent produire des prises semblables. Plusieurs contenants peuvent aboutir à la même pose ou au même versement. Ce sont des proximités éditoriales, pas des preuves d’échec individuel.

**Le modèle doit inventer les propriétés utiles à partir du seul nom.** Un petit nombre de propriétés neutres pourrait l’aider à distinguer les objets, sans lui indiquer quelle scène ni quel problème leur associer.

**L’historique ne mesure pas la réussite visuelle.** Une catégorie différente ne prouve pas un geste différent. Un objet déclaré ne prouve pas une manipulation lisible ni un résultat durable.

**La mémoire de diversité a des angles morts.** Les noms déclarés hors catalogue ne sont pas pénalisés comme les identifiants connus. Le classement par date de mise à jour peut remettre un ancien Plan en tête à l’occasion d’un rendu ou d’une modification de fiche. L’exposition des propositions écartées est volontairement provisoire ; elle ne permet pas de limiter durablement leur répétition dans les assortiments.

Ces points sont des caractéristiques du fonctionnement actuel. Ils ne justifient pas, à eux seuls, de changer le prompter H3.

## Améliorations recommandées, par priorité

1. **Évaluer d’abord l’intention qui vient d’être livrée.** Sur un petit ensemble varié de nouveaux résultats, noter séparément : objet proposé, objet choisi, manipulation visible, bénéfice qui persiste. Observer aussi le geste de gratitude. Quelques essais donnent une première lecture qualitative, sans prétendre mesurer un taux de réussite fiable.
2. **Enrichir les objets avec de courtes propriétés neutres.** Forme, matière, mobilité, articulation, souplesse ou surface ; aucune scène, aucun bénéficiaire et aucune correspondance danger/objet. Le modèle garde le choix de l’opération et du détournement. Ces propriétés seraient des possibilités, pas des usages autorisés exhaustifs.
3. **Diversifier les douze propositions par propriétés autant que par rayons.** Éviter une concentration de prises, de balayages ou de simples contenants. Conserver une part d’exploration pour laisser surgir des idées inattendues ; ne pas restreindre chaque problème à une liste prédéfinie.
4. **Suivre séparément exposition, choix et répétition.** Conserver le détail des propositions pour l’analyse, avec une influence modérée distincte de la véritable utilisation. Pour les répétitions créatives, préférer la date de validation du choix à une mise à jour quelconque de la fiche ; prendre aussi en compte les objets extérieurs explicitement déclarés.
5. **N’ajouter que des objets apportant une manipulation distincte.** Garder pour l’instant les objets peu choisis, notamment fermeture éclair et sèche-cheveux. Réexaminer leur intérêt après le changement d’intention et une exposition suffisante. Éviter de remplacer un objet uniquement à partir de son faible nombre de choix.

Les points 2 à 5 demanderaient une évolution du catalogue, du contexte de variété ou de son sélecteur. **Ils dépassent l’ajustement d’intention récemment autorisé** et restent des propositions. Ils ne nécessitent pas par principe de réécrire le prompter H3 ou la structure du Plan.

## Six ajouts possibles à examiner ensuite

Sélection éditoriale, sans scénarios imposés ni promesse de qualité vidéo :

| Objet proposé | Propriétés et manipulation distinctives |
| --- | --- |
| Soufflet | Volume qui se comprime et se déploie, expulsion d’air visible dans son geste. |
| Seringue sans aiguille | Cylindre transparent et piston, aspiration ou refoulement. |
| Mètre ruban rétractable | Extension, bande flexible et rappel dans un boîtier. |
| Bande autoagrippante | Deux surfaces qui s’accrochent par contact et se séparent. |
| Fer à repasser | Semelle plane chauffante, pression et glissement. |
| Poche à douille | Enveloppe souple comprimée, extrusion par un embout. |

Les trois premiers me paraissent les candidats les plus distinctifs en mouvement. Le choix final devra tenir compte de leur lisibilité dans la scène, du rôle de la main et du temps disponible. Aucun de ces six objets n’a été ajouté.

## Pièces d’audit

- [CSV complet des 80 objets](little-men-catalogue-2026-10-30.csv), avec noms transmis et compteurs avant patch.
- Diagnostics : `.agent/diagnostics/petit-homme-catalogue-audit-20261030/` (`snapshot.json`, `statistics.json`, `comparison.json`, `catalogue-objets.csv`).
- [Audit des productions avant modification](little-men-batch-audit-2026-10-30.md).
- Extraction par lecture AST et JSON ; aucun import applicatif, test, appel LLM, rendu ou redémarrage lancé. Aucun catalogue ni réglage modifié.

## Alignement demandé — catalogue enrichi, sélection et répétitions

L’utilisateur demande le tube de glue, le rouleau de scotch, les six ajouts proposés, un petit groupe sport et les propriétés des objets. Il souhaite préciser le fonctionnement des points 3 et 4 avant l’implémentation de l’ensemble. Cette section est une proposition de conception ; le catalogue effectif reste à 80 objets.

### Ajouts proposés : 95 objets au total

- Ajouter **tube de colle** ainsi que **soufflet, seringue sans aiguille, mètre ruban rétractable, bande autoagrippante, fer à repasser, poche à douille** : sept nouveaux objets.
- Ajouter un groupe **sport** de huit objets : **raquette de tennis, ballon de basket, corde à sauter, frisbee, haltère, palme de natation, tapis de yoga, patin à roulettes**. Ce choix élargit les formes et propriétés ; il n’impose aucun scénario ni utilisation.
- Le rouleau de scotch correspond déjà à `adhesive_tape`, nom anglais canonique `roll of adhesive tape`. Clarifier le libellé français en « Rouleau de scotch » et ajouter des alias au besoin, tout en conservant l’identifiant, le nom anglais canonique et l’historique. Ne pas créer un doublon.

### Propriétés pour chaque objet

Prévoir deux à quatre propriétés distinctives, courtes et neutres, accompagnées de quelques caractéristiques structurées communes servant au sélecteur. Le modèle ne reçoit que les propriétés des douze objets proposés. Les objets restent dimensionnés pour la main et ne sont pas limités à l’époque du village.

| Objet | Exemple de description des propriétés, sans scénario |
| --- | --- |
| Tube de colle | Tube souple, embout étroit, matière visqueuse adhésive, compression. |
| Rouleau de scotch | Bande flexible, face adhésive, déroulement, déchirure. |
| Raquette de tennis | Cadre rigide, manche, cordage tendu et élastique, surface ajourée. |

Ces propriétés décrivent des possibilités, pas une liste exhaustive d’usages permis. Ne pas ajouter de correspondance objet/problème ou imposer une unique famille de mécanisme à un objet.

### Point 3 — composer les douze propositions

Conserver douze candidats et un assortiment figé par préparation. Favoriser les objets qui apportent des propriétés encore peu représentées dans cet assortiment, puis réduire le poids des objets récemment choisis et, plus légèrement, celui des objets souvent proposés. Les rayons éditoriaux deviennent un facteur secondaire ; aucun objet de sport n’est obligatoire dans chaque scène.

Conserver une part d’exploration déterministe propre à la fiche, pour ne pas reconduire systématiquement les mêmes combinaisons. Les proximités entre deux objets sont des pénalités souples, jamais une interdiction de combiner deux objets similaires. Le modèle qui lit l’image décide ensuite de la pertinence, avec la main seule et le choix hors assortiment toujours possibles.

### Point 4 — suivre les répétitions déclarées

Utiliser les champs existants de `variety_choice`, sans nouveau champ à produire par le modèle :

- Objet choisi, avec son identifiant stable ou un nom extérieur normalisé.
- Famille de mécanisme déclarée.
- Couple objet/famille ; pour la main seule, suivre explicitement le couple main seule/famille.

Conserver un historique borné des cinquante derniers choix validés avec une date stable et l’identité de la préparation. Le rendu, une reprise du même Plan ou une modification de fiche ne doivent pas créer une nouvelle utilisation. Garder séparément les propositions et les usages, avec une influence moindre pour une simple exposition.

Les répétitions conduisent à des préférences souples : un même objet reste possible pour une autre opération, et l’utilité prime. Présenter au Plan un résumé bref des combinaisons récentes dans son contexte de variété. Les objets hors catalogue sont suivis à partir des noms explicitement déclarés et d’alias connus ; aucune reconnaissance hasardeuse d’objets dans la prose.

Ce suivi mesure les choix déclarés, **pas les gestes réellement exécutés ou la réussite visuelle**. Deux gestes proches peuvent partager ou changer de famille. Une appréciation qualitative des rendus reste nécessaire ; aucun appel LLM supplémentaire ni analyse vidéo automatique n’est proposé dans cette étape.

### Périmètre et compatibilité

Cette évolution modifierait le catalogue, ses propriétés, le sélecteur, le suivi interne et le contexte de variété fourni au Plan. Le **prompter H3, la structure du Plan, le Writer et les validateurs caméra/parole restent inchangés**. Le contrôle des métadonnées de catalogue devra en revanche comprendre la nouvelle version et préserver l’ancienne.

Ne pas simplement remplacer `CATALOG_VERSION` : le validateur actuel exige la version courante. Prévoir la lecture du catalogue 1.0 pour les assortiments déjà figés, avec leurs anciens noms et descriptions, et la nouvelle version pour les nouvelles réservations. Les préparations existantes ne sont pas réinterprétées à partir du nouveau catalogue. Aucun de ces changements n’est appliqué pendant cet alignement.
