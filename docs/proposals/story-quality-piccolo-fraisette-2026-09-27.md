# Audit d’écriture — Fraisette et Piccolo — 27 septembre 2026

Périmètre : lecture des prompts réellement envoyés, réponses, raisonnements exposés, versions et fabrication enregistrées. Aucun appel LLM, rendu, test ou redémarrage lancé. Le run Piccolo s’est terminé pendant l’audit. Ces conclusions portent sur l’écriture et la préparation des références, pas sur la qualité de vidéos finales non examinées.

## Sources reproductibles

Runtime : D:/Code/panelforge/workspace. Checkout : D:/Code/panelforge-krea2-flux.

- Fraisette avant refonte : story-c994ccbffcc74be98cf709b1b957e94f, contrat 2.3.0, visual_state_policy=1, « Une petite vie ». Fabrication episode-ff7710c04f0f4309bc065d2e14d1f103.
- Fraisette après refonte : story-43f098f0736442ef966f74f3a3387e1b, contrat 2.4.0, policy=2, « L’annonce de Fraisette ». Fabrication episode-ade78190b432447da072c569d9b9af9a.
- Piccolo : story-18c12bf9b9ac46109242a6a728b14bc6, contrat 2.4.0, policy=2, « Les vingt mille balles » / scénario « Le test du portefeuille ».
- Copies d’audit et métriques : D:/Code/panelforge/.agent/diagnostics/story-quality-2026-09-27. Les fichiers <projet>-<opération>-system_prompt/user_prompt/response_text/reasoning_text.txt permettent de comparer la trace à son entrée véritable. Les anciens fichiers *-0-* de ce dossier sont des copies intermédiaires ; utiliser les noms d’opérations explicites et metrics.json.
- Traces originales : workspace/video_llm_traces/calls/<call_id>.json.

## Résultats principaux

La refonte des variantes fonctionne sur le nouvel essai : 4 références au lieu de 15, soit deux personnages, un décor et une seule variante enceinte réutilisée aux scènes 2/3. La base Fraisette décrit la silhouette fine ; l’ellipse porte timing=between_scenes. La relecture ne demande plus d’ancres début/fin redondantes. Les trois références de base et la variante n’ont pas encore d’image acceptée dans l’instantané : succès du contrat et du routage, pas validation du rendu final.

Le temps de relecture Fraisette chute de 151,5 à 36,3 secondes, le raisonnement exposé d’environ 7 312 à 636 mots. Mais le parcours complet passe de 327,1 à 339,2 secondes : la rédaction Gemma et l’édition de l’arc prennent davantage de temps. Les réglages ne sont pas strictement identiques (ancien : 30 s, 3 clips, narration dialogue ; nouveau : 40 s, plafond 4 clips, narration visuelle, 3 clips produits). Ce n’est pas un benchmark contrôlé.

Piccolo est accepté après 5 appels et 764,5 secondes, sans erreur JSON, troncature ni répétition de requête échouée. Une correction automatique est déclenchée par un diagnostic de durée. L’édition de l’arc, censée améliorer la qualité, est ici disproportionnée et allonge un dialogue ensuite raccourci.

## Coût et contribution des appels

| Étape | Fraisette avant | Fraisette après | Piccolo |
| --- | ---: | ---: | ---: |
| Conception | 72,0 s | 82,0 s | 96,7 s |
| Édition de l’arc | 27,5 s | 60,5 s | 244,2 s |
| Rédaction | 76,1 s | 160,4 s | 191,6 s |
| Correction ciblée | — | — | 47,4 s |
| Relecture finale | 151,5 s | 36,3 s | 184,5 s |
| Total des traces | 327,1 s | 339,2 s | 764,5 s |

Modèles inchangés entre ces essais : Qwen3.8-27B HauhauCS Aggressive MTP pour conception/édition/relecture, Gemma4-31B HauhauCS Balanced MTP pour rédaction/correction. Budget 80 000, finish_reason=stop pour tous les appels.

Fraisette : tokens d’entrée cumulés 23 668 → 14 489 ; tokens de sortie déclarés 23 405 → 16 339. Le raisonnement en mots est une mesure approximative distincte du tokenizer. Les temps sont ceux de la requête complète. Les traces ne séparent pas attente, chargement, préremplissage et décodage.

L’éditeur Piccolo produit 28 332 tokens de sortie en 244,2 s (environ 116 tokens/s sur la durée complète) et environ 15 836 mots de raisonnement. Ici, le volume de délibération explique une grande partie de la longueur ; aucune preuve d’un problème de VRAM dans ces traces. Gemma rédige avec seulement 529 mots de raisonnement, mais met 191,6 s : une lenteur distincte, que ces données ne permettent pas d’attribuer à l’offload ou à un changement de modèle.

## Éditeur Piccolo : défauts inventés et modifications inutiles

Trace : llm-8b353dd0774043d3bdbfcd87f9190436. L’objet current_outline du prompt est exactement égal au series_outline de la réponse de conception llm-d6a87a326cea45e69e2d634813bec005.

L’éditeur se met à citer « T’as taken » ou « shoes brillantes » comme s’ils figuraient dans l’arc. L’entrée réelle contient « T’as pris » et « chaussures brillantes ». Il conclut que presque tout l’arc contient des intrusions anglaises, puis entreprend de le nettoyer. Cela suggère une confusion entre ses reformulations bilingues internes et la source. Le raisonnement ne constitue pas une preuve fiable de ce qui figurait dans le prompt.

Résultat : 36 edits proposés, dont 25 exactement identiques aux valeurs reçues ; 11 seulement changent quelque chose. Parmi les changements : Mehdy → Mehdi (utile), notes → billets (utile), détails de voiture/flaque et polissage mineur. Il ne corrige pas « cirier », terme employé à la place de cireur. L’arc contenait déjà la plupart des informations qu’il annonce avoir ajoutées.

Le plus dommageable : il ajoute des explications dans la réplique de la villa, estime approximativement que cela tient et approuve l’arc. Gemma reprend presque mot pour mot ces répliques d’« evidence ». Le diagnostic local trouve ensuite 38 mots + 3 secondes d’actions, soit 18,8 secondes estimées pour un clip de 10 secondes. Un nouvel appel est nécessaire pour réparer un passage aggravé par l’éditeur.

L’éditeur s’interroge aussi plusieurs fois sur fruits/humains, narration/mélodrame, champs de concept absents du schéma, chemins éditables et guillemets JSON. Le prompt court ne suffit pas : le contexte continue à transporter visual_family.description et concept_fields du format fruit historique, alors que la réponse utilise le contrat long. Ces données inutiles provoquent des arbitrages visibles dans les traces.

## Durée : la correction améliore, mais n’atteint pas sa cible

Trace rédaction : llm-bb3b2d82f86644fc9a075cd9a821c9b7. Trace correction : llm-063194e4e6dc4345ad4b02a9e4aeb006.

Paramètres réellement enregistrés : 50 secondes souhaitées, plafond de 5 clips de 10 secondes, accompagnement automatique. Le brief conserve la phrase « chaque clip de 8 secondes ». La conception repère ce décalage et choisit les paramètres structurés ; cela reste une hésitation évitable. Le modèle produit quatre clips. Son raisonnement imagine cependant 15 secondes pour le dernier, sans champ de durée permettant d’appliquer cette liberté : la fabrication reste à 10 secondes par clip.

La correction réduit la villa à 27 mots + 3 secondes d’actions, soit 14,2 secondes estimées. Elle annonce que cela tient confortablement, avec des comptes de mots et de temps incohérents dans la trace. Une place de clip reste inutilisée. Le contrat de correction locale scene_edits ne permet pas de répartir simplement une scène en deux : il encourage le raccourcissement dans la structure existante.

Le seuil local explique l’acceptation : estimate = mots/2,4 + actions ; le niveau blocking exige aussi mots/3,5 + actions > durée × 1,3. Le passage passe donc de blocking à warning. La dernière relecture (llm-0b466f59ba5d4355a153f1ca034ae619) consacre une partie importante de ses 4 555 mots à hésiter sur la gravité du dépassement, puis maintient un avertissement. Le mode automatique approuve les warnings conformément à sa règle actuelle.

Ce diagnostic est indicatif : des regards/sourires peuvent accompagner la parole, contrairement à trois secondes strictement successives. On ne peut pas affirmer une impossibilité physique sans rendu. Mais « prêt » ne signifie pas ici « durée confortablement maîtrisée » ; le risque est une parole accélérée, une fin coupée ou des réactions écrasées.

## Fidélité et force dramatique

Piccolo conserve le squelette du récit, les quatre personnages humains/cinéma, les trois lieux et le portefeuille. L’aspect humain est compris au stade des descriptions.

Cependant :
- Le riche annonce déjà au cireur « Je veux voir si t’es réglo », ce qui modifie le décalage de la référence où le test est expliqué à la compagne.
- L’ordre du riche à Piccolo figure dans le trigger d’un événement, puis disparaît du scénario joué. La relecture accepte l’inférence parce que la menace a été annoncée avant. C’est intelligible, mais moins fidèle et moins expressif que le brief.
- Les répliques sont familières, mais peu crues. « T’as pris » est une chute verbale assez faible ; le registre est surtout signalé par wallah/wesh/frérot. La trace de l’éditeur constate que les exemples sont doux et décide de s’y tenir.
- L’éditeur attribue à l’arc un budget valide sans avoir réellement construit la faisabilité de chaque scène.
- Le portefeuille est déclaré présent dans les quatre scènes, y compris la villa où son détenteur Mehdi est absent. Le relecteur repère le doute, puis accepte la simple mention de l’objet comme présence dans scene_indices. Ce champ signifie pourtant présence visible dans le contrat courant.
- Le portefeuille est tracking=text, reference=false : aucune référence image dédiée ne sera produite par le compilateur actuel. La direction des futurs objets importants doit préciser quand la reconnaissance visuelle entre scènes mérite une fiche unique.
- Son état « plein et épais » persiste malgré l’ouverture, le comptage et les billets serrés contre la poitrine ; la chronologie de manipulation est moins précise que la chronologie des personnages. Risque de raccord, pas défaut vidéo déjà constaté.

Fraisette après : le récit reste simple et cohérent, avec une grossesse durable correctement routée. L’édition remplace utilement les poings serrés par des épaules crispées (moins agressif), puis explicite des informations déjà présentes. Sa durée d’environ une minute est élevée pour trois retouches. La phrase « C’est... c’est déjà si grand ! » est moins explicite sur la peur de devenir père que l’ancien « J’ai peur d’être père ». Le choix de narration visuelle a aussi changé : ce n’est pas une régression causale prouvée du patch. Le registre conserve encore quelques états émotionnels de Pomito, mais reference=false évite les images inutiles.

## Réplique sur les prostituées : responsabilité de l’adaptation fournie

La référence/transcription antérieure contient cette vantardise. Le texte proposé par l’assistant pour ce test l’avait déjà remplacée par le projet d’arrêter de cirer des chaussures ; les exemples étaient également plus doux. Le prompt effectivement reçu ne contient aucune demande de conserver la réplique « se payer des putes ». Les traces examinées n’établissent aucune censure ou refus du moteur à ce sujet.

La cause certaine de cette disparition est donc une omission dans l’adaptation fournie en amont, dont l’assistant est responsable. Le niveau Vocabulaire=3 autorise une couleur, il ne récupère pas un élément absent du brief. Pour une adaptation fidèle, il faut distinguer les répliques exactes de l’auteur à préserver et les simples exemples de ton à réinventer. La vidéo jointe à la conversation n’est pas automatiquement fournie au modèle d’écriture PanelForge.

## Pertinence des appels et périmètre recommandé

1. Conception : garder une passe qui fixe événements, relations et engagements de fidélité. Elle doit décrire l’information à faire comprendre, sans préécrire partout des répliques que les passes suivantes traiteront comme acquises.
2. Édition systématique de l’arc : candidate principale à rendre conditionnelle. L’ancien Fraisette montre une correction utile du sens (« se rassure » → « la rassure »), donc sa fonction n’est pas nulle. Mais le nouveau Fraisette apporte surtout du polissage, et Piccolo montre un bilan défavorable. La conserver sur demande ou pour un problème identifié, puis comparer un parcours conception → rédaction → relecture indépendante sur ces cas. Aucun gain de qualité ne peut être promis sans comparaison.
3. Rédaction : indispensable. Donner un budget concret par scène, traiter les dialogues une fois, distinguer gestes simultanés et actions successives, et utiliser une scène disponible lorsqu’un passage est trop dense.
4. Relecture finale : garder un regard indépendant. Aujourd’hui elle reçoit les scènes et états mais ni brief ni contrat de fidélité ; elle peut juger un récit lisible sans voir ce qui a disparu. Lui fournir seulement les obligations du passage courant, le ton et les répliques protégées, sans dévoiler les secrets futurs. Lui éviter de redécider longuement des seuils déjà calculés par le code.
5. Correction : uniquement ciblée, une tentative puis relecture. Donner la cible temporelle explicite et vérifier le résultat. Prévoir une redistribution autorisée si un clip reste libre, avec gestion cohérente des IDs et des indices ; ne pas ajouter une boucle générale.

Priorité du prochain patch : fidélité et faisabilité des scènes avant d’ajouter des styles. Conserver l’acquis des états visuels. Retirer du contexte les champs de concept fruit et les règles de nommage inapplicables ; séparer simplement style des dialogues et rendu visuel comme proposé, avec héritage vers fabrication. Le style commun des références démarre encore vide, et n’est pas transmis directement à scene_inputs : point à raccorder pour le rendu réaliste, sans refaire l’interface Références/Scènes/Multilangue.

Ne pas ajouter une nouvelle passe universelle, un filtre lexical bloquant ou un arrêt automatique sur répétitions. Le nombre de tokens de réflexion n’est pas un indicateur de qualité : contrôler plutôt les obligations préservées, les scènes jouables et les corrections effectivement utiles.

## Versionnement

Un point de retour Git local est préparé sur une branche snapshot séparée, avec index temporaire, sans changer HEAD, la branche de travail ou l’index de l’utilisateur. Il sauvegarde l’état du code actuel, y compris les travaux préexistants KREA6/usine/thermique et le patch Histoires. Aucun média, fichier runtime ou trace LLM brute n’est ajouté. Aucun push demandé ou effectué. L’identifiant final est consigné dans la continuité et dans checkpoint.json du dossier de diagnostic après création.
