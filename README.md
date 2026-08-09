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

- catalogue de modèles découvert dynamiquement via llama.swap ;
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

Un onglet séparé expose `minimax.h3.i2v.simple@0.1.0/single-first-frame-v1` avec trois étapes visibles seulement :

```text
image de première frame
  → Observation approuvée
  → Brief approuvé
  → prompt MiniMax H3 I2VA approuvé
```

L’image est liée de façon déterministe à `<Picture 1>` et déclarée comme frame exacte à `0.00` seconde. Il n’y a ni plan de références ni beat sheet cachés. Chaque résultat est streamé, éditable, révisable en langage naturel et soumis à une validation humaine.

Le writer suit le [contrat I2VA du guide MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md) : instruction d’ancrage exacte, puis `integrated_multimodal_description`, `overall_soundscape` et `non_diegetic_music`. Un linter dédié refuse les labels étrangers, les champs manquants et les timestamps de plans invalides avant approbation.

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

Le Lab appelle seulement l’API OpenAI-compatible du serveur. llama.swap reste responsable du chargement, du swap et de la mémoire GPU ; aucune bibliothèque d’inférence n’est installée par PanelForge.

Le streaming repose sur `stream=true` et des événements SSE internes réutilisables par les prochaines fenêtres du Prompt Lab. Les appels disposent d’un budget de sortie de 32 768 tokens adapté aux modèles thinking. Si le serveur termine avec `finish_reason=length`, l’interface signale explicitement la troncature et conserve le texte partiel sans l’enregistrer automatiquement comme une révision complète. Avec `sendLoadingState: true` dans llama.swap, PanelForge reconnaît aussi son message de chargement et l’éventuelle position dans la file. llama.swap ne fournit actuellement pas de pourcentage de chargement fiable : l’interface n’en invente donc pas. Les contenus de raisonnement ordinaires du modèle ne sont jamais affichés comme état système.

Les 20 derniers appels sont conservés dans `workspace/llm_calls.json` : opération, modèle, prompts exacts, réponse, durée, tokens, statut, `finish_reason` et erreur éventuelle. Les images ne sont jamais recopiées dans ce journal ; seules leurs métadonnées et leur SHA-256 sont enregistrées. Ce fichier local peut contenir du texte sensible, reste ignoré par Git et n’est pas exposé par l’API du Lab.

## Architecture

- `domain` : assets, recettes, runs, sessions et compositions/révisions immuables ;
- `application` : orchestration d’un cas d’usage sans node ID ComfyUI et contrat générique de streaming LLM ;
- `infrastructure/comfy` : transport HTTP minimal ;
- `infrastructure/llm` : adaptateur multimodal OpenAI-compatible et décorateur de journalisation bornée ;
- `infrastructure/presets` : validation et compilation des recettes versionnées ;
- `infrastructure/storage` : stockage local vérifié par SHA-256 ;
- `features/lab` : fine interface FastAPI et HTML/CSS/JavaScript natif ;
- `prompt_profiles` : instructions LLM immuables, versionnées et modifiables indépendamment ;
- `prompt_cookbooks` : recettes vidéo versionnées, slots, contrats et templates propres à un cas d’usage ;
- `workflows` : snapshots ComfyUI et manifests explicites.

Les node IDs restent dans les manifests. Le domaine ne dépend ni de FastAPI, ni de ComfyUI, ni d’un fournisseur LLM.

## Feuille de route

### 1. Qualifier I2V simple

- tester des premières frames et intentions variées avec le LLM local ;
- comparer les prompts obtenus dans MiniMax H3 ;
- versionner les corrections du writer et du linter sans modifier `0.1.0`.

### 2. Qualifier Fighter Arcade

- qualifier `Qwen3.6-27B` dense dès qu’il est servi ;
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
