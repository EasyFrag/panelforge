# Replacer une image Assisted dans un décor

Patch du 8 septembre 2026. La création des images reste dans **KREA Assisted**.
Une passe **Identity Edit à deux images** tente ensuite de les intégrer dans un
décor commun. La composition locale par masque d’Assisted a été retirée à la demande
de l’utilisateur ; ses résultats enregistrés restent accessibles. Le masque de
**Modifier avec KREA2** est conservé.

## Parcours

1. Dans Assisted, choisir un essai réussi puis **Replacer dans un décor**.
2. Choisir un autre essai, la référence initiale de l’atelier ou importer un décor.
   Les deux références sont visibles : **image 1 = décor**, **image 2 = sujet/action**.
   Un décor vide évite la concurrence avec un personnage déjà présent.
3. Ajuster l’instruction préremplie. Elle sépare architecture/caméra fixes et éléments
   évolutifs : personnage, outils, liquide ou diamants au sol. La dernière base est
   mémorisée dans ce navigateur pour l’atelier Assisted ; les brouillons du dialogue
   restent dans l’onglet jusqu’au rechargement.
4. **Ouvrir dans l’atelier Edit** prépare un atelier distinct, sans LLM ni rendu.
   Chaque requête possède un identifiant stable : réessayer après une erreur ne
   crée pas un deuxième atelier. Changer l’instruction ou le décor permet un nouveau départ.
5. Le prompt est prérempli et éditable. **Envoyer** permet, si souhaité, de le retravailler
   avec le LLM. **Lancer un rendu** déclenche explicitement la génération.
6. Comparer les essais, utiliser un résultat en feedback, retoucher ou améliorer
   ses détails avec les outils Edit existants. **Valider et continuer** exporte le
   résultat choisi et prépare une étape classique depuis ses pixels, sans réinjecter
   automatiquement la seconde référence.

Pour une autre scène de la même séquence, repartir de sa génération Assisted et
réutiliser le **même décor maître**. Le résultat de l’intégration précédente n’est
pas automatiquement la nouvelle base. Les résultats de cette passe sont rangés
dans l’atelier Edit, séparément de l’exploration Assisted et de sa mémoire.

## Réglages et limites du premier essai

- Nouvelle recette `krea2.identity_edit@0.3.0`, **Deux images · décor + sujet**.
  Les recettes 0.1.0/0.2.0 à une image restent intactes ; le défaut général reste 0.2.0.
  L’atelier à deux références propose uniquement la recette compatible. FireRed reste
  disponible dans les ateliers ordinaires, sans ignorer silencieusement une image.
- Départ : KREA2 Turbo, 10 steps, CFG 1, 1 MP modifiable, aucun LoRA de style repris
  automatiquement d’Assisted. Ratio proposé = ratio disponible le plus proche du décor
  orienté. Le réglage **Ref boost · sujet** vaut 4 par défaut ; la force du décor reste
  1 dans cette première recette, indiquée dans la note des paramètres.
- FIT et le chemin image/VAE sont branchés pour **les deux références**, ainsi que
  le latent cible pour pré-encoder avant le sampling. Le sujet n’est pas une simple
  image d’inspiration du LLM : ses pixels arrivent aussi au moteur de génération.
- Cette passe régénère l’image. Elle ne garantit ni décor identique au pixel, ni
  pose/accessoires exacts, ni conservation de la netteté Assisted. Évaluer séparément
  cohérence de la pièce, fidélité de l’action et qualité des textures, sur une paire
  représentative avant d’élargir le parcours. L’upscale reste une option ultérieure.

Rôles et branchements confirmés dans la [fiche du modèle](https://huggingface.co/conradlocke/krea2-identity-edit)
et le [code des nœuds](https://github.com/lbouaraba/comfyui-krea2edit/blob/main/__init__.py).
L’ordre entraîné est scène puis sujet ; les réglages optimaux pour ce scénario
n’ont pas été évalués pendant le codage.

## Contrats et provenance

- Les originaux sont conservés. Décodage/orientation en PNG avant l’envoi au LLM
  et à ComfyUI pour présenter les mêmes vues ; dimensions réelles du résultat lues
  à sa réception. Limites de décodage existantes réutilisées, pas de ratio strict
  de collage à 1 % : le modèle reçoit ici deux références indépendantes.
- Le décor appartient à `source_asset_id`. `subject_reference` stocke l’asset sujet,
  son origine Assisted, l’instruction initiale et l’identifiant de création. Cette
  paire est fixe pour tous les essais de l’étape ; restart et reprise de version
  conservent la référence. L’étape suivante classique abandonne le second input
  et le prompt de placement pour partir du seul résultat validé.
- Le LLM reçoit `STAGE SOURCE`, `SUBJECT REFERENCE` et, si choisi, `GENERATED FEEDBACK`.
  Ce dernier sert à l’évaluation et n’est pas un troisième input ComfyUI. Le contrat
  des deux références complète le writer sélectionné uniquement pour ces ateliers.
- Stockage Edit **schéma 10**, lecture 1–9. Assisted reste au schéma 7 pour lire les
  anciennes compositions, leur feedback, leurs branches et leurs exports. Création
  et reprise du masque Assisted supprimées, ainsi que leurs anciennes routes API.
- API de préparation `POST /api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/restage`
  (`scene_asset_id`, `instruction`, `request_id`). Import décor : `POST …/projects/{project_id}/scene-images`.
  Le premier POST ne crée ni essai, ni exécution. Une reprise identique retrouve
  l’atelier ; même identifiant avec un autre contenu renvoie HTTP 409.
- Export de la chaîne Edit : image choisie, référence sujet séparée et provenance
  dans le sidecar et le manifeste. Le décor initial reste dans `00_original`.
- Graphe 0.3.0 : SHA-256 `63643c41c4585cb9720beb14264e606d56c23c3ecf4c48e18bd736f5371f634e`.
  Les identifiants de nœuds et nouveaux branchements sont dans le graphe/manifeste,
  sans duplication d’un moteur de file ou de génération dans Assisted.
- Caches JS Assisted **20260908.2**, dialogue restaging **20260908.1**, Edit **20260908.7**,
  CSS **20260908.3** ; Canvas Edit existant conservé. Pas de dépendance ajoutée.

## Vérifications à lancer par l’utilisateur

Les tests sont **préparés, non exécutés**. Ils utilisent des images temporaires,
faux gateways et faux ComfyUI, sans modèle réel ni serveur Lab. Le navigateur utilise
Chromium déjà installé, sans téléchargement.

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_krea2_restaging tests.test_krea2_restaging_browser tests.test_firered_edit_browser tests.test_krea2_edit_workflows tests.test_krea2_edit_web tests.test_krea2_retouch tests.test_run_lab_build
```

Couverture préparée : rôles des deux images dans les encodages positifs/négatifs
et le patch visuel, orientation, préparation sans calcul, retry sans doublon,
choix de recette compatible, transmission des deux inputs au rendu simulé et au
LLM simulé, feedback exact, export/réouverture, étape suivante à une seule image,
schémas historiques, anciens composites Assisted et brouillons du dialogue.

Contrôles de l’agent : syntaxe et liaisons statiques uniquement. Aucun test, appel
LLM, génération, téléchargement de modèle, redémarrage ou modification du workspace
runtime. Le tag `stable-avant-masque-2026-09-06` reste le point de restauration.
