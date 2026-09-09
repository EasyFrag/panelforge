# KREA2 Edit — Retouche par masque V1

Plan validé puis implémenté le 7 septembre 2026 dans `D:\Code\localQ\.panelpatch`.
Point de restauration conservé : `stable-avant-masque-2026-09-06`, commit
`56840b877be4b810ee93f8afe9b2f0c40ee73006`. Ce patch ne déplace pas ce tag.

Extension du 7 septembre : [reprendre une étape validée dans une nouvelle version](krea2-edit-versions.md), avec conservation de l'ancienne chaîne et de ses retouches. Stockage courant au schéma 6, lecture des schémas 1–5 conservée ; le contrat de composition décrit ci-dessous reste inchangé.

## Utilisation

1. Dans **Modifier avec KREA2**, ouvrir **Retoucher** sur un essai réussi,
   ou **Retoucher l’image Après** sous le comparateur.
2. L’atelier passe sur toute sa largeur. Conversation et paramètres sont
   temporairement masqués. **L’image 2 (génération)** reste à gauche, le résultat
   composé à droite. Le séparateur avant/après n’est pas présent dans cet outil.
3. Peindre sur l’image 2 indique les éléments à conserver dans le résultat. Le rouge
   semi-transparent montre le masque ; il n’apparaît jamais dans le résultat.
   La gomme restaure la source. Le masque d’un rendu brut commence vide.
   **Afficher le masque rouge** permet de masquer cette aide. Le sélecteur
   **Image à gauche** permet de choisir **Image 2 · génération** (défaut) ou
   **Source de l’étape**. Le même masque est visible et dessinable sur les deux.
   Le changement conserve les traits, l’Annuler/Rétablir, le zoom, le déplacement
   et les réglages d’harmonisation ; le résultat de droite reste identique.
   Ce choix d’affichage est conservé avec le brouillon dans l’onglet.
4. Ajuster la taille et la douceur du pinceau. **Annuler / Rétablir** agit par
   trait ; Ctrl+Z / Ctrl+Maj+Z fonctionne lorsque l’éditeur a le focus.
   Molette et boutons −/+ contrôlent le zoom commun. **Déplacer**, le bouton
   central ou un glissement dans la vue de droite déplacent les deux images.
   **Ajuster à l’écran** recentre les deux vues.
   Dans la même barre, **Harmoniser avec la source** est désactivé au départ.
   L’activer révèle une intensité **0–100 %** : l’image 2 corrigée et le composite
   suivent le curseur en direct, avant ou après le dessin. Aucun masque n’est perdu.
5. **Revenir à Comparer** conserve le brouillon en mémoire dans cet onglet.
   Revenir sur le même essai retrouve son masque non enregistré. Cela fonctionne
   aussi après avoir changé d’étape ou de mode Image Lab. Un rechargement ou la
   fermeture de l’onglet perd les brouillons ; une alerte de navigation le signale.
6. **Enregistrer comme essai** crée un candidat distinct, par exemple
   **Essai 5 — Retouche 1**, puis revient au comparateur avec ce candidat
   sélectionné dans **Après** et comme feedback. Aucun essai n’est créé pendant
   le dessin. Un masque vide peut être enregistré : son résultat est la source.
7. Sous le comparateur, **Valider l’image Après et continuer** valide exactement
   le candidat sélectionné dans **Après**, même si un essai plus récent existe.
   Les conditions sont communes au bouton de l’historique : étape modifiable,
   projet et étape nommés, aucun rendu actif ni sauvegarde de retouche en cours.

**Reprendre le masque** recharge la source et la génération d’origine, ainsi que
le masque et les réglages d’harmonisation de la retouche. Enregistrer à nouveau crée une nouvelle retouche de
cette même génération. Le composite précédent n’est jamais utilisé comme deuxième
image pour cette recomposition. La numérotation des générations reste indépendante.

Les cartes conservent les actions habituelles : agrandir, comparer via le feedback,
reprendre prompt et réglages, **Valider et continuer**. Une retouche ne devient une
étape de la frise qu’à sa validation ; son PNG exact devient alors la source
suivante et l’image exportée. Les étapes validées proposent **Voir le masque** en
lecture seule. Un brouillon local ne remplace pas le masque enregistré dans cette
consultation.

## Harmonisation locale

L’option utilise **Reinhard dans Lab**, avec Pillow / LittleCMS déjà fournis par
la dépendance Pillow : moyenne et écart-type de chaque canal de la génération
sont rapprochés de ceux de la source. Aucun nœud ComfyUI n’est exécuté.
La génération harmonisée à 100 % est préparée une fois à l’ouverture de l’outil,
en plus des deux images normalisées. Le navigateur mélange ensuite cette image
et la génération brute selon l’intensité, puis applique le masque. Aucun appel
serveur n’est effectué par le curseur ou les traits. À l’enregistrement, Pillow
recalcule le même traitement depuis la source et la génération d’origine.

Contrat versionné `reinhard_lab_rgb@1.0.0` : Lab encodé 8 bits, statistiques
globales après orientation/redimensionnement, gain 1 pour un canal uniforme,
valeurs bornées à 0–255. L’intensité mélange les pixels **RGB** des deux versions
avec `niveau = (intensité × 255 + 50) // 100` et l’interpolation entière du masque.
Il s’agit donc d’une adaptation locale, pas d’une reproduction exacte du nœud
ColorTransfer (qui mélange dans Lab), ni du MKL du second nœud du fichier fourni.
L’alpha de la génération reste inchangé. Intensité 0 ou option désactivée :
génération brute exacte ; hors masque/transition : source décodée exacte.

Un transfert global peut atténuer une couleur volontairement nouvelle ; diminuer
l’intensité ou désactiver l’option dans ce cas. Il ne répare ni un décalage de
géométrie, ni une différence de netteté. Le rendu visuel reste à évaluer par
l’utilisateur. Les étapes validées conservent leurs réglages en lecture seule.

## Recommencer l’étape en cours

**Recommencer cette étape**, près du titre de l’atelier, demande confirmation puis
revient à l’état initial de cette même étape : image source, projet, rang et lien
avec l’étape précédente conservés ; conversation, prompts générés, erreurs,
essais et retouches retirés de l’atelier. Les brouillons de prompt, réglages,
feedback et masque de cette étape sont aussi retirés de l’onglet. Les réglages de
rendu sont réhydratés depuis la source et l’étape précédente, comme à l’ouverture
d’une nouvelle étape. Le prompt associé à l’image source reste disponible comme
description de départ ; les échanges abandonnés ne sont plus envoyés au LLM.

Les étapes déjà validées sont immuables. Une réinitialisation est refusée pendant
un échange LLM ou un rendu queued/running/cancel_pending, sans annulation ni appel
au serveur de génération. Une retouche composée en parallèle ne peut pas être
ajoutée après la réinitialisation. Une sauvegarde préalable du JSON est conservée
dans `krea2_edits/<source_id>/restarts/before-<compteur>.json`, hors backlog et hors
contexte LLM. Les assets originaux et les traces techniques restent sur disque.
Aucune étape supplémentaire n’est créée dans la frise.

API : `POST /api/image-lab/krea2-edit/sources/{source_id}/restart`, corps JSON
`{"expected_restart_count": 0}` ; réponse `{source}`. Le compteur persistant
`restart_count` augmente à chaque reprise (défaut 0 pour les anciens schémas).
Une nouvelle tentative portant un compteur déjà dépassé renvoie l’état actuel
sans effacer le travail entrepris entre-temps. Compteur futur ou étape occupée/
validée : 409 ; compteur invalide : 422. L’archive précède l’écriture atomique de
l’état courant ; un échec conserve l’état et les brouillons pour une nouvelle
tentative. Les garanties de concurrence concernent le processus Lab habituel.

## Images et composition

- La sortie conserve **les dimensions de la source après orientation EXIF**.
  Seule la génération est redimensionnée, par Lanczos. Les deux orientations sont
  appliquées avant toute comparaison de dimensions.
- Écart de proportions accepté :
  `abs((largeur_rendu / hauteur_rendu) / (largeur_source / hauteur_source) - 1) <= 0.01`.
  Au-delà, un message demande un rendu au même ratio. Aucun recalage, recadrage
  ou alignement automatique n’est effectué.
- Entrées fixes PNG, JPEG ou WebP, au plus 25 Mio par fichier et 16 millions de
  pixels. Les images de l’aperçu sont des PNG RGBA 8 bits normalisés. Les
  métadonnées EXIF/profils ICC ne sont pas recopiées dans ces PNG ; les originaux
  restent conservés. Cette V1 vise les images ordinaires RGB/RGBA de l’atelier,
  sans chaîne colorimétrique HDR ou profils d’impression.
- Le masque transmis est un PNG RGBA avec la couverture dans l’alpha, ou un PNG
  gris. Le serveur le stocke en niveaux de gris : 0 = source, 255 = génération,
  valeurs intermédiaires = transition. Dimensions exactement égales à la source,
  aucune rotation EXIF autorisée sur le masque.
- Le compositeur Pillow calcule chaque canal, alpha compris, par interpolation
  entre les deux images. Le navigateur utilise la même interpolation entière pour
  son aperçu. Hors masque et transition, les pixels RGBA décodés de la source sont
  conservés exactement dans le PNG final. Sur les images transparentes, l’aperçu
  Canvas peut arrondir les couleurs lors de la prémultiplication alpha ; le calcul
  final est effectué directement depuis les originaux par Pillow.
- La douceur adoucit le bord du pinceau. Elle ne corrige pas une différence globale
  de netteté, de lumière ou un déplacement du décor entre les deux images : ces
  raccords restent à évaluer avec les essais de l’utilisateur.

Le module `krea2-retouch.js` possède ses propres Canvas et brouillons ; les
rafraîchissements de la liste des essais ne les reconstruisent pas. Peindre,
gommer, annuler, zoomer et déplacer ne déclenchent aucun appel serveur.
Pillow est injecté via le contrat applicatif `RetouchCompositor` ; le domaine
n’importe aucune bibliothèque d’image. Référence des opérations :
[Image.composite et resize](https://pillow.readthedocs.io/en/stable/reference/Image.html),
[ImageOps.exif_transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html).

## API et stockage

Les deux opérations utilisent le chemin :

`/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/retouch`

- **GET** prépare les images normalisées et renvoie `source_url`, `generated_url`, `harmonized_url`,
  `mask_url` (data URLs PNG, masque facultatif), `width`, `height`, `editable`,
  `label`, `harmonize`, `harmonize_strength`, `color_method` et les identifiants.
  Cette préparation ne crée pas d’assets ni d’essai.
- **POST** reçoit en multipart `mask`, `request_id`, `harmonize` (défaut false)
  et `harmonize_strength` (entier 0–100, défaut 100). Réponse 201 :
  `{source, attempt_id}`. Masque invalide : 422 ; ressource absente : 404 ; étape
  devenue immuable ou clé réutilisée avec un autre contenu : 409.

Le navigateur conserve la même clé et le même fichier pour réessayer après une
erreur ou une réponse trop lente. Le serveur vérifie la clé avant et après la
composition : une nouvelle tentative identique retrouve le candidat, y compris si
l’étape a été validée depuis. Une modification du masque ou de l’harmonisation
crée une nouvelle clé. Le serveur compare aussi activation et intensité pour
refuser une clé réutilisée avec d’autres réglages.
Un échec laisse le brouillon dans l’éditeur. Une validation concurrente de l’étape
empêche l’ajout tardif d’un candidat. La concurrence est sérialisée à l’enregistrement
dans le processus Lab habituel ; ce n’est pas un stockage distribué multi-serveurs.

Les fichiers `krea2_edits/<source_id>/source.json` sont écrits au **schéma 5**.
Les schémas 1–4 restent lisibles ; une tentative sans `kind` est une `generation`.
Les contrats de statut et d’identité ComfyUI des générations sont conservés.
Les anciennes retouches du schéma 5 sans champs d’harmonisation restent lisibles
avec l’option désactivée ; aucun résultat existant n’est recalculé au chargement.

Une tentative `retouch` a son propre `output_asset_id`, un statut `succeeded`, et
aucun `execution_id` ni hash de workflow compilé. Sa provenance contient :

- `original_attempt_id`, `parent_attempt_id` ;
- `source_asset_id`, `generated_asset_id`, `mask_asset_id` ;
- `width`, `height`, `version` ;
- `harmonize`, `harmonize_strength`, `color_method` (également dans le sidecar exporté) ;
- `request_id` et `submitted_mask_sha256`, empreinte du fichier reçu pour
  l’idempotence, distincte de l’empreinte du PNG gris normalisé stocké comme asset.

Prompt, modèle, LoRA et réglages sont hérités de la génération d’origine pour
permettre leur reprise. L’enregistrement d’une retouche ne remplace pas le prompt
ni la conversation courante. La mise en file ComfyUI d’une retouche est refusée
avant tout appel au moteur de rendu.

L’export d’une étape retouchée contient le composite, `source.*`, `generation.*`
et `mask.png`. Le manifeste donne leurs chemins explicites dans `retouch_files`.
Le sidecar distingue `image.compose.mask@1.0.0` de `image.edit`, indique les
dimensions réelles du composite et précise que les réglages de rendu sont hérités.

## Livraison et vérification à effectuer par l’utilisateur

Pillow `>=12.1.1,<13` est ajouté aux dépendances ; Pillow 12.3.0 a été installé dans
`D:\Code\panelforge\.venv` pendant l’implémentation. Les caches CSS, Edit et du
nouveau module portent la version `20260907.4`. Le défaut des checkpoints dans
`scripts/run_lab.py` est corrigé de `diffusion\_models` vers `diffusion_models`.

Tests préparés, **non exécutés par l’agent** :

- `tests/test_krea2_retouch.py` : masques vide/plein/partiel et alpha, bord doux,
  pixels protégés, dimensions/orientations, ratios invalides, stockage/réouverture,
  reprise sans accumulation, concurrence/idempotence, étape immuable, schémas 1–4,
  API, absence d’appel ComfyUI et choix exact du candidat pour feedback/export/suite.
  Extension couleurs : intensités 0/1/50/100, concordance de l’interpolation avec
  Canvas, alpha, persistance/réouverture sans accumulation, idempotence par réglages,
  anciennes retouches sans réglages et validation HTTP des intensités.
  Reprise d’étape : mémoire vide, archive, idempotence préservant les nouveaux
  échanges, protection des étapes parentes, opérations actives, panne de stockage
  et retouche en cours ; aucun appel externe réel.
- `tests/test_krea2_retouch_browser.py` : Canvas réels sur images synthétiques,
  pinceau/gomme, Annuler/Rétablir, vues communes, brouillon, erreur/reprise de sauvegarde
  et consultation immuable. Utilise Chromium local s’il est installé ; sinon ignoré.
  Extension : génération à gauche, affichage du masque, sélecteur source/image 2, curseur
  local, sauvegarde/reprise des couleurs et validation du candidat Après choisi.
  Reprise : confirmation, échec préservant les brouillons, nettoyage de l’étape
  concernée et gardes ; dessin/annulation sur les deux images avec masque partagé.

Commande ciblée, depuis le checkout actif, lorsque l’utilisateur le souhaite :

```powershell
$env:PYTHONPATH = 'D:\Code\localQ\.panelpatch\src'
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_krea2_retouch tests.test_krea2_retouch_browser tests.test_krea2_edit tests.test_krea2_edit_web tests.test_krea2_project_exports tests.test_run_lab_build
```

Contrôle manuel utile après son redémarrage/rechargement : retoucher un ancien
essai, revenir au comparateur sans enregistrer puis retrouver le brouillon,
enregistrer, rouvrir le masque, choisir un candidat qui n’est pas le dernier,
puis le valider et vérifier l’image de la frise et les fichiers exportés.

Aucun test, appel LLM, génération image/vidéo, annulation de rendu ni redémarrage
de service n’a été lancé par l’agent. L’incident de file Assisted écarté par
l’utilisateur et l’enchaînement vidéo restent hors de ce patch.
