# Modifier avec Minimax — implémentation du 28 septembre 2026

L’atelier est ajouté à côté de « Modifier avec KREA » et « Modifier avec Qwen ». Il reprend le contrôleur, les styles et le cycle de projet de Qwen, avec une instance et un moteur distincts.

## Assistant par défaut et lancement en un clic

Depuis l’ajustement du 28 septembre 2026, les nouveaux projets MiniMax utilisent par défaut `local::unsloth/gemma-4-31B-it-qat-GGUF`, via Unsloth. La case Local est cochée. Un choix déjà enregistré dans un projet reste sélectionné et peut être changé.

Le bouton **Créer le prompt et lancer** sauvegarde la demande, prépare le prompt puis met automatiquement un rendu MiniMax en file dès que la réponse est validée. Cet enchaînement est géré côté serveur : il ne dépend pas du maintien de l’onglet ouvert. La file habituelle respecte les autres traitements de la machine.

Chaque commande possède une identité persistante : une répétition de la requête ou un double clic ne crée pas un deuxième rendu. En cas de prompt invalide, de contexte/réglages modifiés, de nouveau brouillon ou d’échec de planification, l’atelier explique pourquoi le rendu n’est pas parti et conserve le prompt reçu lorsqu’il est valide. La récupération manuelle d’un ancien prompt ne relance pas automatiquement sa génération.

Le bouton de rendu manuel reste disponible pour relancer un prompt prêt. L’atelier Qwen conserve son action de rédaction séparée.

Vérifications de cet ajustement : syntaxe de sept fichiers Python, compilation V8 de six sources applicatives/de scénarios sans exécution, HTML et imports du lanceur via `--help`. Neuf régressions de service/HTTP préparées ; scénario navigateur étendu au sélecteur réel, au modèle local et au clic unique ; assertion Qwen conservant le rendu manuel. **Aucun test fonctionnel, appel LLM, rendu ou redémarrage exécuté.**

Test supplémentaire à lancer par l’utilisateur depuis le checkout actif :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_minimax_prompt_render.py'
```

Le backend doit être rechargé au prochain redémarrage normal de PanelForge, puis la page actualisée.

## Parcours repris

- Import, projets récents, étapes, essais, conversation, prompt modifiable et sauvegarde automatique.
- Références pour l’assistant ou pour le rendu, réutilisation des images du projet, retour visuel d’un essai.
- Zone peinte, pinceau, rectangle, gomme, annulation et comparaison avant/après.
- Réglages persistants, seed conservée en texte pour éviter la perte de précision JavaScript, annulation du rendu.
- Validation puis étape suivante, reprise d’une étape, recadrage, DLSS et comparaison des presets DLSS.
- Téléchargement du projet et copie exportée. Les projets MiniMax ne se mélangent pas aux projets Qwen.

La composition sans source utilise au moins une référence de rendu, comme dans cet atelier Qwen. Ce changement ne crée pas un mode T2I pur et ne modifie pas les moteurs automatiques de Stories.

## Moteur et réglages

Le fichier `workflows/image.edit/minimax-h3-still/1.0.0/workflow.json` est la copie exacte de `Image Edit Minimax.json` fourni par l’utilisateur. Son SHA-256 est `dca8614c053ce994f45c26c97288118fc4833ca058cfa266dfebcb8296b2215c`.

Le manifeste versionné contient les identités des nœuds et les liaisons. Les noms des modèles, les VAE, le CLIP, le loader hybride FL2VA/Ref2VA et son assemblage sont conservés. L’adaptateur remplace le prompt, la seed, les steps, les dimensions et la destination de sortie ; il ajoute les références nécessaires.

| Réglage | Comportement |
| --- | --- |
| Sampling | er_sde, scheduler beta, denoise 1 |
| Steps | 18 au départ, modifiables |
| Résolution initiale | Aire du preset : 2016 × 3584, soit environ 7,2 millions de pixels |
| Édition | Ratio de la source conservé, dimensions arrondies au multiple de 32 |
| Composition | Format choisi dans l’interface, 9:16 au départ |
| Autres résolutions | Taille source, 1, 2, 4 ou 8 MP, selon la convention 1024² déjà utilisée par l’atelier |
| Limites de sortie | De 64 à 4096 pixels par côté ; réduction proportionnelle si nécessaire |
| Références | 9 images maximum au rendu, source et zone peinte comprises |
| Préparation des références | La chaîne du preset applique 1 MP / nearest-exact, puis le conditionnement H3 conserve ref_image_size=max |
| Couleurs | Brut au départ ; harmonisation locale avec la source disponible et brut archivé |
| Seed | Aléatoire à la création du projet, puis réutilisable comme dans Qwen |
| CFG / prompt négatif | Absents de ce preset ; contrôles masqués et paramètres rejetés par l’API |

Le changement de résolution concerne le latent et le conditionnement simultanément. Le prétraitement des références reste celui du workflow fourni. La seed présente dans le JSON est conservée dans l’original versionné ; chaque nouveau projet suit le comportement de variation de l’atelier.

## Zone peinte

La zone peinte reste un guide spatial. Le graphe fourni ne réalise pas de composition finale limitée par un masque et ne protège donc pas les pixels extérieurs.

En édition, l’ordre envoyé à MiniMax est :

1. `<Picture 1>` : source.
2. `<Picture 2>` : guide noir et blanc, si une zone est définie ; le blanc indique où concentrer la modification.
3. Références actives de rendu, dans leur ordre enregistré.

Sans guide, la première référence ajoutée occupe Picture 2. En composition sans source, la première référence occupe Picture 1. Les inspirations réservées à l’assistant n’occupent aucun emplacement de rendu.

La source et le guide sont téléversés dans un PNG RGBA : les couleurs portent la source et l’alpha inversé encode le masque attendu par LoadImage. Le graphe reconvertit ce masque en image de référence. L’assistant voit aussi le guide et explique son rôle dans le prompt.

Le traitement effectif du guide, les raccords et la fidélité des éléments non ciblés doivent être qualifiés sur les premiers rendus. Aucun rendu de qualification n’a été lancé pendant cette implémentation.

## Prompter dédié

`application/minimax_edit_assistance.py`, version `1.0.0`, opération `minimax.edit.assistance@1.0.0`.

- Explication française et prompt anglais ; chaque entrée réelle est identifiée par son label exact `<Picture N>`.
- Retouche simple : instruction concise, changement demandé et attributs à conserver.
- Demande complexe : sections subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music. Un seul instant ; audio N/A.
- Distinction explicite entre les attributs modifiés et conservés, sans ajout automatique d’une nouvelle esthétique.
- Le texte visible conserve ses caractères et sa langue. Une suppression reconstruit les surfaces voisines, sans supposer qu’il s’agit toujours du fond.
- Les images, les anciens prompts et les libellés restent des données de référence. Les références uniquement destinées à l’assistant et le résultat montré pour retour visuel ne deviennent pas implicitement des entrées du moteur.

Une modification des références ou du guide invalide le prompt préparé. Les essais en file conservent leur propre contexte, leurs réglages et leur provenance.

## Organisation technique

- Service partagé avec Qwen, auquel MiniMax injecte sa politique de réglages et son prompter.
- Contrôleur navigateur partagé, monté deux fois : identifiants, stockage local et événements DLSS isolés.
- API : `/api/image-lab/minimax-edit`.
- Projets : `workspace/minimax_edits`, identifiants `minimax-…`.
- Copies exportées : dossier `Minimax Projects`, voisin du dossier KREA configuré.
- Recette : `minimax.h3_still_edit@1.0.0`.
- Les sauvegardes Qwen antérieures restent lisibles ; l’absence historique du champ engine est acceptée pour leur stockage.

Aucune dépendance ajoutée. Les modèles et nœuds ComfyUI doivent être disponibles sur le serveur déjà configuré pour l’atelier Edit, comme pour le JSON fourni.

## Vérifications et prise en main

Contrôles réalisés : syntaxe de 20 fichiers Python ; lecture des deux JSON ; identité du workflow avec l’original ; liaisons du manifeste ; absence d’identifiants HTML dupliqués ; 97 contrôles pour chacun des deux ateliers ; compilation V8 de huit scripts applicatifs/de scénarios sans les exécuter ; `git diff --check` ; imports du lanceur via `scripts/run_lab.py --help`.

Tests préparés, **non exécutés**, conformément à AGENTS.md : édition/guide/contexte figé, rôles des références, isolation Qwen/MiniMax, API, dimensions et conservation des modèles, limite de références, composition, validation/reprise/export, recadrage/annulation/DLSS, atelier non configuré, parcours navigateur commun et navigation.

Depuis `D:\Code\panelforge-krea2-flux`, l’utilisateur peut lancer les vérifications ciblées :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_minimax_edit.py'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_qwen_edit*.py'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_lab_web tests.test_navigation_and_resource_preview_browser
```

Aucun appel LLM, rendu, test fonctionnel ou redémarrage de service n’a été effectué. Le nouvel atelier sera disponible au prochain redémarrage normal de PanelForge choisi par l’utilisateur, puis après rechargement de la page.

Premiers essais conseillés : retouche de couleur sans guide ; remplacement local avec guide ; ajout d’une référence d’identité ; comparaison du brut et de l’harmonisation. Vérifier aussi qu’un projet Qwen existant s’ouvre normalement.
