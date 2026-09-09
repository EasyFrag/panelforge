# Upscale DLSS local — proposition du 2026-09-09

Archive de la discussion initiale. L’utilisateur a ensuite autorisé l’implémentation le 9 septembre 2026 : voir le [guide de la version implémentée](dlss-local.md). Les propositions ci-dessous décrivent l’état de l’alignement avant cet accord.

## Demande acquise

- Utiliser l’instance ComfyUI Windows pour ces nœuds DLSS ; conserver Bucket pour les générations actuelles.
- Démarrer cette instance à la demande d’un upscale, pour éviter un lancement manuel systématique.
- Essayer d’abord la coexistence avec Unsloth, sans décharger ni arrêter automatiquement son modèle.
- Prévoir des commandes pour libérer la mémoire de ComfyUI local et l’arrêter/redémarrer si nécessaire.

## État constaté

- Lanceur réel : `D:\AI\ComfyUI_windows_portable\run_dlss.bat`. Il fixe `DLSS_FFMPEG_PATH` et `DLSS_FFPROBE_PATH` vers `tools`, puis appelle `run_nvidia_gpu.bat`.
- FFmpeg et FFprobe présents. Le second BAT lance le Python embarqué avec `-s ComfyUI\main.py --windows-standalone-build`, puis un `pause`. Aucun port spécifique : défaut du code installé `127.0.0.1:8188`, distinct de `http://bucket:8188` malgré le même numéro. Ni disponibilité actuelle de cette URL ni mémoire disponible mesurées.
- Nœuds installés dans `ComfyUI/custom_nodes/ComfyUI-NVIDIA-DLSS-Frame-Interpolation`. Lecture du code sans import ni exécution. Le `git remote` depuis ce sous-dossier remonte au dépôt ComfyUI parent, pas au dépôt des nœuds.
- `C:\Users\samue\Downloads\nvidia DLSS.json` : LoadImage → NvidiaDLSSImageUpscale, ×2, intensité/tone/structure/skin à 2, detail strength 1. Sorties PreviewImage, ImageCompare, PreviewAny ; pas de SaveImage. Remplacer les sorties UI accessoires par une sauvegarde PNG durable et conserver le rapport JSON pour l’application.
- `C:\Users\samue\Downloads\Video_Upscale_DLSS.json` : LoadVideo → NvidiaDLSSVideoUpscale ×1,5, H.265 NVENC, Max, HDR activé. L’interpolation vers 60 FPS est reliée à l’upscale, **mais SaveVideo reçoit directement l’upscale**, pas l’interpolation. Celle-ci n’appartient donc pas au chemin de sortie enregistré.
- Le pack propose séparément résolution et interpolation ; rapports JSON indiquant notamment `nr_upscaling_active`, `nr_native_fallback`, `feature_18_confirmed`. Les deux workflows autorisent le fallback (`require_neural_upscaling=false`). Une sortie plus grande ne confirme pas à elle seule que le mode d’upscale neural demandé a fonctionné.
- Le code installé ferme la session/processus natif DLSS à la fin de l’image ou vidéo et tente son nettoyage en cas d’échec. Cela ne garantit pas une empreinte GPU nulle pour ComfyUI encore ouvert.
- PanelForge a déjà `ComfyClient.free_vram()` : refus si file active/en attente, puis POST `/free` avec `unload_models` et `free_memory`. Dans ComfyUI installé, cela demande déchargement des modèles, reset des caches, GC et vidage du cache GPU. Réponse HTTP immédiate avant nettoyage effectif ; pas une preuve que toute la VRAM est libérée, ni un arrêt des processus natifs en cours.

## Proposition V1, à confirmer

### Périmètre précisé par l’utilisateur, toujours en discussion

L’utilisateur souhaite DLSS pour les upscales d’image utilisés actuellement (notamment Edit), un bouton sur les vidéos H3 et REF2V terminées, et un bouton directement dans KREA2 Assisted. Il demande explicitement de continuer à discuter avant d’implémenter.

- **Edit, y compris résultats FireRed** : remplacer le moteur ESRGAN/ClearReality du bouton d’amélioration par DLSS. Retirer la liste des anciens modèles du parcours principal ; garder la lecture des anciens résultats et leur provenance. Proposer l’ancien moteur dans les recettes historiques pour comparaison, pas un second panneau permanent. Ce rangement reste une proposition.
- **Assisted** : ajouter Upscale DLSS à l’essai réussi, avec une variante rattachée à cet essai. Elle doit pouvoir servir au feedback, export, reprise de branche et intégration dans un décor sans nouvel échange LLM automatique ; les réglages de génération hérités restent distincts des réglages DLSS.
- **H3 et REF2V** : ajouter le même bouton sous chaque vidéo réussie. Action explicite une fois le rendu terminé, sans nouvelle préparation brief/plan/prompt ; pas d’upscale automatique de tous les essais. Conserver l’audio et les FPS par défaut. Si l’on choisit de continuer depuis la version DLSS, extraire ses frames à elle et ne pas lui attribuer les anciennes vignettes de l’original.
- Variantes groupées sous leur essai d’origine, avec sélection Original / DLSS et leurs propres dimensions/réglages. L’original reste disponible. Dans Edit, les variantes sont aussi de vrais candidats du comparateur, validables pour l’étape suivante ; une amélioration ne crée pas à elle seule une nouvelle étape ni un nouveau numéro de génération.
- Une interface et un service partagés, des entrées dans les ateliers existants ; lancement local et commandes mémoire identiques dans tous les cas.

**Deux tailles de sortie à expliquer dans Edit, proposition à confirmer** : un seul champ « Taille de sortie », avec « Taille de la source » comme défaut pour la poursuite d’étape, et des facteurs d’agrandissement pour la finition. L’actuel chemin masqué améliore la génération sous-jacente puis réapplique masque/harmonisation à la taille source ; DLSS peut remplacer cette passe en préservant ce contrat et les pixels source protégés. Un agrandissement de l’image finale traite le composite sélectionné et peut modifier aussi les zones auparavant protégées ; il conserve une sortie réellement plus grande, avec une provenance de finition distincte, sans prétendre à une conservation des pixels de source. Reprendre l’ancien masque doit repartir de ses entrées enregistrées, pas du composite agrandi présenté comme sa génération d’origine. Ne pas imposer deux boutons ni de nouveau parcours obligatoire. Assisted et vidéo garderaient les facteurs proposés ×2 et ×1,5 par défaut. Le choix final des valeurs reste ouvert.

**Upgrades internes à préserver dans ce périmètre** : H3 Base `0.1.3` et REF2V `0.2.0` utilisent `MinimaxH3LatentUpscaler3D` avant un raffinement par génération. Le batch KREA2 Community contient aussi `LatentUpscaleBy` dans sa recette. Ce sont des opérations sur les représentations latentes au sein du rendu ; le DLSS fourni prend des images/vidéos déjà décodées. Les remplacer demanderait de nouvelles recettes de génération et une comparaison de qualité, pas simplement le branchement de ces boutons. Les réglages MP actuels de génération resteraient donc distincts des dimensions finales DLSS.

### Parcours

- Action facultative **Améliorer / Upscale** sur une image Assisted, un candidat Edit ou une vidéo réussie, panneau compact commun. Réutiliser l’entrée existante dans Edit.
- Cible figée au candidat sélectionné. Afficher original, facteur et dimensions finales, puis Lancer ; les réglages NR/codec restent repliés.
- Valeurs initiales inspirées des fichiers : image ×2, vidéo ×1,5 ; FPS d’origine conservés. Interpolation 60 FPS facultative et désactivée par défaut. HDR désactivé pour les sources SDR ; ne pas imposer le HDR du fichier exemple à tous les clips.
- Résultat distinct avec provenance, comparaison, téléchargement/export et carillon existant ; jamais remplacer l’original. Récupérer et stocker le média dans PanelForge avant toute libération/fermeture du moteur local.
- Garder la sortie agrandie native : l’actuel ESRGAN Edit redimensionne aux dimensions de la source, contrat à préserver pour cet outil. Ne pas injecter DLSS dans ce contrat en supprimant involontairement son gain de résolution. Dans Edit, prévoir explicitement la compatibilité des dimensions avec masque et validation, et les limites de décodage (actuellement 16 MP / 25 Mio dans plusieurs chemins).
- Enregistrer le rapport technique DLSS, réglages, dimensions, durée et moteur réellement utilisés ; signaler sobrement un fallback sans appeler le résultat « upscale neural confirmé ».

### Instance locale et mémoire

- Au clic Lancer, réutiliser l’instance locale compatible si elle répond ; sinon la démarrer en arrière-plan sans fenêtre visible, attendre sa disponibilité et vérifier les classes nécessaires. Aucun démarrage à l’ouverture du panneau.
- Conserver l’environnement du BAT. Pour une supervision fiable, lancer son équivalent Python avec arguments structurés, répertoire et variables FFmpeg explicites, sans le `pause` final. Ne pas modifier le BAT utilisateur sans nécessité.
- Un lancement partagé pour les demandes simultanées, une seule exécution DLSS à la fois. Suivi distinct de Bucket : endpoint enregistré avec chaque tâche pour polling, téléchargement, annulation ciblée et récupération après redémarrage du Lab. Ne jamais envoyer une opération locale sur Bucket par défaut.
- Petit statut **Comfy local : arrêté / démarrage / prêt / traitement / erreur**, progression et erreur consultable. En cas d’échec mémoire, préserver l’original et les réglages, laisser l’utilisateur décider ; aucune fermeture d’Unsloth ni boucle de relance automatique.
- **Libérer la mémoire** : demander le nettoyage seulement une fois sorties et diagnostics récupérés, sans tâche active/en attente ; afficher que c’est un nettoyage demandé, sans promettre zéro VRAM.
- **Arrêter / Redémarrer Comfy local** : seulement instance/processus identifiés comme démarrés par PanelForge, en incluant les sous-processus appartenant à cette instance. Ne jamais tuer globalement python.exe ou un serveur préexistant non possédé. Garde sur la file et sur les tâches PanelForge avant arrêt. Une instance lancée manuellement peut être utilisée, mais sa fermeture automatique demande une stratégie explicite, pas une déduction par numéro de port.
- Par défaut, garder Comfy ouvert après traitement pour comparer la coexistence avec Unsloth. Arrêt après chaque tâche ou inactivité éventuel ultérieur, pas de gestion automatique des modèles LLM dans cette V1.

### Architecture et évaluation ultérieure

- Deux recettes d’upscale versionnées avec manifests explicites et variante vidéo si interpolation choisie ; IDs des nœuds uniquement dans les workflows.
- Petit service applicatif de post-traitement partagé + adaptateur de cycle de vie local, réutilisant assets, client Comfy, suivi, notifications. Ne pas recopier les services de génération ni développer un nouveau studio.
- Préparer des tests simulés pour démarrage unique, instance existante, timeout/port incorrect, routage local, absence de double soumission, queue/arrêt protégé, import du candidat exact, récupération du résultat et du rapport, redémarrage du Lab, erreurs mémoire, dimensions/FPS/audio, compatibilité des anciens projets. Tests exécutés par l’utilisateur seulement.
- Premiers essais réels par l’utilisateur : une image puis une courte vidéo avec Unsloth chargé ; observer qualité, temps et mémoire avant/après avant toute politique d’exclusion automatique. Aucun résultat de performance ou de coexistence actuellement validé.

## Sources

- [Documentation de l’auteur des nœuds](https://github.com/Konohamaru04/ComfyUI-NVIDIA-DLSS-Frame-Interpolation), recoupée avec README et Python installés.
- [Boucle d’exécution et libération mémoire ComfyUI](https://github.com/Comfy-Org/ComfyUI/blob/master/main.py), recoupée avec `main.py` et `server.py` installés.
- Fichiers JSON utilisateur, lanceurs locaux et adaptateurs PanelForge cités ci-dessus.
