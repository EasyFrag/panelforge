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

Recettes intégrées :

```text
workflows/character.change_view/qwen-edit-2511-multiple-angles/0.1.0/
workflows/character.change_view/qwen-edit-2511-multiple-angles/0.2.0/
workflows/image.generate.t2i/krea2/0.1.0/
workflows/video.generate.ref2v/minimax-h3-ref2v/0.1.0/
```

Elles restent `experimental`. Le workflow et le squelette de prompt sont protégés par leurs hashes ; les bindings et valeurs critiques sont vérifiés avant construction d’un run. La version `0.2.0` conserve exactement le snapshot exécutable de `0.1.0` et ajoute un contrôle manifest explicite pour la force de la LoRA d’angle. Seule la valeur `1.0` est qualifiée ; les autres valeurs sont des overrides expérimentaux.

La recette Video Lab MiniMax H3 `0.1.0` accepte strictement une à trois
références ordonnées. Son snapshot ne contient ni image ni prompt d’exemple :
PanelForge compile les références, le prompt, le ratio, les mégapixels, la
durée, les steps et la seed, puis retire les slots d’images inutilisés avant
soumission.

La recette KREA2 `0.1.0` compile seulement le prompt positif, le checkpoint
UNET qualifié, le ratio, les mégapixels, la seed et un préfixe de sortie propre
au run. Son snapshot est nettoyé des branches LoRA et refine prompt du workflow
d’exploration, conserve le sampling validé à huit steps et produit exactement
un PNG via le nœud `SaveImage` déclaré dans le manifest. Elle n’expose aucune
preview intermédiaire.
