# KREA2 Assisted V5 — templates wildcard locaux

## Portée

- V3 est renommée `V3 · STABLE` et devient le choix par défaut pour un nouveau projet.
- V4 reste disponible et conserve sa recherche dans les 15 062 scènes statiques.
- V5 ajoute les 358 templates KREA2 du pack local, sans importer les trois corpus chinois.
- Aucun appel LLM supplémentaire : V5 garde le brief de recherche puis le rédacteur de V4.

## Source locale

Par défaut, le lanceur lit sans les modifier :

`%USERPROFILE%\Downloads\SFW15000QwenZImage15000_porV20500010000`

La racine est configurable avec `--krea2-wildcards-root` ou
`PANELFORGE_KREA2_WILDCARDS_ROOT`. Les 15 YAML de templates et les quatre
`shared-*.yaml` sont obligatoires. Les aperçus PNG sont facultatifs.

## Recherche hybride

1. Le LLM construit le même brief anglais structuré que V4.
2. La bibliothèque de scènes retourne trois candidats.
3. Le moteur wildcard classe localement les archétypes par action, participants,
   interaction, position, cadrage, décor et mots du descripteur.
4. Un template fort est placé en premier avec deux scènes. Un template moyen
   est proposé en second. Un template faible est écarté au profit des trois scènes.
5. Le template retenu est compilé entièrement : références récursives, poids et
   choix inline sont résolus. Le marqueur de ratio est extrait au lieu d’être envoyé
   dans le prompt.
6. Un seul exemple complet épinglé est fourni au rédacteur, comme en V4.

Le prompt compilé, le `template_id`, le `variant_seed` et le ratio recommandé
sont persistés dans le projet. « Nouvelle variante du template » conserve
l’archétype et change uniquement ses choix locaux, sans appel LLM.

## Interface

- Les cartes distinguent « Template » et « Scène ».
- L’aperçu du pack est servi uniquement pour un identifiant de template chargé.
- Le ratio est informatif : il ne remplace pas silencieusement le ratio de rendu.
- Le statut indique séparément le nombre de scènes et de templates disponibles.
- V5 est indisponible si l’index V4 ou le pack wildcard manque ; aucun repli
  silencieux vers V3.

## Compatibilité et limites

- Schéma Assisted 14, lecture des schémas 1 à 13 conservée.
- Le pack contient des templates oral/deepthroat/handjob mais aucun footjob ;
  une recherche footjob reste donc sur les scènes du corpus et peut être faible.
- Les corpus chinois ne sont ni copiés, ni indexés, ni consultés par V5.
- PyYAML 6 est une dépendance explicite ; elle était déjà présente dans
  l’environnement PanelForge contrôlé.
- Le pack et les aperçus restent dans Downloads. Les déplacer exige de modifier
  la racine configurée.

## Validation réalisée

- Analyse syntaxique AST des fichiers Python concernés.
- `git diff --check`.
- Chargement en lecture seule du pack réel : 358 templates, 15 fichiers de
  templates, aucune référence wildcard manquante.
- Contrôles ciblés sans LLM ni rendu :
  - fellation POV hôtel → `action-partner-giving-oral-pov`, pertinence forte ;
  - catalogue debout → template SFW partiel ;
  - arbre en laine → template faible, donc repli sur les scènes V4.
- Les tests automatisés sont préparés mais non exécutés conformément aux
  instructions du worktree.

## Tests utilisateur

`python -m unittest discover -s tests -p "test_krea2_assisted_v5.py"`

`python -m unittest discover -s tests -p "test_krea2_assisted_v4.py"`

`python -m unittest discover -s tests -p "test_krea2_assisted_web.py"`

`python -m unittest discover -s tests -p "test_krea2_assisted_ui.py"`
