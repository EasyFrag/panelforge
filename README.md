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

Un onglet séparé expose par défaut `minimax.h3.i2v.simple@0.2.0/single-first-frame-natural-motion-v2` avec trois étapes visibles seulement :

```text
image de première frame
  → Observation approuvée
  → Brief approuvé
  → prompt MiniMax H3 I2VA approuvé
```

L’image est liée de façon déterministe à `<Picture 1>` et déclarée comme frame exacte à `0.00` seconde. Il n’y a ni plan de références ni beat sheet cachés. Chaque résultat est streamé, éditable, révisable en langage naturel et soumis à une validation humaine.

Le writer suit le [contrat I2VA du guide MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md) : instruction d’ancrage exacte, puis `integrated_multimodal_description`, `overall_soundscape` et `non_diegetic_music`. Un linter dédié refuse les labels étrangers, les champs manquants et les timestamps de plans invalides avant approbation.

La version `0.2.0` ajoute trois principes génériques : respecter la durée et sa capacité d’action, formuler positivement les contraintes de mouvement en conservant les mouvements secondaires naturels, et empêcher la liberté créative d’ajouter des événements séquentiels non demandés. `0.1.0` reste inchangée comme témoin de comparaison.

Le premier retour visuel est encourageant et le prompt du cas androïde montre une meilleure prise en compte de la durée et de l’état final. Deux générations successives ont toutefois abrégé le marqueur de dialogue (`FR`/`fr`) au lieu de produire le tag H3 exact. La recette `0.2.0` reste inchangée : les marqueurs stricts comme `<d>[French] ...</d>` seront insérés ou normalisés de façon déterministe à partir de données de dialogue structurées, plutôt que confiés à la prose libre du LLM.

Lors d’une révision LLM, PanelForge conserve la réponse brute dans le journal technique mais extrait et persiste uniquement le document révisé. Une réponse contenant deux documents complets est refusée comme ambiguë. Un résultat terminal du modèle reste journalisé comme réussi même si le linter applicatif rejette ensuite le document.

### Ref2V — undressing mono-plan

L’onglet séparé `Ref2V` utilise par défaut le cookbook à deux références `undressing.single_shot@0.7.1`. Le parcours visible reste volontairement court :

```text
première frame habillée + référence corporelle du même sujet
  → deux Observations approuvées
  → Brief approuvé
  → prompt MiniMax H3 Ref2V compilé et approuvé
```

`<Picture 1>` est la frame concrète habillée à `0.00` seconde. `<Picture 2>` complète seulement l’apparence corporelle du même sujet et n’est ni une frame finale ni une cible de pose ou de composition. En `0.2.0`, le LLM écrit quatre champs internes — mise en place, action du plan, ambiance sonore et musique — puis PanelForge compile le mapping immuable, `Shot 1:` et les champs audio dans un format compact proche des exemples Ref2V éprouvés. Les sorties incomplètes sont rejetées avant persistance ; le linter verrouille le header, l’unique plan et l’ordre des timestamps.

La `0.3.0` ajoute deux appels internes derrière le même bouton : un planner produit d’abord un JSON de chorégraphie, puis le writer transforme uniquement ce plan validé en prose H3. Le validateur impose un ordre sans chevauchement, un temps minimal par geste, un état observable pour chaque vêtement, une pose finale tenue au moins deux secondes et, si demandée, une caméra déplacée seulement pendant cette pose. Le JSON n’encombre pas l’éditeur principal mais reste consultable dans un volet avancé.

La `0.4.0` distingue les gestes simples des transformations multi-étapes et estime pour celles-ci une marge supplémentaire de 1,5 seconde. Une marge insuffisante ne bloque plus le writer : le volet du plan affiche la durée minimale conseillée et la génération continue. Les incohérences structurelles — JSON invalide, chevauchement, timestamp hors vidéo — restent bloquantes. La caméra déclare un chemin physique (`pedestal`, `dolly`, `orbit`, `crane`, etc.) et le planner doit conserver une trajectoire de vêtement spatialement continue. Le volet est ouvert par défaut, se remplit pendant le premier appel et conserve aussi un candidat rejeté pour diagnostic.

La `0.5.0` rend la durée élastique. Après le planner, PanelForge conserve chaque durée déjà lisible, agrandit seulement les gestes sous leur marge, décale les étapes suivantes et prolonge la fin jusqu’à un maximum de 15 secondes. Le plan persiste `requested_duration_seconds` et `duration_seconds`, tandis que le writer reçoit uniquement la chronologie finale afin d’éviter toute contradiction. L’interface affiche les deux durées.

La `0.6.0` borne cette redistribution sans modifier les prompts LLM de la `0.5.0`. Les gestes simples gardent le rythme choisi par le planner. Les marges des transformations `multi_step` utilisent d’abord le temps de pose finale disponible au-delà de deux secondes, puis la caméra est recalée ou raccourcie ; la vidéo n’est prolongée qu’en dernier recours. Au plafond de 15 secondes, les marges restantes deviennent des avertissements au lieu de bloquer le writer. Les événements partageant une même frontière temporelle sont autorisés, tout comme un repère final exact à `00:15.000`.

La `0.7.0` remplace ce plafond par un contrat consultatif. Le retiming conserve les marges multi-étapes, le délai d’établissement de la pose et la durée de caméra, puis prolonge la chronologie autant que nécessaire. Une durée supérieure à 15 secondes, un landmark absent ou un écart récupérable du format final apparaît comme avertissement sans empêcher l’enregistrement ni l’approbation ; seuls un plan illisible ou les quatre champs indispensables manquants restent bloquants. Les labels génériques `<Image 1>` et `<Image 2>` produits par le writer sont neutralisés avant compilation du mapping fixe.

La `0.7.1` conserve exactement les prompts de la `0.7.0` et corrige un angle mort technique : si le planner place une pose finale cohérente exactement à la fin demandée, PanelForge ajoute automatiquement au moins deux secondes de tenue, avertit l’utilisateur et poursuit le writer sans relancer le planner. Les chevauchements et l’ordre impossible des actions restent bloquants.

Pour réduire l’influence indésirable de la seconde image, son observation transmise au planner est projetée sur les seuls traits d’apparence ; pose, regard, cadrage, décor et caméra en sont retirés. Le writer reçoit le Brief et le plan approuvé, pas les observations brutes. PanelForge conserve ensuite le même compilateur et le même linter final que la `0.2.0`.

Les versions `0.1.0` à `0.7.0` restent disponibles comme témoins de comparaison. La future variante à une seule référence corporelle, où les vêtements initiaux sont entièrement décrits, n’est pas incluse dans `0.7.1`.

L’interface permet d’analyser les deux images en une action ou de relancer, corriger et valider chaque observation séparément. Observation et Brief réutilisent volontairement le profil générique `minimax.h3.reference@0.3.0` ; les cookbooks Ref2V ne modifient donc le Brief d’aucun autre parcours.

Les neuf titres du Brief sont normalisés par code avec ou sans tiret initial, puis validés exactement une fois et dans le bon ordre avant persistance. Après chaque génération, les éditeurs reviennent en haut du document.

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

Les 20 derniers appels sont conservés dans `workspace/llm_calls.json` : opération, modèle, prompts exacts, réponse, durée, tokens, statut, `finish_reason` et erreur éventuelle. Les images ne sont jamais recopiées dans ce journal ; seules leurs métadonnées et leur SHA-256 sont enregistrées. Ce fichier local peut contenir du texte sensible, reste ignoré par Git et n’est pas exposé par l’API du Lab.

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

- rendre et évaluer le cas androïde `0.2.0` : rythme, immobilité demandée, voix et synchronisation labiale ;
- compiler plus tard les tags H3 stricts depuis des champs structurés, sans alourdir le system prompt ;
- figer ou réviser `0.2.0` seulement à partir des défauts reproduits sur plusieurs vidéos.
- qualifier `undressing.single_shot@0.7.1` sur plusieurs couples de références ; mesurer durée planifiée, lisibilité des gestes, délai pose/caméra et valeur réelle des avertissements ;
- concevoir la `0.8.0` comme un plan chorégraphique supervisé : sous-étapes, durées proposées et contradictions sémantiques visibles, puis correction humaine avant compilation des timestamps ;
- ne spécialiser le profil Observation/Brief Ref2V que si un même manque se répète sur plusieurs essais.

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

La suite couvre le domaine, les manifests, les transports, le stockage, l’orchestration et les API du Lab. Les smokes réels nécessitent llama.swap et/ou ComfyUI joignables avec les modèles attendus.
