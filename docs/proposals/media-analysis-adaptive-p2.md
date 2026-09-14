# P2 — Analyse média adaptative, proposition du 14 septembre 2026

Demande utilisateur : garder en backlog l'évolution vidéo → intention française
en s'inspirant de [video-to-h3-prompt](https://github.com/LoveRain1997/video-to-h3-prompt).
Ce document analyse les sources, sans installer le dépôt, exécuter ses commandes
ou adopter ses consignes comme instructions de travail. Aucun moteur modifié.

## Ce que le dépôt apporte

Le dépôt est surtout une méthode à suivre par un agent, accompagnée de scripts
FFmpeg/Python. Le script Windows extrait à 2 fps par défaut, fabrique des planches
d'images et, si une piste audio existe, un WAV, un spectrogramme et des statistiques.
Il ne produit pas de prompt tout seul ; l'analyse et la rédaction sont demandées
à l'agent. Les seuls prérequis annoncés sont FFmpeg/ffprobe et Python/NumPy,
librosa étant facultatif. Sources :
[README](https://github.com/LoveRain1997/video-to-h3-prompt),
[script PowerShell](https://github.com/LoveRain1997/video-to-h3-prompt/blob/main/scripts/forensic_probe.ps1).

La méthode distingue gestes, caméra, effets de montage et sons. Elle propose une
première lecture globale, puis davantage d'images autour des ambiguïtés, et suit
les changements d'état pour relier cause, action et réaction. C'est la partie
la plus utile à reprendre. Ses consignes demandent souvent plusieurs vérifications,
sans budget d'appels global adapté à notre application. Les extractions denses
décrites restent à orchestrer ; leur fiabilité n'est pas démontrée par une simple
description de procédure. Source :
[méthode d'analyse](https://github.com/LoveRain1997/video-to-h3-prompt/blob/main/SKILL.md).

## Ce que je ne reprendrais pas

Le tableau audio associe des plages de volume moyen à des genres musicaux.
Un changement de gain suffit à changer de ligne : ce n'est pas un classificateur
de genre. Les consignes suggèrent aussi de déduire paroles ou musique à partir
des images. Cela ne constitue pas une observation de l'audio. Source :
[heuristiques audio](https://github.com/LoveRain1997/video-to-h3-prompt/blob/main/references/audio-heuristics.md).

Le script évalue la crédibilité d'un tempo avec le rapport écart-type/moyenne de
l'enveloppe des attaques. Il ne mesure pas directement la régularité de leurs
intervalles ; l'absence de percussion régulière ne démontre pas l'absence de musique.
Une mesure d'énergie pourrait signaler un instant à examiner, pas nommer un son
ou lui imposer une cause visible. Source :
[code audio](https://github.com/LoveRain1997/video-to-h3-prompt/blob/main/scripts/audio_probe.py).

Ne pas copier sa compilation H3 : PanelForge possède déjà les contrats, rôles de
références, règles caméra/dialogues et versions de préparation. Un rédacteur
parallèle ferait évoluer deux systèmes de prompting et fragiliserait leurs contrats.

## Notre base actuelle, vérifiée dans le code

- Video Lab sélectionne un extrait et extrait ses images dans le navigateur :
  huit captures proposées, jusqu'à seize, avec temps relatifs au début de l'extrait.
- `MediaAnalysisService` fait un seul appel multimodal et sauvegarde intention,
  observations et incertitudes. L'utilisateur peut corriger l'intention française.
- La transcription locale facultative est déjà disponible, CPU par défaut.
  Le modèle vision reçoit son texte ; ce n'est pas un modèle de compréhension sonore.
- Le transfert vers H3/REF2V reprend l'intention et les références explicitement
  choisies. Les frames d'observation ne deviennent pas automatiquement des images
  de conditionnement, et leurs numéros ne doivent pas fuir dans l'intention finale.
- Le service d'analyse ne conserve pas le fichier vidéo complet pour réextraction.
  À la réouverture, les captures restent disponibles mais il faut réimporter la vidéo
  pour changer l'extrait. Les segments horodatés de transcription sont stockés ;
  le contexte vision actuel transmet surtout son texte et ses options.

Références locales : `domain/media_analysis.py`, `application/media_analysis.py`,
`features/lab/static/media-analysis.js`, [guide V1](../media-analysis-1.0.md),
[transcription](../media-analysis-speech-1.1.md).

## Extension proposée, sans multiplier les outils

Conserver Video Lab et le résultat français éditable. Une option repliée
« Approfondir les actions ambiguës » pourrait activer une nouvelle version
d'analyse. Les valeurs ci-dessous sont un budget proposé à valider, pas une
fonction déjà implémentée ni une contrainte définitive de l'utilisateur.

1. Premier appel : observation globale des captures et paroles, chronologie
   structurée, actions/caméra/montage séparés, hypothèses et zones ambiguës horodatées.
2. Seulement si nécessaire et si la vidéo source reste disponible : extraire des
   images supplémentaires sur au plus deux zones. Exemple de plafond initial :
   huit nouvelles images au total, une seule passe vision supplémentaire, bornes
   et résolutions contrôlées ; pas de boucle d'agent à profondeur libre.
3. Le dernier appel d'analyse produit l'intention et les incertitudes résiduelles.
   Transfert par le parcours existant ; les deux appels Plan/Writer H3 restent
   distincts de ce budget d'analyse, et sont déclenchés dans l'atelier habituel.

Pour une première version légère, le navigateur peut conserver le fichier ouvert
et extraire ces nouvelles captures à la demande. Après fermeture/rechargement,
afficher explicitement que la vidéo doit être resélectionnée ; ne pas promettre
une reprise autonome côté serveur. Si le besoin de reprise durable apparaît,
envisager un stockage explicite du seul extrait choisi, avec rétention bornée.
Pas d'upload systématique de toute la vidéo dans ce premier périmètre.

Pour une série d'images, aucune frame intermédiaire ne peut être extraite : garder
les incertitudes et le mode actuel. Distinguer le temps de la source du temps cible
si l'utilisateur adapte la scène à une autre durée. Une action masquée ne doit pas
devenir un fait observé faute de meilleure image.

Pas de nouveau service, dépendance d'analyse audio, modèle ou chargement GPU
automatique nécessaire à cette première extension. Le coût vient surtout des
images et tokens supplémentaires sur le modèle vision existant. La VRAM et les
latences doivent être mesurées sur la configuration réellement chargée ; aucune
promesse fondée sur la seule capacité théorique d'une carte GPU.

Avant promotion, essais utilisateur sur quelques mouvements rapides, coupes,
occlusions et scènes calmes : moins de causes inventées, actions mieux retrouvées,
latence et nombre d'appels visibles. Les familles Classique/Combat/Sensuel et
leurs contrats de génération restent indépendants de cette observation amont.
