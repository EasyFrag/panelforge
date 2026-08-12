# PanelForge

PanelForge est un atelier local pour construire un canon visuel cohérent, qualifier des recettes ComfyUI puis produire des panels narratifs à partir d’assets approuvés.

Le projet reste un monolithe modulaire : ComfyUI sert à découvrir manuellement les workflows, tandis que PanelForge les exécute comme des recettes explicites, versionnées et traçables.

## Tranches utilisables

### Image Lab

Le Lab propose actuellement `character.change_view` :

- import d’une image ou réutilisation d’un candidat précédent ;
- huit azimuts, quatre élévations et trois cadrages ;
- prompt Qwen Multiple Angles déterministe et verrouillé ;
- slider de force pour la LoRA d’angle ;
- seed avancée conservée sans perte de précision ;
- génération via ComfyUI, comparaison et historique local ;
- décisions humaines `kept` ou `rejected` sans remplacement automatique du canon ;
- provenance persistée : recette, workflow compilé, prompt exact, contrôles, hashes et filiation.

La recette active est `qwen-edit-2511-multiple-angles@0.2.0`. Seule la force LoRA `1.0` est actuellement qualifiée ; toute autre valeur permise par le slider est enregistrée comme `experimental_override`.

```text
image source
  → recette versionnée
  → workflow compilé
  → run ComfyUI
  → candidat persistant
  → comparaison et décision humaine
  → asset réutilisable
```

### Prompt Lab — du brief au prompt H3

Le premier jalon du générateur de prompt est également disponible :

- catalogue de modèles découvert dynamiquement via llama.swap ; `Qwen3.6-27B-Huihui-abliterated-Q8_0` est présélectionné lorsqu’il est disponible, avec repli gracieux et conservation d’un choix manuel ;
- profils de prompting immuables et versionnés ; `minimax.h3.reference@0.3.0` ajoute le Brief sans modifier les versions précédentes ;
- import cumulatif de une à huit images, suppression individuelle et rôle libre ;
- observation vision lancée séparément pour chaque image, avec action, interactions, état initial et composition ;
- action séquentielle « analyser toutes les images » qui ignore les fiches déjà présentes afin de préserver les corrections ;
- relance, correction manuelle ou demande de modification ciblée en langage naturel ;
- références stables `<Image 1>`, `<Image 2>`, etc. insérables dans l’intention utilisateur ;
- usages multiples (`subject`, `first_frame`, `keyframe`, `environment`, etc.) attribués visuellement dans l’étape Brief ;
- Brief structuré généré depuis l’intention et toutes les observations approuvées, avec curseur de liberté créative `0–100` traduit en politique explicite ;
- correction directe, révision LLM, historique et approbation du Brief ; toute modification d’une observation ou d’un usage invalide son approbation ;
- interprétation MiniMax par image conservée comme outil avancé optionnel, sans second appel vision ;
- texte affiché au fil de la génération pour l’observation, l’interprétation et leurs révisions LLM ;
- état commun `préparation/chargement → génération → terminé`, avec progression indéterminée tant que le serveur ne fournit pas de mesure réelle ;
- historiques et approbations indépendants pour l’observation, l’interprétation optionnelle et le Brief ;
- sessions et images persistées localement.

Le premier cookbook vidéo est maintenant `fighter.arcade_versus@0.1.0/readable-v1`. Il s’appuie sur un moteur Ref2VA commun et ajoute trois portes supervisées :

```text
Brief approuvé + 3 observations approuvées
  → affectation Combattant A / Combattant B / Arène
  → plan de références Ref2VA approuvé
  → beat sheet en 6 plans approuvée
  → prompt MiniMax H3 final approuvé
```

Chaque livrable est générable séparément, streamé, éditable, révisable en langage naturel et versionné localement. Changer le Brief, une observation, une interprétation approuvée, un usage ou une affectation rend les résultats dérivés obsolètes sans supprimer leur historique.

Le plan interne verrouille `subject_definitions` et une `retention_policy`. Après approbation de la beat sheet, le writer produit le `summary` et le `retention_analysis` officiels afin que les apparitions déclarées correspondent réellement aux six plans. Seules les définitions approuvées sont préfixées par le code, sans régénération. Le linter contrôle ensuite les six sections Ref2VA, les labels, les marqueurs de conservation, les apparitions par plan et les timestamps.

Les `<Picture N>` sont numérotées localement et de façon contiguë selon l’ordre des slots du cookbook ; ce mapping constitue aussi le futur ordre d’envoi des images à H3. Le preset refuse explicitement une image de combattant sans usage `subject`, une arène sans usage `environment`, ainsi que les flags de frame/keyframe qu’il ne sait pas encore compiler.

Le preset V1 reste volontairement étroit : 15 secondes, 16:9, six actions lisibles, clash final et textes/HUD réservés à la postproduction. Ces choix seront rendus paramétrables après les premiers tests qualitatifs.

### I2V simple — première frame vers prompt H3

Un onglet séparé expose par défaut `minimax.h3.i2v.simple@0.3.0/single-first-frame-natural-motion-canonical-v1` avec trois étapes visibles seulement :

```text
image de première frame
  → Observation approuvée
  → Brief approuvé
  → prompt MiniMax H3 I2VA approuvé
```

L’image est liée de façon déterministe à `<Picture 1>` et déclarée comme frame exacte à `0.00` seconde. Il n’y a ni plan de références ni beat sheet cachés. Chaque résultat est streamé, éditable, révisable en langage naturel et soumis à une validation humaine.

Le writer suit le contrat I2VA MiniMax H3 : instruction d’ancrage exacte, puis `integrated_multimodal_description`, `overall_soundscape` et `non_diegetic_music`. Le LLM choisit la sémantique, la chorégraphie et la prose ; un compilateur déterministe impose ensuite le vocabulaire fermé des mouvements de caméra, les placeholders, les labels et les balises de dialogue. Le protocole `minimax.h3.protocol@0.1.0` épingle la [documentation officielle MiniMax H3](https://github.com/MiniMax-AI/MiniMax-H3/blob/05d91ff89f58b665e56424fd66db9ef0351b3015/skills/h3-prompt-writing/references/base-en.txt) au commit `05d91ff89f58b665e56424fd66db9ef0351b3015`.

La version `0.3.0` conserve les principes de mouvement naturel de `0.2.0`, mais demande au LLM un brouillon interne structuré avant compilation. `0.2.0` reste inchangée comme témoin A/B et `0.1.0` comme témoin historique.

Les marqueurs tels que `<d>[French] ...</d>` sont maintenant normalisés par code. Chaque révision canonique persiste aussi un `compiler_context` interne contenant les directives structurées : une révision non liée à la caméra réhydrate ce contexte au lieu de demander au LLM de le réinventer, tandis qu’une demande explicite de changement de caméra peut produire une nouvelle version du contexte.

Lors d’une révision LLM, PanelForge conserve la réponse brute dans le journal technique mais extrait et persiste uniquement le document révisé. Une réponse contenant deux documents complets est refusée comme ambiguë. Le journal distingue désormais le résultat du transport modèle (`succeeded`, `truncated`, etc.) de l’issue applicative (`accepted` ou `rejected`) : un LLM terminé correctement n’est plus confondu avec un document accepté par le compilateur.

### Ref2V — undressing mono-plan

L’onglet séparé `Ref2V` utilise par défaut le cookbook à deux références `undressing.single_shot@0.11.0`. La `0.10.0` reste son témoin H3. Le parcours reste supervisé étape par étape :

```text
première frame habillée + référence corporelle du même sujet
  → deux Observations approuvées
  → Brief approuvé
  → plan chorégraphique proposé, corrigé et approuvé
  → prompt MiniMax H3 Ref2V compilé et approuvé
```

`<Picture 1>` est la frame concrète habillée à `0.00` seconde. `<Picture 2>` complète seulement l’apparence corporelle du même sujet et n’est ni une frame finale ni une cible de pose ou de composition. En `0.2.0`, le LLM écrit quatre champs internes — mise en place, action du plan, ambiance sonore et musique — puis PanelForge compile le mapping immuable, `Shot 1:` et les champs audio dans un format compact proche des exemples Ref2V éprouvés. Les sorties incomplètes sont rejetées avant persistance ; le linter verrouille le header, l’unique plan et l’ordre des timestamps.

La `0.3.0` ajoute deux appels internes derrière le même bouton : un planner produit d’abord un JSON de chorégraphie, puis le writer transforme uniquement ce plan validé en prose H3. Le validateur impose un ordre sans chevauchement, un temps minimal par geste, un état observable pour chaque vêtement, une pose finale tenue au moins deux secondes et, si demandée, une caméra déplacée seulement pendant cette pose. Le JSON n’encombre pas l’éditeur principal mais reste consultable dans un volet avancé.

La `0.4.0` distingue les gestes simples des transformations multi-étapes et estime pour celles-ci une marge supplémentaire de 1,5 seconde. Une marge insuffisante ne bloque plus le writer : le volet du plan affiche la durée minimale conseillée et la génération continue. Les incohérences structurelles — JSON invalide, chevauchement, timestamp hors vidéo — restent bloquantes. La caméra déclare un chemin physique (`pedestal`, `dolly`, `orbit`, `crane`, etc.) et le planner doit conserver une trajectoire de vêtement spatialement continue. Le volet est ouvert par défaut, se remplit pendant le premier appel et conserve aussi un candidat rejeté pour diagnostic.

La `0.5.0` rend la durée élastique. Après le planner, PanelForge conserve chaque durée déjà lisible, agrandit seulement les gestes sous leur marge, décale les étapes suivantes et prolonge la fin jusqu’à un maximum de 15 secondes. Le plan persiste `requested_duration_seconds` et `duration_seconds`, tandis que le writer reçoit uniquement la chronologie finale afin d’éviter toute contradiction. L’interface affiche les deux durées.

La `0.6.0` borne cette redistribution sans modifier les prompts LLM de la `0.5.0`. Les gestes simples gardent le rythme choisi par le planner. Les marges des transformations `multi_step` utilisent d’abord le temps de pose finale disponible au-delà de deux secondes, puis la caméra est recalée ou raccourcie ; la vidéo n’est prolongée qu’en dernier recours. Au plafond de 15 secondes, les marges restantes deviennent des avertissements au lieu de bloquer le writer. Les événements partageant une même frontière temporelle sont autorisés, tout comme un repère final exact à `00:15.000`.

La `0.7.0` remplace ce plafond par un contrat consultatif. Le retiming conserve les marges multi-étapes, le délai d’établissement de la pose et la durée de caméra, puis prolonge la chronologie autant que nécessaire. Une durée supérieure à 15 secondes, un landmark absent ou un écart récupérable du format final apparaît comme avertissement sans empêcher l’enregistrement ni l’approbation ; seuls un plan illisible ou les quatre champs indispensables manquants restent bloquants. Les labels génériques `<Image 1>` et `<Image 2>` produits par le writer sont neutralisés avant compilation du mapping fixe.

La `0.7.1` conserve exactement les prompts de la `0.7.0` et corrige un angle mort technique : si le planner place une pose finale cohérente exactement à la fin demandée, PanelForge ajoute automatiquement au moins deux secondes de tenue, avertit l’utilisateur et poursuit le writer sans relancer le planner. Les chevauchements et l’ordre impossible des actions restent bloquants.

La `0.8.0` rend le plan obligatoire et visible avant le writer. Le parcours nominal reste à deux appels LLM : le premier propose la chorégraphie, puis l’utilisateur la contrôle et la valide avant le writer. Chaque geste contient des sous-étapes horodatées, l’état séparé des deux mains et l’état observable de l’objet. Le planner remonte aussi les conflits de visibilité, de continuité physique ou d’influence de la seconde référence dans `continuity_concerns` ; une ambiguïté non résolue reste un avertissement et ne bloque pas le parcours.

La `0.9.0` conserve ce plan détaillé en interne, mais le writer n’expose plus chaque micro-étape au moteur vidéo. Le prompt final utilise seulement les débuts des beats majeurs, la pose finale et un éventuel mouvement de caméra comme jalons horodatés ; chaque beat est rédigé comme une transition continue cause → action → réaction → état observable. Le planner traite aussi la construction visible du vêtement comme un contrat physique : un haut sans manches conserve des emmanchures ou des bretelles et ne peut plus être réinterprété comme un vêtement à manches. Les arbitrages sont formulés en résultats visibles plutôt qu’en vocabulaire de moteur 3D.

La `0.10.0` conserve la grammaire compacte et empirique de `0.9.0`, mais remplace la caméra libre par le protocole versionné `minimax.h3.protocol@0.1.0`. Le planner choisit une directive dans le vocabulaire officiel, le writer place seulement un placeholder, puis PanelForge compile la clause exacte depuis le plan approuvé, normalise les tags H3 et persiste le `compiler_context`. `0.9.0` reste le témoin A/B sans ce compilateur canonique.

La `0.11.0` cible les défauts génériques observés sur plusieurs retraits : un vêtement reste un objet connecté, suit une seule route compatible avec ses ouvertures visibles, conserve des prises de mains explicites et franchit les parties du corps avant d’être relâché puis posé. Le planner utilise le plus petit nombre de transitions permettant de prouver cette continuité, sans multiplier les micro-timestamps. Le writer restitue ensuite cette route en prose fluide et interdit duplication, séparation en panneaux, téléportation ou changement de topologie. Aucune couleur, tenue, pose ou pièce propre à un exemple n’est codée dans la recette.

Cette sortie reste volontairement le format compact `minimax.h3.ref2v.single_shot_supervised_compact_h3_v1` qualifié pour ce cookbook. Ce n’est pas le format Ref2VA officiel à six sections ; une future recette six-sections devra porter un contrat distinct au lieu d’être introduite silencieusement ici.

Une caméra explicitement décrite comme fixe mais encodée par le LLM dans l’objet `camera` est normalisée en `camera: null` avec avertissement. Un véritable mouvement peut accompagner l’action, assurer une transition, parcourir tout le plan ou entourer la pose finale. Si le LLM le marque à tort `held_final_pose` alors que ses timestamps commencent plus tôt, PanelForge corrige sa phase et avertit sans rejeter le candidat. En `0.11.0`, un `target_clause` optionnel invalide est retiré avec avertissement tout en conservant le mouvement typé ; la `0.10.0` garde son comportement strict. L’ordre impossible des gestes, les mouvements caméra inconnus et leur chevauchement avec la pose finale restent bloquants.

Une interface d’arbitrage présente chaque conflit sous forme de carte. L’utilisateur peut reprendre la recommandation, accepter explicitement le risque, écrire sa décision ou ajouter une instruction globale telle qu’un changement de durée. « Appliquer les décisions au plan » déclenche un troisième appel optionnel qui réécrit réellement les sous-gestes et les timings. Le résultat redevient non validé pour contrôle humain ; le serveur refuse de le persister si une décision nommée disparaît ou n’est pas recopiée exactement dans sa résolution. Si seules les résolutions changent sans aucun effet sur les gestes, timings, états, décor ou caméra, un avertissement non bloquant le signale. Le JSON reste disponible comme recours avancé.

Le code vérifie seulement la structure, l’ordre et la cohérence des intervalles. Il ne prétend pas estimer la durée sémantique correcte d’un geste : les timings proposés restent modifiables. Une pose finale sans marge est toujours prolongée automatiquement et une caméra de moins d’une seconde produit désormais un avertissement plutôt qu’un rejet.

En `0.11.0`, chaque slot porte une politique de preuve persistante. La seconde image est projetée de manière déterministe sur les seules sections âge apparent et apparence stable avant le Brief puis avant le planner. Le mapping final envoyé à H3 répète explicitement que cette image ne définit ni tenue, état instantané, pose, mains, expression, objectif, angle, lumière, décor ou composition. Ces attributs ne sont donc plus transmis comme preuves par PanelForge, même si la fidélité réelle du moteur à cette frontière doit encore être qualifiée visuellement. La politique fait partie du snapshot du Brief et de la provenance. Les sessions et recettes antérieures conservent leur comportement historique.

Les versions `0.1.0` à `0.10.0` restent disponibles pour comparaison. La future variante à une seule référence corporelle, où les vêtements initiaux sont entièrement décrits, n’est pas incluse dans `0.11.0`.

L’interface permet d’analyser les deux images en une action ou de relancer, corriger et valider chaque observation séparément. Observation et Brief réutilisent le profil générique `minimax.h3.reference@0.3.0`, tandis que la politique de preuve est attachée à chaque référence : les autres parcours restent en politique `full` et ne sont pas filtrés.

Les neuf titres du Brief sont normalisés par code avec ou sans tiret initial, puis validés exactement une fois et dans le bon ordre avant persistance. Après chaque génération, les éditeurs reviennent en haut du document.

### Ref2V Direct — brief multimodal sans observation intermédiaire

L’onglet indépendant `Ref2V Direct` conserve l’ancien Ref2V comme témoin et propose un parcours générique plus court :

```text
1 à 3 images natives + intention simple
  → Brief multimodal éditable et approuvé
  → Plan JSON physique éditable et approuvé
  → prompt MiniMax H3 compilé et approuvé
```

Le profil `minimax.h3.ref2v.direct@0.1.0` ne crée aucune fiche d’observation. Le modèle reçoit directement les images pendant la génération du Brief et à chaque révision de celui-ci. Le planner reçoit à nouveau les mêmes pixels, dans le même ordre, avec le Brief approuvé. Le writer final reste textuel : il ne reçoit que le mapping immuable et le Plan approuvé.

Chaque image porte un rôle fermé — première ou dernière frame, keyframe, sujet, décor, composition, style ou mouvement — et l’ordre affiché fixe le mapping `<Image N> → <Picture N>`. Le sélecteur Ref2V Direct propose toutes les versions du catalogue avant la création du Plan, puis verrouille la version dans la composition. `minimax.h3.ref2v.direct@0.3.2` est sélectionnée par défaut ; `0.3.1` reste son témoin compact, `0.3.0` le témoin verrouillé complet, `0.2.0` le témoin temporel V2 et `0.1.0` le témoin historique.

Le Plan est volontairement générique : personnes, vêtements, accessoires, objets rigides ou articulés utilisent le même contrat de contacts, trajectoires, appuis, relâchement et état observable. Depuis `0.2.0`, le LLM cadence uniquement les actions et choisit `final_hold_ms`; le code place l’état final à la fin du dernier beat et calcule la durée totale, sans retimer ni interpréter les gestes. La `0.3.0` ajoute l’arbitrage supervisé des risques. La `0.3.1` compacte les instructions et le contexte writer. La `0.3.2` ne change ni Plan ni orchestration : elle précise seulement que les labels `<Picture N>` appartiennent à l’en-tête compilé et ne doivent pas être répétés dans les quatre champs produits par le writer.

Une tenue finale faible, une durée dérivée supérieure à 15 secondes et les risques non arbitrés restent des avertissements. JSON illisible, intervalles impossibles, mouvement caméra inconnu ou mapping altéré restent bloquants. Les écarts caméra sans ambiguïté sont réparés avant validation avec un warning traçable : cible optionnelle invalide, amplitude/vitesse incompatibles avec `static_shot`, `shake.*` ou `pov`, point final redondant après `[[camera:camera_N]]` et placeholder placé sur la ligne `shot_1:`. Un placeholder réellement enchâssé dans une phrase reste rejeté.

Cette version représente toujours un seul plan continu. Une demande de coupe ou de second plan doit remonter comme risque explicite ; le support multi-shot sera un contrat séparé, pas une caméra détournée.

Les trois appels nominaux sont déclenchés séparément dans l’interface. Les corrections manuelles ne consomment aucun appel ; une révision du Brief ou du Prompt en langage naturel ajoute un appel explicite. Les recettes historiques et leurs sessions ne sont pas modifiées.

## Lancer le Lab

L’interface tourne sur le poste PanelForge et appelle ComfyUI à distance. Rien n’est installé dans l’environnement Python du serveur GPU.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python scripts\run_lab.py `
  --base-url http://bucket:8188 `
  --llm-base-url http://bucket:8083/v1
```

Puis ouvrir `http://127.0.0.1:7860`.

Les données locales sont écrites sous `workspace/assets`, `workspace/runs`, `workspace/prompt_sessions` et `workspace/prompt_compositions`, tous ignorés par Git. Les URLs peuvent aussi être définies avec `PANELFORGE_COMFY_URL` et `PANELFORGE_LLM_URL`.

Le Lab appelle seulement les API du serveur. llama.swap reste responsable du chargement, du swap et de la mémoire GPU ; aucune bibliothèque d’inférence n’est installée par PanelForge. Le bouton global `Libérer la VRAM` passe par PanelForge puis appelle l’endpoint administratif officiel de llama.swap : tous les modèles LLM actifs sont déchargés et le prochain appel recharge automatiquement le modèle demandé. Cette action peut interrompre une génération LLM en cours.

Le streaming repose sur `stream=true` et des événements SSE internes réutilisables par les prochaines fenêtres du Prompt Lab. Les appels disposent d’un budget de sortie de 32 768 tokens adapté aux modèles thinking. Si le serveur termine avec `finish_reason=length`, l’interface signale explicitement la troncature et conserve le texte partiel sans l’enregistrer automatiquement comme une révision complète. Avec `sendLoadingState: true` dans llama.swap, PanelForge reconnaît aussi son message de chargement et l’éventuelle position dans la file. llama.swap ne fournit actuellement pas de pourcentage de chargement fiable : l’interface n’en invente donc pas. Les contenus de raisonnement ordinaires du modèle ne sont jamais affichés comme état système.

Les 20 derniers appels sont conservés dans `workspace/llm_calls.json` : opération, modèle, prompts exacts, réponse, durée, tokens, statut transport, issue applicative, `finish_reason` et erreurs éventuelles. Les images ne sont jamais recopiées dans ce journal ; seules leurs métadonnées et leur SHA-256 sont enregistrées. Ce fichier local peut contenir du texte sensible, reste ignoré par Git et n’est pas exposé par l’API du Lab.

## Architecture

- `domain` : assets, recettes, runs, sessions et compositions/révisions immuables ;
- `application` : orchestration d’un cas d’usage sans node ID ComfyUI et contrat générique de streaming LLM ;
- `infrastructure/comfy` : transport HTTP minimal ;
- `infrastructure/llm` : adaptateur multimodal OpenAI-compatible, contrôle administratif minimal de llama.swap et décorateur de journalisation bornée ;
- `infrastructure/presets` : validation et compilation des recettes versionnées ;
- `infrastructure/storage` : stockage local vérifié par SHA-256 ;
- `features/lab` : fine interface FastAPI et HTML/CSS/JavaScript natif ;
- `prompt_profiles` : instructions LLM immuables, versionnées et modifiables indépendamment ;
- `prompt_cookbooks` : recettes vidéo versionnées, slots, contrats et templates propres à un cas d’usage ;
- `workflows` : snapshots ComfyUI et manifests explicites.

Les node IDs restent dans les manifests. Le domaine ne dépend ni de FastAPI, ni de ComfyUI, ni d’un fournisseur LLM.

## Feuille de route

### 1. Qualifier les parcours courts I2V et Ref2V

- qualifier `minimax.h3.ref2v.direct@0.3.2` avec Gemma et Qwen, puis comparer à `0.3.1` sur les mêmes références et intentions ; mesurer les répétitions de labels, rejets de forme, fidélité aux rôles, continuité, rythme et clipping ;
- comparer en A/B `minimax.h3.i2v.simple@0.3.0` à son témoin `0.2.0` sur les mêmes images et intentions : qualité vidéo, rythme, tags, voix et synchronisation labiale ;
- comparer en A/B `undressing.single_shot@0.11.0` à son témoin `0.10.0` sur plusieurs constructions de vêtements : topologie, passages par les ouvertures, continuité des prises, clipping, rythme et caméra ;
- versionner une nouvelle recette seulement à partir de défauts reproduits sur plusieurs rendus, en conservant prompts, contexte compilateur et observations de test.

### 2. Qualifier Fighter Arcade

- qualifier `Qwen3.6-27B-Huihui-abliterated-Q8_0` sur plusieurs jeux de références ;
- tester le flux complet avec plusieurs jeux de références ;
- comparer les sorties H3, puis versionner les corrections de prompts et du linter ;
- rendre durée, issue et intensité caméra paramétrables seulement après qualification.

### 3. Vérifier la réutilisabilité du moteur vidéo

- permettre plusieurs compositions/forks sur une même session pour comparer deux versions sans réanalyser les images ;
- ajouter un cookbook de transition comme deuxième cas d’école ;
- introduire explicitement son contrat T2VA/FL2VA au lieu de le forcer dans Ref2VA ;
- conserver les mêmes portes de génération, édition et approbation.

### 4. Qualifier l’Image Lab actuel

- refaire le smoke réel de `character.change_view` ;
- évaluer la matrice visuelle sur plusieurs personnages ;
- ajuster les bornes LoRA uniquement à partir des résultats observés.

### 5. Ajouter le mode Generate

- promouvoir l’expérience `character.bootstrap` en recette versionnée ;
- exposer prompt positif/négatif, résolution et LoRAs déclarées ;
- générer et comparer plusieurs candidats de personnage.

### 6. Étendre l’édition d’image

- recettes à un, deux ou trois slots sémantiques (`source`, `identity_reference`, `scene_reference`, `previous_panel`) ;
- opérations dédiées telles que changement d’âge ou édition libre ;
- continuité optionnelle depuis le panel précédent lorsque la scène ne casse pas.

### 7. Construire la Forge narrative

- importer une histoire et proposer personnages, lieux et props ;
- constituer des reference packs approuvés ;
- planifier les panels par `asset_id`, puis les rendre avec les recettes qualifiées.

Le rendu et l’export vidéo restent ultérieurs ; ce Lab produit et qualifie pour l’instant les prompts. Limitation V1 : une session Prompt Lab ne porte encore qu’une seule composition/cookbook. PanelForge ne cherche pas à devenir un éditeur universel de graphes ComfyUI ni à découvrir automatiquement leurs paramètres.

## Vérification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

La suite couvre le domaine, les manifests, les transports, le stockage, l’orchestration et les API du Lab ; elle compte actuellement 303 tests verts. Les smokes réels nécessitent llama.swap et/ou ComfyUI joignables avec les modèles attendus.
