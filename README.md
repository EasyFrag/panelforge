# PanelForge

PanelForge est un atelier local pour construire un canon visuel cohérent, qualifier des recettes ComfyUI puis produire des panels narratifs à partir d’assets approuvés.

Le projet reste un monolithe modulaire : ComfyUI sert à découvrir manuellement les workflows, tandis que PanelForge les exécute comme des recettes explicites, versionnées et traçables.

## Première tranche utilisable

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

## Lancer le Lab

L’interface tourne sur le poste PanelForge et appelle ComfyUI à distance. Rien n’est installé dans l’environnement Python du serveur GPU.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python scripts\run_lab.py --base-url http://192.168.1.72:8188
```

Puis ouvrir `http://127.0.0.1:7860`.

Les données locales sont écrites sous `workspace/assets` et `workspace/runs`, tous deux ignorés par Git. Pour utiliser Tailscale, remplacer `--base-url` ou définir `PANELFORGE_COMFY_URL`.

## Architecture

- `domain` : assets, recettes, contrôles et cycle de vie immuable des runs ;
- `application` : orchestration d’un cas d’usage sans node ID ComfyUI ;
- `infrastructure/comfy` : transport HTTP minimal ;
- `infrastructure/presets` : validation et compilation des recettes versionnées ;
- `infrastructure/storage` : stockage local vérifié par SHA-256 ;
- `features/lab` : fine interface FastAPI et HTML/CSS/JavaScript natif ;
- `workflows` : snapshots ComfyUI et manifests explicites.

Les node IDs restent dans les manifests. Le domaine ne dépend ni de FastAPI, ni de ComfyUI, ni d’un fournisseur LLM.

## Feuille de route

### 1. Qualifier le Lab actuel

- refaire le smoke réel de `character.change_view` ;
- évaluer la matrice visuelle sur plusieurs personnages ;
- ajuster les bornes LoRA uniquement à partir des résultats observés.

### 2. Ajouter le mode Generate

- promouvoir l’expérience `character.bootstrap` en recette versionnée ;
- exposer prompt positif/négatif, résolution et LoRAs déclarées ;
- générer et comparer plusieurs candidats de personnage.

### 3. Ajouter l’assistance LLM locale

- compiler une intention simple vers un prompt adapté à une recette précise ;
- séparer demande utilisateur, proposition LLM et prompt réellement exécuté ;
- ajouter le `prompt jitter` Qwen : synonymes, réordonnancement et reformulation légère sans changer les invariants ;
- conserver la seed comme variation secondaire et protéger les triggers techniques.

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

La suite couvre le domaine, les manifests, le transport ComfyUI, le stockage, l’orchestration et l’API du Lab. Le smoke réel nécessite une instance ComfyUI joignable avec les modèles et custom nodes de la recette.
