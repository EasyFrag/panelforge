# PanelForge

PanelForge construit des personnages visuels cohérents, leurs références et des panels approuvés par chapitre.

## État

Le projet est volontairement limité à un squelette architectural. Aucun framework UI, moteur de jobs, stockage complexe ou pipeline narratif n'est encore choisi.

## Principes

- Le canon visuel est constitué d'images approuvées et versionnées.
- Les workflows et prompts sont découverts manuellement dans ComfyUI, puis intégrés comme presets immuables.
- Les features échangent des contrats explicites; elles ne recherchent jamais implicitement « le dernier fichier ».
- Le domaine ne dépend ni de ComfyUI, ni du stockage, ni d'un fournisseur LLM.
- La V1 vise des panels approuvés par chapitre. La vidéo est hors périmètre.

## Premier jalon

```text
fiche personnage manuelle
  -> génération de candidats
  -> sélection
  -> édition image-to-image
  -> canon approuvé
```

## Arborescence

- `src/panelforge/domain`: concepts métier purs.
- `src/panelforge/application`: cas d'usage et orchestration.
- `src/panelforge/features`: frontières fonctionnelles côté produit.
- `src/panelforge/infrastructure`: adapters ComfyUI, presets et stockage.
- `workflows`: workflows ComfyUI validés manuellement et versionnés.
- `workspace`: données locales générées, ignorées par Git.

## Vérification

```powershell
python -m unittest discover -s tests
```
