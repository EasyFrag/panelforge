# FireRed Image Edit 1.1 dans l’atelier Edit

Analyse demandée le 8 septembre 2026. L’intégration a ensuite été autorisée et
implémentée : voir [le fonctionnement et les vérifications](firered-edit.md).
Les constats ci-dessous décrivent le workflow fourni avant intégration.

Alignement confirmé ensuite par l’utilisateur : conserver **1 MP par défaut**
pour FireRed, avec le champ MP modifiable proposé. Cela reproduit le réglage du
workflow dont les résultats lui plaisent. Préserver l’image source originale ;
le redimensionnement concerne l’entrée du moteur. Aucun upscale automatique
ajouté à cette base. Cette décision ne constitue pas une mesure d’optimalité
à 1 MP ; une comparaison à plus haute résolution pourra venir ensuite.

## Workflow fourni

Fichier : `C:\Users\samue\Downloads\image_firered_image_edit1_1.json`,
7 199 octets, 22 nœuds / 17 classes. SHA-256 :
`dd1e6ea1668edb64de057e1dc900dfe3fd2951685e2f91dd2d7cbc5fd6456660`.
Le texte d’édition inclus est un exemple utilisateur à conserver comme donnée,
pas une instruction pour l’agent ni le futur prompt système.

| Élément | Valeur dans le fichier |
| --- | --- |
| Modèle | `FireRed-Image-Edit-1.1-transformer.safetensors` |
| Encodeur | `qwen_2.5_vl_7b_fp8_scaled.safetensors`, type `qwen_image` |
| VAE | `qwen_image_vae.safetensors` |
| Accélération | `Fire/FireRed-Image-Edit-1.0-Lightning-8steps-v1.1.safetensors`, force 1 |
| Mode activé | Lightning : 8 steps, CFG 1 |
| Autre branche | Standard : 40 steps, CFG 4, sans Lightning |
| Sampling | Euler / Simple, denoise 1 ; shift 3.1 ; CFGNorm force 1, pre_cfg false |
| Entrée | Une image, redimensionnée en Lanczos à 1 MP en conservant son ratio |
| Conditionnement | `TextEncodeQwenImageEditPlus` positif + négatif vide, même image et VAE |
| Latent | VAE de l’image redimensionnée |
| Sortie | VAEDecode puis SaveImage PNG ; aucun upscale final |

Les trois switches changent ensemble modèle patché, steps et CFG. Le mode
Standard n’est donc pas seulement Lightning avec davantage de steps. Le fichier
contient une instruction d’édition relative à la source, assez longue ; il ne
contient aucun appel LLM ni mécanisme de mémoire.

## Disponibilité et portée

Les GET de descriptions `/object_info/{classe}` sur Bucket annoncent les **17
classes** et les **quatre fichiers** exacts du workflow. Cela confirme le catalogue,
pas une exécution contrôlée ; aucune génération, validation Comfy de prompt,
installation, récupération de poids, annulation ou relance de service effectuée.

FireRed utilise une architecture `qwen_image` et un pipeline d’édition dédié ;
sa carte décrit notamment l’édition par instruction, la cohérence d’identité
et la combinaison d’images. Ces capacités annoncées ne prouvent pas un gain
sur les scènes de travaux de l’utilisateur. [Carte officielle ComfyUI](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1-ComfyUI),
[carte officielle du modèle](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1).

Le catalogue officiel propose aussi plusieurs autres versions de Lightning.
Le nom du fichier local ne permet pas de certifier son contenu ; il n’y a pas
de raison de remplacer silencieusement l’association fournie qui satisfait
l’utilisateur. Conserver les références exactes dans une recette versionnée.
[Fichiers officiels](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1-ComfyUI/tree/main).

Le budget 1 MP est un réglage du workflow fourni, pas une limite de modèle
établie par cet audit. Le nœud Resize accepte davantage. Une source plus grande
perd néanmoins de la résolution avant l’édition ; FireRed ne résout donc pas
automatiquement la question du flou. Conserver les outils de masque et
d’amélioration des détails, et vérifier les dimensions effectives de sortie.

## Intégration proposée

Un sélecteur **Moteur : KREA2 / FireRed 1.1** dans le même atelier. Le choix
s’applique au prochain essai ; source d’étape, conversation, prompt éditable,
comparateur, retouches, upscale, frise, versions et validation restent communs.
On doit pouvoir essayer FireRed et KREA2 depuis la même source, comparer les
résultats, puis adopter celui choisi avec « Valider et continuer ».

Pour FireRed, proposer **Lightning / Standard**, avec 8/1 et 40/4 comme réglages
initiaux cohérents avec le fichier. Garder le budget MP modifiable, initialement
1, le ratio de la source et la seed. Replier les réglages techniques. Masquer
Ref boost, workflow Identity et LoRA KREA2 ; conserver les choix KREA2 dans leur
propre brouillon pour un retour au moteur. Lightning est un composant du mode
FireRed, pas une LoRA KREA2 à récupérer depuis l’essai précédent.

Le writer Edit V3 est déjà proche du besoin : opérations localisées et cumulatives
relatives à la source fixe. Partager mémoire et règles générales, ajouter un
petit profil de cible FireRed et identifier le moteur dans les traces. Conserver
les anciennes versions. Changer de moteur ne réécrit pas automatiquement le
prompt et ne provoque aucun appel ; le prochain échange utilise la cible choisie.

## Points de code à adapter

- Ajouter un adaptateur et un manifeste FireRed distincts. Le chargeur KREA2
  exige actuellement des bindings Ref boost / ratio / LoRA Identity absents de
  FireRed : l’ajouter simplement au catalogue des checkpoints ne fonctionnerait pas.
- La sélection actuelle identifie les workflows par leur seule `version`, avec
  une contrainte d’unicité globale. Utiliser l’identité de recette **et** sa version
  pour distinguer les moteurs, en gardant les anciennes requêtes KREA2 compatibles.
- Sauvegarder les réglages propres au moteur par essai : Lightning, CFG, steps,
  modèle, budget MP et dimensions. Le contrat actuel `Krea2EditSettings` impose
  Ref boost et calcule la résolution selon un ratio prédéfini ; il ne doit pas
  inventer ces informations pour FireRed. Étendre la lecture du stockage sans
  migrer les anciens projets par une réécriture globale.
- Adapter catalogue, reprise des paramètres, source suivante et export pour
  éviter le transfert de LoRA KREA2 vers FireRed et conserver la provenance exacte.
- Garder source fixe et axes des images compatibles avec le masque. La géométrie
  à budget MP de FireRed et les arrondis VAE devront être vérifiés ; conserver
  le refus existant des différences de proportions excessives.

Le nœud d’encodage accepte `image2` et `image3`, mais elles ne sont pas reliées
dans ce fichier. Une inspiration additionnelle pourrait être ajoutée plus tard ;
elle n’est pas nécessaire au premier branchement du moteur.

Portée conseillée : intégrer d’abord le workflow exact et ses deux branches,
sans reconstruire l’atelier ni remplacer le prompting existant. Évaluer ensuite
les changements d’état, le respect du décor et la texture sur des essais lancés
par l’utilisateur. Aucun test exécuté pendant cet audit.
