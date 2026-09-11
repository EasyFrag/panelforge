# Analyse média — transcription locale 1.1

Correctif du 11 septembre : nouvelles consignes **1.0.1 / 1.1.1**, séparation des citations de captures et de l’intention transférée ; [diagnostic et tests](media-h3-boundary-fixes-2026-09-11.md). Les versions décrites ci-dessous restent les bases historiques de l’extension.

Implémentée sur autorisation les 10–11 septembre 2026. Dans **Video Lab → Analyser des médias**, la vidéo propose **Transcrire les paroles**, facultatif et désactivé au départ. Les séries d’images et l’analyse visuelle seule restent utilisables sans moteur audio.

## Parcours

1. Importer la vidéo, sélectionner l’extrait de 0,1 à 60 secondes et préparer les captures.
2. Activer **Transcrire les paroles**, choisir la langue (anglais par défaut, français / auto / autres langues proposées) puis **Transcrire l’extrait**.
3. Traitement **CPU par défaut**, sur demande utilisateur du 11 septembre après son essai GPU infructueux. Le GPU reste sélectionnable ; le processeur enregistré dans une analyse rouverte est conservé.
4. Corriger le texte et ses repères, relatifs au début de l’extrait. **Restaurer la transcription initiale** annule ces corrections. Aucune parole détectée est un résultat valide, sans prouver que la vidéo est silencieuse.
5. **Conserver les répliques dans l’intention**, désactivé par défaut : sans cette option, les paroles servent au contexte ; avec elle, les répliques pertinentes restent dans leur langue originale, entourées d’une intention française. Aucune attribution automatique d’une voix à un personnage.
6. Lancer explicitement **Analyser et rédiger l’intention**, puis les transferts H3/REF2V habituels. La transcription ne lance ni LLM ni génération.

Changer l’extrait ou la langue demande une nouvelle transcription avant l’analyse avec paroles. Revenir aux anciennes valeurs retrouve le brouillon correspondant. Désactiver l’option conserve le texte en mémoire mais l’exclut de l’analyse. Erreur et annulation conservent la transcription précédente et ses corrections. Les autres ateliers restent utilisables pendant le traitement.

Original, segments, corrections, langue, processeur et option de répliques sont enregistrés **avec l’analyse**, puis restaurés à sa réouverture. Avant création d’une analyse, le brouillon reste en mémoire de l’onglet. Après réouverture, seule une nouvelle transcription demande de réimporter la vidéo.

## Moteur et fichiers

Réutilisation de l’installation Subtitle Edit, sans ouvrir son interface ni importer un modèle Python dans le serveur :

`%APPDATA%\Subtitle Edit\SpeechToText\Purfview-Faster-Whisper-XXL`

Ce dossier contient `faster-whisper-xxl.exe`, `ffmpeg.exe` et `_models\faster-whisper-large-v3-turbo\model.bin`. Un autre chemin peut être fixé via **PANELFORGE_WHISPER_ROOT** avant le prochain lancement du Lab. La disponibilité est vérifiée par présence des fichiers ; ouvrir l’écran ne lance aucun processus.

Le navigateur transmet temporairement la vidéo au Lab (**1 Gio maximum**), car V1 ne transmettait que ses captures. ffmpeg extrait le passage choisi en WAV mono 16 kHz ; Whisper reçoit ce WAV avec `--task transcribe`, le modèle existant `large-v3-turbo`, sortie JSON et langue choisie (omise pour détection automatique). CPU utilise `int8`, GPU le calcul automatique. Pas de traduction, de diarisation, de séparation vocale ni de mise en page des sous-titres.

Vidéo temporaire, WAV, JSON et sorties du processus sont supprimés après réussite, erreur ou annulation normale. Pas de copie audio/vidéo dans `workspace/assets`. Un arrêt brutal du Lab ou de Windows peut laisser des fichiers temporaires système. Les chemins de fichiers ne sont pas injectés dans le prompt.

Une transcription locale à la fois. Le moteur tourne dans un processus ponctuel, fermé avant le résultat ; l’annulation interrompt uniquement le processus démarré pour ce traitement. Aucun arrêt, déchargement ou redémarrage d’Unsloth/ComfyUI. Extraction limitée à 120 s de traitement, transcription à 900 s ; phases et temps écoulé affichés, sans pourcentage inventé. La coexistence GPU et la qualité restent à expérimenter. La transcription n’établit pas les bruitages, la musique ou les émotions vocales.

## Contrats et vérification

Service `MediaTranscriptionService`, adaptateur injecté `PurfviewTranscriber`, route multipart `/api/media-analysis/transcriptions/stream` avec événements SSE et annulation sur déconnexion. Modules JavaScript audio et visuel séparés. Aucun appel serveur pendant la correction du texte. Cache CSS/audio/intégration **20260911.1**.

L’analyse **avec transcription** utilise `media.visual-intention@1.1.0` ; sans audio, elle garde les consignes exactes **1.0.0**. Seul le texte corrigé est donné au LLM, avec l’option de répliques et la langue ; les segments originaux restent une provenance sauvegardée. Stockage analyse **schéma 2**, compatible schéma 1 ; aucun changement du stockage H3/REF2V.

Tests préparés, **à exécuter par l’utilisateur** :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_media_transcription tests.test_media_analysis tests.test_media_analysis_browser tests.test_media_analysis_speech_browser tests.test_lab_web tests.test_run_lab_build
```

Moteurs/processus simulés : CPU par défaut et GPU explicite, plage correcte, texte vide, temps invalides, corrections/provenance, réouverture/ancien schéma, isolation LLM/rendu, annulation et nettoyage. Scénarios DOM Chromium local si installé. Vérification de l’agent limitée à syntaxe Python/JavaScript, liaisons HTML, conservation du prompt antérieur et contrôle du diff. Aucun test, exécutable Whisper/ffmpeg, LLM, rendu ou service lancé.

## Évolution en discussion : priorité à l’action

Retour du 11 septembre : description utile pour texte vers vidéo, mais jugée trop détaillée et pas assez centrée sur l’action quand des images seront déjà fournies à H3/REF2V. Proposition à discuter après essai : **Décrire toute la scène / Guider l’action à partir de mes images** avant analyse. Garder actions, changements d’état, caméra, rythme et invariants nécessaires ; ne pas supprimer automatiquement le décor en REF2V si les références portent seulement l’identité. Les références de génération sont choisies après analyse et ne peuvent donc pas être supposées connues. Aucun réglage ou changement des consignes visuelles appliqué sur ce point.

Sources CLI : [Purfview](https://github.com/Purfview/whisper-standalone-win), [composants Subtitle Edit](https://github.com/SubtitleEdit/subtitleedit/blob/main/docs/third-party-components.md).
