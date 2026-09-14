# Upscale DLSS local

Implémentation autorisée le 9 septembre 2026, après la [discussion initiale](dlss-local-proposal-2026-09-09.md). Les tests et essais GPU restent à exécuter par l’utilisateur.

## Utilisation

**Upscale DLSS** est disponible sur les résultats réussis de KREA2 Assisted, de l’atelier Edit (KREA2 ou FireRed), et des vidéos H3 / REF2V. Dans Edit, il est aussi accessible sous le comparateur pour l’image sélectionnée dans « Après ». Pour les images, le panneau montre la cible, les dimensions prévues, la taille souhaitée et le bouton de lancement ; les autres réglages restent repliés.

Pour **H3 / REF2V**, le bouton **Upscale DLSS** lance directement **×1,724 + 60 FPS**, sans popup. Ces valeurs sont fixes et indépendantes des derniers réglages avancés : HDR désactivé, H.264 NVENC, intensité/tonalité/structure/détails à 1, peau automatique (-1), style Default, repli autorisé. **Upscale avancé** ouvre le panneau ; le lancement revient à l’atelier dès que la tâche est enregistrée. Fermer le panneau pendant l’envoi ne l’annule pas.

| Atelier | Taille par défaut | Comportement |
| --- | --- | --- |
| Edit | ×1,5 · Quality | Finition de toute l’image sélectionnée. Le choix explicite « Taille de la source » reste disponible pour continuer une étape avec son masque. |
| Assisted | ×1,5 · Quality | Traite l’image sélectionnée dans son ensemble. |
| H3 / REF2V | ×1,724 + 60 FPS | Lancement direct en arrière-plan ; conserve la durée et la présence d’audio. Le mode avancé permet notamment de garder la cadence source. |

Dans Edit, choisir un facteur au lieu de « Taille de la source » effectue une **finition de toute l’image sélectionnée**, composite inclus. Les zones issues de la source peuvent alors changer aussi. Ce résultat conserve sa taille agrandie ; il ne porte pas l’ancien masque comme si ce masque avait protégé le traitement final. L’ancien candidat masqué reste disponible pour reprendre ce masque. Une nouvelle retouche sur la finition utilise cette image améliorée comme entrée et revient au contrat de taille source du comparateur.

Les facteurs proposés sont ×1 (DLAA), ×1,5, ×1,724, ×2 et ×3. Le panneau affiche les dimensions réellement prévues, avec l’arrondi pair du nœud. Les images de sortie sont limitées à **16 MP** pour rester utilisables dans les ateliers existants ; le nœud accepte au maximum 7680 × 4320, portrait compris. La passe ×2 intermédiaire du mode taille source doit elle aussi respecter cette limite. Les images doivent avoir au moins 64 pixels sur chaque axe. Lecture PNG/JPEG/WebP fixe, orientation EXIF respectée, maximum 100 Mio ; en mode source, un écart de proportions supérieur à 1 % est refusé.

Les réglages avancés reprennent les contrôles NR du workflow fourni. HDR désactivé, codec H.264 NVENC par défaut ; H.265 NVENC requis pour activer HDR. La fluidification passe réellement par le nœud d’interpolation avant la sauvegarde vidéo. L’interpolation et le changement de résolution restent deux opérations distinctes.

### Réglages initiaux image et aides — 11 septembre 2026

Les nouveaux panneaux image reprennent la capture fournie et les valeurs de `NvidiaDLSSImageUpscale` installé : taille ×1,5, intensité NR / tonalité locale / structure locale / détails de sortie à 1, structure peau à −1, style Default, repli autorisé. Les réglages fixes du graphe restent NR Preset Default, DLSS Model Preset Default, Automatic Mask désactivé. Auparavant, le panneau envoyait 2 pour les quatre forces NR, dont la peau, avec ×2 en Assisted et Taille source en Edit.

Les boutons « i » à côté des réglages ouvrent une aide locale, utilisable au clavier ; le survol montre aussi l’explication. Le bouton « Réglages initiaux de l’image », dans les options avancées, restaure ces valeurs sans lancer de traitement. Les réglages déjà choisis restent mémorisés par image tant que le panneau est fermé puis rouvert dans le même onglet.

−1 pour la peau est la valeur native, pas une force négative. Les valeurs natives et les choix de styles sont documentés dans le [projet d’origine](https://github.com/Merserk/dlss5-visual-enhancer#settings). Les effets précis dépendent du moteur et de l’image ; le contrôle Détails à 1 laisse la sortie du moteur intacte, tandis qu’une valeur supérieure amplifie les écarts de luminosité, sans seconde inférence, selon la [documentation du node installé](https://github.com/Konohamaru04/ComfyUI-NVIDIA-DLSS-Frame-Interpolation#sdr-output-detail-strength).

Les requêtes API image partielles reçoivent également ces défauts ; les valeurs explicitement transmises restent prioritaires. Les bindings du workflow appliquent ces valeurs lors de la compilation : le graphe historique 0.1.0 reste immuable, et les tâches déjà enregistrées gardent leurs réglages et leur référence de workflow. Le mode Taille source conserve sa passe intermédiaire ×2 puis sa recomposition avec masque. Aucun changement des réglages vidéo.

Cache CSS et panneau DLSS : **20260911.6**. Tests préparés, non exécutés : `tests.test_dlss_image_defaults`, `tests.test_dlss`, `tests.test_dlss_browser` (défauts jusqu’aux entrées du node, choix explicites, vidéo inchangée, aides et reset sans soumission, brouillons et dimensions). Après ses traitements, l’utilisateur redémarre le Lab pour l’API puis recharge la page. Aucun runtime, LLM, ComfyUI, rendu ou service lancé/modifié par l’agent.

## Résultats et historique

### Comparer les préréglages image — 13 septembre 2026

Dans **Upscale DLSS → Traitement de l’image**, choisir **Comparer des préréglages**. Le mode **Upscale unique** reste sélectionné à la première ouverture. Les cinq profils sont cochés initialement ; décocher ceux qui ne sont pas souhaités, puis **Lancer les N variantes**. La taille de sortie est commune à toute la série. Les réglages avancés constituent le point de départ de chaque profil ; la recette image est versionnée `1.0.0`.

| Profil | Écart par rapport aux réglages actuels |
| --- | --- |
| Réglages actuels | Aucun |
| Traitement doux | Intensité NR −0,25 |
| Détails renforcés | Détails de sortie +0,15 |
| Structure renforcée | Structure locale +0,20 |
| Tonalité adoucie | Tonalité locale −0,20 |

Les valeurs sont bornées aux plages du moteur. Un profil devenu identique au point de départ à une limite est désactivé pour éviter une exécution inutile. Style, peau, taille et refus du repli conservent les choix de l’utilisateur. Les valeurs effectives de chaque profil sont visibles avant lancement. Ces profils sont des points de comparaison, sans promesse de supériorité visuelle.

Le panneau se ferme dès l’envoi ; la file DLSS existante exécute les variantes en arrière-plan, depuis la même source, avec un compteur **N/M variantes terminées**, les erreurs et l’annulation/reprise de chaque tâche. Une seule lecture des dimensions est nécessaire à l’admission de toute la série. En cas d’envoi interrompu, rouvrir le panneau dans le même onglet et relancer la même sélection reprend l’admission avec le même identifiant, sans dupliquer les tâches déjà enregistrées. Un identifiant réutilisé avec d’autres réglages est refusé. Les sorties prêtes restent disponibles si une autre variante échoue.

**Comparer DLSS** apparaît sur la carte source et dans les résultats du suivi. Il ouvre deux panneaux avec Original / variantes terminées, réglages consultables, zoom commun, vue entière et affichage à 100 % des pixels de sortie. Défilement ou glissement à la souris synchronisent la zone examinée ; changer de variante conserve le cadrage. La comparaison propose les résultats de la même source et des mêmes dimensions que la variante sélectionnée. Les images sont chargées à l’ouverture du comparateur, sans précharger cinq sorties HD dans chaque carte.

**Afficher cette variante dans l’atelier** sélectionne le candidat exact, qui peut ensuite être enregistré, utilisé pour un feedback ou validé comme auparavant. Une série ne sélectionne pas automatiquement son dernier résultat et ne rafraîchit pas l’atelier à chaque fin de tâche. Les tâches, profils, paramètres et liens de filiation sont persistés dans le journal DLSS existant ; après un refresh, les séries terminées restent comparables. Aucun schéma de projet ni fichier original n’est remplacé. Dans Edit, **Taille de la source** conserve la recomposition et le masque pour chaque variante.

L’API supplémentaire `POST /api/dlss/image-comparisons` accepte uniquement `assisted` et `edit`, de un à cinq `preset_ids` distincts et les réglages communs. Les jobs gardent leur exécution, annulation et import individuels. H3/REF2V, leur admission simple, les paramètres vidéo, le worker partagé et les workflows versionnés restent inchangés.

Assets DLSS image, DLSS commun, Assisted/Edit et CSS : **20260913.2**. Après les traitements, redémarrer le Lab pour charger la nouvelle route puis Ctrl+F5. Vérifications préparées pour l’utilisateur : `python -m unittest tests.test_dlss_image_comparison tests.test_dlss_image_comparison_browser tests.test_dlss_image_defaults tests.test_dlss_browser tests.test_dlss`. Elles utilisent uniquement les faux gateways et fixtures locales. Contrôles statiques effectués par l’agent, aucun test, navigateur ou upscale réel exécuté.

- Chaque sortie est une **variante du rendu d’origine**, sélectionnable par Original / DLSS dans sa carte. Elle ne consomme pas de numéro de génération et ne remplace aucun fichier existant.
- Feedback, téléchargement, export, validation Edit, reprise Assisted et continuation vidéo utilisent le candidat sélectionné. Les vignettes et la dernière frame d’une vidéo DLSS sont extraites de sa propre sortie.
- Relancer avec d’autres réglages depuis une variante DLSS repart de son original, sans accumuler les passes DLSS. Les paramètres de génération restent hérités et distincts du diagnostic d’upscale.
- Le panneau affiche les tâches, leurs phases, erreurs et liens de téléchargement/diagnostic. « Voir le résultat » sélectionne la variante dans l’atelier ouvert. Le carillon de fin des rendus est réutilisé, une fois par tâche suivie dans l’onglet.
- L’ancien ESRGAN / ClearReality reste dans **Upscaler historique** sous le comparateur Edit. Les anciennes améliorations restent lisibles. Les upscales latents internes aux workflows de génération H3, REF2V et KREA2 Batch restent en place.

## Suivi vidéo en arrière-plan

Le suivi apparaît sous la carte du rendu, avec un indicateur global discret qui reste accessible pendant la navigation. Le panneau avancé reste facultatif. Les commandes de prompt et de génération ne sont pas verrouillées par DLSS ; seuls les traitements DLSS partagent leur file locale. À la fin d’une vidéo DLSS, la sélection actuelle et le brouillon de prompt sont conservés. **Voir le résultat** sélectionne explicitement la variante et recharge les essais, sans réinitialiser le prompt ou les réglages. L’autosélection des upscales image uniques garde son comportement précédent ; les séries comparatives attendent un choix explicite.

Les phases sont **Upscale**, **Fluidification 60 FPS**, **Enregistrement**, puis récupération/import et copie serveur. La barre affiche le pourcentage fourni par Comfy pour la phase courante, avec le temps écoulé ; elle peut donc repartir au début lors du passage à la phase suivante. Aucun pourcentage global de durée n’est inventé. Sans valeur mesurée, l’état reste textuel ; une progression ancienne est signalée comme en attente de mise à jour.

Le serveur Lab observe la socket locale avec le même client que la soumission et filtre l’identifiant exact de l’exécution. Les IDs/labels des phases sont dans les manifests. Une socket indisponible ne fait pas échouer le rendu, qui continue à être suivi par son historique. Les coups de pinceau, LLM et générations Bucket ne dépendent pas de cette connexion.

## ComfyUI Windows et mémoire

Configuration par défaut :

```text
--dlss-root D:\AI\ComfyUI_windows_portable
--dlss-base-url http://127.0.0.1:8188
--dlss-output-root D:\AI\PanelForge\LocalOutput
--dlss-video-export-root X:\data\ComfyUI\output\video\Upscale
```

Les générations habituelles continuent à utiliser Bucket. Ouvrir le panneau ou lire les dimensions ne lance pas ComfyUI. **Lancer l’upscale** réutilise une instance locale compatible ou démarre son équivalent du `run_dlss.bat` : Python embarqué, `ComfyUI/main.py --windows-standalone-build`, environnement FFmpeg/FFprobe dans `tools`, port local configuré, sans fenêtre ni `pause`. Le BAT utilisateur n’est pas modifié. Une tâche autorisée et encore en attente peut aussi reprendre au prochain chargement du Lab.

Comfy reste ouvert après traitement. **Aucune commande ne décharge ou n’arrête Unsloth.** La coexistence réelle, la mémoire consommée et la qualité d’upscale doivent encore être observées.

Le bouton **DLSS local** dans les commandes de maintenance donne accès aux tâches et à :

- **Libérer la mémoire** : demande `/free`, sans promettre une VRAM nulle.
- **Arrêter / Redémarrer Comfy local** : uniquement le processus démarré par PanelForge, identifié par son PID, son heure de création, son exécutable et l’adresse locale enregistrée. L’arrêt cible aussi ses descendants. Une instance déjà ouverte manuellement peut être utilisée et nettoyée, mais sa fermeture reste manuelle.
- **Annuler cette tâche** dans le suivi : annulation du seul identifiant d’exécution local concerné. Les commandes mémoire/arrêt refusent une file active ou en attente, y compris les autres tâches de l’instance locale.

Après un arrêt, le prochain upscale relance Comfy si nécessaire. Le journal de démarrage est disponible depuis le panneau. Aucun service n’a été lancé ou redémarré pendant l’implémentation.

## Reprise et stockage

Le moteur commun sérialise les traitements image/vidéo. Son journal est dans `<workspace>/dlss/` : un JSON par tâche, `runtime.json` pour le processus géré, `comfy-local.log` pour son démarrage. Un verrou système empêche deux processus Lab d’exécuter la même file ; les fichiers JSON sont remplacés atomiquement.

L’identifiant de demande est stable lors d’une nouvelle tentative du navigateur. L’identifiant d’exécution est enregistré **avant** l’envoi à Comfy. Après une réponse perdue ou un téléchargement interrompu, « Reprendre cette tâche » recherche la même exécution. Un échec Comfy terminal confirmé peut être relancé explicitement ; une exécution inconnue n’est pas soumise à nouveau automatiquement. Une annulation avant soumission peut être reprise explicitement.

Pour les nouveaux résultats DLSS, **le PNG/MP4 est référencé directement dans son dossier de sortie** ; aucune copie permanente du média final n’est écrite dans `workspace/assets`. Ce catalogue garde seulement sa fiche (chemin, taille, empreinte), ainsi que les images de feedback extraites et le rapport. La lecture, le feedback, la reprise et l’export continuent à utiliser les mêmes identifiants d’assets. Si le fichier référencé est déplacé, supprimé ou remplacé, la lecture est refusée : il faut conserver ce dossier de résultats.

Une image réellement redimensionnée ou recomposée après DLSS (taille source / masque Edit) est enregistrée comme PNG distinct dans le dossier visible `LocalOutput/dlss`, puis référencée. Le PNG Comfy est réutilisé tel quel quand il ne nécessite aucun de ces traitements. Aucun ancien média ni `content.bin` existant n’est supprimé ou migré automatiquement.

Si l’étape Edit a été recommencée ou validée pendant le traitement, le fichier reste téléchargeable mais n’est pas ajouté à cette nouvelle mémoire. Le candidat n’entre jamais dans la file des générations Bucket. Un nouvel essai d’import ne crée pas de doublon de candidat.

Les rapports contiennent réglages DLSS, provenance, dimensions/cadence/durée, workflow, endpoint et identifiants d’exécution, ainsi que les diagnostics bruts du nœud. Un mode de repli neural est signalé. Les exports image conservent aussi ce rapport et distinguent les réglages de génération et ceux du post-traitement.

### Copie automatique des vidéos sur le serveur

L’emplacement initial dépend du dossier de sortie du processus Comfy utilisé. **L’instance actuelle lancée par `run_dlss.bat` utilise `D:\AI\PanelForge\LocalOutput\dlss\`**, pour les PNG et les MP4 : argument `--output-directory` vérifié dans le BAT et le processus, fichiers présents. Le démarrage automatique de PanelForge est désormais aligné sur ce dossier avec `--dlss-output-root` ; il transmet `--output-directory` sans modifier le BAT. Réutiliser le Comfy déjà ouvert conserve son dossier de sortie. Le dossier standard `ComfyUI/output` reste accepté en repli pour une instance déjà ouverte avec l’ancienne configuration. Une autre destination demande de régler `--dlss-output-root` ; un fichier manquant ou différent du résultat téléchargé est signalé, sans copie cachée de secours dans les assets.

Les anciens résultats gardent leur copie interne (`<workspace>\assets\<asset-id>\content.bin`), ce qui explique l’absence d’extension PNG/MP4 dans ce catalogue. Les nouveaux résultats conservent seulement `asset.json` dans ce sous-dossier. Le **chemin réel du résultat local** est affiché dans le suivi DLSS. Les nouvelles vidéos terminées sont aussi copiées par un worker distinct vers :

```text
X:\data\ComfyUI\output\video\Upscale\YYYY-MM-DD\dlss-<identifiant>.mp4
X:\data\ComfyUI\output\video\Upscale\YYYY-MM-DD\dlss-<identifiant>.json
```

Le sous-dossier correspond à la **date locale du PC au moment où le résultat devient disponible**. La date et le chemin sont enregistrés dans la tâche : une relance de copie après minuit garde la destination initiale. Le JSON accompagne la vidéo avec son diagnostic DLSS. Une copie partielle peut reprendre ; un fichier existant identique est conservé, un contenu différent portant le même nom est refusé.

Le montage `X:` a été vérifié en lecture : `\\sshfs.r\malmo@bucket`, dossier `data\ComfyUI\output\video\Upscale` présent. La copie utilise ce chemin Windows depuis le Lab ; aucun chemin Linux équivalent n’est supposé. Si le Lab change de compte ou de mode de lancement, fournir un chemin absolu accessible à ce processus avec `--dlss-video-export-root` (montage ou UNC).

Un partage lent ne retient ni le verrou de rendu ni celui des requêtes. Si la copie échoue, la vidéo reste réussie et disponible dans le Lab ; **Réessayer la copie** retente uniquement l’export, sans nouvelle génération ni upscale. Le chemin réussi et l’erreur éventuelle sont affichés dans le suivi. Aucune migration automatique des anciennes vidéos déjà terminées. Aucun fichier n’a été envoyé au partage pendant l’implémentation.

Contrats versionnés :

- Workflows image `image.upscale/dlss/0.1.0`, vidéo `video.upscale/dlss/0.1.0` et `video.upscale/dlss-smooth/0.1.0`. IDs des nœuds et liaisons dans leurs manifests, empreintes vérifiées à la lecture.
- Stockage Edit **11** (lecture 1–10), Assisted **8** (lecture 1–7), H3 **4** (lecture 1–3). Variantes réussies avec `output_asset_id` propre et provenance `dlss`, sans identifiant de génération Comfy dans l’essai.
- Journal DLSS enrichi avec progression, heure de fin et état de copie ; anciens journaux compatibles. Graphes et contrats de génération inchangés, phases ajoutées aux manifests.
- Assets externes au **schéma 2**, avec racines autorisées explicites et vérification taille/empreinte à chaque lecture ; assets internes au schéma 1 inchangés. Aucun changement du domaine ou des formats de projet. Journal DLSS conserve le descripteur Comfy et les chemins des résultats.
- Cache **DLSS 20260909.3**, H3 rendu/CSS 20260909.2 ; core/Edit/Assisted restent en 20260909.1. Tag de restauration `stable-avant-masque-2026-09-06` conservé sur `56840b877be4b810ee93f8afe9b2f0c40ee73006`.

## Vérification à effectuer par l’utilisateur

Les tests `tests/test_dlss.py`, `tests/test_dlss_progress_export.py` et `tests/test_dlss_browser.py` sont préparés avec passerelles simulées : file locale, démarrage masqué, réutilisation de l’instance, arrêt ciblé, idempotence/reprise, erreurs de dimensions, masques et pixels protégés, exports, feedback, frames vidéo, compatibilité du stockage et interface. Le complément couvre le routage de progression par exécution, les phases, l’abonnement avant soumission, les sauvegardes concurrentes, le partage indisponible, la reprise d’une copie partielle sans rendu, la date persistée et les commandes vidéo sans modal ni autosélection. Les assertions de schéma, bootstrap et caches existantes ont été actualisées.

`tests/test_dlss_outputs.py` couvre les références sans copie, anciens assets, fichiers manquants/modifiés, racines interdites, repli vers l’ancien dossier Comfy et PNG recomposés. Les scénarios Assisted/Edit/H3/REF2V existants sont enrichis avec la lecture des fichiers référencés, réouverture du masque, continuation et export ; le test de bootstrap vérifie une lecture HTTP partielle (Range) du MP4 référencé et le lancement simulé vérifie le dossier personnalisé. Tests préparés, non exécutés.

Exemple de commande, depuis le checkout actif :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_dlss tests.test_dlss_outputs tests.test_dlss_progress_export tests.test_dlss_browser tests.test_local_storage tests.test_run_lab_build
```

**Tests non exécutés par l’agent.** Seules l’analyse syntaxique Python, la compilation JS sans invocation et la lecture des données/manifests sont utilisées pour les contrôles statiques. Aucun appel LLM, génération, chargement de modèle ni mesure de performance.

Après redémarrage du Lab par l’utilisateur et rechargement de la page : lancer l’upscale rapide d’une courte vidéo avec Unsloth ouvert, écrire un prompt ou lancer une autre génération pendant le traitement, puis vérifier progression, cadence/audio et copie dans le dossier du jour. La qualité et la coexistence GPU restent à expérimenter.
