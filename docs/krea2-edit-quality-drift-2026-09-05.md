# Dérive visuelle des éditions KREA2

Audit du 2026-09-05 : lecture des paramètres, workflows compilés et inspection
de six images existantes. Aucun test, appel LLM, rendu ou changement runtime.

## Séquence observée

Projet `krea2-edit-dcffc7cd55cf44e89772c2a4ab7fb527` : paroi intacte →
trou accepté `attempt-8566a9b4067c4c79ba15d74247b3ad17` → porte acceptée
`attempt-ffb2efeaf52d484b927853ed1120e161` → essais de pavage dans
`krea2-edit-537403cb0f914a2cafb78f4558a47a62`.

- Base 688×1224 ; trou, porte et pavages 1112×1976. Il n'y a pas de baisse
  de résolution dans cette suite. Le passage initial à une plus grande image
  n'établit pas une restauration des détails de la source. Sorties PNG.
- Trou accepté : Cielbleu, Ref boost 2.5, 10 steps, aucune LoRA optionnelle.
- Porte acceptée : même modèle, Ref boost 3, 10 steps, Detailer-KREA2 à 1.
- Pavage `attempt-8cd9a79224b24dc0bb483c4ddb2e687e` : Cielbleu, Ref boost 4,
  12 steps, aucune LoRA optionnelle. Le chemin reste largement non pavé ;
  contours très marqués, nuages et végétation prennent un aspect dessiné.
- Pavage `attempt-320839f74d8246019efd59f35b4f8e2c` : Cielbleu, Ref boost 0.4,
  12 steps, aucune LoRA optionnelle. Pavage réalisé, mais cadrage et paroi
  changent ; apparence moins dessinée que l'essai suivant.
- Dernier essai `attempt-a5d82c46ec6f46348b7504ad865497ab` : mêmes source,
  prompt, modèle, seed, résolution, Ref boost et steps que le précédent ;
  seul réglage enregistré différent = slider_detail_slider_krea2_loraholic
  à 4. Son résultat présente davantage d'aplats et de contours accentués.
  C'est un indice local de contribution de cette LoRA à cette intensité,
  pas une conclusion universelle sur les LoRA de détail.

La base présente déjà certaines surfaces simplifiées. L'aspect se renforce
dans les résultats observés, mais les paramètres et instructions varient :
ce n'est pas une expérience isolant l'effet du nombre d'éditions. Les essais
de pavage sont des alternatives depuis la même porte, pas cinq rééditions
successives les unes des autres. Les révisions lues sont du writer historique
(sans assistance_version) ; ne pas attribuer le résultat au nouveau chat Edit.

## Mécanisme et pistes

Le graphe local `krea2.identity_edit@0.1.0` génère depuis un latent vide,
conditionné par la source via VAE et encodeur visuel, avec denoise 1.
Il ne protège pas les pixels hors de la modification par masque/recomposition.
La réinterprétation globale à chaque promotion est donc une explication
plausible de l'accumulation, sans permettre de quantifier chaque cause.
Ne pas conseiller de simplement diminuer denoise sur ce graphe : la source
n'est pas le latent initial du sampler.

La documentation du [modèle Identity Edit](https://huggingface.co/conradlocke/krea2-identity-edit)
décrit Ref boost <1 comme une influence réduite de la référence, autour de 4
comme un point de départ pour une forte ressemblance, et reconnaît que des
éditions locales peuvent altérer le reste du cadre. Une référence déjà
stylisée peut donc rester stylisée avec un poids fort ; ce réglage n'est pas
un curseur de réalisme. Le [graphe et les nœuds de l'auteur](https://github.com/lbouaraba/comfyui-krea2edit)
confirment le double conditionnement et la génération depuis un latent vide.

Priorités proposées, non implémentées : retirer d'abord les LoRA de détail
optionnelles pour établir une comparaison ; garder modèle/résolution/seed
stables et chercher le compromis Ref boost ; expérimenter un prompt d'édition
court décrivant la modification et la conservation des textures/lumière,
plutôt qu'amplifier encore hyper detailed ; à terme, ajouter une zone à modifier
avec recomposition des pixels extérieurs depuis la source, et une marge pour
les raccords/ombres. Seule cette recomposition protégerait explicitement le
reste de l'image ; elle ne garantirait pas la qualité de la zone générée.

Le patch précédent conserve maintenant Ref boost/steps entre étapes, mais
ne change pas le générateur et ne suffit pas à résoudre cette dérive.
