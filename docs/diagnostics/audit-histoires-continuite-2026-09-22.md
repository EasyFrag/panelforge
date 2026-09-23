# Audit — lisibilité dramatique et continuité visuelle

Date : 22 septembre 2026. Discussion et proposition, sans modification du moteur ni des projets en production.

## Conclusion

Les trois problèmes signalés ont des fondements concrets, à des endroits différents du parcours :

1. **Pommes : les relations existent dans le brief et la bible, mais ne sont pas suffisamment établies dans ce que voit ou entend le spectateur.** Une intrigue médicale ajoutée prend ensuite la place du simple adultère attendu.
2. **Citron : le scénario décrit la transformation, mais la fabrication n'a pas de registre persistant des états visuels.** Chaque clip réinterprète une image de référence initiale et son texte local. Les prompts contiennent déjà des pertes de continuité, indépendamment du résultat vidéo encore incomplet.
3. **Kiwina : l'objet central n'a aucune référence propre.** Les images extraites des deux premiers clips montrent une différence nette de forme entre deux représentations de la même invention.

Je recommande de conserver la chaîne de fabrication et de renforcer son entrée : une dramaturgie plus directe, un registre limité des éléments importants et une transmission explicite de leurs états. Ajouter davantage de consignes générales ou multiplier les relectures ne suffit pas.

## Périmètre et preuves

Sources lues : scénarios, arcs, contrats, réglages, bilans éditoriaux, fiches de fabrication, références, préparations, plans REF2V, prompts finaux et extraits ciblés des raisonnements enregistrés. Inspection visuelle : référence Citron, planches des deux premiers clips produits de chacun des trois épisodes, puis clips 3–4 de Citron terminés pendant l'audit. La transcription existante de Download(21) a été consultée pour la présentation initiale.

Les planches sont des prélèvements d'images, pas une lecture audiovisuelle intégrale. Aucune écoute ou nouvelle transcription n'a été effectuée. Les remarques sur les paroles concernent les textes enregistrés ; elles ne certifient pas leur restitution audio. Une omission de prompt est distinguée d'une erreur effectivement observée dans les images.

| Cas | Projet histoire | Fabrication examinée |
| --- | --- | --- |
| Citron | `story-a964cdcc86584d5aba3b364d989b0963` | `episode-c879378d049d4f8296d739144e52c195` — La suite : le muscle et la banane |
| Pommes | `story-9ddd34b57dc549d2bc959d9c735ac0ec` | `episode-ee4cc16650a546e9981d509c4570db9d` — Le dîner du charmeur |
| Kiwina | `story-66c09b0ce97046258bb2d2ff3529b8ea` | `episode-5911543f659b441cb82e7c9ed459a46f` — La pièce cassée |

Copies de travail et captures locales : `D:/Code/panelforge/workspace/experiments/audit-histoires-continuite-2026-09-22/`. Les traces complètes restent hors du dépôt source.

À 13 h 53, heure de Paris : Citron 1 et 2 terminés, avec sorties DLSS présentes dans les projets de rendu ; clip 3 en cours, clips 4 et 5 en file. Les cinq prompts sont prêts. Aucun nouvel échec enregistré dans ces tentatives à cette lecture. Le journal d'épisode peut être moins à jour que les projets de rendu : il ne faut pas assimiler tous ses états « rendering » à des exécutions simultanées.

Mise à jour à 14 h 00 : clips 3 et 4 également terminés, clip 5 encore en file. Les captures complémentaires confirment une transformation musculaire très visible en fin de clip 4, mais aussi une Banane différente de celle du clip 3. Ces nouvelles sorties sont prises en compte ci-dessous.

L'arc des pommes vient de contrats 2.0 ; son développement final utilise 2.1. Ce projet ne constitue donc pas un essai entièrement neuf de la conception 2.1. Citron comporte six appels narratifs 2.1, tous acceptés et terminés avec `finish_reason=stop`.

## 1. Pommes : pourquoi la tromperie est moins claire

### Une relation fondamentale reste hors écran

Le brief dit explicitement qu'un fils présente sa copine. La première réplique du scénario est pourtant :

> Papa, voilà Fraise !

La transcription existante de la référence commence par :

> Papa, je te présente ma meuf.

Cette différence est déterminante. « Voilà Fraise » présente une personne ; « ma copine » établit immédiatement le couple et donne son sens au flirt du père. La logline ne remplace pas cette information dans la vidéo. Les captures montrent des regards expressifs, mais pas une présentation visuelle du couple qui suffirait à compenser cette omission.

Autre faiblesse du casting observé : Pom a des proportions très enfantines. Pour cette histoire entre adultes, il faut une fiche de **jeune homme adulte**, un gabarit et des vêtements cohérents, plutôt que laisser « jeune pomme naïve » dicter son apparence. C'est aussi une question de lisibilité des rôles familiaux et amoureux.

### Le premier épisode multiplie les intermédiaires

Le scénario fabriqué suit : présentation → verre partagé → diagnostic absurde → départ sous prétexte médical. Il contient quatre personnages, et le médecin apparaît sans que la scène d'arrivée soit racontée. Il manque surtout une conséquence concrète du rapprochement : le spectateur doit interpréter « stimulation douce au jus » et le départ comme une liaison.

Les premiers regards et la réceptivité de Fraise fonctionnent sur le papier et dans les captures. Le problème est ce que le récit leur fait porter : des sous-entendus doivent à la fois établir le couple, le désir, le prétexte, la complicité du médecin et la naïveté du fils.

La seconde unité prévue ajoute brunch, carte « thérapie du jus », billet pour deux, cadeau vide, pacte et fils utilisé comme appât. Cet empilement n'est pas nécessaire pour raconter que la copine couche avec le père dans le dos du fils.

### Le raisonnement montre l'origine de la dérive

Trace de conception : `llm-2a4067718f57481a9f2ab1fb01cf3d43`.

- Le champ d'univers comportait « médecin ananas ». Le modèle reconnaît que le brief ne demande pas son intervention, puis considère qu'il doit probablement l'intégrer. **Une indication de casting disponible devient une obligation d'intrigue immédiate.**
- Le réglage explicite « retournement » conduit à chercher une machination plus grande que l'attirance réciproque : départ prémédité, fils-appât et médecin complice.
- L'arc ainsi produit devient ensuite la référence à respecter. La fidélité à cet arc protège aussi ses inventions inutiles.

Ce n'est donc pas seulement un modèle qui ignore le brief. Des indications valables ont été surinterprétées, puis verrouillées trop tôt.

### La relecture raisonne avec trop d'informations

Dernière relecture : `llm-db04eb7bf15c4b87813b4f6f191c5d84`.

Elle valide le rapprochement et le secret, puis insiste sur la durée d'un clip, le rangement absent de la cuisine et le cadeau vide. Elle ne relève pas l'absence de « ma copine ». Elle connaît déjà la relation grâce au brief et à l'arc : sa compréhension de l'intention lui fait accepter une exposition insuffisante.

Les consignes actuelles demandent déjà de ne pas prendre un état final pour une preuve. Cette bonne consigne ne suffit pas : le contenu présenté au relecteur et les questions prioritaires doivent changer.

### Direction recommandée pour l'épisode 1

Trois adultes, une maison, une tromperie et une fausse explication. Cinq battements possibles, sans quota obligatoire de clips :

| Battement | Ce que comprend le public |
| --- | --- |
| Le fils présente clairement « ma copine » ; geste de couple | Qui est avec qui, et qui est le père |
| Compliment du père ; réponse et regard réceptifs | Attirance réciproque |
| Le père propose la visite ; elle le suit ; le fils les laisse faire | Occasion de tromper sans témoin |
| Extérieur de la même maison qui tremble, avec ellipse comique | Rencontre intime suggérée hors champ |
| Elle redescend essoufflée ; excuse banale ; le fils y croit | Le public sait, le fils se trompe ; chute locale suffisante |

Il n'est pas nécessaire de révéler la liaison au fils ou d'introduire un nouveau complice pour réussir cette fin. La crédulité maintenue est déjà le résultat dramatique.

Pour un prochain essai avec le modèle actuel : Mélodrame, une unité, environ 40–50 secondes, cinq clips maximum, français familier naturel, fin ouverte. « Narration explicite » peut aider à rendre les relations audibles ; elle n'impose pas une voix off. Univers limité aux trois pommes adultes et à la maison pour cet épisode. Le choix « retournement » peut être remis lorsqu'une inversion supplémentaire est réellement voulue. Ces réglages constituent un point de départ, pas une garantie de fidélité.

## 2. Citron : récit prometteur, continuité fragile

### Ce qui fonctionne

Le récit suit bien une chaîne simple : humiliation → effort → changement physique → intérêt de Banane → Pêche perd son ascendant. Le contact des mains de part et d'autre de la vitre rend le rapprochement visible. L'épisode atteint les deux objectifs demandés dans le texte : muscles et romance.

La transformation n'est donc pas entièrement oubliée par le système. Le Plan de la scène 3 stipule même que les bras massifs persistent pendant tout le clip. Les images prélevées en scène 2 montrent Citron plus large sous son vêtement. Dans la scène 3 terminée pendant l'audit, les bras massifs restent peu lisibles et le jogging apparaît ample. En fin de scène 4, le torse devient nettement musclé et le vêtement se déchire : ce résultat est bien visible, pas seulement déclaré dans un texte.

### Ce qui se perd entre les étapes

| Scène | État raconté | Transmission à la vidéo |
| --- | --- | --- |
| 1 | Citron encore frêle, déterminé | Image initiale de Citron en jogging ample |
| 2 | Épaules et biceps gonflent, vêtement tendu | Transformation bien demandée dans le prompt |
| 3 | Bras désormais massifs | Maintien explicite des gros bras et des manches tendues |
| 4 | Nouvelle amplification, coutures déchirées | Le Plan recommence par « loose gray jogger », sans rappeler la carrure déjà acquise |
| 5 | Citron garde sa nouvelle carrure | Gros bras conservés, mais vêtement décrit comme tendu ; déchirures non reprises |

La même image `asset-bebe0345145d495f81126a93c4e5afc9`, visuellement frêle, est utilisée pour Citron dans toutes les préparations. Aucun résultat transformé n'est sélectionné comme référence de sa nouvelle apparence.

**Continuité de l'état intermédiaire mal lisible dans les captures ; maintien de la transformation finale encore à vérifier.** Il ne faut pas confondre ces deux observations : le grand changement de la scène 4 fonctionne, mais la sortie de scène 5 n'était pas encore disponible pour vérifier sa persistance.

### Autres défauts concrets

- Banane est présente dans l'ouverture de la scène 4, mais absente de `character_ids`. Elle n'a donc ni image ni description transmise dans ce clip. Le Plan le remarque et décide de la traiter comme une autre observatrice peu définie. Trace : `llm-90c03278fa9a41029d3c43d87a8df3b5`. **Écart visible confirmé dans les nouvelles captures** : Banane passe de la femme à tête de banane en tenue rose/bleue/violette à une silhouette jaune en forme de banane portant un ensemble noir. L'absence de référence est documentée ; on ne peut pas isoler expérimentalement son effet de tous les autres paramètres, mais elle laisse clairement le générateur réinventer ce personnage.
- En scène 5, « Pêche reste sur le seuil, minuscule » et « Pêche est abattue » deviennent une Pêche de petite taille qui finit allongée au sol. Le Plan transforme une humiliation figurée en changement physique et chute ajoutée. Trace : `llm-178adb3d97c84b019d2ae6f641800ac4`. Le prompt final conserve cette interprétation.
- « Une heure écoulée » conclut une suite de scènes sans ellipse temporelle claire. Une heure diégétique peut tenir en quelques secondes de film, mais le passage du temps doit être perceptible.
- Les questions financières occupent encore l'amorce et les fils ouverts. Dans le contrat Citron, le rapprochement romantique explicitement demandé figure dans `freedoms`, alors que le contexte bancaire et la salle verrouillée occupent `must_keep`. Le récit finit par livrer le rapprochement, mais cette hiérarchie des obligations est mal placée.
- Les préparations et prompts annoncent tous 10 secondes. Les durées de rendu enregistrées sont 9, 8, 9, 8 et 10 secondes. La scène 3 est déjà estimée à 10,5 secondes par le diagnostic narratif. Réduire sa vidéo à 9 secondes laisse moins de place aux gestes et à la réaction. Cela ne justifie pas de modifier silencieusement les prompts : il faut rendre l'écart visible.

### Le passé fourni est mélangé à la demande courante

Ce projet a `parent_story_id: null` : la continuité repose ici sur l'ancien épisode collé dans le brief. La conception passe un long moment à hésiter entre continuer cet épisode et rejouer ses répliques « à prononcer exactement ». Ces instructions appartiennent au récit précédent, pas nécessairement à la nouvelle commande.

Il faut distinguer dans le contexte : demande actuelle, épisode antérieur, faits acquis et éléments disponibles. Les deux objectifs nouveaux — romance et transformation — doivent avoir la priorité sur les anciennes instructions de mise en scène.

## 3. Objets : où placer le curseur

### Kiwina fournit un cas clair

En scène 1, Frambosa prend la boîte contenant la graine-circuit et remet une puce cassée à Kiwina. En scène 2, elle prétend avoir inventé la graine-circuit et la dépose dans un coffre.

Les captures montrent une invention plate ressemblant à une tranche de kiwi dans la boîte, puis un appareil ovoïde avec un centre électronique et des excroissances. L'objet est narrativement le même, mais n'a pas de forme canonique. Les prompts utilisent seulement « intact seed-circuit » puis « seed-shaped circuit device ». Les fiches comprennent quatre personnages et deux lieux ; aucune fiche objet.

Le coffre, déjà présent dans la référence de décor, reste beaucoup plus reconnaissable dans ces images. C'est aussi la preuve qu'une fiche séparée n'est pas nécessaire pour tout.

Attention : la **puce cassée remise à Kiwina** n'est pas automatiquement un état cassé de l'invention volée. Dans ce scénario, ce sont deux objets distincts. Les fusionner parce qu'ils partagent le mot « graine » créerait une nouvelle erreur de causalité.

### Critère de sélection proposé

Question centrale : **si cet objet change d'apparence, perd-on une information ou une reconnaissance importante ?**

| Niveau | Traitement | Exemple |
| --- | --- | --- |
| Décor courant | Laisser dans la description ou la référence du lieu | Chaise, tapis, verre banal |
| Objet suivi | Nom stable, quelques attributs, détenteur et état | Clé ordinaire dont seul le transfert compte |
| Objet à reconnaître | Fiche et image commune, seulement pour les scènes concernées | Invention de Kiwina, flacon distinctif retrouvé dans plusieurs scènes |

Une ou deux occurrences ne suffisent pas, à elles seules, à justifier une génération. Un objet que le public doit reconnaître, un objet inventé difficile à décrire ou une preuve visuelle centrale la justifient davantage. À l'inverse, un objet montré une seule fois peut mériter une référence si sa forme complexe est indispensable. Pas de quota artificiel ; viser souvent quelques éléments seulement.

## 4. Diagnostic du code actuel

- `domain/story_contracts.py`, `character_schema`, `state_schema`, `scene_schema` : personnages décrits par une fiche globale ; faits et connaissances ; pas d'identité d'objet ni d'état physique persistant par personnage. `visual_transition` peut décrire une transition locale, mais ne constitue pas un état hérité par les scènes suivantes.
- `domain/long_stories.py`, `fabrication_scenario` : la projection injecte notamment l'évidence narrative dans l'action. Elle ne calcule pas un registre visuel à l'entrée de chaque scène.
- `domain/episodes.py`, `initial_episode` : création de références uniquement pour `characters` et `locations`.
- `domain/episodes.py`, `scene_inputs` : une image sélectionnée par fiche ; aucune variante par scène. Les personnages avec image sont transmis par nom et image, sans leur description narrative complète. Les personnages omis de `character_ids` ne sont pas récupérés depuis la prose.
- `application/episodes.py`, `_inherit_character_images` : héritage du casting disponible entre fabrications apparentées, mais pas de choix de variante selon une transformation.
- Le Plan REF2V possède des invariants de continuité **dans le clip**. Il est produit à partir d'un contexte local ; cela ne garantit pas la continuité entre clips.

Le système dispose donc déjà de briques utiles. Il manque le lien explicite entre identité, état courant, scène et référence visuelle.

## 5. Proposition d'évolution à aligner

### A. Raconter un drame évident

Conserver les profils existants, sans créer un mode spécial pour chaque exemple. Donner davantage de poids à trois exigences :

1. Les relations nécessaires sont établies par une parole naturelle ou un geste sans ambiguïté.
2. Chaque épisode suit un désir et une chaîne causale faciles à reformuler ; une complication nouvelle doit servir cette chaîne.
3. Les faits décisifs ont une preuve à l'écran. Une formule dans la bible, un secret ou un état final ne compte pas comme une scène jouée.

La tromperie peut être très claire pour le public sans être révélée au fils. Une fin locale ne doit pas forcer une conspiration, une punition ou un aveu. Dans Citron, le rapprochement peut reposer sur le soutien de Banane avant la transformation, puis sur un geste affectueux après : cela évite de réduire tout son intérêt aux biceps.

Utiliser la relecture existante pour vérifier ce qu'un spectateur peut réellement déduire des paroles et gestes. Lui présenter une vue de lecture qui retire les conclusions de `ending_state`, les explications de `evidence` et les secrets non montrés. Lui demander les relations et changements compris, avec leur preuve. Comparer ces réponses au contrat. L'arc reste vérifié dans son étape actuelle ; aucun nouvel appel systématique n'est nécessaire pour un « lecteur » supplémentaire.

### B. Séparer identité et états persistants

Pour Citron : une identité ; un état initial frêle ; éventuellement un stade intermédiaire ; un état final très musclé et vêtement déchiré. L'état final d'une scène devient l'état d'entrée de la suivante jusqu'à changement explicite. Même principe pour une blessure, une coiffure, un costume, un objet cassé ou un transfert de possession.

Ne pas produire automatiquement une image de chaque variation intermédiaire. Une transformation majeure qui dure plusieurs scènes mérite une variante de référence. Une modification légère peut rester textuelle. Pour une transition graduelle, conserver les bornes utiles ; si le scénario n'a pas besoin de deux poussées musculaires, une seule transformation nette simplifie aussi la production.

La référence initiale fournit l'identité ; la variante fournit l'apparence acquise. Les consignes doivent attribuer ces rôles sans envoyer deux personnages concurrents. Une variante peut provenir d'une édition guidée de l'image initiale, ou d'une image extraite et validée d'un rendu. Ne pas adopter automatiquement une image ratée comme nouveau canon. Qwen peut servir à préparer une variante, sans remplacer le pipeline vidéo ; sa fidélité sur ce cas reste à tester.

La narration donne les changements d'état dans les appels existants. Le code propage ces états et résout les références ; pas besoin d'un LLM supplémentaire pour recopier « reste musclé » cinq fois.

### C. Ajouter les objets importants à cette même continuité

ID stable, fonction dramatique, description visuelle courte, scènes concernées, détenteur, état et référence facultative. Les objets incidents restent dans le décor. Une fiche objet ne doit pas être obligatoirement un preset global : elle peut appartenir uniquement à cette histoire, avec promotion au catalogue si l'auteur veut la réutiliser ailleurs.

Limiter les références réellement envoyées à celles qui servent le plan. L'actuel parcours REF2V accepte neuf images par scène, personnages et décor compris : éviter de saturer ce budget avec tous les accessoires. Réutiliser une vue de lieu lorsque l'objet en fait déjà partie et reste lisible.

### D. Une interface courte

Avant Fabrication, un bloc **Continuité** repliable, avec décisions proposées automatiquement :

- Citron — frêle au départ ; transformation ; musclé ensuite ; tenue déchirée après la scène 4.
- Graine-circuit — même objet en scènes 1 et 2 ; détenu par Kiwina puis Frambosa.
- Les autres accessoires — descriptions simples.

Chaque ligne explique « pourquoi cet élément est suivi » et propose les actions utiles : corriger, ignorer, choisir/générer une référence, déplacer le début d'un état. Dans chaque carte scène, afficher seulement les variantes ou changements significatifs. Aucun nouveau groupe de curseurs.

Un bref résumé du drame doit être également visible : « le fils croit à une visite ; le public comprend la liaison ». Cela permet d'intervenir avant de produire les personnages et les vidéos, sans réécrire tout l'arc à la main.

### E. Vérifications proportionnées

Contrôles locaux sur les IDs, le choix de variante, les transitions explicites et les références présentes. Les remarques éditoriales restent des avertissements utiles, pas de nouveaux rejets arbitraires avec boucle de réécriture. Une ambiguïté réelle doit désigner le passage à corriger, sans relancer un récit complet.

Signaler aussi la différence entre durée préparée et durée de rendu. Conserver le choix manuel de l'auteur ; ne pas modifier le prompt, la durée ou les rendus terminés sans demande.

Compatibilité : champs nouveaux facultatifs/versionnés, anciennes histoires lisibles, fabrication existante conservée, instantanés des références par tentative. Une correction ultérieure ne doit pas réécrire l'historique d'un rendu ni modifier une génération déjà envoyée.

## 6. Coût et ordre recommandé

Citron : six appels narratifs acceptés, environ 10 min 43 s cumulées d'appels ; édition d'arc et deux relectures occupent environ 57 % de ce temps. Les longues traces répètent surtout des arbitrages de format, de fidélité et de budget. La dernière relecture affirme même que Pêche n'énonce pas de moquerie audible dans l'unité, alors que « Sans oseille, t'es rien, microbe ! » ouvre la première scène. Une longue réflexion n'est donc pas un contrôle fiable en soi. Les tokens réels n'étant pas fournis dans ces traces, aucune économie de tokens n'est chiffrée.

Ordre proposé :

1. Corriger la priorité des informations : demande actuelle / passé / univers disponible ; relations visibles et relecture centrée sur le spectateur.
2. Ajouter les états visuels persistants et leur transmission à la fabrication. C'est la protection contre la régression de Citron et les vêtements qui se réparent seuls.
3. Étendre cette continuité aux rares objets qui le nécessitent et à leurs images. Kiwina est le premier cas concret à vérifier.
4. Ajouter le résumé UX et les avertissements de durée, puis faire les essais réels avec l'utilisateur.

Critères de réussite : on identifie le couple avant le flirt ; on comprend la tromperie sans lire le résumé ; Citron conserve son état acquis ; la déchirure persiste ; l'invention se reconnaît malgré le changement de détenteur ; les mots « abattue » ou « minuscule » ne créent pas d'action physique non demandée ; un personnage explicitement visible ne perd pas sa référence parce qu'il ne parle pas.

Aucun code applicatif changé dans cet audit. Aucun test, appel LLM, génération, redémarrage ou modification d'un projet utilisateur effectué. Attendre l'alignement avant implémentation.
