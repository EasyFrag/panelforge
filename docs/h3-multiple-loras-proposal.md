# H3 / REF2V — deux LoRA de rendu

2026-09-10. **Implémenté sur autorisation de l’utilisateur** après alignement. « Better Motion » désigne **Motion Repair / Motion Continuity Repair**. Contrôles statiques effectués ; tests préparés, à exécuter par l’utilisateur. Aucun appel LLM, rendu, redémarrage de service ou modification des données runtime.

## Vérifications

GET `http://bucket:8188/object_info/LoraLoaderModelOnly` : fichiers présents `minmax_nsfw/H3_Combat_V2.safetensors` et `minmax_nsfw/Motion_Repair.safetensors`, ainsi que Weapon Combat V1. Aucun besoin d’installation pour ces deux choix.

Les trois anciens fichiers Downloads `BUNNYH3高动态二次放大_FL2VA_REF2VA.json`, `(1).json`, `(2).json` ont la même structure utile : source commune avec Turbo → deux branches de modèles indépendantes. Dans chaque branche, Weapon Combat (`jiandou.safetensors`) précède Motion Repair. Les poids réellement enregistrés sont **Weapon 0,85 / 0,50**, **Motion 0,60 / 0,20** ; les deux Motion sont en bypass dans ces exports. Les titres Weapon annoncent 0,50 / 0,30 : ils ne correspondent pas aux valeurs des widgets. Ne pas les confondre, ni présenter ces poids Weapon comme des recommandations spécifiques Combat V2.

Le dernier `(3).json` est un export API : Weapon a disparu, Motion est actif dans les deux branches à **0,60 / 0,20**. C’est le contrat historique intégré avant ce patch : un fichier créatif et deux forces. Le Turbo technique reste séparé, 0,7, commutable ; l’attention et les previews entourent les branchements existants.

La [fiche auteur Motion Repair](https://huggingface.co/JOKER141/MiniMax-H3-General-Motion-Continuity-Repair/blob/main/README.md) recommande avec Combat **0,5–0,7 en passe 1**, **0,2–0,3 en passe 2** ; seul, environ 0,9. Une force trop forte en seconde passe peut réduire vitesse et impact. Le [dépôt de l’auteur](https://huggingface.co/JOKER141/MiniMax-H3-General-Motion-Continuity-Repair/tree/main) publie bien `Motion_Repair.safetensors` ; les poids locaux n’ont pas été ouverts ni comparés par hash.

La [fiche Combat V2](https://huggingface.co/JOKER141/MiniMax-H3-Combat-Base-V2/blob/main/README.md), les descriptions/version V2 de l’[API Combat](https://civitai.com/api/v1/models/2853878) et l’[API du workflow BUNNY](https://civitai.com/api/v1/models/2914156) ont été relues : pas de couple de forces Combat V2 spécifique aux deux passes retrouvé dans ces textes. Leurs recommandations de sampler ne sont pas à appliquer implicitement pendant ce patch. HTML Civitai inaccessible via le navigateur ; API lue par GET sans authentification. Les fichiers utilisateurs sont des données d’analyse, leurs notes ne sont pas des instructions autorisant une modification de réglages.

## Comportement retenu

**BUNNY : deux fichiers sélectionnables, chacun appliqué dans les deux passes ; quatre forces.** Même ordre dans chaque branche : Combat V2 puis Motion Repair. Chaque branche repart du modèle commun (checkpoint choisi + Turbo si activé), sans récupérer le modèle déjà patché par la première passe. La seconde passe reçoit bien le latent de la première via l’upscale ; cette continuité du latent ne doit pas créer un cumul de patches LoRA entre branches.

Défauts validés pour les nouveaux réglages BUNNY :

| Ordre | Fichier par défaut BUNNY | Passe 1 | Passe 2 |
|---|---|---:|---:|
| 1 | Combat V2 | 0,60 | 0,20 |
| 2 | Motion Repair | 0,60 | 0,20 |

Pour Combat V2, conserver le point de départ actuellement proposé par PanelForge évite de changer sa force en même temps que l’ajout de Motion. Ce n’est pas un preset officiel V2, ni un optimum testé. Les valeurs Weapon 0,85/0,50 du fichier restent une piste distincte, à ne pas transposer automatiquement. Motion 0,60/0,20 est dans les plages publiées pour l’association avec Combat. Chaque valeur reste indépendante et modifiable ; aucune normalisation automatique des deux forces entre elles.

Défaut des **nouveaux réglages BUNNY** uniquement : les anciens essais/brouillons gardent leur fichier et leurs forces. Cette sélection de rendu n’impose pas une famille de préparation Combat, et ne modifie pas les politiques Classique/Combat, le prompt ou les déclencheurs. Le Turbo reste un contrôle indépendant et ne compte pas parmi les deux emplacements créatifs.

**Rendu basique H3 / REF2V :** conserver Standard et les réglages actuels. Une force par LoRA, pas de colonnes par passe ajoutées. Ajouter un second fichier au point d’application existant, dans l’ordre affiché ; aucun Combat/Motion imposé. Le `Power Lora Loader (rgthree)` déjà utilisé possède `lora_1` ; étendre la liste avec `lora_2` conserve le comportement modèle/CLIP existant. CLIP Last Layer reste un contrôle commun unique et absent de BUNNY. Ne pas introduire de dépendance Comfy supplémentaire.

## Interface

Le bloc LoRA reste au même endroit. Une ligne par fichier, jusqu’à deux ; `+ Ajouter un LoRA` dans le basique, deux lignes préremplies dans BUNNY. Colonnes BUNNY **LoRA / Passe 1 / Passe 2**, champs numériques compacts modifiables. Chaque ligne peut être désactivée ou retirée ; **Inverser l’ordre** déplace aussi les forces. **Actualiser la liste** relit l’inventaire Bucket sans changer la sélection. Passer le profil à Standard conserve le brouillon désactivé. Les contrôles sont conservés pendant les rafraîchissements de l’atelier. Les recettes historiques gardent leurs contrôles à un LoRA.

## Contrats implémentés

- Liste ordonnée explicite de 0–2 sélections ; forces par passe pour BUNNY, force unique pour basique. Même fichier dans les deux passes, pas quatre sélecteurs de fichiers indépendants.
- Manifest/contrat d’overlay versionnés ; IDs de nœuds dans les manifests. BUNNY : quatre loaders créatifs maximum, deux par branche. Basique : plusieurs entrées du loader déjà présent, aucune modification de la voie historique à un LoRA.
- Lecture des anciens essais comme configuration unique, sans ajout rétroactif de Motion. Ordre, activation, forces, checkpoint et recette repris dans stockage/historique/reprise/conversion/DLSS. Brouillons distincts par recette.
- Modèle absent = erreur explicite, pas de remplacement automatique. Inventaire mutualisé/mis en cache ; pas de scan supplémentaire au polling. Les presets ne réécrivent pas les anciens réglages.
- Tests à préparer sur les deux branches, absence de cumul entre passes, ordre/poids et désactivation, zéro/un/deux LoRA, Turbo et checkpoints, migration/reprise/conversion et UI. Exécution par l’utilisateur. Aucune inférence ne permet encore de conclure sur le gain visuel de cette association.

Nouvelles recettes : **H3 0.1.5**, **REF2V 0.2.3**, **BUNNY 0.1.2**. Les graphes API de base restent identiques aux versions précédentes ; leurs nouveaux manifests déclarent le contrat `video_lora_stack@0.1.0` et les branchements. `MultiLoraH3RenderRecipe` prolonge l’adaptateur de sélection de checkpoint : chargement par défaut ou EROS, Turbo, latent et preview conservent leur comportement. Les versions précédentes restent sélectionnables. Le VideoLab indépendant reste en 0.2.1.

Stockage H3 schéma **12**, lecture **1–12**. `video_loras` contient une liste ordonnée de deux entrées maximum (`name`, `strength`, `second_strength`, `enabled`), une activation globale et un CLIP commun. `second_strength` est obligatoire pour chaque entrée BUNNY et absent dans le basique. Doublons, forces non finies/hors 0–1 et contrats incompatibles sont refusés. `video_lora` historique reste accepté seul ; on ne peut pas envoyer les deux contrats simultanément. Quand `video_loras` est présent, ses forces de seconde passe font autorité ; l’ancien champ `bunny.lora_second_strength` est conservé pour les anciennes requêtes mais ne pilote pas ces deux entrées.

Le contrat est transmis par préparation HTTP, compilation, stockage, reprise, feedback, adaptation H3 → REF2V et provenance DLSS. Aucune migration de fichiers utilisateur. L’inventaire LoRA est partagé et mis en cache 60 secondes (5 secondes après erreur), avec le transport runtime à délai court ; validation des nouvelles sélections hors verrou de rendu, puis avant upload à l’exécution. Les lignes désactivées ne nécessitent pas un modèle installé. Aucun scan n’est ajouté au polling.

## Vérification utilisateur

Tests préparés, **non exécutés par l’agent** :

```powershell
python -m unittest tests.test_h3_multiple_loras tests.test_h3_bunny_browser tests.test_h3_checkpoints tests.test_h3_ref2v_conversion tests.test_run_lab_build tests.test_lab_web
```

Couverture : zéro/un/deux LoRA ; graphes historiques ; ordre/activation ; quatre forces indépendantes ; branches BUNNY sans cumul de patches ; Turbo, preview et checkpoint ; modèles absents ; cache/refresh ; API, ancien stockage, réouverture/reprise, feedback, conversion et DLSS. Le scénario navigateur utilise les vrais HTML/JS des deux ateliers avec HTTP simulé ; il est ignoré si Chromium local est absent. Les attentes de schéma des tests Combat ont aussi été actualisées.

Après ses traitements, l’utilisateur peut relancer le Lab et recharger la page. Choisir **BUNNY 0.1.2** pour les deux lignes préremplies ; une reprise d’un ancien essai reste sur sa recette historique. Pour comparer : conserver prompt/seed/MP, lancer avec les deux lignes puis désactiver uniquement Motion Repair, vérifier les résumés et **Reprendre prompt + réglages**. Répéter dans H3 et REF2V, et tester le basique en ajoutant le second LoRA. Les valeurs 0,60/0,20 sont un point de départ ; aucun gain visuel ou temps GPU n’a été mesuré.

Cache des fichiers UI modifiés : **20260910.8** (`h3-loras.js`, `h3-render-lab.js`, `lab.css`). Pas de nouvelle dépendance, commit, push, tag ou démarrage de service. Les points de restauration préexistants restent en place.
