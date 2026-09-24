# MiniMax H3 : VAE video INT8 ConvRot — 2026-09-24

Evolution autorisee apres l'alignement du 24 septembre, implementee dans `D:\Code\panelforge-krea2-flux`.

Les nouveaux essais H3 Base, Ref2V, BUNNY et Video Lab utilisent
`minimax_h3_video_vae_int8_convrot.safetensors`, y compris depuis les projets,
histoires et copies multilangues deja enregistres. Cette valeur exacte, sans
prefixe `vae/`, a ete confirmee par lecture de `http://bucket:8188/object_info/VAELoader`
pendant l'audit. Aucun telechargement ou chargement du modele n'a ete effectue.

## Changement

Le manifeste `workflows/video.vae/minimax-h3-int8-convrot/1.0.0/manifest.json`
declare explicitement 18 sources historiques : Latent Speed 0.1.0–0.1.7,
Ref2V 0.2.0–0.2.5, BUNNY 0.1.0–0.1.3. Il contient leurs identites et empreintes
sources, l'ID du loader video, la valeur attendue, le nouveau VAE et les empreintes
des graphes resultants. Les variantes portent le suffixe `+vae-int8-convrot.1`.

L'adaptateur d'infrastructure verifie ces contrats, puis remplace uniquement
`inputs.vae_name` du loader video apres compilation de la recette source.
L'empreinte de la variante porte sur le graphe source modifie serialise en JSON
UTF-8 compact (sans espaces, Unicode conserve). Comme auparavant, l'empreinte
du graphe compile pour l'essai est aussi enregistree separement.

Les graphes et manifestes historiques restent intacts. Cette forme evite de
dupliquer 18 graphes et conserve exactement les capacites de chaque version :
VAE audio, sampling, checkpoints, LoRA, resolutions, bypass/upscale et preview.
En particulier, Video Lab conserve le comportement de Ref2V 0.2.1 ; il ne
recupere pas implicitement le bypass de 0.2.5.

## Projets existants et historique

- La selection d'une ancienne version est resolue vers sa variante INT8 pour
  les nouveaux essais. Les reglages enregistres dans les histoires restent
  utilisables sans migration des documents.
- Un essai deja cree/en file/en cours conserve sa recette complete d'origine.
  Les anciennes empreintes sont encore verifiees ; aucune video historique
  ni workflow compile archive n'est reecrit.
- Le Video Lab garde aussi les recettes 0.2.1 et 0.2.0 pour executer/suivre les
  runs historiques connus. Un nouveau run utilise la variante de 0.2.1.
- L'interface restaure les controles d'un ancien essai avec la nouvelle
  identite de recette, y compris seed 64 bits, checkpoint, forces LoRA et
  controles BUNNY. Les reponses asynchrones perimees ne peuvent ecraser les
  reglages d'une selection plus recente.
- La reprise multilangue reconnait une video reussie sous la variante INT8
  meme si son setup conserve l'identifiant source. Un changement effectif
  de parametres exige toujours un nouvel essai. Les videos muettes deja
  reutilisees restent reutilisees.
- Il n'y a pas de repli silencieux vers FP16 si le loader ou l'empreinte du
  contrat ne correspond plus. Une nouvelle recette source exige une entree
  explicite dans le manifeste de mise a jour du VAE.

## Verification et activation

Effectue : syntaxe Python de huit fichiers concernes ; compilation syntaxique
du script JavaScript et de sa fixture, sans execution de leurs corps ; 18
empreintes sources et 18 empreintes de variantes ; controle du diff et relecture
par rapport a l'etat initial du worktree.

Six regressions ciblees preparees (cinq Python, une navigateur), plus le test
de construction du Lab actualise. Elles couvrent tous les modes/versions,
la comparaison des graphes complets sauf VAE, les options checkpoint/LoRA/upscale,
les empreintes invalides, les anciens essais en file, le Video Lab et la
restauration de l'interface. **Tests non executes**, conformement a AGENTS.md.
La disponibilite du fichier a ete verifiee ; aucun benchmark ou rendu GPU
n'a ete lance pour cette evolution.

Commandes a lancer par l'utilisateur depuis le worktree actif :

```powershell
python -m unittest discover -s tests -p "test_h3_video_vae*.py"
python -m unittest discover -s tests -p "test_run_lab_build.py"
python -m unittest discover -s tests -p "test_video_lab_runner.py"
python -m unittest discover -s tests -p "test_episode_localization*.py"
```

Apres la fin des traitements en cours, redemarrer le Lab puis Ctrl+F5.
Un nouvel essai doit enregistrer la version `+vae-int8-convrot.1` et le VAE
INT8 dans son workflow compile. Aucun redemarrage, test fonctionnel, LLM,
rendu, changement de donnees runtime, commit ou push n'a ete effectue ici.
