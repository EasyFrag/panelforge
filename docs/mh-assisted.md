# Création Assistée MH

Atelier Image Lab ajouté le 28 octobre 2026, immédiatement après Création assistée.
Il produit uniquement des images fixes avec le workflow MiniMax H3 Still déjà utilisé
par Modifier avec Minimax. Les projets et leur historique sont distincts.

## Parcours

1. Donner un nom et, si nécessaire, une intention.
2. Choisir une pose du catalogue, une ou plusieurs images de référence, ou les deux.
3. Choisir le preset personnel, la langue du prompt (anglais/chinois), la direction
   artistique et le modèle LLM. Le modèle local Gemma est proposé par défaut quand disponible.
4. Cliquer sur **Créer et proposer un prompt**, puis affiner par la discussion ou
   modifier directement le prompt.
5. Régler le ratio, la résolution, les steps et la seed, puis **Lancer un rendu**.

Une pose seule suffit ; le texte seul n’est pas pris en charge en V1. La pose décrit
la posture et le point de vue. L’intention définit les sujets et la scène, et la
direction artistique définit leur traitement visuel. Le mannequin gris, son fond
et son absence de visage ne sont pas des attributs à reprendre automatiquement.

Le popup de poses regroupe les angles d’une même pose. Recherche, famille,
catégorie, angle et pagination permettent de parcourir le catalogue. Une pose et
un angle sont actifs à la fois ; une pose du catalogue peut elle-même montrer un duo.
Les 288 noms de poses, familles, catégories et angles sont présentés en français.
La famille **Corps entier · NSFW** regroupe les 80 poses précédemment affichées
sous « Corps entier · expressif ». Les catégories suivent la famille et la
recherche ; les angles suivent ensuite les catégories disponibles. Un choix
devenu incompatible est remis à « Tous ». La recherche ignore les accents et
permet aussi de retrouver les noms japonais originaux, conservés en métadonnées.

Les traductions sont appliquées à la lecture : aucun bouton d’installation n’est
nécessaire pour traduire un index existant, et les révisions des images en cache
et les essais déjà enregistrés restent inchangés. Une future pose sans traduction
reçoit un libellé français neutre en attendant sa traduction.

Les images supplémentaires peuvent être réservées à l’assistant ou transmises au
moteur, avec un rôle explicite. MiniMax accepte au total neuf références de rendu,
pose comprise. L’exemple visuel du preset est envoyé à l’assistant uniquement.

Le formulaire de création et le projet ouvert permettent de sélectionner plusieurs
images en une fois. Chaque image affiche immédiatement une miniature agrandissable,
son utilisation et un rôle facultatif modifiable. Le compteur inclut la pose dans
les neuf références de génération ; l’assistant accepte 32 images au total, exemple
du preset compris. PNG, JPEG et WebP sont acceptés, avec 25 Mo par image et 100 Mo
par ajout. Les images initiales sont toutes enregistrées avant le premier prompt.

Une image peut être retirée ou remplacée individuellement. Le remplacement conserve
sa place et son rôle et reste possible lorsque les neuf places sont occupées.
Les références des essais précédents restent conservées. Un ajout multiple est
enregistré en une seule opération ; réessayer après une réponse réseau perdue ne
duplique pas les images. Dans un projet ouvert, utiliser **Ajouter les images
sélectionnées** avant de préparer un nouveau prompt.

## Presets, langue et directions artistiques

Le catalogue et le gestionnaire de presets personnels existants restent accessibles.
Leur contenu artistique et leur exemple visuel sont réutilisés, sans appliquer les
checkpoints, LoRA ou paramètres de sampling KREA au moteur MiniMax. La direction
artistique et la langue peuvent être choisies indépendamment du preset et de la pose.
Cette V1 réutilise les presets existants ; l’enregistrement d’un essai MH comme
nouveau preset personnel n’est pas encore proposé.

Un changement de pose, de langue, de preset, de direction ou de références invalide
le prompt préparé. **Affiner le prompt** l’actualise ; une modification manuelle
explicite reste possible. Les brouillons locaux sont préservés pendant le suivi
et l’actualisation. Le bouton **Enregistrer les modifications** conserve les champs
modifiés ; ils sont aussi enregistrés avant un rendu, un échange ou un changement
de projet. Quitter la page avec des modifications non enregistrées déclenche
l’avertissement du navigateur.

## Pose et anatomie dans les prompts

Le contrat MH `1.1.0` fait examiner la pose avant la rédaction : point de vue et
cadrage, orientation du bassin et du buste, appuis visibles et parties masquées.
Les notes d’incertitude du catalogue doivent être respectées ; un genou hors cadre
ne permet pas d’affirmer sa flexion. Une référence d’identité fournit l’apparence
sans imposer sa vue frontale ni rendre tous ses accessoires visibles.

Pour les propositions de l’assistant utilisant une pose, l’application ajoute au
prompt final un paragraphe sur la continuité anatomique et les articulations
naturelles, sans sphères mécaniques ni raccords de mannequin. Ce paragraphe suit
la langue choisie, anglais ou chinois, et préserve les styles ou sujets articulés
explicitement demandés. Il est visible et modifiable dans le prompt, avant le rendu.

L’assistant reçoit les références ajoutées, retirées ou modifiées et le changement
de pose par rapport au contexte du prompt précédent. Les anciennes descriptions
de l’assistant liées à d’autres références sont écartées de la discussion transmise,
en conservant les demandes de l’utilisateur. Un contexte antérieur inconnu impose
une nouvelle lecture des références. Les choix artistiques encore demandés restent
à conserver. Tout se fait dans un seul appel, sans évaluation visuelle automatique.

Les essais et réponses historiques restent inchangés, ainsi que les prompts
explicitement saisis à la main. Après activation du nouveau code par redémarrage,
utiliser **Affiner le prompt** sur un ancien projet pour appliquer ces nouvelles
consignes. Leur efficacité visuelle reste à comparer à références, seed et réglages
identiques, d’abord sans LoRA ; aucune génération de contrôle n’est automatique.

## Essais et réglages

Chaque essai conserve les images effectivement utilisées, la pose et son angle,
les snapshots du preset et de la direction, la langue, le prompt et les réglages.
Changer les choix du projet ne modifie pas les essais en file ou terminés.
Un résultat peut devenir le retour visuel d’un échange. **Reprendre ces choix**
restaure les choix d’un essai sans le modifier. Images et archive du projet sont
téléchargeables ; annulation et reprise des rendus suivent le service existant.

Défauts : 2 MP, 9:16, 18 steps, références à 1 MP, nouvelle seed à chaque rendu.
Le sampler, le scheduler et le graphe sont ceux du manifeste MiniMax versionné.
La seed reste une chaîne de caractères pour conserver sa précision entière.

### LoRA MiniMax pour les images

**Création Assistée MH** et **Modifier avec MiniMax** partagent un sélecteur de
quatre LoRA maximum. **Ajouter un LoRA** ouvre un catalogue recherchable ; seuls
les LoRA choisis occupent une ligne. Cliquer sur le nom permet de remplacer le
fichier. Chaque ligne propose activation, force numérique précise entre 0 et 1,
montée/descente dans l’ordre, fiche d’information et retrait. Une force nulle
désactive également l’effet. Aucun fichier n’est sélectionné par défaut.
Le bouton **↻** actualise le catalogue sans effacer les choix, même si un fichier
a disparu. Les doublons sont exclus du sélecteur. La fiche réutilise celle des
LoRA MiniMax H3 ; son chargement se fait uniquement lorsqu’elle est ouverte.

Le catalogue provient du ComfyUI de rendu : seuls les chemins `.safetensors`
sous `minmax_nsfw/` sont proposés. Le dossier personnel
`Y:/models/ComfyUi/loras/minmax_nsfw` doit donc être exposé sous ce nom par ComfyUI.
La présence d’un fichier ne garantit pas sa compatibilité ni son résultat visuel
sur le modèle hybride Still. Aucun mot déclencheur n’est ajouté au prompt.

Les choix, les forces et les activations sont enregistrés dans le projet, figés
dans chaque essai et restaurés par **Reprendre ces choix**. Le récapitulatif des
essais indique aussi les LoRA désactivés. Un LoRA actif absent ou un catalogue
inaccessible bloque le nouveau rendu avec un message explicite ; désactiver le
LoRA permet de rendre sans lui. Les presets KREA ne sélectionnent pas de LoRA MH.

Le manifeste `image.edit/minimax-h3-still/1.4.0` chaîne les adaptateurs actifs
avec le nœud standard `LoraLoaderModelOnly`, après le chargement hybride et avant
l’attention. Le CLIP et ses couches restent ceux du workflow initial. Sans LoRA
actif, le graphe produit conserve le comportement de la version 1.3.0. Les anciens
projets sans champ `loras` restent valides. Aucun téléchargement de poids ni
chargement de modèle n’est nécessaire pour afficher le catalogue.

Les files et la protection thermique sont partagées avec les autres ateliers.
Une commande de création, de prompt ou de rendu rejouée avec le même identifiant
ne lance pas un second travail. Les contrôles de révision protègent les projets
ouverts dans plusieurs fenêtres. Le suivi navigateur s’arrête lorsque l’atelier
ou la page est masqué ; les traitements continuent côté serveur.

## Catalogue local

Source : [AI Pose Gallery](https://ai-pose-gallery.pages.dev/). Au 28 octobre 2026,
l’index consulté contient 288 poses et 1 439 vues.

L’index est installé dans `workspace/catalogs/ai-pose-gallery/catalog.json` par
le bouton du popup ou lors de la mise en place initiale. Les miniatures consultées
et les images choisies sont ensuite téléchargées et conservées à la demande.
Une pose utilisée devient également un asset du projet : elle reste disponible
pour ses essais indépendamment des modifications futures du site.

Les données du site sont lues comme JSON ; son JavaScript n’est pas exécuté.
Les identifiants et chemins sont validés, les téléchargements bornés et limités
à l’origine du catalogue, et les images vérifiées avant mise en cache.
Une actualisation invalide conserve l’index précédent.

Ce catalogue est une installation personnelle. Les images ne sont pas incluses
dans le dépôt Git ni redistribuées avec PanelForge. Les conditions du site
autorisent leur usage comme référence mais interdisent leur redistribution.

### Références personnelles de face

La famille **Mes poses** contient les deux vignettes fournies par l’utilisateur :
**PF001 — Genoux repliés** et **PF002 — Jambes levées en V**, avec l’angle **Face**.
Leurs fichiers PNG sont conservés tels quels, en 94 × 92 et 120 × 165 pixels.
Aucun autre angle ni détail n’a été généré. Leur petite résolution reste celle
des références d’origine.

Le manifeste explicite `workspace/catalogs/ai-pose-gallery/personal/catalog.json`
et ses images sont distincts de l’index du site : une actualisation du catalogue
conserve les poses personnelles. Elles restent utilisables sans installation de
la galerie distante. La provenance enregistrée avec un essai indique qu’il s’agit
d’une image personnelle ; aucune URL du site n’est attribuée à ces vignettes.
Le sélecteur et les références de rendu réutilisent les fichiers d’origine.

### Poses importées depuis un batch

La sélection du 29 octobre 2026 ajoute **129 images dans 95 fiches K…**, après
examen visuel des postures, des appuis et des angles. Les 27 lignes exclues et les
premiers jets de 45 et 69 sont écartés ; leurs seconds rendus sont conservés,
ainsi que les deux rendus distincts de 46. PF001/PF002 et la galerie restent présents.

Dans **Mes poses**, le choix de vue indique l’orientation, la plongée éventuelle,
la ligne du batch et le numéro du rendu. Plusieurs images du même angle restent
sélectionnables. Les variations secondaires sont précisées ; neuf cadrages partiels
portent « Classement à confirmer ». Les regroupements expriment une ressemblance
visuelle, sans garantir une pose 3D identique. Cliquer sur une vignette ouvre
l’original ; seule la grille emploie des miniatures de 320 × 480 pixels maximum.
Les filtres **Dos**, **Trois-quarts dos**, **Plongée** et **Contre-plongée** utilisent
les vues disponibles. La recherche retrouve aussi la ligne et la version.

L’import conserve les PNG originaux octet pour octet et enregistre le batch,
la ligne, le rendu, l’essai, l’asset et son SHA-256 dans chaque entrée, puis dans
la référence figée de l’essai MH. Aucun nom de fichier ne décide du regroupement.
Le manifeste relu est requis ; les futurs rendus ne sont pas importés automatiquement.

Le catalogue enrichi est publié atomiquement dans
`workspace/catalogs/ai-pose-gallery/personal/catalog-v2.json`, en conservant
`catalog.json` pour les anciens processus encore en cours. Le nouveau Lab lit
prioritairement `catalog-v2.json`, ou l’ancien index s’il n’existe pas. Cela permet
de préparer l’import sans interrompre une génération : redémarrer le Lab au moment
choisi, puis recharger la page, pour activer ces vues et l’aperçu original.

Import local, sans réseau ni génération (simulation par défaut) :

```powershell
python -m panelforge.infrastructure.personal_pose_import --workspace workspace --manifest chemin/manifest.json
python -m panelforge.infrastructure.personal_pose_import --workspace workspace --manifest chemin/manifest.json --apply
```

Le manifeste est une liste d’entrées explicites avec `provenance`, classification,
empreinte et exclusions. Une relance identique ne crée aucun doublon ; un ID
réutilisé avec un contenu différent est refusé. Les sources et fichiers existants
sont vérifiés avant fusion. La sauvegarde, le manifeste et le reçu sont dans
`personal/imports/<import_id>/`. Pour rétablir l’index antérieur :

```powershell
python -m panelforge.infrastructure.personal_pose_import --workspace workspace --rollback krea-poses-20261029-v1
python -m panelforge.infrastructure.personal_pose_import --workspace workspace --rollback krea-poses-20261029-v1 --apply
```

Le retour arrière est refusé si l’index a changé depuis l’import. Les PNG et
les reçus restent sur disque pour audit ; aucun original du batch n’est supprimé.

## Organisation et validation

- API dédiée : `/api/image-lab/mh-assisted` ; projets : `workspace/mh_edits`.
- Contrat artistique : `domain/mh_assisted.py` ; prompteur : `mh.assisted@1.0.0`.
- Cycle de projet, assets, file et rendu réutilisent `QwenEditService`, avec politique
  MH dédiée et workflow `minimax.h3_still_edit@1.3.0`. Aucun nœud ComfyUI n’est
  référencé dans le code de l’atelier.
- Aucun appel LLM, rendu réel ou test exécuté pendant l’implémentation.

Tests à lancer par l’utilisateur :

```powershell
python -m unittest discover -s tests -p "test_mh_assisted*.py"
python -m unittest discover -s tests -p "test_minimax_loras_browser.py"
python -m unittest discover -s tests -p "test_minimax_still_loras.py"
python -m unittest discover -s tests -p "test_pose_catalog.py"
python -m unittest discover -s tests -p "test_personal_pose_import.py"
python -m unittest discover -s tests
```

Le backend et les assets sont chargés par instance. Redémarrer le Lab au moment
compatible avec les productions, puis recharger la page pour activer l’atelier.
La fidélité des poses et la qualité du prompt dans chaque langue restent à
qualifier sur les premiers essais utilisateur. Batch, vidéo, édition de squelette
et affectation de plusieurs poses distinctes sont hors périmètre de cette V1.
