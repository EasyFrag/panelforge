# Recherche de seeds H3 — audit du 7 septembre 2026

Demande : s'inspirer de Seed Hunter pour comparer plusieurs seeds puis finaliser
le meilleur candidat dans localQ, en réutilisant l'existant. **Discussion et audit
seulement ; aucune implémentation de cette fonctionnalité autorisée à ce stade.**

## Sources et vérifications

- Fichier utilisateur : `C:\Users\samue\Downloads\minimaxSEEDHUNTERWorkflow_v15.json`,
  287 591 octets ; SHA-256
  `9d03f7b5ffb5ef42b21b8a2470d077fae49b6fae20743e332366892eab1a74fc`.
- [Fiche de foxydits](https://civitai.red/models/2881362/minimax-seed-hunter-workflow-latent-upscaler-seamless-video-continuation-speedups),
  description/version 3293757 consultées via
  [l'API publique](https://civitai.red/api/v1/models/2881362), la page HTML ayant
  échoué dans l'outil web. L'auteur décrit trois aperçus basse résolution suivis
  de la finalisation du favori. Ses annonces de vitesse/qualité ne sont pas des
  mesures sur le serveur de l'utilisateur.
- [Documentation du latent upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler) :
  agrandissement spatial du latent, puis raffinement. La passe haute résolution
  garde son besoin en VRAM ; ne pas présenter le procédé comme une économie
  garantie de mémoire à résolution finale identique.
- Sources officielles ComfyUI :
  [SaveLatent / LoadLatent](https://github.com/comfyanonymous/ComfyUI/blob/master/nodes.py),
  [séparation / réunion audio-vidéo](https://github.com/comfyanonymous/ComfyUI/blob/master/comfy_extras/nodes_lt.py).
  GET en lecture seule des quatre `/object_info/<node>` sur `bucket:8188` : nœuds
  disponibles. Leur présence ne prouve pas encore un aller-retour fidèle de tous
  les champs du latent H3 sur cette installation.

## Ce que fait le JSON fourni

Le fichier est un workflow d'interface avec six sous-graphes, des contrôles de
groupes rgthree et des liaisons implicites Anything Everywhere ; ce n'est pas
directement notre format d'exécution API.

1. Le seed de départ du nœud 16 alimente trois samplers : sous-graphes #1/#2/#3,
   instances 125/133/143. Les calculateurs internes produisent `S`, `S+1`, `S+2`.
   Les autres entrées de génération sont partagées. Les seeds voisines servent
   ici à obtenir des tirages distincts, pas à rechercher un voisin visuellement
   proche du favori.
2. Chaque sortie est décodée en vidéo avec audio et présentée par les nœuds
   `VHS_VideoCombine` 18/134/144. `save_output=false` : aperçus temporaires.
3. Les contrôles Select #1/#2/#3 pilotent le switch 122. Il sélectionne le
   `denoised_output` du candidat, puis le nœud 242 sépare audio et vidéo ; 243
   agrandit le latent vidéo ; 244 le réunit avec l'audio ; 135 effectue la seconde
   passe. Cette passe a aussi son propre seed, contrôlé par 103.
4. Le fichier fourni démarre avec la finalisation désactivée (`mode=4` sur ces
   nœuds). Aucun SaveLatent/LoadLatent n'est présent : pas de reprise persistante
   des latents explicitement enregistrée dans ce graphe.

Les réglages affichés de l'instance Video Settings sont 0,4 MP, 5 secondes,
8 steps, ER-SDE/Beta, portrait ; certains défauts internes du sous-graphe sont
différents et ne doivent pas être confondus avec ces valeurs affichées. La cible
de l'upscaler est 1 MP. Le modèle et le VAE sont des variantes int8 ; le texte
est encodé par la variante NVFP4/AWQ. Ces choix diffèrent du workflow local.

Le workflow contient également continuation vidéo, audio personnalisé,
interpolation RIFE, Sparse Attention, LoRA et Prompt IDE. Leur portage n'est pas
nécessaire pour ajouter une recherche de seeds.

## Ce que PanelForge possède déjà

`scripts/run_lab.py` charge H3 Base `minimax-h3-latent-speed@0.1.2` :

- Première passe à **0,2 MP** (nœud 22), sampler 26, seed 37, steps configurés
  (défaut 25), RES Multistep/Beta.
- Sortie intermédiaire `26:1`, séparation AV en 38, upscale vidéo en 28,
  réunion avec l'audio en 18, raffinement en 25 selon trois étapes de sigmas
  explicitement fixés. Le conditionnement haute résolution est déjà prévu.
- MP4 final, keyframes et prévisualisation de calcul intégrés.

Ref2V `minimax-h3-ref2v@0.2.0` possède également une première passe à 0,2 MP suivie
du même principe d'upscale/raffinement.

`H3RenderAttempt` enregistre déjà prompt effectif, seed, durée, ratio, MP, steps,
musique, Spectrum, LoRA, résultat et keyframes. Les cartes existantes permettent
lecture, feedback et reprise du prompt/réglages. Les profils Brief/Plan/Prompt
1/2/3 étapes n'ont pas besoin de changer : l'exploration intervient **au rendu**.

Manques identifiés : pas de type d'essai aperçu/finalisation, de lien de
finalisation vers un aperçu, d'artefact latent persistant ni de série automatique
de seeds. `H3RenderService.queue_attempt` refuse tout nouvel essai tant qu'un
autre rendu H3 est actif : trois POST `/start` successifs ne constituent donc pas
une implémentation correcte de la recherche.

## Proposition recommandée à discuter

Dans le bloc de rendu existant : **Explorer 3 seeds**. Le bouton fige le prompt,
les références et les réglages de la série. Trois aperçus sont calculés
successivement, sur la durée complète du clip, avec seulement le seed qui varie.
Les cartes sont regroupées pour les comparer ; chacune propose **Finaliser
celle-ci**. Une autre série peut être lancée, et les candidats restent consultables.
Le bouton de rendu complet habituel reste disponible.

Pour la première version, conserver nos modèles, LoRA, sampler, steps et première
passe 0,2 MP. Ne pas ajouter Turbo, changer de VAE ou réduire simultanément les
steps : ces paramètres fausseraient la comparaison avec le parcours actuel.
Une éventuelle première passe plus lisible à 0,3/0,4 MP serait une variante
appariée aperçu/finalisation à évaluer ensuite.

Réutiliser la chaîne actuelle en deux opérations versionnées :

- **Aperçu** : même première passe, décodage d'un MP4 basse résolution et
  enregistrement de l'état intermédiaire audio/vidéo utilisé par la finalisation.
- **Finalisation** : chargement de cet état, conditionnement correspondant aux
  références/prompt de l'aperçu, puis upscale et raffinement existants. Le résultat
  est un nouvel essai lié à son aperçu, sans écraser celui-ci. Un changement
  ultérieur du prompt courant ne modifie pas silencieusement la finalisation
  d'un ancien candidat.

Le résultat sauvegardé devrait partir de la même sortie intermédiaire que celle
dont on décode l'aperçu. Les nœuds de lecture/écriture sont présents, mais il faut
vérifier la conservation séparée des tenseurs AV et des éventuels masques et
métadonnées : le SaveLatent standard sauvegarde principalement `samples`, ce qui
ne suffit pas à présumer un aller-retour complet de tous les dictionnaires H3.
Le cache temporaire ComfyUI peut accélérer l'opération, mais ne doit pas être
l'unique moyen de retrouver un candidat après d'autres travaux ou un redémarrage.

Ajouter une petite file persistante et séquentielle pour ces essais, avec état,
progression et retrait des aperçus en attente. Réutiliser le suivi H3 existant et
respecter les rendus actifs. Les IDs des nouveaux points de branchement et
artefacts appartiennent aux manifests versionnés, pas au code de fonctionnalité.
La provenance de l'essai doit figer la variante de rendu employée.

Une variante plus courte consisterait à enregistrer seulement seed et réglages,
puis recalculer la première passe du favori lors de sa finalisation. Elle économise
le mécanisme de stockage des latents, mais recalcule cette passe et ne garantit
pas de récupérer exactement le même état numérique. Changer simplement la
résolution d'une génération directe avec le même seed ne reproduit pas ce
processus. Pour un outil réutilisable dans le temps, préférer la reprise du latent.

## Limites et suite

L'intérêt attendu est de ne faire l'upscale/raffinement coûteux que pour le ou les
favoris. Les aperçus restent des générations complètes en durée, avec un coût de
décodage et de stockage ; aucune accélération chiffrée n'a été mesurée.
Le raffinement peut encore changer des détails, et la basse résolution permet
surtout de juger action, cadrage et mouvement. La qualité finale doit être revue.

Périmètre raisonnable : extension du rendu H3 Base d'abord, puis adaptation au
Ref2V qui partage déjà ce découpage. L'effort est d'ampleur moyenne : workflows,
stockage/reprise et orchestration, avec une UI légère. Les prompts de préparation,
l'atelier image et les autres fonctionnalités du workflow tiers sont indépendants.

Aucun code runtime modifié, test exécuté, appel LLM, génération, téléchargement de
poids, annulation ou redémarrage. Seuls le JSON, le code, les sources publiques et
quatre descriptions de nœuds ComfyUI ont été lus. La proposition reste à discuter
avant implémentation.
