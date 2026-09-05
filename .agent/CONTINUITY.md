# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - KREA2 Edit applique explicitement les défauts de rendu dès que le spec est chargé, puis les remplace par les métadonnées de la source ou les réglages du dernier essai. Une initialisation partielle n'est plus verrouillée comme réussie : rouvrir l'onglet relance le chargement, et des champs incomplets sont réhydratés sans écraser des réglages valides déjà saisis. Le dernier PNG audité conservait correctement checkpoint, ratio, mégapixels et seed ; le défaut était limité au cycle d'initialisation frontend. Cache `krea2-edit-lab.js?v=20260826.1`, 601 tests verts.
  - PanelForge ne configure plus vLLM. Le catalogue et le routage actifs comprennent uniquement le serveur distant et Unsloth Studio sous le namespace `local::`; aucune requête n'est envoyée au port 8000. Tous les sélecteurs affichent `Local · Unsloth`. Les anciens identifiants namespacés restent lisibles comme valeurs historiques indisponibles et ne sont jamais redirigés silencieusement vers Unsloth.
  - Image Lab exécute `character.change_view@0.2.0`; le moteur partagé fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - L’interface produit ne conserve que `Image Lab`, `H3 Base`, `Ref2V` et `Video Lab`. Storyboard, le Prompt Lab autonome et Archives ont été retirés avec leurs scripts, routes dédiées, recettes et tests verticaux. Le noyau de sessions/compositions reste partagé par H3 Base et Ref2V via `lab-core.js`. Les historiques présents sous `workspace` n’ont pas été supprimés ni migrés. Validation : 599 tests verts et compilation Python complète.
  - Ref2V réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.3` est le mono-plan robuste par défaut. Son writer ne reçoit que `camera_landmarks_ms`; PanelForge insère les clauses caméra depuis le Plan. La `0.3.2` reste le témoin historique à placeholders.
  - `minimax.h3.ref2v.direct.multishot@0.2.0` ajoute séparément 2 à 6 plans et leurs coupes franches, avec le même Brief, Plan et arbitrage ; la `0.1.0` à trois plans reste un témoin immuable.
  - Le sélecteur Ref2V sépare maintenant les recettes `Mono-plan standard`, `Multi-plan structuré` et `Multi-plan direct`. Cette dernière correspond au cookbook interne `minimax.h3.ref2v.direct.multishot.superfast@0.2.0` et impose un seul appel LLM direct : capsule Brief déterministe, images natives, mapping et liberté produisent immédiatement le corps H3. PanelForge ajoute seulement le header canonique, normalise les balises et auto-approuve le Prompt ; aucun Plan JSON n'est créé. La `0.1.0` Plan-first reste chargeable comme recette historique mais n'est pas proposée aux nouveaux runs.
  - Le Plan multi V2 dérive les IDs, coupes, durée et `camera_N` depuis l’ordre du tableau, structure la composition d’ouverture et le raccord spatial/motion de chaque plan, et avertit sur les répétitions exactes entre plans adjacents.
  - Le writer multi V2 reçoit une projection dynamique sans caméra ni placeholder ; PanelForge compile ensuite les champs `shot_1` à `shot_N`, les headings, les timestamps et les phrases caméra canoniques. Arbitrage et révision conservent le nombre de plans approuvé.
  - H3 Base utilise le nouveau profil/cookbook `minimax.h3.fl2va.direct@0.1.0` : intention avec zéro, une ou deux frames facultatives → Brief compact → Plan V2 arbitrable → prompt H3 compilé. La présence des rôles first/last dérive T2VA, I2VA, L2VA ou FL2VA ; le writer ne reçoit ni le Brief complet, ni le header, ni la caméra.
  - H3 Base préfère désormais le profil/cookbook versionné `minimax.h3.fl2va.direct@0.2.0`. Le parcours reste exactement Brief → Plan → Prompt, soit trois appels LLM. PanelForge extrait sans LLM les citations explicites de l’intention, les injecte comme ledger immuable dans le Brief et le Plan, restaure texte/métadonnées/timing manquants avec warnings, puis compile une phrase de parole H3 naturelle avec ID stable et balise `<d>[Language] ...</d>`. Le writer reçoit une projection compacte, sans Brief dupliqué ni métadonnées de schéma inutiles.
  - Dans H3 Base `0.2.0`, les chevauchements caméra à départs distincts deviennent des relais séquentiels sans supprimer de mouvement ; un départ identique reste ambigu et bloquant. Le compilateur ajoute aussi le jalon final dérivé lorsqu’un writer l’oublie. Les recettes/profils `0.1.0` restent immuables et relisibles.
  - Les anciens `minimax.h3.i2v.direct@0.1.0` et `0.2.0` restent immuables et relisibles. Repartir d’un ancien run crée une session H3 Base propre avec les mêmes assets et de nouveaux IDs.
  - Pour I2V `0.2.0` et Ref2V mono `0.3.3`, le contexte persiste directive et horaire, le writer ne voit aucun mouvement/placeholder, et génération, édition ou révision réinsèrent déterministiquement la phrase canonique au bon jalon.
  - Les recettes restent sélectionnables par `id@version` avant le Plan puis verrouillées dans la composition; le multi-plan dérive headings, coupes, durée et caméra sans horloge redondante du LLM.
  - Ref2V conserve la recette sélectionnée après `Nouveau`, avertit sans bloquer si une intention multi-plan utilise le mono-plan et exige une confirmation explicite du mapping des rôles, invalidée à chaque modification.
  - L’aide `?` des références Ref2V résume dans un tableau compact et accessible le canal contrôlé par chacun des huit rôles d’image.
  - I2V et Ref2V proposent un Mode rapide partagé qui génère puis approuve Brief, Plan et Prompt sans nouvelle recette ni appel LLM ; il ignore les warnings et recommandations, s’arrête sur toute erreur bloquante et reprend sans rejouer les étapes déjà validées. Dans Ref2V, l’orchestration ne propose plus que `Supervisé` et `Rapide` ; la rédaction directe en un appel appartient à la recette multi-plan directe et masque ce contrôle.
  - I2V et Ref2V peuvent afficher en direct, sur option explicite, la trace séparée transmise par le modèle. Cette trace de debug reste éphémère, n’est jamais concaténée au document ni au journal, et n’est pas simulée lorsque le modèle n’en fournit pas.
  - I2V et Ref2V Direct remplacent le curseur de liberté créative par cinq modes discrets alignés sur les politiques backend. Le contrôle précise que son effet direct s’arrête au Brief, restaure exactement toute ancienne valeur numérique hors preset et reste aligné dans les colonnes étroites.
  - Les archives neutralisent création et écritures mais laissent ouvrir et copier tout prompt actif, même non approuvé ou obsolète ; leurs listes chargent jusqu’à 200 sessions avant filtrage.
  - H3 Base et Ref2V peuvent créer une session propre depuis une session existante en réutilisant ses assets validés, avec de nouveaux IDs et sans recopier Brief, approbations ni composition.
  - I2V et Ref2V permettent de préparer ce nouveau parcours depuis un run récent en changeant modèle, recette, intention, liberté ou Mode rapide. Les actions combinées proposent/appliquent puis approuvent sans franchir une erreur, l’étape suivante s’ouvre avec défilement, et le prompt expose les noms complets des images à copier.
  - `Nouveau parcours` est disponible dans la barre supérieure à côté de la libération VRAM ; les ouvertures de runs et les chaînes combinées sont protégées contre les réponses asynchrones obsolètes.
  - Les nouveaux parcours préfèrent automatiquement un modèle dont l’identifiant contient `Qwen3.8-27B`, avec repli sur Qwen 3.6 puis sur le premier modèle exposé.
  - Le transport ComfyUI expose maintenant queue/statut normalisés, annulation ciblée via Jobs API avec fallback legacy prudent, et URL WebSocket client-scoped. La preview Video Lab passe par un relais WebSocket PanelForge same-origin qui transmet les événements texte/binaires et évite le rejet CORS du navigateur.
  - Audit runtime du 20/08 : ComfyUI `0.33.2` expose nativement `GET /system_stats` et `POST /free`. Sur la RTX PRO 6000, `system_stats` fournit VRAM totale/libre globale et compteurs PyTorch Comfy, sans attribution fiable par processus ; `/free` accepte `unload_models` et `free_memory`. L’extension installée `ComfyUI-Crystools` diffuse déjà utilisation GPU, VRAM et température via l’événement WebSocket `crystools.monitor`.
  - La topbar interroge à 1 Hz la VRAM GPU globale, la file ComfyUI et les modèles llama.swap, avec une température Crystools transmise par relais WebSocket same-origin. Les pannes restent partielles et non bloquantes, les nettoyages LLM/Comfy sont séparés et le nettoyage Comfy refuse toute file active. Dans H3 Base/Ref2V, `Repartir de ce run` est placé à côté de `Nouveau run` et la trace modèle se déplace juste au-dessus de l’étape active.
  - Le bandeau runtime ne montre plus l’utilisation GPU. Il regroupe deux jauges compactes : VRAM globale verte jusqu’à 30 % puis jaune, et température ramenée sur une échelle 25–100 °C (verte jusqu’à 60, orange jusqu’à 80, rouge au-delà). Les services sains n’occupent plus de pastille ; seuls les services indisponibles affichent une alerte. Les actions de parcours et de maintenance sont séparées visuellement, dans l’ordre `VRAM LLM`, puis `VRAM Comfy`. Validation complète : 642 tests verts.
  - Le Video Lab exécute la recette immuable expérimentale `video.generate.ref2v/minimax-h3-ref2v@0.1.0` avec une à trois références ordonnées, prompt, ratio, mégapixels, durée, steps et seed. Il compile les slots réellement utilisés, conserve un historique séparé et limite l'exécution à un rendu actif.
  - Sa preview live consomme les événements KJ JPEG/WebP/MP4 sur un client WebSocket ComfyUI isolé ; l'interface distingue connexion, disponibilité et erreur du relais sans interrompre le rendu. La vidéo MP4 finale avec audio est importée comme asset. Une annulation cible le job exact et reste en `cancel_pending` si ComfyUI ne confirme pas l'arrêt.
  - Les assets vidéo acceptent les requêtes HTTP Range nécessaires au lecteur natif. La sortie finale conserve uniquement le lecteur vidéo HTML standard, sans bouton, avertissement ni diagnostic audio supplémentaire ; chaque nouvel asset reste chargé via une URL anti-cache stable.
  - Après un redémarrage de PanelForge, la lecture, l'annulation ou la réservation du slot réconcilie un run ComfyUI détaché : une sortie déjà terminée est importée, une erreur devient terminale et un job encore actif reste suivi par le polling UI.
  - Ref2V peut préremplir Video Lab avec ses images ordonnées, le prompt actuellement visible et la durée dérivée du Plan, sans lancer automatiquement le rendu.
  - Image Lab exécute désormais la recette immuable `image.generate.t2i/krea2@0.1.0` : prompt, modèle KREA2 installé, ratio, 0,5–4 MP et seed alimentent un workflow T2I nettoyé. Le modèle GPT KREA2 fourni est sélectionné par défaut, tandis que sampler, scheduler, CFG, steps, VAE et CLIP restent verrouillés par la recette.
  - Image Lab propose aussi le batch de recettes `image.generate.batch/krea2-community@0.2.0` : six familles visuelles versionnées, un seul appel LLM pour 1 à 10 prompts variés, puis rendus KREA2 séquentiels, galerie, votes/commentaires et révision facultative validée humainement. Les réglages communautaires ER SDE/simple, CFG, deux passes et upscale latent restent fixes. Chaque PNG est désormais écrit par `SaveImageKJ` avec un sidecar `.txt` de même stem et dans le même dossier ComfyUI ; ce JSON UTF-8 contient le prompt exact, la variation, la provenance, le modèle LLM, le checkpoint, le ratio, les mégapixels, la seed, les LoRA effectives et le sampling. Le workflow `0.1.0` reste immuable et chargeable. Validation complète : 678 tests verts.
  - Le catalogue batch scanne uniquement les racines KREA2 configurées pour les checkpoints et LoRA. Les modèles sont classés Favoris BF16/Favoris INT8/BF16/INT8 selon favoris et taille (>16 Gio = BF16), les LoRA en Favoris/SFW/NSFW/non classées, avec quatre slots ordonnables. Les fiches et mises à jour CivitAI/CivitAI Red sont vérifiées manuellement et restent informatives ; ressources absentes ou renommées produisent des warnings non destructifs.
  - Les changements de checkpoint, ratio, mégapixels ou pile LoRA créent une révision technique immuable de la recette et réutilisent une révision identique déjà existante. Le ratio choisi remplace uniquement la déclaration de format du squelette fixe et devient le ratio contrôlé dans chaque prompt. Le carillon du batch retentit après les sorties finales, pas après la seule génération des prompts. Validation complète : 674 tests verts.
  - L’inventaire des UNET est découvert dynamiquement via ComfyUI et recoupé avec l’allowlist qualifiée ; la chaîne exacte annoncée par le serveur est conservée. KREA2 fournit PNG final, historique, relance et annulation, sans preview ni LoRA en V1.
  - La sortie PNG KREA2 conserve maintenant son ratio naturel dans un cadre plafonné à 760 × 600 px environ, sans étirement à toute la largeur ou hauteur de la zone de résultat.
  - La grille KREA2 borne aussi ses largeurs intrinsèques : les longs noms de checkpoints sont tronqués dans le sélecteur, peuvent se replier dans les métadonnées et les prompts des cartes d’historique restent ellipsés sans provoquer de défilement horizontal de la page.
  - Les Plans Direct mono réparent désormais silencieusement les actions parallèles dont les intervalles se chevauchent et couvrent leur beat sans trou : chaque groupe connecté est fusionné en un seul step composite avec ses timings internes, les frontières déjà séquentielles restent intactes et aucun step artificiel n’est créé. Les trous, bornes hors beat et formes ambiguës restent bloquants.
  - H3 Base rend une durée explicite dans l’intention autoritaire sur le total vidéo, hold inclus, sans retimer les actions : le hold seul est recalculé et une timeline d’action déjà trop longue reste bloquée. Le writer distingue maintenant `final_state_start_ms` du dernier ancrage `duration_ms`, les noms locaux de fichiers sont retirés des entrées LLM et interdits dans le prompt final, et les diagnostics propres à ce parcours utilisent « H3 Base » plutôt que l’ancien nom Direct I2VA.
  - L’extraction de durée H3 Base privilégie désormais une consigne totale explicite (`plan de N secondes`, `durée : N secondes`) sur les durées incidentes présentes dans un ancien prompt collé comme contre-exemple. Deux consignes explicites réellement incompatibles restent bloquantes.
  - Validation locale : 654 tests passent, dont le parcours H3 Base `0.2.0` complet en exactement trois appels, citations omises/paraphrasées/mal formées, placement temporel compiler-owned, relais caméra, jalon final, édition/révision et chargement legacy `0.1.0`.
  - Image Lab borne maintenant les noms longs de checkpoints, les pastilles de métadonnées et les entrées de l’historique KREA2 ; ils ne peuvent plus élargir la grille ni créer un défilement horizontal de page. Le cache CSS a été incrémenté et 23 tests UI/Web ciblés passent.
  - Les listes `Parcours récents` de H3 Base et Ref2V affichent jusqu’à trois petites miniatures superposées à droite, dans la largeur et la hauteur compactes existantes. Les images utilisent les assets déjà sérialisés, se chargent paresseusement et disparaissent proprement en cas d’échec ; les parcours T2VA sans image gardent la carte texte originale. Validation ciblée : 45 tests UI/Web verts.
  - H3 Base `0.2.0` distingue maintenant les placeholders temporaires `[[dialogue:dialogue_N]]` des anciens placeholders caméra pendant la compilation intermédiaire, puis exige toujours leur disparition avant le lint final. Les sorties compactes `field:value` sans espace sont normalisées sur les trois champs H3. Les candidats réels Gemma, Qwen 3.6 et Qwen 3.8 se recompilent chacun avec deux balises `<d>`, toutes leurs caméras et aucun placeholder ; 656 tests passent.
  - Le batch KREA2 génère désormais des seeds compatibles avec la borne réelle du nœud `Seed (rgthree)` (`0..2^50`) et le compilateur refuse toute valeur supérieure avant soumission. Les erreurs HTTP ComfyUI conservent leur diagnostic structuré par nœud ; un batch dont tous les items échouent devient `failed`, tandis qu’un succès partiel reste `completed` avec warning. Les anciens batches 64 bits restent lisibles. Validation : 677 tests verts, dont 81 tests KREA2 ciblés.
  - `SaveImageKJ` écrit correctement PNG et TXT mais la version installée laisse `outputs` vide dans l’historique ComfyUI. L’adaptateur batch dérive donc le PNG depuis le `filename_prefix` immuable conservé dans le snapshot du prompt, sans sonder le disque distant. Les anciens batches ayant échoué uniquement à l’import sont réconciliés à la lecture ; le batch réel `krea2-batch-6d54b3804d5a494cb3ab990c483f6e61` a ainsi récupéré ses 5/5 assets sans nouveau rendu. Validation complète : 680 tests verts.
  - Image Lab intègre maintenant KREA2 Edit avec la recette immuable `image.edit/krea2.identity_edit@0.1.0`. Les sorties Batch réussies alimentent automatiquement un backlog complété par import PNG/JPEG/WebP ; sidecar puis métadonnées PNG restaurent prompt, checkpoint, ratio, mégapixels, seed et quatre LoRA générales en best effort. Un seul appel multimodal reconstruit ou réécrit le prompt selon l’instruction, avec trace optionnelle et contenu adulte permis uniquement pour des sujets clairement adultes ; les essais suivants ne rappellent pas le LLM.
  - KREA2 Edit expose checkpoint, quatre LoRA générales, ratio, mégapixels, seed, `ref_boost` et steps, tout en verrouillant la LoRA technique d’identité et le stack qualifié. Les sorties, workflows et sidecars sont persistés ; une source peut être marquée traitée ou masquée sans suppression. Les exécutions détachées et annulations `already_finished` sont réconciliées pour importer un PNG tardif plutôt que le perdre. Validation complète : 690 tests verts.
  - Dans KREA2 Edit, le formulaire et les actions précèdent désormais les deux images afin de rester stables pendant les itérations. Source et dernier résultat sont placés en bas ; leur scène n’impose plus de hauteur carrée et les images conservent leur ratio naturel, avec un plafond à 75 % du viewport qui affiche entièrement les portraits 9:16. Les boutons « Préparer le prompt » et « Lancer un rendu » possèdent un contraste vert explicite. Le cache CSS est versionné `20260821.5`.
  - KREA2 Batch et KREA2 Edit utilisent désormais le même composant de listes de ressources : checkpoints ordonnés en Favoris BF16/Favoris INT8/BF16/INT8 et LoRA en Favoris/SFW/NSFW/Non classés. Les catégories restent dérivées du catalogue partagé et une ressource historique absente conserve son option d’avertissement. Validation ciblée : 34 tests KREA2/Web/UI verts.
  - KREA2 Edit est désormais organisé par projets et étapes. Dans une étape, le prompt édité est l’état autoritaire, chaque nouvelle instruction crée une révision persistante et un essai réussi sélectionné est envoyé au LLM comme `GENERATED FEEDBACK`, tandis que ComfyUI repart toujours de la `STAGE SOURCE` immuable. `Valider et continuer` est la seule action qui promeut un résultat en source de l’étape suivante ; backlog, chronologie, révisions, essais et résultat accepté restent groupés sous le projet original. Les cartes d’essai affichent le `Ref boost` en priorité, puis les mégapixels et les steps, sans seed dans cet aperçu compact. À partir de l’étape 2, une préférence locale facultative ajoute l’image initiale du projet à gauche de la source courante et du feedback ; elle reste masquée à l’étape 1 et la grille devient verticale sur mobile. La fin du polling sélectionne puis affiche maintenant immédiatement le nouveau rendu sans attendre une action UI. Les trois vues principales et les miniatures d’essai ouvrent au clic une modale scrollable qui conserve les dimensions naturelles du fichier ; Entrée/Espace et Échap sont utilisables. Les historiques schema V1 sont lus comme projets à une étape sans réécriture destructive. Validation complète : 693 tests verts ; 30 tests UI/Web ciblés verts après ces mini-patches.
  - KREA2 Edit exporte maintenant une copie humaine de l’image originale et de chaque résultat explicitement validé sous `D:\AI\PanelForge\KREA2 Projects` par défaut. Projet et étapes reçoivent des noms lisibles, chaque image possède un sidecar prompt/réglages et `project.json` décrit la chaîne ; les essais rejetés restent dans le stockage technique. La racine est configurable par CLI ou environnement, une panne affiche un warning réessayable sans annuler la validation, et aucun dossier externe n’est créé avant la première validation. Validation complète : 695 tests verts.
  - Le catalogue partagé KREA2 utilise maintenant par défaut les chemins UNC SSHFS `\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion\_models\Krea2` et `\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2`, indépendants de la visibilité du lecteur mappé `Y:`. Il fusionne le scan local avec les ressources `KREA2/` exposées dynamiquement par ComfyUI ; si le partage reste absent, checkpoints et LoRA restent sélectionnables avec précision/métadonnées inconnues et warning non bloquant. Les anciennes options historiques indisponibles ne s’accumulent plus dans le sélecteur Edit.
  - L’export humain KREA2 Edit borne désormais les slugs du projet et des étapes, ne répète plus le nom du projet dans chaque fichier et utilise un nom temporaire court. Le cas réel du tigre échouait sur la limite de chemin Windows pendant l’écriture atomique, après une validation métier pourtant réussie ; une reproduction avec des libellés encore plus longs est maintenant couverte. Dans H3 Base, les noms de frames très longs sont tronqués visuellement avec ellipsis et restent disponibles intégralement au survol, sans réduire la largeur de la vignette. Validation complète : 699 tests verts.
  - KREA2 Batch et KREA2 Edit exposent maintenant le même gestionnaire repliable de catalogue. Les checkpoints ambigus peuvent recevoir une précision manuelle BF16/INT8 et les LoRA peuvent être déplacées ou sélectionnées entre Favoris/SFW/NSFW/Non classés ; l’état reste persisté dans `workspace/krea2_resources.json`. Sans accès local, les marqueurs de nom non ambigus BF16/INT8/INT4/FP8 fournissent un premier classement et les autres ressources restent honnêtement inconnues. Validation complète : 700 tests verts.
  - Image Lab propose désormais `Création assistée`, un projet conversationnel KREA2 distinct d’Edit : intention et référence facultative alimentent le LLM multimodal, mais seule la sortie texte est envoyée au workflow T2I Batch. Chaque tour fournit un prompt KREA2 immédiatement utilisable et des questions d’affinage ; un rendu sélectionné revient au tour suivant avec son image, son prompt exact et ses réglages. Checkpoint, ratio, mégapixels, seed et quatre LoRA restent modifiables entre les essais, regroupés par le catalogue partagé. La galerie reste sous les contrôles, les projets/échanges/essais sont persistés et l’annulation/réconciliation réutilisent les mécanismes ComfyUI existants.
  - Une création sélectionnée peut être copiée explicitement sous `D:\AI\PanelForge\KREA2 Creations` avec PNG, sidecar et manifeste projet. Le mode `Concevoir la recette` entretient une discussion séparée, un brouillon structuré modifiable et une publication explicite en recette immuable `0.1.0` directement compatible avec le catalogue Batch ; aucune conversation ni aucun essai ne modifie la mémoire globale avant cette publication. Validation complète : 705 tests verts.
  - Les cinq bandeaux de sous-vues Image Lab conservent désormais le même ordre lors de la navigation. Le badge `character.change_view · v0.2.0` a quitté la topbar globale et remplace l’ancien libellé expérimental dans le panneau vertical de Changer la vue. Dans les barres d’action, un bouton explicitement primaire conserve maintenant son fond vert et son texte blanc ; cela corrige notamment `Lancer un rendu` dans Création assistée. Le cache CSS est versionné `20260822.3`. Validation ciblée : 34 tests UI/Web verts.
  - La galerie Création assistée affiche maintenant les essais du plus récent au plus ancien, tout en gardant l’éventuelle référence LLM en tête. L’import KREA2 Edit sait désormais récupérer les LoRA du nœud plat rgthree `Lora Loader Stack` utilisé par Batch/Création assistée, en plus de l’ancien `Power Lora Loader`. Sur le PNG réel du dernier tigre, il restaure `realism_engine` à 1,0 et `Detailer-KREA2` à 2,0. Le cache JS assisté est versionné `20260822.2` et 21 tests KREA2 ciblés passent.
  - L’import manuel KREA2 Edit force désormais l’hydratation complète du nouveau projet même pendant le verrou UI de l’upload. Auparavant, `openSource` refusait cet appel interne et pouvait laisser visibles le prompt, le checkpoint, la seed et les LoRA du formulaire précédent ; les paramètres réellement présents dans la nouvelle image n’étaient affichés qu’après une réouverture. Une liste LoRA vide dans les métadonnées efface maintenant correctement les anciens slots. Le cache JS Edit est versionné `20260822.2` et 38 tests ciblés passent.
  - `Valider et continuer` dans KREA2 Edit accepte désormais les instructions longues comme libellé automatique : espaces et retours ligne sont normalisés puis le nom humain est borné à 120 caractères, sans modifier l’instruction ni le prompt. Le même garde couvre les noms de fichiers longs, côté interface et côté serveur, y compris avec un ancien JS encore en cache. Le projet réel `krea2-edit-d4269b6b4dab4df986c12dad22d200fc` passe en étape 2 dans une copie de diagnostic, avec export valide. Le cache JS Edit est versionné `20260822.3` et les 111 tests KREA2 passent.
  - La zone de travail KREA2 Edit est compactée sans changer son flux : le prompt éditable est replié par défaut et n’occupe que quatre lignes lorsqu’il est ouvert, les quatre LoRA sont disposées en grille 2×2 avec contrôles plus bas, et le gestionnaire de catalogue fermé utilise un bandeau aminci. Le message d’état vide ne réserve plus de hauteur ; les quatre boutons d’action font 31 px, restent sur une ligne et le rendu principal utilise seulement l’espace restant. Les paramètres checkpoint/ratio/MP puis ref boost/steps/seed restent inchangés ; sous 620 px, les LoRA reviennent sur une colonne et les actions se replient proprement. Le cache CSS courant est `20260822.8`.
  - Création assistée reprend la grille LoRA compacte 2×2 et les contrôles bas de KREA2 Edit, avec repli en une colonne sous 620 px. Ses quatre emplacements sont désormais fixes : poignée, état et événements de glisser-déposer ont été retirés, tandis que Batch conserve son réordonnancement propre. Les caches CSS/JS courants sont `20260822.8`/`20260822.3`.
  - L’évolution d’une recette Batch est désormais un atelier itératif persistant. La recette publiée source reste immuable ; chaque échange LLM produit une candidate D1/D2… éditable, accompagnée d’une réponse et de questions. La candidate conserve aussi checkpoint, ratio, mégapixels et pile LoRA. Elle peut être sauvegardée sans publication ou testée sur 1 à 10 images via un batch privé lié à l’atelier ; likes, dislikes et commentaires de la source et de tous les tests alimentent l’échange suivant. Chaque batch test embarque un snapshot de recette vérifié par hash, donc reste relançable après redémarrage sans version temporaire dans le catalogue. Seul `Publier la nouvelle version` crée la révision patch immuable suivante, et une double publication est refusée. L’interface reste dans la page Batch, marque les tests dans l’historique et réutilise les réglages du panneau gauche. Validation complète : 712 tests verts ; caches CSS/Batch JS `20260822.8`/`20260822.2`.
  - Le sélecteur de modèles H3 Base ne dépend plus d’un unique appel précoce au chargement global. L’initialisation des modèles et des parcours est maintenant indépendante, une panne llama.swap affiche un état explicite sans bloquer le reste, les réponses concurrentes obsolètes sont ignorées et chaque ouverture de l’onglet H3 Base relance automatiquement la découverte. Un test navigateur réel a simulé une première panne puis confirmé la reprise de 30 modèles avec Qwen 3.8 présélectionné ; 26 tests UI/Web/build ciblés passent. Cache H3 Base : `i2v-direct.js?v=20260822.1`.
  - Le catalogue KREA2 ne remonte plus une fausse alerte globale lorsque les racines UNC locales sont inaccessibles mais que ComfyUI fournit bien les checkpoints ou LoRA correspondants. Les avertissements de métadonnées restent attachés aux ressources distantes, et le bandeau revient si aucune ressource de la catégorie n'est disponible. Validation : 115 tests KREA2 verts.
  - Création assistée réactive désormais toutes les actions après ouverture d'un projet persistant depuis `Projets récents`. L'ouverture possède un verrou de chargement avec nettoyage garanti en succès comme en erreur ; auparavant, le projet était hydraté mais les boutons conservaient l'état désactivé de l'initialisation sans projet. Cache JS : `20260823.1` ; validation : 116 tests KREA2 verts.
  - Les cartes d'essais de Création assistée affichent désormais un résumé compact et reproductible : checkpoint abrégé, résolution réelle en pixels, mégapixels, ratio, seed, puis toutes les LoRA effectives avec leur force. Les noms complets restent disponibles au survol. Le dernier projet réel expose bien `688×1224`, 0,8 MP et ses deux LoRA à 1 ; cache JS `20260823.2`, validation : 117 tests KREA2 verts.
  - Les essais de Création assistée regroupent désormais leurs trois actions sur une ligne : `Reprendre réglages`, `Feedback` et `Enregistrer`. Le bouton Feedback est un vrai toggle persistant, affiche `Feedback ✓` lorsqu'il est actif et retire la sélection au second clic en envoyant explicitement `null` au backend. Les états déjà enregistrés utilisent aussi un libellé court. Caches CSS/JS : `20260823.1`/`20260823.3` ; validation : 118 tests KREA2 et 39 tests UI/Web ciblés verts.
  - Création assistée propose maintenant, au niveau des actions de discussion, une langue de prompt `English`/`中文`. Le premier échange et les projets historiques restent en anglais ; le choix peut changer à chaque itération, persiste par projet et suit le `canonical_prompt` jusque dans une recette Batch publiée. Message et questions restent en français. Les contrats LLM préservent triggers LoRA, noms propres, noms de fichiers et textes littéraux sans dupliquer le prompt en deux langues ; la validation de longueur tient compte de la densité du chinois. Caches CSS/JS : `20260823.2`/`20260823.4`. Validation complète : 719 tests verts, dont 121 tests KREA2.
  - `Modifier avec KREA2` expose à son tour `English`/`中文` près du modèle LLM. Le choix est enregistré avec le projet et chaque révision, transmis à l’étape suivante lors de `Valider et continuer`, inscrit dans les sidecars techniques et les exports humains ; les projets historiques restent en anglais. Le writer multimodal impose une sortie monolingue tout en préservant les triggers LoRA, noms propres, fichiers et textes littéraux, et applique un seuil de densité adapté au chinois. Dans Batch, la langue publiée reste visible mais non modifiable pendant un lancement ordinaire ; seul l’atelier versionné peut convertir la candidate, puis propage ce choix aux tests D1/D2 et à la recette publiée. Caches CSS/Edit/Batch JS : `20260823.3`/`20260823.1`/`20260823.1`.
  - Chaque message de Création assistée peut maintenant recevoir une image d’appoint PNG/JPEG/WebP distincte de la référence permanente et du rendu sélectionné. L’interface compacte montre la miniature avant envoi, permet de la retirer, l’enregistre dans la bulle utilisateur et propose `Réutiliser` plus tard. Le backend la transmet sous le rôle multimodal `TURN GUIDANCE IMAGE` uniquement à l’appel courant, avec une consigne empêchant de remplacer implicitement `REFERENCE IMAGE` ou `GENERATED RESULT`; les tours suivants conservent seulement son nom dans l’historique textuel. Les anciens projets sans ces champs restent lisibles. Limite : une image par message, 25 Mio. Caches CSS/JS : `20260823.4`/`20260823.5`. Validation complète : 722 tests verts.
  - H3 Base propose maintenant la recette séparée `minimax.h3.fl2va.direct.multishot@0.1.0` sans modifier le mono-plan `0.2.0`, qui reste le choix par défaut. Le parcours conserve exactement Brief → Plan → Prompt et les modes Supervisé/Rapide existants. Son Plan choisit 2 à 4 plans au nombre minimal utile ; PanelForge dérive et compile les headings `[Shot N]`, coupes horodatées, une caméra canonique optionnelle par plan, l’état final, les dialogues exacts et le rattachement first-frame au plan 1 / last-frame au dernier plan en T2VA, I2VA, L2VA ou FL2VA. Les variations légères d’angle restent des mouvements de caméra et la V1 refuse de couper une réplique. L’interface sélectionne les recettes par `id@version`, recharge correctement un parcours multi-plan sans Plan et conserve le mono-plan par défaut. Cache H3 Base : `20260823.1`. Validation complète : 727 tests verts.
  - Le mono H3 Base par défaut passe à `minimax.h3.fl2va.direct@0.3.0` sans modifier les runs 0.1/0.2. Le Brief doit expliciter la fin du mouvement principal ; le Plan typé choisit `continue_motion`, `natural_settle` ou `intentional_hold`. Pour un mouvement continu, PanelForge absorbe un hold terminal dans le dernier step sans en créer, projette la simultanéité des effets au writer et compile lui-même une dernière phrase en mouvement. Les dialogues exacts et caméras compiler-owned de 0.2 restent actifs ; 733 tests passent.
  - Le sélecteur H3 Base affiche de nouveau la version de chaque recette mono-plan et multi-plan dans son libellé ; les versions 0.1.0, 0.2.0 et 0.3.0 ne sont plus visuellement confondues. Cache H3 Base `20260823.3` ; 24 tests Web ciblés passent.
  - PanelForge agrège désormais llama.swap et un Unsloth Studio local dans un routeur LLM générique. Les IDs serveur historiques restent inchangés ; les modèles locaux découverts via `/v1/models` sont persistés sous `local::...`, puis dénamespacés uniquement au transport. Les neuf sélecteurs LLM proposent `Local · Unsloth`, restaurent la provenance d'un ancien run et la panne d'une source ne masque pas l'autre catalogue. Configuration : `PANELFORGE_LOCAL_LLM_URL` (défaut `http://127.0.0.1:8888/v1`) et `PANELFORGE_LOCAL_LLM_API_KEY`. Le bouton VRAM LLM reste volontairement réservé à llama.swap. Validation : 81 tests ciblés et 741 tests complets verts.
  - H3 Base propose désormais la recette immuable `minimax.h3.base.animal-interview@0.1.0`. Son formulaire compact recueille animal, décor, langue FR/EN, durée, script partiel et action finale ; le Brief est le seul appel autorisé à compléter les répliques manquantes et verrouille les citations fournies. Le Plan impose l'alternance S1 intervieweuse / S2 animal, des steps de parole et pauses séparés, la propriété de bouche et une action terminale continue. Le writer ne reçoit aucun texte parlé : PanelForge remplace chaque placeholder à sa position narrative par un intervalle `From…to…`, retire les échos exacts et compile le header/caméra selon T2VA, I2VA, L2VA ou FL2VA. L'intervieweuse est par défaut partiellement visible et floue en profil sur le bord gauche, sauf autorité contraire des frames. Les parcours se rouvrent avec leurs champs structurés. Validation complète : 752 tests verts.
  - L'extracteur de citations distingue désormais les préfixes de locuteur (`S1: "…"`, `S1 Interviewer: "…"`) des véritables paires JSON (`"clé": "valeur"`). Le script source et le candidat réel du run animal de 13:10 restituent chacun les quatre répliques exactes et le Brief complet repasse sa validation sans modification.
  - Le compilateur H3 Base multi-plan normalise désormais uniquement ses champs déterministes issus du Plan (`opening_composition`, état final et cible caméra) vers les labels officiels du mode : `<Picture 1>` en I2VA/L2VA, `Picture 1`/`Picture 2` en FL2VA. Le Plan approuvé et les dialogues restent intacts, le header est validé séparément et les répétitions canoniques sont autorisées dans le corps conformément au guide H3. Le cas FL2VA du run `prompt-fac334f74ea4445aba616505bdd4302a` est couvert de bout en bout.
  - H3 Base et Ref2V remplacent le réglage global de créativité par trois axes indépendants `vie de la scène`, `caméra` et `mouvements additionnels`, chacun de 0 à 3. Ce sont des permissions, jamais des quotas ; le Brief ne les emploie que pour combler une scène trop vide ou trop lente. Les nouveaux runs démarrent à 0/0/0, les anciens niveaux globaux sont projetés sans réécriture, la persistance passe au schéma 6 et aucun appel LLM supplémentaire n'est ajouté. Validation complète : 757 tests verts.
  - La recette interview animal possède désormais une version `0.2.0` dédiée à la voix juvénile, sans modifier la `0.1.0`. Le Plan sépare émotion et identité vocale ; le compilateur impose à la première réponse S2 une voix très jeune et enfantine, petite, légère, nettement aiguë, naturelle et intelligible, puis rappelle la même identité aux réponses suivantes. Cette formulation suit le guide H3 qui recommande de fixer âge vocal, hauteur, timbre et débit à la première apparition d'un locuteur. Dans le formulaire, Animal et Environnement occupent chacun toute la largeur ; langue et durée restent côte à côte. Validation complète : 758 tests verts.
  - Le catalogue Unsloth local a été confirmé disponible après achèvement du chargement du modèle et rafraîchissement de l'interface, même avec llama.swap distant éteint. L'absence momentanée venait donc de l'ordre de démarrage/découverte, pas d'une dépendance entre les deux sources.
  - Le lancement isolé de `D:\Code\localQ\.panelpatch\scripts\run_lab.py` sur le port 7861 a confirmé le runtime de la branche `cleanup-orphan-labs` et le Prompt H3 Base a été généré correctement. Le rejet précédent provenait vraisemblablement du brouillon d'un ancien run ou d'une ancienne instance sur 7860. Le warning Git `dubious ownership` concerne uniquement les commandes Git sur le worktree créé par `CodexSandboxOffline` et n'empêche pas Python de lancer PanelForge.
  - Le workflow H3 Render `minimax-h3-latent-speed@0.1.1` porte la lecture de la preview animée `ModelPreviewOverrideKJ` de 12 à 24 fps, sans modifier les 24 fps de la vidéo finale ni la version historique `0.1.0`. Le manifeste et le workflow exposent la même valeur, le runtime charge la nouvelle version et les 599 tests passent.
- Broken / missing:
  - Audit des reglages Unsloth : le gateway OpenAI-compatible envoie seulement `model`, `messages`, `temperature`, `stream` et, selon l'etape, `max_tokens`. Il fixe un timeout de 300 s et desactive les retries du SDK. `top_p`, `top_k`, `min_p`, penalites, seed, schema JSON, `reasoning_effort`, `enable_thinking`, MTP/speculative decoding, contexte et pretraitement des images restent aux valeurs du serveur. Le dernier chat KREA2 utilisait `temperature=0.35`, `max_tokens=16384`, `stream=true` et deux PNG encodes en data URL.
  - Le projet Creation assistee KREA2 `krea2-create-d95a4c1f39da4ecc9c2e1e46b16f8b28` confirme le defaut MTMD intermittent avec `local::unsloth/Qwen3.8-27B-GGUF` : plusieurs tours utilisateur identiques ont ete persistes pendant les echecs, puis le meme contexte multimodal a reussi. Ce n'est ni Spectrum, ni le workflow H3/LoRA, ni un rejet permanent du prompt ; la mitigation applicative reste un retry borne MTMD et une persistance transactionnelle du tour.
  - L'arrêt de PanelForge peut rester sur `Shutting down` lorsqu'une requête longue lancée via FastAPI `BackgroundTasks` est encore suivie (rendu ComfyUI, batch ou édition, avec timeout applicatif pouvant atteindre 3600 s). Le polling navigateur `/api/runtime/status` peut encore laisser apparaître une dernière requête mais n'est pas la cause racine. Uvicorn 0.52.1 attend par défaut indéfiniment ses connexions/tâches ; un second `Ctrl+C` positionne son `force_exit`. Aucun listener 7860/7861 ni essai H3 actif ne subsistait lors de l'audit. Une correction durable devra borner l'arrêt gracieux ou détacher coopérativement les workers longs sans annuler implicitement les jobs ComfyUI.
  - Audit `Music OFF` du projet H3 Render `h3-render-c3fd4f9d57834f398e188f30c9b2021b` : les trois essais persistent `music_enabled=false`, leur `effective_prompt` finit par `non_diegetic_music: N/A` et le workflow compilé transmet exactement cette valeur au nœud prompt 14. Le contrôle fonctionne donc comme substitution sémantique, pas comme suppression d'une piste audio séparée. Le `overall_soundscape` courant contient toutefois `bright chime` et `faint shimmering sparkle bed`, formulation susceptible d'être rendue comme une nappe musicale par H3 malgré `N/A`. Un durcissement éventuel doit distinguer effets diégétiques et vocabulaire musical sans supprimer dialogues ni ambiance.
  - Audit du projet Création assistée KREA2 `krea2-create-12240d33ffdc471a9d02f2582f9a1ca4` : quatre appels locaux Qwen3.8 ont échoué en amont avec `APIError: failed to process mtmd chunk` (deux paires de deux échecs), puis les mêmes requêtes ont réussi avec les mêmes images. Le défaut est donc transitoire dans le traitement multimodal llama.cpp/Unsloth, pas un rejet du prompt, du JSON ou de ComfyUI. Les requêtes envoyaient une référence 1032×1840 (~3 Mo) et un rendu 1664×2960 (~7,3–7,6 Mo).
  - Les échecs de chat KREA2 laissent actuellement le tour utilisateur enregistré avant l'appel LLM ; chaque clic de reprise duplique donc l'instruction dans la mémoire. Le même risque transactionnel existe dans le chat de révision H3. Correctif recommandé : tour en attente non persisté jusqu'au succès (ou identifiant idempotent), réduction d'une copie d'analyse seulement pour les images LLM, puis retry borné uniquement sur l'erreur MTMD transitoire.
  - La branche de travail `h3-base-multishot` et la branche principale locale `master` ont été unifiées le 2026-08-25 par fast-forward après fusion du `master` courant dans la branche de travail. Les 8 commits locaux ont ensuite été publiés sur `https://github.com/EasyFrag/panelforge.git` jusqu'au commit `2ad847b`. Le fichier utilisateur non suivi `D:\Code\panelforge\lancementwork` a été conservé intact.
  - La recette interview animal `0.2.0` est couverte par les quatre modes d'entrée et par des fakes LLM, mais pas encore par un smoke H3 réel ; la voix juvénile déterministe améliore le signal textuel sans garantir à elle seule le timbre généré. La qualité de la voix, de la synchronisation labiale et de l'action finale doit être mesurée séparément du contrat textuel.
  - Le routage Unsloth est couvert par fakes, contrats Web et suite complète, mais pas encore par un smoke réel contre le Qwen3.8 27B UD-Q6_K_XL Dynamic V3 de la RTX 5090. `/v1/models` ne déclare pas la capacité vision : les parcours H3/Ref2V avec images doivent être qualifiés explicitement sur ce modèle.
  - Le projet tigre déjà validé conserve son warning d’export tant que l’utilisateur n’a pas redémarré cette branche puis cliqué sur « Réessayer l’export ». Son ancien dossier partiel à nom long n’est pas supprimé automatiquement.
  - KREA2 Edit est couvert par des fakes ComfyUI et par le PNG réel `103521_00001_.png` pour l’extraction des métadonnées, mais son workflow `0.1.0` n’a pas encore été fumé de bout en bout sur le serveur GPU avec PNG, JPEG, ressource historique absente et plusieurs essais successifs.
  - Les sources KREA2 Edit déjà importées avant l’ajout du lecteur `Lora Loader Stack` conservent leur snapshot de métadonnées vide ; les réimporter après redémarrage applique la récupération corrigée sans réécrire silencieusement l’historique existant.
  - Le projet Edit existant `krea2-edit-d4269b6b4dab4df986c12dad22d200fc` a été créé pendant le défaut d’hydratation : son PNG de plage indique explicitement quatre LoRA `None`, mais sa première révision a reçu comme `base_prompt` le texte de l’image précédente et son formulaire a montré d’anciens réglages. Il n’est pas réécrit silencieusement ; réimporter `image-01_00001_.png` après redémarrage crée un projet propre.
  - Audit des deux derniers H3 Base : `prompt-218c0cd4f9f2489b8ef8551013b84c89` possède un Plan valide de six steps couvrant 0–8 s, mais le writer Qwen3.8 Q8 a omis toute la scène et les actions avant le jalon terminal ; sa réponse brute passe directement du boilerplate à `At 00:08.000, after ...`. Le compilateur n’a fait qu’insérer la caméra. Le linter syntaxique a accepté ce résumé terminal sans vérifier la couverture sémantique des steps. Le run précédent `prompt-7d06b81b0925495fb7418781f89a7477` (Qwen3.8 Q6, quatre steps) conserve correctement scène et progression avant 8 s.
  - Les trois parcours dialogués historiques `prompt-41fff1fef5cb4fa59854572905205d81`, `prompt-4aba62f17cf5488d8a36b036d78cd710` et `prompt-55d53b6a3ead48a5abbc2f1042a3c0a8` conservent leur Plan approuvé mais aucun Prompt final, car ils ont été rejetés avant ce correctif. Ils doivent être régénérés ; aucune migration silencieuse de leur historique n'est faite.
  - Aucun défaut contractuel connu sur les miniatures récentes ; un smoke visuel avec une longue liste de runs reste à faire pour confirmer le coût mémoire du chargement lazy des assets originaux.
  - Les deux échecs historiques H3 Base Gemma (`prompt-0283335687c3478a8ca1a68722e4efa6`) dus aux chevauchements partiels sont couverts par le correctif déterministe, et le candidat joint se canonicalise en un step par beat avec une durée totale exacte de 7 s. Le faux conflit 12 s courant / 13 s ancien contre-exemple est également couvert ; un nouveau smoke UI réel reste à lancer pour confirmer le flux complet.
  - Le premier smoke FL2VA (`prompt-8c186641201146d097988b15aef0cf3c`) avait révélé une confusion entre état final à 6,0 s et fin à 6,5 s. Le contrat et le calcul distinguent désormais début de l’état final et ancrage final, mais le rendu H3 réel doit encore être requalifié.
  - Le nouveau parcours H3 Base est validé contractuellement mais n’a pas encore de smoke qualitatif réel sur T2VA/I2VA/L2VA/FL2VA.
  - Le garde de continuité mono 0.3.0 est couvert sur le cas de valse qui gelait en fin de plan, y compris lorsqu'un writer rend encore une phrase terminale statique, mais son effet réel sur H3 doit être qualifié avec les mêmes frames, seed et paramètres que le run 0.2.0.
  - Le dialogue traversant une coupe et les transitions stylisées ne sont pas couverts par la recette multi-plan flexible.
  - La perte de dialogue du dernier run H3 Base est corrigée contractuellement dans `0.2.0`, mais un smoke réel Qwen3.8/Qwen3.6/Gemma reste nécessaire pour mesurer l’adhérence audio et labiale de H3, distincte de la présence garantie du dialogue dans le prompt final.
  - H3 Base récupère désormais silencieusement les labels modèle legacy selon la grammaire officielle du mode : `<Picture 1>` en I2VA/L2VA, `Picture 1` et `Picture 2` en FL2VA, aucun label en T2VA. Les blocs `<d>` restent strictement inchangés, les numéros hors plage restent bloquants et le diagnostic générique `[[...]]` parle maintenant de placeholder interne.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.
  - Le Super rapide direct accepte volontairement les écarts H3 non fatals comme warnings ; qualifier l'obéissance réelle, la structure des coupes et la densité des prompts par modèle avant de l'élargir au mono-plan.
  - Les contrôleurs UI H3 Base et Ref2V Direct partagent le backend mais gardent encore du code JavaScript dupliqué.
  - Le rendu KREA2 unitaire V1 ne gère pas les LoRA ; le nouveau batch les gère dans quatre slots. Aucun des deux ne découpe encore automatiquement une planche en panels indépendants ni ne transfère ces panels vers Ref2V.
  - La récupération temporelle refuse volontairement tout trou, intervalle hors beat ou timeline d’action dépassant une durée totale explicite ; elle ne compresse jamais silencieusement les actions.
  - Deux arrêts llama.swap `upstream command exited prematurely` sont présents dans les historiques disponibles ; ils sont distincts des rejets contractuels et les relances suivantes réussissent.
  - Audit de poids Ref2V : sur le dernier Plan Qwen, le user prompt fait 18 103 caractères, dont 8 815 de Brief et 8 921 de schéma/tail ; le writer reçoit ensuite 15 329 caractères, dont le même Brief. Les moyennes Qwen observées atteignent environ 21,9 k caractères d’entrée pour le Plan, 21,6 k pour le writer et 32,8 k pour reconcile.

- L'Interview guidée affiche désormais une aide `?` près de la durée (`1 réplique ≈ 4 s`, `2 ≈ 8 s`, `4 ≈ 16 s`) et compte automatiquement les lignes de dialogue `S1/S2`, y compris les blancs à compléter. Un script plus dense que la durée choisie produit un diagnostic orange non bloquant avec durée choisie et durée conseillée ; les citations servent de repli pour un script libre. Le cache UI H3 Base est passé à `i2v-direct.js?v=20260824.5` et `lab.css?v=20260824.4`. Validation : 36 tests Web/UI ciblés verts.
- H3 Base intègre désormais sous le prompt final un atelier de rendu persistant fondé sur le workflow exact `minimax_h3_i2v_Latent_speed test (1).json`, figé comme `video.generate.h3-base/minimax-h3-latent-speed@0.1.0`. Le compilateur active ou élague déterministiquement les loaders de première et dernière frames pour couvrir T2VA, I2VA, L2VA et FL2VA ; prompt, ratio, mégapixels, durée, steps et seed restent réglables, tandis que le graphe deux passes et ses modèles restent recipe-owned.
- Chaque essai H3 Base conserve son prompt effectif, ses réglages, sa seed, le job ComfyUI, la preview live, le MP4 final et ses keyframes. `Music Off`, actif par défaut, remplace uniquement `non_diegetic_music` par `N/A`. Annulation, reprise après réouverture, restauration exacte des réglages et sélection d'un essai comme feedback sont persistantes.
- Le projet de rendu possède une conversation dédiée : un appel LLM réécrit directement le prompt H3 final à partir du prompt courant, de l'échange, des réglages et des keyframes de l'essai sélectionné, sans relancer Brief ni Plan. Les keyframes mono sont réparties uniformément ; en multi-plan elles encadrent les coupes avec une marge de 500 ms plutôt que d'échantillonner la transition exacte. Validation complète : 767 tests verts ; validation ciblée H3 render/web/build : 30 tests verts.
- Le retrait est couvert par la suite complète, mais aucun smoke navigateur manuel des quatre onglets restants n’a encore été fait sur cette branche.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.
- H3 Base/FL2VA et Ref2V restent deux produits et deux contrôleurs séparés ; H3 Base déduit T2VA, I2VA, L2VA ou FL2VA depuis la présence facultative des frames initiale/finale, tandis que Ref2V conserve ses références libres.
- Les familles de recettes propres aux écrans supprimés ne sont plus chargeables par le catalogue produit. Les fichiers d’historique utilisateur restent volontairement sur disque ; aucun nettoyage destructif du `workspace` n’est implicite.
- Le parcours I2V historique reste immuable et lisible ; les nouveaux parcours H3 Base utilisent une nouvelle recette/version et ne présentent pas I2VA comme un checkpoint distinct de H3-Base-FL2VA.
- KREA2 est une recette Image Lab dédiée et versionnée ; le modèle, le ratio, les mégapixels et la seed sont variables, tandis que le sampling et les modèles auxiliaires restent immuables dans la V1.
- Les itérations KREA2 Edit doivent être rangées sous un projet stable : image originale → étapes → révisions de prompt et essais. La source d’une étape reste immuable ; seul un résultat explicitement validé crée l’étape suivante. Ce mécanisme ne crée pas une seconde recette ComfyUI.
- L’export humain KREA2 Edit reste distinct du dépôt et du `workspace` technique. Sa racine par défaut est `D:\AI\PanelForge\KREA2 Projects`, configurable, et il ne recopie que l’image originale puis la chaîne des résultats explicitement validés, avec noms lisibles et sidecars ; les essais rejetés restent uniquement dans l’historique interne/ComfyUI.

- H3 Base mono-plan `0.3.1` conserve le Brief, le Plan V4 et les directives caméra typées de `0.3.0`, mais projette vers le writer uniquement les sémantiques sujet/état dépourvues de prose caméra. Le compilateur final réutilise les mêmes champs nettoyés pour le contrat de mouvement et l'instant final, puis insère exactement la directive caméra canonique. Le Plan réel de valse précédemment rejeté est accepté par cette projection sans perdre le mouvement continu ni la composition finale ; `0.3.0` reste disponible pour comparaison. La `0.3.1` est le mono-plan par défaut et le cache H3 Base est `i2v-direct.js?v=20260824.2`. Validation complète : 745 tests verts.
- Deux essais Plan JSON effectués pendant l'état intermédiaire du patch (Qwen serveur puis Qwen local) ont bien terminé côté LLM mais ont été rejetés par PanelForge parce que `camera_clean` avait été transmis au recalage de durée. L'argument est maintenant limité au compilateur final et ce cas est couvert par la suite complète.
- La liberté créative vidéo est portée par trois axes discrets indépendants `vie de la scène`, `caméra` et `mouvements additionnels`, chacun de 0 (aucun ajout) à 3 (plusieurs enrichissements compatibles). Les niveaux sont des autorisations ; le Brief décide selon la densité, le Plan matérialise les ajouts, sans appel LLM supplémentaire ni champ libre redondant avec l'intention. Le score global reste une projection interne de compatibilité pour les cookbooks et anciens parcours.

- Audit du Plan interview animal `prompt-adc2bf293ffc47438709676d4dff2658` avec Qwen3.8 27B local : l'appel a réussi et le candidat a été accepté, mais a duré 256,2 s. Les 42 mots de dialogue, trois pauses minimales de 250 ms et 1 s d'action finale laissent 10,25 s de parole sur 12 s, soit environ 4,1 mots/s. La trace de 93 k caractères répète plusieurs allocations temporelles et hésite aussi sur la frontière entre `cue.start_ms` et `step.start_ms`. Le même script en recette `0.1.0` prenait déjà 229,7 s : la voix juvénile ajoute du contrôle, mais la cause dominante reste le budget de 12 s combiné au schéma temporel strict et au mode de raisonnement local non borné (`max_tokens` 32768, sans effort de raisonnement explicite envoyé par PanelForge).
- Revue du retour éditorial sur l'interview animal : le diagnostic d'une faiblesse d'assemblage final est confirmé, mais le bloc proposé ne doit pas être copié tel quel. `as From` est une jointure déterministe autour d'un placeholder et doit être réparé par le compilateur ; texte, speaker, intervalle et bouche sont déjà application-owned, mais leur prose reste visible dans les actions projetées au writer et peut provoquer des échos. La cohérence d'état et la distinction mouvement continu/action tardive restent des contrôles sémantiques du writer/Plan. Le débit appartient au Plan et au diagnostic déterministe, pas au writer qui ne reçoit pas le texte parlé. Le cadrage intervieweuse doit rester conditionnel (profil latéral autorisé) et la convention épinglée du projet reste `N/A`, pas `None.`.
- Témoin qualitatif caneton confirmé à 10 s et 12 s : les quatre répliques/30 mots sont complètes, la marche finale est présente, la voix du caneton est bien enfantine et aucune différence qualitative n'est perçue entre les deux durées. Le nombre de répliques seul ne prédit donc pas la durée nécessaire ; longueur en mots, brièveté syntaxique, cadrage hors champ et action finale linéaire dominent. L'interface actuelle n'expose pas encore explicitement le choix hors champ/profil latéral, son défaut restant le profil latéral partiel.
- Audit du mono-plan H3 Base `prompt-ba9f339fd27540c0a136b9f06251b85f` : la voix hors champ vient des guillemets autour de `"étaler"` dans l'intention, pas d'une invention spontanée de Qwen ou de H3. `extract_explicit_dialogues` traite actuellement toute citation non structurelle comme du dialogue et a créé déterministiquement `dialogue_1`; le Brief l'a exposé comme citation verbatim, le Plan a attribué `Off-screen voice (S1)` à 800 ms et le compilateur a inséré `<d>[French] étaler</d>`. Le correctif doit rendre l'extraction contextuelle : speaker explicite, label S1/S2 ou verbe de parole ; une citation d'emphase/action sans contexte vocal doit rester du texte ordinaire.
- Audit du workflow fourni `minimax_h3_i2v_Latent_speed test.json` : il réalise un H3 Base I2VA en deux passes, avec première génération à 0,2 MP, upscale latent 3D vers 1,2 MP puis seconde passe courte, décodage vidéo/audio à 24 fps et preview `ModelPreviewOverrideKJ`. Les variables sûres identifiées sont prompt (nœud 14), première frame (9, utilisée par 16 et 19), ratio (15 et 22), MP cible (27), durée (20), seed (37) et préfixe de sortie (4). Le sampling multi-passe, les sigmas, modèles, VAE, CLIP, basse résolution et FPS doivent rester recipe-owned en V1. Ce graphe ne câble qu'une première frame : T2VA, L2VA et l'ancre finale FL2VA ne sont pas encore prouvés. `ffmpeg/ffprobe` ne sont pas installés côté PanelForge ; pour le feedback LLM, privilégier des keyframes produites par ComfyUI et persistées avec le run plutôt qu'un MP4 envoyé directement.
- Architecture proposée pour le rendu intégré H3 Base : un projet enfant persistant sous la composition, initialisé avec le prompt final et ses frames, porte des révisions de prompt de rendu, une conversation dédiée et des essais vidéo. Chaque tour d'édition reste un seul appel LLM direct depuis le prompt courant, sans Brief ni Plan, et ne modifie jamais la composition approuvée. Chaque essai conserve prompt effectif, réglages, seed, mode musique, run ComfyUI, MP4 et keyframes ; un essai sélectionné devient feedback visuel du tour suivant. `Music Off` force seulement la copie de rendu de `non_diegetic_music` à `N/A`, sans retirer dialogues ni sons diégétiques et sans réécrire le prompt canonique.

## Next steps

1. Lancer un smoke navigateur d’Image Lab, H3 Base, Ref2V et Video Lab sur la branche `cleanup-orphan-labs`, en sélectionnant aussi `vLLM · qwen3.8-27b-nvfp4` sur un parcours multimodal jusqu’à quatre images.
2. Vérifier qu’un ancien run H3 Base/Ref2V s’ouvre encore depuis les parcours récents.
3. Fusionner la branche après validation visuelle.

## Risks / open questions

- Les anciens historiques Storyboard et Archives restent présents dans `workspace`, mais ne sont plus exposés par l’interface ni par leurs anciennes routes. Leur suppression éventuelle devra être une action séparée et explicite.
- Le contexte vLLM est publié dans `/v1/models`, mais sa limite multimodale ne l'est ni dans ce catalogue, ni dans l'OpenAPI, ni dans les métriques. La valeur quatre reste donc un paramètre PanelForge configurable (`PANELFORGE_VLLM_MAX_IMAGES`) et qualifié par probe réel. Le plafond de sortie de 32 768 tokens réserve la moitié du contexte au prompt sans calculer exactement sa tokenisation ; une entrée exceptionnellement longue peut encore dépasser le contexte total de 65 536 tokens.
- Les champs de provenance Storyboard des anciens runs KREA2 restent dans le domaine et le stockage pour relire les JSON existants ; les nouveaux runs ne peuvent plus les renseigner.
- `PromptLabSession`, `PromptLabService` et les stores de sessions/compositions conservent des branches de compatibilité historique parce qu’ils portent aussi H3 Base et Ref2V. Les retirer demanderait une migration de données distincte, pas un simple nettoyage d’interface.

- À 12 s, le script anglais de quatre répliques est planifiable mais impose un débit très rapide. L'interface le signale maintenant avec une heuristique volontairement simple de 4 s par réplique, sans bloquer le parcours. Cette aide ne remplace pas encore un futur calcul déterministe des fenêtres exactes de parole avant le Plan LLM.
- Une déduplication algorithmique libre de la prose finale risquerait de supprimer des mouvements ou états légitimes. Le prochain nettoyage doit rester borné aux artefacts structurels certains ; la cohérence sémantique générique doit être demandée au writer ou signalée, pas réécrite aveuglément.
- Le guide UI de 4 s par réplique est désormais confirmé comme très conservateur : il conseille 16 s pour le témoin caneton alors que 10 s et 12 s sont qualitativement équivalents. Il reste non bloquant pendant l'expérimentation ; une future estimation devrait combiner nombre de mots, pauses et réserve d'action finale plutôt que le seul nombre de tours.
- Tant que l'extracteur de citations reste global, tout mot ou fragment placé entre guillemets dans une intention H3 Base peut devenir une voix hors champ. Contournement immédiat : retirer les guillemets lorsqu'ils servent seulement à insister sur une action ; modifier seulement le Brief ne suffit pas si le ledger est redérivé depuis l'intention source.
- Le workflow Latent Speed avec ses deux frames actives est désormais figé et couvert contractuellement dans les quatre modes, mais aucun rendu GPU réel de cette intégration n'a encore confirmé les custom nodes, modèles et branchements sur le serveur ComfyUI courant.
- Les keyframes permettent au LLM d'évaluer composition, mouvement échantillonné et continuité, mais pas la qualité de la voix, la synchronisation labiale fine ou la musique. Ces défauts doivent rester décrits par l'utilisateur tant qu'aucune analyse audio/vidéo dédiée n'est disponible.
- Les marges de 500 ms autour des coupes sont une heuristique robuste aux transitions molles, pas une détection visuelle des coupures réelles ; elles peuvent manquer une transition particulièrement longue ou décalée par H3.

- Les fins de parole sont dérivées du step dédié contenant chaque cue. Un planner qui ne sépare pas réellement parole, pause et action est rejeté plutôt que réparé silencieusement ; il faudra mesurer le taux de conformité sur Qwen3.8, Qwen3.6 et Gemma.
- Unsloth Studio est OpenAI-compatible mais le catalogue `/v1/models` ne fournit pas de matrice fiable texte/vision. Un modèle local texte-only peut donc être choisi pour une étape multimodale et échouera proprement au moment de l'appel ; aucune capacité n'est inventée côté PanelForge.
- Unsloth Studio peut lister un modèle sans l'avoir chargé. Si l'auto-switch API est désactivé, l'appel échoue immédiatement en HTTP 400 avec `No model loaded`; PanelForge ne charge pas encore automatiquement le modèle sélectionné.
- La recette H3 Base multi-plan est validée contractuellement mais pas encore qualifiée sur un rendu H3 réel ; il faut notamment mesurer si 4 plans restent lisibles dans une durée courte et si FL2VA atteint bien la dernière frame après une coupe.

- Le switch anglais/chinois est couvert contractuellement mais pas encore qualifié par un A/B réel à seed, checkpoint et LoRA identiques. Comparer Qwen et Gemma avant d’envisager de changer le défaut anglais ou de durcir la détection automatique de langue.
- Le nouveau parcours assisté est couvert par fakes LLM/ComfyUI, API, persistance, export et publication, mais pas encore par un rendu GPU réel. La référence facultative est renvoyée à chaque tour LLM pour conserver le contexte visuel, ce qui augmente le coût multimodal des longues conversations.
- Les images d’appoint de Création assistée sont persistées comme assets dès l’envoi du message et restent consultables/réutilisables ; elles ne sont pas supprimées automatiquement lorsqu’un projet est abandonné. Une politique future de collecte des assets non référencés pourra devenir utile si l’usage est intensif.
- L’atelier d’évolution Batch est couvert par persistance, API, batches privés, feedback et publication, mais pas encore par un smoke GPU réel. Les batches d’essai interrompus conservent la même limite que les batches ordinaires : ils persistent et restent annulables, sans reprise automatique des items restants après redémarrage.
- Les recettes publiées ont un identifiant et une version immuables ; un slug déjà utilisé doit être changé au lieu d’écraser silencieusement une recette existante. La mémoire injectée au LLM est volontairement bornée aux recettes publiées et à un sous-ensemble du catalogue de ressources.
- Le garde-fou rejette exhaustivement les formulations caméra canoniques et garde une détection volontairement étroite des paraphrases libres pour ne pas confondre mouvement du sujet et caméra ; qualifier ses faux positifs/négatifs sur des sorties réelles.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
- La grammaire H3 Base dépend de l’entrée : aucun header image en T2VA, ancrage 0,00 s en I2VA, ancrage terminal en L2VA et double ancrage en FL2VA ; le compilateur doit en rester la source de vérité.
- La normalisation H3 Base ne récupère que les alias non ambigus `<Image N>`/`@image N` correspondant aux frames effectivement liées ; elle ne réécrit jamais le dialogue exact et ne devine aucun numéro absent ou hors plage.
- Les axes créatifs restent des permissions sémantiques données au Brief : leur effet dépend de l'obéissance du LLM. Le score global calculé subsiste uniquement pour la compatibilité des cookbooks et historiques, sans redevenir le réglage principal de l'interface.
- La durée Video Lab et les timestamps écrits dans le prompt restent deux entrées indépendantes ; l'interface affiche la durée effective quantifiée mais ne réécrit jamais le prompt silencieusement.
- Le workflow H3 conserve en V1 l'historique et l'archive Spectrum en VRAM ; mesurer son coût réel avant d'automatiser la cohabitation avec llama.swap.
- `system_stats` mesure bien la VRAM GPU globale mais ne permet pas d'isoler exactement llama.swap, ComfyUI et les autres processus ; afficher une telle répartition comme exacte serait trompeur sans endpoint NVML/nvidia-smi sur le serveur GPU.
- Une coupure de PanelForge entre la soumission ComfyUI et la persistance de son identifiant reste une fenêtre transactionnelle externe non récupérable sans idempotence côté serveur.
- La présence d’un modèle dans ComfyUI ne suffit pas à le qualifier : seuls les checkpoints de l’allowlist sont sélectionnables, et les performances/consommations 3–4 MP doivent encore être mesurées sur la RTX 6000.
- Le catalogue classe la précision par taille lorsque le fichier local est accessible. Sinon, les seuls indices automatiques sont les marqueurs explicites du nom ; le gestionnaire permet une correction manuelle persistante, mais celle-ci reste déclarative et ne vérifie pas le dtype interne du checkpoint. La détection CivitAI sans sidecar repose sur un nom de fichier exact et peut rester indéterminée sans bloquer le rendu.
- Un batch actif est suivi par le processus PanelForge qui l’a lancé. Après un redémarrage au milieu d’une série, le run persiste et reste annulable, mais la reprise automatique des items restants est encore à ajouter.
- Le sidecar batch `0.2.0` dépend de `SaveImageKJ` fourni par ComfyUI-KJNodes. Le couple PNG/TXT et son naming `_00001_` ont été confirmés sur le serveur actuel ; un changement futur du naming de KJNodes exigera une adaptation, car ce nœud ne publie aucun descripteur de fichier dans l’historique ComfyUI.
- Les historiques sont actuellement répartis entre `D:\Code\panelforge\workspace` et `.panelpatch\workspace` selon la copie de code lancée ; cette séparation peut faire croire à deux versions de Python et fragmenter l’audit des runs.
- Le poids dominant des prompts Ref2V vient des données répétées (Brief, schéma, Plan), pas des seules règles système ; supprimer des garde-fous avant de réduire ces duplications risquerait de dégrader la qualité sans gain principal.
- L’extraction déterministe H3 Base ne considère que les citations explicites entre guillemets ; une parole demandée sans citation exacte reste une décision sémantique du modèle. Si un cue entier est absent, le texte est garanti mais la langue et le locuteur de repli restent génériques jusqu’au smoke multi-modèles.
- Les miniatures récentes utilisent pour l’instant l’asset image original avec `loading=lazy`, faute de dérivé miniature côté serveur ; limiter la liste à 30 runs et trois images par carte évite d’élargir le scope, mais un endpoint miniature deviendra pertinent si les assets très lourds affectent la mémoire navigateur.
- Les métadonnées ComfyUI embarquées dans un PNG restent une entrée non fiable : l’extracteur KREA2 Edit borne les chunks et textes, ne fait que parser les données et accepte les informations partielles. Un checkpoint ou une LoRA disparu reste donc un warning UI et devra être remplacé manuellement avant rendu.
- Les étapes KREA2 Edit rendent explicite la dérive cumulative : sélectionner un feedback ne modifie jamais la source, mais chaque clic sur `Valider et continuer` adopte réellement le PNG produit. Une longue chaîne peut donc accumuler des artefacts malgré la conservation complète de l’historique.
- Les sorties KREA2 existent sous deux formes techniques : PNG/TXT dans les sous-dossiers `image/krea2-batch` ou `image/krea2-edit` de ComfyUI, puis copie immuable en `workspace/assets/<asset-id>/content.bin` avec état JSON séparé. L’export humain ajoute une troisième copie volontairement redondante des seules images validées ; surveiller sa volumétrie et vérifier en smoke réel les droits d’écriture sur `D:\AI\PanelForge\KREA2 Projects`.
- Une relance d’export après l’ancien échec MAX_PATH crée le nouveau dossier borné et met à jour l’état du projet, mais laisse le dossier partiel historique sur disque pour éviter toute suppression implicite de données utilisateur.
- Le processus PanelForge courant ne peut pas lire les racines UNC KREA2, mais le fallback ComfyUI expose bien 16 checkpoints et 26 LoRA. Les rendus restent disponibles ; seules la taille, la précision déduite du fichier et les métadonnées locales demeurent invérifiables tant que l'accès UNC n'est pas rétabli.

## Update 2026-08-26 — monitoring GPU local

### Works
- Le bandeau runtime affiche maintenant deux lignes compactes `Serveur` et `Local`. La ligne locale lit automatiquement la VRAM globale et la température de la première carte NVIDIA via `nvidia-smi`, avec un cache court compatible avec le rafraîchissement à une seconde.
- Les seuils visuels sont partagés avec le serveur : VRAM verte jusqu'à 30 % puis jaune ; température verte jusqu'à 60 °C, orange jusqu'à 80 °C puis rouge.
- La sonde réelle a détecté la RTX 5090 et les 604 tests passent.

### Broken / missing
- La télémétrie locale est globale à la carte et ne ventile pas la VRAM entre vLLM, Unsloth Studio et les autres processus.
- Si `nvidia-smi` ou le pilote NVIDIA est indisponible, l'interface affiche seulement `GPU local indisponible` et conserve le reste du bandeau fonctionnel.

### Next steps
1. Vérifier visuellement le bandeau à la largeur d'écran habituelle et sur une fenêtre étroite.

### Risks / open questions
- La V1 cible la première carte NVIDIA (`GPU 0`) ; une machine locale multi-GPU nécessiterait plus tard une sélection explicite ou l'affichage de plusieurs lignes.

## Audit 2026-08-27 — last-frame tenue trop tôt

### Works
- Le brief du run L2VA `prompt-c163edcfb00c4ec28ad85a3ded420719` qualifie correctement la dernière frame comme un instant visuel sans arrêt, et le compilateur ajoute bien le contrat `continue_motion` ainsi que l'absence de pause/freeze/hold.

### Broken / missing
- Le plan contredit ensuite ce contrat : sujet déjà dans le bas-gauche dès le début, `settles into ... final frame` entre 7,0 et 8,8 s, puis `composition stable` jusqu'à 10 s. La résolution du risque demande même de verrouiller la position finale avant la fin.
- La caméra passe de `large amplitude` à `small amplitude` à 5 s, sans demande explicite de ralentissement, et le prompt final ne conserve pas de preuve forte de parallaxe/défilement du décor malgré l'intention de suivi avec impression de sur-place.

### Next steps
1. Cadrer une recette FL2VA suivante qui interdit la convergence/tenue anticipée pour `continue_motion`, sans imposer un rapprochement du sujet incompatible avec un tracking sur-place.
2. Ajouter un contrôle déterministe ciblé sur les contradictions `settle/lock/match/stable final frame` et sur les réductions de caméra non motivées.

### Risks / open questions
- Retarder systématiquement la totalité de l'état final serait incorrect pour une transformation qui peut finir avant la fin pendant que le mouvement principal continue ; le garde-fou doit viser la pose/composition tenue, pas tous les attributs visuels finaux.

## Update 2026-08-27 — H3 Base mono-plan 0.3.2

### Works
- La recette et le profil H3 Base mono-plan `0.3.2` sont ajoutés et sélectionnés par défaut. Ils conservent les trois appels LLM et les versions `0.3.0`/`0.3.1` restent disponibles.
- Pour `continue_motion`, le Plan doit maintenant traiter la dernière frame comme un échantillon instantané du mouvement : aucune convergence anticipée par `settle`, `lock`, `reach`, `match`, `stable final frame` ou réduction de caméra destinée à tenir la composition finale.
- Le tracking/sur-place est explicitement compatible : le sujet peut rester stable à l'écran si la parallaxe, le défilement du décor, les projections et son mouvement corporel prouvent que l'action continue.
- Un contrat déterministe propre à la `0.3.2` rejette les contradictions réelles tout en acceptant les formulations négatives (`without settling...`), les passages instantanés et les politiques `natural_settle`/`intentional_hold`. Les risques descriptifs ne sont pas confondus avec des instructions exécutables.
- Validation : 613 tests passent et `git diff --check` ne remonte aucune erreur (uniquement les avertissements CRLF habituels).

### Broken / missing
- Aucun rendu H3 réel n'a encore qualifié la fin de mouvement produite par la `0.3.2` sur le cas du toboggan aquatique.

### Next steps
1. Relancer le même L2VA de toboggan en `Mono-plan · standard (0.3.2)` et comparer surtout les trois dernières secondes avec le run précédent.
2. Vérifier dans le Plan que la preuve de mouvement reste visible jusqu'à la coupe sans imposer un rapprochement du sujet.
3. Tester ensuite une intention réellement conçue pour `natural_settle` afin de confirmer que ce comportement reste autorisé.

### Risks / open questions
- Le garde-fou lexical vise volontairement les contradictions les plus certaines ; une paraphrase nouvelle peut encore lui échapper et devra être ajoutée à partir d'un run réel, sans élargir aveuglément la détection.

## Update 2026-08-28 — aperçu des frames avant création H3 Base

### Works
- Tant qu'aucune session H3 Base n'est active, la zone de droite affiche les frames sélectionnées à la place du message d'accueil : une image occupe seule la galerie, deux images sont disposées côte à côte.
- Toutes les images utilisent `object-fit: contain` dans un cadre ajusté à l'espace disponible. Les noms longs sont ellipsés sans élargir la grille et restent disponibles au survol.
- Chaque fichier librement sélectionné possède maintenant un bouton `Retirer` distinct du clic sur la vignette, qui continue à ouvrir le remplacement. Les frames verrouillées d'un parcours préparé depuis un ancien run ne deviennent pas implicitement modifiables.
- La galerie est strictement limitée à l'état sans session. Ouvrir ou créer un parcours conserve la bascule historique vers l'éditeur complet Brief, Plan, Prompt et rendu. Validation complète : 613 tests passent.

### Broken / missing
- Aucun smoke navigateur manuel n'a encore vérifié le rendu exact avec une image 9:16, deux images de ratios différents et un nom de fichier exceptionnellement long.

### Next steps
1. Vérifier visuellement les cas zéro, une et deux frames avant création d'un parcours.
2. Ouvrir ensuite un ancien parcours et confirmer que son historique complet reste immédiatement exploitable.

### Risks / open questions
- Les ratios extrêmes créent volontairement des marges dans le cadre sombre afin de préserver l'image entière plutôt que de la recadrer.

## Audit 2026-08-28 — convergence terminale encore trop précoce en 0.3.2

### Works
- Le run L2VA `prompt-e00d499240cb4d75a63b1718aaa68064` utilise bien `minimax.h3.fl2va.direct@0.3.2`, `continue_motion`, un hold nul et une caméra continue sans correction terminale.
- Le prompt final contient correctement l'ancre à 10 s et les clauses explicites d'absence de pause, freeze ou held pose.

### Broken / missing
- Les keyframes du rendu réussi montrent une convergence réelle : à 7,562 s, la pose des bras, le regard, la silhouette et la floraison sont déjà très proches de la frame à 10,083 s. Les dernières 2,5 s ressemblent donc à une tenue avec micro-mouvements.
- Le Plan contourne lexicalement le garde 0.3.2 : son état à 7 s installe déjà les bras hauts, le regard upward-left et les fleurs presque ouvertes ; le beat 7–10 s `sustains the raised-arm dance phrase`, puis le step 8,6–10 s décrit `the visible composition at the cut instant includes...` au lieu d'une action évolutive.
- Le garde actuel cherche surtout `settle`, `lock`, `reach`, `match` et `final frame`. Il ne détecte pas encore un step temporisé qui décrit une snapshot/composition finale sans changement observable.

### Next steps
1. Cadrer une version 0.3.3 qui réserve les descriptions `at the cut instant` au seul `final_state` et exige une action réellement évolutive dans le dernier step de `continue_motion`.
2. Conserver dans le prompt final un unique intervalle terminal explicite, issu du dernier step, afin que H3 ne répartisse pas librement la convergence sur plusieurs secondes.
3. Rejouer le même L2VA et comparer les keyframes vers 7,5 s et 10 s.

### Risks / open questions
- Interdire globalement `sustain` serait trop large : soutenir une danse ou un écoulement peut rester dynamique. Le contrôle doit viser les steps d'état/snapshot et l'absence de changement observable, pas un mot isolé.

## Update 2026-08-28 — ordre Image Lab et audit H3 Base / Ref2V

### Works
- `Création assistée` est maintenant le premier choix visuel dans chacun des cinq bandeaux Image Lab, devant `Changer la vue`, sans changer la vue active ni l'ouverture des projets existants.
- Le test d'ordre partagé protège cette disposition dans les cinq workspaces. Validation ciblée : 19 tests ; validation complète : 613 tests passent.
- L'audit confirme les acquis déjà communs aux deux parcours supervisés : trois appels Brief/Plan/Prompt, lecture native des images, axes de créativité, Plan physique, réparation déterministe des steps parallèles et insertion canonique de la caméra.
- Le dernier Ref2V mono `prompt-aa12c34f11c8443ba30cbd92e48c693d` compile correctement un plan de 10 s avec tilt up et un hold final de 400 ms pour garder le texte `Happy Birthday !!!` lisible.

### Broken / missing
- Le Ref2V mono courant `minimax.h3.ref2v.direct@0.3.3` reste sur le Plan V2 : aucun `motion_contract` typé et aucun ledger de dialogue compilé. Il ne distingue donc pas structurellement `continue_motion`, `natural_settle` et `intentional_hold`; son hold de 400 ms est une décision implicite du modèle.
- Son Brief 0.1.0 et son writer restent plus lourds que H3 Base 0.3.2. Sur le dernier run, le Brief fait environ 12,4 k caractères et le Plan 10,9 k, puis le writer reçoit encore les deux, alors que le writer H3 Base ne reçoit plus le Brief complet.
- La prose Ref2V finale reste propriétaire de l'état terminal et du hold. H3 Base compile désormais la terminaison, les dialogues et l'ancre finale de manière déterministe.
- H3 Base possède une boucle de rendu/itération conversationnelle intégrée ; Ref2V envoie encore son prompt vers le Video Lab séparé. Le nouveau workflow Ref2V avec upscale doit être qualifié avant de modifier cette partie.

### Next steps
1. Qualifier le workflow Ref2V avec upscale comme recette de rendu versionnée, indépendante de la recette de prompting.
2. Cadrer un Ref2V mono `0.4.0` : Brief compact, Plan V4 avec mouvement/dialogue, writer sans Brief complet et terminaison compilée, tout en conservant strictement la grammaire `ref-en` et le mapping des rôles.
3. Tester cette recette sur trois fins distinctes : mouvement continu, stabilisation naturelle et tenue volontaire lisible comme le feu d'artifice.

### Risks / open questions
- Les images Ref2V sont des références sémantiques libres, pas automatiquement des ancres temporelles. Le garde de dernière frame H3 Base ne devra s'appliquer qu'à un rôle `last_frame` explicite, jamais à une image de sujet, style, composition ou environnement.
- Le Ref2V multi-plan 2–6 plans possède son propre contrat de coupes et de continuité. Porter le nouveau contrat mono sans le redéfinir par plan créerait une fausse équivalence ; il doit rester un chantier séparé après qualification du mono.

## Scope 2026-08-28 — prochaine recette Ref2V mono

### Works
- La documentation officielle MiniMax H3 confirme que Ref2VA accepte jusqu'à neuf images. La grammaire `ref-en` distingue les contenus réutilisables `<Subject N>` des images servant réellement d'ancre concrète `<Picture N>`.
- L'architecture cible conserve exactement trois appels LLM : Brief multimodal compact, Plan physique structuré, puis writer final compact.

### Broken / missing
- Le workflow Ref2V fourni n'est nativement câblé que pour trois images ; l'adaptateur de rendu doit étendre déterministiquement ses entrées jusqu'à neuf lorsque le nœud Ref2V le permet.
- Ref2V ne possède pas encore le contrat de mouvement, le ledger de dialogue, la terminaison compilée ni l'atelier de rendu conversationnel de H3 Base mono.

### Next steps
1. Créer une recette Ref2V mono `0.4.0` inspirée de H3 Base mono pour Brief, Plan et writer, tout en conservant strictement la grammaire et les rôles Ref2V.
2. Accepter jusqu'à neuf images côté Ref2VA/rendu et transmettre toutes les images au LLM choisi sans garde locale, contact sheet ni appel supplémentaire, même si sa capacité réelle est inconnue ou inférieure.
3. Qualifier le nouveau workflow Ref2V avec upscale, puis intégrer sous le prompt l'atelier de rendu et d'itération conversationnelle.

### Risks / open questions
- Une image Ref2V ne devient jamais implicitement une first/last frame. Seul un rôle d'ancre explicite autorise les règles temporelles de H3 Base ; les autres références restent sémantiques.
- Un fournisseur LLM peut rejeter lui-même une requête contenant trop d'images ; PanelForge doit alors restituer cette erreur distante telle quelle sans prévalidation bloquante.
- Le multi-plan, les références vidéo/audio et les recettes Ref2V directes/rapides restent hors de ce patch.

## Update 2026-08-28 — Ref2V mono 0.4 et atelier intégré

### Works
- La nouvelle recette immuable `minimax.h3.ref2v.direct@0.4.0` conserve exactement trois appels LLM : Brief multimodal compact, Plan V4 physique, puis writer final compact sans réinjecter le Brief complet.
- Ref2V accepte désormais une à neuf images natives ordonnées dans l'interface, le domaine, le profil et le cookbook. Les appels Plan transmettent chaque fichier séparément sous `<Picture 1>` à `<Picture 9>`, sans contact sheet, appel supplémentaire ni prévalidation de capacité du LLM.
- Le routage Ref2V reste distinct de H3 Base : rôles libres et mapping `<Picture N>` côté Ref2V, ancres first/last côté H3 Base. Les deux partagent désormais le contrat de mouvement, les dialogues verbatim, la caméra typée, la réparation déterministe des chevauchements et la terminaison compilée.
- Le compilateur Ref2V 0.4 impose `continue_motion|natural_settle|intentional_hold`, compile la durée, la caméra, les cues de dialogue exacts et la snapshot finale, puis valide le protocole seulement après résolution des placeholders internes.
- L'atelier `Créer et ajuster la vidéo` est intégré sous le prompt Ref2V : paramètres, musique OFF par défaut, preview live, vidéo finale, historique, keyframes à marge de 500 ms, feedback et boucle conversationnelle en un appel. Toute la conversation antérieure est conservée dans chaque itération.
- L'adaptateur de rendu déclare une capacité de une à neuf références et étend le workflow publié en clonant les loaders neutres pour les références 4 à 9. Cette capacité est exposée par `/api/h3-render/spec?mode=ref2va`.
- Image Lab ouvre désormais `Création assistée` par défaut. La validation finale compile les sources et fait passer 619 tests.

### Broken / missing
- Aucun rendu réel Ref2V à quatre ou neuf images n'a encore validé sur le GPU que la version installée du nœud `MiniMaxH3ReferenceToVideo` accepte bien les entrées variadiques ajoutées.
- L'atelier utilise encore le workflow Ref2V versionné courant sans upscale ; le futur workflow avec upscale devra être qualifié puis ajouté comme nouvelle recette de rendu, sans modifier la recette de prompting 0.4.
- `node --check` n'a pas pu être exécuté car Node.js n'est pas installé dans cet environnement ; les tests UI statiques passent.

### Next steps
1. Lancer un Ref2V réel avec 1, 3 puis 4–9 images et vérifier ordre des références, preview, vidéo finale et keyframes.
2. Comparer qualitativement les trois fins `continue_motion`, `natural_settle` et `intentional_hold`, puis un dialogue exact.
3. Versionner le workflow Ref2V avec upscale quand son JSON testé sera disponible.

### Risks / open questions
- Le câblage des références 4 à 9 suppose la convention variadique `ref_images.ref_image_3` à `ref_images.ref_image_8` du nœud installé ; une divergence de custom node remontera comme erreur ComfyUI au premier smoke test.
- Un fournisseur LLM peut refuser lui-même plus d'images qu'il n'en supporte. Conformément à la décision produit, PanelForge envoie néanmoins toutes les images et restitue l'erreur distante sans garde locale.
- Les références Ref2V restent sémantiques par défaut : aucune image n'est transformée implicitement en ancre temporelle, et le multi-plan reste hors scope.

## Audit 2026-08-28 — rejet de la caméra Ref2V à 0 ms

### Works
- Les deux derniers candidats du writer Ref2V 0.4 sont structurellement exploitables : ils respectent les champs internes, le landmark `At 00:00.000` et celui de 6 s, sans prose de caméra inventée.
- Le Plan approuvé contient deux directives canoniques cohérentes : `push.in` de 0 à 6 s puis `tilt.up` de 6 à 10 s.

### Broken / missing
- Le pipeline compile d'abord la caméra 0 ms au début de `Shot 1`, puis `apply_direct_ref2v_timing_v4` préfixe la clause de continuité `Throughout the entire shot...` devant elle. La relecture déterministe rejette ensuite cette sortie avec `the 0 ms camera clause is not at the start of Shot 1`.
- Il manque un test Ref2V 0.4 combinant `continue_motion` avec une directive caméra dont `start_ms == 0`; le test V4 existant ne couvre qu'une caméra démarrant à 8 s.

### Next steps
1. Faire insérer la clause de continuité immédiatement après la ou les clauses caméra canoniques de 0 ms, sans changer les prompts LLM ni relâcher l'invariant de caméra.
2. Ajouter une régression Ref2V 0.4 `continue_motion + camera start_ms=0`, puis exécuter les tests Ref2V et la suite complète.
3. Relancer uniquement la génération du prompt sur le parcours concerné après le correctif.

### Risks / open questions
- Aucun risque de grammaire H3 n'est identifié : le correctif doit uniquement changer l'ordre de deux clauses compilées par PanelForge. Il ne doit pas demander au LLM d'écrire la caméra ni accepter une caméra placée arbitrairement.

## Update 2026-08-28 — caméra Ref2V V4 à 0 ms corrigée

### Works
- `apply_direct_ref2v_timing_v4` conserve désormais la clause caméra canonique de 0 ms en tête de `Shot 1` et insère la continuité du mouvement immédiatement après.
- Aucun prompt LLM ni validateur H3 n'a été relâché. Si la caméra canonique attendue n'est pas déjà en tête, le compilateur continue de bloquer explicitement.
- La nouvelle régression Ref2V 0.4 reproduisait l'erreur `the 0 ms camera clause is not at the start of Shot 1` avant le correctif. Elle passe maintenant, ainsi que les 14 tests Ref2V et les 620 tests complets.

### Broken / missing
- Le parcours utilisateur qui avait échoué conserve seulement ses candidats comme brouillons ; sa dernière étape doit être relancée pour enregistrer un prompt compilé.

### Next steps
1. Redémarrer PanelForge sur la branche courante si le serveur utilisait encore l'ancien processus.
2. Relancer uniquement `Générer le Prompt` sur le dernier parcours Ref2V.
3. Effectuer ensuite le smoke test de rendu Ref2V prévu.

### Risks / open questions
- Aucun risque ouvert propre à ce correctif ; les risques de rendu Ref2V à plus de trois images restent ceux déjà documentés.

## Scope 2026-08-28 — workflow Ref2V Latent Upscale fourni

### Works
- Le fichier `minimax_h3_r2v_Latent Upscale.json` est un workflow API ComfyUI de 37 nœuds. Son chemin utile est cohérent avec H3 Base Latent Upscale : Ref2V basse résolution, première passe, séparation audio/vidéo, upscale du latent vidéo, recombinaison avec l'audio, seconde passe courte, décodage puis sortie vidéo sonorisée.
- Les contrôles directement identifiés sont : prompt (nœud 2), références (nœud Ref2V 11), ratio et basse résolution (20), durée (17), cible finale en mégapixels (23), steps principaux/split (24/13), seed (31), preview (12) et sortie (5).
- Le workflow peut alimenter la preview live, la vidéo finale et les keyframes depuis le décodage final, tout en conservant l'audio issu de la première passe.

### Broken / missing
- Une seule image est actuellement chargée et reliée à `ref_images.ref_image_0`. PanelForge devra neutraliser ce fichier local, créer les slots 2 et 3 de la recette publiée, puis conserver l'extension dynamique existante jusqu'à neuf références.
- Six nœuds sont orphelins de la sortie finale et doivent être retirés de la snapshot versionnée : `ManualSigmas` 6 et 22, `VAEDecode` 7, `VAEDecodeAudio` 8, `UNETLoader` 30 et la note `Textbox` 46.
- Le manifest Ref2V actuel est lié à l'ancien workflow sans upscale et le runner charge explicitement sa version 0.1.0.

### Next steps
1. Valider les valeurs par défaut et le petit ensemble de paramètres exposés avant de publier `video.generate.ref2v/minimax-h3-ref2v@0.2.0`.
2. Importer et neutraliser le graphe, ajouter les slots de référence, manifester ses invariants et basculer le runner sur 0.2.0 sans modifier 0.1.0.
3. Tester la compilation avec 1, 3 et 9 images, puis effectuer un rendu GPU avec preview, audio, upscale, keyframes et sortie finale.

### Risks / open questions
- Le champ `steps` pilote la passe principale et son split ; la seconde passe conserve trois sigmas fixes. L'UI devrait le nommer ou l'expliquer comme `steps principaux`, pas comme le total exact des deux passes.
- Le nouveau graphe fixe la prépasse à 0,2 MP, l'upscaler en FP16/CUDA et Spectrum sur OFF. Ces choix doivent rester des invariants de recette en V1 sauf demande contraire.

## Update 2026-08-28 — Ref2V Latent Upscale actif

### Works
- L'ancienne recette de rendu Ref2V 0.1.0 a été retirée comme demandé et remplacée par `video.generate.ref2v/minimax-h3-ref2v@0.2.0`, chargée par défaut dans le runner.
- La snapshot fournie a été neutralisée : prompt et trois loaders utilisent des sentinelles PanelForge, six nœuds orphelins ont été retirés et le manifest verrouille les modèles hybrides, la prépasse 0,2 MP, l'upscaler FP16/CUDA, les sigmas de raffinement, Spectrum OFF, l'audio, la preview et la sortie finale.
- Le preset par défaut est `9:16`, `1,2 MP`, `10 s`, `25 steps principaux`. L'interface continue d'inférer la durée du prompt et n'utilise 10 s qu'en repli.
- Le binding `steps` alimente désormais le scheduler principal et `SplitSigmas`; la seconde passe conserve trois steps fixes. L'UI Ref2V l'indique par le libellé `Steps principaux` et une aide au survol.
- L'atelier intégré compile 1, 3 et 9 images ; les références 4 à 9 restent clonées sur l'entrée variadique. Preview, keyframes et vidéo finale utilisent le décodage après upscale, tandis que l'audio de la première passe est recombiné avant la sortie.
- Validation : 33 tests ciblés puis 620 tests complets passent.

### Broken / missing
- Aucun rendu GPU réel n'a encore qualifié cette snapshot depuis PanelForge. La validation actuelle couvre le graphe, les bindings, le hash, la compilation et les parcours Web, pas l'exécution des custom nodes sur ComfyUI.

### Next steps
1. Redémarrer PanelForge pour charger la recette Ref2V 0.2.0.
2. Lancer un smoke test avec une image, puis trois images, en vérifiant preview, audio, 1,2 MP final et historique.
3. Tester ensuite quatre à neuf images pour confirmer l'entrée variadique du custom node installé.

### Risks / open questions
- Le passage de 0.1.0 à 0.2.0 supprime volontairement l'ancienne snapshot. Les anciens rendus restent lisibles, mais un run technique 0.1.0 non encore soumis ne peut plus être recompilé avec son ancien workflow.
- La capacité 4–9 images dépend toujours de la convention `ref_images.ref_image_N` réellement acceptée par la version locale de `MiniMaxH3ReferenceToVideo`.

## Audit 2026-08-29 — modèle LLM fantôme dans H3 Base

### Works
- Les journaux isolent quatre échecs `brief.structure` sur `vllm::qwen3.8-27b-nvfp4`, suivis d'un succès immédiat sur `local::unsloth/Qwen3.8-27B-GGUF`; le prompt H3 Base n'est pas en cause.
- Le catalogue routé interroge bien chaque endpoint OpenAI-compatible et ignore une source indisponible lors d'une nouvelle découverte.

### Broken / missing
- L'ouverture d'un ancien parcours réinjecte son `model_id` dans le select même s'il n'est plus publié par le catalogue live, afin de garder le parcours lisible.
- `Nouveau run` ne recharge pas le catalogue et peut conserver cette option historique indisponible. En outre, une actualisation en échec conserve volontairement les anciennes options. Un modèle vLLM arrêté peut donc rester sélectionnable et produire `Connection error.`

### Next steps
1. Sur un nouveau run, reconstruire le select depuis le dernier catalogue live et choisir un modèle disponible.
2. Garder les modèles historiques visibles uniquement dans le contexte de consultation/reprise, avec un état indisponible non sélectionnable pour un nouvel appel.
3. Ajouter une régression UI couvrant `ouvrir ancien run vLLM -> Nouveau run alors que vLLM est hors ligne`.

### Risks / open questions
- Un endpoint peut disparaître après une découverte valide; même avec ce correctif UX, une panne entre la sélection et l'appel restera une erreur de connexion normale.

## Scope 2026-08-29 — Social Lab Instagram

### Works
- Les briques existantes permettent de réutiliser le prompt H3 final quand il est retrouvé et la mémoire conversationnelle des projets assistés.
- La V1 validée prend uniquement une vidéo uploadée et quatre champs de texte libre : `mood`, `vibe`, exemple représentatif du channel et consignes.
- La langue vaut anglais par défaut avec français sélectionnable. Trois variantes sont demandées par défaut; chacune contient titre/hook, légende, hashtags et emojis, avec une seule action `Tout copier`.
- Une discussion persistante permet d'affiner les variantes avec toute la mémoire d'échange. Les profils de channel sont nommés, enregistrables et réutilisables depuis l'interface.

### Broken / missing
- Les gateways LLM actuelles ne fournissent pas de compréhension audio/vidéo native garantie. Une vidéo externe sera représentée par quatre frames; sans prompt PanelForge retrouvé, le son et les paroles ne sont pas connus du modèle.
- `ffmpeg` et `ffprobe` ne sont pas disponibles sur le PATH courant. L'extraction V1 doit donc se faire côté navigateur via le lecteur HTML et canvas pour les formats web compatibles.
- Le module, son stockage de projets et son interface n'existent pas encore.

### Next steps
1. Implémenter `Social Lab` avec upload vidéo, lecteur, quatre keyframes, sélection/création de profil et choix du LLM.
2. Ajouter le projet conversationnel persistant, les trois variantes structurées et `Tout copier`.
3. Ajouter la recherche best effort du prompt source PanelForge et les tests UI/service/storage.

### Risks / open questions
- Les frames seules ne permettent pas d'entendre un dialogue, une voix ou une musique; seul un prompt source retrouvé peut fournir ces informations en V1.
- L'extraction navigateur dépend des codecs lisibles par le navigateur; MP4/WebM est le périmètre naturel de la première version.

## Update 2026-08-29 — Social Lab Instagram implémenté

### Works
- `Video Lab > Texte Instagram` accepte un upload MP4/WebM, en extrait exactement quatre JPEG côté navigateur à 10, 35, 65 et 90 %, puis envoie uniquement ces frames au LLM sélectionné. Le sélecteur partagé expose serveur, Unsloth et vLLM.
- La langue est anglaise par défaut avec français sélectionnable. Le nombre de variantes vaut trois par défaut et reste réglable de 1 à 8. Chaque proposition persistée contient angle, hook, légende, hashtags, emojis et un bouton `Tout copier`.
- Les profils de chaîne enregistrent nom, langue, mood, vibe, exemple représentatif et consignes. Les projets conservent vidéo, keyframes, réglages, source H3 retrouvée par hash, conversation complète et anciennes variantes ; ils peuvent être rouverts et affinés après redémarrage.
- Chaque itération renvoie au LLM les quatre images, le prompt source disponible et la totalité des échanges/propositions antérieurs. Changer le nombre de variantes ne rend pas les anciens tours illisibles.
- Le service, le stockage, les routes HTTP/SSE, le démarrage produit et l'interface sont couverts par quatre nouveaux tests. La suite complète atteint 624 tests ; les deux seules régressions observées étaient des assertions statiques de cache/navigation mises à jour, puis les 29 tests concernés sont repassés.

### Broken / missing
- Aucun smoke navigateur réel n'a encore validé l'extraction canvas sur les codecs MP4/WebM utilisés en production ni la qualité éditoriale d'un modèle réel.
- Les quatre frames ne fournissent aucune information audio. PanelForge n'autorise les affirmations sur dialogue, voix ou musique que lorsqu'un prompt source identique est retrouvé dans les sorties H3/Video Lab.

### Next steps
1. Tester un MP4 H3 connu puis une vidéo externe, et vérifier frames, prompt source, copie et reprise après redémarrage.
2. Comparer les variantes anglaises et françaises avec le modèle serveur puis `vLLM · qwen3.8-27b-nvfp4`.
3. Ajuster le format éditorial du prompt système à partir de quelques publications réellement retenues.

### Risks / open questions
- Le décodage dépend des codecs pris en charge par le navigateur même si le conteneur est MP4 ou WebM ; une vidéo non décodable échoue avant toute création de projet avec un message explicite.
- La recherche du prompt source repose sur l'égalité SHA-256 du fichier uploadé et d'un asset vidéo PanelForge. Un réencodage, même visuellement identique, supprime cette correspondance et force l'analyse visuelle seule.
- Les vidéos et keyframes sont conservées comme assets immuables dans le workspace ; aucune collecte automatique des projets abandonnés n'est encore définie.

## Scope 2026-08-30 — orchestrateur de production Image → KREA2 → H3

### Works
- Les services KREA2 assisté, KREA2 Edit et H3 Render possèdent déjà des projets/essais persistants, la soumission, l'annulation, la reprise et les assets nécessaires pour être pilotés par un orchestrateur sans dupliquer leurs moteurs.
- La V1 conserve l'image source comme inspiration immuable et cherche trois recréations par modification directe du prompt dans le parcours KREA2 assisté, comme les itérations manuelles actuelles. KREA2 Edit reste hors périmètre.
- Le degré de liberté créative est exposé dès le départ sur le même principe que H3 et vaut le maximum par défaut.
- Le workflow H3 Base garde sa première passe à 0,2 MP et son réglage exposé pilote la sortie upscalée. Un brouillon à 0,2 MP puis un rendu à 1,2 MP peuvent donc verrouiller prompt, frames, seed et réglages, même si la seconde soumission recalcule encore le graphe complet.
- La température/VRAM du GPU local est déjà disponible côté serveur via `nvidia-smi`.

### Broken / missing
- Il n'existe pas encore d'agrégat de production ni de machine à états durable reliant les IDs de projets/essais KREA2 et H3, leurs validations humaines, les erreurs et les pauses thermiques.
- La température du GPU Comfy distant est actuellement relayée par WebSocket Crystools jusqu'au navigateur, mais n'est pas conservée par un moniteur serveur autonome ; elle ne peut donc pas encore sécuriser une file de nuit sans navigateur ouvert.
- Le workflow ne persiste pas aujourd'hui le latent 0,2 MP pour une reprise d'upscale seule ; le rendu final 1,2 MP doit d'abord être une nouvelle exécution verrouillée, avec un faible risque de divergence si un nœud n'est pas strictement déterministe.

### Next steps
1. Concevoir le parcours V1 mono-job autour d'un LLM orchestrateur qui choisit l'image parmi trois essais et décide des révisions vidéo ; une validation humaine reste disponible comme option, sans être requise en mode full auto.
2. Ajouter l'agrégat `ProductionJob`, son journal d'étapes idempotent et le garde thermique local/distant paramétrable, avec 85 °C pour l'arrêt, reprise sous 40 °C et 120 secondes d'attente minimale par défaut.
3. Construire l'interface d'orchestration en réutilisant les services KREA2/H3, tout en préparant le schéma pour une future file nocturne.

### Risks / open questions
- Le LLM orchestrateur doit prendre les décisions en mode full auto malgré une observation vidéo limitée aux prompts et keyframes ; il faut conserver scores, justification, budget d'itérations et conditions d'arrêt pour éviter les boucles sans fin.
- Une validation humaine optionnelle doit pouvoir suspendre le même automate sans créer un second parcours ni perdre la possibilité de reprendre automatiquement.
- L'hystérésis thermique 85/40 °C implique potentiellement de longues pauses ; la télémétrie inconnue doit rester un état explicite et paramétrable, sans être implicitement considérée comme sûre.

## Snapshot 2026-08-30 — version stable avant orchestrateur

### Works
- La suite complète passe avec 634 tests en 87,456 secondes.
- Le lot courant est figé dans le commit `8c309df` (`Stabilize current Image Lab and H3 workflows`) et publié sur `master` du dépôt GitHub `EasyFrag/panelforge`.
- Le tag annoté `stable-pre-production-orchestrator-2026-08-30` est publié sur GitHub et constitue le point de restauration avant le chantier d'orchestration.
- Aucun code du nouvel orchestrateur de production n'est inclus dans ce snapshot.

### Broken / missing
- Le remote local du worktree pointe vers `D:\Code\panelforge`; son transfert intermédiaire est refusé sous le compte sandbox par la protection Git `dubious ownership`. La publication directe vers GitHub a réussi sans modifier cette configuration globale.
- Le checkout local `D:\Code\panelforge` n'a donc pas été avancé automatiquement sur le nouveau `master`; son fichier non suivi `lancementwork` est resté intact.

### Next steps
1. Faire le dernier alignement sur les décisions et limites du LLM orchestrateur full auto.
2. Créer la branche du chantier depuis le snapshot stable publié.
3. Implémenter l'agrégat persistant, le garde thermique et le premier parcours mono-job.

### Risks / open questions
- Une mise à jour du checkout principal devra être lancée sous le compte Windows propriétaire avant de l'utiliser comme copie de travail à jour.
- Le tag stable doit rester immuable ; les travaux d'orchestration partiront sur une nouvelle branche et non par déplacement du tag.

## Update 2026-08-30 — orchestrateur Production V1 implémenté

### Works
- La branche `production-orchestrator-v1` ajoute un agrégat `ProductionJob` persistant et un journal borné qui conserve les projets/essais enfants KREA2 et H3, les sélections, scores, justifications, corrections, pauses et erreurs. Un redémarrage ne remplace pas les historiques KREA2/H3 existants.
- Le mode `full_auto` exécute : image source immuable comme inspiration du LLM KREA2 assisté → trois rendus T2I obtenus par itérations directes du prompt → sélection multimodale parmi les trois candidats → H3 Base I2VA `0.3.3` en trois appels Brief/Plan/Prompt → preview 0,2 MP → évaluation sur l'ancre et trois keyframes → révision bornée ou acceptation → nouveau rendu verrouillé à 1,2 MP avec la même seed.
- Le mode `human_review` suspend le même automate après la recommandation d'image et après l'évaluation vidéo. L'utilisateur peut remplacer la sélection, accepter le preview ou demander une correction, sans créer un second pipeline.
- Les appels LLM et les rendus enfants échoués sont retentés une fois. Les previews annulés par le garde thermique ne consomment pas le budget des previews réellement évalués ; quand la limite est atteinte, le meilleur score est retenu avec une décision `fallback` explicite.
- Un moniteur serveur Crystools lit désormais la température du GPU Comfy distant sans navigateur ouvert et l'agrège avec `nvidia-smi` local. Les seuils sont configurables ; les défauts sont arrêt à 85 °C, reprise sous 40 °C et stabilité/cooldown de 120 secondes. Les rendus KREA2/H3 appartenant au job sont annulés au seuil, puis recréés après refroidissement.
- Le nouveau menu `Production` expose source, intention, mode, modèles serveur/Unsloth/vLLM, checkpoint/ratio/MP/LoRA KREA2, liberté créative maximale par défaut, trois axes H3, budget de previews, musique et politique thermique. Le suivi affiche source/candidats, previews et scores, final, décisions et événements, avec bip terminal OK/KO.
- Validation : compilation Python complète, `git diff --check`, 13 tests ciblés verts et 643 tests complets verts en 75,743 secondes. Node.js n'est pas installé ; la structure UI est couverte par des tests statiques.

### Broken / missing
- Aucun smoke test réel n'a encore exécuté un job complet contre KREA2, le LLM sélectionné, ComfyUI H3 et les deux sources thermiques. La V1 a été validée avec les contrats réels et un test de chaîne simulé.
- Les appels LLM synchrones ne sont pas annulables en plein calcul : un dépassement thermique survenu pendant un appel est observé avant l'étape suivante. Les rendus ComfyUI, qui constituent les charges longues principales, sont surveillés et annulés activement.
- La V1 ne gère qu'un job actif lancé depuis l'interface ; le schéma est durable mais la future file nocturne multi-jobs, la priorité et la reprise automatique globale ne sont pas encore implémentées.

### Next steps
1. Lancer un job full-auto réel court avec télémétrie locale/distante disponible et vérifier les trois images, le choix LLM, le preview, la keyframe review et le final 1,2 MP.
2. Tester volontairement le mode validation humaine puis un seuil thermique abaissé pour qualifier pause, annulation ciblée, cooldown et reprise.
3. Ajuster les prompts de sélection/évaluation et les seuils de score à partir des premiers résultats qualitatifs avant de concevoir la file nocturne.

### Risks / open questions
- Une évaluation par keyframes ne prouve ni l'audio ni chaque mouvement intermédiaire. Les prompts d'arbitrage interdisent d'inventer ces preuves, mais la qualité du choix full-auto devra être mesurée sur des vidéos réelles.
- Le rendu final 1,2 MP recompile le graphe complet avec prompt, frames, seed et réglages verrouillés ; le workflow ne reprend pas encore directement le latent du preview 0,2 MP.
- Avec `pause_when_unavailable` activé par défaut, une source thermique absente maintient volontairement le job en pause jusqu'à son retour ou à une modification de la politique sur un nouveau job.

## Alignment 2026-08-30 — ressources thermiques et deux flux

### Current state
- Le garde thermique V1 est encore global : chaque étape vérifie simultanément le GPU local et le GPU Comfy distant, et `paused_thermal` suspend le job entier. Ce comportement est trop conservateur pour deux machines indépendantes.
- Les appels Unsloth/vLLM utilisent normalement le GPU local. KREA2 et H3 utilisent le GPU Comfy distant. Un modèle LLM de source `server` peut en revanche partager la machine distante et doit donc être routé vers sa ressource physique réelle.
- Plusieurs jobs peuvent actuellement démarrer dans des threads séparés, mais il n'existe ni ordonnanceur central, ni capacité par ressource, ni priorité FIFO explicite.

### Target
- Chaque opération déclare la ressource physique dont elle a besoin : au minimum `local_gpu` ou `remote_gpu`. La température, l'indisponibilité, le cooldown et l'annulation sont évalués uniquement sur cette ressource.
- Une ressource chaude bloque uniquement les tâches qui la réclament. L'autre machine reste disponible pour une tâche prête d'un autre job.
- Le futur ordonnanceur garde au plus deux jobs actifs. Il attribue des leases de capacité 1 par GPU, favorise le job le plus ancien et utilise le second de façon opportuniste quand une autre ressource est libre et froide. Une tâche déjà lancée n'est pas préemptée.
- Le cooldown minimal de 120 secondes concerne la lane vidéo distante entre deux générations vidéo. Les appels LLM locaux et les rendus image ne doivent pas attendre ce cooldown vidéo, sauf si leur propre ressource franchit son seuil thermique.

### Next steps
1. Remplacer le garde global par des `ComputeResource`, `ThermalGate` et `ResourceLease` indépendants, puis mapper chaque type de tâche et chaque source LLM.
2. Conserver le runner mono-job sur cette abstraction et exposer l'état des deux lanes dans le journal/UI, afin de valider le comportement sans introduire immédiatement une queue nocturne complète.
3. Ajouter ensuite l'ordonnanceur FIFO à deux jobs et ses tests de concurrence : vidéo distante du flux 1 + LLM local du flux 2, sans deux tâches simultanées sur le même GPU.

### Risks / open questions
- Les étapes d'un même job restent dépendantes : l'itération KREA2 suivante attend l'image précédente utilisée comme feedback. Le parallélisme utile apparaît donc surtout entre deux jobs, pas arbitrairement à l'intérieur d'un seul job.
- Les appels LLM OpenAI-compatibles ne sont pas préemptables aujourd'hui. Le scheduler peut empêcher leur démarrage sur un GPU chaud, mais un appel déjà parti termine avant de libérer sa lease.

## Update 2026-08-30 — lanes thermiques et concurrence Production

### Works
- L'orchestrateur Production déclare maintenant la ressource physique de chaque travail : `local_gpu` pour les modèles `local::`/`vllm::`, `remote_gpu` pour le LLM serveur par défaut et pour les rendus KREA2/H3. Le mapping du LLM serveur reste injectable dans `ProductionService`.
- La garde thermique ne lit plus que la télémétrie de la ressource demandée. Un GPU local chaud ou indisponible ne bloque donc plus KREA2/H3 sur le serveur, et un GPU serveur chaud ne bloque plus un appel LLM local.
- `ResourceLeaseManager` fournit une capacité FIFO non préemptive de 1 par GPU. Deux ressources différentes peuvent travailler simultanément, tandis que deux tâches visant le même GPU sont sérialisées.
- Le runner accepte au maximum deux jobs actifs, dans l'ordre d'arrivée. Le premier conserve la priorité d'accès FIFO ; le second peut utiliser opportunistement l'autre GPU. Une tâche déjà lancée n'est pas interrompue par une nouvelle demande du premier job.
- Le cooldown de 120 secondes est limité aux transitions entre rendus vidéo H3. Il réserve la lane distante pendant la descente sous le seuil de reprise et la période de stabilité, sans immobiliser la lane LLM locale. Les rendus image ne subissent pas ce cooldown vidéo.
- L'UI Production expose les deux lanes (`Disponible`, `Occupé`, `Trop chaud`, `Refroidissement`, `Indisponible`), leur température et l'opération propriétaire via `/api/production/resources`.
- La suite complète passe depuis la racine de branche : 650 tests verts en 77,187 s. Les 16 tests Production ciblés couvrent aussi l'isolation thermique, le parallélisme inter-GPU, le FIFO mono-GPU et la limite de deux jobs.

### Broken / missing
- La file nocturne multi-job avec réordonnancement, reprise planifiée et tableau de queue n'est pas encore construite ; ce patch fournit les primitives et la limite de deux runners concurrents.
- Les leases et les places actives sont volontairement en mémoire. Après redémarrage, les jobs restent durables mais doivent être remis en file ; aucune lease fantôme n'est restaurée.
- Un appel LLM OpenAI-compatible déjà envoyé ne dispose pas d'une annulation transport fiable : son seuil est vérifié avant départ, puis il libère sa lease à son retour. Les rendus ComfyUI restent surveillés et annulables pendant l'exécution.
- Node n'est pas installé dans l'environnement ; le nouvel encart UI est couvert statiquement et par la suite Web, mais pas encore par un smoke navigateur réel.

### Next steps (max 3)
1. Smoke tester deux jobs réels : H3/KREA2 distant sur le flux 1 pendant un appel vLLM local sur le flux 2, puis vérifier les états des lanes dans l'interface.
2. Ajouter la file nocturne durable (ordre, activation de deux jobs, reprise après redémarrage) au-dessus des primitives existantes, sans modifier les moteurs KREA2/H3.
3. Après mesure réelle, décider si les seuils doivent devenir distincts par machine au lieu de partager les valeurs 85/40 configurées par job.

### Risks / open questions
- Une phase de refroidissement distante bloque volontairement tout nouveau travail sur ce GPU afin qu'un second job ne l'empêche pas de redescendre sous 40 °C ; le GPU local reste libre.
- La priorité est FIFO et non préemptive : si le second job a déjà acquis une lane libre, le premier attend sa libération au lieu d'annuler une opération utile en cours.
- Les générations lancées manuellement hors de l'orchestrateur Production ne prennent pas encore ces leases applicatives ; ComfyUI conserve toutefois ses propres contraintes de queue.

## Audit 2026-08-30 — visibilité des décisions de l'orchestrateur

### Works
- `ProductionService` est l'orchestrateur déterministe : il choisit l'étape suivante et les services à appeler. Le LLM ne choisit pas librement ses tools ; il produit les prompts KREA2, sélectionne une image par JSON, construit les documents H3 et évalue les previews par keyframes.
- Les décisions d'image et de vidéo persistent déjà un score, une justification et une éventuelle instruction de révision. Le journal UI les affiche, mais il n'expose pas encore une chronologie complète de chaque direction créative LLM.

### Broken / missing
- L'audit du parcours réel a révélé un raccord incomplet dans `_build_h3_prompt` : Production génère le Brief puis demande directement `FINAL_PROMPT`, alors que la recette H3 Base directe exige d'abord un `BEAT_SHEET`/Plan JSON généré et approuvé. Le commentaire affirmant que `FINAL_PROMPT` produit ce Plan en interne ne correspond pas au contrat actuel de `PromptCompositionService`.
- Sans correctif, le parcours Production réel peut s'arrêter à la compilation H3 après la sélection d'image, même si les tests actuels à doubles simplifiés passent.

### Next steps (max 3)
1. Corriger Production pour exécuter explicitement Brief → Plan JSON → writer final, avec reprise idempotente de chaque document.
2. Ajouter un test d'intégration Production utilisant le vrai `PromptCompositionService`, et non uniquement le fake actuel.
3. Concevoir un panneau « Directions du modèle » fondé sur les sorties structurées déjà disponibles, sans exposer le chain-of-thought ni ajouter d'appel LLM.

### Risks / open questions
- Le nombre logique d'appels LLM du parcours nominal est de 8 avant le rendu final si le premier preview est accepté : 3 prompts KREA2, 1 sélection d'image, 3 étapes H3 et 1 évaluation vidéo. Chaque révision vidéo ajoute 2 appels ; chaque opération peut être retentée une fois en cas d'échec.

## Diagnostic 2026-08-30 — premier run Production réel

### Works
- Le job `production-c4b21544e15a418bb7af996b6b382304` a produit exactement trois images KREA2. Les appels LLM associés sont trois `krea2.assisted.creation_chat@0.3.0`, suivis d'un unique `production.image_select@0.1.0` une seconde après la fin du troisième rendu ; aucun retry caché ni doublon n'apparaît dans `llm_calls.json`.
- Le sélecteur a recommandé le candidat 2 avec un score de 88 et une justification persistée. En validation humaine, l'utilisateur a finalement choisi le candidat 3 ; la chaîne a bien respecté ce choix avant de démarrer `brief.structure`.

### Broken / missing
- Le job a échoué à l'étape `h3_prompt` avec `approve a current beat_sheet first`, ce qui confirme sur un run réel le raccord Plan JSON manquant identifié dans l'audit précédent.
- L'API/UI actuelle n'autorise pas la remise en file d'un job `failed`. Les projets KREA2, l'image choisie, la session Prompt Lab et le Brief restent persistés, mais il n'existe pas encore d'action sûre « Relancer cette étape ».
- Le catalogue LoRA persiste favoris, sécurité, précision et métadonnées CivitAI, mais aucune mémoire sémantique des effets, plages de force, compatibilités ou observations de rendu.

### Next steps (max 3)
1. Corriger le parcours H3 en Brief → Plan généré/approuvé → writer final, puis ajouter un test d'intégration avec les vrais services.
2. Ajouter une reprise idempotente de l'étape en échec : endpoint et bouton « Relancer cette étape », remise à `queued`, conservation des enfants valides et aucun rejeu des rendus KREA2.
3. Concevoir séparément un mode expérimental « Sélection LoRA assistée » avec profils sémantiques et observations versionnées, sans modifier le parcours stable par défaut.

### Risks / open questions
- Un simple retry du job actuel sans correctif reproduirait la même erreur structurelle ; le retry automatique doit distinguer erreurs transitoires et invariants de pipeline.
- Les résultats de runs ordinaires ne prouvent pas causalement l'effet d'une LoRA, car prompt, seed et autres LoRA peuvent changer. La mémoire doit séparer métadonnées déclarées, observations à faible confiance et essais A/B contrôlés.

## Alignment proposé 2026-08-30 — reprise Production, sélection visible et LoRA expérimental

### Current state
- Les vignettes Production sélectionnent un candidat mais n'ouvrent pas de visionneuse agrandie. La recommandation LLM est surtout visible dans le journal et le contrat `production.image_select@0.1.0` ne note que le candidat retenu, pas chaque image.
- Le choix recommandé et le choix humain sont bien conservés séparément dans l'agrégat, ce qui permet de les afficher sans ambiguïté.
- Le job réel en échec conserve ses trois rendus KREA2, son choix humain, sa session H3 et son Brief, mais il manque le Plan JSON et aucune action de reprise n'est exposée.
- Les réglages LoRA sont actuellement fixes pour les trois essais et le catalogue ne contient pas encore de profils d'effets ni d'observations exploitables par un LLM.

### Target
- Ajouter une visionneuse `object-fit: contain` pour la source et chaque candidat, tout en conservant une action distincte pour sélectionner un candidat.
- Faire retourner au même appel de sélection une note et un résumé pour chaque candidat, puis afficher un encart compact avec recommandation, scores, choix humain éventuel et un `<details>` pour l'analyse complète. Les anciens jobs restent lisibles sans inventer les scores absents.
- Corriger le raccord H3 en Brief → Plan JSON → Prompt final, rendre ces étapes idempotentes et ajouter `Relancer cette étape` sur un job en échec sans rejouer les trois rendus KREA2 ni perdre les documents valides.
- Ajouter une case désactivée par défaut `Sélection LoRA assistée (expérimental)`. Un appel Production dédié choisit une seule pile validée de 0 à 4 LoRA avant les trois essais ; les LoRA déjà renseignées par l'utilisateur restent verrouillées et le LLM ne remplit que les emplacements libres. La pile reste identique sur les trois rendus afin de préserver une comparaison utile.
- Persister séparément les profils déclarés (effets, déclencheurs, compatibilités, plage de force, risques) et les observations de jobs (réglages, score, choix, note, contexte), avec une confiance faible pour les runs non contrôlés. La mémoire est récupérée de façon bornée lors du futur choix LoRA ; elle ne constitue pas un apprentissage causal automatique.

### Next steps (max 3)
1. Implémenter et tester le raccord H3 idempotent ainsi que la reprise d'un job échoué.
2. Étendre le contrat de sélection, la persistance et l'UI de recommandation/visionneuse avec compatibilité des anciens jobs.
3. Ajouter le sélecteur LoRA expérimental, son allowlist stricte, sa mémoire versionnée et ses tests sans modifier le comportement par défaut.

### Risks / open questions
- Une note LLM est un jugement relatif aux candidats présentés, pas une mesure absolue de qualité ; l'interface doit l'indiquer comme score de recommandation.
- Le premier historique LoRA sera surtout observationnel et corrélé. Une future exploration A/B devra garder prompt, seed et pile constants pour produire des preuves plus fiables.

## Update 2026-08-30 — reprise H3, recommandation image et LoRA expérimental

### Works
- Production exécute désormais explicitement et de façon idempotente `Brief → Plan JSON → Prompt final` pour H3 Base 0.3.3. Chaque document déjà approuvé est réutilisé ; un candidat actif valide est approuvé sans nouvel appel, tandis qu'un candidat invalide est régénéré au maximum une fois par le retry LLM existant.
- Un job `failed` expose `POST /api/production/jobs/{job_id}/retry` et le bouton `Relancer cette étape`. La reprise remet uniquement l'étape courante en file, efface l'erreur terminale et conserve les rendus KREA2, le choix d'image, la session, les documents approuvés, les previews et le journal.
- Le sélecteur d'image `production.image_select@0.2.0` note maintenant chaque candidat exactement une fois et recommande séparément un essai. Les évaluations par candidat sont persistées de manière rétrocompatible dans `ProductionDecision`; les anciens jobs sans détail restent lisibles.
- L'UI Production affiche un encart de recommandation compact avec le score de chaque essai, le choix humain courant, un détail repliable et la justification finale. La recommandation LLM et la sélection humaine utilisent des états visuels distincts.
- La source et chaque image générée ouvrent une visionneuse native agrandie en `object-fit: contain`. La sélection humaine passe par un bouton séparé afin qu'un clic sur l'image n'écrase plus le choix.
- La case `Sélection LoRA assistée (expérimental)` est désactivée par défaut. Quand elle est active, un unique appel `production.lora_select@0.1.0` choisit uniquement parmi les LoRA installées, complète au plus les quatre emplacements, conserve les choix manuels comme valeurs verrouillées et applique une pile identique aux trois rendus.
- Le plan LoRA, les forces, les effets attendus et la justification sont persistés avec le job et visibles dans l'encart. La pile sélectionnée est aussi communiquée au prompteur KREA2 pour qu'il écrive un prompt cohérent sans inventer d'autre LoRA.
- `production_lora_memory.json` sépare profils déclarés, hypothèses du sélecteur et observations de rendu à confiance faible. Chaque candidat noté alimente les observations avec checkpoint, prompt, seed, pile, score et statut de sélection ; une sélection humaine ajoute une observation distincte.
- Validation finale : compilation Python, `git diff --check`, 39 tests ciblés et 655 tests complets verts en 82,978 secondes. Un test d'intégration utilise le vrai `PromptCompositionService` et le cookbook H3 Base 0.3.3 pour vérifier l'ordre Plan approuvé puis writer final.

### Broken / missing
- Aucun smoke test navigateur réel n'a encore validé la visionneuse `<dialog>`, les deux styles de sélection et le bouton de reprise sur le job utilisateur existant. Node.js reste absent, donc le JavaScript est couvert statiquement et par les tests Web mais pas par `node --check`.
- L'interface ne propose pas encore d'éditeur des profils LoRA déclarés. Le store possède le contrat durable pour les recevoir, mais la V1 expérimentale apprend surtout des hypothèses LLM et des observations corrélées.

### Next steps (max 3)
1. Redémarrer la branche et utiliser `Relancer cette étape` sur le job H3 échoué pour confirmer qu'il reprend au Plan sans recréer les trois images.
2. Lancer un job en validation humaine et vérifier dans le navigateur l'agrandissement, les trois scores, la recommandation et le remplacement manuel.
3. Lancer un petit job avec sélection LoRA assistée, puis contrôler le plan visible et `workspace/production_lora_memory.json` avant d'envisager une exploration A/B.

### Risks / open questions
- Les scores sont des jugements relatifs du LLM sur les candidats présentés, pas une métrique absolue de qualité.
- Les observations LoRA ordinaires restent confondues par les variations de prompt et de seed malgré la pile fixe. Elles sont donc injectées comme preuves à faible confiance ; une future mesure causale devra comparer à prompt et seed constants.
- Le catalogue transmis au sélecteur est borné aux 200 premières LoRA déjà classées par le catalogue. Si l'inventaire dépasse cette taille, une politique de recherche sémantique devra remplacer ce bornage.

## Update 2026-08-30 — troncature JSON de la sélection d'image Production

### Works
- Le diagnostic du job `production-bf1f8226640840ee891291a4a1e12e34` montre deux réponses `production.image_select@0.2.0` terminées avec `finish_reason=length` à exactement 2048 tokens. L'erreur `Expecting ',' delimiter` provenait donc d'un JSON coupé, pas d'une virgule isolée réparable localement.
- Le contrat `production.image_select@0.2.1` fournit maintenant la forme complète correspondant au nombre réel de candidats, exige des scores entiers de 0 à 100 et borne chaque résumé ainsi que la justification pour éviter la prose excessive.
- La première tentative de sélection dispose de 4096 tokens. Si le fournisseur signale encore `finish_reason=length`, la tentative bornée existante repart à 8192 tokens ; un second dépassement remonte une erreur explicite de réponse tronquée au lieu d'une erreur JSON trompeuse.
- La reprise reste idempotente : après redémarrage, `Relancer cette étape` reprend `image_selection` avec les trois rendus KREA2 existants et ne les régénère pas.
- Validation : 9 tests Production ciblés et 656 tests complets passent ; `git diff --check` ne signale aucune erreur de diff.

### Broken / missing
- Le job utilisateur n'a pas été relancé automatiquement : son appel au LLM local doit rester une action explicite après redémarrage de PanelForge.

### Next steps (max 3)
1. Redémarrer PanelForge sur `production-orchestrator-v1`, rouvrir le job en échec et cliquer sur `Relancer cette étape`.
2. Confirmer que l'encart affiche trois scores sur 100 et une recommandation avant la validation humaine.
3. Si le modèle atteint aussi 8192 tokens malgré les bornes de texte, inspecter sa configuration de raisonnement avant d'augmenter davantage le budget.

### Risks / open questions
- Le budget de secours n'est consommé que si la première réponse est rejetée ; il peut augmenter la latence du retry, mais évite de persister un JSON incomplet.
- Aucune réparation syntaxique n'est appliquée à une réponse tronquée : les scores ou justifications absents ne doivent pas être inventés par l'application.

## Diagnostic 2026-08-30 — steps H3 du flux Production

### Works
- Production réutilise bien le workflow H3 Base Latent Speed `0.1.1`, dont le preset publié conserve `25 steps`, et n'a pas modifié le graphe ComfyUI.
- Le flux conserve le même seed entre previews et rendu final, utilise l'image KREA2 retenue comme first frame, reprend son ratio, force la musique désactivée par défaut et produit la finale à 1.2 MP.

### Broken / missing
- Le nouveau `ProductionConfig` et le formulaire Production fixent actuellement `video_steps=10`; `_video_settings` transmet cette valeur aux previews 0.2 MP comme à la finale 1.2 MP. Ce défaut est incohérent avec le preset H3 publié à 25 steps.
- La durée 10 secondes, les previews à 0.2 MP, la limite de trois previews et le seuil d'acceptation LLM de 80/100 sont des choix propres à l'orchestrateur Production ; seuls les steps constituent ici l'écart non intentionnel identifié.

### Next steps (max 3)
1. Après accord utilisateur, remettre le défaut Production à 25 steps côté domaine, API et navigateur.
2. Exposer éventuellement les steps dans les réglages Production au lieu de les cacher, avec 25 par défaut.
3. Vérifier qu'un ancien job persisté à 10 steps reste lisible et conserve son réglage historique lors d'une reprise.

### Risks / open questions
- Modifier uniquement le défaut ne changera pas les jobs déjà créés, qui ont correctement persisté `video_steps=10`; une politique explicite est nécessaire si l'utilisateur veut migrer le job courant vers 25.

## Update 2026-08-30 — trace détaillée de la compilation H3 Production

### Works
- Production persiste maintenant un contrat d'entrée H3 explicite avant la compilation : mode `I2VA`, essai KREA2 utilisé comme `first frame`, absence de `last frame`, ratio, durée, steps, niveaux de qualité, seed et état de la musique.
- Chaque appel de la chaîne `Brief H3 → Plan JSON H3 → Prompt final H3` écrit un événement `thinking` avec modèle, numéro de tentative et heure, puis un événement de succès avec durée ou un rejet détaillé. Les documents déjà approuvés signalent clairement leur réutilisation sans nouvel appel LLM.
- `GET /api/production/jobs/{job_id}/h3-audit` expose les trois documents durables, la recette H3 exacte, le prompt H3 courant et le contrat de rendu. L'UI ajoute une carte « Trace de compilation H3 » avec les documents repliables.
- Chaque preview et la finale affichent le ratio, les mégapixels, les steps, la seed et le prompt effectif réellement envoyé au moteur. La finale affiche aussi sa résolution exacte.
- Le parcours Production courant est confirmé en `9:16 (Portrait Widescreen)` lorsque ce ratio est sélectionné : `_video_settings` le convertit directement vers `VideoAspectRatio` pour les previews et la finale.
- Validation : `git diff --check`, 11 tests Production/UI ciblés et la suite complète de 656 tests passent en 80,158 secondes.

### Broken / missing
- La chaîne de pensée privée brute n'est ni capturée ni affichée. `thinking` décrit l'état opérationnel, le modèle, les tentatives et les durées ; les artefacts auditables sont le Brief, le Plan JSON et les prompts finaux/effectifs.
- Aucun smoke test navigateur réel n'a encore validé la carte d'audit pendant un appel LLM lent. Node.js n'est pas installé, donc `node --check` n'a pas pu être exécuté ; la syntaxe et les sélecteurs sont couverts statiquement et via les tests Web.
- Les jobs existants créés à `10 steps` conservent volontairement cette valeur historique. Ce patch de traçabilité ne migre pas encore le défaut Production vers les `25 steps` du preset H3.

### Next steps (max 3)
1. Redémarrer PanelForge, lancer ou reprendre un job et vérifier visuellement la progression Brief/Plan/Prompt ainsi que les panneaux repliables.
2. Décider séparément si les nouveaux jobs Production doivent passer à 25 steps et si le champ doit être exposé dans le formulaire.
3. Si davantage d'audit est nécessaire, ajouter une vue filtrable par type d'appel sans persister de chain-of-thought privé.

### Risks / open questions
- Le contrat affiché reflète la configuration persistée du job ; il rend donc visibles les anciens choix à 10 steps au lieu de les corriger silencieusement.
- Les contenus Brief/Plan/Prompt peuvent être volumineux ; ils sont repliés par défaut pour préserver la lisibilité du journal.

## Update 2026-08-30 — UX Production, annulation et diagnostic Fantasy noire

### Works
- Le sélecteur « Image source immuable » affiche désormais immédiatement une preview locale en `object-fit: contain`, avec le nom du fichier tronqué proprement si nécessaire.
- Le polling Production ne reconstruit plus les balises `<video>` lorsque seuls le journal ou la trace LLM changent. Les previews et la finale utilisent une clé de rendu stable ; la lecture, la position et les contrôles du lecteur ne sont donc plus remis à zéro toutes les deux secondes.
- Le bouton `Annuler` est renommé `Arrêter le flux`. Il persiste un événement d'arrêt global, interrompt immédiatement un rendu Comfy KREA2/H3 actif, annule directement un job inactif/en attente de validation et empêche tout appel ou rendu suivant.
- Pour un appel LLM OpenAI-compatible synchrone déjà envoyé, le résultat est désormais rejeté dès son retour si l'arrêt a été demandé, avant toute étape suivante. L'UI précise honnêtement que le transport courant ne permet pas encore de couper de force la requête déjà en vol côté fournisseur.
- Le run `Fantasy noire` (`production-86ceaef39fea4c1c93a2f32b13dcb6aa`) est bien en I2VA 9:16, preview 0,2 MP, 10 steps et seed verrouillée. Les deux previews ont été notées 38 puis 42 : le cimetière disparaît vers 5 s, remplacé par des fonds beige/blancs et des lignes de vitesse.
- Le diagnostic montre une cause combinée. Les 10 steps, très inférieurs aux 25 du preset publié, aggravent fortement l'instabilité à 0,2 MP. Mais la frame KREA2 retenue était déjà en pleine charge/transformation avec main dominante, flou radial, speed streaks et arrière-plan volontairement flou ; le prompt H3 ajoutait une transformation translucide complexe et trois phases caméra (`pull.out`, statique, shake). Le décor abstrait n'était pas demandé, mais ces entrées favorisaient sa disparition.
- Une révision manuelle Production ne rejoue pas Brief, Plan et Writer. Elle utilise `h3.base.render.revision@0.2.0`, le prompt courant, les keyframes et la mémoire du projet. Sur le run `fantasy2`, deux appels de révision identiques ont été observés uniquement parce que le premier candidat a été rejeté (`camera directive 1 must use id camera_1`) puis retenté une fois ; l'évaluation de la nouvelle vidéo est ensuite un appel séparé `production.video_evaluate@0.1.0`.
- Les trois images KREA2 sont séquentielles : le premier prompt part de la source immuable, puis chaque prompt suivant reçoit l'image réussie précédente comme feedback. À la fin seulement, la source et les trois candidats sont comparés ensemble par le sélecteur.
- Validation : 37 tests ciblés et la suite complète de 657 tests passent en 91,349 secondes ; `git diff --check` ne signale aucune erreur de diff.

### Broken / missing
- L'annulation immédiate d'un appel LLM déjà en vol demanderait un transport réellement interruptible/streamé jusqu'au client OpenAI-compatible. Le flux PanelForge s'arrête bien après ce retour et n'enchaîne rien, mais le serveur LLM peut continuer à calculer jusque-là.
- La recherche KREA2 optimise actuellement les candidats pour représenter toute l'intention vidéo dans une image spectaculaire. Pour l'I2VA, cela peut produire une mauvaise first frame : action déjà commencée, flou de mouvement, afterimages et décor peu ancré.
- En mode validation humaine, une itération manuelle peut encore déclencher un appel de révision (avec au plus un retry de validation), le rendu H3, puis un appel d'évaluation visuelle distinct. Ce n'est pas un rejeu des trois documents H3, mais ce n'est pas non plus strictement un seul appel LLM total par boucle.

### Next steps (max 3)
1. Décider si le mode humain doit conserver l'évaluation LLM automatique après chaque nouveau preview ou devenir strictement « un appel de révision + rendu + validation humaine ».
2. Versionner la stratégie KREA2 Production pour rechercher une first frame stable avant l'action : décor net, sujet cohérent, sans speed lines, afterimages ni transformation déjà accomplie.
3. Passer séparément les nouveaux jobs Production à 25 steps par défaut, sans migrer silencieusement les anciens jobs persistés à 10.

### Risks / open questions
- Monter seulement à 25 steps devrait améliorer la cohérence, mais ne corrigera pas une first frame déjà conçue comme une image de climax ni des mouvements caméra contradictoires.
- Supprimer l'évaluation LLM en mode humain réduirait les appels et la latence, mais ferait aussi disparaître les scores, le diagnostic automatique et la recommandation de correction après chaque preview.

## Update 2026-08-30 — sélection sans plafond, vraie first frame et boucle d'évaluation

### Works
- Le sélecteur visuel Production passe en `production.image_select@0.2.2`. Ses deux tentatives bornées n'envoient plus aucun paramètre `max_tokens` : le client OpenAI-compatible omet entièrement ce champ lorsque la requête utilise `None`, même si la source LLM possède un plafond par défaut configuré pour les autres appels.
- `CompletionRequest`, la journalisation LLM et le stockage acceptent désormais explicitement `max_tokens=None`; le journal persiste alors `null`. Les appels existants conservent leurs limites numériques inchangées.
- Si le fournisseur renvoie malgré tout `finish_reason=length`, Production retente une fois sans plafond client puis signale clairement une limite fournisseur/contexte, au lieu d'annoncer une limite PanelForge de 8192 tokens.
- Les instructions KREA2 Production demandent maintenant une vraie first frame stable immédiatement avant l'action : identité, environnement, lumière et profondeur lisibles, sans transformation/climax déjà commencé, flou cinétique, speed lines, afterimages, états temporels dupliqués ni fond abstrait de remplacement. Les itérations conservent cette position pré-action tout en utilisant le rendu précédent comme feedback.
- Le sélecteur pénalise explicitement les candidats qui compressent toute l'intention vidéo dans une image de climax et favorise l'ancre pré-action cohérente avec un décor exploitable par l'I2VA.
- Les nouveaux jobs Production utilisent 25 steps par défaut dans le domaine, l'API et le navigateur. La lecture conserve le fallback historique à 10 pour les anciens fichiers qui n'avaient pas ce champ, et tout job qui a persisté 10 reste à 10 lors d'une reprise.
- L'évaluation visuelle automatique est conservée en validation humaine. Sa dernière `revision_instruction` de type `revise` préremplit la zone de correction ; l'utilisateur peut la modifier ou l'effacer. Le polling ne remplace pas un texte manuel en cours de saisie et une nouvelle recommandation remplace seulement l'ancienne suggestion automatique.
- Le cache de `production-lab.js` passe en `20260830.6`. Validation : 82 tests ciblés, 659 tests complets et `git diff --check` sans erreur.

### Broken / missing
- Aucun smoke test réel n'a encore confirmé la longueur effective choisie par vLLM lorsqu'aucun `max_tokens` n'est envoyé ni le préremplissage de la recommandation dans le navigateur.
- Node.js reste absent ; le JavaScript est couvert par les tests statiques/Web, pas par `node --check`.

### Next steps (max 3)
1. Redémarrer PanelForge et relancer l'étape `SÉLECTION IMAGE` du job en échec pour réutiliser les trois images avec le contrat `0.2.2` sans plafond client.
2. Créer un nouveau job afin de vérifier dans la trace H3 `25 steps` et d'observer que les trois candidats KREA2 sont bien des états pré-action.
3. En validation humaine, attendre une évaluation `revise`, vérifier son texte prérempli puis le modifier avant de demander une nouvelle itération.

### Risks / open questions
- L'absence de plafond client ne rend pas le contexte infini : vLLM et le modèle gardent leur fenêtre maximale et peuvent encore terminer par `length` si la configuration serveur leur impose une limite.
- La contrainte pré-action améliore l'ancrage I2VA mais peut produire des images volontairement moins spectaculaires ; la dynamique doit désormais être créée par H3, pas précomprimée dans KREA2.
- Les jobs déjà créés à 10 steps ne sont pas migrés automatiquement ; il faut un nouveau job pour obtenir le nouveau défaut de 25.

## Diagnostic 2026-08-30 — affichage 10 steps après le patch

### Works
- La carte H3 affiche la valeur réellement persistée dans le job, pas le défaut courant du formulaire.
- Le job visible `production-626a5327f72345ec96d54f2df8dcec02` (`Danseuse peinture`) a été créé à 14:33 avec `video_steps=10`, avant le passage du défaut à 25, puis repris à l'étape `h3_prompt`. Son affichage à 10 steps est donc exact.
- Les nouveaux jobs créés après redémarrage utilisent 25 steps ; une reprise conserve volontairement les paramètres historiques du job.

### Broken / missing
- Aucun défaut d'affichage identifié. Il n'existe pas encore d'action explicite pour migrer un job existant de 10 à 25 steps.

### Next steps (max 3)
1. Créer un nouveau job après redémarrage pour confirmer l'affichage à 25 steps.
2. Ajouter seulement si demandé une action explicite de changement de qualité sur un job existant, sans migration silencieuse.

### Risks / open questions
- Modifier silencieusement les steps pendant une reprise rendrait les previews d'un même job difficilement comparables et fausserait son historique de configuration.

## Update 2026-08-30 — sécurité LoRA et catalogue KREA2 dans Production

### Works
- Les nouveaux jobs Production refusent toute LoRA manuelle dont la force sort de `-1..1`; l'interface utilise les mêmes bornes et ramène une saisie hors plage à la borne correspondante au changement du champ.
- Le sélecteur expérimental passe en `production.lora_select@0.2.0` et exige explicitement une force inclusive entre `-1` et `1`. Une protection déterministe ramène malgré tout toute proposition LLM comprise dans l'ancien domaine `-20..20` vers `-1..1` et consigne cet ajustement dans la justification du plan.
- Le dernier raccord avant le rendu KREA2 rebornе aussi toutes les forces à `-1..1`. Les anciens jobs et souvenirs contenant par exemple `1.25` restent donc lisibles, mais une reprise ne peut plus envoyer plus de `1` à ComfyUI.
- Le menu de checkpoint Production réutilise maintenant `PanelForgeKrea2ResourceUi` : groupes Favoris/BF16/INT8/précision inconnue et noms complets en infobulle, comme Création assistée, Batch et Edit.
- Un encart `Organiser le catalogue KREA2` est intégré à Production. Il manipule les mêmes préférences persistées et partagées pour les checkpoints et LoRA ; les choix courants du formulaire sont conservés pendant l'actualisation du classement.
- Les listes LoRA Production utilisent elles aussi le classement partagé Favoris/SFW/NSFW/Non classés. Le cache de `production-lab.js` passe en `20260830.7`.
- Validation : 33 tests ciblés, 660 tests complets et `git diff --check` sans erreur.

### Broken / missing
- Aucun smoke test navigateur réel n'a encore vérifié l'ouverture du gestionnaire de catalogue dans la colonne Production et le reclassement immédiat du menu de checkpoints.
- Les écrans KREA2 historiques hors Production conservent volontairement leurs anciennes plages LoRA ; cette limitation `-1..1` concerne le nouvel orchestrateur Production demandé ici.

### Next steps (max 3)
1. Redémarrer PanelForge et vérifier que le checkpoint Production est regroupé selon le catalogue partagé.
2. Activer la sélection LoRA assistée sur un nouveau job et confirmer dans l'encart de recommandation qu'aucune force ne dépasse `1` en valeur absolue.
3. Après validation réelle, décider séparément si la plage `-1..1` doit être étendue aux anciens ateliers KREA2.

### Risks / open questions
- Une ancienne observation LoRA à force supérieure à `1` reste dans la mémoire pour l'audit, mais ne peut plus être réappliquée telle quelle par Production.
- Le gestionnaire partagé expose aussi l'organisation des LoRA, conformément au composant existant ; le besoin principal de ce patch reste le classement des checkpoints.

## Update 2026-08-30 — état Production intégré au moniteur global

### Works
- Le bandeau de ressources Production séparé a été supprimé. Les lignes `Serveur` et `Local` du moniteur global possèdent désormais une quatrième cellule qui affiche `Idle` ou `Busy · KREA2`, `Busy · H3_plan`, `Busy · H3_low` ou `Busy · H3_high`.
- `Busy` décrit exclusivement une ressource réservée par l'orchestrateur PanelForge. Les jauges VRAM/température restent des mesures physiques globales et peuvent donc être élevées alors que la file Production est `Idle`.
- Les identifiants techniques d'opération et d'attempt ne sont plus exposés dans le bandeau : le backend les compile en quatre phases stables selon le stage et le type de workload. L'identifiant du job reste disponible dans l'infobulle pour le diagnostic.
- Le moniteur global `/api/runtime/status` transporte maintenant les états de ressources Production. La température serveur continue d'utiliser le WebSocket Crystools rapide dans le navigateur, avec la lecture Crystools côté serveur de Production comme repli ; l'ancien cas `Temp —` en haut alors que Production affichait une température est ainsi couvert.
- Le polling redondant de `/api/production/resources` dans `production-lab.js` a été retiré. Le statut reste visible et actualisé dans toutes les vues par le polling global à une seconde.
- Le moniteur passe à 438 px sur écran large et conserve quatre colonnes adaptatives sur mobile. Les caches `lab.js`, `lab-core.js`, `lab.css` et `production-lab.js` sont renouvelés.
- Validation : 39 tests ciblés, 661 tests complets et `git diff --check` sans erreur.

### Broken / missing
- Aucun défaut automatisé connu. Node n'est pas installé dans l'environnement ; la syntaxe JavaScript est couverte par les tests statiques et Web, mais pas par `node --check`.
- Le rendu réel des quatre cellules et le repli de température Crystools doivent encore être confirmés dans le navigateur connecté aux deux machines.

### Next steps (max 3)
1. Redémarrer PanelForge et vérifier successivement un appel LLM local, un rendu KREA2, un preview H3 et le rendu final afin de voir les quatre libellés attendus.
2. Couper brièvement le relais WebSocket navigateur et confirmer que la température serveur reste renseignée par le repli REST Production.
3. Ajuster seulement la largeur de la quatrième cellule après observation sur la résolution réelle si un libellé est tronqué.

### Risks / open questions
- La lecture Production côté serveur de Crystools peut prendre jusqu'au timeout configuré lorsque le plugin distant est indisponible ; l'endpoint runtime masque cette panne et conserve les autres données partielles.
- Une forte VRAM ou une température élevée provoquée par un programme externe n'affiche pas `Busy`, car aucune ressource Production n'est alors réservée. C'est volontaire : les jauges décrivent le GPU, `Idle/Busy` décrit uniquement l'orchestrateur.

## Update 2026-08-30 — activité globale hors Production

### Works
- Le constat utilisateur était exact : la première version de `Idle/Busy` ne suivait que les leases de l'orchestrateur Production. Les ateliers historiques appelaient directement le gateway LLM et ComfyUI, donc Création assistée restait faussement `Idle`.
- `LoggedMultimodalGateway` expose maintenant, sous verrou et sans contenu de prompt, les appels réellement actifs avec leur source physique (`server`, `local` ou `vllm`) et leur `operation_id`. Les appels synchrones, streamés, réussis, échoués ou interrompus sont toujours retirés dans un `finally`.
- `/api/runtime/status` expose ces appels ainsi que les activités de la file ComfyUI, classées à partir du `client_id` : `KREA2`, `H3` ou fallback `Comfy`. Les opérations LLM sont condensées en `KREA2`, `H3_plan` ou fallback `LLM`.
- Le bandeau fusionne les trois signaux avec priorité au lease Production précis. Hors Production, Création assistée affiche désormais `LOCAL Busy · KREA2` pendant un prompt vLLM local, puis `SERVEUR Busy · KREA2` pendant son rendu ComfyUI.
- La généralisation couvre aussi Générer/Batch/Edit KREA2, H3 Base, Ref2V, Video Lab et Social Lab. Une activité inconnue reste honnêtement nommée `LLM` ou `Comfy` plutôt que d'être attribuée à tort.
- Les identifiants DOM ont été renommés `runtime-server-activity` et `runtime-local-activity`; le cache `lab.js` passe en `20260830.4`.
- Validation : 41 tests ciblés, 663 tests complets et `git diff --check` sans erreur.

### Broken / missing
- Aucun défaut automatisé connu. Le changement doit encore être observé dans le navigateur pendant un vrai échange puis un vrai rendu Création assistée.
- Un travail ComfyUI lancé par un client externe sans `client_id` PanelForge apparaît volontairement comme `Busy · Comfy`, sans recette inventée.

### Next steps (max 3)
1. Redémarrer PanelForge, lancer un affinage KREA assisté sur vLLM local et confirmer `LOCAL Busy · KREA2`.
2. Lancer ensuite le rendu de l'image et confirmer le basculement vers `SERVEUR Busy · KREA2`, puis le retour à `Idle`.
3. Vérifier une génération H3 hors Production pour confirmer `H3_plan` pendant les appels LLM et `H3` pendant ComfyUI.

### Risks / open questions
- La file ComfyUI est échantillonnée chaque seconde : un travail extrêmement court peut commencer et finir entre deux lectures sans être visible. Les rendus image/vidéo usuels sont suffisamment longs pour être observés.
- Plusieurs activités simultanées hors Production sur la même machine sont concaténées avec `+`; le bandeau reste synthétique et les détails complets demeurent dans les journaux propres aux ateliers.

## Update 2026-08-30 — Direction créative H3 mono-plan 0.1.0

### Works
- H3 Base mono-plan et Production proposent désormais une case `Direction créative` expérimentale, décochée par défaut. Les parcours existants et le mode standard conservent donc strictement leur comportement antérieur.
- L'activation sélectionne une variante versionnée `creative-direction@0.1.0` uniquement pour le Brief. Elle demande au LLM de choisir une progression visuelle plus ambitieuse dans les limites des trois axes existants, sans ajouter spontanément dialogue, musique, nouveau personnage, coupe ou changement de lieu.
- Le Plan JSON et le Writer final restent compilés par la recette H3 Base standard `0.3.3`; la variante créative n'est pas une nouvelle recette vidéo complète.
- Dans H3 Base, le choix peut être modifié tant qu'aucun Brief n'existe, puis il est verrouillé afin que l'historique reste explicable. Production persiste le choix dès la création du job.
- La session, les forks, le stockage, l'API, les traces Production et l'audit H3 exposent la variante de Brief. Les anciens fichiers de sessions (schémas 1 à 6) et les anciens jobs sont relus en mode standard.
- Validation : 668 tests complets réussis et `git diff --check` sans erreur de whitespace. Node.js reste absent ; le JavaScript est couvert par les tests statiques/Web, pas par `node --check`.

### Broken / missing
- La direction créative est volontairement limitée au mono-plan. Elle n'est affichée ni pour le multi-plan structuré ni pour l'interview animale.
- Aucun test réel avec le modèle local n'a encore évalué le niveau d'initiative obtenu par `creative-direction@0.1.0`.

### Next steps (max 3)
1. Redémarrer PanelForge et comparer une même intention H3 Base mono-plan avec la case désactivée puis activée, à axes identiques.
2. Tester Production avec la direction créative activée et vérifier dans la trace `Brief : direction créative 0.1.0` puis `Plan/Writer : standard 0.3.3`.
3. Ajuster le prompt versionné seulement après plusieurs comparaisons réelles, sans modifier la recette standard.

### Risks / open questions
- Un axe réglé à `0` interdit volontairement les ajouts de cette catégorie ; cocher le mode sans ouvrir les axes produit donc une direction plus structurée mais peu d'initiatives nouvelles.
- La créativité reste contrainte par la durée, les ancres et la faisabilité physique afin de ne pas réintroduire les freezes ou les fins tenues corrigés dans H3 Base.

## Diagnostic 2026-08-30 — premier run Direction créative 0.1.0

### Works
- Le dernier parcours H3 Base `prompt-73592d30971b4a67a9f82a7a13011e85` a bien utilisé `creative-direction@0.1.0` avec les trois axes au maximum (`scene_life=3`, `camera=3`, `extra_motion=3`).
- Le Brief a ajouté une chorégraphie physiquement lisible : main vers le guidon, pied vers le repose-pied, redressement puis inclinaison du buste, montée des phares, vibration et embrasement du moteur, cheveux et jupe dans le flux d'air.
- La vie de scène et la caméra sont présentes : pluie continue, reflets néon, projections d'eau, traînées lumineuses et grand arc de face vers trois-quarts arrière. Le Plan et le Writer ont conservé ces apports ainsi que le mouvement continu à la coupure.

### Broken / missing
- Pour un maximum `3/3/3`, la proposition reste prudente : presque tous les ajouts sont des transitions attendues pour relier les deux frames et réaliser le départ de la moto.
- Aucun motif visuel distinctif ou événement surprenant propre à cette scène cyberpunk n'a été retenu. L'axe sensuel de l'intention est décrit par l'apparence, mais peu exploité dans la gestuelle ou la mise en scène.
- Le grand arc est utile, mais il répond aussi mécaniquement au passage d'une frame frontale à une frame arrière ; ce n'est donc pas une initiative créative entièrement nouvelle.

### Next steps (max 3)
1. Classer ce premier essai comme créativité moyenne : forte cohérence, initiative limitée.
2. Comparer encore deux ou trois scènes avant de modifier `0.1.0`, afin de distinguer un biais récurrent d'un cas fortement contraint par deux ancres.
3. Si le biais se confirme, renforcer uniquement le Brief expérimental pour exiger, à axes élevés, au moins une idée-signature compatible avec le thème et non nécessaire à la simple interpolation.

### Risks / open questions
- Les deux frames très directives réduisent naturellement l'espace créatif : le LLM consacre une partie importante du plan à construire une transition fiable entre elles.
- Exiger trop tôt une idée-signature systématique pourrait surcharger dix secondes ou concurrencer le mouvement principal ; elle devra rester subordonnée et visuellement simple.

## Design 2026-08-30 — axe d'audace créative proposé

### Works
- La case `Direction créative` sélectionne aujourd'hui le Brief expérimental ; elle ne représente pas une intensité.
- Les trois curseurs existants définissent les terrains dans lesquels le LLM est autorisé à enrichir la scène (`vie de la scène`, `caméra`, `mouvements additionnels`). Ils répondent à « où ajouter ? », pas à « à quel point proposer une idée inattendue ? ».

### Broken / missing
- Aucun paramètre explicite ne fixe actuellement un objectif de nouveauté, d'initiative ou d'idée-signature. Même avec les trois permissions au maximum, le LLM peut donc choisir uniquement des enrichissements prudents.

### Next steps (max 3)
1. Si validé, ajouter au Brief expérimental un quatrième curseur `Audace créative` ou `Initiative visuelle`, distinct des trois permissions.
2. Définir une échelle 0 à 3 : aucune initiative, enrichissement discret, une idée-signature mémorable, une idée-signature forte avec au plus un soutien cohérent.
3. Garder Plan et Writer standards ; le nouvel axe ne doit agir que sur la sélection créative du Brief.

### Risks / open questions
- Le niveau maximal ne doit pas signifier « multiplier toutes les actions » : il doit augmenter l'originalité de la direction retenue, avec une ou deux idées fortes au maximum.
- Le libellé `surprise` seul peut encourager l'aléatoire ; `Audace créative` ou `Initiative visuelle` exprime mieux une nouveauté thématique et contrôlée.

## Update 2026-08-30 — slider Audace créative et Brief 0.2.0

### Works
- H3 Base mono-plan affiche désormais un quatrième curseur `Audace créative` de 0 à 3, distinct des permissions `Vie de la scène`, `Caméra` et `Mouvements additionnels`. Il est visible uniquement lorsque la variante créative mono-plan est disponible, désactivé tant que la case n'est pas cochée, puis verrouillé avec les autres entrées après création du Brief.
- L'échelle est explicite : 0 aucune initiative, 1 enrichissement discret facultatif, 2 exactement une idée-signature mémorable, 3 une idée-signature forte avec au plus un effet de soutien. Le maximum ne constitue jamais un quota d'actions.
- Les nouveaux parcours utilisent la variante versionnée `creative-direction@0.2.0`; `0.1.0` reste intacte et chargeable pour préserver l'audit des anciens runs. Plan JSON et Writer restent en recette standard H3 Base `0.3.3`.
- Le niveau est transmis seulement au Brief initial, conservé lors des éditions/révisions, persisté dans chaque révision et exposé par l'API. Le schéma de session passe à 8 ; les schémas 1 à 7 restent lisibles, et un ancien Brief créatif sans niveau explicite migre à l'audace prudente 1.
- Production remplace son ancien slider global 0–100 sans effet réel par le même curseur 0–3, à 2 par défaut. Le job, le journal et l'audit H3 enregistrent l'audace ; un ancien job créatif migre à 1 et un ancien job standard à 0.
- Les nouveaux prompts précisent que l'idée-signature doit être thématique, non nécessaire à la simple interpolation des frames, compatible avec un axe autorisé et subordonnée au mouvement principal. Si les trois axes valent 0, leurs interdictions priment.
- Validation : 670 tests complets réussis et `git diff --check` sans erreur de whitespace. Node.js reste absent ; le JavaScript est couvert par les tests statiques/Web, pas par `node --check`.

### Broken / missing
- Aucun smoke test navigateur réel n'a encore confirmé le rendu visuel du nouveau curseur et la qualité d'un Brief généré à audace 2 ou 3.
- Ref2V, multi-plan et interview animale ne reçoivent volontairement pas ce réglage ; le périmètre reste H3 Base mono-plan et Production.

### Next steps (max 3)
1. Redémarrer PanelForge, cocher Direction créative et comparer la même scène à audace 1, 2 puis 3 avec les trois permissions constantes.
2. Vérifier dans l'en-tête de session ou l'audit Production le libellé `Brief 0.2.0 · audace N/3`.
3. Évaluer si les idées-signatures proposées restent lisibles en dix secondes avant de modifier le calibrage du prompt 0.2.0.

### Risks / open questions
- Une audace 2 ou 3 avec les trois permissions à 0 ne peut produire aucune idée-signature ; l'interface laisse cette combinaison possible afin que les interdictions explicites restent prioritaires.
- Deux frames très directives peuvent limiter la nature de l'idée-signature, mais le niveau 2 ou 3 exige désormais qu'elle ne soit pas une simple transition mécanique entre les ancres.

## Design 2026-08-30 — variante MiniMax H3 avec un LoRA vidéo

### Works
- Le workflow utilisateur `video_minimax_h3_i2v speed up porn.json` confirme le branchement attendu : le modèle et le CLIP passent dans `Power Lora Loader (rgthree)`, la sortie modèle rejoint ensuite la chaîne MiniMax, et la sortie CLIP passe par `CLIP Set Last Layer` à `-2` avant le conditionnement H3.
- Ce workflow n'est pas un remplacement sûr de la recette H3 Base actuelle : sa topologie d'échantillonnage et d'upscale diffère. Le changement minimal consiste à conserver intégralement le workflow PanelForge publié et à n'ajouter que cette branche LoRA/CLIP dans une variante versionnée.
- La recette Ref2V actuelle possède les mêmes points d'insertion. Sa sortie `MiniMaxH3HybridLoader` peut alimenter la branche modèle du LoRA avant `MiniMaxH3SigmaShift`, et la sortie `CLIPLoader` peut alimenter la branche CLIP du LoRA puis `CLIP Set Last Layer` avant `MiniMaxH3ReferenceToVideo`.
- ComfyUI expose déjà l'inventaire générique par `/models/loras`. Le catalogue KREA2 existant ne convient pas tel quel, car il ignore volontairement les chemins hors du préfixe `krea2/`; un inventaire H3 filtré sur `minmax_nsfw/` est donc nécessaire.

### Broken / missing
- H3 Render ne transporte actuellement ni choix de profil LoRA, ni nom, ni force, ni réglage CLIP dans le domaine, l'API, le stockage des attempts ou le compilateur de workflow.
- Aucune variante H3 Base ou Ref2V publiée ne contient encore le nœud LoRA et le branchement CLIP `-2`.
- Le workflow fourni prouve `-2` pour la configuration testée, mais ne permet pas d'affirmer que tous les LoRA présents dans `minmax_nsfw/` exigent ce réglage.

### Next steps (max 3)
1. Ajouter un profil de rendu expérimental H3 Base `LoRA MiniMax`, avec un seul fichier filtré sur `minmax_nsfw/`, force `0..1` et compatibilité CLIP `-2` activée par défaut.
2. Publier une variante versionnée du workflow H3 Base actuel qui ne modifie que la branche modèle/CLIP, puis persister et afficher ces paramètres dans chaque attempt afin de préserver reprise et audit.
3. Réutiliser le même contrat de sélection dans une variante Ref2V distincte, après validation réelle du premier rendu H3 Base.

### Risks / open questions
- Un mode `Aucun` dans la variante ne doit pas laisser `CLIP Set Last Layer -2` actif silencieusement ; l'absence de LoRA doit sélectionner la recette standard inchangée.
- Le réglage `-2` devrait rester visible comme option avancée ou être attaché à une mémoire de compatibilité par LoRA si les essais montrent que certains fichiers doivent conserver le CLIP standard.
- Le chemin LoRA doit être validé contre l'inventaire ComfyUI et le préfixe autorisé, sans accepter un chemin libre envoyé par le navigateur.

## Clarification 2026-08-30 — différences du workflow H3 LoRA fourni

### Works
- La recette H3 Base PanelForge `0.1.1` effectue une passe initiale fixe à `0.2 MP` avec un scheduler beta à `25` steps, sépare le latent audio/vidéo, upscale le latent vidéo vers la résolution cible (par défaut `1.2 MP`), puis applique une seconde passe de raffinement avec les sigmas fixes `0.9035, 0.6316, 0.3158, 0.0000`.
- Le workflow utilisateur effectue une seule génération H3 directe à `0.6 MP` avec un scheduler beta à `32` steps et ne contient pas `MinimaxH3LatentUpscaler3D` ni deuxième sampler de raffinement.
- Les deux utilisent le même UNET MiniMax H3, le même CLIP int8 convrot, le sampler `res_multistep`, les mêmes shifts vidéo/audio et le même backend d'attention.
- Une autre différence indépendante du LoRA est que Spectrum est désactivé dans PanelForge et activé dans le workflow fourni.

### Broken / missing
- Aucun : cette comparaison est un diagnostic de graphe, pas une modification du rendu.

### Next steps (max 3)
1. Conserver la chaîne PanelForge à deux passes pour la variante initiale et y greffer uniquement le LoRA et, si activé, `CLIP Set Last Layer -2`.
2. Ne comparer le workflow direct `0.6 MP / 32 steps / Spectrum ON` que dans une expérimentation séparée afin de ne pas confondre l'effet du LoRA avec celui du sampling.

### Risks / open questions
- Reprendre tout le workflow fourni changerait simultanément le LoRA, la résolution de génération, le nombre de passes, les steps et Spectrum ; un écart de résultat ne pourrait alors plus être attribué au LoRA seul.

## Alignment 2026-08-30 — emplacement du profil LoRA H3

### Works
- La modification validée conserve exactement la recette H3 Base PanelForge : passe initiale `0.2 MP / 25 steps`, upscale latent vers la cible, raffinement final et Spectrum désactivé.
- La variante ajoute seulement deux nœuds : `Power Lora Loader (rgthree)` entre l'UNET/CLIP et leurs consommateurs, puis `CLIP Set Last Layer` entre la sortie CLIP du LoRA et les deux conditionnements H3 basse et haute résolution.
- Le contrôle doit être placé dans H3 Base, dans le module `Créer et ajuster la vidéo` et ses paramètres du prochain rendu. Il concerne le rendu ComfyUI, pas le Brief, le Plan, le Writer ou les échanges de révision du prompt.

### Broken / missing
- L'interface, la persistance des attempts et la variante versionnée ne sont pas encore implémentées.

### Next steps (max 3)
1. Ajouter dans H3 Base un profil `Standard` par défaut et un profil expérimental `LoRA MiniMax`, qui révèle un sélecteur filtré `minmax_nsfw/`, une force et l'option CLIP `-2`.
2. Garantir que `Standard` compile le workflow actuel sans aucun changement de nœud ou de liaison.
3. Après validation H3 Base, répliquer le contrat d'interface et de persistance dans Ref2V avec son propre branchement de graphe.

### Risks / open questions
- Les anciens attempts doivent rester relisibles et reproductibles comme rendus standards ; aucun défaut de migration ne doit activer un LoRA.

## Alignment 2026-08-30 — profil LoRA vidéo dans Production

### Works
- Production appelle déjà la même instance de `H3RenderService` que l'atelier H3 Base pour préparer et exécuter ses previews et son rendu final. La compilation LoRA peut donc être partagée sans deuxième implémentation du graphe.
- Le LoRA expérimental déjà présent dans Production concerne uniquement les images KREA2 ; il est distinct du futur LoRA vidéo MiniMax H3.

### Broken / missing
- `ProductionConfig` ne contient actuellement aucun profil de rendu H3, nom de LoRA vidéo, force ou réglage CLIP. Les appels `prepare_attempt` de Production transmettent seulement prompt, réglages vidéo et musique ; une implémentation limitée à l'interface H3 Base laisserait donc Production en mode standard.

### Next steps (max 3)
1. Étendre le même patch avec une section `LoRA vidéo H3` dans la configuration Production, désactivée par défaut, avec le même inventaire filtré, la même force et le même réglage CLIP.
2. Appliquer et persister la sélection identique sur tous les previews `H3_low` et sur le rendu `H3_high` du job.
3. Migrer tous les anciens jobs vers `Standard` et distinguer clairement dans l'audit les LoRA KREA2 image des LoRA MiniMax H3 vidéo.

### Risks / open questions
- Changer de LoRA entre preview et final invaliderait la comparaison visuelle ; le réglage vidéo doit donc être verrouillé au niveau du job, sauf reprise explicitement reconfigurée.

## Audit 2026-08-30 — slider Audace créative avant snapshot GitHub

### Works
- Le slider est borné et validé de bout en bout sur l'échelle entière `0..3` dans le domaine, l'application et les formulaires Web. Une valeur booléenne ou hors plage est rejetée.
- L'audace est transmise exclusivement aux prompts du Brief `creative-direction@0.2.0`. Le Plan JSON et le Writer final continuent d'utiliser la recette standard H3 Base `0.3.3` et ne reçoivent aucun nouveau paramètre d'audace.
- Les éditions manuelles et révisions LLM du Brief conservent la valeur initiale. L'interface compare la valeur affichée à celle du Brief et verrouille le choix après génération afin d'éviter une divergence silencieuse.
- Le stockage de session version 8 persiste la valeur. Les sessions créatives de schéma 7 migrent à l'audace prudente `1`; les sessions standards plus anciennes migrent à `0`.
- Production sélectionne la variante de Brief seulement lorsque la case est activée, journalise sa version et son audace, et conserve Plan/Writer standards. Les anciens jobs créatifs sans champ migrent à `1` et les autres à `0`.
- Validation : 66 tests ciblés puis 670 tests complets réussis en 83 secondes ; `git diff --check` ne signale aucune erreur de whitespace. Le premier lancement ciblé avait importé l'installation `D:\Code\panelforge` au lieu du worktree ; il a été écarté et relancé avec `PYTHONPATH` fixé sur `.panelpatch/src`.

### Broken / missing
- Aucun défaut fonctionnel détecté par l'audit ou les tests automatisés.
- Aucun smoke test navigateur réel ni comparaison de génération aux quatre niveaux n'a encore été effectué depuis l'ajout du slider.

### Next steps (max 3)
1. Figer cette version sur la branche `production-orchestrator-v1` et la publier sur GitHub avant l'évolution LoRA vidéo.
2. Comparer une intention identique aux niveaux 0, 1, 2 et 3 avec les mêmes frames et axes afin de confirmer le calibrage qualitatif.
3. Implémenter ensuite le profil LoRA vidéo H3 Base/Production validé dans les sections de design précédentes.

### Risks / open questions
- Le dernier impératif de `brief_user.txt` emploie encore « direction créative mono-plan forte » quel que soit le niveau. Les règles système et la politique injectée définissent ensuite précisément 0–3 et restent prioritaires ; le point est non bloquant, mais pourra être reformulé dans une future version de prompt si les essais montrent une audace excessive aux niveaux 0–1.

## Update 2026-08-30 — profil LoRA vidéo MiniMax H3 Base et Production

### Works
- La branche de travail est `h3-video-lora`. La recette H3 Base active passe à `minimax-h3-latent-speed@0.1.2`; son graphe est identique à `0.1.1` avant l'overlay dynamique (seule la fin de fichier JSON a été normalisée, SHA-256 `5a7e6e2283ee91764b785e520aa7c7b3f0002de98ba1c48e703c807e5e39c78a`). La `0.1.1` publiée reste intacte, chargeable et Standard uniquement.
- Le profil `Standard` compile toujours le graphe original sans nouveau nœud ni liaison. Le profil expérimental `LoRA MiniMax` injecte uniquement `Power Lora Loader (rgthree)` entre l'UNET/CLIP et leurs consommateurs, puis `CLIPSetLastLayer -2` sur la branche CLIP si l'option est cochée. La passe 0,2 MP à 25 steps, l'upscale latent vers 1,2 MP, le raffinement final et Spectrum OFF ne changent pas.
- L'inventaire est découvert via ComfyUI puis filtré sur `minmax_nsfw/*.safetensors`. Un seul LoRA est accepté, avec force bornée à `0..1`, défaut `0.5`, et CLIP `-2` activé par défaut. Le chemin est revalidé contre l'inventaire au moment de préparer un rendu; une panne d'inventaire ne bloque jamais le profil Standard.
- H3 Base expose le profil dans `Créer et ajuster la vidéo`, restaure ses réglages depuis un ancien essai et affiche LoRA, force et CLIP dans l'historique. Les attempts persistés passent au schéma 2; le schéma 1 reste lisible et migre vers Standard.
- Production expose une section distincte `LoRA vidéo H3`, séparée des LoRA image KREA2. La sélection est enregistrée dans le job puis réutilisée sans variation sur chaque preview `H3_low` et sur le final `H3_high`; contrat H3, journal et audit l'affichent. Les jobs passent au schéma 2 et les jobs schéma 1 restent lisibles en Standard.
- Ref2V reste volontairement hors périmètre de cette première validation et refuse un LoRA vidéo au backend. L'API l'indique sans exposer de contrôle trompeur.
- Validation finale : 676 tests complets réussis en 82 secondes, compilation Python réussie et `git diff --check` propre. Node.js n'est toujours pas installé; le JavaScript est couvert par les tests statiques/Web.

### Broken / missing
- Aucun rendu ComfyUI réel n'a encore validé les deux nouveaux nœuds avec les LoRA présents sur le serveur. Les contrats du graphe correspondent au workflow utilisateur fourni, mais le smoke test GPU reste à faire.
- Ref2V ne propose pas encore de LoRA vidéo; son adaptation est reportée après validation qualitative et technique de H3 Base.

### Next steps (max 3)
1. Redémarrer PanelForge sur `h3-video-lora`, vérifier que les fichiers de `minmax_nsfw/` apparaissent, puis comparer un rendu H3 Base Standard et LoRA avec prompt, seed et réglages identiques.
2. Tester le même LoRA dans Production et confirmer dans la trace que preview 0,2 MP et final 1,2 MP conservent exactement le même nom, la même force et le même réglage CLIP.
3. Après validation réelle, créer une recette Ref2V versionnée avec son propre binding LoRA/CLIP, sans modifier le workflow Ref2V publié actuel.

### Risks / open questions
- Le nœud `Power Lora Loader (rgthree)` et `CLIPSetLastLayer` doivent être présents sous les mêmes `class_type` dans le ComfyUI distant; sinon ComfyUI refusera le workflow avec une erreur de nœud explicite.
- Certains LoRA pourraient ne pas nécessiter CLIP `-2`; l'option reste donc visible et désactivable par essai au lieu d'être imposée globalement.
- Un LoRA supprimé ou renommé après un ancien essai reste visible dans l'historique, mais sa relance est volontairement refusée tant qu'il n'est plus déclaré par l'inventaire ComfyUI.

## Publication 2026-08-30 — snapshot avant LoRA vidéo

### Works
- Le snapshot applicatif audité est le commit `e11f3efc92d3ffe7517dae93ad0876a3563e71a2` sur la branche `production-orchestrator-v1`.
- Le tag annoté `stable-production-orchestrator-audacity-2026-08-30` pointe sur ce commit.
- La branche et le tag ont été publiés avec succès sur `https://github.com/EasyFrag/panelforge.git` après confirmation explicite de l'utilisateur.

### Broken / missing
- Aucun échec de publication connu.

### Next steps (max 3)
1. Conserver le tag stable comme point de retour avant l'évolution LoRA vidéo.
2. Implémenter le profil LoRA MiniMax partagé par H3 Base et Production, puis l'étendre à Ref2V après validation réelle.
3. Comparer séparément les quatre niveaux d'audace sur une même scène lorsque des essais qualitatifs seront disponibles.

### Risks / open questions
- La branche de travail pourra avancer avec le patch LoRA ; le tag stable doit rester immuable sur `e11f3ef`.

## Current handoff 2026-08-30 — branche `h3-video-lora`

### Works
- L'évolution LoRA vidéo décrite dans la section précédente est implémentée sur `h3-video-lora`, avec recette active H3 Base `0.1.2`, H3 Base et Production couverts, migrations legacy testées et 676 tests verts.

### Broken / missing
- Le smoke test ComfyUI réel reste à exécuter; Ref2V reste volontairement Standard uniquement.

### Next steps (max 3)
1. Redémarrer la branche et comparer Standard/LoRA dans H3 Base à prompt et seed identiques.
2. Valider ensuite que Production conserve le même LoRA entre preview et final.
3. N'ouvrir l'évolution Ref2V qu'après ces deux validations.

### Risks / open questions
- La disponibilité réelle des `class_type` rgthree/CLIP et la compatibilité de chaque LoRA avec CLIP `-2` doivent être confirmées sur le serveur ComfyUI.

## Design en discussion 2026-08-31 - modèle LLM de révision

### Works
- H3 Render conserve actuellement le modèle du parcours initial dans `project.model_id`; KREA2 Assisted fait de même. La recette de révision H3 est déjà sélectionnable indépendamment du parcours initial.

### Broken / missing
- Aucun des deux chats ne permet encore de choisir un autre modèle pour un ajustement sans changer le modèle historique du projet.

### Next steps (max 3)
1. Ajouter un sélecteur de modèle dans `Ajuster avec le LLM` pour H3 Base/Ref2V et dans la conversation KREA2 Assisted.
2. Conserver le modèle initial immuable, persister une préférence de révision séparée et tracer le modèle effectivement utilisé sur chaque tour.
3. Faire porter le choix uniquement sur les appels directs de révision, sans rejouer Brief, Plan ou Prompt initial.

### Risks / open questions
- Le sélecteur doit restaurer un ancien modèle même s'il est momentanément absent du catalogue, sans rerouter silencieusement l'appel vers un autre fournisseur.

## Update 2026-08-31 - modèle LLM de révision sélectionnable

### Works
- H3 Base, Ref2V et KREA2 Création assistée proposent maintenant un sélecteur LLM dans leur zone d'ajustement. Le choix ne concerne que le prochain appel direct de révision : il ne rejoue ni Brief, ni Plan, ni génération initiale.
- Le modèle initial du projet reste immuable dans `model_id`. Une préférence distincte `revision_model_id` est persistée et reprise aux ajustements suivants ; le modèle effectivement renvoyé par la gateway est conservé sur chaque tour assistant et affiché dans l'historique.
- Les anciens projets restent lisibles : H3 Render accepte les schémas 1/2 et écrit le schéma 3 ; KREA2 Assisted accepte le schéma 1 et écrit le schéma 2. Un modèle historique momentanément absent du catalogue reste sélectionné et signalé, sans fallback silencieux.
- Validation : 678 tests complets réussis en 82 secondes, compilation Python réussie et `git diff --check` sans erreur de whitespace.

### Broken / missing
- Aucun défaut fonctionnel détecté par les tests automatisés.
- Aucun smoke test navigateur réel n'a encore vérifié le basculement serveur/local au milieu d'une conversation historique.

### Next steps (max 3)
1. Redémarrer PanelForge et ouvrir un ancien projet H3 Base, Ref2V puis KREA2 Assisted pour confirmer la restauration de l'historique.
2. Basculer le modèle dans la zone d'ajustement, envoyer un tour, puis vérifier le badge du modèle sur la réponse et la conservation du modèle initial.
3. Tester un second ajustement sans retoucher le sélecteur afin de confirmer la persistance de la préférence.

### Risks / open questions
- Un modèle peut rester visible comme historique alors qu'il a été déchargé après la lecture du catalogue ; l'appel échoue alors explicitement sur ce modèle au lieu d'être rerouté.

## Diagnostic 2026-08-31 - Plans H3 tronqués par le budget de sortie

### Works
- Les journaux du dernier parcours identifient trois appels `action_plan.generate` à 08:57:32, 08:58:26 et 08:59:58 UTC. Unsloth a terminé chacun avec `finish_reason=length` et PanelForge avait envoyé `max_tokens=32768`.
- Les trois réponses visibles font seulement 5 853, 7 449 et 6 862 caractères, mais sont réellement coupées au milieu du JSON. Le budget de complétion inclut le raisonnement non exposé du modèle, ce qui explique qu'une sortie finale courte puisse épuiser 32 768 tokens.
- Le retry automatique a correctement rejoué l'étape, mais avec le même budget client ; il ne pouvait donc pas supprimer cette classe d'échec.

### Broken / missing
- Le message UI « flux terminé sans résultat persistant » masque la cause précise `finish_reason=length`.
- Les appels du parcours Prompt Composition/H3 imposent historiquement `max_tokens=32768` au lieu de laisser le fournisseur utiliser son budget natif. Cette limite n'a pas été ajoutée par le dernier patch de sélection de modèle, mais elle est bien la cause directe de ce run.

### Next steps (max 3)
1. Après validation utilisateur, omettre la limite client sur les appels structurés longs H3 (`max_tokens=None`) afin que seul le contexte du fournisseur borne la génération.
2. Afficher explicitement « réponse tronquée par la limite de sortie/contexte » et conserver le brouillon, au lieu du seul message terminal générique.
3. Tester Brief, Plan et Writer avec Unsloth en thinking long, puis vérifier qu'un retry ne réemploie pas une borne fautive.

### Risks / open questions
- Omettre `max_tokens` ne rend pas la sortie infinie : la fenêtre de contexte et les réglages du serveur Unsloth/vLLM restent les limites finales. Un modèle qui raisonne jusqu'à épuiser son contexte peut encore être tronqué par le fournisseur.

## Update 2026-08-31 - garde-fous LLM doublés et diagnostic explicite

### Works
- Tous les plafonds numériques applicatifs ont été doublés sans modifier les appels déjà configurés avec `max_tokens=None` : défaut 32 768→65 536, H3/KREA Assisted/Edit et révisions Batch 16 384→32 768, Social 8 000→16 000, retries Production 2 048→4 096 avec plafond 32 768→65 536.
- Brief, Plan, Writer et arbitrages H3/Ref2V utilisent désormais 65 536 tokens. Le plafond client vLLM par défaut passe lui aussi à 65 536 via `PANELFORGE_VLLM_MAX_OUTPUT_TOKENS`, tout en laissant le contexte combiné du serveur autoritaire.
- Une troncature `finish_reason=length` affiche désormais le budget exact, précise que le raisonnement interne le consomme et conserve le brouillon. H3 Base et Ref2V ne remplacent plus ce diagnostic par « flux terminé sans résultat persistant ».
- Le message détaillé est partagé par H3 Render, KREA2 Assisted, Batch, Edit, Social et Production. README et documentation des services locaux sont alignés.
- Validation : 137 tests ciblés puis 679 tests complets réussis en 77 secondes ; compilation Python et `git diff --check` réussis.

### Broken / missing
- Aucun défaut automatisé détecté.
- Le dernier Plan ayant échoué doit être relancé après redémarrage : son appel historique reste légitimement enregistré comme tronqué à 32 768 tokens.

### Next steps (max 3)
1. Redémarrer PanelForge sur `h3-video-lora`, recharger la page pour prendre les nouveaux scripts puis relancer uniquement le Plan du parcours concerné.
2. Vérifier dans `workspace/llm_calls.json` que le nouvel appel `action_plan.generate` annonce `max_tokens: 65536`.
3. Si Unsloth renvoie encore `finish_reason=length`, comparer sa fenêtre de contexte et son réglage de thinking avant d'augmenter de nouveau le garde-fou.

### Risks / open questions
- Pour vLLM configuré avec un contexte total de 65 536, le serveur peut réduire ou refuser un budget de sortie de 65 536 lorsque le prompt occupe déjà une partie du contexte. La variable d'environnement permet de conserver 32 768 pour ce seul fournisseur si nécessaire, sans réduire le nouveau budget Unsloth.

## Update 2026-08-31 - retrait de la source vLLM

### Works
- Le lanceur ne déclare plus les options ni variables `PANELFORGE_VLLM_*` et ne construit plus de gateway vers `127.0.0.1:8000`; la découverte active couvre seulement le serveur distant et Unsloth Studio.
- Le catalogue frontend considère uniquement `local::` comme source locale. Les dix sélecteurs LLM affichent désormais `Local · Unsloth`, avec cache frontend renouvelé.
- Le routage des ressources et le bandeau d'activité classent uniquement `local::` sur le GPU local. Les anciens IDs préfixés restent affichables comme modèles historiques indisponibles, sans reroutage.
- README et `docs/local-services.md` ne documentent plus vLLM comme service actif.
- Validation : 107 tests ciblés puis 679 tests complets réussis. Les seuls avertissements de catalogue du build concernent maintenant `server` et `local`; aucune tentative vLLM n'est observée.

### Broken / missing
- Aucun défaut automatisé détecté.
- Un ancien run enregistré avec un modèle `vllm::...` reste consultable, mais une nouvelle exécution avec cet ID échoue explicitement comme source inconnue jusqu'à ce que l'utilisateur choisisse un modèle Unsloth ou serveur.

### Next steps (max 3)
1. Redémarrer PanelForge puis forcer le rechargement du navigateur pour prendre `lab.js?v=20260831.1` et les nouveaux libellés.
2. Ouvrir les listes locale et serveur et confirmer que seul le catalogue Unsloth apparaît sous la case locale.
3. Sur un ancien run vLLM, choisir explicitement un modèle disponible avant de relancer une étape.

### Risks / open questions
- Les mentions vLLM antérieures restent dans les sections historiques de ce journal de continuité ; elles décrivent l'état passé et non la configuration active.

## Update 2026-08-31 - garde-fous LLM portés à x4

### Works
- Tous les budgets applicatifs numériques courants sont multipliés par quatre : défaut et appels H3/Ref2V longs `65 536→262 144`, révisions H3/KREA et workshop Batch `32 768→131 072`, Social `16 000→64 000`.
- Les appels JSON courts de Production commencent à `16 384` au lieu de `4 096`; leur croissance exponentielle est plafonnée à `262 144` au lieu de `65 536`. La sélection d'image explicitement configurée avec `max_tokens=None` reste sans limite client.
- Le message de troncature continue d'afficher le budget exact et de conserver le brouillon. README précise que ces plafonds très hauts servent principalement de protection contre une génération sans fin.
- Validation : 102 tests ciblés puis 679 tests complets réussis en 82 secondes. La recherche statique ne trouve plus les anciens budgets dans le code applicatif.

### Broken / missing
- Aucun défaut automatisé détecté.
- Un fournisseur dont la fenêtre de contexte est inférieure à `262 144` peut plafonner ou refuser la requête avant d'atteindre le garde-fou PanelForge.

### Next steps (max 3)
1. Redémarrer PanelForge puis relancer l'étape qui épuisait `65 536` tokens.
2. Vérifier dans `workspace/llm_calls.json` que `action_plan.generate` transmet maintenant `max_tokens: 262144`.
3. Si le fournisseur renvoie encore `finish_reason=length`, vérifier sa fenêtre de contexte et sa limite serveur plutôt que d'augmenter encore PanelForge.

### Risks / open questions
- Un budget de sortie élevé n'allonge pas la fenêtre de contexte du modèle et peut augmenter fortement la durée maximale d'un appel qui boucle dans son raisonnement.

## Update 2026-08-31 - Texte Instagram par défaut et JSON final récupérable

### Works
- Dans Video Lab, `Texte Instagram` précède désormais `Générer une vidéo` et devient la vue ouverte par défaut lorsque l'utilisateur clique sur l'onglet principal Video Lab. Les préremplissages explicites vers le générateur vidéo continuent d'ouvrir ce dernier directement.
- Le parseur Social Lab récupère désormais un objet ou tableau JSON complet auquel le modèle a seulement omis des fermetures en toute fin de réponse. Il ne modifie aucun champ et refuse toujours une chaîne JSON coupée ou une structure ambiguë.
- Les trois rejets Social Lab récents observés dans `llm_calls.json` avaient précisément la dernière accolade de l'objet absente malgré trois variantes complètes; ils sont couverts par la réparation déterministe.
- Aucun prompt ni appel LLM supplémentaire n'a été ajouté. Le cache de `lab-core.js` passe à `20260831.2`.
- Validation : 7 tests ciblés puis 681 tests complets réussis en 78 secondes.

### Broken / missing
- Un vrai contenu tronqué au milieu d'une chaîne ou un JSON sémantiquement invalide reste volontairement rejeté avec `Social Lab response is not valid JSON`.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer le rechargement de la page pour charger `lab-core.js?v=20260831.2`.
2. Ouvrir Video Lab et confirmer que Texte Instagram apparaît en premier et s'ouvre immédiatement.
3. Relancer une génération Social Lab avec le modèle local et vérifier qu'une accolade finale omise ne fait plus perdre les variantes.

### Risks / open questions
- La réparation est syntaxique et bornée à la fin de sortie; elle ne doit pas être étendue à des réécritures heuristiques de captions ou hashtags sans cas réel supplémentaire.

## Update 2026-08-31 - aperçu latéral de l'image d'appoint KREA2

### Works
- Création assistée duplique désormais l'image d'appoint sélectionnée dans un grand aperçu à droite de la discussion, sans retirer la vignette compacte ni le bouton `Retirer` existants.
- Le panneau latéral n'occupe aucun espace sans image, utilise `object-fit: contain`, suit immédiatement sélection, remplacement, réutilisation et suppression, et ouvre la lightbox au clic. Sous 860 px, il repasse en une colonne.
- Aucun changement de stockage, de payload, de prompt ou d'appel LLM. Les caches passent à `krea2-assisted-lab.js?v=20260831.3` et `lab.css?v=20260831.2`.
- Validation : 24 tests ciblés puis 681 tests complets réussis en 80 secondes.

### Broken / missing
- Aucun défaut automatisé détecté; le rendu visuel exact doit encore être confirmé dans le navigateur avec une image portrait et une image paysage.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5` pour charger les nouveaux assets frontend.
2. Sélectionner une image d'appoint portrait puis paysage et vérifier la taille du panneau à la largeur d'écran habituelle.
3. Ajuster seulement la proportion latérale actuelle de 30 % si le smoke test montre que la zone de texte devient trop étroite.

### Risks / open questions
- Sur une fenêtre relativement étroite mais supérieure à 860 px, le panneau peut réduire la largeur du fil de discussion; le breakpoint peut être remonté après test visuel réel.

## Alignment 2026-08-31 - progression approximative des rendus H3

### Current state
- Le relais WebSocket PanelForge transmet déjà tels quels les événements texte et binaires ComfyUI au navigateur. Les événements structurés `progress`, `executing` et `executed` peuvent donc alimenter une progression sans analyser les logs console ni changer le workflow.
- Dans la recette H3 Latent Speed actuelle, le sampler `26` correspond à la passe principale configurée à 25 steps, le nœud `28` à l'upscale latent 3D et le sampler `25` à la passe de raffinement fixe de 3 steps. Ces IDs doivent être déclarés dans le manifeste de recette, jamais codés en dur dans l'UI.
- Les deux traces fournies durent 256 et 279 secondes : la passe 25 steps prend 93–95 s, la passe 3 steps 120–122 s, et préparation/transferts/upscale/décodage/export environ 39–67 s. Le nombre brut de steps ne constitue donc pas un pourcentage global valide.

### Proposed progress profile
- Pondération initiale indicative : préparation `0–8 %`, diffusion principale `8–43 %`, upscale/transferts `43–50 %`, raffinement `50–95 %`, VAE/audio/encodage `95–100 %`.
- L'interface afficherait la phase, le step local (`17/25` ou `2/3`), un pourcentage marqué `estimé` et le temps écoulé. Le terminal réussi fixe exactement 100 %.
- Chaque événement doit être filtré par `prompt_id == execution_id` afin qu'un autre rendu ComfyUI parallèle ne modifie jamais la barre du job affiché.

### Next steps (max 3)
1. Ajouter au manifeste H3 un profil de phases/poids associé aux nœuds de la recette et l'exposer avec chaque tentative.
2. Créer un composant frontend partagé pour H3 Base, Ref2V, Video Lab et Production, avec fallback `Rendu en cours` si une recette ne déclare pas de profil.
3. Tester les événements ComfyUI réels des deux samplers et ajuster les poids à partir de plusieurs rendus plutôt qu'avec une estimation unique.

### Risks / open questions
- Les événements `executing` signalent les changements de nœud mais pas toujours l'avancement interne des chargements, de l'upscale ou du VAE; ces portions resteront volontairement approximatives.

## Update 2026-08-31 - progression approximative des rendus H3

### Works
- Les manifestes actifs H3 Base `0.1.2` et Ref2V `0.2.0` déclarent maintenant leurs nœuds de progression par phase : diffusion principale, upscale latent, raffinement haute résolution, puis décodage/export. Aucun ID de nœud n'est codé en dur dans les interfaces.
- Le relais WebSocket conserve les événements ComfyUI bruts et émet en plus `panelforge_render_progress`, filtré dynamiquement sur l'`execution_id` du run. La progression reste monotone et atteint 100 % uniquement sur succès confirmé.
- H3 Base, Ref2V, Video Lab et Production affichent la phase, le step local quand ComfyUI le fournit, le pourcentage marqué comme estimé et le temps écoulé. Les mises à jour ciblent seulement ces champs et ne reconstruisent pas les lecteurs vidéo.
- Production expose désormais l'`execution_id` et l'URL d'événements de chaque essai H3 sérialisé, afin de suivre aussi bien les previews 0,2 MP que le rendu final 1,2 MP.
- Les caches passent à `lab.css?v=20260831.3`, `h3-render-lab.js?v=20260831.3`, `video-lab.js?v=20260831.1` et `production-lab.js?v=20260831.1`.
- Validation : tests de manifeste, normalisation des deux samplers, filtrage inter-job et UI ajoutés ; 682 tests complets passent en 81 secondes.

### Broken / missing
- Aucun défaut automatisé détecté.
- La préparation des modèles, l'upscale et l'export ne publient pas de sous-progression fiable ; le pourcentage avance donc par jalons pendant ces phases.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5`, puis lancer un rendu H3 Base et un Ref2V pour confirmer les noms de phases avec le serveur ComfyUI réel.
2. Comparer trois à cinq durées de rendu et ajuster uniquement les poids des manifestes si la barre paraît systématiquement trop rapide ou trop lente.
3. Vérifier un preview puis un final Production afin de confirmer que la barre se rattache au nouvel essai à chaque itération.

### Risks / open questions
- Le temps écoulé commence à la connexion de la page au rendu ; après un rechargement du navigateur pendant un calcul actif, il repart de zéro sans affecter le job.
- Les pourcentages sont calibrés sur les deux traces disponibles et restent une estimation, surtout pendant la passe de raffinement dont chaque step est beaucoup plus coûteux que ceux de la passe principale.

## Update 2026-08-31 — aperçu du feedback KREA2 assisté

### Works
- Le panneau visuel placé à droite de la discussion suit maintenant aussi l’essai actuellement sélectionné avec le bouton `Feedback`, et plus seulement l’image d’appoint ajoutée au prochain message.
- Une image d’appoint explicitement choisie reste prioritaire pour l’échange courant. Après son envoi ou son retrait, le panneau revient automatiquement au feedback persistant du projet.
- Le bandeau du panneau distingue `FEEDBACK VISUEL` et `IMAGE D’APPOINT`; l’image reste agrandissable dans la lightbox existante. Le cache du script passe à `20260831.4`.
- Les 18 tests KREA2 assistés ciblés et les 682 tests complets passent.

### Broken / missing
- Aucun défaut automatisé connu. Le comportement doit encore être confirmé dans le navigateur sur un projet existant possédant déjà un feedback sélectionné.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5`, puis sélectionner et désélectionner le bouton `Feedback` d’un essai KREA2.
2. Vérifier qu’une image d’appoint remplace temporairement cet aperçu et que le feedback réapparaît après l’échange.

### Risks / open questions
- Un feedback ancien sans `output_url` exploitable reste volontairement sans aperçu, même si son identifiant est encore présent dans le projet.

## Update 2026-08-31 — Spectrum optionnel dans les ateliers H3

### Works
- Les ateliers intégrés `Créer et ajuster la vidéo` de H3 Base et Ref2V proposent maintenant une case `Spectrum · Activer`, décochée par défaut.
- Le booléen est validé, persisté par essai, restauré avec `Reprendre prompt + réglages`, sérialisé dans l’API et rappelé dans le résumé de l’historique.
- Les compilateurs utilisent les bindings déclarés par les manifestes (`H3 Base: node 43.enabled`, `Ref2V: node 40.enabled`) sans coder les IDs dans l’interface. Tous les autres réglages Spectrum restent ceux des workflows publiés.
- Les anciens projets sans champ Spectrum sont relus avec `false`. Le workflow H3 legacy sans binding refuse seulement une activation explicite et conserve son comportement standard sinon.
- Les caches passent à `h3-render-lab.js?v=20260831.4` et `lab.css?v=20260831.4`. Les 57 tests ciblés puis les 684 tests complets passent.

### Broken / missing
- Ref2V conserve trois écarts UX/fonctionnels par rapport à H3 Base : pas de LoRA vidéo/CLIP -2, seulement le moteur de révision Ref2V legacy (pas de contrat caméra compilé 0.2.0), et pas d’encart visible pour le candidat de révision rejeté.
- Les différences d’entrées (1–9 références Ref2V contre T2VA/I2VA/L2VA/FL2VA H3 Base) sont propres aux modèles et ne constituent pas un retard.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5`, puis lancer un court essai Spectrum OFF et ON dans chaque atelier.
2. Vérifier dans ComfyUI que `enabled` change seul sur le nœud Spectrum des deux workflows.
3. Décider séparément si le prochain rattrapage Ref2V doit prioriser l’affichage des brouillons rejetés ou le support LoRA vidéo.

### Risks / open questions
- Spectrum reste expérimental et peut modifier nettement le rendu ou son coût; aucun autre paramètre interne du nœud n’est exposé pour éviter de multiplier les variables.

## Update 2026-08-31 — alignement de l’atelier Ref2V sur H3 Base

### Works
- Ref2V expose désormais le même profil `LoRA MiniMax · expérimental` que H3 Base : un seul LoRA, force bornée de 0 à 1 et `CLIP Set Last Layer · -2` optionnel.
- L’overlay Ref2V est décrit par le manifeste et injecté uniquement à la compilation d’un essai LoRA : modèle entre le chargeur hybride `44` et le Sigma Shift `38`, CLIP entre le loader `15` et l’encodeur Ref2V `11`. Les nœuds applicatifs `22000/22001` restent absents des rendus standard.
- Ref2V propose maintenant `Stable 0.2.0 · caméra compilée` par défaut et conserve `Legacy 0.1.0`. La version stable protège les clauses caméra avec des tokens, recompile les directives validées et préserve l’en-tête canonique `<Picture N>`.
- L’atelier Ref2V affiche maintenant la recette de révision et conserve visiblement un candidat rejeté avec son erreur, comme H3 Base.
- Le catalogue LoRA Ref2V réutilise la même découverte sûre `minmax_nsfw/`; aucun workflow ComfyUI standard, sampler, upscale, Spectrum ou câblage de références n’a été modifié.
- Validation : 53 tests ciblés puis 686 tests complets passent; `git diff --check` ne signale aucune erreur.

### Broken / missing
- Aucun écart fonctionnel connu ne subsiste dans l’atelier conversationnel commun. Les modes d’entrée restent volontairement différents : références Ref2V contre ancres T2VA/I2VA/L2VA/FL2VA H3 Base.
- Un smoke test ComfyUI réel reste requis pour confirmer que les custom nodes Power LoRA Loader et CLIPSetLastLayer acceptent le modèle hybride Ref2V sur l’installation serveur.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5`, puis vérifier la présence du profil LoRA et du sélecteur Stable/Legacy dans Ref2V.
2. Lancer un court rendu Ref2V standard puis LoRA et comparer les workflows compilés/nœuds actifs.
3. Tester un ajustement stable accepté puis un candidat volontairement invalide afin de confirmer l’encart de brouillon.

### Risks / open questions
- Les LoRA MiniMax disponibles ont pu être entraînés surtout sur H3 Base; leur compatibilité technique Ref2V est câblée, mais leur qualité avec le modèle hybride doit être évaluée LoRA par LoRA.
- Comme dans H3 Base stable, une révision caméra conserve le nombre de directives compilées; ajouter ou retirer une phase caméra entière nécessite encore le mode Legacy.

## Release 2026-08-31 — ateliers H3 Base et Ref2V stabilisés

### Works
- Le périmètre courant réunit les ateliers H3 Base et Ref2V alignés, Spectrum optionnel, le profil LoRA vidéo, les moteurs de révision sélectionnables, l'aperçu de feedback KREA2, la progression de rendu et les correctifs de robustesse LLM/UI accumulés depuis le précédent socle Production.
- La suite complète passe avec 686 tests verts et `git diff --check` ne signale aucune erreur de contenu.
- La publication stable cible le commit `Stabilize H3 and Ref2V creation workflows` et le tag `stable-h3-ref2v-workshops-2026-08-31` sur `EasyFrag/panelforge`.

### Broken / missing
- Les overlays LoRA et Spectrum nécessitent encore un smoke test sur le serveur ComfyUI réel pour valider les custom nodes et les modèles installés.
- Production sait déjà enchaîner un projet simple, mais sa boucle d'évaluation vidéo n'est pas encore assez structurée pour piloter seule plusieurs révisions fiables.

### Next steps (max 3)
1. Publier le commit complet et le tag stable sur GitHub, puis vérifier leurs références distantes.
2. Construire un patch Production borné autour de l'évaluation visuelle du preview 0,2 MP, d'une décision structurée et d'une instruction de révision préremplie.
3. Ajouter ensuite la reprise déterministe d'une étape échouée avant d'étendre l'orchestrateur à une file nocturne multi-projets.

### Risks / open questions
- L'évaluation Production devra rester un appel LLM unique après rendu et ne devra pas rejouer Brief/Plan/Prompt lors d'une simple révision du prompt final.
- Les seuils d'acceptation automatique devront être visibles et bornés; la validation humaine restera disponible tant que la boucle mono-projet n'aura pas été éprouvée.

## Update 2026-08-31 — compteurs de steps H3 fiables

### Works
- La progression H3 Base et Ref2V distingue désormais les vraies passes de diffusion des sous-progressions internes émises par ComfyUI sur les mêmes nœuds.
- Les recettes déclarent le total attendu : la valeur principale configurée par l'utilisateur, puis 3 steps fixes pour le raffinement haute résolution.
- Les compteurs parasites comme `3/50` ou `2/6` sont ignorés; l'interface conserve les compteurs réels `25/25` puis `1…3/3`. Spectrum ne change pas ces totaux.
- Validation : 37 tests ciblés puis 686 tests complets passent; `git diff --check` ne signale aucune erreur.

### Broken / missing
- Aucun défaut automatisé connu. Un rendu ComfyUI réel doit encore confirmer que toutes les versions installées publient les événements `25/25` et `3/3` dans le même ordre.

### Next steps (max 3)
1. Redémarrer PanelForge et lancer un rendu H3 avec Spectrum OFF puis ON pour vérifier les deux compteurs affichés.
2. Si le serveur publie un nouveau sous-compteur, conserver la trace WebSocket brute afin de l'ajouter comme cas de test sans modifier les steps du workflow.
3. Reprendre ensuite le patch Production consacré à la boucle d'évaluation du preview 0,2 MP.

### Risks / open questions
- Le filtrage est volontairement limité aux ateliers H3 Base/Ref2V, où PanelForge connaît le réglage principal de l'essai. Le Video Lab autonome conserve son comportement historique tant que son relais n'est pas aligné explicitement.

## Audit 2026-09-01 — état du parcours Production V1

### Works
- Production est un orchestrateur V1 mono-projet borné : source immuable + intention, trois candidats KREA2 conversationnels, sélection visuelle LLM, compilation H3 Base I2VA, puis une à trois previews 0,2 MP évaluées et un nouveau rendu final 1,2 MP avec prompt et seed du preview retenu.
- Le moteur KREA2 est celui de Création assistée avec le workflow Batch `krea2-community@0.2.0`, son historique conversationnel, son catalogue partagé et les réglages checkpoint/ratio/MP/LoRA. Chaque candidat après le premier utilise le rendu précédent comme feedback d'un nouvel appel LLM.
- La compilation vidéo utilise le profil/cookbook H3 Base mono `minimax.h3.fl2va.direct@0.3.3`, le Brief créatif optionnel `creative-direction@0.2.0`, le workflow de rendu `minimax-h3-latent-speed@0.1.2`, 25 steps principaux, la révision caméra stable, une seed verrouillée, les LoRA vidéo et la musique OFF par défaut.
- Full auto sélectionne l'image, évalue chaque preview et peut accepter avant la limite. Human review ajoute un point de validation image puis un point de validation après chaque preview produit. Les étapes échouées sont reprenables sans rejouer les prédécesseurs valides.

### Broken / missing
- Production ne possède pas encore de champ Spectrum et n'en transmet aucun à H3 Render; les previews et le final sont donc Spectrum OFF.
- La V1 ne garantit pas trois previews : elle s'arrête dès qu'une évaluation accepte le résultat ou atteint le seuil. En mode humain, la validation vidéo peut revenir jusqu'à trois fois au lieu de constituer un unique second point d'arrêt.
- Le « final 1,2 MP » est un nouveau rendu H3 depuis le prompt et la seed du preview choisi, pas un upscale direct du fichier vidéo low-res.

### Next steps (max 3)
1. Ajouter Spectrum à la configuration Production, activé par défaut pour les previews et le final, sans changer le défaut OFF des ateliers H3 Base/Ref2V.
2. Décider si Production doit toujours produire et noter exactement trois previews avant sélection, ou conserver l'arrêt anticipé actuel en full auto.
3. Si deux points humains stricts sont retenus, déplacer la validation vidéo après la galerie complète des trois previews et leur comparaison finale.

### Risks / open questions
- Activer Spectrum uniquement sur les previews puis le couper au final rendrait la comparaison peu fiable; le même réglage devrait être conservé sur toute la série.
- Forcer trois previews augmente fortement le temps et la chauffe par rapport à l'arrêt anticipé actuel, mais fournit un choix réel et des évaluations comparables.

## Alignment 2026-09-01 — vision Production V2 par ancres

### Works / decisions
- La cible n'est plus un batch fixe de trois images, mais une recherche itérative de candidats KREA2 organisée par rôle vidéo : `first_frame`, `last_frame` ou `reference` Ref2V.
- En mode humain, aucun appel LLM de comparaison globale des images n'est requis : l'utilisateur like/dislike, choisit un feedback, ajoute une correction et relance un nouveau lot jusqu'à promouvoir une image dans un rôle.
- En mode autonome, le LLM doit évaluer les candidats et décider de continuer ou promouvoir une image; chaque boucle automatique conserve une limite stricte.
- La recherche d'images peut explorer plusieurs checkpoints KREA2 BF16 installés et qualifiés. Checkpoint et pile LoRA peuvent être verrouillés dès le départ ou après une direction convaincante; chaque candidat conserve prompt, modèle, LoRA, seed, parent et feedback.
- Les rôles dérivent le moteur sans ambiguïté : first seule → I2VA, last seule → L2VA, first + last → FL2VA, référence(s) → Ref2V. La source ou tout candidat validé peut être promu comme ancre/référence.
- Les previews vidéo restent en 0,2 MP, 25 + 3 steps et Spectrum ON sur toute la série, final compris. En mode humain, chaque nouvelle itération est explicitement demandée et n'a pas besoin de plafond automatique; en full auto, la limite est obligatoire.

### Broken / missing
- Production V1 ne modélise qu'une image sélectionnée comme first frame I2VA et un checkpoint KREA2 unique par job. Elle ne possède ni branches d'ancres, ni rôles first/last/reference, ni exploration autonome multi-checkpoints.
- Le like/dislike et les commentaires KREA2 ne sont pas encore une mémoire de recherche Production durable; la recommandation LLM globale est actuellement toujours calculée, même en mode humain.

### Next steps (max 3)
1. Concevoir un schéma Production V2 séparé et relisible, sans migrer ni altérer les jobs V1 : branches d'ancres, rounds, candidats, préférences et verrouillage checkpoint/LoRA.
2. Implémenter d'abord le parcours humain KREA2 → promotion first/last/reference, avec dérivation I2VA/L2VA/FL2VA/Ref2V et sans appel comparatif inutile.
3. Ajouter ensuite la politique autonome bornée et la boucle vidéo Spectrum ON, en réutilisant les ateliers H3 Base/Ref2V existants.

### Risks / open questions
- Explorer librement tous les checkpoints crée des comparaisons confondues entre prompt et modèle; l'UI doit rendre les réglages de chaque candidat immédiatement visibles et permettre de verrouiller la direction retenue.
- Une first et une last générées indépendamment peuvent diverger visuellement. La seconde branche devrait pouvoir prendre l'ancre déjà validée comme référence de cohérence.

## Alignment 2026-09-01 — périmètre humain et UX de Production V2

### Works / decisions
- Production V2 sera une page dédiée `Production / V2`, séparée de l'orchestrateur V1 et de ses historiques. La première version est exclusivement pilotée par validation humaine; le mode autonome reste une cible d'architecture, pas une option active.
- Les vidéos de calibration utilisent 6 secondes par défaut, preview 0,2 MP, 25 + 3 steps et Spectrum ON. Le rendu 1,2 MP est une action explicite réservée au parcours humain après validation d'un preview.
- Un futur mode autonome ne devra pas lancer de rendu 1,2 MP tant que cette politique n'est pas réévaluée. Ses limites de boucles resteront obligatoires même si le mode humain peut itérer sans plafond automatique.
- Le mapping est confirmé : image(s) `reference` → Ref2V; `first_frame`/`last_frame` → H3 Base I2VA/L2VA/FL2VA.
- La mémoire de préférences devient profilée. Plusieurs profils persistants et sélectionnables (par exemple SFW, NSFW) isolent likes, dislikes, commentaires et effets observés des checkpoints/LoRA. Un candidat conserve toujours le profil actif et les réglages réellement utilisés.
- Le modèle LLM initial reste choisi au démarrage, mais chaque zone d'échange KREA2 et H3 vidéo possède son propre sélecteur `Modèle du prochain échange`, hérité par défaut et modifiable sans réécrire l'historique.
- Le panneau gauche utilisera un preset humain simple et des réglages progressifs : projet/source/intention/profil mémoire au départ; paramètres KREA2 au stade image; paramètres H3 au stade vidéo; options techniques et futur contrat d'automatisation dans un volet avancé.

### Broken / missing
- Aucun schéma V2, profil mémoire, route dédiée ni UI progressive n'est encore implémenté. La V1 reste active avec 10 secondes, son mode full auto et son formulaire monolithique.
- Le sélecteur de modèle de révision existe déjà dans les ateliers KREA2/H3 autonomes, mais Production V1 ne l'expose pas et réutilise le modèle initial du job pour toutes les opérations.

### Next steps (max 3)
1. Créer le domaine et le stockage V2 versionnés : projet humain, profils mémoire, branches d'ancres, rounds/candidats et promotion des rôles.
2. Construire la page dédiée avec preset `Exploration humaine` et paramètres contextuels, puis brancher la recherche KREA2 BF16 et les sélecteurs LLM par échange.
3. Brancher H3 Base/Ref2V avec preview 6 s Spectrum ON et bouton humain explicite de rendu final 1,2 MP; laisser l'automatisation désactivée.

### Risks / open questions
- Le profil mémoire actif doit être visible sur chaque round pour éviter qu'un feedback NSFW enrichisse accidentellement un profil SFW. Un changement de profil ne doit jamais reclasser rétroactivement les candidats passés.
- Les options nécessaires au futur agent doivent rester dans le contrat durable sans encombrer le formulaire humain; l'UI progressive ne doit donc pas supprimer les paramètres avancés du modèle de données.

## Alignment final 2026-09-01 — calibration puis recette visuelle verrouillée

### Works / decisions
- Les sections du panneau gauche restent toujours accessibles. Elles s'ouvrent au stade courant, puis se replient automatiquement avec un résumé des réglages effectivement utilisés; l'utilisateur peut les rouvrir à tout moment.
- Production V2 ne propose qu'un preset initial `Exploration humaine`. Il n'existe pas de preset de départ « Fidélité verrouillée ».
- Les premiers rounds KREA2 servent à calibrer la recette visuelle : checkpoint BF16, pile LoRA et intensités, ratio et mégapixels. Le prompt, la seed et le rôle d'ancre ne font pas partie du verrouillage stylistique.
- Lorsqu'un candidat convainc, l'utilisateur valide sa recette visuelle. Un snapshot versionné de ces réglages devient le défaut commun des branches suivantes `first_frame`, `last_frame` et `reference`; le déverrouiller crée une nouvelle révision sans altérer les anciens candidats.
- Le candidat de calibration peut être promu directement comme référence Ref2V, créant un parcours court qui saute la génération d'ancres first/last.

### Broken / missing
- Ces comportements restent à implémenter dans Production V2; la V1 ne connaît ni recette visuelle validée ni résumé progressif des sections.

### Next steps (max 3)
1. Patch 1 : domaine/stockage V2, profils mémoire, calibration KREA2, snapshots de recette visuelle et panneau progressif repliable.
2. Patch 2 : branches first/last/reference, promotion Ref2V courte, compilation vidéo et boucle humaine 6 s Spectrum ON.
3. Valider chaque patch avec les tests V1 existants afin de garantir l'absence de régression sur les historiques Production actuels.

### Risks / open questions
- Changer une recette visuelle après création d'une ancre doit afficher clairement que les ancres précédentes appartiennent à une révision différente; aucune mise à jour implicite ne doit les masquer.

## Update 2026-09-01 — Production V2 humaine implémentée

### Works
- Une page dédiée `Production V2` coexiste avec `Production V1` sans migration ni modification de ses projets. Le parcours est exclusivement humain et commence par une source immuable, une intention, un profil mémoire, un modèle LLM et le preset unique `Exploration humaine`.
- Les profils mémoire SFW/NSFW et personnalisés sont persistants et isolés. Chaque candidat conserve le profil, le modèle LLM, le prompt, le checkpoint, les LoRA bornées entre -1 et 1, la seed, le parent et le feedback effectivement utilisés.
- La recherche KREA2 génère 1 à 6 candidats sans appel comparatif LLM en mode humain. L'exploration peut faire tourner plusieurs checkpoints BF16, puis un candidat valide un snapshot versionné checkpoint + LoRA + ratio + mégapixels réutilisé sur les branches suivantes.
- La source ou un candidat peut être promu en `first_frame`, `last_frame` ou `reference`. Les routes sont dérivées automatiquement : I2VA, L2VA, FL2VA ou Ref2V; le mélange silencieux entre familles H3 Base et Ref2V est refusé.
- Le déverrouillage de la recette conserve l'historique, archive les prompts/rendus vidéo aval et ouvre une nouvelle calibration au lieu de modifier les anciens essais.
- La compilation vidéo réutilise les recettes stables H3 Base `0.3.3` ou Ref2V `0.4.0` et exécute Brief, Plan JSON puis Prompt final avec une seconde tentative bornée par étape. Les révisions de preview restent un seul appel LLM avec le modèle sélectionné près de la zone d'échange.
- Les previews utilisent 6 secondes, 0,2 MP, 25 steps principaux + 3 fixes, Spectrum ON et une seed persistée. Le rendu 1,2 MP est uniquement lancé par une action humaine explicite depuis un preview sélectionné.
- Le panneau gauche est progressif et repliable : Projet, Recherche d'ancre, Création vidéo et Réglages avancés. Les candidats/ancres sont agrandissables, les réglages restent inspectables et les versions vidéo invalidées restent lisibles.
- La protection thermique ne bloque KREA2/H3 qu'en fonction du GPU serveur distant : stop 85 °C, reprise sous 40 °C et attente minimale 120 s par défaut, tous paramétrables. La chauffe du GPU local LLM n'empêche pas les rendus distants.
- Validation finale : compilation Python réussie, `git diff --check` sans erreur de contenu et 697 tests complets passent.

### Broken / missing
- Le futur mode agent/autonome, ses limites de boucles et l'ordonnancement multi-projets ne sont volontairement pas activés dans cette V2 humaine.
- Aucun smoke test réel Unsloth/KREA2/H3 n'a été lancé pendant ce patch; les services externes étaient hors du périmètre des tests automatisés.
- Node.js n'est pas installé dans l'environnement : le JavaScript est couvert par les tests statiques/API mais n'a pas pu être passé dans `node --check`.

### Next steps (max 3)
1. Redémarrer PanelForge et faire un smoke navigateur complet : source → deux rounds KREA2 → verrouillage de recette → promotion d'ancre → compilation → preview 6 s → final explicite.
2. Tester une route H3 Base puis une route Ref2V sur le serveur réel, notamment Spectrum ON, les LoRA et la restauration des historiques invalidés.
3. Après calibration humaine, formaliser les décisions observées avant d'ajouter l'agent autonome et la file multi-projets.

### Risks / open questions
- Les catalogues BF16/LoRA et les custom nodes disponibles varient avec l'installation ComfyUI; un nom présent dans le catalogue doit encore être validé qualitativement sur le serveur.
- Une last frame générée depuis une first frame peut encore diverger malgré la référence de cohérence; l'efficacité du guidage doit être mesurée sur des cas réels.
- Le verrou thermique attend un délai minimal depuis son déclenchement puis exige une température sous le seuil de reprise; il ne mesure pas encore une fenêtre continue de 120 secondes sous 40 °C.

## Hotfix 2026-09-01 — saisie des feedbacks Production V2

### Works
- La galerie de candidats Production V2 n'est plus reconstruite lorsque le polling rapporte exactement le même état. Après la fin du batch, le polling à cinq secondes ne détruit donc plus les zones de feedback.
- Si un autre candidat passe de `prompting` à `rendering` ou `succeeded` pendant la saisie, le brouillon local, le focus et la position du curseur du textarea actif sont capturés puis restaurés sans scroll forcé.
- Les brouillons restent isolés par candidat et sont vidés uniquement lors du changement de projet ou du retour au formulaire de création. Le cache du script passe à `production-v2-lab.js?v=20260901.2`.
- Validation : 31 tests Production V2/Web ciblés passent et `git diff --check` ne signale aucune erreur de contenu.

### Broken / missing
- Le comportement doit encore être confirmé dans un navigateur pendant un vrai batch KREA2, Node.js n'étant pas disponible pour une validation dynamique du script dans cet environnement.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5` pour charger la version `20260901.2`.
2. Commencer un feedback sur le candidat 1 pendant que les candidats 2/3 avancent, puis vérifier que texte et caret restent stables après leur finalisation.
3. Continuer ensuite le smoke complet Production V2 jusqu'au preview H3.

### Risks / open questions
- Les brouillons non validés par Like/Dislike restent volontairement locaux à la page et ne survivent pas à un rechargement complet du navigateur.

## Update 2026-09-01 — Production V2, base souple et ateliers d’ancres

### Works
- La validation d’un candidat crée désormais une `Base visuelle` versionnée avec son image, son prompt, sa seed, son checkpoint, son ratio, ses mégapixels et ses LoRA. Cette base préremplit les ateliers suivants sans verrouiller les contrôles : checkpoint, MP et pile LoRA restent modifiables.
- L’historique KREA2 est regroupé dans quatre ateliers repliables : calibration de la base, First frame, Last frame et références Ref2V. Une base ou une ancre validée apparaît dans le bandeau supérieur tandis que sa recherche se replie mais reste consultable.
- `Feedback suivant` devient `Continuer depuis cette image`. Cette action choisit uniquement la branche de feedback et son rôle; elle ne fige pas le checkpoint et ne désactive pas l’exploration BF16.
- Chaque candidat terminé peut être relancé à 2,1 MP. Ce clone réutilise exactement le prompt, la seed, le checkpoint, le ratio et les LoRA, sans appel LLM supplémentaire; seule la résolution change et le résultat reste lié au même round.
- Les candidats de calibration proposent `Valider comme base` et `Utiliser directement en Ref2V`. Les ateliers suivants exposent des promotions contextuelles First frame, Last frame ou référence; Ref2V reste plafonné à neuf références actives.
- Le mode `Comparaison technique` réutilise le prompt, la seed, le checkpoint et la résolution du candidat parent. Avec `Exploration LoRA assistée`, un seul appel LLM planifie tout le batch : baseline avec les LoRA manuelles, puis variantes avec ajouts distincts pris dans la liste installée et forces strictement bornées entre -1 et 1.
- La mémoire LoRA expérimentale accepte désormais un `profile_id`. Les hypothèses et observations SFW/NSFW utilisées par Production V2 sont filtrées par profil, tandis que les connaissances déclarées du catalogue restent communes.
- Les anciens documents Production V2 restent lisibles grâce aux valeurs par défaut des nouveaux champs; Production V1 et ses historiques ne sont pas modifiés par ce parcours.
- Validation finale : compilation Python réussie, `git diff --check` sans erreur de contenu et 705 tests complets passent.

### Broken / missing
- Aucun smoke test réel KREA2/Unsloth/H3 n’a été exécuté pendant ce patch. Il faut encore confirmer dans le navigateur le clone 2,1 MP, la galerie repliable et une comparaison LoRA sur les ressources réellement installées.
- Node.js n’est pas disponible dans l’environnement; le script Production V2 est couvert par les tests statiques et les contrats API, mais n’a pas pu être soumis à `node --check`.
- Le mode autonome et l’ordonnancement multi-projets restent volontairement hors de cette évolution humaine.

### Next steps (max 3)
1. Redémarrer PanelForge ou forcer `Ctrl+F5`, puis tester calibration 0,8 MP → `Continuer depuis cette image` → clone 2,1 MP → validation de la base.
2. Tester un atelier First/Last puis un parcours direct Ref2V et vérifier que les blocs validés se replient sans perdre leur historique.
3. Lancer une comparaison LoRA assistée à trois candidats avec une contrainte explicite telle que `inclure wetness`, puis liker/disliker sous deux profils mémoire différents.

### Risks / open questions
- Le clone 2,1 MP transmet la même seed au moteur KREA2, mais le changement de résolution peut naturellement modifier la composition malgré des paramètres identiques.
- Les choix LoRA du modèle sont limités à la liste exacte découverte sur le serveur; une ressource absente ou mal nommée provoque une erreur explicite plutôt qu’une substitution silencieuse.

## Update 2026-09-01 — Production V2, feedback contextualisé et boucle vidéo H3

### Works
- `Figer le checkpoint` et `Figer le prompt et la seed` sont désormais deux choix indépendants. Un prompt/seed figé peut encore comparer plusieurs checkpoints BF16; l’exploration LoRA assistée active seulement le gel prompt/seed.
- `Continuer depuis cette image` restaure le rôle, checkpoint, ratio, mégapixels et toute la pile LoRA réellement utilisée, sans changer le modèle LLM choisi ni les cases de gel. L’image parente, ses réglages et les réponses/recommandations de sa branche sont visibles à côté du feedback.
- Les ateliers First/Last peuvent être rouverts depuis l’ancre validée; l’ancienne ancre reste active jusqu’à validation de son remplacement. Les emplacements manquants First/Last ouvrent directement l’atelier correspondant.
- La création vidéo n’expose plus le raccourci ambigu de promotion de la source. L’intention vidéo est modifiable avant compilation; une recompilation explicite archive le prompt H3 et les rendus précédents.
- Les réglages vidéo Production V2 sont persistants et alignés sur H3/Ref2V : ratio, durée 6 s par défaut, preview 0,2 MP, final 1,2 MP, 25 steps, seed verrouillable/régénérable, Spectrum ON, musique et LoRA MiniMax optionnelles. Chaque preview conserve son snapshot; le final réutilise celui du preview sélectionné en ne changeant que les MP.
- Le chat vidéo révise le prompt final en un seul appel LLM et n’enchaîne plus automatiquement un rendu coûteux. Les réponses, recommandations, questions et prompts proposés restent consultables.
- Les lecteurs vidéo ne sont plus reconstruits pendant le polling si les médias n’ont pas changé. Les previews et candidats sont triés par index décroissant, avec trois cartes maximum par ligne.
- La progression H3/Ref2V est disponible dans Production V2 via le relais WebSocket existant et affiche les vraies passes 25 puis 3, sans doubler les steps lorsque Spectrum est actif.
- Validation finale : 23 tests ciblés, compilation Python, `git diff --check` et les 710 tests complets passent.

### Broken / missing
- Aucun smoke navigateur réel KREA2/H3/Ref2V n’a été exécuté pendant ce patch. Node.js reste absent, donc le script n’a pas pu être vérifié avec `node --check`.
- Le mode autonome et la comparaison qualitative automatique restent volontairement hors de cette V2 humaine.

### Next steps (max 3)
1. Redémarrer PanelForge et tester un round KREA2 pendant la génération en saisissant déjà les feedbacks, puis vérifier le contexte parent et les ateliers First/Last rouverts.
2. Compiler une intention vidéo corrigée, envoyer un message au chat H3 sans lancer de rendu, puis produire plusieurs previews et vérifier lecture stable, tri décroissant et progression 25/3.
3. Sélectionner un preview avec LoRA/Spectrum, modifier les réglages du prochain essai, puis confirmer que le final reprend bien le snapshot du preview retenu sauf la résolution finale.

### Risks / open questions
- Les réponses de chat KREA2 sont relues depuis les projets enfants; un ancien projet enfant supprimé laisse simplement la conversation vide sans casser le projet Production V2.
- Un changement de statut réel (`queued` → `running` → `succeeded`) reconstruit encore la carte concernée; après succès, le polling de journal seul ne touche plus au lecteur vidéo.

## Hotfix 2026-09-01 — rendu final direct depuis une preview

### Works
- Chaque preview 0,2 MP terminée expose désormais `Générer en 1,2 MP` directement sur sa carte. L’action transmet l’identifiant de cette preview sans nécessiter une sélection préalable.
- Le backend réactive le prompt historique du preview choisi et reprend son snapshot complet : seed, ratio, durée, steps, Spectrum, musique et LoRA. Seuls les mégapixels passent à la résolution finale configurée.
- `Sélectionner` conserve son sens non destructif : il marque la preview pour le feedback visuel des prochains échanges LLM, sans remplacer immédiatement le prompt courant. Le prompt réellement envoyé par chaque preview est maintenant consultable dans ses détails.
- Validation : compilation Python, `git diff --check` et 24 tests Production V2 ciblés passent.

### Broken / missing
- Le bouton doit encore être vérifié dans le navigateur sur un rendu H3 réel; Node.js reste indisponible pour `node --check`.

### Next steps (max 3)
1. Recharger PanelForge et lancer le final depuis une ancienne preview après avoir révisé le prompt courant.
2. Vérifier dans les détails et le journal que le prompt/seed/LoRA historiques ont été repris.
3. Confirmer que la preview reste lisible pendant le rendu final et que la progression 25/3 s’affiche.

### Risks / open questions
- Un rendu final depuis une ancienne preview restaure volontairement son ancien prompt dans le projet H3; les révisions plus récentes restent dans l’historique mais ne pilotent pas ce final.

## Alignment 2026-09-01 — audace de conception et de révision vidéo

### Current state
- Production V2 compile actuellement le Brief avec une liberté agrégée à 100 et les trois axes à 3/3, mais sans contrôle UX ni variante de Brief créative. La valeur `creative_audacity=2` est codée en dur et le template standard ne consomme pas cette consigne d’audace.
- Le chat vidéo H3/Ref2V effectue bien un seul appel de révision du prompt final avec mémoire et keyframes, mais ne possède aucun niveau d’audace distinct.
- H3 Base possède déjà la variante de Brief `creative-direction@0.2.0`; Ref2V n’a pas encore d’équivalent dédié respectant sa grammaire de références.

### Next steps (max 3)
1. Ajouter à Production V2 une audace de conception 0–3, réglable et à 3 par défaut, puis la persister et l’afficher dans la trace de compilation.
2. Ajouter une audace de révision 0–3 au prochain échange vidéo, sans appel LLM supplémentaire, avec une politique anti-empilement et conservation des invariants H3/Ref2V.
3. Réutiliser la variante H3 existante et créer un équivalent Ref2V dédié avant de déclarer les deux routes alignées; différer l’audace KREA2 Production après expérimentation dans KREA Assist.

### Risks / open questions
- Une audace maximale répétée ne doit pas accumuler mécaniquement de nouvelles actions à chaque tour : le modèle doit pouvoir remplacer ou rééquilibrer l’idée-signature existante.
- Une modification de caméra en révision doit passer par les directives canoniques compilées et non par de la prose caméra libre.

## Update 2026-09-01 — audace Production V2 implémentée

### Works
- Production V2 expose maintenant `Audace de conception` de 0 à 3 juste avant `Compiler Brief → Plan → Prompt`, avec 3 par défaut. La valeur est persistée, visible dans le contrat vidéo et son changement invalide explicitement une compilation existante.
- Les routes H3 Base utilisent réellement `creative-direction@0.2.0` au lieu du Brief standard. Ref2V possède désormais sa propre variante `creative-direction@0.2.0`, qui conserve les rôles, usages et frontières de transfert de ses une à neuf références.
- Le chat vidéo expose séparément `Audace du prochain ajustement`, de 0 à 3 avec 3 par défaut. La valeur est envoyée dans le même et unique appel LLM, mémorisée dans le projet et inscrite dans le journal durable.
- La politique de révision demande de rééquilibrer ou remplacer les passages faibles plutôt que d'empiler des actions. Au niveau 3, elle autorise une idée-signature, au plus un effet de soutien et une modification de caméra uniquement via les directives canoniques compilées.
- Les chats H3 Base/Ref2V existants qui n'envoient pas ce nouveau contrôle conservent leur comportement antérieur : aucune politique d'audace implicite ne leur est ajoutée.
- Les anciens projets Production V2 migrent sans rupture avec les deux valeurs à 3. Le stockage passe au schéma 4 et le cache navigateur Production V2 à `20260901.7`.
- Validation : compilation Python, `git diff --check`, 93 tests ciblés puis les 715 tests complets passent.

### Broken / missing
- Aucun smoke navigateur ou appel réel Unsloth/H3/Ref2V n'a été exécuté pendant ce patch. La réaction qualitative des modèles au niveau 3 doit encore être calibrée sur de vrais previews.
- L'audace KREA2 Production reste volontairement différée jusqu'à son expérimentation dans KREA Assist.

### Next steps (max 3)
1. Recharger PanelForge, compiler une route H3 Base puis Ref2V à audace 3 et vérifier que la trace annonce bien la variante créative et le niveau retenu.
2. Comparer sur une même preview une révision à 0 puis à 3, en demandant de densifier une scène lente, et vérifier que le niveau 3 rééquilibre sans surcharger.
3. Ajuster les formulations ou les niveaux seulement après comparaison réelle des prompts et vidéos produits.

### Risks / open questions
- L'audace 3 est volontairement maximale par défaut; selon le modèle LLM, elle peut nécessiter une calibration si l'idée-signature devient trop spectaculaire ou trop dense pour six secondes.
- La variante Ref2V créative protège explicitement les canaux de référence, mais son respect doit être confirmé avec les modèles locaux réellement utilisés.

## Hotfix 2026-09-01 — hauteur des aperçus KREA2 Production V2

### Works
- Les cartes de candidats KREA2 ne sont plus limitées à une hauteur fixe de 330 px. Chaque aperçu reprend maintenant le ratio enregistré dans sa recette (`9:16`, `16:9`, carré, etc.) et affiche l'image entière avec `object-fit: contain`.
- Le contexte compact affiché à côté du feedback conserve volontairement sa hauteur de 150 px afin de ne pas écraser la zone de discussion.
- Les versions de cache passent à `lab.css?v=20260901.3` et `production-v2-lab.js?v=20260901.8`.
- Validation : `git diff --check`, 37 tests UI ciblés et les 716 tests complets passent.

### Broken / missing
- Aucun contrôle visuel dans un navigateur réel n'a été exécuté pendant ce hotfix.

### Next steps (max 3)
1. Recharger Production V2 et vérifier un batch `9:16` sur une fenêtre large puis étroite.
2. Confirmer que l'ouverture plein écran et l'aperçu compact du feedback restent pratiques.

### Risks / open questions
- Sur un écran large, une carte `9:16` est volontairement nettement plus haute; l'historique reste organisé en trois colonnes mais demande davantage de défilement vertical.

## Update 2026-09-01 — modèle LLM dédié à la compilation vidéo V2

### Works
- La section `Création vidéo` expose désormais `Modèle LLM de compilation` juste avant l'audace et le bouton `Compiler Brief → Plan → Prompt`, avec le sélecteur Local · Unsloth habituel.
- Le choix est distinct du modèle LLM initial, du prochain échange KREA2 et du prochain échange vidéo. Il est prérempli depuis le modèle initial pour les anciens/nouveaux projets, puis persisté indépendamment pour les recompilations.
- La session Prompt Lab utilise ce modèle unique pour toute la chaîne de compilation : Brief, Plan JSON et Prompt final. Le journal durable indique le modèle au lancement.
- Un changement de modèle après une compilation est traité comme un changement de contrat et demande une recompilation explicite; les anciens projets migrent avec leur modèle initial. Le stockage passe au schéma 5 et le cache Production V2 à `20260901.9`.
- Validation : compilation Python, `git diff --check`, 47 tests ciblés et les 717 tests complets passent.

### Broken / missing
- Aucun appel LLM réel ni smoke navigateur n'a été exécuté pendant ce patch.

### Next steps (max 3)
1. Recharger Production V2, choisir un modèle différent dans `Modèle LLM de compilation`, puis lancer une compilation.
2. Vérifier dans le journal et la trace Prompt Lab que Brief, Plan et Prompt utilisent ce modèle.
3. Confirmer que les sélecteurs KREA2 et échange vidéo ont conservé leurs choix précédents.

### Risks / open questions
- Les trois étapes partagent volontairement le même modèle de compilation; un choix séparé par étape n'est pas exposé afin de garder le parcours lisible.

## Diagnostic 2026-09-01 — révision caméra et comportement historique d'audace

### Works
- Le run `fLYING woman` a été retrouvé. Les deux révisions rejetées ont conservé le prompt H3 courant et n'ont donc pas corrompu le projet.
- Le LLM avait correctement choisi `arc_shot`, amplitude `large`, vitesse `fast`; les erreurs ont eu lieu à audace 3/3, pas à 0/3.

### Broken / missing
- Le contrat de révision demande `target_clause` sans expliquer que la valeur doit commencer par une continuation telle que `around`, `following`, `focused on` ou `as`. Qwen a renvoyé les groupes nominaux naturels `the woman flying horizontally over the lake` puis `the flying woman`, que le validateur a rejetés deux fois.
- Dans Production V2, 0/3 n'est pas le comportement historique : il ajoute une politique stricte « uniquement la correction demandée ». L'ancien comportement sans bloc d'audace n'est actuellement pas sélectionnable dans cette page, même s'il reste utilisé par les parcours qui omettent le paramètre.

### Next steps (max 3)
1. Aligner le contrat LLM caméra sur la grammaire réellement validée, avec exemples explicites, puis ajouter une récupération bornée pour un groupe nominal évident.
2. Exposer `Standard (historique)` séparément des niveaux 0–3; conserver 0 comme correction stricte et 3 comme initiative maximale.
3. Ajouter des tests reproduisant les deux `target_clause` rejetés du run réel.

### Risks / open questions
- Préfixer automatiquement une cible doit dépendre du mouvement (`around` pour `arc_shot`, `following` pour un tracking, etc.) afin de ne pas modifier arbitrairement l'intention.

## Update 2026-09-01 — niveau 0 historique et diagnostic du gel L2VA

### Works
- Dans Production V2, `Audace du prochain ajustement = 0` retrouve maintenant exactement le contrat historique : aucun bloc de politique d'audace n'est ajouté à l'appel H3. Les niveaux 1 à 3 conservent leur politique explicite.
- Le libellé UX et le journal durable indiquent `standard historique` pour le niveau 0. Les instructions `target_clause` et les retries caméra n'ont volontairement pas été modifiés.
- Le run réel `fLYING woman` a été audité. Sa première ligne L2VA est correcte et les protections `continue_motion`, `final_hold_ms: 0`, `instantaneous sample` et `without a pause, freeze, or held pose` sont bien présentes.
- Validation : 29 tests Production V2 ciblés puis les 718 tests complets passent.

### Broken / missing
- Le preview sélectionné demande 6,0 s mais le workflow arrondit 144 frames à 158 pour respecter la contrainte latente `17n+5`, soit 6,583 s effectives à 24 fps. Le prompt et son ancre finale restent pourtant compilés à 6,00 s.
- Les keyframes du run montrent encore une évolution à 3,27 s, puis des compositions presque identiques à 4,91 s et 6,54 s : l'ancre L2VA est atteinte environ 1,6 s trop tôt malgré le garde-fou textuel.
- Le Plan possède des étapes à 0 / 1,5 / 3 / 4,5 / 6 s, mais le writer actuel les résume sans timestamps intermédiaires; le prompt final ne contraint donc pas une convergence réellement tardive. La caméra est en outre compilée `at slow speed`.

### Next steps (max 3)
1. Aligner la durée inscrite dans le header, le Brief/Plan et le prompt H3 sur la durée effective du nombre de frames réellement rendu.
2. Concevoir un contrat L2VA de convergence tardive qui conserve des jalons temporels intermédiaires et n'atteint la composition exacte que sur la dernière frame, sans changer les règles caméra demandées dans ce tour.
3. Comparer le même dernier frame avec ce contrat sur une seed figée et vérifier les keyframes de la dernière seconde avant généralisation.

### Risks / open questions
- Le décalage de 0,583 s explique une partie de la tenue finale, mais pas à lui seul les quelque 1,6 s quasi figées : la convergence L2VA anticipée et la formulation photographique de l'ancre restent les facteurs principaux.

## Update 2026-09-01 — compilation vidéo et preview en un clic

### Works
- Le bouton Production V2 compile ou recompile désormais `Brief → Plan → Prompt`, puis enchaîne automatiquement la preview avec les réglages vidéo courants, 0,2 MP et Spectrum ON par défaut.
- L'enchaînement est réalisé dans le même travail backend : il continue pendant les rafraîchissements de page, passe de `h3_compile_preview` à `h3_preview`, puis expose la progression H3 dès que l'essai existe.
- Le bouton manuel de preview reste disponible après les échanges LLM. `Envoyer au LLM` conserve son fonctionnement de chat multi-round sans lancer automatiquement de rendu.
- Le libellé du bouton affiche les mégapixels de preview courants et son cache passe à `production-v2-lab.js?v=20260901.10`.
- Validation : compilation Python, `git diff --check`, 30 tests Production V2 ciblés puis les 719 tests complets passent.

### Broken / missing
- Aucun appel LLM ni rendu ComfyUI réel n'a été lancé pendant ce patch.
- La convergence anticipée L2VA et le décalage entre durée demandée et durée effective restent volontairement inchangés.
- Les contrats `target_clause` et la politique de retry n'ont pas été modifiés.

### Next steps (max 3)
1. Recharger Production V2 et vérifier qu'un clic compile les trois étapes puis lance bien une preview 0,2 MP sans intervention intermédiaire.
2. Vérifier qu'après plusieurs échanges `Envoyer au LLM`, aucun rendu ne part avant un clic explicite sur `Lancer un preview`.
3. Reporter la correction de convergence/durée L2VA à un patch dédié si les essais longs la rendent encore nécessaire.

### Risks / open questions
- Si la sécurité thermique bloque le lancement après une compilation réussie, le prompt H3 reste disponible et la preview peut être relancée manuellement lorsque le serveur est froid.

## Diagnostic 2026-09-01 — retrait de la last frame sur le dernier run

### Works
- Le dernier rendu du projet `fLYING woman` est bien compilé en I2VA avec le candidat 21 comme unique `first_frame`; le projet persistant ne contient aucune `last_frame` ni référence.
- Le workflow ComfyUI de l'essai `attempt-6721832d5dac4068839cc2afda7be244` charge seulement l'asset de first frame. Le nœud de chargement de last frame est absent et les deux entrées `last_frame` des nœuds H3 ont été retirées.
- Le candidat 20 créé comme `last_frame` et le candidat 21 créé comme `first_frame` ont exactement les mêmes pixels : prompt, seed, checkpoint, résolution et LoRA avaient été figés et sont identiques.

### Broken / missing
- Aucun reliquat de paramétrage `last_frame` n'a été trouvé. L'UX ne signale toutefois pas qu'un changement de rôle avec prompt et seed figés peut recréer une image pixel pour pixel identique.
- Le prompt I2VA courant demande un tonneau complet, puis un retour au vol bas avec la main qui retouche l'eau à la fin; cette trajectoire cyclique peut aussi faire ressembler la fin de la vidéo à son image de départ.

### Next steps (max 3)
1. Si souhaité, afficher un badge `image identique / même recette et seed` lorsqu'un candidat reproduit exactement un candidat antérieur sous un autre rôle.
2. Décider si un changement de rôle doit seulement avertir ou proposer de déverrouiller la seed, sans modifier automatiquement le comportement actuel.

### Risks / open questions
- Le rôle `first_frame` ou `last_frame` est une affectation de l'image dans H3; il ne transforme pas l'image KREA2 elle-même. Avec une recette et une seed identiques, les pixels restent donc identiques quel que soit le rôle choisi.

## Update 2026-09-01 — audace du prochain ajustement dans H3 Base

### Works
- La section `Ajuster avec le LLM` de H3 Base expose maintenant `Audace du prochain ajustement`, de 0 à 3, initialisée à `0/3` et accompagnée des mêmes niveaux lisibles que Production V2.
- Le niveau 0 est normalisé en absence de politique d'audace, dans la route web comme dans le service H3 : il produit donc exactement le contrat de révision historique. Les niveaux 1 à 3 utilisent le même appel LLM avec leur politique explicite.
- Le contrôle est volontairement limité à H3 Base; Ref2V conserve son interface et son comportement actuels. Le cache de `h3-render-lab.js` passe à `20260901.1`.
- Validation : compilation Python, `git diff --check`, 8 tests de révision H3, 19 tests web ciblés et les 720 tests complets passent.

### Broken / missing
- Aucun smoke navigateur ni appel LLM réel n'a été exécuté pendant ce patch.
- La valeur choisie reste un réglage du prochain échange dans la page courante; elle n'est pas persistée dans le projet H3 Base.

### Next steps (max 3)
1. Recharger H3 Base et confirmer que le curseur apparaît à `0/3` dans `Ajuster avec le LLM`.
2. Comparer un même ajustement à 0 puis à 3 pour calibrer l'effet qualitatif sans modifier le nombre d'appels.
3. Décider ultérieurement si ce réglage doit aussi être exposé dans Ref2V ou persisté par projet.

### Risks / open questions
- Le niveau 0 est garanti identique au comportement historique; les niveaux 1 à 3 dépendent toujours de la sensibilité du modèle local aux consignes d'audace.

## Hotfix 2026-09-01 — LoRA KREA2 et lisibilité Production V2

### Works
- Les retours de chat KREA2 dans Production V2 utilisent maintenant la typographie compacte déjà employée dans les autres conversations KREA2 (`.64rem`, interligne 1.45).
- Sélectionner une LoRA KREA2 dans un emplacement dont la force vaut 0 initialise automatiquement sa force à 1. La force reste ensuite modifiable et bornée entre −1 et 1; choisir `Aucun` la remet à 0.
- Activer `Exploration LoRA assistée` impose désormais 3 candidats, au cochage puis au lancement : une baseline manuelle et deux variantes. Le prompt et la seed restent automatiquement figés comme auparavant.
- Les erreurs de validation FastAPI en liste affichent maintenant leur chemin et leur message précis au lieu du seul `Erreur HTTP 422` / `Unprocessable Entity`.
- Le run réel `Monstre Poison Ivy` a confirmé que le backend fonctionne : le candidat 14 a été rendu sans LoRA, puis le candidat 15 a réussi avec `krea2/wetness_krea2_loraholic.safetensors` à force 1.0.
- Les caches passent à `lab.css?v=20260901.4`, `lab-core.js?v=20260901.2` et `production-v2-lab.js?v=20260901.11`. Validation : tests ciblés puis les 721 tests complets passent; `git diff --check` est propre hors avertissements CRLF existants.

### Broken / missing
- Aucun smoke navigateur n'a été exécuté après rechargement du nouveau frontend; l'application actuellement ouverte doit être redémarrée ou rechargée pour prendre les nouveaux assets.
- L'erreur 422 originale n'était pas persistée dans le projet. Le dernier état observé avait un batch de 1 candidat, incompatible avec l'exploration assistée qui exige baseline + variante; les nouveaux garde-fous suppriment ce chemin invalide et le détail API restera visible si une autre validation échoue.

### Next steps (max 3)
1. Recharger complètement PanelForge, choisir `wetness` dans un emplacement vide et confirmer que la force passe immédiatement à 1.
2. Continuer depuis une image, cocher l'exploration assistée et confirmer que le nombre de candidats passe à 3 avant le lancement.
3. Si une nouvelle erreur apparaît, relever le message désormais détaillé afin d'isoler le champ ou l'appel LLM exact.

### Risks / open questions
- Une LoRA sélectionnée à force 1 peut être très marquée; la valeur est un défaut d'activation visible, pas un verrou, et peut être réduite avant le rendu.

## Diagnostic 2026-09-01 — contamination last frame vers first frame

### Works
- Le run `Monstre Poison Ivy` confirme que les rôles et parents sont correctement persistés : la base visuelle vient du candidat 7, la last frame promue du candidat 13 et les candidats 14 à 21 sont bien étiquetés `first_frame`.
- La cause principale est identifiée : `_consistency_anchor()` choisit volontairement l'ancre temporelle opposée. Les premiers candidats first frame 14 et 15, sans parent, ont donc reçu l'asset de la last frame 13 comme `guidance_asset_id`; le projet KREA2 du candidat 14 le confirme explicitement.
- La mémoire textuelle SFW n'est pas la source directe du sang dans ce run : elle mélange les observations de tous les rôles, mais `_memory_context()` ne transmet que préférence, rôle, checkpoint, LoRA et commentaire; les commentaires last frame concernés sont vides.
- Les candidats 19 à 21 sont des comparaisons LoRA techniques : ils recopient exactement prompt et seed du candidat 17 sans appel LLM. Leur instruction `Fait en sorte de faire disparaitre le sang des mains` ne pouvait donc pas réécrire le prompt.

### Broken / missing
- Une ancre last frame peut contaminer visuellement la création initiale d'une first frame, puis cette contamination se propage par les parents first frame successifs.
- La mémoire de préférences n'est pas cloisonnée par rôle; même si elle n'a pas transmis le contenu sanglant ici, elle expose des choix last frame lors de la création first frame.
- Le mode de comparaison LoRA laisse saisir une correction sémantique alors que son contrat fige le prompt et ne peut appliquer cette correction.

### Next steps (max 3)
1. Séparer la continuité d'identité fournie par la recette de base de la continuité temporelle first/last, et ne plus injecter automatiquement l'ancre opposée comme image de feedback.
2. Cloisonner le contexte de travail par rôle tout en conservant un profil esthétique global explicite.
3. Clarifier la comparaison LoRA : correction du prompt avant comparaison ou champ de correction désactivé tant que prompt et seed sont figés.

### Risks / open questions
- Il reste à décider si l'ancre opposée doit être totalement interdite, optionnelle via une case `cohérence avec l'autre frame`, ou seulement fournie comme contexte faible explicitement annoté.

## Alignement 2026-09-02 — principes UX des itérations KREA2

### Works
- Direction retenue pour simplifier l'interface : ne plus exposer `Comparaison technique` comme un mode distinct; elle découle des quatre choix explicites `Conserver Prompt`, `Conserver Seed`, `Conserver Modèle` et `Conserver LoRA`.
- Lorsque `Conserver Prompt` est actif, la conversation de réécriture doit être grisée. L'assistance LoRA reste un appel LLM indépendant et doit être comptée même si prompt et seed sont conservés.
- Le bouton de lancement doit annoncer dynamiquement le coût logique du batch, par exemple `3 rendus · aucun appel LLM` ou `3 rendus · 1 appel LLM`.
- Le guidage visuel doit devenir explicite et distinct de la mémoire : aucune image, recette R1 par défaut, ou ancre/candidat choisi; aucune ancre temporelle opposée ne doit être injectée silencieusement.

### Broken / missing
- L'interface actuelle mélange réécriture narrative, comparaison technique, planification LoRA et guidage visuel, ce qui masque quels appels LLM auront réellement lieu.
- Le backend courant ne distingue pas encore clairement la référence visuelle commune, le parent de branche et l'ancre temporelle facultative.

### Next steps (max 3)
1. Définir la matrice exacte des quatre options de conservation et le compteur d'appels LLM associé.
2. Concevoir un bloc compact `Point de départ / Guidage visuel` avec miniatures et choix explicite `aucune référence`.
3. Implémenter ensuite l'isolation des branches first/last et l'état `Nouvelle branche depuis R1` dans un patch dédié.

### Risks / open questions
- `Conserver LoRA` doit signifier conservation exacte; si l'exploration assistée reste autorisée simultanément, son libellé doit indiquer clairement qu'elle ajoute des variantes au-delà de la pile conservée.

## Alignement 2026-09-02 — matrice des appels LLM

### Works
- Principe retenu pour la future implémentation : la réécriture du prompt est un appel unique au niveau du batch, puis tous les candidats utilisent ce prompt commun; elle ne doit pas être répétée une fois par image.
- `Conserver Prompt` décoché ajoute 1 appel LLM. `Exploration LoRA assistée` ajoute séparément 1 appel LLM. Les deux ensemble annoncent donc 2 appels, quel que soit le nombre de rendus KREA2 du batch.
- Le bouton devra afficher `X rendus · Y appels LLM`, avec une infobulle détaillant chaque appel prévu.
- L'état supérieur devra suivre l'appel actif par son rôle et son avancement. Pour chaque appel, `thinking` disponible et sortie finale devront être persistés et consultables dans des volets repliables, ouverts par défaut sur la possibilité de les inspecter.

### Broken / missing
- Le backend courant effectue encore la génération de prompt par candidat créatif; il faudra introduire une préparation de batch pour garantir le décompte convenu.
- Les traces actuelles ne forment pas encore un journal uniforme distinguant réécriture du prompt et planification LoRA.

### Next steps (max 3)
1. Concevoir l'objet de préparation du batch avec prompt commun et plan LoRA optionnel.
2. Ajouter le calcul prévisionnel et le détail du coût dans le bouton et l'état global.
3. Persister pour chaque appel son modèle, son statut, son thinking lorsqu'il existe et sa sortie finale.

### Risks / open questions
- L'API locale peut ne pas toujours séparer un canal `thinking`; dans ce cas l'interface devra afficher honnêtement `thinking non fourni` plutôt que fabriquer une trace.

## Réalignement 2026-09-02 — stratégie de prompt du batch

### Works
- Le comportement actuel a été vérifié : chaque candidat créatif déclenche son propre appel LLM avant son rendu, mais tous ces appels repartent du même parent et de la même image de guidage; ils ne forment pas une boucle d'analyse du rendu précédent.
- Pour éviter deux cases `Conserver Prompt` ambiguës, la proposition devient un choix exclusif à trois états : `Conserver le prompt actuel`, `Réécrire une fois puis conserver`, `Faire évoluer entre les rendus`.
- Avec 3 rendus, ces états représentent respectivement 0, 1 ou 3 appels de prompt. L'assistance LoRA ajoute indépendamment 1 appel au total affiché.
- Le mode évolutif devra être une vraie chaîne : chaque appel suivant reçoit le prompt et l'image du candidat précédent.

### Broken / missing
- Le code actuel ne sait ni partager un nouveau prompt commun entre les candidats, ni chaîner automatiquement le rendu précédent dans le candidat suivant.

### Next steps (max 3)
1. Remplacer la logique binaire de prompt figé par la stratégie explicite à trois états dans le contrat et l'interface.
2. Implémenter la préparation unique du prompt commun et le chaînage séquentiel du mode évolutif.
3. Calculer le nombre exact d'appels, assistance LoRA comprise, avant le lancement.

### Risks / open questions
- Le mode évolutif est nécessairement plus lent, car appels LLM et rendus deviennent séquentiels; il doit rester optionnel et ne pas être le défaut des comparaisons techniques.

## Alignement 2026-09-02 — presets d'itération

### Works
- Proposition UX retenue pour le patch : ajouter un menu `Preset d'itération` qui préremplit les contrôles visibles sans créer de mode backend caché ni les verrouiller.
- Toute modification manuelle d'un contrôle fait passer automatiquement le preset à `Personnalisé`; le coût en rendus et appels LLM est recalculé immédiatement.
- Presets proposés : `Ajustement standard`, `Comparer les modèles`, `Comparer les LoRA`, `Exploration créative`, puis `Personnalisé`.

### Broken / missing
- La combinaison exacte des réglages est encore à implémenter et devra rester lisible sous le menu, notamment la stratégie de prompt à trois états et les quatre paramètres conservés.

### Next steps (max 3)
1. Implémenter le menu comme raccourci de formulaire, sans persister un comportement parallèle aux valeurs explicites.
2. Définir et tester la matrice de chaque preset et le passage automatique à `Personnalisé`.
3. Relier le compteur et son infobulle aux valeurs effectives après application ou modification du preset.

### Risks / open questions
- Le preset `Exploration créative` devrait faire varier prompt et seed tout en conservant modèle et LoRA par défaut, afin de ne pas modifier trop de dimensions simultanément; les comparaisons de modèle et de LoRA restent des presets séparés.

## Implémentation 2026-09-02 — parcours d’itération KREA2 Production V2

### Works
- Production V2 expose désormais quatre presets qui ne font que remplir des contrôles visibles (`Ajustement standard`, `Comparer les modèles`, `Comparer les LoRA`, `Exploration créative`) et bascule sur `Personnalisé` dès qu’un réglage est modifié.
- La stratégie de prompt est explicite : conservation du prompt courant (0 appel), réécriture commune au batch (1 appel), ou évolution réellement séquentielle où chaque nouveau prompt reçoit le rendu précédent (1 appel par rendu). L’assistance LoRA ajoute exactement un appel distinct, sans retry caché.
- `Conserver Seed`, `Conserver Modèle` et `Conserver LoRA` sont indépendants. Une comparaison initiale sans parent peut créer une seed commune; la conservation modèle/LoRA fige la sélection courante, ou restaure la recette/branche lorsqu’elle existe.
- Le bouton annonce `X rendus KREA2 · Y appels LLM`; son infobulle détaille chaque appel dans son ordre réel. Le statut supérieur affiche l’appel actif et toutes les entrées, références, sorties et traces de thinking disponibles sont persistées dans des volets repliables.
- Les branches narratives sont cloisonnées par rôle : un parent de feedback doit appartenir au même rôle. Une image d’un autre rôle ne passe que par le guidage visuel explicite (`aucune`, `source/R1`, `R1 + image choisie`). `Nouvelle branche depuis R1` efface parent et guidage secondaire.
- La mémoire globale ne transmet entre rôles que les préférences checkpoint/LoRA; les commentaires narratifs ne sont fournis qu’au rôle courant. Cela empêche un commentaire Last Frame comme des mains ensanglantées de contaminer automatiquement une First Frame.
- Les LoRA manuelles restent la baseline de l’exploration assistée; les variantes ajoutées restent bornées entre −1 et 1 et leur mémoire utilise le checkpoint réel de chaque candidat, même si les checkpoints varient dans le même batch.
- Persistance Production V2 passée au schéma 6 avec compatibilité des anciens projets. Cache frontend passé à `production-v2-lab.js?v=20260902.1` et `lab.css?v=20260902.1`.
- Validation : 38 tests Production V2 ciblés puis 728 tests complets passent; compilation Python et `git diff --check` sont propres hors avertissements CRLF existants.

### Broken / missing
- Aucun smoke test manuel dans un navigateur réel n’a été exécuté après le patch; il faut recharger complètement PanelForge pour prendre les nouveaux assets.
- Le canal `thinking` n’est affiché que si le gateway LLM le fournit réellement; sinon la trace indique explicitement qu’il n’a pas été fourni.

### Next steps (max 3)
1. Recharger Production V2 et vérifier visuellement les quatre presets, leur coût et le grisage du feedback lorsque le prompt est conservé.
2. Tester un passage Last Frame → Nouvelle branche First Frame depuis R1, puis ajouter volontairement une ancienne image via le guidage explicite pour comparer les deux comportements.
3. Tester un batch `Comparer les LoRA` avec une contrainte `inclure wetness` et contrôler dans la trace l’appel unique de planification et les piles réellement rendues.

### Risks / open questions
- `Faire évoluer entre les rendus` est volontairement séquentiel et donc plus lent; son coût augmente avec le nombre de candidats et reste visible avant lancement.
- `Ajustement standard` réécrit un prompt commun et utilise de nouvelles seeds afin d’éviter trois sorties déterministes identiques; les presets techniques conservent une seed commune pour rendre la comparaison interprétable.

## Patch 2026-09-02 — aperçu live Production V2 et initialisation Video Lab

### Works
- L’audit du run `Futuristic moto` confirme que son premier Plan caméra était valide et que le preview a réussi. Les erreurs suivantes venaient de réponses de révision LLM invalides (`target_clause` commençant par `Begin`/`Start`, objet au lieu d’une liste, puis vocabulaire caméra interdit) ; elles ont été rejetées avant persistance et n’ont pas modifié le snapshot utilisé par le rendu final.
- Production V2 relaie maintenant les previews H3 exactement comme H3 Base : frames WebSocket binaires, `kj_preview_override` en base64 et URLs de preview sont affichés dans un bloc `Aperçu de création` pendant le preview ou le rendu final.
- Un bouton `Annuler ce rendu` est placé directement dans le panneau de progression. Il réutilise l’annulation Production V2 existante, qui transmet déjà la demande à l’essai H3 actif.
- L’entrée principale `Video Lab` initialise désormais le menu `Texte Instagram`, comme le faisait déjà son sous-onglet. Les modèles LLM, profils éditoriaux et projets sont donc chargés sans rafraîchissement manuel de la page.
- Les caches passent à `lab.css?v=20260902.2`, `production-v2-lab.js?v=20260902.2` et `social-lab.js?v=20260902.1`.
- Validation : 42 tests ciblés puis les 728 tests complets passent ; `git diff --check` ne remonte que les avertissements CRLF préexistants.

### Broken / missing
- Aucun rendu ComfyUI réel ni smoke test navigateur n’a été lancé pendant ce patch.
- Le contrat strict des directives caméra et l’absence de retry silencieux restent volontairement inchangés.

### Next steps (max 3)
1. Recharger PanelForge, lancer un rendu final Production V2 et confirmer que l’aperçu live se met à jour puis que `Annuler ce rendu` interrompt bien l’essai H3.
2. Ouvrir Video Lab depuis l’onglet principal et vérifier que modèles LLM et profils Instagram apparaissent au premier clic.
3. Si les rejets caméra restent fréquents sur de nouveaux runs, prévoir un patch séparé sur le contrat de révision plutôt qu’un contournement silencieux.

### Risks / open questions
- La disponibilité et la fréquence des images live dépendent des événements envoyés par les nœuds ComfyUI ; en leur absence, la progression continue et l’interface indique honnêtement que l’aperçu est en attente.

## Diagnostic 2026-09-02 — rejets des révisions caméra H3

### Works
- La révision caméra `0.2.0` est transactionnelle : une réponse invalide conserve le prompt et les directives précédents, tout en gardant le candidat comme brouillon. Aucun prompt partiellement invalide n’est envoyé à ComfyUI.
- Les échecs du run `Futuristic moto` ne viennent ni de l’audace ni d’un seul modèle : les deux modèles sélectionnés ont produit des formes rejetées à température 0,25.
- Cause racine : le contrat visible par le LLM demande une `spatial or visual continuation`, mais n’énumère ni les préfixes réellement acceptés par `_TARGET_PREFIX`, ni l’interdiction exacte des termes caméra, ni un exemple non-null montrant que `camera_directives` reste toujours une liste.

### Broken / missing
- Après un rejet, le modèle ne reçoit pas au prochain échange l’erreur précise du validateur. Répéter le même retour ajoute donc un nouveau tour utilisateur, mais ne lui apprend pas comment corriger sa structure.
- Production V2 montre l’erreur dans le journal, sans rendre le brouillon refusé et sa cause aussi visibles que H3 Base.

### Next steps (max 3)
1. Aligner le prompt de révision sur le validateur avec préfixes autorisés, termes interdits et exemple JSON valide pour une directive unique.
2. Ajouter une action utilisateur explicite `Corriger la structure et réessayer`, qui transmet l’erreur et le brouillon dans un appel supplémentaire non silencieux.
3. Exposer dans Production V2 le brouillon refusé et rappeler que le prompt courant n’a pas été modifié.

### Risks / open questions
- Un auto-fix sémantique silencieux de `target_clause` pourrait modifier l’intention caméra ; les seules normalisations déterministes sûres sont structurelles, par exemple envelopper un objet unique dans une liste quand un seul token est attendu.

## Patch 2026-09-02 — contrat caméra et réparation explicite

### Works
- Les recettes de révision caméra H3 Base et Ref2V indiquent maintenant explicitement que `camera_directives` reste toujours un tableau JSON, même pour une seule directive. Le contrat injecté énumère les préfixes `target_clause` acceptés, les termes caméra interdits et un exemple JSON non-null valide.
- Une réponse contenant un objet unique pour l’unique token caméra est normalisée mécaniquement en liste. Aucune correction sémantique de `target_clause` n’est réalisée : une formulation invalide reste refusée avant persistance.
- H3 Base, Ref2V et Production V2 affichent le brouillon refusé, l’erreur exacte et la garantie que le prompt courant est inchangé. Le bouton `Corriger la structure et réessayer · 1 appel LLM` déclenche uniquement sur action utilisateur un nouvel appel contenant l’erreur du validateur et le brouillon conservé; aucun retry silencieux n’a été ajouté.
- Production V2 sérialise désormais les informations de rejet du projet H3 enfant et journalise séparément la correction explicite. Les caches passent à `h3-render-lab.js?v=20260902.1` et `production-v2-lab.js?v=20260902.3`.
- Validation : 88 tests ciblés puis 731 tests complets passent. La vérification JavaScript avec Node n’a pas pu être exécutée car Node n’est pas installé dans cet environnement; les tests UI statiques passent.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué après ce patch.
- Le brouillon persistant est le prompt candidat récupéré de la réponse; lorsqu’aucun champ `prompt` ne peut être décodé, la réponse brute bornée est conservée.

### Next steps (max 3)
1. Recharger complètement PanelForge pour prendre les nouveaux assets, puis provoquer une révision caméra invalide et vérifier l’affichage du rejet dans H3 Base et Production V2.
2. Cliquer sur la correction explicite et vérifier dans les logs qu’un seul nouvel appel LLM est émis et qu’aucun rendu ne démarre automatiquement.
3. Surveiller les prochains runs pour confirmer que le contrat détaillé réduit les rejets `target_clause` sans assouplir le validateur.

### Risks / open questions
- Le modèle peut encore produire une clause sémantiquement invalide malgré le contrat détaillé; elle restera volontairement bloquée et nécessitera le bouton explicite.
- L’enveloppement objet-vers-liste ne s’applique que lorsqu’un seul token caméra est attendu, afin de ne masquer aucune ambiguïté multi-directive.

## Patch 2026-09-02 — durée de rendu non bloquante

### Works
- L’audit du dernier projet Production V2 confirme que le blocage venait de `configure_video` : toute durée différente de celle utilisée lors de la compilation déclenchait une erreur 422 avant enregistrement. Le projet et ses trois essais étaient donc restés à 6 s.
- Une modification de durée seule ne force plus la recompilation et ne supprime ni le projet H3 ni les previews existantes. Intention, ratio, modèle LLM de compilation et audace de conception restent des changements structurels exigeant une recompilation.
- Production V2 affiche immédiatement un avertissement du type `Prompt compilé pour 6 s · rendu configuré pour 10 s`, tout en laissant lancer une nouvelle preview. La recompilation volontaire continue d’archiver l’ancienne version et réaligne Brief, Plan, Prompt et durée.
- H3 Base et Ref2V utilisent le même avertissement non bloquant. Il est affiché dès la modification du champ et persisté sur l’essai rendu; les avertissements de durée survivent maintenant à la réussite et à l’import des keyframes.
- Les bornes techniques 5–15 s restent imposées par `VideoLabSettings`. Les caches passent à `h3-render-lab.js?v=20260902.2` et `production-v2-lab.js?v=20260902.4`.
- Validation : 91 tests ciblés, compilation Python, `git diff --check`, puis 734 tests complets passent. Seuls les avertissements CRLF préexistants sont signalés.

### Broken / missing
- Aucun smoke test navigateur ni rendu ComfyUI réel n’a été lancé après ce patch.
- Si un prompt libre n’emploie aucune des formulations de durée reconnues, aucun avertissement n’est fabriqué; le rendu reste autorisé.

### Next steps (max 3)
1. Recharger complètement PanelForge, passer un projet compilé à 6 s vers 10 s et vérifier que l’avertissement apparaît sans erreur 422.
2. Lancer une preview avec cette durée divergente et confirmer que l’essai conserve le warning dans ses détails.
3. Tester ensuite `Recompiler` pour vérifier que la nouvelle compilation à 10 s fait disparaître l’avertissement.

### Risks / open questions
- Allonger un rendu sans recompiler peut produire une fin ralentie ou tenue après les événements minutés; raccourcir peut couper les événements tardifs. Le warning rend désormais ce compromis explicite sans interdire l’expérimentation.

## Patch 2026-09-02 — LoRA actifs visibles sur les candidats Production V2

### Works
- Chaque carte candidat Production V2 affiche maintenant ses LoRA actifs directement dans l’en-tête replié du volet de métadonnées.
- L’affichage reste compact : un LoRA par ligne, nom tronqué par ellipsis, force toujours visible et nom complet disponible au survol.
- Les candidats sans LoRA conservent exactement leur résumé checkpoint/résolution précédent; le détail complet existant reste disponible à l’ouverture.
- Les caches passent à `lab.css?v=20260902.3` et `production-v2-lab.js?v=20260902.5`.
- Validation : 42 tests UI ciblés puis 735 tests complets passent; `git diff --check` ne remonte que les avertissements CRLF préexistants.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.

### Next steps (max 3)
1. Recharger complètement PanelForge et vérifier une carte avec plusieurs LoRA dans les états ouvert et fermé.
2. Confirmer sur une carte étroite que les noms longs sont tronqués tandis que les forces restent visibles.

### Risks / open questions
- Une pile comportant beaucoup de LoRA augmente nécessairement la hauteur du résumé, même si chaque ligne est volontairement très compacte.

## Patch 2026-09-02 — base visuelle assignable directement aux frames

### Works
- La carte `Base visuelle` de Production V2 propose maintenant deux actions compactes : `First frame` et `Last frame`.
- Ces actions réutilisent directement le candidat source et l’asset de la recette active; aucun rendu KREA2 ni nouvel asset n’est créé.
- La promotion passe par le contrat d’ancre existant : une frame du même rôle est remplacée, l’ajout de l’autre frame fait évoluer automatiquement la route vers FL2VA, et les rendus vidéo aval sont invalidés selon la règle existante.
- Un rôle déjà assigné à la base est indiqué par une coche et désactivé. En route Ref2V, les deux actions sont désactivées avec une explication au survol, car les références doivent être retirées avant de revenir aux ancres H3 Base.
- Les caches passent à `lab.css?v=20260902.4` et `production-v2-lab.js?v=20260902.6`.
- Validation : 43 tests UI ciblés puis 736 tests complets passent; `git diff --check` ne remonte que les avertissements CRLF préexistants.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.

### Next steps (max 3)
1. Recharger complètement PanelForge et assigner une base seule comme First, puis comme Last, pour vérifier les routes I2VA et L2VA.
2. Affecter la même base aux deux rôles et vérifier que la route devient FL2VA avec les deux cartes d’ancre visibles.
3. Vérifier qu’un projet Ref2V explique bien au survol pourquoi ces actions sont temporairement indisponibles.

### Risks / open questions
- Utiliser exactement la même image en First et Last frame est autorisé; cela peut être utile pour une boucle mais contraindre fortement le mouvement H3 selon le prompt.

## Patch 2026-09-02 — exploration aléatoire équilibrée des checkpoints KREA2

### Works
- Lorsque `Conserver Modèle` est décoché dans Production V2, la sélection des checkpoints est maintenant effectuée côté serveur par tirage aléatoire pondéré et ne dépend plus de l’ordre alphabétique du catalogue.
- Le poids favorise fortement les checkpoints les moins utilisés. L’historique est calculé sur tous les candidats Production V2 durables associés au profil mémoire actif, y compris les projets précédents.
- Les choix sont effectués sans doublon tant que le nombre de BF16 disponibles suffit pour remplir le batch. Si le catalogue ne marque aucun BF16, le pool complet reste le fallback historique.
- `Conserver Modèle` garde son comportement de verrouillage. L’interface renomme le sélecteur en `Checkpoint manuel` et explique quand le tirage équilibré s’applique.
- L’API accepte le nouveau drapeau explicite `explore_models`; sa valeur par défaut reste `false` pour préserver les autres appelants et tests existants.
- Le cache passe à `production-v2-lab.js?v=20260902.7`.
- Validation : compilation Python, 63 tests ciblés puis 738 tests complets passent; `git diff --check` ne remonte que les avertissements CRLF préexistants.

### Broken / missing
- Aucun batch KREA2 réel ni smoke test navigateur n’a été lancé pendant ce patch.

### Next steps (max 3)
1. Recharger PanelForge et lancer plusieurs batches avec `Conserver Modèle` décoché pour confirmer la diversité du catalogue réel.
2. Vérifier dans deux profils mémoire différents que leurs fréquences de sélection évoluent indépendamment.
3. Ajuster la force de pondération seulement après observation de plusieurs batches réels.

### Risks / open questions
- Le calcul relit l’historique des projets Production V2 au lancement d’un batch; le coût restera négligeable au volume actuel mais pourra nécessiter un compteur indexé si plusieurs milliers de projets s’accumulent.
- Un checkpoint tenté puis échoué compte actuellement comme utilisé, car le compteur mesure l’exposition du modèle plutôt que les seuls succès ou likes.

## Patch 2026-09-02 — création visible des profils mémoire Production V2

### Works
- Le bouton `Nouveau profil mémoire` n’utilise plus `window.prompt`, qui pouvait être bloqué ou invisible selon le contexte navigateur.
- Il ouvre maintenant un éditeur directement sous le sélecteur avec un champ de nom et les actions `Créer et sélectionner` / `Annuler`.
- Le nouveau profil est ajouté via l’API existante, le catalogue est rechargé puis ce profil est automatiquement sélectionné pour le nouveau projet.
- Entrée valide, Échap ferme, un nom vide utilise la validation native du champ et les doubles soumissions sont bloquées pendant la requête.
- Les caches passent à `lab.css?v=20260902.5` et `production-v2-lab.js?v=20260902.8`.
- Validation : 71 tests ciblés puis 739 tests complets passent; `git diff --check` ne remonte que les avertissements CRLF préexistants.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.

### Next steps (max 3)
1. Recharger complètement PanelForge, créer un profil depuis le formulaire d’un nouveau projet et vérifier sa sélection immédiate.
2. Créer un projet avec ce profil, puis confirmer que les futures sélections aléatoires de checkpoints utilisent son historique indépendant.

### Risks / open questions
- Si la création serveur réussit mais que le rechargement immédiat du catalogue échoue, le profil existera malgré l’erreur affichée et réapparaîtra au prochain chargement.

## Patch 2026-09-02 — démarrage Ref2V sans base préalable

### Works
- Production V2 permet maintenant de terminer un parcours commencé directement dans l’atelier `Référence Ref2V`, sans passer auparavant par un candidat de calibration.
- Tant qu’aucune recette visuelle n’est active, chaque candidat `reference` réussi expose `Démarrer Ref2V avec cette référence`. Cette action réutilise le chemin atomique existant : le candidat devient la recette technique interne et la première référence Ref2V.
- Une fois la recette créée, les candidats suivants retrouvent l’action normale `Ajouter aux références Ref2V`. Les First/Last frames restent indisponibles sans recette active.
- Le cache passe à `production-v2-lab.js?v=20260902.9`.
- Validation : 45 tests Production V2 ciblés puis 739 tests complets passent.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.
- Le catalogue LoRA ne possède encore que les dimensions `favorite` et `safety`; la future famille fonctionnelle discutée n’est pas implémentée.

### Next steps (max 3)
1. Recharger Production V2 et vérifier le nouveau bouton sur un projet sans base contenant des candidats `reference`.
2. Confirmer que cette action crée une route Ref2V puis que les références suivantes peuvent être ajoutées normalement.
3. Aligner la taxonomie LoRA avant implémentation : favori indépendant, filtre SFW/NSFW et famille fonctionnelle principale.

### Risks / open questions
- La recette visuelle existe techniquement après le raccourci, même si l’utilisateur n’a pas effectué une étape de base séparée; elle sert à conserver le checkpoint, le prompt, la seed et les LoRA du candidat initial.
- Les familles fonctionnelles LoRA doivent rester assez peu nombreuses pour éviter de remplacer une longue liste par une taxonomie tout aussi difficile à parcourir.

## Patch 2026-09-02 — catalogue LoRA fonctionnel et sliders

### Works
- Le favori LoRA est maintenant indépendant de sa catégorie durable. Le catalogue propose `SFW · Utility`, `SFW · Style`, `SFW · Sliders`, `NSFW · Utility`, `NSFW · Global`, `NSFW · Sliders`, `NSFW · Details`, `NSFW · Poses`, `Other · KREA EDIT — ne pas utiliser` et `Non classé`.
- L’organisateur en colonnes glissables est remplacé par une liste compacte : nom tronqué, menu de catégorie, étoile de favori et bouton `i`. La popup lit la sidecard locale et expose fichier, hash, base model, trained words, description, lien CivitAI et jusqu’à quatre aperçus chargés uniquement à l’ouverture.
- Les LoRA techniques KREA Edit restent visibles dans l’organisateur mais sont retirées des sélecteurs et des catalogues transmis à l’exploration LoRA assistée.
- L’inventaire réel contient 59 LoRA. Les 19 nouveaux fichiers du dossier `sliders` sont classés automatiquement : Cleavage, Underboob, Cum Amount et Penis Size dans `NSFW · Sliders`; les 15 autres dans `SFW · Sliders`.
- `b3tterbreast` était déjà absent du dossier et n’a donc nécessité aucune suppression. Les classements fonctionnels discutés pour Wetness, styles, global NSFW, détails, poses et autres sliders historiques sont appliqués par défaut et restent modifiables.
- Les caches passent à `lab.css?v=20260902.6` et `krea2-resource-ui.js?v=20260902.2`. Validation : 60 tests ciblés, compilation Python, inventaire réel, `git diff --check`, puis 740 tests complets passent.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.
- Trois anciens LoRA restent volontairement `Non classés` faute de consigne fonctionnelle : `INSANE_BY_STX_V4`, `Krea_2_zidiusArt_Melancholy_v2` et `we_paint_krea2`.

### Next steps (max 3)
1. Recharger complètement PanelForge et vérifier la densité de la liste ainsi que la popup `i` sur une sidecard réelle.
2. Tester un favori puis un changement de catégorie pour confirmer que les deux propriétés restent indépendantes dans tous les sélecteurs.
3. Classer les trois LoRA restants seulement après validation de leur usage réel.

### Risks / open questions
- Les aperçus de sidecards sont servis par CivitAI et nécessitent donc une connexion au moment où la popup est ouverte; le reste de la fiche reste local.

## Patch 2026-09-02 — fiche LoRA éditable

### Works
- La popup `i` charge maintenant immédiatement jusqu’à trois images de la sidecard locale au moment de son ouverture. Aucun aperçu distant n’est chargé tant que la fiche reste fermée.
- Les lignes `Nom`, `Force minimale`, `Force maximale` et `Notes additionnelles` possèdent un crayon. Chaque crayon ouvre le même formulaire d’édition et place le focus sur le champ demandé.
- Les annotations sont conservées dans l’état PanelForge `krea2_resources.json`; les fichiers `.rgthree-info.json` restent inchangés. Un nom vide restaure le nom de la sidecard, et les forces peuvent être laissées vides.
- Les forces éditées sont bornées entre −1 et 1 et la sauvegarde refuse une force minimale supérieure à la maximale. Fichier, hash, modèle de base, trained words et description CivitAI restent en lecture seule.
- Les caches passent à `lab.css?v=20260902.7`, `krea2-resource-ui.js?v=20260902.3` et `20260902.1` pour les quatre consommateurs du catalogue. Validation : 81 tests ciblés, compilation Python, `git diff --check`, puis 740 tests complets passent.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch.
- Une sidecard comportant moins de trois images ne peut naturellement afficher que les aperçus disponibles.

### Next steps (max 3)
1. Recharger complètement PanelForge, ouvrir une fiche riche en aperçus et vérifier le rendu des trois images.
2. Modifier le nom, les forces et les notes, rouvrir la fiche puis confirmer leur persistance.

### Risks / open questions
- Les aperçus dépendent toujours des URLs CivitAI enregistrées dans la sidecard et peuvent être indisponibles hors connexion.

## Patch 2026-09-03 — fiches checkpoint et sélecteur LoRA KREA2 moderne (patch 1)

### Works
- Les checkpoints KREA2 disposent maintenant du bouton `i` dans le catalogue. Leur fiche expose fichier, taille, précision, nom, base model, trained words, description, notes, lien CivitAI et jusqu’à trois aperçus chargés uniquement à l’ouverture.
- Le nom affiché et les notes d’un checkpoint sont éditables localement avec le crayon. Les champs de force restent réservés aux LoRA et sont rejetés par l’API pour un checkpoint.
- La recherche CivitAI est explicite depuis la fiche : elle utilise le hash déjà présent dans une sidecar, sinon un nom de fichier exactement identique. Une correspondance ambiguë n’est jamais choisie silencieusement et les métadonnées retenues sont mises en cache dans `krea2_resources.json`.
- Aucun SHA-256 de checkpoint ou de LoRA n’est calculé. Le SHA-256 interne restant ne porte que sur le petit identifiant texte stable de la ressource; les hashes de sidecars existants restent lus sans parcourir les poids.
- Le sélecteur LoRA KREA2 partagé remplace les quatre menus vides fixes : sans LoRA, seul `+ Ajouter une LoRA` apparaît; la popup permet recherche, filtre de catégorie, favoris et accès à la fiche `i`.
- Chaque LoRA active occupe une ligne compacte avec nom tronqué, force, fiche et suppression. Les doublons sont exclus et le réordonnancement reste disponible dans Batch.
- Le composant est branché dans KREA2 Assisted, Batch, Edit, Production V1 et Production V2. La limite fonctionnelle reste volontairement à quatre LoRA dans ce premier patch.
- Les caches passent à `20260903.1` pour le CSS, le composant de ressources et ses cinq consommateurs. Validation : compilation Python, 66 tests UI ciblés, 18 tests catalogue/API ciblés, `git diff --check`, puis 743 tests complets passent.

### Broken / missing
- Aucun smoke test navigateur réel n’a été effectué pendant ce patch; Node.js n’est pas installé dans l’environnement pour exécuter un parseur JS séparé.
- Les checkpoints sans correspondance CivitAI exacte restent avec leur fiche locale et un lien de recherche; aucune sidecar artificielle n’est créée automatiquement.
- Le passage de quatre à dix LoRA et son alignement complet dans les contrats/domaines restent réservés au patch 2.

### Next steps (max 3)
1. Recharger complètement PanelForge et tester le sélecteur moderne ainsi que la fiche `i` dans Production V2 puis KREA2 Assisted.
2. Lancer explicitement la recherche CivitAI sur quelques checkpoints réels et relever les fichiers sans correspondance exacte pour créer leurs sidecars par itération.
3. Implémenter le patch 2 : pile dynamique jusqu’à dix LoRA KREA2 dans toutes les interfaces et validations serveur concernées.

### Risks / open questions
- La recherche sans hash dépend du nom de fichier public CivitAI : un fichier renommé peut ne pas être trouvé, tandis qu’un nom dupliqué restera volontairement non résolu.
- Les aperçus distants restent tributaires de CivitAI et de la connexion au moment de l’ouverture de la fiche.

## Patch 2026-09-03 — premier checkpoint exploratoire et clones image 4 MP

### Works
- Dans Production V2, décocher `Conserver Modèle` ne remplace plus le checkpoint choisi pour le premier candidat. Le candidat 1 utilise toujours la valeur visible dans le sélecteur; seuls les candidats 2 à X sont tirés aléatoirement en favorisant les checkpoints les moins utilisés.
- Les checkpoints exploratoires suivants restent sans doublon tant que le catalogue BF16 comporte assez d’alternatives. Si aucune alternative n’existe, le checkpoint choisi est réutilisé.
- Le formulaire indique dynamiquement `Checkpoint du candidat 1` en exploration et `Checkpoint retenu pour tous les candidats` lorsque le modèle est conservé.
- Chaque image KREA2 réussie propose maintenant côte à côte les clones `2,1 MP` et `4 MP`. Les deux actions reprennent strictement le prompt, la seed, le checkpoint et la pile LoRA du candidat source, sans appel LLM.
- L’historique des clones affiche leur résolution réelle au lieu du libellé fixe `clone 2,1 MP`.
- Le cache Production V2 passe à `production-v2-lab.js?v=20260903.2`. Validation : compilation Python, 67 tests ciblés, `git diff --check`, puis 746 tests complets passent.

### Broken / missing
- Aucun rendu KREA2 réel ni smoke test navigateur n’a été exécuté pendant ce patch.
- La pile dynamique jusqu’à dix LoRA n’est pas incluse ici et reste le patch 2 convenu.

### Next steps (max 3)
1. Recharger complètement Production V2 et confirmer visuellement le checkpoint du candidat 1 sur un batch exploratoire réel.
2. Lancer un clone 4 MP depuis une image basse résolution et vérifier son coût/temps sur ComfyUI.
3. Implémenter le patch 2 pour autoriser jusqu’à dix LoRA KREA2 dans toutes les interfaces et validations concernées.

### Risks / open questions
- Un clone 4 MP est volontairement coûteux; l’action reste explicite et ne fait pas partie d’un batch automatique.

## Patch 2026-09-03 — sélecteurs KREA2 modernes, dix LoRA et traces de compilation (patch 2)

### Works
- Le checkpoint KREA2 n’est plus un menu natif dans les ateliers concernés : le contrôle compact ouvre un sélecteur recherchable et groupé (`Favoris`, `BF16`, `INT8`, précision inconnue), avec étoile et fiche `i` accessibles à la fois sur la valeur active et dans chaque résultat. Fermer une fiche ouverte depuis le sélecteur rend la main au même sélecteur sans perdre recherche ni position.
- La pile LoRA KREA2 partagée accepte maintenant de zéro à dix entrées. Seules les lignes actives et le bouton `+ Ajouter une LoRA` sont affichés; recherche, catégories, favoris, fiche `i`, remplacement, suppression et réordonnancement Batch restent disponibles.
- Les contrats serveur KREA2 Assisted, Batch, Edit, Production V1 et Production V2 acceptent dix LoRA. Les rendus Batch de cinq à dix LoRA convertissent uniquement le graphe compilé historique vers `Power Lora Loader (rgthree)`; KREA2 Edit ajoute les entrées dynamiques au Power Loader déjà présent. Les workflows sources et leurs hashes versionnés restent inchangés.
- Le menu `Preset d’itération` de Production V2 est supprimé. Les contrôles explicites Conserver Prompt/Seed/Modèle/LoRA et l’indicateur du nombre de rendus/appels LLM restent la seule configuration visible.
- La compilation vidéo Production V2 conserve une trace durable par tentative pour Brief, Plan JSON et Prompt final. Pendant le streaming, l’appel actif ouvre automatiquement son `Thinking du modèle`; l’entrée, l’output brut et toute erreur de transport ou de validation restent consultables après succès, retry ou échec.
- Les caches passent à `lab.css?v=20260903.3`, `krea2-resource-ui.js?v=20260903.3` et aux versions datées du jour pour tous les consommateurs modifiés. Validation : compilation Python, 135 tests ciblés, trois tests verticaux des nouveaux chemins, `git diff --check`, puis 752 tests complets passent.

### Broken / missing
- Aucun smoke test dans un navigateur réel ni rendu ComfyUI à dix LoRA n’a été exécuté pendant ce patch; Node.js n’est pas installé pour un parsing JS indépendant.
- Le petit atelier T2I KREA2 historique ne possède toujours pas de pile LoRA dans son contrat de rendu; il reçoit le nouveau sélecteur de checkpoint lorsque le catalogue KREA2 partagé est disponible.

### Next steps (max 3)
1. Redémarrer/recharger complètement PanelForge et vérifier le checkpoint compact `nom + étoile + i` dans Production V2.
2. Ouvrir le sélecteur LoRA, naviguer fiche → fermer → sélecteur, puis lancer un rendu réel avec cinq LoRA avant de tester une pile de dix.
3. Lancer une compilation Brief → Plan → Prompt et confirmer que le thinking et l’output brut progressent dans les volets pendant les trois appels.

### Risks / open questions
- Le support de cinq à dix LoRA repose sur les entrées dynamiques officielles de `Power Lora Loader (rgthree)`; un smoke ComfyUI réel reste nécessaire pour confirmer la version du custom node installée sur la machine.
- Les fiches et aperçus de checkpoints sans sidecar dépendent toujours d’une correspondance exacte par nom sur CivitAI; aucune ambiguïté n’est résolue automatiquement.

## Audit 2026-09-04 — file KREA2 Assisted et fiche cielbleu

### Works
- L’interface KREA2 Assisted autorise déjà un nouveau clic dès que la requête de lancement précédente est revenue; les tentatives et leurs réglages sont persistés séparément.
- La file native ComfyUI et l’annulation ciblée permettent techniquement de soumettre plusieurs rendus sans exécution GPU parallèle.
- L’inventaire ComfyUI confirme les noms `Krea2/cielbleuKrea2_v1bf16.safetensors` et `Krea2/soliloquy_v2.safetensors`.

### Broken / missing
- `Krea2AssistedService.queue_attempt` refuse actuellement tout second rendu Assisted tant qu’une tentative quelconque est queued/running/cancel_pending, y compris dans un autre projet. Le second clic peut donc créer une tentative `created`, puis échouer au démarrage au lieu de l’ajouter à la file.
- L’API rgthree ne retourne aucune métadonnée en cache pour cielbleu ni Soliloquy. La recherche publique CivitAI sur le nom exact `cielbleuKrea2_v1bf16` ne retourne aucune fiche; PanelForge ne peut donc pas inventer ses aperçus.

### Next steps (max 3)
1. Remplacer le hard stop KREA2 Assisted par une soumission durable à la file ComfyUI et afficher `⚠ Ajouté à la file · position N` lorsque d’autres tentatives sont actives.
2. Éviter toute tentative `created` orpheline si la soumission échoue, et préciser l’état queued/running dans les cartes.
3. Ajouter à la fiche ressource un rattachement manuel par URL/ID CivitAI ou des aperçus locaux pour les checkpoints comme cielbleu sans correspondance automatique.

### Risks / open questions
- Avec plusieurs rendus soumis, le bouton d’annulation global doit viser explicitement le rendu en cours; l’annulation individuelle d’un élément encore en file serait une amélioration utile mais peut rester hors du premier patch.
- Soliloquy peut tirer ses images d’une sidecar locale ou d’un cache PanelForge antérieur; le workspace du serveur n’était pas actif au moment de l’audit pour confirmer cette provenance exacte.

## Audit 2026-09-04 — couverture des fiches checkpoints KREA2

### Works
- L’inventaire live ComfyUI contient 28 checkpoints KREA2. Sept sont déjà retrouvés par la recherche exacte actuelle : Artaix, Art Universe, Fascium, ReaKrea2 Turbo, Serendipity, Soliloquy et Solstice.
- Seize autres fichiers peuvent être rattachés à une fiche publique par recherche de famille, normalisation des suffixes techniques ou inclusion des résultats NSFW : Chimera Center Kroma, CielBleu Krea2, Krea 2 Turbo, les deux Henmix Turbo, Lustify, les familles Moody Amateur/Cutie/Krea2 Mix et RedCraft.
- La fiche CielBleu Krea2 existe (`model 2812328`, version `3171612`) et expose 20 aperçus. Elle est masquée par défaut dans la recherche API car NSFW, et son fichier public `cielbleuKrea2_v1.safetensors` diffère du nom local `cielbleuKrea2_v1bf16.safetensors`.
- Les fichiers Kroma v0.2 et v0.3 ont une source exacte et documentée sur Hugging Face (`lodestones/Kroma`), mais pas de fiche CivitAI exacte équivalente trouvée.

### Broken / missing
- Le résolveur CivitAI actuel ne demande pas les résultats NSFW et n’essaie que le stem brut du fichier avec une égalité stricte du nom; 21 des 28 checkpoints échouent donc aujourd’hui, alors que 16 ont une fiche de famille identifiable.
- Aucune fiche source fiable n’a été retrouvée pour les deux fichiers Dark Beast ni pour `krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors`.
- Les rattachements Moody Amateur v1 non-BF16 et RedCraft 3.0 restent probables mais non exacts, car leurs noms de fichiers publics diffèrent de ceux installés.

### Next steps (max 3)
1. Demander les URLs/IDs manuels pour Dark Beast (deux variantes) et GPT Grand PUSSY Truth; demander une fiche CivitAI Kroma seulement si elle est souhaitée à la place de Hugging Face.
2. Étendre le résolveur par une seconde passe explicite : `nsfw=true`, nom sans suffixes BF16/INT8/FP8 et recherche par famille, avec confirmation en cas d’ambiguïté.
3. Ajouter les rattachements confirmés au catalogue/sidecars sans calculer de SHA-256 sur les gros checkpoints.

### Risks / open questions
- Un nom de famille plausible ne prouve pas que le fichier local est byte-identique; les variantes renommées ou quantifiées doivent rester marquées comme rattachements de fiche, pas comme vérifications de hash.

## Patch 2026-09-04 — fiches checkpoints KREA2 via CivitAI.red

### Works
- Le lecteur de métadonnées utilise maintenant l’API `civitai.red`, inclut explicitement les résultats NSFW et essaie une recherche de famille après le nom de fichier brut. Les suffixes terminaux BF16/FP8/INT8/INT4/ConvRot peuvent être ignorés pour retrouver un fichier public équivalent.
- Des rattachements explicites, sans calcul de hash, couvrent CielBleu v1, Chimera Center Kroma v2, Dark Beast 3.0, Dark Beast KREA2 FP8 et REDGPT2/KREA2 GPT. Les deux fichiers Dark Beast locaux pointent vers leurs versions distinctes `3173268` et `3078453`.
- La sécurité retournée par CivitAI est conservée dans le catalogue : les fiches NSFW ouvrent `civitai.red`, les fiches SFW restent sur `civitai.com`. Un rattachement nominal affiche un avertissement indiquant que l’identité binaire n’a pas été vérifiée par hash.
- Le chemin réel a été testé contre l’API : Dark Beast 3.0, Dark Beast FP8, Chimera, REDGPT2, CielBleu et Henmix retournent chacun la bonne version et trois aperçus. Validation : compilation, tests ciblés, `git diff --check` et 755 tests complets passent.

### Broken / missing
- Les anciennes recherches négatives déjà présentes dans `workspace/krea2_resources.json` ne sont pas effacées automatiquement; le bouton `Actualiser depuis CivitAI` recharge la fiche avec le nouveau résolveur.
- Kroma v0.2/v0.3 reste documenté par Hugging Face sans fiche CivitAI exacte connue. Les variantes Moody Amateur non-BF16 et RedCraft renommée restent des rattachements de famille non confirmés.

### Next steps (max 3)
1. Redémarrer PanelForge, ouvrir les fiches concernées puis utiliser `Actualiser depuis CivitAI` si une ancienne réponse vide est encore affichée.
2. Confirmer visuellement les trois aperçus de CielBleu, Dark Beast et REDGPT2 dans le sélecteur de checkpoints.
3. Reprendre séparément le patch de file d’attente KREA2 Assisted demandé précédemment.

### Risks / open questions
- Les IDs fournis identifient la fiche et la version attendues, mais les fichiers locaux renommés/quantifiés ne sont volontairement pas déclarés byte-identiques sans hash.

## Audit 2026-09-04 — état REF2V et loader Hybrid

### Works
- Le workflow REF2V `0.2.0` charge bien les poids officiels BF16 `minimax_h3_fl2va_bf16.safetensors` et `minimax_h3_ref2va_bf16.safetensors` avec `MiniMaxH3HybridLoader`, preset `block_range_adaln`, blocs 25 à 49. Le schéma live ComfyUI contient le nœud et les deux poids.
- Cette configuration correspond au preset courant du loader de Scott Mudge : le code amont expose lui aussi 25–49 par défaut. Le guide Ref2VA épinglé par le profil PanelForge `0.4.0` est octet pour octet identique au guide officiel courant.
- Le backend partagé sait déjà traiter l’audace de Brief (`creative_audacity`, 0–3) et l’audace des révisions vidéo (`revision_audacity`, 0–3). La valeur de révision 0 conserve le comportement historique.

### Broken / missing
- L’interface REF2V Direct n’expose pas l’audace créative initiale ni le curseur d’audace des échanges vidéo présent dans H3 Base. Le payload du Brief omet `creative_audacity`; le mode rapide omet aussi ce champ dans son contrat. Les révisions vidéo partent donc implicitement à 0.
- Le workflow ne constitue pas l’unique recette Hybrid récente : l’implémentation communautaire ANe5s propose une stratégie plus légère 45–49 et n’est pas installée. Elle est alternative, pas démontrée supérieure au preset 25–49 actuel.
- La surface REF2V reste image-only dans PanelForge. MiniMax Ref2VA officiel accepte aussi des références vidéo/audio; l’UI autorise 1–9 images mais le snapshot du manifeste porte encore 1–3 et la durée publique PanelForge commence à 5 s alors que le cœur de plan accepte 4 s.

### Next steps (max 3)
1. Ajouter à REF2V Direct la parité d’audace : direction créative du Brief et curseur de révision vidéo `0/3 = standard historique`, y compris le mode rapide et la persistance/hydratation.
2. Publier une nouvelle version de workflow avec choix explicite de recette (`Hybrid 25–49` actuel, `Hybrid 45–49` expérimental, `Ref2VA natif`) et les comparer à prompt/seed/références identiques avant de changer le défaut.
3. Harmoniser ensuite les limites déclarées (jusqu’à 9 images, 4–15 s) et décider séparément si les références vidéo/audio entrent dans le périmètre PanelForge.

### Risks / open questions
- « Plus récent » ne signifie pas « meilleur » : 25–49 transfère davantage de comportement Ref2VA, tandis que 45–49 cherche une influence plus légère. Un A/B réel est nécessaire.
- Les deux poids BF16 complets sont très lourds; le workflow dépend du chargement dynamique/offload. Une variante préfusionnée ou quantifiée serait un axe de coût/mémoire, pas une mise à niveau qualitative automatique.

## Patch 2026-09-04 — parité d’audace REF2V / H3 Base

### Works
- REF2V Direct expose maintenant `Direction créative` et le curseur d’audace du Brief comme H3 Base. La direction reste désactivée par défaut; lorsqu’elle est activée, l’audace proposée est 2/3 et la variante `creative-direction@0.2.0` est attachée à la session.
- Le choix de variante et l’audace sont envoyés lors de la création, conservés lors d’un fork explicite, restaurés à la réouverture et intégrés au contrôle d’obsolescence du Brief. Le mode rapide standard réutilise le même payload.
- Le chat vidéo REF2V possède désormais `Audace du prochain ajustement`, initialisée à `0/3 = standard historique`; le moteur H3 partagé transmet déjà cette valeur sans changer le comportement par défaut.
- La route Super Fast accepte et persiste aussi `creative_audacity` dans son Brief déterministe. Le cache de `ref2v-direct.js` passe à `20260904.1`.
- Le workflow ComfyUI REF2V, le loader Hybrid, les poids BF16 et le preset de blocs 25–49 sont inchangés. Validation : compilation Python, 88 tests ciblés, `git diff --check`, puis 755 tests complets passent.

### Broken / missing
- Aucun smoke test dans un navigateur réel ni génération REF2V réelle n’a été exécuté pendant ce patch.
- La direction créative reste volontairement limitée à la recette mono-plan standard, conformément à H3 Base; les recettes multi-plan conservent leur comportement actuel.

### Next steps (max 3)
1. Redémarrer/recharger complètement PanelForge et vérifier que REF2V affiche les deux curseurs d’audace aux emplacements attendus.
2. Tester un run supervisé puis un run rapide avec Direction créative activée et confirmer le libellé `audace N/3` dans la session.
3. Comparer une révision vidéo à 0 puis à 2 ou 3 sur le même prompt REF2V.

### Risks / open questions
- Une session ayant déjà un Brief conserve son niveau d’audace historique; il faut repartir de ce run pour choisir une nouvelle variante de Brief, comme dans H3 Base.

## Handoff produit 2026-09-05 — contexte difficilement dérivable du code

### Works / décisions produit à préserver
- Production V2 est actuellement un atelier **human-first** de calibration et d’expérimentation. Le mode automatique/agent est une cible future : conserver états, traces et mémoire compatibles avec cette cible, sans encombrer l’usage humain présent.
- Parcours voulu : explorer environ 3 candidats KREA2 basse résolution pour trouver une recette visuelle ; commenter/liker chaque candidat ; poursuivre depuis une image avec un feedback général ; valider une recette ; créer indépendamment une First Frame, une Last Frame ou des références Ref2V ; compiler ensuite la vidéo avec les ancres réellement retenues.
- La recette visuelle transporte l’identité esthétique et technique (checkpoint, LoRA, style, prompt/seed de base), mais pas automatiquement toute la narration d’une branche. Un feedback Last Frame comme « mains ensanglantées » ne doit pas contaminer une nouvelle branche First Frame demandant des mains intactes.
- Les références entre branches doivent être **explicites et optionnelles** : montrer une autre frame peut préserver une pièce, une identité ou une composition, mais une nouvelle branche depuis la recette R1 doit pouvoir repartir proprement.
- Contrôles d’itération indépendants : `Conserver Seed`, `Conserver Prompt`, `Conserver Modèle`, `Conserver LoRA`. Une comparaison technique fixe prompt et seed, mais peut explorer plusieurs checkpoints. Si le prompt est conservé, l’échange LLM est grisé ; l’exploration LoRA assistée reste un appel LLM si les LoRA ne sont pas conservées.
- En exploration de checkpoints, le candidat 1 utilise toujours le checkpoint choisi ; seuls les suivants sont randomisés, avec préférence pour les modèles les moins souvent essayés dans le profil mémoire actif.
- Ordre visuel : plus récent en haut à gauche ; vidéos limitées à 3 cartes par ligne. Pour KREA2, des IDs historiques 1/2/3 s’affichent donc 3/2/1.
- Chaque candidat image doit pouvoir être relancé à réglages strictement identiques en 2,1 MP ou 4 MP. `Continuer depuis cette image` restaure checkpoint, résolution, LoRA, etc., et montre une copie de l’image près du feedback.
- Une base visuelle peut être affectée directement comme First Frame ou Last Frame. Une candidate peut aussi partir directement en Ref2V sans base préalable. `Utiliser directement cette image comme référence` signifie Ref2V ; First/Last restent le parcours H3 Base.
- Une recherche First/Last validée se replie mais doit pouvoir être rouverte. La carte `Base visuelle` est une recette/contexte et ne doit pas devenir silencieusement une entrée vidéo supplémentaire quand First/Last sont définies.
- Plusieurs profils mémoire sont indispensables, notamment SFW et NSFW. Le profil reste généralement stable dans un projet, avec possibilité secondaire de le changer.
- Le modèle LLM est choisi initialement puis peut changer à chaque nouvel échange KREA ou vidéo, sans réécrire l’historique. Les réponses doivent former un petit chat : changements recommandés, questions restantes, thinking/output repliables et visibles pendant le streaming.
- Contrat caméra : ne pas corriger silencieusement une `target_clause` sémantiquement invalide et ne pas retenter silencieusement. Rejeter transactionnellement, conserver le prompt courant, montrer le brouillon et l’erreur exacte, puis laisser l’utilisateur relancer. Une normalisation structurelle sûre reste acceptable.
- Sémantique de l’audace : `0/3` signifie toujours comportement historique. Elle autorise une mise en scène plus remplie quand la vidéo est trop lente, sans empiler mécaniquement des actions. H3 Base et Ref2V Direct gardent la direction créative désactivée par défaut ; activée, la proposition initiale est 2/3. Ne pas homogénéiser silencieusement les valeurs historiques de Production V2 sans discussion.
- Pour les tests : durée vidéo par défaut 6 s, previews Production V2 0,2 MP avec Spectrum ON, final 1,2 MP déclenché humainement. Changer la durée sans recompiler produit un warning, jamais un hard stop.
- Le ralentissement/gel final en L2VA 6 s est connu : H3 converge trop tôt vers la Last Frame. Décision actuelle : ne pas patcher ; défaut jugé moins gênant sur des durées longues.
- Le polling/refresh ne doit jamais voler le focus des textareas ni recharger les médias. C’est un point de régression important.
- UI progressive à gauche : `Projet` toujours visible ; `Recherche d’ancre` pendant KREA2 ; `Création vidéo` après validation ; `Réglages avancés` fermé. Un panneau replié conserve un résumé compact des réglages utilisés.
- LoRA : favoris indépendants des catégories ; sélecteur avec recherche/catégorie/favori/info ; fermer `i` revient au sélecteur au même filtre/scroll ; jusqu’à 10 LoRA, uniquement les lignes actives puis `+`. Résumé : un LoRA par ligne, nom tronqué + force, nom complet au survol.
- Taxonomie demandée : SFW Utility/Style/Sliders ; NSFW Utility/Global/Sliders/Details/Poses ; `Other - KREA EDIT - do not use` ; Unclassified. `Realism Engine Ideogram 4 + Krea 2 v3` est NSFW malgré son nom. Ne calculer automatiquement le SHA-256 ni des gros checkpoints ni des LoRA.
- Ref2V Hybrid doit rester inchangé pour le moment : loader Scott et plages actuelles. La demande est la parité UI/audace avec H3 Base, **pas** un changement de Hybrid.

### Broken / missing
- Le patch Ref2V audace a 755 tests verts, mais aucun smoke navigateur/Comfy réel n’a validé les chemins standard, rapide et une vraie génération Hybrid.
- La file d’un second rendu KREA2 Assisted pendant qu’un rendu tourne reste à faire : soumission durable à Comfy, message `Ajouté à la file · position N`, états queued/running explicites et annulation ciblée sans tentative orpheline.
- Plusieurs composants récents (jusqu’à 10 LoRA, navigation `i`, profils mémoire, progression/annulation des finals) restent sensibles aux essais navigateur réels malgré les tests.
- Les caches CivitAI négatifs anciens demandent parfois un rafraîchissement manuel. Kroma v0.2/v0.3 n’a pas de fiche exacte connue. Trois LoRA restent à classer : `INSANE_BY_STX_V4`, `Krea_2_zidiusArt_Melancholy_v2`, `we_paint_krea2`.
- Ref2V reste image-only dans l’UI ; vidéo/audio, manifeste 1–9 et minimum 4 s sont des évolutions possibles, pas des priorités validées.

### Next steps (max 3)
1. Redémarrer/recharger et faire un smoke navigateur + une vraie génération Ref2V : direction créative ON/OFF, révision audace 0 puis 2/3, chemin rapide, Hybrid inchangé.
2. Tester réellement une pile de 5–10 LoRA, le retour fiche `i` → sélecteur et la création/changement de profil mémoire.
3. Implémenter ensuite la queue KREA2 Assisted si la priorité est confirmée.

### Risks / open questions
- Worktree actif : `D:\Code\localQ\.panelpatch`, très sale avec des changements utilisateur accumulés. Ne rien reset/revert et garder les diffs petits.
- Des tests verts ne garantissent ni un asset JS rafraîchi dans le navigateur ni le comportement d’un flux Comfy réel.
- La séparation mémoire esthétique/narrative par branche est une intention forte, mais son interface et sa persistance ne sont pas encore entièrement spécifiées.
