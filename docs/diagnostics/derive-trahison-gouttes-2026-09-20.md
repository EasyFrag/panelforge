# Audit de la dérive narrative des gouttes — 20 septembre 2026

La dérive est réelle : **L’eau qu’on donne** conserve épouse, mari, médecin et issue cruelle, mais organise une fable sur le sacrifice qui détruit l’identité. La référence organise une tromperie consciente, une complicité et une élimination. La différence porte sur les responsabilités des personnages et l’émotion produite, pas seulement sur le vocabulaire.

## Périmètre et sources

- Dernière histoire passée en Fabrication : **L’eau qu’on donne**, `story-fcd6917016b04555bf7dd96e367e0d83`, version de stockage 415, révision narrative 14, fabrication `episode-dbeb0e1642a44404b2cf5d83e4ee397b`.
- Projet créé ensuite : **La Goutte trahie**, `story-bc3c97f1549c4853bd02eb0eb027f34a`. Son scénario existe aussi ; il est examiné séparément pour ne pas confondre dernière création et dernière fabrication. **La dernière trace**, `story-3ac069f9aeb3435ba5f27e9e439acada`, fournit un troisième point de comparaison au stade de l’arc.
- Référence : le MP4 AQO fourni, 47,808 s. Réexamen de sa planche horodatée toutes les quatre secondes et de sa transcription locale déjà produites lors du premier audit. Baiser vers 4 s, soins domestiques vers 12–16 s, complicité et boisson vers 24–28 s, préparation et ingestion vers 32–36 s, véhicule d’intervention vers 40 s et nouvelle union vers 44 s. La transcription vers 23,5–28,2 s confirme le projet des amants. Le décès n’est pas constaté médicalement à l’écran dans les éléments examinés ; l’empoisonnement et l’élimination de l’épouse sont suggérés par l’enchaînement.
- Analyse textuelle intégrale du scénario retenu, de son concept initial, du contrat, des versions et des relectures, puis des prompts réellement envoyés. Les seules différences des cinq actions lors de leur transfert en Fabrication sont l’ajout des informations indispensables à rendre visibles ou audibles. La dérive est donc déjà présente dans la rédaction.
- Cet audit ne mesure pas la qualité audiovisuelle des cinq rendus ni leur mixage. Aucun test, génération, appel LLM ou redémarrage effectué. Aucun code applicatif ni projet enregistré modifié.

Les pièces sélectionnées, avec les prompts et réponses utiles, sont conservées dans [evidence.json](D:/Code/panelforge/workspace/experiments/audit-derive-gouttes-2026-09-20/evidence.json). La [planche de référence](D:/Code/panelforge/workspace/experiments/audit-stories-2026-09-20/aqo-1.jpg) et la [transcription](D:/Code/panelforge/workspace/experiments/audit-stories-2026-09-20/aqo.json) restent disponibles.

## Le changement de registre

| Dimension | Référence AQO | L’eau qu’on donne |
|---|---|---|
| Fonction des gouttes | Apparence de personnages vivant dans un monde social familier : hôpital, maison, cuisine, transport, mariage | Matière qui impose le fonctionnement du récit : transfert d’essence, reflets, pluie, évaporation |
| Épouse | Personne dévouée dont la confiance est exploitée | Donneuse qui épuise son corps et altère l’identité de son mari |
| Mari | Participe à une liaison et à une manœuvre contre son épouse | Subit un effacement, retrouve son identité, choisit la médecin |
| Médecin | Complice amoureuse dans la préparation d’une boisson suspecte | Professionnelle qui identifie et retire une essence étrangère |
| Secret | Ce que les amants font derrière le dos de l’épouse ; le spectateur en sait davantage | La nature des soins et leurs effets surnaturels |
| Cruauté | Des personnes prennent des décisions nuisibles et profitent du dévouement | Une règle fantastique rend le dévouement destructeur et conduit à la disparition |
| Émotion dominante attendue | Indignation, tension, sentiment d’injustice devant une trahison | Tristesse, malaise, lecture symbolique de l’effacement de soi |

Dans le scénario, le diagnostic de la médecin est explicite : **« Ce n’est pas une maladie. C’est une intrusion. »** Son action rend au mari son visage original. Cette causalité fournit une justification au départ du mari et fait de l’épouse une source involontaire du problème. L’abandon reste cruel, mais la responsabilité morale des amants est atténuée. C’est une interprétation étayée par leurs actes et par les règles écrites, pas une accusation d’intention cachée du modèle.

La référence révèle déjà la liaison au public au début. Son intérêt n’exige donc pas une révélation finale sur la nature du soin. Il vient aussi de l’attente : l’épouse ignore ce que le public voit, continue de se dévouer, puis subit les conséquences du projet des amants.

## Où la dérive apparaît et se fixe

1. **Brief transmis.** Le modèle reçoit : « Des gouttes d’eau anthropomorphes. Une femme soigne son mari malade, mais il tombe amoureux de sa médecin. Je veux un mélodrame visuel cruel dont la fin change complètement le sens des soins du début. » La requête ne contient ni la vidéo, ni ses images, ni une analyse de ses événements. Le champ `images` est vide. Le contexte de notre échange n’est pas automatiquement celui du moteur PanelForge.
2. **Première proposition, révision 1, vers 13 h 37 à Paris.** Qwen invente déjà le transfert d’identité, l’évaporation et « La règle de l’eau » comme antagoniste. La cause principale précède donc le rédacteur, les erreurs de format et les reprises ultérieures. Appel : `llm-239d7701bb5240bb8a913d7314c3c52a`.
3. **Contrat, révision 2.** Le modèle inscrit sa règle inventée dans `must_keep`, à côté des demandes de l’auteur. Il ajoute dans `freedoms` : **« Rendre Litchi professionnelle et non méchante »**. Une interprétation du modèle devient ainsi une contrainte à préserver, et l’innocuité de la médecin une possibilité explicitement encouragée. Appel : `llm-5b062e712dc04dc1bb7caf19d99f37aa`.
4. **Relectures de l’arc, révisions 3 et 5.** Elles jugent l’arc conforme. La première identifie un vrai maillon manquant : le passage de la goutte de l’épouse au mari doit être montré. La seconde insiste sur la lisibilité de son attirance pour la médecin. Elles renforcent la cohérence de l’invention sans remettre en cause le remplacement de la trahison par une libération identitaire.
5. **Développement, révision 12.** Gemma met cet arc en scènes et ajoute notamment le diagnostic d’« intrusion ». Sa réponse annonce elle-même un sacrifice « cruel et contre-productif ». Le rédacteur suit majoritairement la direction déjà retenue.
6. **Relecture finale, révision 14.** Elle valide la fidélité au brief et la requalification des soins comme effacement ; ses remarques concernent l’extraction d’une seule goutte, la prise de conscience et les souvenirs non montrés. Elle ne relève pas l’absence de tromperie organisée. Appel : `llm-d64f6bfc21c64225abe188d48d443c7c`.

Le même modèle de conception, `local::unsloth/Qwen3.8-27B-GGUF`, produit les propositions et les relectures. Ces dernières sont des appels séparés ; il serait abusif d’y voir une simple continuation de conversation. Elles reçoivent néanmoins le concept et le contrat construits par ce modèle, ce qui peut favoriser la conservation de sa première interprétation. Changer uniquement de relecteur ne réparerait pas une référence éditoriale insuffisamment définie.

## Les causes, par importance

**La référence a été résumée de façon trop ouverte.** « Tomber amoureux » autorise une attirance sincère ; cela ne précise ni mensonge, ni duplicité, ni complicité. « Fin cruelle » autorise une mort accidentelle ou un sacrifice tragique. « Changer le sens des soins » encourage une nouvelle explication des soins eux-mêmes. Ces formulations couvrent plusieurs genres. Cette run respecte une lecture possible de son brief local tout en manquant la cible exprimée dans notre échange. La réduction de la référence et les réglages proposés n’ont pas suffisamment protégé cette cible.

**L’univers visuel est devenu le moteur causal.** Bien que le prompt dise de séparer univers et profil, les gouttes déclenchent ici eau, essence, reflets et évaporation. Le modèle consacre les cinq clips à rendre cette mécanique compréhensible. La référence consacre une durée comparable à des actions sociales ordinaires. L’effet est observable ; on ne peut pas mesurer, sur ces seules runs, quelle part revient aux associations du modèle ou à chaque consigne.

**Les inventions ont acquis trop tôt le statut d’exigences.** La stabilité des IDs et du contrat est utile pour produire. Mais le contrat mélange des volontés de l’auteur et des décisions du modèle. Une fois « règle de l’eau antagoniste » verrouillée, les étapes suivantes doivent préserver la cause même de la dérive.

**La relecture vérifie surtout la conformité à cette interprétation.** Ses consignes incluent bien fidélité au brief et promesse abandonnée : le contrôle n’est pas absent. Il reste trop général. Il ne demande pas explicitement quel personnage trompe qui, quel acte prouve cette tromperie, ce que sait la victime et quel sentiment doit provoquer la fin. Une architecture cohérente peut donc recevoir une validation alors qu’elle produit une autre expérience.

**Les options ne distinguent pas les sous-registres nécessaires.** Mélodrame / visuel / retournement conviennent aussi à une tragédie poétique de sacrifice. Visuel n’implique pas muet, mais peut être interprété comme une invitation aux métaphores matérielles ; la référence utilise justement une courte réplique décisive pour préciser le projet des amants. Le registre de dialogue 1 règle l’oralité des paroles, pas la cruauté ou la responsabilité des personnages.

Aucune trace examinée ne montre un refus de représenter une trahison ou une consigne imposant de rendre les personnages innocents. Attribuer cette dérive à une censure, au DLSS ou à la génération vidéo ne serait pas étayé.

## Le cas de La Goutte trahie

Ce projet ultérieur reçoit une intention minimale explicite : « Une trahison amoureuse entre des gouttes d’eau, avec une fin cruelle. » Le mot trahison est conservé, et Source quitte effectivement Larme pour Rivage. Il y a donc une amélioration sur cet élément précis.

Le récit reste pourtant une fable de matière et de survie : fusion sur une feuille, attraction, absorption de petites gouttes, arrachement forcé, réunion possessive, chute et évaporation. Le dommage final vient de la réunion et de la chute ; il ne résulte pas d’un projet cruel des amants. La victime participe activement à cette issue en forçant la réunion. Ce n’est pas la même mécanique que l’exploitation clandestine d’une épouse confiante.

L’arc reçoit une relecture sans problème restant. Le scénario reçoit seulement des remarques sur la flaque, la pierre et la trajectoire de chute. Les consignes récentes contre l’accumulation de symboles et le verrouillage des premières inventions figurent déjà dans le prompt de conception effectivement envoyé. Elles n’ont pas suffi dans ce cas. **La dernière trace**, au stade de l’arc, réutilise aussi feuille, chaleur, survie et absorption : cela constitue un signal récurrent dans ces quelques exemples, pas une mesure générale de fiabilité.

## Direction proposée pour le moteur, sans implémentation

Il faut préserver une promesse dramatique plus précise dès la conception, puis la vérifier dans la relecture existante. Cela ne nécessite pas, à ce stade, davantage d’appels ni une nouvelle rangée de sélecteurs.

- Pour cette cible, exprimer une **tromperie volontaire**, une confiance exploitée, une complicité, des actes qui établissent les responsabilités et une conséquence cruelle préparée. Les gouttes peuvent conserver une apparence liquide tout en vivant un drame social. Une physique fantastique reste possible quand elle est demandée ou sert cette promesse sans la remplacer.
- Distinguer les contraintes de l’auteur des choix de conception révisables. Ne pas présenter les noms ou une règle inventés comme des obligations initiales de l’utilisateur.
- Faire présenter la direction en une phrase lisible avant le détail : « Une épouse confiante continue de soigner son mari pendant que celui-ci et sa médecin préparent sa disparition. » Cette formulation est un exemple de cible pour la référence, pas un scénario obligatoire pour toutes les histoires.
- Faire citer au relecteur les actes qui portent la promesse : qui cache quoi, qui profite de quoi, qui prend la décision nuisible, et pourquoi le dénouement en est la conséquence. En leur absence, corriger l’arc avant de perfectionner ses accessoires.
- Vérifier la lisibilité humaine des actions. Un geste affectueux, un mensonge et un objet détourné peuvent exprimer davantage que plusieurs transformations d’identité difficiles à reconnaître en dix secondes.

Une fable de sacrifice peut rester un résultat légitime si l’auteur veut ce registre. Le moteur doit savoir l’annoncer et éviter de l’assimiler automatiquement à une vidéo de tromperie. Les prochains essais doivent comparer ces critères sur les textes avant la fabrication, avec les modèles et budgets habituels ; leur exécution reste du côté de l’utilisateur.
