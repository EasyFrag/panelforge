# Consignes LLM actives et historiques

Ouvrir **Recettes LLM** dans la barre supérieure de PanelForge, ou **Consignes
LLM** près de la recette H3 Base / REF2V. L'éditeur travaille sur des fichiers
persistants du workspace, séparés des anciens cookbooks du dépôt.

## Sources actives

Les six recettes actuelles sont enregistrées explicitement dans
[`EDITABLE_RECIPES`](../src/panelforge/application/prompt_recipes.py).
Chaque couple ID/version possède son propre paquet. Aucune édition ne se
propage à une autre famille ou à l'autre mode H3/REF2V.

```text
<workspace>/prompt_recipes/
  minimax.h3.fl2va.classic.cinematic.planned/1.0.0/
    active.json                  # référence persistante de la révision active
    revisions/1/
      plan.system.txt            # consignes du Plan
      writer.system.txt          # consignes de la Rédaction
      revision.system.txt        # révision du prompt avant rendu
      render.system.txt          # ajustement après rendu
      camera_contract.txt
      ...                        # règles conditionnelles, par fonction
      manifest.json              # date, note, variables et empreintes
    revisions/2/
      ...
```

Utiliser **Enregistrer et appliquer** pour créer une nouvelle révision et
l'activer, puis **Appliquer cette version** pour revenir à une ancienne.
Les fichiers des révisions sont consultables directement ; les modifier en
place invalide leurs empreintes. Pour une édition dans un outil externe,
copier le texte puis le recoller dans l'éditeur et enregistrer une nouvelle
révision. L'interface est la voie d'activation, pour garder les historiques fiables.

La révision 1 reprend les consignes avant ce patch. Classique initialise une
révision 2 qui précise le contrat des cibles caméra ; cette précision apparaît
aussi dans la description du champ du schéma envoyé au Plan. Le format du
Plan et les validateurs restent dans le code.

`_defaults/` contient les textes conditionnels initiaux extraits du code.
Son manifest référence explicitement chaque fragment et ses éventuelles
variables. Ces fichiers initialisent les paquets à la première utilisation ;
un paquet déjà enregistré conserve ses propres textes. Les anciens parcours
gardent leurs constantes de compatibilité et leurs comportements.

## Sources historiques

[`prompt_cookbooks/`](../prompt_cookbooks) conserve les recettes originales,
leurs identifiants, versions et blocs partagés à versions exactes. Ce stockage
constitue la bibliothèque historique et le point de départ de la migration.
Il n'est plus nécessaire de chercher parmi ces archives pour modifier les six
recettes actuelles : leurs textes effectifs sont accessibles dans l'éditeur.
Le chargement d'une recette par ID/version ne parcourt plus tous les cookbooks.

Les appels passés conservent leurs messages exacts dans
`<workspace>/video_llm_traces/`, consultables depuis les rendus. La révision
active et le prompt H3 déjà écrit sont deux choses différentes : relancer
uniquement une vidéo n'appelle pas le LLM et ne réécrit pas son prompt.
