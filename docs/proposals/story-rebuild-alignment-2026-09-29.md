# Nouveau parcours Histoire — proposition d'alignement — 29 septembre 2026

## Statut

Discussion de conception demandée par l'utilisateur, après son retour détaillé sur les cinq scènes de Kiwino et les sept scènes de La même espèce. Aucun accord d'implémentation déduit de « on s'aligne ». Les choix de parcours ci-dessous sont des propositions, à distinguer des exigences déjà exprimées.

Aucun code applicatif, prompt actif, modèle, réglage, génération ou service modifié. Lecture de la continuité, des audits, des intentions effectivement envoyées à l'usine pour Kiwino et de l'interface existante. Les cinq tâches Kiwino sont désormais `succeeded`, dernière terminée le 28 septembre à 21:53:40 UTC ; le relevé précédent où elles étaient en attente est historique. Pas de nouvel examen audiovisuel complet de Kiwino dans ce travail : ses défauts de réception sont le retour utilisateur, rapproché du scénario source.

## Demande et préférences établies

- Reconstruire sur une base solide ; un nouveau menu/parcours Histoire est acceptable. L'utilisateur ne demande pas encore de coder.
- L'histoire doit poser clairement ses bases, même au prix d'un setup plus explicite. Les relations, intentions, événements et changements de temps nécessaires doivent être compréhensibles.
- Les intentions importantes doivent passer dans le jeu ET dans les paroles lorsque la compréhension en dépend. Peu de sous-entendus ; ne pas fonder l'intrigue sur une notification, une photo ou une formule équivoque.
- L'UX doit être minimaliste et fonctionnelle. Le brief utilisateur peut rester court ; le moteur porte la responsabilité de développer une scène intelligible.
- Conserver la vigilance déjà demandée : prompts peu chargés, consignes non contradictoires, présence distincte de parole, références accessibles pour les retravailler sans lancer une génération.

La clarté pour le spectateur ne signifie pas que tous les personnages doivent connaître le secret. Une scène entre les deux amants peut rendre la tromperie explicite au public tout en laissant le mari ignorant. Il faut respecter l'instant prévu des révélations. À l'inverse, expliciter n'impose pas de verbaliser chaque geste ou de transformer les personnages en narrateurs de leur fiche.

## Retours à conserver comme cas de qualification

| Scène | Retour utilisateur | Compréhension attendue |
| --- | --- | --- |
| Kiwino 1 | « Un truc qui clignote », notification : trop indirect. | Identifier le couple et le sens relationnel du secret. Une alerte téléphonique seule ne prouve pas une liaison. |
| Kiwino 2 | « C'est nous, c'est officiel ? », veste : peu naturel et incompréhensible. | Annonce claire de grossesse, futur père qui comprend et exprime sa joie ; un éventuel départ pour fêter doit avoir un motif compréhensible. |
| Kiwino 3 | La scène seule devant une photo ne suffit pas. Demande d'une scène des deux amants parlant du mari. | Liaison visible et contexte verbal explicite pour le public. Ce choix demandé est spécifique à ce cas, pas un patron obligatoire pour toutes les histoires. |
| Kiwino 4 | Révélation visuelle réussie, mais bébé/naissance non introduits. | Situer l'écoulement du temps et présenter le nouveau-né avant de faire porter le retournement sur sa ressemblance. |
| Kiwino 5 | « C'était jamais à nous » : référent ambigu. | Comprendre sur quoi porte l'accusation et quelle décision de couple est prise. |
| Copine 1 | Présentation devant porte fermée bizarre. | Père disponible et en position de recevoir la présentation ; relation nommée naturellement. |
| Copine 2 | Vin puis invitation trop directs. | Courte attirance réciproque lisible, puis invitation et acceptation. |
| Copine 3 | Acceptable si la scène 2 établit correctement le contexte. | Conserver ce qui fonctionne ; ne pas réécrire systématiquement toutes les scènes. |
| Copine 4 | Plutôt bien mais trop rapide. | Laisser le temps d'identifier la grossesse et la complicité, sans empiler de gestes inutiles. |
| Copine 5 | Grossesse, dates, photos : dialogue incompréhensible. | Doute précis, explication portant sur ce doute, réaction compréhensible. |
| Copine 6 | Réglages du lit et « héros » : incohérence de l'échange. | Une excuse absurde mais interprétable, reliée à la situation et à la naïveté du fils. |
| Copine 7 | Petit humain et grossesse persistante. | Naissance installée, état de Mia adapté, faux raisonnement préparé et conclusion sur la fidélité intelligible. |

Pour Kiwino, les intentions réelles confirment le mécanisme : scène 3, Cerisa seule regarde une photo ; scène 4, Bananito tient déjà le bébé ; scène 5, il ferme une valise et reste dans l'appartement. Les champs « À la fin » affirment une compréhension de la paternité et la perte du couple, sans fournir à eux seuls une scène qui les rende certaines pour le public.

## Direction recommandée : reconstruire l'écriture et son parcours

Créer un nouvel accès Histoire et un nouveau contrat d'écriture, en réutilisant les capacités utiles de références, édition d'images, usine vidéo, suivi et stockage. Un nouvel habillage seul conserverait les mêmes erreurs. Réécrire tous les moteurs de production ajouterait du risque sans traiter la causalité narrative.

Le scénario devient la pièce centrale, directement lisible : qui est là, où et quand, ce que les personnages font et leurs paroles. Un court fil causal peut guider l'auteur en interne ; il ne doit pas imposer précocement une collection de preuves, d'accessoires ou de mouvements de caméra.

Les moyens inventés par l'auteur restent modifiables jusqu'à la validation du récit. Les contraintes explicites de l'utilisateur, les répliques qu'il protège et les identités établies gardent leur statut distinct.

### Ordre de travail proposé

1. Interpréter le brief : relations, situation initiale, désirs, événement déclencheur, conséquence ou chute. Compléter les choix ordinaires et rendre visibles les hypothèses importantes, notamment univers et tonalité. Ne pas multiplier les questions lorsque le brief permet d'avancer.
2. Écrire une histoire jouable avec des actions et dialogues naturels. Installer les relations avant les ambiguïtés ; relier une suspicion à une excuse identifiable ; préparer un changement de temps et une naissance.
3. Relire ce que la scène permet effectivement de comprendre, avec possibilité de remettre en cause les moyens inventés. Un contrôle de conformité reste utile, mais ne se substitue pas au jugement éditorial.
4. Découper en clips à partir de ce récit. Adapter à la durée visée sans sacrifier silencieusement le setup, les réactions ou la conclusion ; simplifier l'intrigue ou signaler une durée insuffisante. Une scène dramatique peut nécessiter plusieurs clips ; le nombre technique de clips ne doit pas décider à lui seul du contenu narratif.
5. Préparer les références et prompts de production à partir de la version approuvée, avec les changements d'apparence correspondant aux événements. La mise en scène précise ne doit pas réinventer une autre histoire.

Ces responsabilités ne prescrivent pas cinq appels LLM ni cinq nouvelles validations UI. Première piste : une rédaction et une relecture aux responsabilités distinctes, avec correction ciblée si nécessaire et arrêt explicite si le défaut reste non résolu. Le nombre d'appels, le budget et les modèles devront être décidés lors du cadrage technique ; aucune nouvelle boucle de relances sans limite. Les IDs et contrats restent explicites dans la représentation technique, mais le raisonnement éditorial ne doit pas être dominé par un inventaire d'états/objets.

### Contrôle éditorial proposé

La relecture examine les scènes visibles/audibles avant de consulter les intentions explicatives de l'auteur. Elle restitue simplement ce qu'elle a compris des relations, de l'événement et de ses conséquences, puis confronte cette compréhension au brief. Ce principe réduit l'acceptation d'une conclusion simplement déclarée dans une métadonnée ; il ne garantit pas à lui seul la qualité d'un juge LLM.

Les constats doivent être concrets : « on ne sait pas qu'ils forment un couple », « on ne sait pas quel doute cette excuse résout », « le bébé apparaît sans naissance ni présentation ». Ils doivent pouvoir entraîner une réécriture du plan, pas seulement l'ajout d'une ligne descriptive. La relecture existante comportant déjà des instructions de lisibilité, réécrire encore la même injonction ne constitue pas une solution démontrée.

Une réplique libre générée ne devient pas intangible avant cette étape. Une fois le récit approuvé, sa fidélité en production est nécessaire ; une correction doit alors créer une nouvelle version explicite.

## UX proposée : un espace, trois vues

Bibliothèque compacte avec « Nouvelle histoire » et reprise d'un projet. À l'intérieur : **Scénario → Références → Vidéos**. Le point de départ se renseigne directement dans Scénario, sans une succession d'écrans de conception technique.

| Vue | Contenu principal | Action principale proposée |
| --- | --- | --- |
| Scénario | Idée courte au départ, puis scènes dans l'ordre : situation, actions, dialogues. Sélecteur d'épisode si nécessaire. | « Écrire le scénario », puis « Préparer les références » après relecture utilisateur. |
| Références | Personnages, décors et objets réellement nécessaires, avec leurs images et variantes. Fiches accessibles immédiatement, sélection pour génération indépendante de leur consultation. | « Générer la sélection », puis préparation vidéo de la version retenue. |
| Vidéos | Liste ordonnée des clips, statuts, lecture et retours localisés ; liens vers l'usine partagée. | « Lancer les vidéos » / reprise ciblée selon état. |

Formulaire initial compact proposé : idée, univers/aspect visuel et durée souhaitée. Distinguer espèce/univers et technique d'image : « fruits adultes » et « animation 3D » ne sont pas interchangeables. Ton, langue, modèles et paramètres détaillés restent accessibles dans Réglages ; les valeurs qui changent nettement le résultat apparaissent dans un résumé visible. Une durée par épisode et le nombre d'épisodes peuvent être proposés dans le format série, sans imposer une saga à chaque nouveau projet.

Dans Scénario, une liste sobre numérotée au centre et un détail éditable suffisent ; lecture suivie de toutes les scènes disponible. Un champ de retour unique peut viser toute l'histoire ou la scène sélectionnée. L'utilisateur peut corriger les dialogues directement ou demander une modification. Les détails de diagnostic, historiques techniques et modèles ne dominent pas l'écran.

Pas de validation séparée du concept, de l'arc, de chaque secret, de chaque micro-scène et de chaque état. Proposition : un vrai arrêt de lecture devant le scénario avant les dépenses d'images/vidéos, puis le choix habituel des références et lancement. Ce niveau de validation reste à aligner avec l'utilisateur, ce n'est pas une règle d'autorisation imposée par un fichier.

La bibliothèque doit permettre de retrouver les histoires et épisodes sans confondre leurs versions. Une retouche locale conserve les éléments inchangés. Une modification de relation ou de chronologie peut toucher plusieurs scènes : l'interface signale les parties à revoir, conserve les médias produits et ne remplace pas silencieusement une version déjà envoyée à l'usine.

## Garde-fous à conserver et complexité à retirer

À conserver : identités stables, présence distincte du dialogue, modes hors champ explicites, états visuels temporaires à durée de validité claire, continuité utile entre épisodes, références liées à des assets précis, sauvegarde/reprise/versionnement, files et historique de production partagés.

À réexaminer : plan narratif contraignant trop tôt les objets/preuves, schémas éditoriaux volumineux, états qui affirment une conclusion non jouée, pose/émotion traitée comme identité, répétitions entre plan et prompt compilé, nombre de clips prédéterminant artificiellement toute l'écriture.

La sobriété du prompt exige de retirer les obligations remplacées, pas de superposer une nouvelle politique de clarté aux anciennes. Aucun curseur « clarté » nécessaire : c'est la qualité de base attendue. Une scène peut conserver du sous-texte si la relation, l'enjeu et l'action restent compréhensibles.

## Exemples de direction, sans répliques imposées

- Un test peut être montré et accompagné d'une annonce directe ; le futur père répond à la grossesse, pas à un énigmatique « c'est officiel ».
- Une scène entre les amants peut montrer leur proximité et une inquiétude explicite au sujet du mari. Elle établit le contexte pour le public sans révéler prématurément le secret au mari.
- Après un saut temporel, présenter le bébé et le moment familial avant d'utiliser sa ressemblance comme retournement.
- La séparation doit nommer clairement sa cause et la décision prise ; une photo retournée peut renforcer cette décision, mais ne devrait pas être sa seule expression.

Ce sont des critères de lisibilité pour les cas signalés, pas quatre nouvelles obligations identiques à injecter dans tous les prompts.

## Périmètre et qualification proposés

Premier périmètre : histoires courtes dialoguées, autonomes ou regroupées en quelques épisodes. Prévoir la continuité et la reprise d'épisode dès la conception ; réserver les parcours de sagas complexes à une décision ultérieure. Ne pas supprimer automatiquement les anciennes histoires ni leur parcours ; proposer un accès historique pendant l'évaluation du nouveau.

Commencer la qualification par deux scénarios, Kiwino et la copine, avant de payer des rendus complets. Critères : relations reconnues sans résumé externe, intention de chaque action majeure comprise, dialogue répondant à une information identifiable, ellipse explicable, grossesse/naissance situées, révélation et conséquence reformulables par un lecteur. Les retours de l'utilisateur constituent les cas à faire réussir, pas une promesse que tous les récits seront garantis.

Qualifier ensuite quelques passages audiovisuels importants, puis une chaîne complète. Mesurer temps complet, nombre de reprises et défauts réels, avec mêmes briefs et réglages lors des comparaisons. Aucun essai LLM ou rendu n'est autorisé au titre de ce document. Aucun changement de modèle conseillé comme remède démontré.

## Points encore ouverts pour la discussion

- Valider le principe du scénario complet à relire avant les références et les trois vues proposées.
- Préciser le périmètre initial des séries/suites à conserver ; proposition actuelle : épisodes courts, pas uniquement histoires isolées.
- Après accord sur ce parcours, dessiner une maquette compacte et préciser les contrats/rôles, puis seulement demander ou recevoir l'autorisation d'implémenter. Ne pas transformer l'alignement actuel en chantier automatique.
