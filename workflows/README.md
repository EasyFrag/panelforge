# Integrated workflows

Les workflows placés ici ont d'abord été découverts et validés manuellement dans ComfyUI. PanelForge ne crée pas automatiquement ces presets.

Convention active :

```text
workflows/
  <capability>/
    <model-family>/
      <version>/
        workflow_api.json
        manifest.json
        prompt.txt
```

Exemple :

```text
workflows/character.bootstrap/qwen-photo/1.0.0/
```

Une version publiée ne doit pas être modifiée. Une évolution crée une nouvelle version. Le manifest devra déclarer les bindings de nodes, les variables, modèles, LoRA, valeurs par défaut et sorties attendues.

Première recette intégrée :

```text
workflows/character.change_view/qwen-edit-2511-multiple-angles/0.1.0/
```

Elle est encore `experimental`. Le workflow et le squelette de prompt sont protégés par leurs hashes; les bindings et valeurs critiques sont vérifiés avant construction d'un run.
