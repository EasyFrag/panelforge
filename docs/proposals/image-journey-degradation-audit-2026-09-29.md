# Parcours d’images — dégradation observée le 29 septembre 2026

## Périmètre et résultat

Run inspecté : `journey-323a50895e5f5c72bf755375b6070023`, intention « Ajouter une porte dans le bois, des équipements de bois (deck ou autre) un paneau solaire ». Créé le 29 septembre à 09:28 heure de Paris, suspendu à 09:33 après quatre transformations. Les trois premières sont relues ; la lanterne n’a pas encore de relecture enregistrée. La suspension ne prouve pas un rejet automatique de qualité.

Images, journaux de tentative, workflows compilés et préparation examinés en lecture seule. La dégradation est visible : microtextures simplifiées, contours noirs accentués, contrastes durcis, feuilles et mousse devenant des taches, aspect progressivement illustré/plastique. La géométrie générale reste assez proche. Il s’agit d’une dérive de rendu, pas seulement d’un flou ou d’une baisse de dimensions.

Planches :
- [Suite complète](D:/Code/panelforge/.agent/diagnostics/image-journey-degradation-20260929/overview.png).
- [Zones non ciblées : écorce et racines](D:/Code/panelforge/.agent/diagnostics/image-journey-degradation-20260929/detail-crops.png).
- [Source commune, Qwen manuel et parcours MiniMax](D:/Code/panelforge/.agent/diagnostics/image-journey-degradation-20260929/qwen-comparison.png).

## Constats établis

| Élément | Observation enregistrée |
| --- | --- |
| Départ | PNG de 1120 × 1984 ; SHA-256 identique à asset-c43172ba664c4d4dbf8218da24cea71d, l’étape deck du projet Qwen qwen-50769e9edefb4302a0ffab8f34bd6125 |
| Résultats | Quatre PNG de 2016 × 3584, soit 7,23 millions de pixels ; résultat brut et résultat conservé identiques |
| Progression | Porte → extension du deck/rambarde → panneau solaire → lanterne |
| Source de rendu | Exactement le résultat précédent ; une référence, aucun masque |
| Préparation | ImageScaleToTotalPixels, 1 MP, nearest-exact, à chaque édition ; ref_image_size=max ensuite |
| Génération | Même workflow MiniMax hybrid/Fizgig que l’atelier manuel ; latent de génération distinct, bruit neuf, denoise=1, 18 steps, er_sde/beta |
| Modèles | Base FL2VA BF16, overlay REF2VA BF16, encodeur Qwen3-VL BF16, VAE vidéo INT8 convrot |
| LLM | Gemma Unsloth 31B pour progression et prompt ; prompts courts avec changements ciblés et demandes de conservation |
| Couleur | color_finish=raw sur les quatre étapes ; aucune harmonisation |
| Relecture | Trois avis usable affirmant la conservation du décor ; aucune remarque sur textures ou contraste |

La normalisation et les échanges d’assets utilisent du PNG. Il n’y a pas de chaîne de recompressions JPEG expliquant la dérive. L’agrandissement des miniatures ne modifie aucun pixel des assets.

Le mode max ne restaure pas les détails supprimés avant le nœud H3. Le [code officiel actuel de ComfyUI](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py) limite les références par leur petit côté (2048 px), puis les aligne sur des multiples de 32 ; il n’impose pas cette réduction préalable à 1 MP. La [documentation du nœud](https://github.com/Comfy-Org/embedded-docs/blob/main/comfyui_embedded_docs/docs/MiniMaxH3ReferenceToVideo/en.md) précise le coût plus élevé des grandes références. Ces sources décrivent le code public actuel ; la version déployée sur la machine Comfy distante n’a pas été inspectée.

## Diagnostic et comparaison

**Mécanisme principal plausible : accumulation de reconstructions globales.** Chaque édition redessine aussi les régions non visées, sans composition qui en conserve les pixels. L’image transformée devient la référence suivante. Les dérives de texture et contraste peuvent être réinterprétées et amplifiées. La réduction préalable à 1 MP retire des informations fines ; nearest-exact est un suspect supplémentaire pour les textures. Une seule chaîne ne permet pas de mesurer leur contribution respective.

Le fichier final de 7,23 MP contient des pixels nouvellement générés à partir d’une référence bien plus petite. Augmenter seulement les dimensions de sortie ne garantit pas la fidélité.

**Pas de moteur autonome moins qualitatif caché.** Les graphes enregistrés de l’étape 1 et du rendu MiniMax manuel attempt-dd833ae8bf414c16969268e2f031c5e2 ne diffèrent que par seed, fichier source, prompt et préfixe de sortie. Modèles, résolution, réduction de référence, sampler et steps sont identiques. Le contexte visuel diffère (arbre extérieur contre intérieur) : ce n’est pas une comparaison de qualité contrôlée.

**Qwen : même image de départ retrouvée.** Les étapes suivantes de sa chaîne manuelle utilisent une finition naturelle réellement appliquée à 55 %, avec des sorties à 1120 × 1984. Sa fin montre aussi une accentuation et une dérive de texture, mais les aplats et contours artificiels sont moins marqués que dans ce run MiniMax. Les moteurs, prompts et modifications diffèrent : ne pas attribuer tout l’écart à la finition. Celle-ci rapproche les couleurs de la source, sans récupérer les détails perdus.

Les ateliers manuels gardent une source fixe pour les essais d’une étape, puis passent à l’image suivante après validation humaine. Le parcours produit un essai par étape et enchaîne dès que sa relecture estime le résultat exploitable. Il ne sélectionne pas humainement la meilleure variante.

**Relecture insuffisante ici.** Elle compare résultat, source précédente et original, mais sa politique vise surtout l’avancement du chantier, l’identité et le cadrage. Ses trois validations passent à côté de la détérioration. L’original est montré à l’assistant de progression ; le renderer MiniMax et son prompter ne disposent que de la source de l’étape. Les mots de conservation ne verrouillent pas les pixels.

Les seeds diffèrent entre étapes : chacune crée un projet enfant avec une nouvelle seed. reuse_seed=true concerne les essais de ce projet, pas une seed commune au parcours. Cela ne démontre pas la cause de la dérive.

## Pistes à discuter, non appliquées au moteur

1. Comparer une édition identique, à image/prompt/seed/sortie/steps constants, avec une référence plus détaillée, puis un redimensionnement adapté. Séparer l’effet de la taille de celui de l’interpolation, mesurer temps et mémoire.
2. Relire explicitement textures, contraste, couleur et régions non visées face à l’original, avec des détails agrandis. Ne pas promouvoir silencieusement un résultat conforme à l’action mais dégradé. Aligner pause, rejet ou nouvelle tentative avant d’ajouter un rejeu automatique.
3. Évaluer l’original comme référence supplémentaire pour texture/lumière et l’état courant pour les travaux. Aide possible sans garantie ; des rôles ambigus peuvent faire revenir à un ancien état.
4. Pour une retouche locale, masque et composition finale avec la source permettent de conserver les pixels extérieurs. Inclure ombres et raccords dans la zone remplacée ; un simple guide par prompt ne suffit pas.
5. Comparer séparément la finition naturelle pour la couleur. Elle ne restaure pas les microtextures.

Ne pas conclure sans comparaison que Gemma, les 18 steps ou le VAE INT8 sont responsables. Les prompts ne demandent ni accentuation excessive ni changement de style. Changer seulement le LLM ne traite pas les facteurs confirmés de la chaîne.

## Interface et piste future

Le retour miniatures concernait Parcours d’images autonome. Il y est reporté : frise 450 × 330 px, source 216 × 198 px, aperçu ×3 plafonné à l’écran, loupe visible sur toutes les miniatures et ouverture agrandie, y compris avant import. Ctrl+F5 suffit ; aucun réglage de rendu modifié.

Piste gardée : **insérer une image intermédiaire entre deux états existants**, A → intermédiaire → B, en conservant A et B comme références. Le comportement sur la suite et les transitions reste à aligner. Aucune implémentation.

Contrôles UI : trois sources JS compilées sans exécution, 63 règles CSS, 1 947 IDs HTML uniques, 38 références et fragment du scénario existant vérifiés. Tests non exécutés selon AGENTS.md. Aucun backend, preset, asset, run, service ou file modifié ; aucun appel LLM/rendu lancé. Preuves, sauvegardes, diff et validation : D:/Code/panelforge/.agent/diagnostics/image-journey-degradation-20260929/.
