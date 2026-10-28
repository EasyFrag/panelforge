# Création Assistée MH

Atelier Image Lab ajouté le 28 octobre 2026, immédiatement après Création assistée.
Il produit uniquement des images fixes avec le workflow MiniMax H3 Still déjà utilisé
par Modifier avec Minimax. Les projets et leur historique sont distincts.

## Parcours

1. Donner un nom et, si nécessaire, une intention.
2. Choisir une pose du catalogue, une image de référence, ou les deux.
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

**Création Assistée MH** et **Modifier avec MiniMax** proposent quatre emplacements
LoRA dans les paramètres du rendu. Aucun fichier n’est sélectionné par défaut.
Choisir un fichier, régler sa force entre 0 et 1 et utiliser sa case pour activer
ou désactiver son effet. Une force nulle désactive également l’effet. Le bouton
**↻** actualise le catalogue sans effacer les choix, même si un fichier a disparu.

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
python -m unittest discover -s tests -p "test_pose_catalog.py"
python -m unittest discover -s tests
```

Le backend et les assets sont chargés par instance. Redémarrer le Lab au moment
compatible avec les productions, puis recharger la page pour activer l’atelier.
La fidélité des poses et la qualité du prompt dans chaque langue restent à
qualifier sur les premiers essais utilisateur. Batch, vidéo, édition de squelette
et affectation de plusieurs poses distinctes sont hors périmètre de cette V1.
