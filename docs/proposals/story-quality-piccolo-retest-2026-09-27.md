# Audit du nouvel essai Piccolo / portefeuille — 2026-09-27

## Périmètre et état observé

Audit en lecture seule des données métier et appels déjà enregistrés. Aucun appel LLM, rendu, test ou redémarrage lancé ; aucun scénario ni réglage modifié.

- Histoire : `story-53551c9387a74685886728a88a9db13d`, titre « Le Portefeuille du Test ».
- Scénario : « Cinq scènes pour un portefeuille ».
- Fabrication : `episode-7e67dd3b2c054d4bbc16dd83fa634ade`.
- Politique nouvelle `story_quality_version=1`, recette révision 7 ; automatique, Qwen3.8-27B HauhauCS Aggressive MTP aux trois étapes d’écriture, français, registre 3, street, fast.
- Cinq scènes de 10 s, 50 s visées. État écriture ready, trois appels acceptés, aucune correction.
- Images de référence produites. Les cinq listes preparations sont encore vides à la lecture : le présent avis porte sur l’écriture et les consignes de fabrication, pas sur des vidéos regardées.
- `visual_render=story` et non custom, mais les notes hybrides sont présentes et intégralement transmises au champ style de fabrication. Les prompts d’images distinguent humains photoréalistes et personnage animé 3D.

## Résultat narratif

Les trois manques signalés par l’auteur sont corrigés dans le scénario final :

1. Scène 2 : Piccolo figure explicitement dans character_ids, physiquement près de l’escalier ; Nabil le désigne et Piccolo répond « Toujours dispo. ».
2. Scène 3 : Mehdi prononce exactement « Je vais me payer une pute. ».
3. Scène 4 : colère visible, appel de Piccolo, arrivée à travers le plafond, face-à-face et ordre exact « Piccolo, retrouve Mehdi et tabasse-le ! », puis accusé de réception et départ.

Les cinq scènes distinctes sont conservées, le test n’est plus révélé prématurément à Mehdi. La chute reste la correction burlesque, sans moralisation ni enquête ajoutée.

Le portefeuille dispose maintenant d’une référence d’objet dédiée, produite et sélectionnée. Le registre de continuité ne le déclare visible qu’aux scènes 1 et 3, avec transfert de Nabil à Mehdi. Un changement de détenteur ne crée pas une seconde image. Total : quatre personnages, trois décors, un objet ; aucune variante visuelle inutile.

## Réserves éditoriales

- Scène 1, « Vingt mille balles » révèle déjà le montant à Mehdi. La découverte de la somme en scène 3 perd donc sa surprise. Proposition : Nabil remet le portefeuille sans annoncer le montant ; l’annonce au public peut rester en scène 2.
- La réplique « J’ai lâché vingt mille balles à ce ciré de chaussures » contient une erreur : cireur, pas ciré. « Le gars qui cire mes pompes » serait plus oral.
- Le statut de test est expliqué dans l’action, mais pas nommé aussi nettement dans la réplique. « Je lui ai filé mon portefeuille pour voir s’il me le rend » donnerait une intention audible plus claire.
- Registre compréhensible mais peu incisif hors réplique imposée. Mehdi emploie « Wesh » dans trois scènes ; Piccolo répond « Toujours dispo », « Ça marche », « C’est l’ordre de Nabil ». Ces formulations fonctionnent comme explications, moins comme des répliques comiques mémorables.
- Scène 4 cumule table frappée, verre renversé, appel, plafond fissuré, effondrement, atterrissage, ordre et départ. La priorité visuelle devrait rester colère → arrivée → ordre. Le risque vient des actions successives davantage que des 20 mots parlés.
- Scène 5 : « têtes qui tournent » et « s’accroche à l’air » peuvent tirer le jeu des humains vers un cartoon alors que l’objectif vise des acteurs réalistes avec violence burlesque. Décrire des réactions physiques concrètes éviterait cette ambiguïté.
- Anglais résiduel réel dans l’action de scène 5 : « Mehdi stumbles ». Aucun anglais constaté dans les dialogues finaux. Le résumé du relecteur invente en revanche « C’est l’ordre of Nabil », absent du scénario et de son entrée.

Volumes parlés approximatifs par séparation sur espaces : 16 / 30 / 10 / 20 / 12 mots. Ces chiffres ne prouvent pas une capacité vidéo ; les réactions, alternances de locuteurs et actions restent à vérifier sur rendu. La scène 2 ne justifie pas à elle seule une réduction avec le débit rapide demandé.

## Fausse alerte de fidélité : chaîne causale vérifiée

La phrase correcte de l’auteur existe dans le brief et author_exact_lines.

1. **compose** (`llm-e653216636d74983add1084c84ace76f`) déforme cette phrase en « Je vais me pay a pute. » dans overall_arc, un event.evidence et must_keep. Il introduit aussi le nom mal écrit « Nbil ».
2. **develop** (`llm-e8652b5b39904c26ad04fd070e6d97fe`) reçoit simultanément cette variante corrompue et les répliques originales correctes. Son raisonnement revient longuement sur les variantes, mais sa réponse finale restitue bien « Je vais me payer une pute. ».
3. **review_block** (`llm-96d70522e7914932af132435152b73ca`) reçoit le dialogue correct dans reader_units, la phrase correcte dans protected_lines, et la variante incorrecte dans required_on_screen/evidence hérité de l’arc. Il affirme à tort que le dialogue contient la variante corrompue et émet un warning fidelity.

Il existe donc une contradiction réelle dans le contexte de relecture, puis une attribution erronée au scénario par le lecteur. Ce n’est pas une censure ni une phrase absente du scénario. Le warning n’a pas bloqué cette exécution.

Les deux autres remarques locales portent sur Mehdi cité mais absent du casting en scènes 2 et 4 : il est seulement évoqué, pas visible. Elles ne justifient pas de l’ajouter aux images. Le lecteur le comprend mais elles restent enregistrées comme avertissements informatifs.

## Appels et raisonnement

| Étape | Durée complète de requête | Tokens de sortie déclarés | Mots de raisonnement approximatifs |
| --- | ---: | ---: | ---: |
| Conception | 87,0 s | 6 435 | 2 188 |
| Développement | 264,2 s | 27 364 | 13 894 |
| Relecture | 95,5 s | 9 631 | 5 687 |

Les trois appels terminent sur stop, sans JSON invalide, troncature ni erreur applicative. Total enregistré : 446 859 ms, soit 7 min 27. Ancien essai story-18c12bf9b9ac46109242a6a728b14bc6 : 764 656 ms, cinq appels, soit 12 min 45. Environ 42 % de temps en moins sur ces deux essais ; ce n’est pas un benchmark contrôlé : modèle rédacteur, brief et consignes ont changé.

La longueur de raisonnement reste disproportionnée au développement : hésitations répétées sur les citations exactes et vérifications du schéma. Le lecteur poursuit le même conflit et aboutit à une fausse alerte. Les durées sont celles des requêtes complètes, pas une mesure isolée de la vitesse de décodage ou de l’occupation VRAM.

## Suite proposée, sans implémentation

Conserver les cinq scènes et les trois fonctions conception / écriture / relecture. Retouches éditoriales ciblées avant un rendu soigné : découverte du montant, formulation du test, voix de Piccolo, actions secondaires scène 4, langue et faute cireur.

Priorité moteur : garder une seule source autoritative pour les répliques exactes, ne pas les réécrire en variantes dans les obligations issues de l’arc. Faire vérifier leur présence par le contrôle exact local existant ; demander au lecteur de juger leur attribution, leur contexte et la causalité réellement jouée. Ne pas ajouter une passe universelle pour compenser ce conflit. Rien n’est implémenté dans cet audit.

Un essai avec un brief aussi détaillé valide surtout la fidélité d’adaptation. Il ne démontre pas encore la capacité à inventer cette même qualité depuis une intention minimale.

## Sources locales

- `D:/Code/panelforge/workspace/stories/story-53551c9387a74685886728a88a9db13d.json`
- `D:/Code/panelforge/workspace/episodes/episode-7e67dd3b2c054d4bbc16dd83fa634ade.json`
- `D:/Code/panelforge/workspace/video_llm_traces/calls/llm-e653216636d74983add1084c84ace76f.json`
- `D:/Code/panelforge/workspace/video_llm_traces/calls/llm-e8652b5b39904c26ad04fd070e6d97fe.json`
- `D:/Code/panelforge/workspace/video_llm_traces/calls/llm-96d70522e7914932af132435152b73ca.json`
