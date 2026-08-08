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

### Prompt Lab — analyse des références

Le premier jalon du générateur de prompt est également disponible :

- catalogue de modèles découvert dynamiquement via llama.swap ;
- profils de prompting immuables et versionnés, avec une première recette `minimax.h3.reference@0.1.0` ;
- import de une à huit images avec un rôle libre par référence ;
- analyse vision lancée séparément pour chaque image ;
- relance, correction manuelle ou demande de modification ciblée en langage naturel ;
- historique linéaire des révisions et approbation indépendante de chaque fiche ;
- sessions et images persistées localement.

Ce jalon s’arrête volontairement après la validation des fiches visuelles. Le brief français, le degré de liberté créative et la compilation du prompt vidéo avancé constituent le jalon suivant.

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

Les données locales sont écrites sous `workspace/assets`, `workspace/runs` et `workspace/prompt_sessions`, tous ignorés par Git. Les URLs peuvent aussi être définies avec `PANELFORGE_COMFY_URL` et `PANELFORGE_LLM_URL`.

Le Lab appelle seulement l’API OpenAI-compatible du serveur. llama.swap reste responsable du chargement, du swap et de la mémoire GPU ; aucune bibliothèque d’inférence n’est installée par PanelForge.

## Architecture

- `domain` : assets, recettes, runs et sessions/révisions immuables du Prompt Lab ;
- `application` : orchestration d’un cas d’usage sans node ID ComfyUI ;
- `infrastructure/comfy` : transport HTTP minimal ;
- `infrastructure/llm` : adaptateur multimodal OpenAI-compatible minimal ;
- `infrastructure/presets` : validation et compilation des recettes versionnées ;
- `infrastructure/storage` : stockage local vérifié par SHA-256 ;
- `features/lab` : fine interface FastAPI et HTML/CSS/JavaScript natif ;
- `prompt_profiles` : instructions LLM immuables, versionnées et modifiables indépendamment ;
- `workflows` : snapshots ComfyUI et manifests explicites.

Les node IDs restent dans les manifests. Le domaine ne dépend ni de FastAPI, ni de ComfyUI, ni d’un fournisseur LLM.

## Feuille de route

### 1. Terminer le Prompt Lab vidéo

- qualifier `Qwen3.6-27B` dense dès qu’il est servi ;
- ajouter le brief français et son découpage éditable ;
- ajouter le curseur de liberté comme politique explicite, pas comme simple température ;
- composer, réviser et approuver le prompt MiniMax H3 final à partir des fiches validées.

### 2. Qualifier l’Image Lab actuel

- refaire le smoke réel de `character.change_view` ;
- évaluer la matrice visuelle sur plusieurs personnages ;
- ajuster les bornes LoRA uniquement à partir des résultats observés.

### 3. Ajouter le mode Generate

- promouvoir l’expérience `character.bootstrap` en recette versionnée ;
- exposer prompt positif/négatif, résolution et LoRAs déclarées ;
- générer et comparer plusieurs candidats de personnage.

### 4. Étendre l’édition d’image

- recettes à un, deux ou trois slots sémantiques (`source`, `identity_reference`, `scene_reference`, `previous_panel`) ;
- opérations dédiées telles que changement d’âge ou édition libre ;
- continuité optionnelle depuis le panel précédent lorsque la scène ne casse pas.

### 5. Construire la Forge narrative

- importer une histoire et proposer personnages, lieux et props ;
- constituer des reference packs approuvés ;
- planifier les panels par `asset_id`, puis les rendre avec les recettes qualifiées.

La vidéo reste un jalon ultérieur. PanelForge ne cherche pas à devenir un éditeur universel de graphes ComfyUI ni à découvrir automatiquement leurs paramètres.

## Vérification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

La suite couvre le domaine, les manifests, les transports, le stockage, l’orchestration et les API du Lab. Les smokes réels nécessitent llama.swap et/ou ComfyUI joignables avec les modèles attendus.
