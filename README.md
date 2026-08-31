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

### Video Lab — MiniMax H3 Ref2V

Le Video Lab exécute la recette expérimentale et immuable
`video.generate.ref2v/minimax-h3-ref2v@0.2.0` :

- une à trois images ordonnées, reliées à `<Picture 1>` jusqu’à `<Picture 3>` ;
- prompt H3 libre, ratio, mégapixels finaux, durée et steps principaux modifiables ;
- preset initial `h3-balanced` (`9:16`, `1,2 MP`, `10 s`, `25 steps`) ;
- première passe fixe à `0,2 MP`, upscale du latent vidéo, recombinaison de
  l’audio puis seconde passe fixe de trois steps ;
- seed aléatoire par défaut, verrouillable et réutilisable depuis l’historique ;
- preview live depuis le WebSocket natif de ComfyUI, puis lecture et téléchargement de la vidéo MP4 finale avec audio ;
- historique local, annulation ciblée et un seul rendu Video Lab actif à la fois ;
- bouton « Envoyer au Video Lab » dans Ref2V, qui préremplit images, prompt visible et durée du Plan sans lancer automatiquement le rendu.

Les slots d’images inutilisés sont retirés du workflow avant soumission. La durée est exposée entre 5 et 15 secondes à 24 fps, puis quantifiée par le workflow H3 ; par exemple, 10 secondes donnent 243 frames, soit 10,125 secondes effectives. Modifier la durée ne réécrit pas les timestamps du prompt.

La preview passe par un relais WebSocket same-origin de PanelForge, connecté à ComfyUI avec l’identifiant client propre au Video Lab. La sortie finale utilise simplement le lecteur vidéo HTML natif du navigateur, sans surcouche ni diagnostic audio. La surveillance de température de la RTX 6000 et l’arbitrage automatique de VRAM entre llama.swap et ComfyUI restent volontairement hors de cette V1.

Si PanelForge redémarre pendant un rendu, l'identifiant ComfyUI persistant permet de réconcilier le run lors de sa prochaine consultation : une sortie déjà terminée est alors importée, tandis qu'un job encore actif reste suivi.

### Video Lab — textes Instagram assistés

Le sous-mode `Texte Instagram` transforme une vidéo MP4 ou WebM en projet éditorial conversationnel :

- quatre images clés sont extraites dans le navigateur à 10, 35, 65 et 90 % ; la vidéo complète n'est pas envoyée au LLM ;
- anglais par défaut ou français, avec trois variantes par défaut contenant angle, hook, légende, hashtags et emojis ;
- `mood`, `vibe`, exemple représentatif et consignes restent libres et peuvent être enregistrés dans un profil de chaîne réutilisable ;
- chaque projet conserve la vidéo, les images clés, toutes les propositions et la conversation complète afin de reprendre les ajustements après un redémarrage ;
- lorsque la vidéo correspond exactement à une sortie H3 ou Video Lab connue, son prompt est ajouté au contexte ; sinon l'analyse reste strictement visuelle et ne prétend pas entendre l'audio ;
- chaque variante dispose d'une action `Tout copier` prête à publier.

### Image Lab — génération KREA2

Le second mode de l’Image Lab exécute la recette immuable expérimentale
`image.generate.t2i/krea2@0.1.0` à partir d’un prompt texte :

- modèle UNET KREA2 choisi parmi la liste qualifiée et réellement installée ;
- découverte dynamique des checkpoints via ComfyUI, avec actualisation manuelle ;
- ratio, résolution de `0,5` à `4,0` mégapixels et seed aléatoire par défaut ;
- seed verrouillable ou réutilisable depuis un ancien run ;
- sortie PNG finale, historique local, relance et annulation ciblée ;
- un seul rendu KREA2 actif à la fois et reprise d’un résultat ComfyUI terminé
  après redémarrage de PanelForge.

Le preset `krea2-base` utilise par défaut
`Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors`, un ratio `2:3`
et `3 MP`. Le sampling reste volontairement fixe à huit steps, CFG `1`, Euler,
scheduler `simple`, denoise `1`, avec le CLIP et le VAE du workflow qualifié.
La recette publiée ne contient ni branche LoRA, ni refine prompt, ni preview :
ces capacités nécessiteront de nouvelles versions explicites.

### Image Lab — création assistée KREA2

Le mode « Création assistée » organise la conception d’une image comme un projet
conversationnel distinct de KREA2 Edit :

- une intention et, facultativement, une image de référence descriptive sont
  transmises au LLM ; la référence n’entre jamais dans le workflow ComfyUI T2I ;
- chaque réponse conserve des questions d’affinage et un prompt anglais complet,
  immédiatement éditable et exécutable ;
- un résultat réussi peut devenir le feedback visuel du tour suivant, avec son
  prompt exact, son checkpoint, son ratio, ses mégapixels, sa seed et ses LoRA ;
- checkpoint, ratio, mégapixels, seed et quatre LoRA ordonnables restent
  modifiables à chaque essai, tandis que le sampling communautaire reste fixe ;
- les images sont regroupées en bas du projet et une image choisie peut être
  exportée explicitement avec son sidecar sous
  `D:\AI\PanelForge\KREA2 Creations` par défaut ;
- une discussion dédiée peut produire un brouillon de recette (identité,
  invariants, variables, risques et prompt canonique). Seul le bouton de
  publication crée la version immuable `0.1.0`, immédiatement compatible avec
  le catalogue Batch.

La mémoire du projet contient les échanges, décisions, prompts et essais. La
mémoire globale proposée au LLM reste limitée aux recettes déjà publiées et aux
ressources réellement exposées ; un essai ou une discussion ne l’altère jamais.
La racine d’export peut être remplacée par
`PANELFORGE_KREA2_CREATIONS_ROOT` ou `--krea2-creations-root`.

### Image Lab — batches de recettes KREA2

Le mode Batch de l’Image Lab exécute le workflow communautaire versionné
`image.generate.batch/krea2-community@0.2.0`. Il part d’une famille visuelle
publiée et produit jusqu’à dix variations en un seul appel LLM, puis les rend
séquentiellement dans ComfyUI :

- six recettes initiales, dont `high_jewelry_animal_bust_v1` avec Kroma ;
- direction facultative par batch et mémoire des signatures récentes pour éviter
  les répétitions ;
- checkpoint, ratio, mégapixels et pile ordonnée de zéro à quatre LoRA intégrés
  à la version de recette ;
- inventaires locaux limités aux dossiers KREA2 configurés, checkpoints classés
  par favoris et précision, LoRA classées par favoris/SFW/NSFW ;
- un gestionnaire repliable partagé avec KREA2 Edit permet de forcer BF16 ou
  INT8 sur les checkpoints ambigus et de déplacer les LoRA par glisser-déposer
  entre Favoris, SFW, NSFW et Non classés. Ces préférences sont persistées dans
  le workspace et ne modifient pas silencieusement une recette publiée ;
- liens CivitAI/CivitAI Red et vérification manuelle, purement informative, des
  versions disponibles ; une ressource absente reste un warning non destructif ;
- galerie unique, votes, commentaires, historique et révision facultative de la
  recette, publiée seulement après validation humaine.
- pour chaque PNG, un sidecar `.txt` de même nom est sauvegardé dans le même
  dossier ComfyUI ; son JSON contient notamment le prompt exact, la recette, le
  modèle, le ratio, les mégapixels, la seed et la pile LoRA réellement utilisée.

Le sampling reste fixé par le workflow : ER SDE, scheduler `simple`, première
passe de huit steps à CFG `1,1`, upscale latent Bislerp `×1,5`, puis seconde
passe de deux steps à CFG `1` et denoise `0,3`. Aucun de ces réglages n’est
exposé dans l’interface V1 et aucune preview intermédiaire n’est demandée.

Lorsque le lecteur local des modèles est inaccessible, l’inventaire ComfyUI ne
fournit que les noms : PanelForge utilise alors un marqueur explicite `BF16`,
`INT8`, `INT4` ou `FP8` présent dans le nom, sinon conserve « précision
inconnue » jusqu’au classement manuel. Une racine locale ou UNC accessible reste
la seule manière de classer automatiquement les noms ambigus par taille.

### Image Lab — modification KREA2

Le mode de modification de l’Image Lab exécute la recette immuable
`image.edit/krea2.identity_edit@0.1.0`. Il réunit dans un seul écran le backlog,
la reconstruction du prompt et les essais de rendu :

- les sorties réussies du Batch Lab rejoignent automatiquement le backlog ;
  une image PNG, JPEG ou WebP externe peut aussi être ajoutée manuellement ;
- un sidecar Batch ou les métadonnées PNG ComfyUI restaurent au mieux prompt,
  checkpoint, ratio, mégapixels, seed et jusqu’à quatre LoRA générales ; les
  informations absentes ou les ressources renommées produisent seulement un
  avertissement et des valeurs par défaut éditables ;
- chaque appel multimodal traite le prompt actuellement édité comme état
  autoritaire et la nouvelle instruction comme le tour suivant de l’échange.
  Sans prompt récupéré, le premier appel reconstruit la scène depuis l’image.
  Un résultat réussi peut être choisi comme feedback visuel : le LLM le compare
  à la cible, tandis que ComfyUI continue de repartir de la source immuable de
  l’étape. La trace séparée reste affichable en option et n’est pas persistée ;
- le prompt final reste éditable, puis les rendus peuvent être répétés sans
  nouvel appel LLM en changeant checkpoint, LoRA, ratio, mégapixels, seed,
  `ref_boost` ou nombre de steps ;
- le workflow conserve la LoRA technique `krea2_identity_edit_v1_2` à force
  `1`, ainsi que CFG, sampler, scheduler, CLIP, VAE et grounding qualifiés ;
- « Valider et continuer » promeut explicitement un essai réussi en source de
  l’étape suivante. Le backlog reste groupé par projet, avec chronologie des
  étapes, révisions de prompt, essais et résultat validé ;
- à chaque validation, l’image originale puis la chaîne des seuls résultats
  acceptés sont recopiées dans un projet lisible hors du workspace technique.
  L’utilisateur nomme le projet et chaque résultat validé ; chaque image reçoit
  un sidecar `.txt` avec prompt et réglages, plus un manifeste `project.json`.
  Les noms visibles sont bornés et ne répètent pas le nom du projet dans chaque
  fichier, afin de rester compatibles avec les limites de chemins Windows ;
- « Traité » retire tout le projet du backlog courant et « Masquer » l’archive
  sans supprimer l’image originale, les étapes ni les essais déjà produits.

La reconstruction accepte une description NSFW lorsque les personnes sont
clairement adultes. Elle ne déduit jamais un âge adulte ambigu et n’ajoute pas
d’acte ou de participant non demandé.

La racine d’export est `D:\AI\PanelForge\KREA2 Projects` par défaut. Elle peut
être remplacée avec `PANELFORGE_KREA2_PROJECTS_ROOT` ou
`--krea2-projects-root`. Une panne de ce stockage produit un avertissement
réessayable dans l’interface sans annuler la validation ni déplacer les fichiers
techniques conservés par ComfyUI et PanelForge.


### H3 Base / FL2VA — texte et frames frontières facultatives

Les parcours H3 Base et Ref2V proposent aussi un `Mode rapide` avant leur création. Cette option orchestre les mêmes opérations que l’interface manuelle — génération puis approbation du Brief, du Plan et du Prompt final — sans créer de recette ni d’appel LLM supplémentaire. Les recommandations et warnings restent visibles mais ne déclenchent aucun arbitrage et ne bloquent pas la chaîne. Une erreur de contrat, une réponse tronquée ou un échec réseau arrête immédiatement le parcours ; les étapes déjà approuvées sont conservées et un bouton permet de reprendre depuis la première étape incomplète. Un rechargement ne relance jamais silencieusement une génération.

Ref2V propose trois familles de recettes dans le même sélecteur : mono-plan standard, multi-plan structuré et multi-plan direct expérimental. Cette dernière correspond à `minimax.h3.ref2v.direct.multishot.superfast@0.2.0` et impose son exécution en un seul appel : elle crée une capsule de Brief sans LLM puis confie directement aux images, à l’intention et à la politique de liberté l’unique rédaction du corps H3. PanelForge ajoute seulement l’en-tête canonique des références, normalise les balises et auto-approuve le Prompt ; aucun Plan JSON ni writer intermédiaire n’est créé. `Supervisé` et `Rapide` restent des choix d’orchestration séparés pour les recettes standard. Les écarts de caméra, de nombre de plans ou de timestamp restent des avertissements, tandis qu’un document vide, sans Shot 1, sans champs audio, avec labels invalides ou placeholders est bloqué. La `0.1.0` Plan-first reste chargeable pour les parcours historiques sans être proposée aux nouveaux runs.

Une option de debug peut afficher en direct la trace séparée transmise par le modèle. Elle n’active aucun raisonnement, ne parse pas de balises `<think>` et ne persiste rien : si le serveur ou le modèle ne fournit pas de canal `reasoning`, l’interface l’indique simplement.

Dans ces deux parcours Direct, la liberté créative est présentée sous cinq modes explicites — Factuel strict, Conservateur, Équilibré, Cinématographique et Exploratoire — alignés sur les politiques déjà appliquées par le backend. Ce choix agit directement sur les propositions du Brief ; le Plan et le prompt final n’en héritent qu’indirectement par le Brief approuvé. Les anciennes valeurs numériques restent relisibles sans arrondi ni invalidation artificielle.

L’onglet principal `H3 Base` utilise le checkpoint MiniMax H3-Base-FL2VA. La présence des deux emplacements facultatifs détermine automatiquement le mode de prompt, sans demander un choix technique supplémentaire :

```text
intention + [première frame] + [dernière frame]
  → T2VA / I2VA / L2VA / FL2VA déduit par les entrées
  → Brief compact éditable et approuvé
  → Plan JSON physique éditable, arbitrable et approuvé
  → prompt MiniMax H3 Base compilé et approuvé
```

Le profil `minimax.h3.fl2va.direct@0.1.0` relit directement zéro, une ou deux images pendant le Brief et ses révisions. La recette `minimax.h3.fl2va.direct@0.1.0` réutilise le Plan V2 mono-plan — beats, contacts, risques, caméra typée et `final_hold_ms` — mais compacte le Brief et le schéma transmis au planner. Le writer reçoit uniquement le mode, la propriété des frames et la projection compacte du Plan ; le Brief complet n’est pas répété.

La recette mono-plan sélectionnée par défaut est désormais `minimax.h3.fl2va.direct@0.3.2`. Elle conserve les contrats de mouvement et la caméra compilée de `0.3.1`, mais traite une last frame comme un échantillon instantané plutôt qu’une destination : un mouvement déclaré continu ne peut plus rejoindre, verrouiller ou stabiliser la composition finale en avance. Pour un tracking avec impression de sur-place, le sujet peut garder une position écran voisine tandis que le Plan doit conserver une preuve de vitesse par parallaxe, défilement, écoulement, projections ou mouvement corporel. Les fins `natural_settle` et `intentional_hold` explicitement demandées restent autorisées.

PanelForge compile ensuite l’enveloppe officielle : aucun header image en T2VA, ancrage de départ en I2VA, ancrage terminal en L2VA, ou double alignement en FL2VA. Il insère aussi les phrases caméra canoniques aux jalons approuvés. Le modèle ne peut donc ni confondre la frame finale avec l’ouverture, ni modifier l’enveloppe, ni réinventer la caméra lors d’une révision.

Les anciennes recettes `minimax.h3.i2v.direct@0.1.0` et `0.2.0` restent immuables et relisibles. L’action « Repartir de ce run » migre leur première frame vers une nouvelle session H3 Base propre, sans copier le Brief, le Plan ni le Prompt historiques.

### Ref2V — brief multimodal sans observation intermédiaire

L’onglet principal `Ref2V` utilise le parcours Direct générique :

```text
1 à 3 images natives + intention simple
  → Brief multimodal éditable et approuvé
  → Plan JSON physique éditable et approuvé
  → prompt MiniMax H3 compilé et approuvé
```

Le profil `minimax.h3.ref2v.direct@0.1.0` ne crée aucune fiche d’observation. Le modèle reçoit directement les images pendant la génération du Brief et à chaque révision de celui-ci. Le planner reçoit à nouveau les mêmes pixels, dans le même ordre, avec le Brief approuvé. Le writer final reste textuel : il ne reçoit que le mapping immuable et le Plan approuvé.

Chaque image porte un rôle fermé — première ou dernière frame, keyframe, sujet, décor, composition, style ou mouvement — et l’ordre affiché fixe le mapping `<Image N> → <Picture N>`. Avant création, l’interface affiche ce mapping et exige sa confirmation ; toute image ajoutée, retirée, déplacée ou requalifiée invalide cette confirmation. Un warning non bloquant signale aussi une intention explicitement multi-plan lorsque la recette mono-plan est active. Le sélecteur propose toutes les versions Direct avant la création du Plan, puis verrouille la recette dans la composition et conserve ce choix après `Nouveau`. `minimax.h3.ref2v.direct@0.3.3` est sélectionnée par défaut ; `0.3.2` reste le témoin mono-plan à placeholders, `0.3.1` son témoin compact précédent, `0.3.0` le témoin verrouillé complet, `0.2.0` le témoin temporel V2 et `0.1.0` le témoin historique.

Le Plan est volontairement générique : personnes, vêtements, accessoires, objets rigides ou articulés utilisent le même contrat de contacts, trajectoires, appuis, relâchement et état observable. Depuis `0.2.0`, le LLM cadence uniquement les actions et choisit `final_hold_ms`; le code place l’état final à la fin du dernier beat et calcule la durée totale, sans retimer ni interpréter les gestes. La `0.3.0` ajoute l’arbitrage supervisé des risques. La `0.3.1` compacte les instructions et le contexte writer. La `0.3.2` réserve les labels `<Picture N>` à l’en-tête compilé. La `0.3.3` retire aussi toute sémantique caméra du contexte du writer : celui-ci ne voit que `camera_landmarks_ms`, tandis que PanelForge insère déterministiquement la clause officielle depuis le Plan approuvé. Cette dernière recette mono-plan est la voie robuste sélectionnée par défaut.

Une tenue finale faible, une durée dérivée supérieure à 15 secondes et les risques non arbitrés restent des avertissements. JSON illisible, intervalles impossibles, mouvement caméra inconnu ou mapping altéré restent bloquants. Dans la `0.3.3`, landmark absent ou dupliqué, placeholder résiduel et prose de mouvement caméra réintroduite par le writer sont rejetés avant compilation ; la casse de la phrase sujet suivant l’insertion est normalisée mécaniquement. Ces contrôles sont propres au nouveau contrat et ne modifient pas les compositions historiques.

`minimax.h3.ref2v.direct.multishot@0.2.0` ajoute à côté la recette expérimentale flexible : une à trois références et deux à six plans reliés par des coupes franches. Elle réutilise le même Brief multimodal, le Plan éditable et l’arbitrage, sans appel LLM supplémentaire. Le planner choisit le nombre minimal de plans, leur durée, leur composition d’ouverture et un raccord structuré — repère spatial, position, direction et phase du mouvement. PanelForge dérive `shot_N`, les timestamps de coupe, la durée totale et `camera_N`. Le writer produit dynamiquement `scene_setup`, `shot_1` à `shot_N` et les deux champs audio, sans voir ni paraphraser les mouvements caméra ; le code compile l’en-tête, les headings et les clauses canoniques. La `0.1.0`, limitée à trois plans et aux placeholders, reste un témoin immuable.

Les risques non arbitrés, une tenue finale faible et une durée dérivée supérieure à 15 secondes restent des avertissements. La V2 verrouille le nombre de plans pendant l’arbitrage et les révisions, mais autorise une nouvelle génération du Plan à en choisir un autre. Elle exclut encore `<scenetrans>`, les dialogues traversant une coupe et les transitions stylisées ; ces syntaxes resteront dans des recettes séparées.

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

Unsloth Studio peut servir de fournisseur LLM local sur le poste PanelForge.
Lancez-le séparément, créez une
clé dans `Settings > API`, puis configurez la connexion avant de démarrer
PanelForge :

```powershell
unsloth studio -p 8888
$env:PANELFORGE_LOCAL_LLM_URL="http://127.0.0.1:8888/v1"
$env:PANELFORGE_LOCAL_LLM_API_KEY="votre-cle-unsloth"
python scripts\run_lab.py `
  --base-url http://bucket:8188 `
  --llm-base-url http://bucket:8083/v1
```

Chaque sélecteur LLM propose alors la case `Local · Unsloth`. La liste locale
est relue dynamiquement depuis `/v1/models` ; les IDs sont
préfixés par leur provenance (`local::`) afin que toutes les étapes
suivantes d'un même parcours restent sur le fournisseur sélectionné. Si un
serveur local est arrêté ou inaccessible, son catalogue est simplement masqué
sans bloquer les autres. Les parcours qui envoient des images exigent un modèle
compatible vision. PanelForge transmet toutes les images choisies au
fournisseur sans appliquer de limite locale ; une éventuelle limite reste donc
celle du serveur appelé.
Le bouton `VRAM LLM` continue de piloter uniquement llama.swap sur le serveur et
ne décharge pas Unsloth Studio.

Les données techniques locales sont écrites sous `workspace/assets`, `workspace/runs`, `workspace/krea2_runs`, `workspace/krea2_batches`, `workspace/krea2_assisted`, `workspace/krea2_edits`, `workspace/video_runs`, `workspace/prompt_sessions` et `workspace/prompt_compositions`, tous ignorés par Git. Les URLs peuvent aussi être définies avec `PANELFORGE_COMFY_URL`, `PANELFORGE_LLM_URL` et `PANELFORGE_LOCAL_LLM_URL`; la clé Unsloth reste dans `PANELFORGE_LOCAL_LLM_API_KEY` et ne doit pas être versionnée. Les projets KREA2 Edit validés utilisent séparément `D:\AI\PanelForge\KREA2 Projects` ou la racine configurée par `PANELFORGE_KREA2_PROJECTS_ROOT`. Les créations assistées explicitement enregistrées utilisent `D:\AI\PanelForge\KREA2 Creations` ou `PANELFORGE_KREA2_CREATIONS_ROOT`.

Le catalogue KREA2 utilise par défaut les chemins UNC stables du montage SSHFS :
`\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion\_models\Krea2` pour
les checkpoints et `\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2`
pour les LoRA. Ils correspondent au lecteur `Y:` sans dépendre de sa visibilité
dans la session qui lance Python. Ces racines peuvent être remplacées par
`PANELFORGE_KREA2_MODELS_ROOT` et `PANELFORGE_KREA2_LORAS_ROOT`. Lorsque le
lecteur local n’est pas visible dans la session de PanelForge, l’inventaire des
ressources `KREA2/` exposées par ComfyUI sert de secours ; taille, précision et
métadonnées locales restent alors indiquées comme inconnues.

Le Lab appelle seulement les API du serveur. llama.swap reste responsable du chargement, du swap et de la mémoire GPU ; aucune bibliothèque d’inférence n’est installée par PanelForge. Le bouton global `Libérer la VRAM` passe par PanelForge puis appelle l’endpoint administratif officiel de llama.swap : tous les modèles LLM actifs sont déchargés et le prochain appel recharge automatiquement le modèle demandé. Cette action peut interrompre une génération LLM en cours.

Le streaming repose sur `stream=true` et des événements SSE internes partagés par H3 Base et Ref2V. Les garde-fous de sortie sont échelonnés à 64 000, 131 072 ou 262 144 tokens selon le type d'appel ; les étapes structurées longues Brief/Plan/Writer H3 utilisent 262 144. Ces valeurs sont volontairement très hautes et servent surtout de protection contre une génération sans fin ; la fenêtre de contexte du fournisseur peut imposer une borne inférieure. Si le serveur termine avec `finish_reason=length`, l’interface indique le budget épuisé, rappelle que le raisonnement interne y est inclus et conserve le texte partiel sans l’enregistrer automatiquement comme une révision complète. Avec `sendLoadingState: true` dans llama.swap, PanelForge reconnaît aussi son message de chargement et l’éventuelle position dans la file. llama.swap ne fournit actuellement pas de pourcentage de chargement fiable : l’interface n’en invente donc pas. Les contenus de raisonnement ordinaires du modèle ne sont jamais affichés comme état système.

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

- comparer en A/B le mono-plan robuste `minimax.h3.ref2v.direct@0.3.3` et le multi-plan flexible `minimax.h3.ref2v.direct.multishot@0.2.0` sur les mêmes références et intentions ; qualifier notamment 2, 3, 4 et 6 plans, la distinction des cadrages et les raccords de trajectoire ;
- qualifier `minimax.h3.i2v.direct@0.2.0` sur plusieurs premières frames, intentions et familles de modèles : conformité I2VA, qualité du Brief et du Plan, rythme, continuité, caméra compilée, clipping, tags, voix et synchronisation labiale ;
- versionner une nouvelle recette seulement à partir de défauts reproduits sur plusieurs rendus, en conservant prompts, contexte compilateur et observations de test.

Les transitions stylisées et le dialogue continu à travers les coupes restent hors scope tant que ce premier A/B n’est pas qualifié.

### 2. Vérifier la réutilisabilité du moteur vidéo

- permettre plusieurs compositions/forks sur une même session pour comparer deux versions sans réanalyser les images ;
- ajouter un cookbook de transition comme deuxième cas d’école ;
- introduire explicitement son contrat T2VA/FL2VA au lieu de le forcer dans Ref2VA ;
- conserver les mêmes portes de génération, édition et approbation.

### 3. Qualifier l’Image Lab actuel

- refaire le smoke réel de `character.change_view` ;
- évaluer la matrice visuelle sur plusieurs personnages ;
- ajuster les bornes LoRA uniquement à partir des résultats observés.

### 4. Qualifier la génération KREA2

- faire un smoke réel des ratios et résolutions de `image.generate.t2i/krea2@0.1.0` ;
- comparer les checkpoints qualifiés sur les mêmes prompts et seeds ;
- ajouter les LoRAs dans une nouvelle version seulement après qualification de
  leur chargement, de leur ordre et de leurs poids.

### 5. Étendre l’édition d’image

- recettes à un, deux ou trois slots sémantiques (`source`, `identity_reference`, `scene_reference`, `previous_panel`) ;
- opérations dédiées telles que changement d’âge ou édition libre ;
- continuité optionnelle depuis le panel précédent lorsque la scène ne casse pas.

### 6. Construire la Forge narrative

- importer une histoire et proposer personnages, lieux et props ;
- constituer des reference packs approuvés ;
- planifier les panels par `asset_id`, puis les rendre avec les recettes qualifiées.

Le Video Lab couvre maintenant un premier rendu Ref2V strictement versionné ; les autres workflows vidéo restent à qualifier avant intégration. Limitation V1 : une session de génération ne porte encore qu’une seule composition/cookbook. PanelForge ne cherche pas à devenir un éditeur universel de graphes ComfyUI ni à découvrir automatiquement leurs paramètres.

## Vérification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

La suite couvre le domaine, les manifests, les transports, le stockage, l’orchestration et les API du Lab. Les smokes réels nécessitent llama.swap et/ou ComfyUI joignables avec les modèles attendus.
