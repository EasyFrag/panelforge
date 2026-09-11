# Analyse visuelle → intention française — V1

Extension : [transcription locale facultative 1.1](media-analysis-speech-1.1.md), CPU par défaut. Le parcours visuel reste disponible sans audio ; l’enregistrement passe au schéma 2, compatible avec le schéma 1.

Implémentation du 10 septembre 2026, checkout `D:\Code\localQ\.panelpatch`.

Dans **Video Lab → Analyser des médias**, importer une vidéo ou une série d’images. Un texte français facultatif indique les éléments à conserver ou à adapter. L’analyse produit une intention française éditable, avec observations et incertitudes séparées. Elle ne génère pas elle-même de prompt H3/REF2V ni de vidéo.

## Vidéo et images

- Vidéo : sélecteur début/fin à deux poignées, valeurs saisissables, lecture de l’extrait. Extrait de **0,1 à 60 secondes** ; **8 captures** proposées, réglables de **2 à 16**. Préparer/actualiser les captures après un changement de plage, retirer une capture ou ajouter celle du curseur. Les temps transmis commencent à zéro au début de l’extrait ; un extrait 12–20 s devient une chronologie 0–8 s. Les captures gardent les dimensions de la vidéo et utilisent JPEG qualité 95 ; la dernière capture de fin de fichier est prise légèrement avant la fin décodable.
- Images : **1 à 16 PNG/JPEG/WebP**, ajout à la série, retrait, flèches de réordonnancement, ouverture en grand. Temps en secondes facultatif par image. Le temps reste attaché à l’image déplacée. Repères contradictoires : message, correction ou effacement manuel ; aucun tri ou effacement silencieux. Les temps absents restent inconnus.
- Durée cible **5 à 15 secondes**, cohérente avec les limites actuelles de `VideoLabSettings` utilisées par H3 et REF2V. Elle est distincte de la longueur de la vidéo source. Un extrait plus long peut être analysé pour adapter la progression à une scène plus courte. Pour les images, le dernier repère doit tenir dans la durée cible. Changer les entrées après analyse marque le résultat comme ancien et demande une nouvelle analyse avant transfert.

Le navigateur décode les vidéos lisibles localement, extrait seulement les captures choisies et les envoie au serveur. Le fichier vidéo complet n’est pas uploadé. Les captures/images sont conservées dans le magasin d’assets ; seule la copie envoyée au LLM est orientée selon EXIF, convertie en JPEG et réduite à un côté maximal de 1280 px. Aucun traitement GPU ou dépendance supplémentaire.

## Analyse, sauvegarde et transfert

Un appel multimodal via le routage existant (dont Local/Unsloth), consigne versionnée `media.visual-intention@1.0.0`. Texte français en JSON strict : intention, observations et incertitudes. La consigne sépare faits visibles, adaptations demandées, transitions inconnues et sons non observés. Elle ne choisit ni famille de préparation, ni modèle vidéo, ni LoRA.

Le module charge ses modèles et ses trois analyses récentes seulement à son ouverture. Le flux et l’éventuelle trace restent propres à cet écran ; naviguer vers d’autres ateliers ne l’interrompt pas. Une erreur ou une annulation conserve les entrées. Réessayer une analyse déjà créée réutilise le même identifiant ; une réponse déjà réussie n’entraîne pas un second appel. Cliquer à nouveau sur Analyser après un succès crée volontairement une nouvelle analyse. Le bouton Annuler interrompt le flux côté navigateur ; la libération côté fournisseur dépend de sa fermeture effective, sans décharger le modèle ou interrompre les autres travaux.

Les analyses sont stockées séparément sous `workspace/media_analysis`, **schéma 1**, avec sources, temps, extrait, durée cible, modèle, consigne, version, identifiant d’appel et textes généré/édité. Une analyse vidéo rouverte conserve les captures ; resélectionner le fichier vidéo pour modifier son extrait. Les brouillons avant analyse et références supplémentaires restent dans la mémoire de l’onglet.

Après relecture, Enregistrer conserve les corrections et Copier fournit le texte. La zone Références pour générer permet de choisir explicitement les images analysées utiles, ou d’importer ses propres références :

- H3 : aucune, première, dernière ou première + dernière image.
- REF2V : 1 à 9 images, avec leurs rôles habituels ; une première et une dernière frame exactes au maximum.

Les boutons Préparer dans H3 / REF2V enregistrent l’intention puis préremplissent un nouvel atelier avec uniquement les références choisies. Un brouillon de destination ou une préparation active n’est pas écrasé : un message conserve l’analyse disponible pour un transfert ultérieur. Les recettes existantes restent sélectionnables, aucune famille Classique/Combat imposée ; pas d’appel de préparation ou de rendu automatique.

## Implémentation et vérification

Contrat métier `domain/media_analysis.py`, service applicatif isolé, stockage et préparation Pillow injectés, adaptateur HTTP séparé `features/lab/media_analysis_web.py`. Opérations spec, création multipart, lecture/liste, flux d’analyse et sauvegarde d’intention. Validation des temps, limites, nombre et décodage des images avant création du dossier d’analyse ; maximum 20 Mio par image et 64 Mio au total. Aucun changement des schémas de sessions/projets H3/REF2V ni des workflows ComfyUI. Cache CSS/core/H3/REF2V et nouveaux modules **20260910.11**.

Tests préparés, **non exécutés pendant l’implémentation** :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_media_analysis tests.test_media_analysis_browser tests.test_lab_web tests.test_social_lab_ui tests.test_run_lab_build
```

Couverture préparée : temps partiels et ordre, bornes d’extrait et temps relatifs, validation des uploads, orientation et originaux, un appel et reprise sans doublon, échec/troncature/annulation, stockage et intention corrigée, chargement différé, transfert explicite des références et protection des ateliers occupés. Transports simulés ; scénario DOM Chromium local si installé.

Vérification par l’agent limitée à AST Python, syntaxe JavaScript sans invocation, liaisons HTML, empreintes des prompts antérieurs et contrôle du diff. Aucun test, import applicatif de vérification, LLM, rendu, navigateur ou redémarrage lancé. La précision temporelle de l’analyse et les codecs vidéo restent à expérimenter par l’utilisateur ; des captures espacées ne démontrent pas tous les gestes ou toutes les coupes. Audio/transcription et analyse vidéo native hors V1.
