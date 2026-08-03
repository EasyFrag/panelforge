# Integrated workflows

Les workflows placés ici ont d'abord été découverts et validés manuellement dans ComfyUI. PanelForge ne crée pas automatiquement ces presets.

Convention envisagée :

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
