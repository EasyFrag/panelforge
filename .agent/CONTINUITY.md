# CONTINUITY

## Release 2026-09-19 — PanelForge 1.0.0

### Works
- Le placeholder historique `0.1.0` du paquet et de `panelforge.__version__` passe à `1.0.0` pour la première version majeure de l'application.
- La branche de travail est un descendant direct de la branche stable distante : la publication peut donc mettre `master` à jour par fast-forward, sans merge conflict. Le dépôt GitHub utilise `master` comme branche par défaut ; aucune branche `main` concurrente n'est créée.
- Les recettes, manifests ComfyUI, schémas de stockage et numéros de cache navigateur conservent leurs versions propres. Ils ne sont pas artificiellement renommés `1.0.0` avec l'application.
- Les notes de version sont dans `docs/releases/1.0.0.md`. La publication cible le tag annoté `v1.0.0` ainsi que les branches distantes `feature/vocal-normalizer-dialogue-register` et `master`.

### Broken / missing
- GitHub CLI n'est pas installé : la publication utilise Git et un tag distant, sans objet GitHub Release enrichi avec pièces jointes.
- La suite complète conserve les 38 échecs et 31 erreurs historiques documentés hors des surfaces ciblées ; la version majeure ne prétend pas les masquer.

### Next steps (max 3)
1. Utiliser `v1.0.0` comme point de retour stable avant les prochaines automatisations.
2. Continuer le développement sur une branche dédiée après publication plutôt que directement sur `master`.
3. Résorber progressivement les anciens tests H3/Combat avant une future version corrective.

## Patch 2026-09-19 — arc long plus causal, prompts spécialisés et brouillon revalidable

### Works
- Le parcours Histoires conserve exactement le même nombre d'appels LLM. Les propositions, l'arc long et le développement d'un épisode ont maintenant des consignes distinctes : le prompt d'arc ne transporte plus les exemples de concepts ni le quota de dialogues par micro-scène.
- L'Architecte doit calibrer chaque épisode sur `target_scene_count × target_clip_seconds`, montrer tout incident causal qui n'a pas déjà eu lieu, introduire une preuve avant son usage et accomplir visiblement le payoff local. Les beats sont des jalons et ne sont plus présentés comme un découpage mécanique des clips.
- Le Rédacteur reçoit uniquement la bible compacte, l'épisode sélectionné et la mémoire réelle des épisodes précédents. Il doit réparer une ouverture qui suppose un incident jamais montré, respecter la capacité temporelle et jouer le payoff dans la dernière scène.
- Une ou deux propositions ne reçoivent plus les anciennes phrases contradictoires imposant trois pistes. Une relance identique après échec ne duplique plus le tour utilisateur dans le contexte.
- Un brouillon JSON refusé par une règle applicative peut être appliqué avec **Revalider la réponse reçue**, sans nouvel appel LLM. **Relancer le LLM** reste une action séparée.
- Validation : 35 tests Histoires et 28 tests navigateur/Lab verts. Suite complète : 1 415 tests, avec les 38 échecs et 31 erreurs historiques hors de cette surface, soit les mêmes comptes qu'avant l'ajout des deux nouveaux tests.

### Broken / missing
- Aucun appel LLM réel n'a été lancé pendant le patch ; l'effet sur la durée du thinking et la cohérence du prochain arc doit être observé sur un nouveau run.
- La revalidation ne répare pas un JSON incomplet ou sémantiquement toujours invalide : dans ce cas, il faut corriger la règle concernée ou relancer le LLM.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger `stories.js?v=20260919.2`.
2. Créer un nouvel arc long Fruit avec le même format que le run audité et comparer le thinking, l'ouverture de l'épisode 1 et son payoff local.
3. Si une réponse complète est rejetée uniquement après une correction locale, utiliser d'abord **Revalider la réponse reçue** au lieu de demander une seconde génération.

## Correctif 2026-09-19 — espèce Fruit non bloquante

### Works
- Le contrat Fruit ne rejette plus une fiche uniquement parce que son espèce n'emploie pas la formulation stricte `espèce pomme` ou `pomme anthropomorphe`. Le brouillon réel de `L'éclat de Pomitta`, qui dit naturellement `Pomme adulte`, est maintenant accepté.
- Aucune consigne LLM n'a été modifiée. Lorsque l'espèce est détectée sans ambiguïté, le contrôle existant reliant le nom fruité à cette espèce reste actif.
- Validation : les 33 tests `tests.test_stories` sont verts et le brouillon persisté de Pomitta passe directement le contrat.

### Broken / missing
- Une fiche ne nommant pas explicitement l'espèce ne permet plus au validateur local de vérifier que le radical du nom correspond précisément au fruit ; la consigne éditoriale reste responsable de ce cas.

### Next steps (max 3)
1. Redémarrer PanelForge avant de relancer la création de l'arc de Pomitta.
2. Vérifier que le nouveau run franchit l'étape d'arc sans l'ancien message sur l'espèce.

## Patch 2026-09-19 — Fruits audio-first et noms fruités

### Works
- La famille Mélodrame fruits exige désormais, dans ses histoires générées courtes, longues et leurs suites, un nom unique inventé à partir de l'espèce : `Figos/Figette`, `Pomitto/Pomitta`, `Mangotino/Manguette`, `Ananito/Ananette`, etc. Les formes humaines telles que `Nour Myrtille` sont refusées avant persistance du scénario ou de l'arc.
- Le contrat de rédaction applique un test d'écoute : situation, intention, obstacle, causalité et conséquence doivent être compréhensibles via les dialogues, pensées ou voix off. Chaque micro-scène Fruit contient de une à quatre entrées `dialogue`; un texte écrit indispensable est lu ou reformulé.
- Le contrôle est déterministe pour les noms et la limite de quatre lignes, en complément de la consigne sémantique donnée à l'Architecte et au Rédacteur. Le brouillon LLM reste conservé lorsqu'une sortie est refusée. Le mode Script fidèle est exempté afin de ne jamais renommer un personnage humain ni altérer un dialogue fourni.
- Le précédent changement de valeurs par défaut a été resserré : seuls audace, vie de scène, caméra, mouvements additionnels et dialogues/réactions passent à `3/3/3/3/1`. H3 Base et REF2V Direct retrouvent leur recette vidéo historique ; le manifeste BUNNY retrouve ses LoRA Combat + Motion Repair. Dans Histoires, la durée du rendu continue de provenir automatiquement de chaque scène.
- Validation : 33 tests Histoires, 41 tests Episodes/LoRA et 46 tests navigateur/web/dialogues verts. Les tests H3 BUNNY couvrent aussi la restauration des brouillons après retour aux recettes vidéo historiques. La suite complète exécute 1 413 tests et conserve 38 échecs / 31 erreurs historiques hors de cette surface ; toutes les suites directement touchées restent vertes.

### Broken / missing
- Le test d'écoute sémantique repose sur la consigne éditoriale ; le validateur local garantit la présence de 1–4 paroles mais ne prétend pas juger automatiquement leur qualité narrative.
- Aucun appel LLM ni rendu H3 réel n'a été lancé pendant ce patch.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger les valeurs créatives et l'action de rendu armé déjà ajoutées au patch précédent.
2. Créer une nouvelle histoire Fruit courte puis longue et vérifier que les noms sont immédiatement fruités et que chaque scène reste compréhensible en n'écoutant que les paroles.
3. Si un nouveau run reste trop elliptique malgré le contrat audio-first, auditer ses quatre paroles par scène avant d'ajouter un évaluateur LLM ou un curseur de densité.

## Patch 2026-09-19 — catalogue Persona, presets classés et KREA2 Assisted bilingue

### Works
- Le catalogue KREA2 expose une catégorie logique **NSFW - Persona** en bas des catégories métier. Les LoRA du sous-dossier `people` y sont classés sans déplacer aucun fichier. `pussy_helper_v01alpha.safetensors` reste explicitement dans **NSFW · Details** et `lenovo_krea2.safetensors` reste **Non classé**, même s'il se trouve sous `people`.
- Les presets de style portent désormais une catégorie **Work / Fun / NSFW / Archive**. Les sélecteurs Assisted et Fabrication sont groupés dans cet ordre ; le gestionnaire compact permet de reclasser ou supprimer un preset. Le stockage passe au schéma 2 avec révisions immuables et tombstones de suppression ; le schéma 1 est relu avec `Work` par défaut.
- Supprimer ou mettre à jour un preset ne modifie jamais sa copie déjà épinglée dans un projet ou un épisode. Un preset retiré reste visible comme copie du projet, mais `Réappliquer` est désactivé puisque sa source catalogue n'existe plus.
- KREA2 Assisted propose English / 中文 dès le nouveau projet et pendant la conversation. Le preset présélectionne sa langue, l'utilisateur peut l'écraser, les échanges et rendus suivants mémorisent le choix, et aucun appel supplémentaire n'est ajouté au parcours normal. Le bouton de conversion LLM n'apparaît que lorsqu'un prompt courant existe et que la langue sélectionnée diffère de la langue persistée.
- Validation : compilation Python, `git diff --check` et **140 tests ciblés verts**, dont parcours Chromium Assisted/Fabrication/catalogue. Suite complète : **1 409 tests**, 40 échecs et 32 erreurs historiques hors de cette surface (contre 42/32 consignés avant ce patch) ; tous les tests du patch restent verts.

### Broken / missing
- Aucun appel LLM ni rendu KREA2 réel n'a été lancé pendant ce patch ; la qualité comparée d'un prompt chinois reste à évaluer sur les modèles de l'utilisateur.
- La suppression masque le preset du catalogue sans bouton d'annulation. Ses révisions et les copies épinglées sont conservées sur disque, mais une restauration UI n'est pas encore proposée.
- Le classement Persona est logique et déterministe ; il ne crée ni ne déplace de dossier sur le serveur ComfyUI.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger `lab.css`, `krea2-resource-ui.js`, `episodes.js` et `krea2-assisted-lab.js` datés du 19 septembre.
2. Ouvrir **Gérer** dans Création assistée, vérifier Work/Fun/NSFW/Archive et confirmer que les LoRA `people` apparaissent dans **NSFW - Persona**, avec Pussy Helper et Lenovo dans leurs catégories prévues.
3. Tester le même projet en English puis 中文 : échange normal après bascule, conversion explicite du prompt courant, puis deux rendus comparables.

## Patch 2026-09-19 — histoires courtes/longues et casting hérité

### Works
- Le parcours Histoires propose désormais deux formats isolés. **Histoire courte** conserve les propositions, le script fidèle, les suites cumulatives et le nombre exact de scènes existants. **Histoire longue** ajoute après le choix d'une piste un arc global validé de quatre épisodes autoportants et reliés.
- Chaque épisode long possède son propre réglage de 1 à 12 micro-scènes et de 5 à 15 secondes par clip. Il est développé séparément ; les actions causales importantes doivent rester visibles et la mémoire compacte des épisodes déjà écrits prévaut sur l'arc prévu, sans appel LLM de résumé supplémentaire.
- La bible d'arc impose des identifiants et noms stables aux personnages récurrents. Les quatre scénarios restent dans un même projet, mais Fabrication produit une préparation distincte par épisode grâce à une empreinte incluant l'identifiant d'épisode.
- À la création de la Fabrication suivante, les images de personnages retenues sont présélectionnées depuis le dernier épisode antérieur compatible. Le même héritage fonctionne pour une suite courte créée depuis le bouton dédié via `parent_story_id` et remonte toute la chaîne d'ascendance si un épisode intermédiaire n'a pas de Fabrication. Seules l'image et sa provenance sont reprises : prompts, LLM, projet KREA2, réglages techniques et décors restent indépendants.
- Validation : compilation Python, `git diff --check` et 95 tests ciblés verts (`stories`, `episodes`, navigateurs, routes web et page Lab), incluant arc exact de quatre épisodes, formats indépendants, mémoire réelle, isolation du mode court et héritage d'images. Suite complète : 1 405 tests exécutés, 42 échecs et 32 erreurs historiques hors de cette surface (contre 43/32 consignés avant ce patch) ; les suites Histoires/Fabrication ciblées restent entièrement vertes.

### Broken / missing
- Le nombre de quatre épisodes est volontairement fixe dans cette première version ; seule la longueur interne de chaque épisode est configurable.
- Une histoire longue commence uniquement par les propositions. Le mode Script fidèle et l'ancien mode Suite restent disponibles dans Histoire courte.
- Aucun appel LLM ni rendu KREA2/H3 réel n'a été lancé pendant ce patch.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger `stories.js`, `stories.css` et `episodes.js` version `20260919.1`.
2. Tester un arc long avec deux épisodes volontairement courts, puis ouvrir Fabrication sur le second et vérifier que les portraits retenus au premier sont déjà sélectionnés.
3. Après retour d'usage, décider si le nombre global d'épisodes doit lui aussi devenir configurable ; ne pas le confondre avec le nombre de micro-scènes par épisode.

## Goal

- **Réglage A/B Unsloth recommandé le 18 septembre, sans modification automatique** : dans Run Settings, remplacer `Context Length: Auto` par `32768` sur le modèle réellement utilisé, conserver `KV q8_0`, MTP 3, un slot, Vision et les arguments de stabilité image `--batch-size 2048 --ubatch-size 1120`, puis recharger le modèle. Ne modifier aucun autre paramètre pendant le premier essai. La capture montre HauhauCS Uncensored, tandis que les trois appels sociaux audités utilisaient `unsloth/gemma-4-31B-it-qat-GGUF` ; le réglage doit être mémorisé séparément pour chacun. Si 32k limite un usage long, tester ensuite 65536 ; viser une estimation GPU inférieure à environ 30–31 Gio et l'absence de mémoire GPU partagée.

- **Audit latence Unsloth du 18 septembre, sans correctif** : les trois demandes `social.instagram.generate@0.1.0` sur `local::unsloth/gemma-4-31B-it-qat-GGUF` ont été correctement sérialisées par la voie locale. Elles ont attendu respectivement 0 s, 80 s et 124 s avant admission, puis occupé la machine 94 s, 60 s et 56 s. Le premier appel inclut environ 14 s de démarrage du serveur et 22 s de chargement du modèle. Chaque appel transmet quatre keyframes et environ 2 156 tokens de prompt ; llama.cpp passe ensuite 46–47 s au prompt multimodal mais seulement 9–10 s à générer environ 900–1 050 tokens, à environ 100 tokens/s. Le processus réserve 31,42 Gio de VRAM dédiée et déborde de 1,77 Gio en mémoire GPU partagée avec `n_ctx_slot=204288`, alors que les requêtes observées utilisent environ 3 200 tokens au total. Un essai identique à 17 h 02 avec le même build llama.cpp `b11027-mix-3e83366` avait pris 12,7 s, dont 4,5 s de prompt eval : la mise à jour seule n'explique donc pas la régression. Priorité proposée avant tout patch PanelForge : tester un contexte Unsloth nettement plus petit / auto-fit, puis distinguer visuellement attente FIFO, chargement et temps avant premier token.

- **Diagnostic de l'alerte DLSS fantôme du 18 septembre, sans correctif** : `dlss-lab.js` interroge `/api/dlss/jobs` dès le chargement puis toutes les 15 secondes même sans tâche DLSS. Une erreur réseau transitoire publie une notice globale persistante `Suivi DLSS indisponible`, qui n'est pas retirée lors du polling réussi suivant. Les endpoints DLSS et ordonnanceur répondent actuellement HTTP 200 ; cette alerte ne signifie pas qu'un DLSS était lancé.

- **Sélecteur local de la variante chinoise corrigé le 18 septembre** : exposer dans H3 Base et REF2V Direct la bascule standard `Local · Unsloth`, cochée par défaut, et présélectionner `HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP` lorsqu'il est disponible.

- **Progression Spectrum H3/REF2V débloquée le 18 septembre** : accepter le compteur d'étapes réellement exécutées par Spectrum (`2/4`, par exemple) au lieu de rejeter tout compteur différent des 25 steps du scheduler. Toute connexion de preview H3 doit également republier la progression dans l'ordonnanceur global, afin que plusieurs onglets ne laissent plus le serveur figé à 8 %.

- **File FIFO des rendus directs H3/REF2V corrigée le 18 septembre** : permettre de lancer un second rendu depuis un autre onglet pendant que le premier tourne. Chaque clic réserve immédiatement sa place dans la voie GPU distante PanelForge ; le worker ne soumet à ComfyUI qu'à son tour. Conserver la détection prudente des anciens jobs distants après redémarrage, rendre le démarrage idempotent et retirer proprement une réservation annulée.

- **Variante chinoise H3 et insertion déterministe des dialogues autorisées et implémentées le 18 septembre** : conserver le prompt anglais comme canon, proposer à la demande dans H3 Base et REF2V Direct une transcompilation chinoise issue du Plan accepté et du prompt final anglais, puis ouvrir un atelier de rendu distinct pour l’A/B. Pendant Plan, Writer, révision et arbitrage, remplacer les paroles imposées par des jetons opaques et réinsérer localement les textes originaux avant compilation/validation afin qu’aucun LLM ne puisse les traduire ou les paraphraser.

- **Snapshot GitHub pré-variante chinoise demandé le 18 septembre** : publier l’état courant après les correctifs de reprise Histoires, de refroidissement distant, de suivi global et de navigation. La future transcompilation chinoise reste hors de ce snapshot et sera d’abord limitée à H3 Base et REF2V Direct ; Histoires ne l’adoptera qu’après qualification A/B.

- **Suites d’histoires cumulatives autorisées et implémentées le 18 septembre** : ajouter un mode « Continuer une histoire » valable pour toutes les familles. Conserver les épisodes anciens sous forme de mémoire cumulative et le dernier épisode sous forme détaillée, sans appel LLM supplémentaire. Chaque piste doit expliciter `reprise du canon → nouvel obstacle → conséquence préparée`, puis le Rédacteur met la mémoire à jour après le nouvel épisode. Permettre de préparer directement l’épisode suivant depuis un scénario terminé.

- **Défauts H3/REF2V et navigation allégée autorisés le 18 septembre** : pour tout nouveau run H3 Base ou REF2V, sélectionner Qwen3.8-27B-GGUF local pour le plan, Gemma-4-31B-it-qat-GGUF local pour le prompt final et activer le mode rapide. Retirer des menus les anciens Générer avec KREA2, Batch de recettes et Générer une vidéo, en conservant les données historiques. Auditer séparément la cohérence du dernier épisode Fruits sans modifier encore les recettes Histoires.

- **Ordonnanceur global PanelForge autorisé et implémenté le 18 septembre** : remplacer les files implicites des moteurs par deux voies FIFO contrôlées avant appel, locale pour LLM/DLSS et distante pour KREA2/vidéo. DLSS ne peut plus concurrencer un LLM local. Le suivi global remplace l'indicateur DLSS, affiche tâche active, progression, attente et prochaines tâches, et centralise les seuils thermiques ainsi que le repos vidéo distant de 30 s.

- **Bypass upscale H3/REF2V, repos vidéo Histoires et monitoring stable implémentés le 18 septembre** : les recettes courantes H3 Base `0.1.7` et REF2V `0.2.5` décodent directement la première passe lorsque la cible effective est égale ou inférieure aux MP initiaux ; une cible inférieure sort à la résolution initiale. Le test A/B peut forcer l’ancienne branche uniquement à dimensions égales. La chaîne Histoires réserve le GPU distant pendant un repos configurable de 30 s entre vidéos, puis applique le garde thermique. Le suivi sépare LLM/GPU, nomme les scènes et ne recrée plus les lecteurs vidéo pendant le polling. BUNNY et recettes historiques restent inchangés.

- **Langue parlée Histoires autorisée et implémentée le 18 septembre** : proposer Français, English, Coréen, Japonais ou Russe au niveau du projet, conserver Français par défaut, ne jamais traduire automatiquement un Script fidèle et transmettre le nom canonique de la langue à la préparation vidéo Histoires sans appel LLM supplémentaire ni modification des ateliers H3/REF2V directs.

- **Diagnostic REF2V classique / Spectrum du 18 septembre — sans correctif PanelForge** : REF2V `minimax-h3-ref2v@0.2.4` fonctionne avec Spectrum désactivé. Les essais avec Spectrum actif échouent dans l’ancien wrapper `ComfyUI-Spectrum-MiniMax-H3` après le changement de signature `FinalLayer.forward` de ComfyUI 0.36.0. Mettre à jour Spectrum vers `v0.2.21` ou plus récent et redémarrer ComfyUI ; en attendant, laisser Spectrum désactivé.

- **Transitions visuelles Histoires autorisées et implémentées le 18 septembre** : marquer uniquement les transformations d’état importantes avec un contrat `before → trigger → visible_change → after`, puis le compiler dans Fabrication. Renforcer la lisibilité sans paroles pour les chats muets, conserver les autres scènes inchangées, protéger Script fidèle contre l’invention et ne modifier ni H3 Direct ni REF2V Direct.

- **Recherche du 17 septembre — lisibilité narrative et contrôle spatial Ref2V, sans implémentation** : auditer la scène 2 du run chats puis confronter les pistes first frame, référence de pose, multi-références et image de composition aux guides MiniMax H3 et retours communautaires. Rester sur le contrôle général de continuité, d'anatomie et de proximité ; ne pas concevoir de prompting pornographique explicite.

- **Correctifs du premier run vidéo Histoires autorisés et implémentés le 17 septembre** : ne plus confondre une pose de sujet telle que `tilted head` avec un mouvement caméra, sans relâcher le rejet des véritables commandes concurrentes. Rendre l'état global de la chaîne lisible en séparant prompts et vidéos, sans doublons de statut, et signaler visuellement les tâches actives.

- **Grand patch Fabrication images + vidéos autorisé et implémenté le 17 septembre** : rationaliser le style et les réglages KREA2 autour d’un bloc commun, avec héritage par défaut et personnalisations Personnages/Décors explicites qui ne sont jamais écrasées silencieusement. Ajouter dans Histoires une vue de toutes les scènes, des réglages vidéo communs ou propres à une scène, une chaîne prompts → vidéos sans validation intermédiaire, pause après les tâches en cours/reprise, puis DLSS manuel par scène uniquement lorsque tous les prompts sont terminés. Ne pas exposer de file technique à l’utilisateur.

- **Snapshot GitHub préalable publié le 17 septembre** : commit `44a9b7f`, branche `snapshots/stories-pre-video-2026-09-17` et tag `snapshot-stories-pre-video-2026-09-17` sur `EasyFrag/panelforge`, avant le grand patch vidéo.

- **Rafraîchissement unifié KREA2 Création assistée implémenté le 17 septembre** : remplacer les boutons séparés catalogue, LLM et projets par une seule petite commande animée dans l'en-tête. Elle recharge en parallèle modèles/LoRA KREA2, modèles LLM, presets de style et projets récents tout en conservant le projet, les sélections et les brouillons en cours.

- **Automatisation vidéo Histoires — implémentée le 17 septembre** : vue unique de toutes les scènes, réglages vidéo communs/personnalisables, génération ordonnée des prompts puis des vidéos, pause coopérative et reprise. Le DLSS reste manuel par scène et n’est déverrouillé qu’après préparation de tous les prompts et réussite de la vidéo concernée.

- **Sélecteurs LLM locaux de la fabrication en lot corrigés le 17 septembre** : les profils Personnages et Décors doivent reprendre le sélecteur classique avec case `Local · Unsloth`, locale cochée par défaut, et permettre la bascule explicite entre catalogues local et serveur sans déclarer à tort un modèle local indisponible.

- **Nombre exact de micro-scènes Histoires autorisé et implémenté le 17 septembre** : le choix 1–12 fait foi pour tout nouveau scénario ou toute révision structurée. En Script fidèle, les rubriques source sont des événements à regrouper dans ce nombre exact sans omettre les actes, la fin ni modifier les dialogues. Une sortie de taille différente est refusée sans second appel et conserve son brouillon ; les histoires existantes ne sont pas migrées automatiquement.

- **Réorganisation KREA2 Création assistée autorisée et implémentée le 17 septembre** : afficher Nouveau projet avant les projets récents tout en le gardant replié au chargement, présélectionner le modèle local `unsloth/gemma-4-31b-it-qat-GGUF` lorsqu'il est disponible et ajouter un rafraîchissement dédié du catalogue LLM sans recharger la page. Les projets existants conservent leur modèle historique.

- **Production en lot des références Histoires et ordonnancement physique autorisés le 17 septembre** : publier d’abord le point voix off/registre, puis ajouter dans Fabrication un lancement groupé configurable des personnages et décors. Deux profils indépendants Personnages/Décors doivent choisir LLM et réglages KREA2 complets, afficher notamment la famille de workflow, pipeliner les prompts séquentiels avec la file image distante et s’arrêter avant toute vidéo pour validation humaine. PanelForge doit garantir un seul appel LLM ou DLSS sur la machine locale et un seul KREA2 ou rendu vidéo sur le serveur distant, les deux machines restant parallèles. DLSS reste une finition vidéo déclenchée après les appels LLM ; seuils thermiques configurables avant lancement.

- **Normalisation prudente des voix off et registre de dialogues Histoires autorisés et implémentés le 17 septembre** : après le Writer Classique, normaliser localement les seules voix off explicitement demandées et reconnues sans ambiguïté pour H3 Base/REF2V, sans nouvel appel ni modification des prompts Plan/Writer. Ajouter aux trois familles Histoires un curseur de vocabulaire 0–3 ; niveau 0 strictement inchangé, script fidèle protégé. Ne pas ajouter de curseur de densité de dialogue dans ce patch.

- **Version GitHub complète demandée le 16 septembre** : figer le bon point courant, incluant KREA2 + Flux Klein, Histoires multi-familles et script fidèle, Fabrication et dialogues structurés, dans une branche snapshot et un tag dédiés. Inclure les sources, workflows, tests et documentation, mais exclure les données d'exécution du workspace et tout secret.

- **Audit comparatif REF2V/H3 demandé le 16 septembre — sans coder** : établir la parité réelle des préparations, recettes de rendu et modèles, clarifier le rôle du sélecteur de recette par rapport au checkpoint et confirmer l'usage du loader hybride/fusionné sur le dernier rendu REF2V.

- **Dialogues de script structurés autorisés et implémentés le 16 septembre** : remplacer la dépendance aux préfixes textuels de voix off par un contrat sémantique rétrocompatible. Conserver les paroles mot pour mot dans `text`, et porter séparément l'identifiant stable, le canal de restitution et l'indication originale jusqu'à l'affichage et aux prompts Fabrication/REF2V.

- **Reprise des réglages entre fiches Fabrication autorisée et implémentée le 16 septembre** : lorsqu’un personnage ou décor est suivi d’une fiche vierge du même type, reprendre le modèle LLM et les réglages image sélectionnés sans copier le prompt, la description ou l’image, et sans écraser une fiche déjà configurée.

- **Famille Histoires Cru ++ autorisée et implémentée le 16 septembre** : ajouter `story.explicit-hard@1.0.0` comme troisième famille indépendante à côté de Fruits et Sensuel, centrée sur des scènes sexuelles explicites décrites sans euphémisme. Conserver les parcours une/deux/trois propositions et script fidèle, ainsi que Fabrication, sans couplage automatique avec une famille vidéo.

- **Histoires 1/2/3 propositions et script fidèle autorisés et implémentés le 16 septembre** : permettre de choisir une, deux ou trois pistes ; sélectionner automatiquement la piste unique. Ajouter un parcours script en un seul appel Rédacteur, sans phase concepts, où le script prévaut sur le ton éditorial et où les dialogues détectables sont validés mot pour mot, dans leur ordre, avant application. Conserver familles, projets historiques et Fabrication.

- **Correctifs Windows/Fabrication autorisés et implémentés le 16 septembre** : absorber les verrous Windows transitoires lors du remplacement atomique d’une histoire, réduire la fréquence des sauvegardes de trace et réactiver « Utiliser cette image » après avoir quitté puis rouvert Fabrication.

- **Trace live Histoires et limite de réponse autorisées le 16 septembre** : afficher pendant l’écriture le raisonnement/plan fourni par le serveur et le JSON en construction, sans nouvel appel LLM, puis porter le champ `reply` de 12 000 à 144 000 caractères. Conserver la validation structurée, le brouillon en cas d’échec et la compatibilité des histoires existantes.

- **Grand patch Histoires multi-familles autorisé et implémenté le 16 septembre** : conserver la famille Fruits historique, ajouter une famille `story.sensual-light@1.0.0` entièrement indépendante, séparer les modèles Architecte/Rédacteur sans appel supplémentaire, réduire le contrat commun envoyé au LLM, permettre l’édition structurée d’une scène et afficher des diagnostics déterministes. Rendre les deux familles KREA2 Assisted interchangeables depuis Fabrication. Le rendu en lot et l’assemblage vidéo restent hors périmètre ; aucun LLM, rendu, service ou publication GitHub demandé.

- **KREA2 Assisted + Flux Klein autorisé et implémenté le 16 septembre** : ajouter une seconde famille complète et indépendante dérivée de `Catlover workflow(1).json`, sélectionnable en parallèle de `krea2-sampling@1.0.0`. Conserver deux passes KREA2 et deux banques LoRA, retirer purge et LoRA désactivées, dériver trois seeds d'une racine, faire du MP la taille finale, garder Flux fixe et récupérer la sortie KREA2 pré-Flux. Aucun rendu, service ou publication GitHub demandé dans ce tour.

- **Version GitHub demandée le 16 septembre** : sauvegarder l’état actuel Histoires et Fabrication 1.1 dans `snapshots/fabrication-1.1-2026-09-16`, avec le tag `snapshot-fabrication-1.1-2026-09-16`, puis vérifier les références distantes. Publication seule, sans nouveau patch ni lancement de tests/LLM/rendus.

- **Fabrication 1.1 autorisée et implémentée le 16 septembre** : presets de style KREA2 Assisted, référence visuelle facultative, picker checkpoint/favoris/fiches et LoRA communs, héritage et personnalisation par fiche, cinq sliders créatifs REF2V indépendants persistants. Préserver H3 et les deux appels vidéo ; pas de GitHub demandé dans cet échange.

- **Fabrication 1.1 — alignement du 15 septembre, pas de patch fonctionnel livré dans cet échange** : l'utilisateur demande checkpoint/favoris/fiches et LoRA comme KREA2 Assisted, style commun texte ou image, presets KREA2 et mêmes sliders créatifs H3/REF2V. Dernier message : « On s'aligne ». Examiner l'existant et cadrer la prochaine itération ; conserver H3 inchangé.

- **Fabrication d’épisode 1.0 autorisée et implémentée le 15 septembre** : première version Histoires → validation/snapshot → fiches KREA2 compactes → scènes REF2V, neuf images, deux appels Qwen/Gemma locaux, BUNNY 0.1.3 et Motion Repair seuls par défaut dans cet atelier. Import Video Lab différé, H3 et les défauts des ateliers existants conservés.

- **Limite REF2V, vérification du 15 septembre** : l'utilisateur conteste le maximum trois annoncé. Aligner uniquement sur la capacité actuelle ; import depuis Video Lab explicitement différé, aucun patch fonctionnel demandé. Correction : neuf images dans le parcours REF2V intégré et BUNNY, trois seulement dans l'ancien rendu Video Lab.

- **Atelier de fabrication d'épisode : alignement du 15 septembre** : scénario validé ou importé ultérieurement → références personnages/décors via KREA2 Assisted compact → micro-scènes par menu déroulant avec assets/rôles modifiables, intention et dialogues → Plan Qwen local + prompt Gemma local en REF2V Classique deux appels expérimental → BUNNY actuel + Motion Repair. Discussion uniquement, pas de nouvelle implémentation autorisée.

- **Histoires : sélecteur Local/Gemma et erreurs JSON, autorisés le 15 septembre** : reprendre le sélecteur commun avec Local coché et Gemma 4 Hauhau par défaut, puis examiner les erreurs signalées pendant ce travail et corriger leur cause ciblée. Conserver les deux appels, les choix persistants et les familles vidéo.

- **Histoires r3 autorisée, implémentée et activée le 15 septembre** : rapprocher les propositions/scénarios des références par des actes concrets et un exemple de micro-scènes JSON. Deux appels et interface conservés ; historique r1/r2 et personnalisations protégés. Aucun autre chantier engagé.

- **Proposition de reformulation Histoires r3, 15 septembre** : l'utilisateur demande comment rapprocher automatiquement les scénarios des références et s'il faut reformuler les prompts. Examiner les consignes actuelles puis proposer une révision ciblée ; discussion, sans activation de recette ni génération.

- **Avis sur le scénario exporté Le Prix du Luxe, 15 septembre** : lire le fichier fourni et évaluer cohérence, intensité narrative et rythme des six clips de 10 s. Discussion uniquement, aucun nouveau patch fonctionnel ni génération.

- **Avis après relance Histoires r2, 15 septembre** : évaluer « Le Prix du Luxe » et les trois concepts réellement produits avec r2, sans nouveau patch fonctionnel. Conseiller le développement de la piste choisie et les points narratifs à vérifier.

- **Avis sur les nouvelles propositions Histoires, 15 septembre** : évaluer « Tromperie » et la capture, sans nouvelle modification fonctionnelle. Vérifier le brief et la révision réellement envoyée avant de juger le recadrage r2.

- **Retour Histoires du 15 septembre, recadrage livré** : les propositions ne ressemblent pas assez aux vidéos exemples. Examiner le run Gemma, corriger les consignes vers mélo/antagonistes excessifs/fruits et le rejet de la demande de transformation en fruits. Préserver les anciens textes et choix utilisateur ; aucun changement H3/REF2V ni appel LLM supplémentaire.

- **Histoires 1.0 autorisé et implémenté le 15 septembre** : nouvel espace du bandeau, trois propositions, choix/conversation, scénario en micro-scènes, persistance/versions, recette éditable et intentions copiables. Périmètre d'écriture retenu ; ne pas lancer implicitement les fiches KREA2, les clips ou le montage. H3/REF2V restent les moteurs existants.

- **Générateur d'histoires « skibidi / brainrot », discussion du 15 septembre** : concepts simples, antagonistes excessifs, création automatique ou en quelques échanges LLM à partir des quatre exemples vidéo. Les intentions REF2V laissant le LLM inventer la mise en scène conviennent ; ne pas imposer de plans caméra. Aucun développement demandé dans cet échange, H3 inchangé.

- **Atelier narratif précisé le 15 septembre** : l'utilisateur veut dialoguer avec le LLM pour choisir une histoire, obtenir des micro-scènes de 10 s avec personnages/décors/dialogues, créer les fiches personnages via KREA2, puis un storyboard textuel des intentions avec répliques injectées, générer les clips automatiquement et appliquer DLSS. Discussion uniquement pour ce nouvel atelier. Retrait de Production V1/V2 demandé explicitement, effectué au niveau navigation/chargement frontend ; conserver H3 inchangé.

- **Vidéos narratives automatisées, discussion du 15 septembre** : examiner `C:\Users\samue\Downloads\Download.mp4` et `Download(1).mp4`, puis préciser les manques de PanelForge pour produire ce format. Aucun patch demandé. Préserver H3 comme moteur inchangé ; ne pas réordonner P1/P2 sur cette seule discussion.

- **Version GitHub après correctif REF2V demandée le 15 septembre** : sauvegarder l'état courant dans la branche `snapshots/ref2v-2026-09-15` et le tag `snapshot-ref2v-2026-09-15`, puis vérifier les références distantes. Publication uniquement ; aucune nouvelle modification fonctionnelle, aucun test ou redémarrage.

- **Snapshot puis correctif REF2V autorisés le 15 septembre** : publier d'abord la version actuelle sur GitHub, puis réparer l'alignement REF2V en gardant H3 strictement inchangé. Le prompting REF2V étant déjà distinct au mapping et à la compilation, intervenir sur son raccordement au rendu et la reprise du projet mal classé, sans réécrire ses consignes ni son Plan.

- **Alignement REF2V confirmé le 15 septembre : H3 strictement inchangé**. L'utilisateur impose H3 comme référence fonctionnelle et interdit de le modifier pour cet alignement. Adapter uniquement REF2V à la même méthode en deux appels, avec ses entrées variées, rôles d'images et grammaire de sortie. Des différences ciblées de Plan JSON et de construction du prompt sont acceptables lorsqu'elles répondent à ces particularités ; ne pas changer le comportement H3 par une modification commune. Le patch a ensuite été autorisé, après snapshot GitHub.

- **Audit H3 I2V / REF2V demandé le 15 septembre — sans coder** : prendre H3 comme référence des prochaines évolutions et établir les écarts réels de recettes, consignes actives, UI et raccordement au rendu. Ne pas lancer de correctif, de test, de génération ou de redémarrage pendant cet état des lieux.

- **KREA2 Modif, référence visuelle pour la rédaction de consigne — discussion le 15 septembre** : l'utilisateur propose de joindre une image au prompt de modification pour guider les changements. Examiner l'existant et proposer un ajout léger, sans modifier le patch sampling Assisted déjà livré ni élargir implicitement le workflow de rendu.

- **KREA2 Assisted sampling autorisé et implémenté le 15 septembre 2026** : patch strictement limité aux trois presets convenus, réglages des deux passes et persistance/reprise par essai. Actuel par défaut ; aucune évolution des autres ateliers ni du prompting, P1/P2/EROS-BUNNY différés.

- **Choix KREA2 confirmé le 14 septembre 2026** : l'utilisateur retire son tableau alternatif res_multistep/er_sde/euler et valide explicitement notre proposition Actuel, Finition 4 steps, Moody · Beta. Conserver les trois presets exacts, les réglages par passe et leur persistance ; périmètre validé mais pas encore de demande de lancer le patch.

- **KREA2 Assisted : proposition de presets sur les deux passes, 14 septembre 2026.** L'utilisateur veut discuter des steps, sampler et scheduler, puis demande des idées pour les deux passes. Vérifier l'actuel et proposer un sélecteur léger, avec réglages avancés indépendants ; conserver P1 I2V et P2 analyse adaptative. Discussion uniquement, aucune implémentation du sampling engagée.

- **Durée H3 vers réglages de rendu corrigée le 14 septembre 2026** : les prompts des recettes cinématiques récentes portent `The target video lasts N seconds.`, formulation absente du lecteur de durée de l’interface. La reconnaître pour initialiser le rendu avec la durée du prompt au lieu du défaut 6 s. Conserver les durées reprises d’un essai et les changements manuels.

- **Profil DLSS vidéo léger demandé et implémenté le 14 septembre 2026** : réduire fortement les effets pour les prochains upscales H3/REF2V. Style Natural, intensité NR 0,20, tonalité 0, structure 0,20, peau 0, détails 1 ; NR Preset Default et masque automatique désactivé. Changement limité aux défauts d’effets vidéo ; ×1,724/60 FPS du bouton rapide conservés.

- **Nouvelle version GitHub demandée le 14 septembre 2026** : publier l’état courant après l’optimisation Sensuel sans alignement, les correctifs de validation Plan et le déverrouillage LoRA KREA2, dans une branche snapshot et un tag dédiés, sans modifier le remote local ni la branche principale.

- **Correctif du validateur Plan Sensuel autorisé et implémenté le 14 septembre 2026** : absorber sans nouvel appel LLM les deux écarts bénins observés dans les traces, tout en conservant le registre vocal exact et le rejet des vraies instructions caméra libres. Ne pas ajouter de tokens aux prompts ni modifier les recettes Classique/Combat.

- **Correctif rapide KREA2 Modif autorisé le 14 septembre 2026** : empêcher les contrôles LoRA de rester désactivés après l’import d’une image. Corriger uniquement le cycle d’état de l’interface, sans modifier le catalogue, les compatibilités de modèles, les forces ni les réglages enregistrés.

- **Test Sensuel sans alignement autorisé et implémenté le 14 septembre 2026** : retirer uniquement des entrées LLM Sensuel H3 Base/Ref2V les notions d’âge, consentement, interaction volontaire, jeunesse et coercition, y compris les champs du schéma Plan. Conserver la précision explicite, la fidélité à la demande et tous les contrats techniques. Classique, Combat et KREA2 restent inchangés ; aucune autre optimisation de tokens n’entre dans ce test.

- **Version actuelle sauvegardée sur GitHub le 14 septembre 2026, sur demande explicite** : snapshot du Lab incluant UX vidéo, édition/versionnement des consignes et traces LLM, correctifs KREA2, recadrage et réglages Qwen. Branche de sauvegarde `snapshots/lab-2026-09-14`, tag de livraison `snapshot-lab-2026-09-14`. Aucun nouveau patch fonctionnel dans cette publication.

- **Rappel du backlog après les correctifs DLSS vidéo et durée H3** : prochaine évolution P1 prompting I2V / Mise en scène 1.1, puis P2 analyse vidéo adaptative ; presets sampling EROS/BUNNY encore à raccorder, priorité non numérotée. UX vidéo/éditeur de consignes, recadrage KREA2, réglages Qwen et derniers correctifs déjà implémentés, à valider à l’usage ; ne pas les présenter comme de nouveaux chantiers. Recherche de seeds mise de côté, comparaison dédiée de presets BUNNY abandonnée. Rappel documentaire uniquement, aucune nouvelle implémentation autorisée, aucun code ni service modifié.

- **Qwen Changer la vue : réglages de rendu implémentés le 14 septembre 2026**. Steps, résolution MP et format accessibles en avancé ; defaults actuels préservés (8 steps, dimensionnement automatique, PNG). Demande parallèle : diagnostic des doubles rejets H3 et rappel des quatre consignes de l’éditeur. Diagnostic terminé, aucune recette H3 modifiée. Contrôles statiques terminés, tests laissés à l’utilisateur.

- **Recadrage KREA2 Modif autorisé et implémenté le 14 septembre 2026** : rectangle libre sur la source de l’étape, déplacement et poignées, puis Valider et continuer. Le résultat local devient une étape conservée dans l’historique et la source du prochain échange. Prompt et conversation de l’étape suivante remis à zéro pour éviter les descriptions hors cadre. Vérifications statiques terminées ; tests préparés pour l’utilisateur, aucun service ni génération relancé.

- **Correctif KREA2 Modif du 14 septembre 2026 implémenté après diagnostic** : accepter les réponses JSON dans un bloc Markdown complet et ajouter Télécharger le PNG aux résultats Qwen Changer la vue. L'utilisateur exclut explicitement le bouton de transfert vers Modifier avec KREA2. Vérifications statiques terminées ; tests préparés, laissés à l'utilisateur ; aucun service ni modèle relancé.

- **Patch UX vidéo + recettes LLM autorisé puis implémenté le 14 septembre 2026** : sélecteur de presets existants, réglages lisibles, éditeur versionné des six recettes H3/REF2V actuelles à deux appels, traces durables après rendu. Durée cible et contrat caméra Classique corrigés. Vérifications statiques terminées, tests fonctionnels préparés pour l'utilisateur conformément à AGENTS.md ; aucun service ni modèle relancé. P1 I2V, P2 analyse adaptative et adaptation sampling EROS/BUNNY hors de ce patch.

- **Précision suivante sur les recettes LLM** : proposer une interface spécialisée simple sur les recettes actuelles, édition/enregistrement persistants, révision active appliquée par défaut aux nouveaux cycles, retour à une ancienne révision par sélection/application. Consultation durable des prompts réellement envoyés et échanges LLM depuis une vidéo terminée. Rangement lisible des fichiers accepté comme alternative ; privilégier un petit éditeur sans nouveau service. Demande parallèle d'examiner les échecs durée/Plan : diagnostic dans ce tour, pas de correctif ou refonte pendant cet alignement.

- **Suite confirmée le 14 septembre : maquette vidéo validée.** Prochaine itération à aligner : UX du rendu + accès simple aux consignes LLM, fichiers actifs éditables et rangement séparé des anciennes recettes. La demande actuelle autorise un snapshot GitHub et un audit/proposition, pas encore le patch UX ni la migration des prompts. P1 I2V et P2 analyse média restent différées dans cet ordre.

- **Ordre de travail confirmé le 14 septembre 2026** : maquetter d'abord la simplification du rendu H3/REF2V (sélecteur unique de presets, sans comparaison BUNNY). Évolution I2V / Mise en scène 1.1 conservée en **P1**, différée ; enrichissement de l'analyse vidéo → intention française, inspiré de `LoveRain1997/video-to-h3-prompt`, en **P2**. Garder le pipeline existant et limiter la complexité ajoutée. La demande actuelle autorise une maquette et une analyse, pas l'implémentation des deux moteurs.

- Construire un atelier local confortable pour préparer des clips courts : exploration conversationnelle KREA2 Assisted, cohérence visuelle et affectation libre des First/Last Frames, puis préparation H3 Base/Ref2V. L'automatisation thématique via une référence Ref2V est une cible secondaire ; le parcours imposé Production V1/V2 n'est plus la référence UX.

- **Contrainte confirmée par l’utilisateur les 2026-09-10/11, à préserver** : Combat, Classique et Sensuel sont trois familles de préparation indépendantes. Une modification spécifique ne change pas les deux autres. Partager uniquement les améliorations générales via un socle à versions exactes et une adoption explicite examinée ; aucun héritage de « latest » entre familles. Conserver familles, versions et réglages jusque dans les révisions conversationnelles, conversions et continuations. Application/file/rendu restent communs.

## Current state

- **Mode Suite disponible localement dans Histoires** : le formulaire accepte jusqu’à 60 000 caractères d’historique, l’Architecte produit dans son appel normal une mémoire structurée (`series_summary`, fin récente, faits acquis, états des personnages, fils ouverts, éléments disponibles) et des plans causaux par proposition. Le Rédacteur met cette même mémoire à jour après développement/révision. La mémoire source reste séparée de l’état après épisode afin que de nouvelles propositions repartent du bon point. L’interface l’affiche et « Créer l’épisode suivant » prépare un nouveau projet avec la mémoire cumulative et le dernier scénario détaillé ; un ancien projet sans mémoire transporte une fois son brief antérieur pour amorcer la chaîne. Validation : 35 tests Histoires et 31 tests Episodes passent.

- **Défauts directs et menus nettoyés localement** : H3 Base et REF2V utilisent les deux modèles Unsloth demandés et l'orchestration rapide pour les nouveaux runs ; l'ouverture d'un run historique restaure toujours son choix enregistré. Image Lab n'expose plus que Création assistée, Changer la vue et Modifier avec KREA2. Video Lab n'expose plus que Texte Instagram et Analyser les médias ; l'ancien pont REF2V vers Video Lab est retiré et les anciennes vues mémorisées sont redirigées. Les scripts retirés des menus ne sont plus chargés par la page, mais leurs sources restent dans le dépôt pour une suppression physique ultérieure éventuelle.
- **Audit de `story-061512992bf4482eb85a7a1d2b943105`** : la suite « L'Addition » conserve bien le conflit et fait évoluer Citron vers l'action, mais elle redécouvre une preuve déjà acquise à la fin de l'épisode 1 et invente successivement un enregistrement audio, une décharge, Kiwi et un remboursement sans préparation causale. Banane filme sans payoff, le sas est déclaré puis inutilisé, et les deux premières scènes dépassent le budget de dialogue. Aucun prompt Histoires n'a été modifié dans ce patch.

- **File globale locale/distante prête sur `feature/vocal-normalizer-dialogue-register`** : `MachineWorkCoordinator` est l'autorité FIFO partagée par LLM, DLSS, KREA2 et vidéo. Les deux machines restent parallèles mais chaque voie est exclusive. Le repos de 30 s entre vidéos est global et s'applique avant la vidéo suivante ; Histoires ne détient plus sa propre pause. L'état public expose tâche active, phase, progression, file, pause, refroidissement et historique. Les paramètres sont persistés dans `workspace/system/work-scheduler.json`. Le moniteur du bandeau et le nouveau panneau **Traitements** pilotent pause/reprise et réglages globaux ; l'ancien panneau flottant DLSS est retiré. Snapshot préalable publié au commit `0ec14f7`, branche/tag `snapshots/pre-global-queue-2026-09-18`. Documentation : `docs/global-work-scheduler.md`. Validation : compilation Python et `git diff --check` verts, 125 tests ciblés verts dont trois fixtures Chromium. La suite complète exécute 1 373 tests et conserve 48 échecs/33 erreurs historiques ou hors surface, sans échec du nouvel ordonnanceur, de DLSS, d'Episodes, H3/REF2V ou KREA2 Assisted ciblés.

- **Langue parlée Histoires raccordée localement** : le nouveau projet choisit Français, English, 한국어, 日本語 ou Русский à côté du registre. Le choix est persisté avec l’histoire ; les anciennes histoires et fabrications utilisent Français. Les descriptions et `reply` restent en français, tandis que `dialogue.text` suit la langue choisie. Script fidèle conserve chaque mot et affiche qu’aucune traduction n’est faite. Chats muets désactive le sélecteur et normalise la valeur technique sur Français. Fabrication recopie la langue dans son snapshot et demande au Plan REF2V la valeur canonique correspondante dans `spoken_languages`, sans modifier H3 Direct/REF2V Direct et sans appel supplémentaire. Cache Stories `20260918.1`. Régressions Python/API/navigateur préparées ; AST Python et `git diff --check` réussis, tests non lancés conformément aux instructions du dépôt.

- **Diagnostic du run `Le Remède Miracle` et recherche Ref2V terminés** : les quatre keyframes de la scène 2 confirment que Blanc paraît déjà alerte dès l'ouverture. Le prompt déplace la compresse du front vers l'avant-bras, omet la couverture verte et conserve la compresse dans l'état final ; il anime donc argent → excitation → câlin, pas une guérison visible. La scène 3 est jugée réussie par l'utilisateur. Le guide officiel H3 distingue identité de sujet, image-ancre et storyboard de composition, et permet plusieurs assets pour un même sujet. Les retours communautaires signalent ordre/rôles explicites, positions gauche/droite et `ref_image_size=max` pour limiter le mélange ; l'instance Comfy expose bien `match|max`. Pour deux personnages proches, les retours Flux privilégient une composition commune puis inpainting/passes séparées. Le mélange I2V + références existe via conditionnements expérimentaux ; le support H3 Fun ControlNet proposé dans ComfyUI PR 15860 a été fermé, donc ne constitue pas une base stable. Aucun code ni donnée d'exécution modifié.

- **Faux positif `tilted head` et suivi vidéo corrigés localement** : le contrat caméra accepte désormais le participe `tilted` comme adjectif de pose, mais rejette toujours `tilting down`, `tilted down`, les mentions de caméra et les autres mouvements cachés. L'écran Histoires calcule séparément les prompts prêts/en cours/en erreur et les vidéos terminées/en cours/en erreur/bloquées ; les cartes n'affichent plus `Échec du prompt · Échec du prompt` ni `Prompt prêt · Prompt prêt`, et une tâche active porte `aria-busy` avec une pulsation respectant `prefers-reduced-motion`. Cache Episodes `20260917.4`. Vérification : 45 tests ciblés MiniMax H3/Episodes/API/navigateur passent et `git diff --check` est propre. Le run observé n'avait pas planté : scène 2 terminée, scène 3 réellement active dans ComfyUI, une tâche distante en cours et aucune en attente au moment du diagnostic.

- **Fabrication rationalisée et chaîne vidéo Histoires implémentées localement sur `feature/vocal-normalizer-dialogue-register`** : la direction artistique, l’image d’inspiration, le workflow, checkpoint, LoRA et sampling KREA2 vivent dans un seul bloc commun au lot. Personnages et Décors héritent par défaut, gardent format/MP/seed et LLM propres, et n’exposent leurs réglages techniques qu’après `Personnaliser`; les profils historiques restent personnalisés afin qu’un preset ne les écrase pas. Côté vidéo, chaque scène hérite d’un profil commun en conservant durée/seed, peut figer sa propre copie, et apparaît dans une carte avec prompt, rendu et résultat. La chaîne persiste son snapshot, prépare un prompt à la fois, chevauche la rédaction suivante avec la vidéo distante en cours, ordonne les départs H3/REF2V, s’arrête après les tâches actives à la demande et reprend sans refaire les réussites. Le DLSS reste manuel et n’est exposé qu’après tous les prompts et la réussite de la scène. Le renderer partagé a uniquement reçu un mode optionnel `openSetup` sans projet, utilisé par Histoires ; les parcours H3/REF2V directs gardent leur ouverture normale. Validation ciblée : 27 tests Episodes/API/navigateur passent et `git diff --check` est propre. Suite globale : 1 229 tests, 35 échecs et 44 erreurs sur les contrats H3/Combat/fixtures déjà désynchronisés hors de ce patch. Aucun LLM, rendu, DLSS ou service réel n’a été lancé.

- **Le nombre de micro-scènes est maintenant contractuel** : l'appel Writer reçoit deux consignes cohérentes avec `target_scene_count`, les sections d'un script doivent être regroupées, et `parse_response` rejette transactionnellement tout `scenario.scenes` d'une autre taille. L'interface parle de `Nombre exact`, le cache passe à `stories.js?v=20260917.3`, et les anciens documents restent lisibles/éditables sans normalisation destructive. 56 tests Histoires/Fabrication/API/navigateur passent ; aucun LLM ou rendu réel n'a été lancé.

- **Références en lot Fabrication 1.2 et coordinateur global implémentés sur `feature/vocal-normalizer-dialogue-register`** : le panneau Histoires configure séparément Personnages et Décors (LLM, `KREA2 · deux passes` ou `KREA2 + Flux Klein`, checkpoint, LoRA, sampling, ratio, MP, seed), sélectionne les fiches, affiche le profil effectif sur chaque ligne, trois progressions et les images intermédiaires. Le worker prépare un seul prompt à la fois, met immédiatement son image dans la file Assisted puis poursuit le prompt suivant ; il termine sur une validation humaine et ne lance aucune vidéo ni DLSS. Les profils, le lot et ses seuils thermiques sont persistés dans l’épisode, les lots interrompus sont signalés et une ancienne image retenue ne valide pas une nouvelle sortie. Un `MachineWorkCoordinator` FIFO commun réserve jusqu’au terminal la machine locale pour tous les LLM/DLSS et le serveur distant pour KREA2 simple/batch/Assisted/Edit/changement de vue, Video Lab et H3/REF2V ; les deux ressources restent indépendantes. Le snapshot pré-patch est publié au commit `ada89e6`, branche/tag `snapshots/stories-vocal-2026-09-17`. Compilation et `git diff --check` réussis ; 178 tests ciblés passent. La suite globale expérimentale exécute 1346 tests mais conserve 39 échecs et 33 erreurs hors de ce patch (principalement anciens contrats H3/Combat et assertions de fixtures) ; aucun appel LLM, rendu, DLSS ou service réel n’a été lancé.

- **Voix off locale + registre Histoires livrés sur `feature/vocal-normalizer-dialogue-register`** : le compilateur partagé Classique 1.0 de H3 Base et REF2V accepte désormais un post-traitement optionnel, adopté uniquement par la famille Classique. Il lit les répliques citées explicitement marquées voix off/pensée, conserve les `<Picture N>`, attribue des `(Sx)` stables et remplace seulement les enveloppes Writer connues par `says in an off-screen voiceover`, puis impose immédiatement les lèvres fermées aux personnages visibles. Une voix diégétique hors cadre (`O.S.`, derrière la porte) n’est pas convertie. Une forme ambiguë reste octet pour octet intacte et ajoute seulement `vocal_normalization.warnings` au contexte ; aucun rejet, appel LLM, changement de Plan/schema/prompt ou effet Combat/Sensuel. Histoires persiste `dialogue_register` 0–3 pour Fruits/Sensuel/Cru ++ ; 0 n’ajoute aucune clé ni consigne aux requêtes, 1 oral direct, 2 cru, 3 très cru/argot. La consigne n’est envoyée qu’au développement/révision, épargne narration/actions et ne fixe aucun quota. Script fidèle force 0 et désactive le curseur. Densité inchangée. Caches stories CSS/JS `20260917.1`, guides `docs/stories-1.0.md` et `docs/voiceover-normalizer-1.0.md`. Vérifications : 29 tests ciblés service/compilateur et 5 tests navigateur verts ; `py_compile` et `git diff --check` verts. Node.js absent. Suite complète demandée par le dépôt : 1343 tests, 39 échecs et 49 erreurs déjà présents dans ce snapshot expérimental (H3/rendu/fixtures/empreintes), aucun dans les nouvelles suites ciblées. Aucun LLM, rendu, service ou donnée du workspace lancé/modifié.

- **Snapshot GitHub complet publié le 16 septembre** : le commit fonctionnel `0c230c5cc303a58a387638009cb82577f310543d` est publié sur `snapshots/complete-2026-09-16` et marqué par le tag `snapshot-complete-2026-09-16`. Il contient 53 fichiers modifiés ou ajoutés : sources, prompts, workflow KREA2 + Flux Klein, tests et documentation ; le workspace externe est exclu et aucun secret littéral `sk-unsloth-*` n'a été détecté. La suite ciblée KREA2 Assisted/Histoires/stockage/Fabrication exécute 96 tests avec succès. La suite globale expérimentale reste connue comme non verte pour des échecs préexistants documentés ; aucun LLM, rendu ou service n'a été lancé pour cette publication.

- **Audit REF2V/H3 du 16 septembre** : les préparations Classique H3 et REF2V sont deux cookbooks 1.0.0 à deux étapes partageant le même contrat de mise en scène, mais H3 reçoit First/Last Frame tandis que REF2V reçoit 1–9 références ordonnées. La couche de révision est commune et vaut 0.3.0 par défaut. Les rendus « actuels » sont des graphes cousins mais distincts (`H3 0.1.6`, `REF2V 0.2.4`) ; BUNNY 0.1.3 est au contraire un même graphe commun qui choisit la branche UNET directe en H3 ou le `MiniMaxH3HybridLoader` en REF2V. Par défaut REF2V fusionne à l'exécution `minimax_h3_fl2va_bf16` + `minimax_h3_ref2va_bf16`, preset `block_range_adaln`, blocs 25–49. Choisir explicitement un checkpoint remplace ce loader par un chargement UNET direct ; les checkpoints nommés hybrides sont alors des fichiers déjà fusionnés. Le dernier rendu `h3-render-76d43d315d084bcb8bbedab83f09308f` a bien utilisé la fusion dynamique par défaut et a réussi. BUNNY 0.1.2 et 0.1.3 ont un workflow JSON identique ; 0.1.3 étend seulement le contrat LoRA par passe jusqu'à quatre entrées. Aucun code, rendu ou donnée utilisateur modifié pendant l'audit.

- **Diagnostic Préparer le prompt du 16 septembre à 21:31** : la première préparation de la scène 1 de `episode-7e75873f96f44edd8ac3cb3461b697f6` a été rejetée après un appel LLM réussi parce que `target_clause: "toward Tom's tilted pear head"` a fait reconnaître `tilted` comme le terme caméra interdit `tilt`. C'est un faux positif lexical sur la posture du personnage, sans rapport avec les champs de voix off. La seconde préparation `prompt-e660fb772b624efa94fd15708c0f8200` a ensuite réussi : Plan et prompt final approuvés, état `ready`, projet `h3-render-76d43d315d084bcb8bbedab83f09308f`. Aucun correctif ni donnée d'exécution modifiée pendant ce diagnostic.

- **Les indications vocales ne polluent plus les paroles du script** : l'extracteur reconnaît notamment `VOIX OFF DE LÉA`, `LÉA (V.O.)`, `TOM [O.S.]`, les séparateurs tiret/deux-points et les indications derrière une porte/téléphone/pensée. Chaque réplique source reçoit un `dialogue_id` et des champs `delivery`/`delivery_note`; le validateur canonise un ancien préfixe connu mais refuse toujours toute modification réelle des mots, du locuteur, de l'ordre ou du canal. Les anciens objets `{speaker_id, text}` restent valides. Histoires, l'éditeur, l'export d'intention et Fabrication/REF2V affichent et transmettent le canal séparément. Le brouillon réel de `story-b309aa69d5934b9cb52666b7f480dae2` est désormais validé localement avec ses 21 répliques, cinq voix off et une voix hors champ. Compilation, `git diff --check` et 33 tests ciblés passent ; aucun LLM, rendu, service ou fichier de projet utilisateur n'a été relancé/modifié.

- **La fiche suivante reprend les réglages de la précédente** : au changement de référence, Fabrication mémorise modèle LLM, héritage/personnalisation, workflow, checkpoint, LoRA, sampling, format, mégapixels et seed. Ces valeurs sont appliquées uniquement à une fiche de révision initiale, sans prompt, projet KREA2, image, essai ou tâche, et seulement entre références de même type. Elles deviennent persistantes lors de l’action ou navigation suivante. Le prompt et les contenus propres à la fiche restent distincts. L’interface documente le comportement et charge `episodes.js?v=20260916.6`. Les trois tests navigateur ciblés passent. Les tests applicatifs Episodes restent bloqués par leur fixture historique `StoryService(recipes=None)`, indépendante de ce correctif.

- **Cru ++ est câblé de bout en bout dans Histoires** : la recette et ses sources `concepts/scenario/revision` sont isolées de Fruits et Sensuel ; ses contrats ajoutent participants/dynamique, actes/progression, escalade physique et `sexual_state`. La validation exige des personnages adultes et la continuité physique par scène. `sexual_state` est éditable, visible dans le scénario et transmis aux intentions Fabrication/REF2V. L’interface expose la famille avec le cache `stories.js?v=20260916.4`. Les 28 tests ciblés Histoires/navigateur passent ; aucun appel LLM, rendu, redémarrage de service ou publication GitHub n’a été effectué.

- **Sélecteur et script fidèle Histoires livrés localement** : `creation_mode` et `proposal_count` sont persistés avec repli legacy `ideas/3`. Le contrat, le validateur, les IDs `concept-N`, les libellés et les consignes effectives suivent exactement 1, 2 ou 3 propositions ; une proposition est auto-sélectionnée. Le mode `script` saute l’Architecte, appelle directement le Rédacteur à température 0,35 et rend le script autoritaire sur le ton par défaut. Un extracteur local reconnaît les blocs usuels `LOCUTEUR` des scénarios ; la réponse n’est appliquée que si la concaténation des dialogues correspond exactement au source, sans omission, reformulation, réordonnancement ni ajout. Le brouillon reste disponible en cas d’écart. UI, API, traces, éditeur de recettes et documentation sont alignés ; caches `stories.js` `20260916.3` et `prompt-recipes.js` `20260916.1`. Les 27 tests Histoires/service/navigateur passent. Suite complète : 1208 tests exécutés, 36 échecs et 60 erreurs préexistants dans le worktree expérimental (H3/Combat/Fabrication et fixtures sans catalogue), sans échec ciblé Histoires. Aucun LLM, rendu ou service lancé.

- **Correctifs Windows/Fabrication livrés localement** : `_atomic_write` réessaie maintenant uniquement les `PermissionError` de `os.replace` selon sept délais bornés (10 à 640 ms, 1,27 s au total), en conservant le fichier temporaire déjà vidé et synchronisé ; les autres erreurs ne sont pas masquées et le temporaire est toujours nettoyé. La trace Histoires est persistée au plus toutes les 1,5 s, alignée sur le polling ~1,6 s au lieu de 0,75 s. Les boutons dynamiques d’essais portent `data-image-choice`/`data-selected` et `controls()` recalcule leur état après chaque action : une image terminée redevient sélectionnable après navigation, une image déjà retenue reste désactivée. Cache `episodes.js` `20260916.5`. Régressions stockage et navigateur préparées ; compilation Python, IDs HTML et `git diff --check` validés. Tests applicatifs non exécutés. Les images existantes et les données serveur n’ont pas été modifiées.

- **Trace live Histoires livrée localement** : les requêtes Histoires activent désormais le raisonnement exposé par le fournisseur. Le worker conserve séparément le plan/raisonnement et le brouillon JSON, les persiste au plus toutes les 0,75 s, et l’UI les affiche dans un panneau en direct rafraîchi par le polling existant (~1,6 s). Le raisonnement et le JSON du dernier échange restent consultables après succès ; le JSON brut reste aussi conservé après échec. Les anciens projets reçoivent les champs manquants à la lecture. Le validateur `reply` accepte exactement 144 000 caractères. Cache stories.js/css `20260916.2`; régressions service et navigateur préparées. Compilation Python et `git diff --check` réussis ; Node.js absent, tests applicatifs non exécutés, aucun LLM/rendu/service lancé.

- **Histoires multi-familles livré localement dans `D:\Code\panelforge-krea2-flux`** : `story.brainrot@1.0.0` reste l’identité et l’archive des projets Fruits existants ; `story.sensual-light@1.0.0` possède ses propres champs de concepts, prompts courts et révisions. Les scénarios Sensuel light exigent des personnages explicitement adultes et suivent aussi dynamique relationnelle/tenues par scène. Les projets enregistrent famille/version, modèle Architecte, modèle Rédacteur et provenance dans chaque révision/appel. L’UI choisit les deux modèles, affiche les champs propres à la famille, permet de modifier une scène sans LLM et montre les diagnostics de densité/dialogues/références. Fabrication expose désormais le choix `KREA2 · deux passes` ou `KREA2 + Flux Klein` au niveau commun et par fiche, avec héritage et persistance ; la sortie KREA2 pré-Flux est téléchargeable depuis l’essai. Compatibilité de lecture des histoires et fabrications existantes conservée. Prompts Fruits r3 inchangés ; seul le court contrat applicatif commun a été compacté. Compilation Python et `git diff --check` réussis ; tests préparés mais non exécutés, aucun LLM/rendu/service lancé.

- **Famille `krea2-flux-klein@1.0.0` livrée dans le worktree `D:\Code\panelforge-krea2-flux`, branche `feature/krea2-flux-klein`** : manifeste et graphe autonomes (37 nœuds), sans purge/cache-clear ni LoRA désactivée. Checkpoint et jusqu'à dix LoRA KREA2 configurables via deux loaders 5+5 ; Flux Klein, CLIP/VAE, LoRA technique et sampling Flux restent fixes. Le preset initial est Moody Beta 8+4, deuxième passe denoise 0,39. Un MP final pilote rétroactivement la base KREA2 avant upscale latent ×1,5. Trois seeds déterministes proviennent d'une seed racine. Sortie finale obligatoire et `pre_flux` facultative persistées, affichées et exportées. L'UI conserve un brouillon de sampling distinct par famille ; chaque essai mémorise recette/version/hash. Schéma Assisted 10, lecture 1–9 conservée. Le checkout principal sale a été laissé intact. Compilation Python, validation du hash/manifeste, inspection du graphe et `git diff --check` réussis ; tests préparés mais non exécutés selon les consignes. Node.js absent, donc pas de contrôle syntaxique JS par Node.

- **Snapshot GitHub du 16 septembre — Histoires et Fabrication 1.1** : commit fonctionnel `71efb1da5a0f47c7c00782c18d8c64211328ae85` publié et vérifié sur `https://github.com/EasyFrag/panelforge`, branche `snapshots/fabrication-1.1-2026-09-16`. 45 fichiers, sources éditoriales Histoires r1/r2/r3 et atelier Fabrication inclus. Le tag de version `snapshot-fabrication-1.1-2026-09-16` accompagne cette branche et le commit de consignation. Branche principale et origine locale conservées ; aucun test applicatif, LLM/rendu ou redémarrage lancé pendant la publication. La sauvegarde porte sur le code et les consignes sources, pas sur les données d’exécution ignorées du workspace.

- **Fabrication 1.1 (16 septembre)** : domaines/services/routes/JS/CSS Fabrication étendus sans modifier les moteurs H3/KREA2/REF2V. Le catalogue KREA2 existant fournit le picker checkpoint (favoris/informations) et la pile LoRA (dix, ordre/forces), avec presets de sampling inchangés. Style commun texte/image importée ou retenue, et presets Assisted existants : snapshot de nom/id/version/prompt/image, application explicite checkpoint/LoRA communs, version suivante uniquement sur demande. Image de guidage au même appel KREA2, extrait borné du prompt d'exemple, pas d'appel supplémentaire ni d'image ajoutée au renderer. Révision commune pour conflits d'édition ; réglages effectifs hérités ou personnels par fiche, anciens choix explicites conservés. Cinq sliders 0–3 affichés et transmis à PreparationIntent : audace 2, vie 1, caméra 2, mouvements 1, dialogue 0 par défaut ; empreintes v1 inchangées à entrées égales. Provenance style des prompts et des essais, mentions édition manuelle, style à vérifier et anciennes images conservées. Contrôles AST/JS/markup et tests simulés préparés ; aucun test applicatif exécuté, LLM/rendu de vérification, restart ou publication. Scripts épisodes chargés après le composant ressources partagé ; cache `20260916.1`. Guide `docs/episodes-1.0.md` actualisé en 1.1.

- **Audit Fabrication 1.1** : v1 utilise un select checkpoint simple ; les LoRA sont acceptées dans les réglages mais aucun picker ne permet de les choisir. Style commun texte seulement, sans image ni preset Assisted ; les trois presets de sampling sont déjà présents. Audace par select, axes cachés fixés à vie=1/caméra=2/mouvements=1/dialogue=0 dans EpisodeService. KREA2 dispose déjà du composant partagé ressources (favoris/fiches/LoRA), de presets de style avec image/prompt/checkpoint/LoRA et du guidage visuel par échange. Proposition : style d'épisode réutilisable, défauts communs et exceptions par fiche explicites, contrôle créatif complet par scène. Une image de style guide le LLM ; ce n'est pas un conditionnement image supplémentaire du renderer KREA2. Discussion conservée dans `docs/proposals/episode-workshop-10s.md`. Aucun nouveau changement fonctionnel conservé, aucun test/LLM/rendu/redémarrage/publication dans cet échange.

- **Contrôles finaux Fabrication 1.0** : AST de neuf fichiers Python, syntaxe de quatre scripts JS et de deux fixtures navigateur, IDs HTML uniques, champs de l’atelier présents et correctement imbriqués dans Histoires. Diff whitespace des fichiers suivis et scan UTF-8/espaces des neuf nouveaux fichiers OK. Pas de tests exécutés ni d’import applicatif de vérification. Points inspectés : 4 références sans troncature, contrats KREA2/REF2V, deux appels explicites, rôles/Picture/locuteurs, reprise sans nouveau Plan, sauvegarde des réglages vidéo avant navigation/rendu, chargement des catalogues différé, options d’extension du renderer désactivées dans les ateliers H3/REF2V existants. Validation du rendu réel et du navigateur laissée à l’utilisateur.

- **Fabrication 1.0 dans `.panelpatch`, non publiée** : nouveaux domain/application/storage `episodes.py`, routeur `episodes_web.py`, UI `episodes.js/css` dans Histoires. Validation explicite du scénario sans modèle, snapshots et plusieurs fabrications, fiches personnages/décors réutilisées, import/choix d’images, mini KREA2 Assisted 3.0.0 (rédaction puis file existante), historique et ouverture du projet complet. Scènes par sélecteur, rôles/ordre 1–9 images, action éditable et dialogues exacts du scénario ajoutés automatiquement ; pas de coupure à trois. REF2V Classique `planned@1.0.0`, Qwen local `unsloth/Qwen3.8-27B-GGUF` puis Gemma local `unsloth/gemma-4-31B-it-qat-GGUF`, modifiables, Plan puis writer via services actuels, reprise du writer sans refaire un Plan accepté. Copies des entrées et liens session/projet conservés, changements d’images signalés comme anciens, conflits de révision et jobs interrompus traités. Instance isolée du composant H3Render pour l’épisode, defaults BUNNY 0.1.3 / 9-4-5 / 0,9 MP / durée scène / Motion Repair 0,60-0,20 seul, réglages persistants et essais/preview/DLSS existants. Extensions facultatives du composant pour montage dans Histoires, contexte et sauvegarde ; aucun workflow ni prompt H3 modifié. Cache stories.js 20260915.3, h3-render-lab.js 20260915.1, krea2-assisted-lab.js 20260915.2, episodes 20260915.1. Tests `test_episodes` et `test_episodes_browser` préparés, non exécutés selon AGENTS ; vérifications statiques seulement, aucun LLM/rendu/redémarrage. Guide `docs/episodes-1.0.md`. Import long Video Lab, production en lot et assemblage différés ; P1/P2 inchangées.

- **Limite REF2V rectifiée après audit complet** : UI `ref2v-direct.js` et contrats session/projet acceptent neuf images. `run_lab.py` injecte `Ref2VH3RenderPresetRecipe` (maximum 9) dans H3RenderService via les wrappers checkpoint/LoRA qui délèguent cet attribut ; les trois loaders du manifeste 0.2.4 sont étendus jusqu'à neuf. BUNNY accepte aussi 1–9 et câble les références aux deux conditionnements. GET object_info Bucket confirme `ref_images.max=9` pour `MiniMaxH3ReferenceToVideo` et `MiniMaxH3AudioConditioningT8`. Trois persiste uniquement dans l'ancien rendu Video Lab et son transfert `sendToVideoLab` (`slice(0, 3)`). L'annonce de trois pour l'atelier et la question de repli personnages/décor sont invalidées : trois personnages + décor utilisent quatre images, capacité actuelle neuf au total par rendu. Aucun test/rendu/LLM/redémarrage, uniquement lectures et correction documentaire ; la qualité à neuf sujets n'est pas validée par cet audit.

- **Fabrication d'épisode cadrée après lecture de l'existant** : scénario actuel possède personnages/décors/liens de scènes et dialogues attribués ; REF2V expose Sujet / identité et Décor, ainsi que Plan/Rédaction avec modèles distincts. Recette Classique préférée `minimax.h3.ref2v.classic.cinematic.planned@1.0.0`, BUNNY actuel `minimax-h3-bunny@0.1.3`. Motion Repair du manifeste `minmax_nsfw/Motion_Repair.safetensors` = 0,60/0,20 ; pour le futur atelier proposer cette LoRA seule active, car le preset brut inclut aussi Combat V2. Réutiliser les services actuels ; H3/REF2V et leurs defaults globaux restent inchangés. Proposition navigation Histoires → Références → Scènes, snapshot du scénario validé, références partagées et réglages/essais propres à chaque scène ; changements signalés sans effacer l'historique. Import futur Video Lab >15 s explicitement différé, à distinguer des clips générés ~10 s ; rattachement P2 conservé. Docs cadrage/backlog actualisés seulement, aucun code/test/rendu/LLM/service modifié.

- **Histoires : sélecteur et virgules JSON corrigés dans le checkout** : `stories.js` réutilise `PanelForgeModelPicker`, checkbox `story-local` avec `data-llm-local-for=story-model` ; défaut nouvelle histoire Local + `local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP`, préférences par source dans localStorage, reprise du modèle enregistré d'une histoire et catalogue asynchrone sans écraser ce choix. Modèle absent indiqué indisponible, génération désactivée ; projets consultables même si découverte LLM échoue. Toolbar alignée en deux groupes, cache stories.js/css `20260915.2`, aucun changement au picker partagé. Trois échecs du projet `story-4ae5c19da61a415196ec8d3cf3891fba` examinés : deux Gemma Hauhau, un standard, tous finish_reason=stop, chacun trois virgules après ending avant }. Retirer ces seules virgules sur une copie permet la lecture de trois concepts complets. `decode_story_json` isolé au domaine Histoires accepte uniquement ces virgules finales hors chaînes/échappements ; contrats, données brutes, troncature et autres erreurs restent traités comme avant, sans appel en plus. Régressions Python/navigateur préparées, non exécutées. AST 4 fichiers, node --check stories.js et 4 scripts de fixtures, HTML IDs/coche et diff check OK. Aucun service redémarré ni LLM/rendu lancé. Brief du projet vide malgré son titre Tromperie ; aucune correction implicite du brief. Documentation/diagnostic ajoutés ; pas de publication GitHub.

- **Histoires r3 livrée et active dans le workspace** : trois nouveaux textes sous `prompt_sources/story.brainrot/1.0.0/editorial-r3/`. Concepts définis par actes/enjeux/conséquences ; writer illustré par deux micro-scènes JSON liées avec une enveloppe, des connaissances acquises au bon moment et une aide retirée ; révision conversationnelle alignée. Dialogues brefs sans quota rigide, fins par actes, anatomie fruit explicite, diversité des conflits et aucune caméra imposée. Seul changement Python fonctionnel : `LocalStoryRecipeStore._ensure` migre les installations r1/r2 d'origine vers r3 et préserve personnalisations/rollback. Régressions de migration ajoutées, non exécutées. AST 2 fichiers, UTF-8, syntaxe/forme/références du JSON d'exemple et `git diff --check` OK. Activation persistante effectuée via le stockage existant dans `D:\Code\panelforge\workspace` après constat active=2/last=2 et textes r2 d'origine : maintenant active=3/last=3, historique [3,2,1], les 12 fichiers d'archives r1/r2 vérifiés inchangés. Le port Lab par défaut 7860 ne répondait pas ; aucun service démarré ou redémarré. Chaque futur échange lit la recette active ; aucun LLM/rendu/test applicatif lancé. Pas de modification H3/REF2V, du schéma, de l'UI ni du nombre d'appels ; pas de commit ou publication GitHub. Guide/backlog et diagnostic r3 mis à jour. Qualité avec Gemma restant à évaluer par l'utilisateur.

- **Diagnostic des consignes r2 avant proposition r3** : les trois prompts `editorial-r2` demandent déjà actes concrets, causalité, preuves traçables, continuité et fins actives. Répéter ces règles n'est donc pas un correctif suffisant. `_request` envoie `concepts.txt` au premier appel et `scenario.txt` au développement ; les trois exemples narratifs complets du premier ne sont pas transmis au second, qui dispose surtout de règles abstraites et de deux exemples de répliques. Hypothèse à tester : montrer un court exemple de scènes liées au format JSON au rédacteur, reformuler les champs existants en actions/réactions/conséquences observables et suivre objets/connaissances dans opening_state/ending_state améliorera l'application des règles. Proposition r3 éditoriale : concepts plus distincts par actes/enjeux, exemple concret de micro-scènes, dialogues courts adaptés à 10 s, fin par acte, révision conversationnelle alignée. Garder variété d'intrigues et de fins, deux appels, schéma/UI et moteurs H3/REF2V. R2 restera accessible. Aucun patch fonctionnel ni appel de vérification effectué.

- **Scénario Le Prix du Luxe lu après développement r2** : export utilisateur `C:\Users\samue\Downloads\story-72b84838f7584d4cabbab3e8835329ce.txt`, appel `llm-88dc9db8e4904d5e950e3bee6c7fe864`, opération develop réussie en révision 2. Historique utilisateur : propositions puis développement direct, sans le retour narratif suggéré dans notre avis précédent. Six scènes de 10 s, deux décors et quatre personnages ; structure exploitable mais sacrifice seulement raconté, mépris concret tardif, scènes 3–5 étirent la révélation, fin sans décision visible. Contradiction majeure scène 3 : collier récupéré après le départ d'Ananas alors qu'elle est toujours observée dans la pièce ; collier « identique » ajoute une ambiguïté d'objet. Scène 5 : Fraise dit « tu n'as jamais vu ce collier » au lieu de parler de ce qu'il connaît lui-même. Dialogues scènes 5/6 autour de 30 mots chacun en 10 s, donc marge limitée pour silences/réactions ; scène 3 très peu d'évolution. Descriptions de Mangue/Prune insuffisamment explicites sur leur anatomie fruit pour de futures fiches KREA2. Avis : réviser actes, preuve et décision finale avant les rendus, sans changer la durée cible ni imposer de caméra. Aucun code, test, LLM ou service touché ; seule cette note de continuité est mise à jour.

- **Relance r2 confirmée, Le Prix du Luxe** : projet `story-72b84838f7584d4cabbab3e8835329ce`, appel `llm-4b1b026cfd8c4af5bf9274e306dfe9f9`, 16:49–16:50 UTC, réussi avec `recipe_revision=2` ; index actif=2/last=2. Le v3 affiché est la version du document après sélection, pas celle des consignes. Trois concepts uniquement, scénario pas encore développé. Progrès : sacrifice du mari, contraste social, quatre rôles conjugaux plus clairs, conséquences envisagées. Limites : méchanceté encore surtout qualifiée plutôt que montrée ; provenance du collier apporté par Prune non expliquée ; fin de la piste 1 réduite à un choix abstrait. Piste 2 recycle le motif salle de sport ; rouge à lèvres de la piste 3 insuffisant seul comme preuve. Avis : développer la piste 1 avec actes visibles, preuve cohérente et décision finale avant d'ajouter un nouveau correctif. Audit en lecture seule hors cette note, aucun appel LLM, test ou redémarrage.

- **Le dernier essai affiché n'utilise pas encore r2** : projet `story-134bf9ae422b4ffab49078acfbb7120b`, appel `llm-4b69a7525a3341e3a37b880c60b3bf05`, démarré 16:34 UTC ; trace et système envoyé = recette r1. `workspace/prompt_recipes/story.brainrot/1.0.0/active.json` reste active=1/last=1, sans marqueur de mise à jour. Code r2 écrit avant cet appel (stockage 16:25 UTC, consigne 16:27 UTC) : le chargement de r2 n'a pas eu lieu dans ce service. Nouveau brief contient fruits explicitement et omet l'insistance sur le jargon adolescent, mais garde la faute « machineins », interprétée comme « machine-like » dans le raisonnement. Avis : progrès d'apparence, trois variations du même mécanisme alibi→objet→annonce, peu d'actes cruels/enjeux/conséquences ; Piste 1 contradiction retour maison puis liaison « actuellement » en cours ; « co-épouse » ne désigne pas l'épouse de l'amant. Piste 3 offre une base plus forte par l'exploitation des soins du conjoint. Lecture seule, aucun changement de recette/code/runtime ni appel LLM pour cet avis.

- **Histoires r2 éditorial dans le checkout, à charger au redémarrage** : diagnostic du projet `story-2ed759b21bef4e348389fa67eae9dc16` et ses trois traces en lecture seule. Gemma interprète brainrot comme slang/comédie ; ancienne recette trop orientée gag, liens conjugaux incohérents et trois scènes de soupçon répétitif. Correction fruits rejetée à cause des clés `concepts` et `selected_id` ajoutées au scénario. Nouvelles consignes sous `prompt_sources/story.brainrot/1.0.0/editorial-r2/` : fruits adultes/échelle humaine par défaut, mélo sérieux malgré l'apparence absurde, conséquences, morale simple si demandée, relations/preuves cohérentes, exemples plus proches. `LocalStoryRecipeStore._ensure` active r2 uniquement sur r1 usine intacte, garde r1 et respecte personnalisations/rollback. Workspace utilisateur non modifié ; trois sources actives vérifiées identiques à l'usine. Parseur accepte l'enveloppe connue en révision après validation, sans changer la sélection et sans effacer le scénario ; inconnus/incohérences restent refusés. Nouvelles pistes excluent ancien scénario et anciennes réponses LLM du contexte principal, gardent demandes auteur et pistes à éviter. AST 4 fichiers, UTF-8 et diff check OK ; tests ajoutés non exécutés, aucun LLM/rendu/redémarrage. Voir `docs/diagnostics/stories-editorial-r2-2026-09-15.md`.

- **Histoires 1.0 dans `.panelpatch`** : nouveaux modules `domain/stories.py`, `application/stories.py`, stockage local et routeur dédiés ; branchement dans `run_lab.py`/`create_app`, nav `stories`, HTML/JS/CSS séparés. Trois concepts, discussion sans mutation ou révision, scénario structuré avec locuteurs/décors référencés, sélection et reprise de versions. Un appel par action, workers sur demande, annulation coopérative, double soumission dédupliquée, conflit de version, reprise après interruption. Les modèles ne sont chargés qu'à l'ouverture et les projets restent accessibles indépendamment. Recette isolée `story.brainrot@1.0.0`, sources `prompt_sources/story.brainrot/1.0.0`, édition/reprise via l'éditeur existant et traces durables avec ID story. Export texte/intentions avec ou sans durée, dialogues exacts, aucune caméra imposée. Docs `docs/stories-1.0.md`, backlog/proposition actualisés ; tests `test_stories.py` et `test_stories_browser.py` préparés, non exécutés selon AGENTS. Aucun LLM, rendu ou redémarrage lancé. Contrôles statiques terminés : AST de dix fichiers Python, syntaxe des trois scripts JS et des fixtures navigateur, 41 identifiants HTML/40 liaisons JS, navigation/chargement et git diff --check OK ; pas de publication GitHub demandée pour ce patch.

- **Quatre exemples narratifs supplémentaires examinés visuellement** : `Download(6).mp4` 64,73 s, `Download(2).mp4` 60,70 s, `Download.mp4` 61,43 s, `Download(5).mp4` 77,20 s ; captures CPU toutes les quatre secondes dans le répertoire temporaire `panelforge-story-examples-lny6ixbq`. Pas d'écoute/transcription, aucun appel LLM, rendu ou redémarrage. Constats fondés sur images et sous-titres visibles : conflit simple, excès des antagonistes, contraste apparence rassurante/comportements hostiles, objets et révélations concrets, fins parfois cruelles/ouvertes. Proposition narrative documentée dans `docs/proposals/episode-workshop-10s.md` : concepts variés → choix/dialogue → scénario attribué → intentions libres ; ne pas généraliser la morale réconciliatrice du pilote fraise/poire. Tests de prompts avec huit secondes explicites ou durée absente ne changent pas encore le format d'atelier de dix secondes.

- **Production V1/V2 retirés de l'interface active** : deux boutons et deux imports de scripts supprimés dans `index.html`, espaces retirés du registre de navigation `lab-core.js`, cache 20260915.1. Les anciennes vues en sessionStorage retombent sur Image Lab. Backend, données, scripts historiques et markup masqué conservés ; aucun job interrompu ni service redémarré. Assertions existantes de navigation/imports/cache ajustées, aucun nouveau test écrit ; syntaxe JS, AST des trois tests Python, structure HTML et diff vérifiés. Tests applicatifs non exécutés selon AGENTS. H3/REF2V et les autres ateliers ne changent pas.
- **Cadrage narratif 10 s documenté** : `docs/proposals/episode-workshop-10s.md` et proposition non priorisée dans backlog. L'entrée souhaitée est l'idéation/dialogue sur une histoire, ce qui précise la question asynchrone précédente. Une micro-scène de 10 s est une unité de rendu et peut contenir plusieurs plans caméra ; scénario avec répliques attribuées comme source, fiches KREA2 validées et décors récurrents proposés, storyboard utilisateur distinct du Plan JSON interne. Références REF2V directes ou étape d'image de départ supplémentaire en I2V à discuter. Clips en file, reprise individuelle, DLSS après sélection, assemblage/sous-titres proposés ; voix constante entre clips non garantie par les fiches. Aucun générateur d'épisodes implémenté, aucun LLM/rendu lancé.

- **Deux exemples vidéo examinés visuellement** : premier 61,43 s, second 108,74 s, tous deux 576×1024 / 30 FPS, piste AAC. Extraction CPU de captures toutes les deux secondes avec le FFmpeg déjà installé dans Subtitle Edit ; planches temporaires hors workspace (`panelforge-video-review-pjn0_jon`, `panelforge-video-review-2-3gqgy_ve`). Pas d'écoute ni de transcription exécutée : constats issus des images et sous-titres visibles. Format commun : courts épisodes verticaux en 3D stylisée, fruits/légumes anthropomorphes récurrents, visages expressifs, scènes dialoguées relativement simples, réactions en gros plan, changements de lieux et fondus, sous-titres courts. Premier : restaurant, bureau, cuisine ; second : mine, lingots/sac, bureaux et chambre, retours aux personnages.
- **Manques pour automatiser ce format** : coordination à l'échelle d'un épisode (scénario causal, dialogues attribués, découpage, états des personnages/objets/décors), casting et références persistantes entre clips, sélection/reprise par séquence, montage et sous-titres exportés, continuité vocale entre rendus à évaluer. Les moteurs KREA2/Qwen, H3/REF2V, dialogue et transcription existent ; Production V1/V2 possèdent déjà file/validation/reprise mais leurs contrats restent centrés sur un clip et V2 pointe d'anciens profils H3/REF2V. Analyse média actuelle : 16 frames maximum, extrait ≤60 s, cible 5–15 s ; elle ne transforme pas un épisode complet en plan de production multi-clips. Proposition : petit atelier Épisode coordonnant les services actuels, preset de série, deux appels H3 par clip conservés ; commencer par un pilote 20–30 s, deux personnages/un décor, avant l'automatisation plus longue. Aucune implémentation, aucun LLM/test/rendu ou service lancé dans ce tour.

- **Version REF2V du 15 septembre** : snapshot de livraison `snapshot-ref2v-2026-09-15`, branche `snapshots/ref2v-2026-09-15`, dépôt `https://github.com/EasyFrag/panelforge.git`. Comprend le routage Classique REF2VA, l'ordre des références et la reprise des projets mal classés sans essais, les tests préparés et le guide. Point de retour avant patch conservé sous `snapshot-avant-alignement-ref2v-2026-09-15` (`608e312`). Aucun changement supplémentaire de code pendant cette publication ; H3 reste figé.

- **Vérification finale du patch REF2V** : AST des trois Python modifiés/ajoutés valide, `git diff --check` OK. Comparaison AST avec `608e312` : seul `H3RenderService.get_or_create_from_session` diffère dans le fichier fonctionnel ; comparaison Git des sources/workflows/profils/cookbooks/consignes/UI/scripts : seul `h3_render.py` modifié. Tests de régression préparés mais non exécutés selon AGENTS ; aucun appel LLM réel, rendu, serveur ou donnée de workspace modifié. Le snapshot après correctif est demandé au tour suivant et référencé ci-dessus.

- **Snapshot pré-REF2V publié avant patch** : commit `608e312f91760ce5f70188ee005b94ac42a678b4`, branche `snapshots/avant-alignement-ref2v-2026-09-15`, tag `snapshot-avant-alignement-ref2v-2026-09-15`, sur `https://github.com/EasyFrag/panelforge.git`. Push atomique des deux nouvelles références puis vérification `ls-remote` branche/tag résolu : même commit. Remote local et branche principale GitHub inchangés. Contient l'état courant avec KREA2 sampling, DLSS léger, durée H3 et audits précédents.
- **Raccordement REF2V Classique corrigé le 15 septembre** : reconnaissance explicite de `minimax.h3.ref2v.classic.cinematic` en mode direct multimodal. Images reprises depuis le mapping de composition utilisé par les LLM, ordre/subset conservés ; projet REF2VA avec liste de références, sans champs de frames H3. Réouverture depuis la session : réparation du projet mal classé sans essai, par remplacement exclusif du mode et des champs images ; prompt courant, brouillons, paramètres et conversation conservés. Aucun balayage/migration du workspace pendant le patch ; un projet ayant déjà des essais reste consultable et sa reprise demande un nouvel atelier. Chemins H3 et REF2V historiques/Combat/Sensuel inchangés ; consignes, schémas, grammaire, UI et workflows inchangés. Tests ciblés écrits pour deux appels/LLM distincts, rôles, mono/multi, 1–9 images, ordre/subset, recette 0.2.4, réparation, historique et quatre modes H3. Guide `docs/ref2v-classic-render-fix-2026-09-15.md`.

- **Vérification du deuxième appel REF2V le 15 septembre** : `_sequence_request_scoped` transmet au rédacteur le Plan approuvé et le mapping REF2V des rôles d'images ; les images elles-mêmes sont vues par le Plan, pas renvoyées au Writer. Pour les dernières recettes à deux appels, le Writer produit les paragraphes de phases dans un JSON, puis le compilateur construit le prompt vidéo. `cinematic_core_v1` conserve le header de rôles REF2V, omet `integrated_multimodal_description` en REF2V et distingue le titre mono-plan ; le contexte REF2VA est bien construit à partir du target_mode du cookbook. Ces adaptations de prompting existent déjà et sont distinctes du bug de routage vers le rendu. Le schéma de Plan est actuellement commun à H3/REF2V au sein d'une famille ; ce sont les rôles/contextes qui diffèrent. Ne pas présenter une future spécialisation du JSON REF2V comme déjà implémentée.

- **Audit H3/REF2V terminé le 15 septembre 2026** : recettes récentes présentes des deux côtés (Classique 1.0, Combat 1.3, Sensuel 1.0, deux appels et LLM rédacteur indépendant). Comparaison du workspace : Classique r2/r2, 34 fichiers identiques ; Sensuel H3 r2/REF r1, 35 fichiers identiques ; Combat REF non initialisé dans l'éditeur, mais recette 1.3 et mêmes blocs disponibles. UI de rendu partagée, catalogue actuel H3 0.1.6 / REF 0.2.4 / BUNNY 0.1.3 ; anciens essais REF conservés en 0.2.3 et BUNNY 0.1.0.
- **Défaut REF2V Classique confirmé, non corrigé** : `h3_render.py:get_or_create_from_session` omet le profil `minimax.h3.ref2v.classic.cinematic`. Session récente `prompt-b08c5a9d2ca4447abbbe38d61efed33f` avec première frame + référence sujet, Plan Qwen / Rédaction Gemma r2, produit le projet `h3-render-22b2bdeb73a94092894086b85365d070` en I2VA, première frame conservée, références vides, zéro essai lors de l'audit. Le relevé trouve ce seul projet mal classé contre 35 anciens Direct/Combat correctement classés. La reprise retourne le projet sauvegardé avant le routage : correction future doit couvrir aussi ce cas existant. Diagnostic `docs/diagnostics/h3-ref2v-parity-2026-09-15.md`. Aucun code ni donnée applicative modifiés dans ce tour ; documentation seulement.

- **Constat KREA2 Modif image jointe au message** : `stream_prepare_prompt` reçoit STAGE SOURCE et éventuellement GENERATED FEEDBACK ; le parcours décor + sujet existant peut aussi transmettre SUBJECT REFERENCE au LLM puis au renderer, avec rôles spécifiques. L'API `Krea2EditPromptBody` n'a pas de champ de référence libre par échange. Proposition : une pièce jointe facultative à la consigne, vue par le LLM avec source/feedback, attributs à reprendre déterminés par le texte utilisateur, aperçu et historique, prompt final autonome sans renvoi à une image que le renderer ne recevrait pas. Un appel multimodal existant enrichi, aucun appel supplémentaire prévu ; guidage direct du renderer par cette image exclu du premier périmètre proposé. Backlog documenté ; aucun code, test, rendu, LLM ou service exécuté/modifié dans ce tour.

- **Sampling Assisted 1.0 implémenté** : contrat propre `Krea2AssistedSettings` étendant les réglages communs sans modifier Batch, deux passes validées 1–50 steps, sampler/scheduler natifs explicitement proposés. Presets current 8+2 er_sde/simple, finish_4 8+4 er_sde/simple, moody_beta 8+4 euler_ancestral/beta ; custom après saisie, version 1.0.0 et valeurs réelles sauvegardées. Wrapper `image.generate.assisted/krea2-sampling@1.0.0`, base Batch 0.2.0/SHA exact, six bindings dans manifest uniquement ; source/compilateur Batch inchangés, CFG/denoise/latent intacts. Injection propre au service Assisted dans run_lab. API essai, brouillon de branche et application de preset de style transmettent le sampling ; stockage schéma 9 lit 1–8 sans migration à la lecture et conserve le type historique. Conversion au contrat Batch pour presets de style partagés/publication, sans propagation implicite. Métadonnées de sortie incluent sampling ; prompts LLM inchangés. UI : sélecteur compact, Avancé replié avec chaque passe, résumé et info sur cartes, restore/ancien essai/nouveau projet, actualisation catalogue sans écrasement des saisies, invalidité locale avant envoi, file par essai immuable. JS Assisted/CSS 20260915.1. AST de 19 Python modifiés/nouveaux, syntaxe JS et deux fixtures assemblées, HTML/IDs/hash/bindings/diff vérifiés ; tests métier/API/stockage/navigateur préparés mais non exécutés selon AGENTS. Guide `docs/krea2-assisted-sampling-1.0.md`, backlog actualisé. Aucun LLM, rendu, navigateur, test applicatif, service, commit ou push lancé ; les patches DLSS/durée H3 précédents restent présents sans autre modification fonctionnelle dans ce tour.

- **Alignement KREA2 final** : Actuel = 8+2 er_sde/simple ; Finition 4 steps = 8+4 er_sde/simple ; Moody Beta expérimental = 8+4 euler_ancestral/beta. CFG 1,1 puis 1,0 et denoise finition 0,30 conservés. Preset visible, détails des deux passes repliés, Personnalisé après modification, instantané dans chaque essai et reprise fidèle. Tableau alternatif transmis puis retiré par l'utilisateur ; ne pas ajouter res_multistep ni substituer euler à euler_ancestral. Backlog marqué périmètre validé, priorités P1/P2 inchangées ; aucun code, test, génération ou service modifié/exécuté.

- **Constat et proposition KREA2 sampling** : Assisted utilise `image.generate.batch/krea2-community/0.2.0` injecté par `run_lab.py`, pas le workflow T2I simple. Première passe : 8 steps, er_sde/simple, CFG 1,1, denoise 1 ; latent ×1,5 ; finition : 2 steps, er_sde/simple, CFG 1,0, denoise 0,30. Ces valeurs restent fixes lors d'un changement de checkpoint. Proposition : actuel 8+2, essai finition 8+4 au même couple, essai Moody 8+4 en euler_ancestral/beta aux deux passes ; CFG/denoise/seed/résolution conservés pour commencer. Indications primaires consultées : dépôt officiel krea-ai/krea-2 (Turbo distillé 8 steps) et API Civitai modèle 2731187 (Moody Euler A/beta 8, jusqu'à 12 dans les recommandations V6, sans confirmation propre V7 BF16). Les deux passes proposées sont notre adaptation à tester, pas un preset auteur validé. Ne pas confondre avec le T2I historique Euler/simple 8 ou Identity Edit Euler/simple 10. Proposition ajoutée au backlog sans modifier P1/P2 ; seuls backlog et continuité édités, aucun code, test, rendu, LLM, service, commit ou push lancé dans ce tour.

- **Transmission de durée H3** : ajout du format canonique `target video lasts N seconds` (décimales comprises) à `inferredDuration` du panneau commun H3/REF2V et à l’avertissement serveur `h3_prompt_duration_warning`. Les anciens formats restent pris en charge, le défaut de recette reste le repli en absence de durée admissible (5–15 s). Initialisation depuis le prompt seulement à l’ouverture ; `fillSettings`, paramètres manuels et envoi de `duration_seconds` inchangés. Cache `h3-render-lab.js` 20260914.2. Fixture navigateur utilise désormais le vrai lecteur de durée et couvre 12,5 s jusqu’à la requête, override manuel, ancien essai et REF2V ; test backend d’avertissement ajouté. Vérifications syntaxiques de quatre Python, JS H3 et fixture assemblée, diff OK. Aucun test fonctionnel, appel LLM, génération, service, commit ou push lancé. Patch DLSS vidéo léger précédent conservé.

- **DLSS vidéo, profil léger** : `videoEffects` partagé par les défauts rapide/avancé et le bouton `Profil vidéo léger`, qui ne réinitialise que les six effets. Géométrie, interpolation, codec et HDR explicitement choisis restent conservés ; HDR désactivé par défaut. `DlssRequestBody.resolved_settings` applique les mêmes effets uniquement aux champs omis pour H3/REF2V. Contrat partagé DlssSettings, tâches enregistrées, workflow manifests/graphes et réglages/comparaison image inchangés. Cache `dlss-lab.js` 20260914.1. Documentation `docs/dlss-local.md` actualisée. Trois fichiers Python, JS DLSS et quatre blocs de fixtures navigateur vérifiés syntaxiquement ; constante image comparée au HEAD identique, diff sans erreur. Tests adaptés aux frontières API/workflows et navigateur (profil, reset sans lancement, préservation HDR/taille/cadence, isolation image), non exécutés conformément à AGENTS. Aucun LLM, rendu, service, test applicatif, commit ou push lancé dans cette tâche ; qualité du teint à évaluer par l’utilisateur.

- **Snapshot GitHub `2026-09-14.2`** : contenu fonctionnel regroupé dans `75f1271781aadb576bff79a7f190f711cdc98e35` (16 fichiers, 202 ajouts, 70 suppressions) et publié sur `https://github.com/EasyFrag/panelforge.git`, branche `snapshots/lab-2026-09-14.2`. Le tag annoté `snapshot-lab-2026-09-14.2` pointe sur le commit documentaire final de cette livraison. Branche distante et tag déréférencé vérifiés ; branche locale `h3-video-lora` et remote local `origin` vers `D:\Code\panelforge` conservés. Inventaire, diff stagé, whitespace et motifs de credentials contrôlés sans inclure de données runtime. Vérifications statiques des patches terminées ; tests applicatifs non exécutés, aucun LLM/rendu/service lancé ou redémarré.

- **Validateur Plan Sensuel corrigé après diagnostic des deux derniers rejets** : dans `sensual_cinematic._normalize_speech`, une balise `<d>English texte</d>` sans crochets est canonisée seulement si `texte` correspond exactement à une entrée de `spoken_lines` et si `English` est exactement sa langue déclarée ; une langue ou des mots différents restent rejetés. Dans le lint H3 commun, seule la formulation spatiale passive `from [the] camera position` est retirée de la détection de mouvement ; `camera position shifts`, `camera drifts` et les autres mouvements libres restent des erreurs. Cette exception générique corrige un faux positif du protocole commun sans changer les prompts ou les sorties des familles ; la tolérance vocale reste propre à Sensuel. Régressions ajoutées dans `test_sensual_cinematic` et `test_minimax_h3_protocol`, couvrant les deux cas acceptés et les deux contre-exemples rejetés. AST des quatre fichiers, gardes structurelles et `git diff --check` OK. Tests applicatifs non exécutés, aucun LLM/rendu/service lancé ou redémarré. Le Lab doit être redémarré par l’utilisateur pour charger le Python modifié.

- **KREA2 Modif, LoRA après import corrigés** : le chemin d’import remettait `state.busy` à faux seulement après `openSource(..., hydrate: true)`. L’hydratation reconstruisait donc les champs LoRA désactivés, puis `render()` ne les reconstruisait pas ; cela expliquait le comportement intermittent selon le chemin d’ouverture. L’état occupé est maintenant terminé juste avant l’hydratation, comme sur les chemins recadrage, promotion, reprise et recommencement. Cache `krea2-edit-lab.js` passé à `20260914.2` et assertion de régression ajoutée dans `test_krea2_edit_web`. Catalogue, sélection, forces et backend inchangés. AST du test, présence du cache-buster, ordre du déverrouillage et `git diff --check` vérifiés. Le Lab local sur le port 7861 sert déjà l’index `20260914.2` et le JavaScript corrigé : aucun redémarrage nécessaire, seulement Ctrl+F5. `node --check` indisponible car aucun exécutable Node n’est présent dans le PATH ni aux emplacements locaux usuels ; le changement JavaScript est une seule affectation existante déplacée dans le cycle d’état. Aucun test applicatif, rendu, modèle ou service lancé/redémarré.

- **Sensuel sans alignement, patch local** : `Participant.adult` et `Plan.consent_confirmed` supprimés du contrat Pydantic et donc du JSON Schema envoyé au Plan ; descriptions, direction, Plan, Writer, exemple, politique dynamique et révision avant/après rendu nettoyés des notions ciblées. Les règles de caméra, références, identité, continuité, dialogues, structure JSON et non-invention restent en place. Les anciens Plans portant encore ces deux champs sont normalisés à la lecture pour préserver les ateliers archivés, sans réinjecter ces champs dans le nouveau contrat. Les blocs partagés Sensuel alimentent H3 Base et Ref2V sans toucher Classique/Combat/KREA2. Workspace courant : H3 Base révision 2 active, révision 1 archivée ; Ref2V initialisé en révision 1 propre car aucune archive n’existait encore. Le premier enregistrement API a révélé un `TypeError` préexistant dans `validate_template` pour les placeholders sans format ; garde `spec` corrigée d’une ligne, puis sauvegarde versionnée réussie. Contrôles statiques : AST Python, JSON exemple, assemblage H3/Ref2V, schéma/politique/révision sans les six familles de termes ciblées, compatibilité d’un ancien Plan et `git diff --check` OK. Tests applicatifs non exécutés, aucun LLM/rendu/service lancé ou redémarré.

- **Publication GitHub du Lab** : code regroupé dans `8aa23e10cb162fed0e9032d5f4d1cbd4e59f2a14` (132 fichiers), poussé sur `https://github.com/EasyFrag/panelforge` / `snapshots/lab-2026-09-14` ; correspondance du SHA distant vérifiée. Le commit documentaire suivant enregistre cette livraison et porte le tag annoté `snapshot-lab-2026-09-14`. Checkout actif `.panelpatch`, branche locale `h3-video-lora` ; remote local `origin` conservé, publication directe vers GitHub. Vérifications statiques : 47 Python, 7 JavaScript, 3 JSON ; hashes du workflow/prompt Qwen corrects dans l’index ; 61 fragments LLM identiques aux replis du code. Cinq espaces terminaux de fragments de prompt sont intentionnels et conservés pour l’assemblage exact, autres fichiers sans erreur de whitespace. Aucun test applicatif, LLM, rendu ou service lancé. Le snapshot antérieur `snapshot-before-render-ux-prompts-2026-09-14` reste disponible.

- **Qwen Changer la vue 0.3.0** : nouveau bundle conservant les octets du workflow/prompt 0.2.0, bindings supplémentaires validés ; identifiants de nodes uniquement dans le manifest. `ChangeViewRenderSettings` valide 1–50 steps, 0,1–4 MP ou automatique, ratios explicites. Défauts inchangés ; MP manuel utilise ImageScaleToTotalPixels, ratio imposé ImageScale/crop center, alignement 32 px, aucune dépendance ajoutée. LoRA Lightning 8 steps, CFG/sampler/prompt conservés. API spec + champs multipart, paramètres persistés dans les runs, reprise à l’ouverture de l’historique, bouton Réglages initiaux. UI rangée dans les réglages avancés existants ; lab.js 20260914.2, CSS 20260914.4. Guide `docs/qwen-change-view-settings-0.3.0.md`. Tests préparés pour defaults identiques, réglages indépendants, bornes, persistance et route ; uniquement AST Python/Node --check/HTML/hashes/diff vérifiés, aucune génération ni service relancé.

- **Diagnostic H3 Plan du 14 septembre** : `docs/diagnostics/h3-plan-dialogues-2026-09-14.md`. Qwen a répondu normalement, puis rejets applicatifs : registre des paroles imposées vide → répliques japonaises classées comme ajouts réservés à l’anglais ; autre réponse avec deux `<Picture N>` dans un champ unique ; autre réponse avec `Japanese` sans crochets dans les blocs vocaux. Plan accepté à 11:04 Paris : deux citations délimitées par guillemets droits, registre contenant exactement ces deux paroles japonaises ; Writer Gemma accepté à 11:06. Les parenthèses ne sont pas reconnues par l’extracteur, ce sont bien les guillemets qui diffèrent dans les traces. Pas de changement H3 dans cette tâche. Quatre consignes expliquées : Plan, Writer, révision facultative avant rendu et révision dans l’atelier après essai ; deux appels habituels restent inchangés.

- **Recadrage de la source KREA2** : bouton `Recadrer la source` dans les contrôles de comparaison de l’étape éditable. Petit module `image-crop.js`, dialogue natif créé à l’ouverture et détruit à la fermeture, image ajustée à l’écran, rectangle en pixels natifs, extérieur assombri, déplacement et huit poignées. Annuler ne modifie rien ; validation POST `/api/image-lab/krea2-edit/sources/{source_id}/crop` avec source/dimensions/restart_count attendus et ID de demande conservé lors d’un retry du même rectangle. Décodage borné Pillow existant, orientation EXIF appliquée, recadrage PNG local sans redimensionnement ni LLM/Comfy. `Krea2EditCrop` et tentative locale `kind=crop`, stockage schéma 12 lisant 1–11, ancien original conservé. `crop_source` réutilise la promotion existante pour les versions, la chaîne et l’export, avec récupération du même résultat après échec partiel de création de l’étape. Prochaine étape : metadata.prompt/generated_prompt vides, état idle, historique de conversation vide ; réglages sauvegardés hérités. Exports marqués `image.crop@1.0.0` avec rectangle et dimensions, cartes sans faux steps GPU. Les outils de retouche/upscale restent réservés aux rendus, pas aux tentatives locales de recadrage. JS `image-crop.js` et `krea2-edit-lab.js` en `20260914.1`, CSS `20260914.3`. Guide `docs/krea2-crop-1.0.md` ; tests de régression `test_krea2_crop.py` et route dans `test_krea2_edit_web.py` ajoutés sans exécution. Contrôles statiques Python/JS/HTML/diff OK.

- **Petit correctif KREA2 appliqué dans `.panelpatch`** : `krea2_edit_assistance.decode` retire uniquement l'enveloppe complète json (ou sans langue), puis conserve la validation JSON/champs/types/tailles ; V2 et V3 utilisent ce décodeur, sans changement des consignes. Réponse brute conservée. Deux tests de régression ajoutés dans `test_krea2_edit_assistance_v3.py` : flux simulé V2/V3, stockage brut, LF/CRLF, rejet des enveloppes incomplètes, prose, JSON invalides et champs non conformes. Pas exécutés conformément à AGENTS.md. Dans Changer la vue, `change-view-download` utilise l'URL de l'asset existant avec un nom `.png`, visible seulement sur un résultat réussi, également depuis Historique → Voir ; lien précédent retiré pour les autres statuts. Aucun transfert ajouté vers KREA2 Edit. Actions peuvent revenir à la ligne. Versions navigateur lab.js `20260914.1`, CSS `20260914.2`. Syntaxe Python/JS, unicité des IDs HTML et diff vérifiés statiquement.

- **KREA2 Edit / angles Qwen, audit du 14 septembre** : deux runs Qwen Edit 2511 réussis à 10:21–10:22, `run-e487db66b8e148748853627d321a7626` (plan moyen) et `run-d159d2883db14dc190f38db519f40b65` (gros plan, marqué kept). Sorties Comfy Bucket à la racine `output/Qwen_Edit_2511_00001_.png` et `output/Qwen_Edit_2511_00002_.png`, historique Comfy et téléchargement GET confirmés ; empreintes identiques aux copies `workspace/assets/asset-69f64a3e9f024210a6e0c6b716cc4003/content.bin` et `asset-656447ab3fc34f16bdbcfaba81cce989/content.bin`. Aucun lien de ces assets dans les projets KREA2 Edit/Assisted ; Conserver ne fait que classer le run, Utiliser comme source reste dans Changer la vue. Journal disponible : 15 appels `krea2.edit.conversation@3.0.0`, neuf rejetés entre 10:08 et 10:31 (heure Paris), tous `JSONDecodeError` au premier caractère. Dans les neuf cas, un unique bloc Markdown json entoure un objet valide à deux chaînes message/prompt ; finish_reason stop, aucun échec fournisseur. V3 importe le decode V2, qui appelle json.loads(raw) directement ; Création assistée possède déjà une normalisation des blocs fermés. Détails dans `docs/diagnostics/krea2-edit-2026-09-14.md`. Aucun contenu de scène recopié dans le diagnostic, aucun service/modèle relancé.

- **Livraison UX/Recettes LLM dans le checkout actif `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`** : guide `docs/video-ux-prompt-editor-1.0.md`, sources expliquées dans `prompt_sources/README.md`. Nouveau `LocalPromptRecipeStore` injecté par `scripts/run_lab.py` : `<workspace>/prompt_recipes/<id>/<version>/active.json` et révisions numérotées immuables en fichiers UTF-8 avec empreintes, sauvegarde optimiste/activation persistante, portée exacte parmi six recettes. Écran `prompt-recipes.js` ouvert depuis barre supérieure ou Consignes LLM près du choix de préparation : Plan/Rédaction/Ajustement avant ou après rendu, règles conditionnelles facultatives, note, Enregistrer et appliquer, retour de version, aperçu du prochain appel sans LLM et historique de l'atelier. Sources historiques conservées dans `prompt_cookbooks`, résolution `get()` directe sans parcourir tous les manifests. Onze fonctions de politiques instrumentées avec `prompt_text` sous portée ContextVar ; 61 fragments initiaux dans `prompt_sources/_defaults`, comparaison AST inversée aux originaux : aucune différence de contenu ou interpolation. Hors recettes adoptées, les valeurs de compatibilité sont utilisées à l'identique ; aucun changement métier de prompting.

- **Cycles et traçabilité du patch** : `CompositionRevision` ajoute `llm_call_id`/`prompt_recipe_revision`, stockage schéma 6 lisant 1–5. Nouveau Plan/ajustement prend l'active, Writer d'un Plan existant reprend sa révision (ancien Plan sans métadonnée → r1 initiale), édition manuelle conserve la provenance de paquet. `LoggedMultimodalGateway` archive les appels portant un contexte vidéo dans `<workspace>/video_llm_traces`, en plus du journal vingt appels ; texte exact, réponse, raisonnement fourni, images par métadonnées/hash, résultats applicatifs avant/après fin persistés. Chaque rendu fige ses IDs d'appels de préparation et tours d'ajustement ; reprise d'un ancien prompt borne les tours, variantes DLSS utilisent le root_attempt_id. Consultation à la demande, pas de reconstruction trompeuse des traces anciennes manquantes. Ajustements après rendu utilisent la famille/mode/version du projet, indépendamment d'un changement ultérieur de recette dans l'atelier source.

- **UX/correctifs du patch** : contrôles H3/REF2V regroupés recette/checkpoint/preset ; MP, seed Réutiliser, ratio/durée/musique conservés ; LoRA (quatre et fiches) dans details avec résumé/interrupteur, steps/Turbo/aperçu avancés repliés. Raccourcis BUNNY on/off remplacés par select Rapide/Classique/Personnalisé, seuls les trois steps sont changés ; résumé Turbo arrondi à deux décimales ; pas de nouveau sampling, EROS ni comparaison BUNNY. `Durée cible` reconnue comme total (repères conservés, vrais totaux contradictoires rejetés). Classique initialise r2 technique avec liste fermée des cibles caméra dans système et description du champ Plan ; r1 initiale réactivable, validateur global intact. Cache scripts modifiés `20260914.1`. Redémarrage Lab par l'utilisateur requis.

- **Vérification de livraison** : Python AST, quatre scripts JS via `node --check`, HTML sans doublon d'ID ni erreur d'imbrication, `git diff --check` ; contrôle structurel des onze fonctions/61 fragments externalisés identiques au HEAD. Tests préparés `tests/test_prompt_recipes.py` (durée, stockage/reprise/rollback/isolation, variables/empreintes, deux appels synchrones/stream, aperçu sans gateway, traces >20, reprise de prompt, routes API) et adaptations des assertions de schéma/cache et fixture de contrôles déplacés. Tests NON exécutés, aucun appel LLM/image/vidéo, aucun redémarrage, aucun commit/push supplémentaire. Snapshot GitHub préalable `934cd2f` et tag du 14 septembre conservés. Les entrées de proposition/audit ci-dessous décrivent les étapes précédant cette autorisation.

- **Premier patch cadré, 14 septembre, documentation uniquement** : `docs/proposals/video-ux-prompt-editor-patch.md` détaille une livraison UX vidéo + Recettes LLM + traces exactes après rendu, précédée de correctifs durée/caméra distincts. Presets actuels exécutables seulement, EROS/BUNNY dépend d'un autre lot technique. Éditeur des dernières recettes à deux appels, révisions immuables du paquet et activation persistante, cycles en cours épinglés, familles/modes sans propagation implicite, sources lisibles et archives résolubles, migration à contenu constant. Critères de réception et suite du backlog précisés ; aucun code applicatif, prompt métier, runtime, service, génération, test, commit ou push modifié/exécuté pendant ce cadrage.

- **Éditeur versionné et traces après rendu, précision du 14 septembre** : `docs/proposals/editable-llm-prompts.md` et backlog actualisés. Recommandation : Recettes LLM → recette/étape → éditeur + révision, Enregistrer et appliquer crée une révision immuable active, ancienne version réactivable sans effacer les suivantes ; futurs cycles utilisent l'active même dans un projet existant, appels passés conservés et Plan/Writer d'un cycle entamé figés. Sources en fichiers et petite référence persistante, pas de DB/service/branches imposés. Échanges LLM accessibles depuis le rendu, système/user/contexte/réponse/raisonnement si fourni, modèle/date/étape/révision/erreur ; lier les appels aux préparations et rendus, lecture à la demande, assets référencés sans duplication. Ne pas promettre de reconstruire les anciennes traces évincées du journal à vingt appels. Un nouveau rendu sur un prompt H3 déjà écrit ne relance pas le LLM : les modifications s'appliquent à la prochaine préparation/ajustement. Discussion et documentation seulement.

- **Diagnostic durées média et Plan H3, 14 septembre, sans patch** : dernière analyse `analysis-31ddfde6821745f6b6a66db8354fbba5` / appel `llm-bda605532ed84833b25972835411396c` réussie à 07:29 UTC, extrait/cible 12,95 s. Le service produit `Durée cible : 12.95 secondes.` ; `direct_fl2va_prompt._EXPLICIT_TOTAL_DURATION_RE` ne reconnaît pas « cible », donc repli sur toutes les mentions : 12,95 / 6,66 / 9,16 s → conflit avant appel LLM. Compositions `prompt-b1b230ee255e4751938f72733cea024f` (07:30:42, trois durées) et `prompt-412eed3c7f3d4f3b9d1c3bc6bce56f1f` (07:31:27, durée changée à 10 mais repères conservés) sans aucune révision Plan/Writer. `prompt-0e3d19d7ace147c68c818a2370d4f763` (07:31:58, seule mention 10 s) : Plan `llm-a616bb69c34b47a89835a991aa5fc592` puis Writer `llm-6e185badef5045b5931d0946bf453b91` acceptés. Projet lié `h3-render-41cef7bebb4b4a46b928ff786da27de6` contient un succès et un rendu en cours au moment de la lecture, aucun processus touché. Correctif minimal proposé : reconnaître notre libellé cible et donner priorité à la vraie durée totale sans retirer les repères ; transmission structurée possible plus tard, préserver conflits de vrais totaux. Aucun contenu de scène recopié ; analyse de métadonnées et des motifs regex sur données existantes, pas d'import applicatif ni test/LLM/génération.

- **Rejet de Plan distinct retrouvé dans le même journal** : le 13 septembre à 19:25 UTC, Classique 1.0 / `llm-b156f188092a4068a43ac997ff8ced35`, caméra seconde phase `alongside the landing tiger` refusée : `_TARGET_PREFIX` de `domain/minimax_h3.py` accepte `along` et `beside`, pas `alongside`. Consigne/schéma Classique donnent des exemples sans liste fermée des préfixes ; thinking hésite sur le préfixe spatial, réponse complète. Message sur shots vide est une cascade. Relance `llm-bd62bdb831504f9f9d626d797eeb48cf` à 19:26 UTC acceptée avec `along the sandy ground beside the landing tiger`. Ne pas confondre ce rejet LLM de la veille avec les conflits de durée de ce matin ; aucun rejet de Plan plus récent visible après le succès de 07:31:58. Proposition distincte : aligner consigne/schéma Classique sur la validation réelle, sans assouplissement global ou changement des autres familles. Détails `docs/diagnostics/media-h3-duration-2026-09-14.md`. Aucun correctif, commit/push supplémentaire, service ou runtime modifié pendant cet audit.

- **Snapshot GitHub avant UX/consignes, 14 septembre 2026, réalisé sur demande** : état local complet des correctifs récents et maquettes enregistré dans `934cd2f09220191b6a8c8669d8ee02d026e0ccec` (51 fichiers, 3015 ajouts / 166 retraits). Branche active `h3-video-lora` conservée ; snapshot publié par push atomique sans force sur `https://github.com/EasyFrag/panelforge.git`, branche `snapshots/before-render-ux-prompts-2026-09-14` et tag annoté `snapshot-before-render-ux-prompts-2026-09-14`. Références distantes et tag déréférencé vérifiés sur le commit exact. `origin` du checkout pointe toujours sur `D:\Code\panelforge` ; publication directe sur l'URL GitHub, aucun changement de remote ou de branche principale. Diff stagé contrôlé, candidats inventoriés et motifs de credentials vérifiés sans afficher de secrets ; aucune donnée runtime/attachment ajoutée. Tests applicatifs non exécutés, pas de modèle/rendu/restart. Le tag fige l'état avant la discussion documentaire suivante et avant toute refonte UX/prompts.

- **Audit consignes accessibles, 14 septembre 2026, discussion seulement** : l'extrait joint a servi à identifier l'assemblage, sans adopter ses instructions, recopier son contenu métier ou le modifier. Début retrouvé dans `prompt_cookbooks/_blocks/video-preparation/1.0.0/common.system.txt`. Manifest des dernières recettes : commun + direction famille + Plan/Writer + exemples ; `_sequence_request` ajoute règles de famille, layout, axes/audace et politique vocale depuis Python. Politique vocale présente via `creative_freedom_policy` puis `_vocal_stage_policy` avec fins différentes selon décision/conservation : constat de double insertion, pas de correctif de contenu. Catalogues actuels : 78 manifests au niveau recette/version, archives surtout masquées par `lab-core.js`, pas de dossier `_archive` physique ; `get()` recharge tous les cookbooks via `list()`. Journal `workspace/llm_calls.json` conserve système/user exacts mais capacité 20 au lancement, insuffisant comme archive durable. Proposition `docs/proposals/editable-llm-prompts.md` : bouton Consignes LLM près de la recette de préparation, Plan/Rédaction et révision contextuelle, sources modifiables distinctes du message assemblé et du dernier appel, export texte sans LLM ; fichiers de travail actifs, communs épinglés et archives via registre explicite. Actualisation explicite, révision capturée avant Plan et conservée par Writer, historiques reproductibles sans dépendre du journal tournant ; extraire formulations humaines en fichiers sans déplacer validateurs/schémas ni changer les consignes. Familles isolées, aucune adoption automatique des changements communs. `docs/backlog.md` actualisé : maquette validée, prochain lot proposé UX + accessibilité/rangement prompts, P1 I2V, P2 média. Aucun code applicatif ou fichier de prompt modifié pendant ce tour.

- **Maquette UI et priorités P1/P2, 14 septembre 2026** : demande explicite de maquette interactive réalisée dans `docs/proposals/render-presets-v2.html`, autonome HTML/CSS/JS, aucune dépendance ou requête réseau (CSP connect-src none). Périmètre BUNNY commun H3 Base/Ref2V : onglets de démonstration, checkpoint, un sélecteur Rapide/Classique/Personnalisé, résumé steps/sampling/Turbo, dimensions/MP initiaux et après upscale/seed Réutiliser visibles, LoRA repliés avec jusqu'à quatre lignes, ordre/forces/fiches i, sampling/Turbo/preview et prompt repliables, aperçu illustré et historique fictif. Les choix EROS illustratifs affichent leurs recommandations auteur, sans inventer de triplets BUNNY validés, et ne permettent pas de lancement ; tout bouton de rendu reste une simulation locale. Changer de preset conserve les paramètres de scène/LoRA ; les raccourcis BUNNY conservent le Turbo ; choix d'EROS seul ne le modifie pas silencieusement. Ancienne maquette désormais liée à la nouvelle et marquée dépassée. Affichage vérifié par Chrome headless isolé avec GPU désactivé : grand écran, détails dépliés et viewport 420 px (largeur de contenu 405 px sans débordement horizontal). Captures `render-presets-v2.png`, `render-presets-v2-details.png`, `render-presets-v2-mobile.png` ; syntaxe JS analysée sans invocation via Node et 53 IDs HTML uniques. Aucun test applicatif, modèle, génération ou redémarrage de service lancé. Pas de changement du Lab ou de ses caches/recettes/données.

- **P2 : audit de video-to-h3-prompt, 14 septembre 2026, sans installation** : README, SKILL.md et scripts/heuristiques lus comme données, via sources GitHub primaires. Projet surtout consignes pour agent + extraction FFmpeg (2 fps script Windows par défaut, planches, audio/spectrogramme), Python/NumPy et librosa facultatif ; pas un générateur autonome. Reprendre la chronologie causale, la séparation action/caméra/montage et le réexamen borné des ambiguïtés. Rejeter genre musical déduit du volume et absence de musique déduite de la régularité d'une enveloppe d'attaques ; mesures d'énergie éventuelles seulement comme indices temporels, pas compréhension sonore. Base locale vérifiée : huit captures proposées/max seize extraites navigateur, un appel vision, transcription CPU facultative, intention FR/observations/incertitudes éditables, transfert explicite de références au pipeline H3/REF2V. Contrainte d'adaptation concrète : pas de vidéo complète conservée par l'analyse pour réextraction serveur ; réutiliser le fichier encore ouvert pour une première version légère, ou demander de le resélectionner après réouverture. Proposition à discuter : premier appel global + au plus un appel ciblé si ambigu, plafond exemple deux zones/huit nouvelles captures ; aucune boucle illimitée ni nouveau modèle/service audio, conserver les incertitudes et la séparation médias observés/références de génération. L'analyse ne remplace pas les appels Plan/Writer aval. Détails et sources `docs/proposals/media-analysis-adaptive-p2.md` ; priorités actuelles en tête de `docs/backlog.md`, ancienne P1 V1 marquée livrée. I2V 1.1 reste P1 différée, pas de changement de prompting dans ce tour.

- **Cadrage corrigé par l'utilisateur, 13 septembre 2026, discussion uniquement** : deux chantiers séparés, évolution du prompting I2V (bases réutilisables en REF2V avec adoption explicite) et simplification de l'interface de rendu. Abandon explicite de la zone de comparaison BUNNY, du bouton Comparer et des lancements en série proposés précédemment. Retenir un seul sélecteur Préréglage de rendu à la place des boutons Steps rapides / classiques ; conserver 9/4/5 et 30/25/5, puis ajouter les presets de sampling compatibles (steps + sampler/scheduler effectifs). Résumé visible, contrôles détaillés repliés, un rendu à la fois dans le parcours et l'historique habituels. Conserver MP initiaux/final, Seed Réutiliser et accès aux quatre LoRA/fiches ; aucun changement implicite de checkpoint, prompt, images, seed, dimensions ou LoRA. Les anciens raccourcis de steps ne changent pas le Turbo ; les nouveaux presets pourront avoir une politique explicite. Audit/adaptation des deux passes requis avant presets EROS utilisables, pas de promesse de presets déjà validés. `docs/proposals/bunny-sampling-presets.md` actualisé ; ancienne maquette marquée dépassée. Cette annulation concerne la proposition vidéo BUNNY, pas la comparaison DLSS image déjà implémentée. Aucun code applicatif, défaut, recette, projet, modèle ou service modifié ; documentation seule.

- **Proposition presets EROS/BUNNY et allègement UI, 13 septembre 2026, discussion seulement** : l'utilisateur réserve EROS à BUNNY, fournit six setups de https://huggingface.co/TenStrip/10Eros-Max?not-for-all-audiences=true et cherche en parallèle ceux de MiniMax classique. Fiche auteur consultée : er_sde/beta 4 ; er_sde/beta57 4–6 ; res_multistep/simple 6–8 (préférence mouvement auteur) ; lcm/simple 6–8 (audio Turbo selon auteur) ; lcm/beta 4–6 ; euler/simple 4–8. TURBO fusionné dans les variantes correspondantes ; pas de validation par nos rendus. Audit local BUNNY 0.1.3 + cinq GET `/object_info/<classe>` sur Bucket, lecture seule : DualClock expose les quatre samplers et beta57 (infobulle alpha 0,5 / beta 0,7) ; BasicScheduler n'expose pas beta57 ; ParityPlan refine 3–5 ; DetailMixer reçoit refine_sigmas sans sélecteur sampler/scheduler correspondant. Graphe actuel : sampler première passe issu DualClock mais sigmas issus ParityPlan ; seconde passe sampler/sigmas issus DetailMixer alimenté ParityPlan. Le calendrier du DualClock n'est donc pas directement branché sur les diffusions. 9/4/5 = 4+5 pas, impossible d'assimiler directement les nombres de l'auteur à nos trois champs. Nécessaire avant presets exécutables : vérifier/calibrer le raccordement réel modèle/samplers/calendriers des deux passes dans une nouvelle recette de rendu versionnée, témoin BUNNY 0.1.3 intact ; les entrées disponibles ne prouvent pas la qualité GPU. L'ancien lien source T8 `learned_latent_upscale_advanced.py` renvoie 404 ; aucun changement serveur tenté. Proposition documentée `docs/proposals/bunny-sampling-presets.md` et maquette autonome interactive `docs/proposals/render-presets-ui.html` : écran quotidien Moteur/Modèle/Préréglage + Ratio/Durée/MP initiaux/sortie/Seed Réutiliser/Musique/Lancer ; LoRA (4 et fiches conservés), sampling/Turbo/preview et prompt/conversion repliés ; retirer le sélecteur technique Profil de rendu LoRA et arrondir 0,700000… à 0,70. Presets liés aux checkpoints/moteurs exacts, versionnés, paramètres sampling/Turbo explicites sans remplacement des LoRA/images/prompt/résolution/seed. Comparaison dédiée : témoin + candidats Mouvement/Audio/Rapide, source auteur distincte d'une adaptation BUNNY non encore validée, valeurs exactes par passe requises. Série asynchrone orchestrée côté serveur, snapshots complets, suivi N/M, UI libre, pas de promesse de calcul GPU parallèle. Pour la suite des prompts : après 1.1 anti-redescription, envisager jeu d'acteur/perception/réaction, puis invention d'événements selon audace, puis rythme/cadrages, une variable/version à la fois, deux appels et familles indépendantes. Aucun code applicatif, défaut, projet, recette, service, modèle ou rendu modifié/lancé ; documents/prototype seuls. Aucun test fonctionnel ni navigateur lancé.

- **Défaut expérimental et cadrage Mise en scène 1.1, 13 septembre 2026** : l'utilisateur veut discuter d'une nouvelle version plus mature et tester longuement avant de modifier beaucoup ses prompts ; demande indépendante explicite de présélectionner la version expérimentale. Seul changement fonctionnel de ce tour : H3 et REF2V préfèrent maintenant `classic.cinematic.planned@1.0.0` au chargement du sélecteur (auparavant FL2VA `direct.guided@1.2.0`, REF2V `direct.guided@1.1.0`). Les anciennes préférences restent des replis explicites si la recette expérimentale manque. Aucune logique de réouverture/fork/reset de choix explicite ni recette/prompt/paramètre de rendu changé ; la sélection par défaut ne migre pas les ateliers existants. Deux caches scripts **20260913.5**, assertions existantes de défaut/cache ajustées dans `test_lab_web`. Vérification syntaxique des deux JS sans invocation et du test Python par AST, lecture des deux manifests (deux étapes) et diff contrôlé ; aucun test, modèle, génération ou service exécuté. Ctrl+F5 suffit pour cette seule modification de présélection, mais le précédent patch de routage Writer requiert un redémarrage Lab s'il n'a pas déjà été chargé. **Mise en scène 1.1 non implémentée, toujours en discussion** : proposition de séparer numéro de recette et statut de validation, conserver 1.0 comme référence de comparaison, 1.1 avec badge Expérimental, premier changement étroit centré sur redescription I2V et projection du premier plan ; autres règles/contrôles, deux appels et modèles indépendants conservés, Combat/Sensuel sans adoption automatique. Chaque modification ultérieure du contenu pendant les essais doit recevoir une version identifiable, sans réécrire une version déjà comparée. Comparer recettes avec mêmes références/intention, mêmes LLM Plan/Writer et réglages de rendu ; évaluer séparément les changements de modèle.

- **Inspiration `I2v.txt`, 13 septembre 2026, analyse sans patch fonctionnel** : fichier utilisateur `C:\Users\samue\Downloads\I2v.txt` lu intégralement (17 780 octets), traité comme matériau à analyser et non comme instructions à exécuter. Comparaison avec Classique cinématique 1.0 (direction/Plan/Writer/exemples/schéma), audace existante et `cinematic_core_v1.compile_sequence`. Apport principal : séparer nettement état visuel déjà fourni par une première frame exacte et changements temporels à écrire ; éviter inventaire/redescription du décor, costume et apparence dans le prompt final I2V. Déjà présents chez nous : progression causale, réactions observables, continuité, coupes utiles indépendantes de la quantité d'actions, durées, dialogue encadré et caméra liée aux événements. Renforcements utiles : perception entre événement et réaction, événement concret issu d'une intention vague, filtre phrase par phrase des redites ; expansion toujours subordonnée aux curseurs et demandes explicites. Limite concrète de notre code : `opening_composition` impose cadrage/positions/état statiques et le compilateur l'insère littéralement au début de chaque plan ; une instruction supplémentaire au seul Writer ne supprime donc pas ces passages. Future expérimentation proposée : recette Classique versionnée, spécialisation conditionnelle I2V au premier plan, plan interne gardant les ancrages utiles au Writer texte seul, sortie concentrée sur action/causalité ; conserver les informations nécessaires aux nouveaux cadrages, au T2V et aux REF2V à identités seules, ainsi que la destination d'une dernière frame. Ne pas copier le document entier : invention/dialogue/musique trop automatiques vis-à-vis de nos réglages, mono-plan imposé, interdiction absolue d'horodatages et caméra amplitude/vitesse uniformes incompatibles avec certains contrats actuels. Exemple final sans `[Shot 1]` pourtant requis ; exemple du téléphone posé sur un comptoir présenté comme vide compromet l'état initial ; exemples finaux parfois vagues malgré l'exigence de concrétude. Aucun rendement/qualité vidéo démontré par ce fichier, provenance officielle non établie. Pas de navigation web nécessaire à cette comparaison locale, aucun test, modèle, rendu, service, recette ou code modifié ; note de continuité seule. Maintenir Combat/Sensuel isolés et deux appels lors d'une éventuelle adoption, attendre instruction d'implémentation.

- **LLM distinct pour le Writer H3/REF2V, 13 septembre 2026, implémenté sur autorisation** : option « Utiliser un autre modèle pour le prompt final », décochée par défaut, second sélecteur avec source Local · Unsloth indépendante et résumé Plan → Prompt. Adoption explicite de six identités exactes uniquement : FL2VA/REF2V `classic.cinematic.planned@1.0.0`, `combat.planned@1.3.0`, `sensual.planned@1.0.0`, toutes à deux étapes. Allowlist neutre `domain/prompt_writer.py`, capacité publiée dans catalogue/composition ; anciennes versions et parcours un/trois appels exclus, aucun bloc de prompt, profil ou workflow modifié. `PromptComposition.writer_model_id` optionnel, stockage schéma **5**, lecture 1–4 conservée sans migration à la lecture ; validation domaine interdit une surcharge sur les autres recettes. API POST composition accepte le champ ; PUT `composition/writer-model` avec ancienne valeur attendue et sauvegarde conditionnelle pour modifier la prochaine rédaction sans invalider Plan/Prompt. Routage au seul Writer existant de `_sequence_request` (génération/révision, sync/stream) ; premier appel inchangé, pas d'appel ajouté ni nouvelle compilation. Images toujours au Plan seulement ; Writer reçoit le même contexte texte/consignes/schéma qu'auparavant. Sélection restaurée à la réouverture, conservée au fork UI et en continuation compatible vers H3 ; retour au défaut pour un nouveau parcours vierge. Module commun `prompt-writer-model.js`, contrôles désactivés pendant appels/sauvegarde, erreurs visibles avec retour à la valeur sauvegardée, catalogue partagé déjà chargé sans requête additionnelle et modèle choisi absent conservé explicitement. Caches CSS/deux écrans/module **20260913.4**, tests de cache ajustés ; tous les patches locaux UI/catalogue/DLSS précédents préservés. Tests préparés `test_prompt_writer_model` (routage même/deux modèles, reprise du Writer après panne, API, persistance, six capacités, isolation historique, sync/stream), `test_prompt_writer_model_browser` (vrais contrôles/ModelPicker, HTTP factice) ; test stockage adapté à 5. Syntaxe AST de 11 Python, trois modules JS et fixture navigateur vérifiées sans invocation, HTML/IDs/assets/ordre des scripts et six manifests à deux étapes contrôlés, diff vérifié. **Aucun test exécuté, import applicatif pour vérification, appel LLM, génération, navigateur, service ou commit/push lancé** conformément à AGENTS. Guide `docs/prompt-writer-model.md`. Qualité du couple Qwen/Gemma et chargement des modèles à valider par l'utilisateur après redémarrage du Lab et Ctrl+F5.

- **Lancement Comfy expliqué, 13 septembre 2026, lecture seule** : l’utilisateur a installé une nouvelle copie à côté de l’ancienne. Processus Lab actuels : `--base-url http://bucket:8188`, sans override DLSS. Démarrage local configuré via Python embarqué de `D:\AI\ComfyUI_windows_portable`, `-s ComfyUI/main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 --output-directory D:\AI\PanelForge\LocalOutput`, cwd racine portable, fenêtre masquée, FFmpeg/FFprobe dans `tools` via variables DLSS. Le .bat n’est pas appelé ; une instance compatible déjà présente sur l’URL locale est réutilisée. Journal et dernières tâches confirment URL locale 8188 et sorties LocalOutput. Pour changer l’installation démarrée automatiquement, fournir `--dlss-root` au lanceur Lab ; nouveau chemin pas encore communiqué. Aucun runtime/configuration/code fonctionnel modifié ni processus lancé/arrêté.

- **Affichage Dialogues et réactions corrigé, 13 septembre 2026**. Signalement utilisateur : la ligne apparaît seulement après manipulation de Vie de la scène. Cause dans les deux écrans H3/REF2V Direct : `updateCreativeAxes()` masque initialement le contrôle tant que `state.cookbook` est vide ; le chargement/changement de recette appelle `render()` sans recalculer la visibilité, contrairement aux événements input des axes. Correctif limité à deux appels `updateCreativeAxes()` au début des deux `render()`. La visibilité suit immédiatement `vocal_policy_version` après chargement ou changement de recette ; valeurs, defaults, payloads, contraintes de familles, prompts et backends inchangés. Caches des seuls scripts `i2v-direct.js` et `ref2v-direct.js` **20260913.3**, assertions de cache existantes adaptées dans `test_lab_web`. Syntaxe des deux JS et du Python modifié vérifiée, diff contrôlé ; aucun test fonctionnel, LLM, génération, navigateur ou redémarrage exécuté. Rechargement Ctrl+F5 après les traitements ; autres patches locaux conservés.

- **Comparaison de préréglages DLSS image, 13 septembre 2026**. Implémentation autorisée, limitée à Assisted/Edit : choix Upscale unique (défaut) / Comparer des préréglages, cinq profils initialement cochés, sous-sélection de un à cinq. Recette image `1.0.0` : actuels ; NR −0,25 ; détails +0,15 ; structure +0,20 ; tonalité −0,20. Chaque profil modifie un seul champ, conserve taille/style/peau/repli, est borné et devient indisponible s’il duplique la base à une limite. Route dédiée `/api/dlss/image-comparisons` refusant H3/REF2V, admission par helper image avec lecture de source/dimensions unique, identifiants de groupe/tâches stables et reprise idempotente d’un envoi partiel dans le même onglet ; conflit si même identifiant réutilisé avec réglages/sélection différents. Jobs enregistrés dans le journal et exécutés par le worker existant, métadonnées comparatives persistées, filiation/import et masque Edit inchangés. Nouveau module UI isolé `dlss-image-comparison.js` : lancement non modal après clic, suivi N/M, bouton Comparer DLSS sur les cartes et tâches prêtes, deux images avec zoom/déplacement synchronisés, source et variantes de mêmes dimensions, sélection explicite du candidat. Une fin de série ne sélectionne ni ne rafraîchit l’atelier automatiquement. Assets CSS/DLSS/module comparaison/Assisted/Edit **20260913.2**, resource-ui précédent conservé. Syntaxe vérifiée sur 22 Python modifiés/nouveaux, quatre modules JS et six blocs JS de fixtures, diff sans erreur ; `quick`, `jobText` et défauts vidéo comparés statiquement à HEAD et inchangés, aucun changement du worker, des presets/graphiques vidéo ou des schémas de projets. Tests préparés `test_dlss_image_comparison` (dont masques, admission interrompue, origine et annulation individuelle), `test_dlss_image_comparison_browser`, helper browser existant enrichi du vrai module/CSS ; non exécutés selon AGENTS. Documentation `docs/dlss-local.md`. Aucun service, LLM, Comfy, navigateur ou traitement réel lancé/redémarré, aucun commit/push demandé ; patches catalogue/UI/DLSS antérieurs conservés.

- **Diagnostic Gemma local, 13 septembre 2026, lecture seule** : les deux modèles locaux `unsloth/gemma-4-31B-it-qat-GGUF` et `HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP` sont présents dans le catalogue de PanelForge. Appel QAT texte accepté à 17:34:50 UTC ; trois appels avec une image échouent ensuite (Uncensored 17:36:35 et 17:38:22, QAT 17:38:43). Les logs enfants Unsloth `llama-1789321008-port-57421-try0.log:20`, `llama-1789321057-port-57636-try0.log:36`, `llama-1789321135-port-62354-try0.log:29` finissent tous sur `non-causal attention requires n_ubatch >= n_tokens`, assertion de `llama-context.cpp:1751`, puis WinError 10054 et perte de connexion remontée à PanelForge. Projecteurs chargés correctement, même panne avec MTP et ngram-mod ; pas de preuve de manque de VRAM causant ces trois échecs. Commandes de lancement sans réglage batch/ubatch : valeurs du code installé 2048/512, insuffisance du micro-batch pour une image Gemma4. Runtime installé le jour même : Unsloth llama.cpp `b10909-mix-bea84f7`, source `329b616`, CUDA13. Le signalement amont https://github.com/unslothai/unsloth/issues/10559 correspond exactement ; contournement signalé 2048/2048. La PR encore ouverte https://github.com/unslothai/unsloth/pull/10683 affine à ubatch 1120, plafond image Gemma4 également confirmé dans le `clip.cpp` installé. Recommandation ciblée au prochain chargement de ces modèles : `--batch-size 2048 --ubatch-size 1120`, conserver les autres paramètres ; validation image par utilisateur nécessaire. Aucun réglage, modèle, service, code fonctionnel ou donnée de projet modifié, aucun test/inférence/rechargement lancé ; seulement cette note de diagnostic. Les correctifs UI/DLSS locaux antérieurs restent présents.

- **Correction de la régression Image Lab, 13 septembre 2026**. Retour utilisateur : grosse zone vide à gauche, ateliers décalés et projets inaccessibles. Cause visuelle certaine : `catalogStatus` ajoutait un enfant direct à la grille, occupant la colonne des contrôles et repoussant le contenu à la ligne suivante. Emplacements explicites dans les deux panneaux latéraux ; projets récents Assisted en haut, liste bornée en hauteur, formulaire Nouveau projet repliable ; checkbox LLM locale corrigée. Ouverture de projet remplaçable pendant le chargement avec AbortController, délai 15 s, protection contre réponses tardives et message près de l’historique ; verrous des actions conservés, initialisation ne les remet plus à zéro. Réponse catalogue marquée appliquée seulement après affichage réussi, y compris initialisation statique Edit ; erreurs réseau/affichage distinguées et reprise possible sur une réponse identique. Cache existant lu : 38 modèles, 60 LoRA, aucun avertissement ; Lab non accessible sur 7861 pendant l’intervention, seule écoute Python Unsloth 8888. Cause exacte du message catalogue passé non confirmée, détail demandé à l’utilisateur ; aucune reprise serveur effectuée. Test préparé avec vrai HTML/CSS/module Assisted et vrai sélecteur LLM, requêtes factices ; contrôles statiques seulement, tests non exécutés selon AGENTS. Assets **20260913.1**, recharge complète suffisante lorsque le Lab tourne. Pas de changement backend, recette, réglage ou donnée utilisateur dans cette correction ; patch DLSS antérieur préservé. Guide `docs/image-lab-background-catalog.md` actualisé, aucun commit/push demandé.

- **Image Lab : catalogue en arrière-plan, 11 septembre 2026**. Suite au diagnostic (spec Assisted ≈7,7 s, historique ≈0,07 s, sidecars SSHFS ≈6,2 s), Assisted/Edit chargent désormais projets et catalogue indépendamment ; ouvrir un projet Assisted n’attend plus la file globale. Cache léger persistant `workspace/krea2_inventory_cache.json`, portée dossiers + URL ComfyUI, fraîcheur cinq minutes, un scan partagé en arrière-plan, anciennes données conservées si indisponibilité et reprise temporisée. Découverte LLM séparée et cache mémoire par passerelle. Bouton « Actualiser les modèles », fiches « i » chargées à la demande, métadonnées locales réutilisées cinq minutes ; préférences répercutées immédiatement. Rafraîchissement conserve sélection même disparue, LoRA/forces, prompt, navigation et masque ; worker Assisted vérifie les ressources sans lire toutes les fiches. Batch/H3 gardent leurs contrats, aucun graphe/recette/sampling/projet modifié. Cache CSS/resource-ui/Assisted/Edit **20260911.7**. Nouveaux tests factices `test_image_catalog_cache` et `test_image_catalog_browser`, attentes existantes adaptées ; contrôles statiques uniquement, tests non exécutés conformément à AGENTS. Aucun service, LLM, rendu ou navigateur lancé/redémarré ; gain réel à confirmer par l’utilisateur. Guide `docs/image-lab-background-catalog.md`. Patch DLSS image antérieur préservé ; pas de commit/push demandé.

- **DLSS image : défauts natifs et aides, 11 septembre 2026**. Le checkout est déjà à `3f7deb2`, identique à la branche GitHub `snapshots/sensual-1.0-2026-09-11` signalée par l’utilisateur. Intervention limitée à DLSS image : nouveaux panneaux Assisted/Edit à ×1,5 Quality, intensité/tonalité/structure/détails 1, peau −1 native, style Default, repli autorisé ; choix Taille source conservé dans Edit, réglages vidéo inchangés. Ancien panneau envoyait les quatre forces NR à 2. Aides « i » accessibles par clic/clavier/survol, valeurs fixes NR/modèle Default et masque auto désactivé visibles ; reset explicite image sans soumission, choix personnalisés conservés dans le brouillon par image. Défauts API image appliqués aux seuls champs omis, entrées explicites prioritaires ; bindings de workflow existants utilisés, aucun graphe/empreinte/tâche historique modifié. Documentation `docs/dlss-local.md`, cache CSS/DLSS **20260911.6**, tests préparés non exécutés conformément aux consignes. Contrôles statiques seulement ; aucun modèle, LLM, upscale, runtime, test ou redémarrage lancé. Aucun commit/push demandé pour ce patch ; version GitHub préexistante conservée.

- **Contrat `target_clause` Sensuel 1.0 aligne apres le premier smoke, 11 septembre 2026**. Le rejet `llm-ca1718f7ebf74655845ff780738bdbd7` etait correct : `tilt.down` portait la clause invalide `down between ...`; l'erreur de phase vide etait une cascade. La relance Plan `llm-915b73cab96243ec9be943442e184d95` puis le Writer `llm-c5cea031bc7d4c1091ed0d4c9a5df26a` ont ete acceptes. Correction limitee a Sensuel 1.0 : le bloc Plan partage par ses recettes H3 Base/Ref2V et la description JSON Schema enumerent maintenant exactement les 31 prefixes spatiaux/visuels acceptes par `H3CameraDirective`, interdisent de repeter la direction deja portee par le mouvement et donnent des exemples `tilt.down` valides avec `ending on`/`toward`. Le validateur commun, Classique et Combat restent inchanges ; aucun auto-fix ni retry silencieux. Test de regression prepare : contrat present dans prompt/schema, ancien `down ...` toujours rejete, `ending on ...` accepte. AST Python et `git diff --check` controles ; tests non executes conformement aux instructions. Aucun LLM, rendu, navigateur, service ou redemarrage lance. Version de livraison GitHub : branche `snapshots/sensual-1.0-2026-09-11`, tag `snapshot-sensual-1.0-2026-09-11`; snapshots anterieurs et `master` conserves.

- **Sensuel 1.0 explicite maximal implémenté sur autorisation, 11 septembre 2026**. Nouvelle famille indépendante `sensual@1.0.0` dans H3 Base et Ref2V, un seul niveau V1 verrouillé `explicit_maximal`, nombre de plans Auto ou 1–6 et exactement deux appels visibles Plan → Writer. Contrat propre `minimax.h3.sensual.cinematic_planned_v1`, schémas Pydantic, contexte/marker, prompts et exemple adulte explicite propres ; chaque beat porte `actor/action/contact/response/resulting_state` et un `beat_id` global conservé exactement par le Writer. Consignes renforcées pour employer une terminologie anatomique/action directe et éviter euphémisme, ellipse et résumé ; adultes consentants obligatoires, sans invention d’acte, participant, coercition, blessure, fluide ou climax non demandé. Aucun bloc, import de politique ou exemple `undressing.single_shot`, Combat ou Classique ; seul `cinematic_core_v1@1.0.0` neutre est adopté. Deux cookbooks/profils propres, sources MiniMax officielles et page H3 Eros Max épinglées. Réglages conservés dans création/fork/réouverture, projets/révisions H3, conversion H3→Ref2V et continuation depuis la dernière frame ; révision post-render propre `0.5.0`. Sessions schéma **15** (lecture 1–14), projets H3/Ref2V **14** (lecture 1–13). Sélecteur/contrôles dédiés dans les deux ateliers, cache core/H3/Ref2V/render incrémenté. Tests hors-ligne et DOM préparés (`test_sensual_cinematic`, `test_sensual_controls_browser`) avec régressions de schéma existantes actualisées. Contrôles statiques réussis : AST Python, JSON et `git diff --check` ; Node indisponible, donc syntaxe JS non contrôlée par Node. **Aucun test, import applicatif de vérification, LLM, rendu, navigateur, service ou redémarrage exécuté.** Patch local non committé/poussé.

- **Analyse média : récupération JSON ciblée, 11 septembre 2026**. Autorisation utilisateur après diagnostic sans modification du rejet `llm-79b7038e6cef4bd29d7109070847bf63` (13:06 UTC, 10 captures, fin normale) : crochet final `]` absent dans `uncertainties`. `media_analysis.parse_result` récupère seulement ce caractère devant l’accolade finale quand les trois champs exacts, sans doublon, et toutes les validations habituelles sont respectés ; `uncertainties` doit être le dernier champ. Aucun texte inventé, autre erreur/troncature refusée, réponse brute LLM préservée, journal de récupération avec `call_id`. Service garde un seul appel et ses contrats de sauvegarde/reprise. Tests neutres préparés, non exécutés ; contrôles statiques uniquement. Aucun runtime, modèle, transcription, rendu ou service modifié/lancé, aucun redémarrage. Interface/prompts inchangés, pas de cache à incrémenter. Guide `docs/media-analysis-json-recovery-2026-09-11.md`. Version de livraison GitHub `snapshot-media-analysis-json-2026-09-11`, branche `snapshots/media-analysis-json-2026-09-11` ; socle antérieur enregistré séparément dans `9c70b51`, puis commit du correctif. Anciens tags conservés.

- **Erreur Writer `phases2` corrigée, 11 septembre 2026**. Dernier rejet `llm-795cf8d48b2e47ba90dad84884612282`, 12:59:45 UTC : JSON reçu avec un seul plan mais `phases: [texte 1]` et clé inventée `phases2: [texte 2]`. Le Plan `llm-37bfa3830b1e4fa58ae6aedc80e5bc90` est accepté, un plan à deux phases ; le squelette/schéma précédent était bien fourni. Erreur primaire extra_forbidden ; tableau vide = conséquence. `classic_cinematic.compile_result` normalise cette écriture avant Writer uniquement avec correspondance exacte au Plan (deux listes singleton de chaînes non vides, deux phases attendues, pas d’autre clé). Aucun mot supprimé/réécrit ni clé arbitraire tolérée, validations caméra/paroles et structure préservées ; cas ambigus restent rejetés. Schéma et squelette clarifient la clé unique `phases`. Tests neutres H3/REF2V mono/multi, immutabilité et rejets ajoutés, non exécutés ; syntaxe/diff seulement. Combat, parcours deux appels, sources de prompt historiques, paramètres/rendus inchangés. Aucun runtime, modèle, LLM, navigateur, test, import applicatif ou redémarrage exécuté/modifié ; pas de publication Git. Guide `docs/h3-turbo-history-lora-writer-2026-09-11.md` complété.

- **Navigation persistante et aperçus vidéo des fiches LoRA, 11 septembre 2026**. Refresh revenait au HTML par défaut ; `lab-core.js` mémorise maintenant section/sous-onglet dans `sessionStorage` (`panelforge.lab.last-view.v1`), par onglet, restauration de visibilité avant scripts puis activation du seul sous-onglet différé à DOMContentLoaded. Pas de découverte H3/REF2V supplémentaire ; clé invalide/stockage bloqué gérés. Conservation de page seulement, pas des brouillons/fichiers de travail. Lecture seule de `workspace/h3_lora_resources.json` : quatre fiches, dix URL MP4 déjà présentes mais affichées en `<img>`. Fiche partagée KREA2/H3/REF2V corrigée : lecteurs vidéo sur extensions reconnues, images conservées, commandes natives, muet initialement, sans autoplay, preload metadata, arrêt/libération à fermeture, erreur visible et lien direct. Anciennes URL/sidecars réutilisées, aucune migration ni récupération distante nécessaire. Cache CSS/core/resource-ui **20260911.4**, rechargement complet suffisant ; aucun restart serveur pour ce patch statique. Tests navigateur navigation/reload/aperçus préparés, attentes cache actualisées ; syntaxe Python/JS/HTML/diff contrôlée, **tests non exécutés**. Aucun LLM, rendu, import applicatif, navigateur, média distant ou service lancé/modifié, aucune publication Git. Guide `docs/navigation-resource-previews-2026-09-11.md`.

- **EROS Turbo ajouté au catalogue H3/REF2V, 11 septembre 2026**. Suite au modèle invisible, lecture seule de `http://bucket:8188/object_info/UNETLoader` : `10Eros_Max_h3_TURBO-hybrid_beta5.safetensors` est bien installé, à côté de `10Eros_Max_h3_hybrid_beta5.safetensors`. L’entrée manquait dans `infrastructure/presets/h3_checkpoints.json` ; ajout exact pour `h3-base` et `ref2va`, libellé « EROS · Turbo intégré · hybride beta5 ». Défauts, chargement direct, autres entrées, LoRA et sampling inchangés ; Turbo externe BUNNY à décocher explicitement. Catalogue chargé au démarrage : l’utilisateur redémarre le Lab après ses traitements, puis actualise la liste ; aucun redémarrage de ComfyUI nécessaire pour ce correctif. Test inventaire/cache/absence préparé, non exécuté ; contrôles statiques uniquement. Pas d’appel LLM, génération, import applicatif de vérification, mutation runtime ou publication Git. Guide `docs/h3-checkpoint-selection-proposal.md` actualisé.

- **H3/REF2V Turbo, historique, fiches LoRA et Writer — 11 septembre 2026**. Option « Ajouter le Turbo BUNNY » visible directement sous la recette, activée par défaut ; désactivation conserve les steps pour les checkpoints avec Turbo intégré. Steps/preview repliés, choix explicites 9/4/5 ou 30/25/5 indépendants, reprise/brouillons conservés. Aucun graphe/contrat de rendu changé. Les derniers projets `h3-render-8a977e6eeaaf47a5a7f98487999d980b` et `h3-render-f312d533fe8d4cdcb92bc5a6ec0f93b8` existent et contiennent des succès : l’historique excluait les profils `minimax.h3.*.classic.cinematic`, désormais inclus dans H3 et REF2V ; transfert Analyse média non responsable. Boutons « i » sur chaque LoRA vidéo, y compris anciennes recettes : fiche KREA réutilisée, notes/favoris/aperçus/CivitAI, catalogue H3 injecté à inventaire existant et stockage distinct `h3_lora_resources.json`, aucune recherche avant le clic et aucun effet sur les forces/ordre/prompt. Trois nouveaux rejets Writer `llm-1b9f09b3807542a69615840ea9d2aec9`, `llm-56633c951cb1493a882d93cfc9a0a9c0`, `llm-ac3cd46952a24d27b3228532ae9bac17` : un plan approuvé à deux phases rédigé comme deux plans à une phase. Classique seulement : schéma et squelette Writer bornés au Plan approuvé, regroupement local de ce seul cas un-plan/deux-phases sans changer les paragraphes ; validations caméra/langue/contenu maintenues, deux appels, Combat inchangé. Cache des JS/CSS concernés **20260911.3**. Guide `docs/h3-turbo-history-lora-writer-2026-09-11.md` ; tests préparés non exécutés, contrôles statiques seulement. Aucun modèle, transcription, rendu, test, import applicatif, navigateur ou redémarrage lancé, aucun runtime existant réécrit, aucune publication Git.

- **Correctifs Analyse média / H3 Classique, 11 septembre 2026**. Lecture seule des deux derniers échecs Plan `llm-6658345f33f143a69879619fb06dd1a9` et `llm-07f29e7459624e639226a3c605949911` : JSON reçu, `<d>` sans langue dans les deux ; seconde erreur supplémentaire = faux positif sur `rather than any camera motion`. Contrat Classique renforcé avec `spoken_languages` explicite dans les nouveaux schémas, champ facultatif au chargement des anciens Plans. Complétion locale d’une langue manquante uniquement pour les mots exacts dont la langue est déclarée ou déjà balisée dans le Plan ; pas de supposition/traduction/ajout ; contradictions rejetées. Writer reprend ces langues ; parcours reste deux appels. Validateur caméra commun tolère les mentions d’absence de mouvement, garde les vrais mouvements libres rejetés ; adoption générale examinée pour Classique ET Combat, schéma/politique Combat non modifiés. Analyse média passe aux consignes **1.0.1 / 1.1.1**, anciennes sources conservées : numéros de captures uniquement dans observations/incertitudes ; nettoyage local des citations parenthétiques, quotes préservées, renvois intégrés laissés éditables avec avertissement et bloqués avant transfert tant que non reformulés. Anciennes intentions nettoyées à l’enregistrement/transfert explicite ; navigateur transmet le texte retourné par le serveur, aucun atelier existant réécrit. Cache média **20260911.2**. Guide `docs/media-h3-boundary-fixes-2026-09-11.md`, tests neutres préparés **non exécutés** ; vérifications statiques seulement. Aucun runtime modifié, test, LLM, rendu, navigateur, import applicatif ou redémarrage lancé ; pas de publication Git. CPU audio par défaut préservé ; priorité à l’action reste en discussion.

- **Transcription locale Analyse média implémentée, 10–11 septembre 2026** : sur autorisation, option vidéo « Transcrire les paroles », anglais par défaut / langues modifiables / auto, large-v3-turbo réutilisé depuis Subtitle Edit via CLI. **CPU par défaut demandé expressément le 11 septembre après retour utilisateur sur un échec GPU**, GPU encore sélectionnable ; aucune cause GPU affirmée sans diagnostic. Paroles horodatées corrigibles/restaurables, option distincte conserver les répliques (off), intention française avec répliques originales seulement si demandées. Extrait/langue changés rendent le brouillon audio ancien ; le désactiver garde les corrections et autorise l’analyse visuelle. Schéma analyse 2 compatible 1, original/segments/corrections/langue/device/options sauvegardés avec analyse, réouverture sans retranscrire. Prompt audio isolé `media.visual-intention@1.1.0`, **sans audio prompt 1.0 inchangé**, seul texte corrigé fourni au LLM. Service/adaptateur injectés et module JS audio distincts ; upload vidéo temporaire max 1 Gio, extraction WAV du seul extrait, processus ponctuel/annulable, nettoyage sur issue normale, aucun appel LLM/rendu ni arrêt des autres services. Configuration `PANELFORGE_WHISPER_ROOT` facultative, défaut dossier `%APPDATA%/Subtitle Edit/SpeechToText/Purfview-Faster-Whisper-XXL`. Cache CSS/audio/intégration **20260911.1**. Guide `docs/media-analysis-speech-1.1.md`, tests backend/DOM préparés, **non exécutés** ; contrôles statiques uniquement. Aucun moteur Whisper/ffmpeg, LLM, rendu, navigateur, redémarrage ou opération Git de publication lancé par l’agent.

- **Discussion priorité à l’action dans l’intention, 11 septembre 2026** : utilisateur juge l’analyse trop descriptive quand une first frame ou des références existent déjà ; il veut discuter et essayer la sortie actuelle avant décision. Proposition : choix facultatif avant analyse « Décrire toute la scène / Guider l’action à partir de mes images », actions/transformations/caméra/rythme prioritaires en I2V, descriptions conservées quand pertinentes. En REF2V, références d’identité seules ne définissent pas nécessairement le décor. Les références de génération sont actuellement choisies après analyse : ne pas supposer que le LLM les connaît. **Ne pas implémenter cette évolution sans validation**, ne pas changer les prompts Classique/Combat. Le patch audio autorisé continue indépendamment de cette discussion.

- **Discussion transcription locale pour Analyse média, 2026-09-10** : l’utilisateur a testé V1 (« marche pas mal ») et souhaite discuter d’une option speech-to-text comparable à Subtitle Edit, sans autorisation d’implémentation à ce stade. Vérification en lecture seule : `C:\Users\samue\AppData\Roaming\Subtitle Edit\SpeechToText\Purfview-Faster-Whisper-XXL\faster-whisper-xxl.exe`, ffmpeg et `_models\faster-whisper-large-v3-turbo\model.bin` présents. Le dépôt officiel Purfview confirme l’usage CLI indépendant de Subtitle Edit. Proposition : bloc Audio facultatif dans l’analyse vidéo, transcription du seul extrait choisi, anglais par défaut comme la capture (langue modifiable, traduction désactivée), texte horodaté corrigeable avant analyse. Intention française et paroles originales séparées ; distinguer comprendre le contexte et demander de reproduire les répliques, sans attribution inventée aux personnages ni promesse d’analyse des bruitages/musiques. Processus STT ponctuel terminé avant l’appel visuel, sans déchargement automatique d’Unsloth/ComfyUI ; option CPU envisageable. V1 ne transfère actuellement que des captures : transport audio/vidéo temporaire et extraction restent à concevoir. Aucun exécutable, transcription, test, modèle ou service lancé ; aucune modification du code.

- **Analyse média V1 implémentée sur autorisation, 2026-09-10**. Video Lab → Analyser des médias : import vidéo ou 1–16 images, extrait 0,1–60 s avec deux poignées/champs début-fin et lecture limitée, 8 captures par défaut (2–16) ajustables avec ajout au curseur/retrait ; images ajoutables/réordonnables et temps facultatifs, repères conservés au déplacement, conflits signalés. Durée cible **5–15 s**, alignée sur les rendus actuels, distincte de l’extrait ; changement d’entrées marque le résultat ancien. Texte français facultatif → un appel multimodal `media.visual-intention@1.0.0` → intention française éditable + observations/incertitudes. Références de génération choisies séparément, propres images possibles ; préremplissage H3/REF2V sans génération automatique, brouillon/préparation cible protégés. Service/route/stockage isolés, Pillow injecté pour validation/orientation et copies LLM 1280 px ; images originales conservées, vidéo entière non uploadée. Stockage `workspace/media_analysis` schéma 1 (sources/temps/version/appel/intention générée et éditée), trois analyses récentes à chargement différé ; rouvrir une vidéo restaure ses captures, changer l’extrait demande resélection du fichier local. Reprise d’un même identifiant sans doubler un succès, erreurs/annulation conservent les entrées. Aucune modification des recettes Classique/Combat ou des réglages de rendu ; pas de migration des projets. Tests `test_media_analysis` / `test_media_analysis_browser` préparés, attentes de cache actualisées, **non exécutés**. Contrôles statiques uniquement ; cache UI **20260910.11**. Guide `docs/media-analysis-1.0.md`, backlog actualisé. Aucun LLM/rendu/navigateur/import applicatif de vérification/redémarrage ni commit/push/tag ; patchs précédents préservés. Qualité d’analyse et lecture des codecs à expérimenter par l’utilisateur. Sensualité reste différé. Les entrées suivantes retracent l’alignement antérieur à cette autorisation.

- **Dernier alignement Analyse média, 2026-09-10** : utilisateur confirme la sélection d’un extrait vidéo avec sélecteur et demande des temps facultatifs par image (0 s / 1 s / 3 s), tout en conservant le réordonnancement. Parcours convenu : Video Lab → médias + texte français facultatif → analyse → intention française éditable → ateliers H3/REF2V existants, références choisies séparément. Détails proposés : plage vidéo début/fin avec poignées et valeurs, lecture de l’extrait, captures limitées à cette plage, chronologie d’intention relative à zéro ; temps liés aux images, conservés au déplacement avec signalement des incohérences, sans minutage inventé pour les cases vides. Durée cible modifiable et distincte du dernier repère. `docs/backlog.md` actualisé. **Alignement uniquement**, aucun code, test, LLM, génération, runtime ou service modifié/lancé ; attendre une autorisation explicite d’implémenter.

- **Alignement analyse vidéo/images repris, 2026-09-10** : l’utilisateur bifurque depuis Sensualité vers import d’images OU vidéo + texte d’intention facultatif en français, intention ensuite transmise à H3/REF2V. Discussion uniquement. Proposition actualisée dans `docs/backlog.md` : espace Video Lab, intention française éditable en sortie d’analyse, puis préremplissage des ateliers existants pour leur préparation et rendu habituels. L’ancienne proposition de deux appels avec compilation directe vers le prompt final n’est pas un choix validé ; nombre d’appels d’analyse à cadrer. Distinguer médias observés et références choisies pour génération, fidélité proposée sans texte / adaptations explicites avec texte ; extrait vidéo sélectionnable et images réordonnables. Propositions V1 : visuel seulement, captures horodatées ajustables, durée cible cohérente, aucune génération automatique. Sensualité reste différé. Aucun code, test, LLM, rendu, service ou runtime modifié ; documentation seulement, attendre validation du périmètre et autorisation d’implémenter.

- **Discussion Sensualité : lecture du dernier prompt, 2026-09-10**. Atelier `h3-render-94ac1444ec4143149aff5e94c889b285`, session `prompt-63697ff45ee241fb83c48aa481b0d241` : utilise Classique Mise en scène 1.0, I2VA, un plan, pas de famille Sensualité implémentée. Intention, composition et dernière révision consultées en lecture seule ; aucune vidéo visionnée. Texte sexuellement explicite : analyse structurelle non graphique et piste adulte non explicite uniquement, sans optimisation de la partie explicite. Constats : durée du texte 8 s contre réglage de rendu 6 s dans les deux derniers essais ; geste répété à la jonction des phases, posture debout répétée dans la dernière révision ; ouverture caméra fixe puis inclinaison lente, succession à mieux expliciter ; jeu d'acteur surtout décrit par des sourires génériques. Audace/caméra/mouvements/vie à 3, liberté 90. Direction proposée pour le futur mode non explicite : deux appels, plan de jeu d'acteur puis rédaction, progression émotionnelle observable et quelques gestes lisibles, nombre de plans indépendant. **Discussion uniquement**, aucun code, runtime, test, LLM, rendu ou service modifié/lancé ; chantier Sensualité reste en backlog sans autorisation d'implémentation.

- **Quatre LoRA H3/REF2V implémentés sur demande, 2026-09-10** : recettes **H3 0.1.6 / REF2V 0.2.4 / BUNNY 0.1.3**, contrat `H3VideoLoraStack@0.2.0`, maximum quatre fichiers distincts. Anciennes recettes et contrat 0.1.0 conservent deux emplacements. Ajout à la demande, compteur et flèches ↑/↓ par ligne dans le bloc existant ; déplacement conjoint fichier/forces/activation, restauration sans troncature, pas de reconstruction au polling. Basique Standard et MP/seed inchangés ; BUNNY garde Combat V2 → Motion Repair à 0,60/0,20 chacun, deux ajouts facultatifs. Chaînes MODEL indépendantes dans les deux passes, ordre identique et huit forces possibles ; Turbo/preview/checkpoint/sampling inchangés. IDs dans les nouveaux manifests, graphes de base identiques aux versions précédentes. Limite vérifiée dans API/service/compilation avant soumission, ressources actives validées ; stockage H3/REF2V reste schéma 13, pas de migration. Cache `h3-loras.js` **20260910.10**. Guide `docs/h3-four-loras.md`, tests dédiés Python/navigateur préparés, **non exécutés** ; contrôles statiques uniquement. Aucun LLM/rendu/import applicatif de vérification/redémarrage ni commit/push ; patch Classique précédent préservé, snapshots GitHub intacts.

- **Classique Mise en scène 1.0 implémenté sur autorisation, 2026-09-10**. Point GitHub publié AVANT le patch : commit `2b68523`, tag `snapshot-avant-classique-cinematique-2026-09-10`, branche `snapshots/avant-classique-cinematique-2026-09-10` sur `EasyFrag/panelforge`. Branche de travail `h3-video-lora`, checkout `D:\Code\localQ\.panelpatch` ; tags antérieurs intacts. Nouvelle option Version Classique dans H3/REF2V : Mise en scène 1.0, expérimental, deux appels Plan puis Writer. Nombre de plans Auto par défaut / 1–6, choix manuel prioritaire. Contrat propre `minimax.h3.classic.cinematic_planned_v1`, préparation `classic@1.0.0`, consignes/exemples propres sans politique Combat. Compilation neutre `cinematic_core_v1@1.0.0` extraite explicitement du comportement Combat 1.3, qui garde ses contrats/politiques. Une ou deux phases continues facultatives par plan ; cadrages, rythme, états et raccords conservés par compilation. `cinematic_settings` distinct de Combat et conservé dans session, fork, rendu, révision, conversion H3→REF2V et continuation. Révision de rendu Classique cinématique `0.4.0` propre. Sessions schéma **14** (lecture 1–13), projets H3/REF2V **13** (lecture 1–12), aucun atelier utilisateur migré. Anciennes recettes/parcours/défauts MP/seed/checkpoints/LoRA/rendu inchangés ; 591 empreintes de prompts/profils/recettes antérieurs vérifiées. Tests `test_classic_cinematic` et `test_classic_cinematic_browser` préparés, anciens tests de schéma/cache ajustés ; **aucun test exécuté**, import applicatif de vérification, appel LLM, rendu ou redémarrage. Contrôles statiques Python/JS/JSON/blocs/HTML/empreintes/diff réussis. Caches JS modifiés **20260910.9**. Guide `docs/h3-classic-cinematic-1.0.md`, backlog actualisé. Le patch reste local après le snapshot GitHub demandé ; qualité à expérimenter par l’utilisateur. Analyse média et Sensualité restent en backlog.

- **Classique expérimental en deux étapes : discussion antérieure, mise en œuvre dans l’entrée ci-dessus**. L’utilisateur met en attente les deux chantiers analyse vidéo/images et Sensualité / jeu d’acteur non explicite, puis demande si l’approche Combat à deux appels mérite une version expérimentale Classique et si le nombre de plans devrait rester dans l’intention. Manifests relus : Classique propose déjà H3 mono planned 1.2.0 / REF2V mono planned 1.1.0 / H3 multi planned 1.1.0 en deux appels. Proposition : adapter surtout le Plan de mise en scène et la transmission au rédacteur de Combat 1.3, avec politiques/exemples Classique propres et socle neutre à versions exactes ; ne pas attribuer le gain au seul nombre d’appels. Entrée expérimentale distincte, deux appels initiaux seulement, anciens 1/2/3 et défauts conservés. Petit contrôle nombre de plans Auto / 1–6 proposé : Auto suit l’intention explicite sinon laisse le Plan choisir ; sélection manuelle prioritaire et visible. Actions et coupes indépendantes ; scène calme possible, pas d’intensité Combat imposée. Documentation `docs/backlog.md`. Cette entrée retrace la proposition avant autorisation ; l’implémentation est décrite ci-dessus. L’entrée suivante décrit le chantier analyse média, remis en backlog.

- **Analyse vidéo/images → prompt H3 : discussion active, 2026-09-10**. L’utilisateur remet ce P1 au premier plan, souhaite importer une vidéo ou plusieurs frames, propose Video Lab et demande une vision de l’outil ; **pas d’autorisation d’implémenter à ce stade**. Code relu : Video Lab contient déjà Générer une vidéo / Texte Instagram ; Social Lab extrait quatre frames via Canvas/seek navigateur. Proposition : troisième sous-onglet à chargement différé, import/extrait court, lecteur + frise horodatée modifiable ; images seules réordonnables avec durée cible. Un bouton, deux appels proposés (observation chronologique puis rédaction/compilation H3/REF2V), synthèse corrigible et prompt éditable/conversation visible, transfert dans les ateliers existants sans Brief/Plan redondants ni rendu automatique. Distinguer images analysées et références effectives ; les états intermédiaires/sons non observés ne sont pas des faits. Fidélité par défaut, consigne d’adaptation facultative ; nombre de captures ajustable aux actions/coupes. Détails dans `docs/backlog.md`. **Sensualité / jeu d’acteur non explicite différé expressément**, sans travail fonctionnel. Ce tour ne modifie que la documentation ; aucun test, appel LLM, rendu, import applicatif ou redémarrage.

- **Deux LoRA H3/REF2V implémentés sur autorisation, 2026-09-10** : nouvelles recettes **H3 0.1.5 / REF2V 0.2.3 / BUNNY 0.1.2** ; anciennes versions toujours disponibles, VideoLab indépendant inchangé en 0.2.1. BUNNY propose **Combat V2 puis Motion Repair**, chacun **0,60 en passe 1 / 0,20 en passe 2**, quatre forces indépendantes. Chaque branche MODEL repart de la source checkpoint/Turbo commune et applique les deux fichiers dans le même ordre ; seul le latent poursuit son parcours entre passes. Turbo/schedules/preview/EROS inchangés. Basique conserve Standard, seed coché et MP initiaux/après upscale 0,2/0,2 modifiables ; jusqu’à deux entrées facultatives dans le chargeur existant, une force par fichier, CLIP commun. Aucun changement de politique ou de version de prompt Combat/Classique.

- **Contrat et interface des deux LoRA** : `H3VideoLoraStack@0.1.0`, maximum deux fichiers distincts, activation globale/par ligne, quatre forces BUNNY ou deux forces basiques ; IDs de câblage dans les nouveaux manifests. Schéma H3 **12**, lecture **1–12**, pas de migration runtime. Ancien `video_lora` accepté seul ; `video_loras` fait autorité pour les nouvelles sélections, y compris seconde passe (ancien `bunny.lora_second_strength` conservé pour compatibilité). Ordre/activation/forces transmis dans historique/reprise/réouverture/feedback/conversion/DLSS. Module `h3-loras.js` dans le bloc existant : champs numériques, ajouter/retirer/désactiver/inverser, refresh explicite ; brouillons par recette, pas de reconstruction des lignes au polling. Inventaire partagé en cache 60 s / erreurs 5 s via transport runtime court ; validation hors verrou avant création puis avant upload, absent = erreur sans remplacement. Lignes désactivées sans dépendance au fichier.

- **Livraison des deux LoRA** : tests `test_h3_multiple_loras` et scénario navigateur BUNNY/H3/REF2V préparés, attentes d’assemblage/schéma/cache actualisées, **non exécutés**. Contrôles AST Python, syntaxe JS/scénarios sans invocation, imports internes statiques, JSON/hashes/bindings/IDs HTML et diff. Graphes API de base identiques aux versions précédentes ; anciens fichiers de workflows et de prompts inchangés. Cache UI modifiée **20260910.8**. Guide et commande utilisateur : `docs/h3-multiple-loras-proposal.md`. Aucun test, import applicatif de vérification, LLM, génération, service, workspace utilisateur, commit/push/tag modifié/lancé. Qualité/vitesse réelles de la paire et réglages à expérimenter par l’utilisateur. L’entrée de discussion ci-dessous décrit l’état antérieur à l’autorisation, désormais reçue et appliquée.

- **Deux LoRA H3/REF2V à aligner, 2026-09-10, discussion uniquement** : utilisateur demande maximum deux fichiers ; BUNNY par défaut Combat V2 puis « Better Motion », et confirme que ce dernier est **Motion Repair**. GET inventaire Bucket : `minmax_nsfw/H3_Combat_V2.safetensors` et `minmax_nsfw/Motion_Repair.safetensors` présents. Anciens JSON BUNNY non suffixé/(1)/(2) : Weapon `jiandou` puis Motion dans CHAQUE branche ; valeurs réelles Weapon **0,85/0,50**, titres **0,50/0,30** non concordants ; Motion **0,60/0,20**, bypass dans ces trois fichiers. Dernier (3) API et intégration actuelle : Motion seul actif **0,60/0,20**. Fiche auteur Motion relue : accompagnement Combat passe 1 0,5–0,7, passe 2 0,2–0,3 ; trop de Motion en passe 2 peut réduire l'impact/vitesse. Pas de forces spécifiques deux passes Combat V2 trouvées dans README/API consultés. Proposition **non encore validée** : deux fichiers, quatre forces BUNNY ; Combat V2 **0,60/0,20** pour conserver le point de départ actuel et Motion **0,60/0,20**. Chaque branche repart du checkpoint/Turbo commun, Combat puis Motion ; pas de cumul des patches de première passe dans le modèle de seconde passe. Turbo reste séparé. Basique : Standard/défauts actuels, une force par LoRA, ajouter deux entrées dans le Power Lora Loader existant ; CLIP unique, aucune nouvelle colonne de passes. UX même bloc, deux lignes compactes, Ajouter/activer/inverser, BUNNY prérempli aux nouveaux réglages seulement. Anciennes reprises et familles de prompts isolées, ordre/poids/activation enregistrés. Guide `docs/h3-multiple-loras-proposal.md`. **Aucun patch fonctionnel autorisé/lancé dans ce tour** ; documentation seule, aucun test/LLM/rendu/service/poids/runtime modifié, aucun commit/tag. Attendre l'alignement puis l'autorisation d'implémenter.

- **Checkpoints H3/REF2V implémentés sur autorisation, 2026-09-10** : ligne repliable **Modèle vidéo · Par défaut** sous la recette de rendu. Catalogue explicite des H3 reconnus croisé avec les modèles Bucket ; EROS `10Eros_Max_h3_hybrid_beta5.safetensors` en chargement direct, sans réassemblage REF2VA, y compris BUNNY. Défauts, MP, seed, LoRA, Turbo, preview et prompts/familles Combat/Classique conservés. Nouvelles recettes **H3 0.1.4 / REF2V 0.2.2 / BUNNY 0.1.1** ; graphes API identiques octet par octet aux anciennes versions, source alternative pilotée par leurs manifests. Anciennes recettes disponibles et restaurées exactement, sans sélecteur alternatif : choisir la recette actuelle pour tester EROS dans un ancien atelier. VideoLab indépendant reste 0.2.1. Checkpoint/chargement effectif enregistrés dans essais, reprises, conversion compatible et provenance DLSS ; brouillons de l'onglet par recette. Schéma H3 **11**, lecture 1–10, aucune migration runtime. Inventaire en cache 60 s, lecture différée à l'ouverture du sélecteur ou au choix alternatif, refresh explicite, erreurs 5 s ; aucune nouvelle requête pour défaut/polling. Validation avant création hors verrou de rendu, puis avant upload à l'exécution ; absent/incompatible = erreur sans repli. UI garde la sélection en cas d'échec, historique montre les modèles effectifs. Tests `test_h3_checkpoints`, navigateur BUNNY/H3/REF2V et attentes d'assemblage/schema/cache préparés **non exécutés**. AST/JS sans invocation/JSON/hash/bindings/diff contrôlés. Caches JS rendu/sélecteur et CSS **20260910.7**. Guide `docs/h3-checkpoint-selection-proposal.md` actualisé. Aucun appel LLM, rendu, redémarrage, import applicatif de vérification, modification de workspace utilisateur, commit/push/tag. Qualité EROS et deux passes à tester par l'utilisateur. L'entrée d'analyse suivante décrit l'état antérieur à cette autorisation.

- **Choix de checkpoint H3/REF2V étudié, 2026-09-10, discussion sans patch fonctionnel** : demande de tester EROS sans surcharger l’interface, défauts actuels à conserver. Deux lectures GET de l’inventaire Bucket (`object_info/UNETLoader`, `MiniMaxH3HybridLoader`) : **`10Eros_Max_h3_hybrid_beta5.safetensors` présent**, avec PinkCherry FL2VA et MiniMaxREDMix notamment ; aucun EROS-TURBO nommé dans la liste de 78 modèles. README/fichier publiés TenStrip consultés : beta5 distingue non-Turbo et TURBO intégré ; hybride construit sur delta1024. Poids non ouverts/vérifiés/exécutés. Code lu : H3 courant FL2VA BF16 seul, REF2V courant assemblage FL2VA + AdaLN REF2VA blocs 25–49 ; BUNNY emploie les mêmes branches selon le mode. Pour un test EROS pur, proposer un chargement direct de l’hybride, sans le réassembler avec le REF2VA d’origine. UX proposée : une ligne repliable **Modèle vidéo · Par défaut/EROS**, sous la recette de rendu ; un sélecteur de checkpoints H3 reconnus/installés, pas les 78 UNET. Défaut par recette, choix par prochain essai, visible dans résumé/historique et repris dans réglages/réouverture/conversion compatible ; modèles/chargement effectifs enregistrés, validation sans repli silencieux. Inventaire en cache, pas de scan au polling. Aucun changement de prompt, famille Combat/Classique, seed, MP, LoRA ou Turbo implicite ; EROS non-Turbo et Turbo externe BUNNY à distinguer. Spectrum déjà désactivé sur REF2V, non supporté en BUNNY ; auteur le déconseille en référence. Proposition `docs/h3-checkpoint-selection-proposal.md`. **Aucun code fonctionnel, test, LLM, rendu, service, workspace utilisateur, commit ou tag modifié/lancé** ; documentation seulement. Attendre l’accord sur cette approche avant le patch de sélection.

- **Combat 1.3.0 implémenté sur autorisation, 2026-09-10 — deux appels uniquement** : dernière demande « Va y tu peux implémenter; reste sur 2 appels uniquement pour le moment » appliquée à H3 et REF2V. Deux nouvelles recettes `.combat.planned@1.3.0` et leurs profils, Plan puis Writer ; aucun Brief ni appel caché. Anciennes versions et leurs parcours 1/2/3 conservés, Classique isolé, **583 empreintes de prompts/profils antérieurs inchangées**. Nouvelle orientation **Pouvoirs / magie**, recalibrage Déchaîné vers vitesse/amplitude/traversées/ripostes dans le genre, quatre niveaux et nombre de plans indépendants. Cinq exemples locaux complets (pouvoirs, armes lourdes, armes rapides sans magie, fantasy aérienne, corps à corps), sélection déterministe orientation/mots explicites/niveau ; pas de classificateur LLM. Nouveau contrat `minimax.h3.combat.cinematic_planned_v1` : 1–6 plans, 1–2 phases continues par plan, caméra mouvement/vitesse/amplitude/cible, minimum 500 ms par phase, maximum 12 clauses seulement en 1.3. Compilation insère cadrage, événements de phase, rythme, état final et raccord du Plan dans leur plan ; Writer rend un paragraphe d’action par phase. Validation du Plan exerce localement le même compilateur avant approbation, sans LLM. Consignes/schema anglais de tous les champs compilés, attribution explicite des attaques, identité/morphologie protégées ; pas de détecteur/traducteur automatique. Révisions, conversion, continuation/fork et stockage adaptés aux phases (phase continue sans timestamp distincte d’une coupe), zéro changement de workflow/rendu/seed/MP/LoRA. Sessions schéma **13** (lecture 1–12), projets H3 **10** (lecture 1–9), caches quatre JS **20260910.6**, socle inchangé .5. Guide `docs/h3-combat-1.3.md`, proposition actualisée, tests `test_combat_cinematic` et régressions navigateur/stockage préparés **non exécutés**. Vérifications statiques AST, JS sans invocation, manifests/liens/empreintes/HTML/diff ; aucun import applicatif de vérification, appel LLM, génération, redémarrage, modification du workspace utilisateur, commit/push/tag. Qualité de Qwen et fidélité vidéo à expérimenter par l’utilisateur. Les entrées d’analyse précédentes ci-dessous décrivent l’état avant cette autorisation ; les parcours 1/3 appels en 1.3 restent différés.

- **Recul sur direction cinématographique Combat, 2026-09-10, analyse sans implémentation** : quatre nouveaux TXT joints lus entièrement (médiéval 5 390 caractères, sabres lumineux 6 888, exécution 6 116, hache/épée 5 325) et exemple chinois inline examiné. Leurs leviers diffèrent : combinaisons/repères/raccords, inertie lourde, rotations et densité, impact dramatique/POV, vitesse aérienne/portée magique. Pas une simple échelle de coups ni de violence ; pas de vidéos associées inspectées. **Limite structurelle confirmée** : Combat ne fournit au schéma que `camera_motion` et compile une directive sans cible/vitesse/amplitude, pourtant déjà disponibles dans le domaine commun. Pas de phases caméra, une clause par plan, maximum huit dans stockage/révision ; mouvements libres refusés dans la prose. L'intention « orbit then dive » ne peut donc pas être fidèlement exprimée par les seuls prompts actuels. Proposition documentée dans `docs/combat-cinematic-direction-proposal.md` : Combat 1.3 comme direction complète (chorégraphie, pouvoirs, rythme, caméra, raccords), quelques exemples intention→sortie conformes choisis par orientation/niveau, vrai contraste Intense/Déchaîné, anglais de tous les champs compilés. Exploiter d'abord les paramètres caméra existants puis contrat propre avec courtes phases continues motivées, cibles et raccords préservés de bout en bout ; compter les vraies coupes, certains Shot des exemples en contiennent plusieurs. Garder 1/2/3 appels sans passe cachée ; deux appels utiles pour calibrer, trois avec Brief centré sur arc/identités/genre sans dupliquer toute la chorégraphie. Orientation magie acceptée, maximum renforcé selon genre, contrôles indépendants, anciennes versions/Classique isolés. Distinguer sortie Qwen, compilation et rendu dans les comparaisons à paramètres constants ; pas de gain garanti ni de changement de modèle/température/LoRA présumé nécessaire. **Demande actuelle de prise de recul, documentation uniquement** ; aucun code fonctionnel, test, LLM, génération ou service modifié/lancé. Le prochain patch doit être cadré autour de ce contrat et des exemples, pas limité à quelques adjectifs d'intensité.

- **Déchaîné jugé trop timide / orientation magie approuvée dans son principe, 2026-09-10** : l'utilisateur compare au prompt de combat chinois extrême joint (`attachments/5fe1200d-83db-4070-8c36-2bdbb2960497/pasted-text.txt`, 6 286 caractères, lu entièrement). Exemple : héroïne au tachi, 15 s / six plans, accélération initiale, traversées très rapides, esquives frôlantes, trois frappes liées, départ aérien et tempête de qi, changements d'appui/direction sur les murs, trajectoires à travers une formation et attaque d'énergie de très grande portée. Alternance de ralentis/accélérations et impacts, puis dernier plan de 3 s avec atterrissage et menace ; l'intensité demandée repose sur vitesse/amplitude/échelle/contrastes autant que sur quantité. Texte étudié, pas de vidéo associée inspectée ni de benchmark. Nos définitions Intense/Déchaîné restent trop voisines : davantage de combinaisons/poursuite sans directives fortes de rupture de vitesse, grande amplitude et usage dominant des pouvoirs ; exemples martiaux communs persistants. Direction proposée pour une future **Combat 1.3.0** : conserver quatre niveaux, différencier nettement le maximum par rythme, amplitude, traversées et enchaînements ambitieux adaptés au genre et à la morphologie ; permettre des trajectoires surhumaines lorsque le genre/l'intention le justifient, conserver origine/cible/conséquence lisibles, sans attribuer automatiquement de nouveaux pouvoirs aux combats réalistes. Orientation **Pouvoirs / magie** ajoutée au sélecteur existant, attaques magiques comme armes principales, compatible avec chaque niveau d'action ; Libre/mixte suit la dominante demandée. Plans/caméra/audace/1–2–3 appels restent indépendants, pas de nouveau curseur ni de quota de coups. En Magie + Déchaîné : salves/gerbes/arcs et esquives à distance, ripostes pendant déplacement, couvert/terrain et conséquences, montées en puissance plutôt que poings lumineux systématiques. Pas de reprise imposée du format six sections, de la durée 15 s, de la foule, de l'issue létale, des cuts internes ou de la pose finale de l'exemple : respecter les choix de l'atelier. Anciennes versions et Classique isolés, réglages de rendu conservés pour de futures comparaisons ; pas de gain vidéo garanti par le texte. Accord utilisateur explicite sur l'idée magie, recalibrage du maximum demandé à discuter ; **aucune implémentation fonctionnelle lancée dans ce tour**, aucun test, LLM, rendu ou service touché. Garder les défauts langue/attribution des attaques/durée et morphologie du diagnostic Pokémon en mémoire pour cadrer le prochain patch.

- **Exploration demandée : combats de pouvoirs, 2026-09-10, discussion sans patch**. L'utilisateur trouve les combats Pokémon/monstres trop au corps à corps et souhaite gerbes de feu, arcs électriques et attaques magiques structurant l'échange. Nouveau run retrouvé : session `prompt-7bf97dd6157a4cd2afe84e125f832e68`, projet `h3-render-5ff32a6a0d95469ca9402c2dcf1bb2ca`, essai `attempt-e97ac7b8bc7647ffbf43baf280be2efc`, **Combat 1.2.0 prompt direct un appel, Libre/mixte, action 3, plans Auto → 3** (coupes 2,8/5,8 s), intention identique et références de mêmes empreintes que le run Pokémon précédent. Durée corrigée à 8 s, nouveau seed ; BUNNY/LoRA 0,6/0,2 inchangés. Rendu achevé pendant la lecture (12:37:52 UTC), six keyframes existantes examinées : davantage d'arc électrique/gerbe de feu en confrontation à distance vers 5,3 s, mais frappes au contact à 3,3 et 6,3 s ; dernière image face-à-face. Pas de lecture vidéo continue ni d'écoute, donc pas de conclusion exhaustive sur le rythme. Prompt anglais cette fois, meilleur avantage initial électrique, mais double-jab, frappe de paume, griffes et saut au contact restent centraux. Flamme sur la crête/tête inventée dans le prompt et visible au rendu, absente de la référence ; distinguer pouvoir et modification morphologique. **Biais de nos consignes** : socle 1.1 réutilisé en 1.2 illustré par parades/prises/épée-bouclier/contacts ; Libre/mixte présente la magie comme prolongement d'une attaque concrète. L'intention conseillée précédemment (« pouvoirs accompagnent les mouvements », « contacts lisibles ») favorise aussi cette interprétation. Hypothèse étayée par le prompt, rôle propre du LoRA non isolé ; plusieurs paramètres de préparation et seed ayant changé, ne pas attribuer le gain à la seule version. Proposition à discuter : quatrième orientation générique **Pouvoirs / magie**, portée et trajectoires, origine/cible/conséquence/réponse explicites, distances intermédiaires et longues, esquives/couverts/contre-sorts/déplacement, morphologie cohérente ; contact ponctuel, pas de quota ni liste de techniques obligatoire. Libre/mixte devrait suivre la dominante demandée ; distinguer causalité lisible et contact obligatoire dans une future version Combat propre, anciennes versions/Classique isolés, sans nouvelle passe LLM ou workflow Pokémon. Essai possible par intention donnant aux pouvoirs le rôle d'armes principales, en gardant les réglages pour comparer. Aucun test, LLM, rendu ou service lancé/modifié par l'agent ; lecture locale et documentation uniquement. L'utilisateur demande d'explorer, pas encore d'implémenter cette orientation.

- **Combat Pokémon examiné, 2026-09-10, avis demandé sans patch** : session `prompt-53d31252e6c14ae59f1b3ebd939c1dd9`, projet `h3-render-5c69f5911aa24949b5034e45c8e29b13`, essai réussi `attempt-0e97930b2d46493f9b862e6309e3fa94`. REF2V Combat **1.1.1 guidé trois appels**, action 3, cinq plans, audace/caméra/vie 3 ; ce run ne teste pas les orientations 1.2. BUNNY turbo 9/4/5, H3_Combat_V2 0,6/0,2, 0,9 MP initial/final, seed conservé. Références Pikachu peint/fourrure et créature de feu rouge en capture basse résolution avec overlay ; originaux et huit keyframes existantes examinés, pas de lecture vidéo continue ni d'écoute. Images : identités reconnaissables, feu plus rond/générique que sa référence ; décor forestier, tronc cassé, rochers et impacts cohérents dans les images observées, contacts partiellement cachés par les effets. Brief/Plan/prompt lus : avantage initial de Pikachu peu concrétisé, Feu contre presque tout ; double-jab de l'Électrique dans le Brief devient ambigu dans le Plan (« épaule du Feu, qui… »), puis attribué au Feu dans le Writer. Mécaniques difficiles à situer (glisser sous une vague de feu au ras du sol, Feu redirigeant l'électricité adverse) ; réinitialisation finale « les deux se relèvent » malgré Feu resté debout. **Défaut de langue confirmé dans l'assemblage** : Plan et `opening_composition` en français, réinjectés tels quels dans les descriptions anglaises du Writer avec les désignations françaises ; le Plan n'impose pas explicitement l'anglais, contrairement au Writer. Le run demande 8 s dans le prompt mais le rendu est réglé 10 s ; lecture CPU ffprobe confirme **736×1280, 24 fps, 10,125 s**. Causalité de ces écarts sur la qualité non démontrée. Priorité proposée : clarifier langue des champs compilés, acteur de chaque attaque, arc tactique et durée cohérente, en conservant richesse/action et réglages pour comparer. Aucun code fonctionnel, prompt sauvegardé, test, LLM, génération ou service modifié/lancé ; documentation seule. Attendre instruction avant un éventuel correctif versionné ; 1.2 n'est pas démontrée comme remède à ces points.

- **Combat 1.2.0 et parcours 1/2/3 implémentés sur autorisation, 2026-09-10** : le filtre `recipeTier` classait 1.1.1 comme historique parce qu'il ne reconnaissait que les versions 1.0/1.1 se terminant par `.0` ; seul le choix actif restait visible. Correction pour toutes les versions Combat installées, toujours filtrées par leur version exacte : les trois parcours H3/REF2V sont visibles en 1.1.1 comme en 1.2.0 sans option archives. Six nouvelles recettes et deux profils 1.2.0 ; orientation **Libre / mixte** par défaut, **Corps à corps**, **Armes**. Blocs compacts dans `application/combat_orientation.py`, transmis aux appels Brief/Plan/Writer/révisions existants, sans appel supplémentaire. Un contre plusieurs conditionnel à l'intention ; suggestion de LoRA uniquement, aucune sélection automatique ni changement de forces/rendu. Orientation enregistrée et conservée dans échanges, révisions après rendu, fork, conversion, continuation et réouverture ; choix verrouillé dans l'atelier créé comme les autres contrôles. Action et nombre de plans restent indépendants. Adoption explicite des protections identité/caméra 1.1.1 et chorégraphie 1.1.0 ; Classique et anciennes versions conservés, **574 empreintes de prompts/profils antérieurs inchangées**. Sessions schéma **12** (lecture 1–11), projets H3/REF2V **9** (lecture 1–8), aucune migration du workspace. Caches des cinq JS **20260910.5**. Guide `docs/h3-combat-1.2.md`, proposition actualisée, tests `test_combat_orientation` et régressions DOM/parcours/stockage préparés. Vérifications statiques réussies : AST de 18 Python, compilation syntaxique des cinq JS sans invocation, huit manifests/profils et 112 références de blocs, 976 IDs HTML uniques, caches et diff. **Aucun test exécuté, import applicatif de vérification, appel LLM, génération, redémarrage, commit/push/tag ni modification des ateliers utilisateur**. La discussion externe ci-dessous décrit l'état avant cette autorisation ; elle est désormais mise en œuvre. Qualité réelle des orientations à observer par l'utilisateur.

- **Consignes externes Combat analysées, 2026-09-10, discussion uniquement** : lecture complète de `Downloads/Action Director.txt`, `One vs many.txt`, `H3_Weapon_Combat_Choreography_Director__v1.1.txt`. Apports : techniques/cadrages propres à l'arme, trajectoire héritée, effets ancrés dans les attaques ; en un-contre-plusieurs, trajet central du protagoniste et pression relayée, obstacles canalisant les entrées, récupération/états persistants. Règles brutes non adoptées : formats six sections/T2V/monoplan, quotas/tranches horaires, mains nues, zéro pause absolu, visibilité intégrale des armes ou effacement d'historique. Proposition enregistrée dans `docs/combat-director-specializations-proposal.md` : futur Combat 1.2.0 avec Orientation Libre/mixte (défaut), Corps à corps, Armes ; un-contre-plusieurs transversal demandé dans l'intention, sans sélecteur supplémentaire obligatoire ni classificateur LLM. Choix conservé dans l'atelier/révisions/continuation ; suggestions de LoRA modifiables, workflow/forces indépendants. Socle Combat à versions exactes + blocs courts de spécialisation, Classique et anciennes versions isolés ; pas d'injection des manuels entiers. Aucun code, test, LLM, génération, service ou réglage de run touché. **Périmètre à aligner, implémentation non autorisée par cette demande de discussion.**

- **Combat 1.1.1 implémenté sur autorisation, 2026-09-10** : six recettes H3/REF2V en 1/2/3 appels, deux profils, nouveaux blocs propres d'identité et de rédaction. Association explicite rôle/`<Picture N>` au premier usage puis désignations stables, identité faciale distincte du costume/pouvoir ; noms sans ambiguïté de métier (cas « fire fighter »). Mouvement exclusivement dans `camera_motion`, cadrage initial dans `opening_composition`, actions dans `description`/`exchanges` ; descriptions placées sur les champs du schéma et entrées Writer. Le compilateur autorise les mentions Picture dans la prose **uniquement pour 1.1.1**, refuse les numéros inconnus et conserve les en-têtes/caméras/coupes protégés ; anciennes validations conservées. Plan et révisions portent les mêmes associations. Révision après rendu 1.1.1 conserve son contrat conversationnel/tokens caméra, sans appel caché. Version exacte reconnue dans domaine, stockage sans migration, fork, continuation/conversion, lancement et UI ; nouveau choix Combat = 1.1.1, ateliers existants et versions 1.1.0/1.0.0 conservés. Adoption explicite de la chorégraphie 1.1.0 et contrats neutres épinglés ; **561 empreintes de prompts/profils antérieurs inchangées**. Seed, MP, LoRA/BUNNY, quantité d'action, plans et files de rendu intacts. Caches des quatre JS concernés **20260910.4**. Guide `docs/h3-combat-1.1.1.md` et régressions `tests/test_combat_identity.py`, fixtures historiques + DOM continuation/contrôles actualisées. Vérifications : AST des Python modifiés, compilation syntaxique des quatre JS sans invocation, liens/versions des manifests et diff ; **aucun test exécuté, import applicatif de vérification, appel LLM, génération, redémarrage, commit/push/tag ni modification du workspace utilisateur**. Prochaines étapes : utilisateur termine le run courant, recharge ensuite le Lab avec le patch, exécute les tests préparés puis compare les visages dans une nouvelle exploration 1.1.1 à références/seed/réglages identiques. Gain réel de ressemblance à observer, pas garanti par la validation du prompt.

- **Ressemblance du rendu Combat réussi examinée, 2026-09-10, discussion uniquement** : utilisateur désigne explicitement le run déjà audité, pas celui en cours. Projet `h3-render-94a63cda91b54700a2fb947552b9c7a6`, essai `attempt-f91a5e62c9404c27b8fd80ce6d5d3389`, BUNNY turbo 9/4/5, LoRA `H3_Combat_V2` 0,6/0,2, MP 0,9/0,9 ; deux références Sujet présentes dans le projet et originaux inspectés (première de profil, yeux fermés ; seconde de face). Le `effective_prompt` répète « fire fighter », ambigu avec « pompier » ; la capture utilisateur montre une tenue de pompier à bandes jaunes, indice fort de cette interprétation, sans expliquer à lui seul la dérive des visages. Le prompt remplace les associations explicites `<Picture N>`/rôle par des descriptions physiques génériques et invente les tenues. Priorité proposée pour le correctif Combat versionné : liaison explicite image 1/personnage du feu et image 2/personnage de glace, désignations stables sans ambiguïté lexicale, identité faciale conservée distinctement du costume/pouvoir ; conserver la clarification des champs caméra prévue. La longueur, le montage et le LoRA ne peuvent être départagés causalement sur ce seul résultat. À vérifier après correction avec réglages/seed conservés ; aucun code fonctionnel, modèle, génération, test ou service touché. Note annexe : rendu réglé à 10 s alors que le prompt demande 8 s, sans causalité d'identité démontrée.

- **Dernier prompt Combat 1.1 audité, 2026-09-10, discussion uniquement** : session `prompt-14f7aed4a03e440c83346758274d0d2e`, appel `llm-a1c1218310c24c67a5b2aca345431c07` à 11:17:32 UTC, 75 812 ms, `finish_reason=stop`, résultat accepté. REF2V direct en un appel, action Déchaîné (3), quatre plans sur 8 s ; coupures compilées à 2,3 / 4,4 / 6,3 s. Progression gauche/centre/pilier droit, avantage feu puis contre-pression glace et fin en pleine offensive bien préparés. Réserves sur le texte : canal décrit sec puis rempli d'eau, formulation « stomps his gauntlet down », nombreuses actions successives dans les 1,7 dernières secondes ; richesse demandée à préserver, cohérence mécanique à améliorer. La trace retire délibérément les mentions `<Picture N>` en interprétant « Do not repeat reference labels » ; association explicite référence/rôle feu-glace moins claire dans le prompt final. Elle reformule aussi les mouvements en « view follows/carries » à cause de la permission ambiguë sur le sujet suivi : validation réussie de cet exemple, pas preuve que le rejet mono précédent est résolu. Pistes : clarifier en version Combat les champs caméra et la différence entre en-têtes compilés et mentions d'identité dans la prose, puis privilégier des enchaînements physiquement cohérents. Aucun prompt/code fonctionnel, test, LLM, rendu ou service modifié/lancé ; seul ce compte rendu est ajouté. Prochaine étape : retour utilisateur sur cette analyse et sur le rendu, puis décision d'un éventuel correctif versionné.

- **Thinking de l'échec mono Combat 1.1 analysé, 2026-09-10, discussion uniquement** : appel `llm-fccfdb67247646a3bfd4050d349524e0`. Le modèle choisit explicitement `tracking_shot` pour « Caméra mobile accompagnant l’action », puis cite la permission de préciser cadrage/sujet suivi sans ajouter un second mouvement ; sa trace conclut « The tracking camera follows laterally (truck within tracking). Fine. ». Il semble donc considérer sa phrase libre « The camera tracks laterally… » comme une précision du même mouvement, pas une seconde décision. Ambiguïté du prompt `sequence-direct.system.txt` : interdit de répéter des directives *canoniques* et un *second* mouvement, alors que le validateur refuse toute description libre du mouvement caméra, même compatible avec l'enum. Le schéma nomme `camera_motion` et `description` sans descriptions locales de cette répartition. Piste proposée : remplacer les consignes ambiguës par une règle de champ explicite (mouvement uniquement dans `camera_motion`, composition statique dans `opening_composition`, actions sujets/décor dans `description`), rapprochée des champs du schéma ; conserver liberté caméra et cadrage. Aucun signe ici d'incapacité à choisir une caméra ou de besoin démontré de passer en 2/3 appels. Pas de modification des prompts/code, ni test, LLM, rendu ou service lancé ; clarification à valider avant un futur changement versionné.

- **Relances REF2V Combat 1.1 comparées, 2026-09-10, lecture seule** : six appels du 10/09 entre 11:04:22 et 11:09:32 UTC. Quatre rejets multi-plan (4/4/2/2 plans, 57,58 / 71,438 / 50,172 / 42,552 s) ont exactement la même erreur de comparaison des caméras horodatées, couverte par le correctif précédent. Cinquième appel `llm-fccfdb67247646a3bfd4050d349524e0` : un plan, 39,79 s, rejet distinct `camera movement must come from a canonical compiled directive` ; le modèle ajoute dans `description` « The camera tracks laterally with the action as it relocates through the courtyard. » malgré `camera_motion=tracking_shot`. Ce cas n'est pas couvert par la correction des horodatages. Sixième appel `llm-998d81178ed94bd09097d7d4f92b8049` : un plan, 50,424 s, accepté. Aucun appel modèle tronqué/échoué ; rejets applicatifs uniquement. Pas de code fonctionnel, test, LLM, rendu ou service lancé pour cette comparaison. Prochaine étape : utilisateur charge le correctif multi-plan ; éventuel traitement séparé des consignes caméra libres à décider.

- **Échec REF2V Combat 1.1 diagnostiqué et corrigé, 2026-09-10** : session `prompt-2cabaf246aa443ef81ec6aa1a79d778c`, appel `llm-00785d89c1d5480f858c3da25a419b80` du 10/09 à 11:04:22 UTC. LLM réussi en **57 580 ms**, `finish_reason=stop`, JSON de quatre plans (2 300 / 1 900 / 1 900 / 1 900 ms), application rejetée : « Conservez les directives caméra de la séquence. ». Cause dans `combat_sequence.compile_result` : contexte enregistrant des phrases caméra sans heure alors que le lecteur partagé inclut `At …,` immédiatement après chaque coupure. Correction locale : enregistrer la phrase caméra horodatée exacte à partir du temps compilé, maintenir comparaison stricte de l’ordre, du mouvement et des coupes ; aucun changement des prompts, du lecteur partagé, de Combat 1.0 ou Classique. Réponse sauvegardée comme fixture `tests/fixtures/combat_1_1_four_shot_response.json`, régression préparée H3/REF direct et Plan/rédacteur, caméra/coupe altérée toujours refusée. Aucun test, import applicatif pour vérification, LLM, rendu, redémarrage ni écriture dans le workspace utilisateur. Prochaine étape : utilisateur charge le correctif au prochain redémarrage du Lab puis réessaie ; réponse originale toujours dans ses logs.

- **Lisibilité des contrôles Combat corrigée, 2026-09-10** : la grille générique des axes plaçait le curseur d’action dans une colonne de 22 px et comprimait le select des plans. Classe CSS dédiée `combat-controls` dans H3 et REF2V : intitulé/valeur sur la première ligne, curseur et sélecteur chacun sur toute la largeur, aide sur une ligne indépendante. Cache CSS `20260910.3`, assertion existante actualisée. Réglages, valeurs et prompts inchangés. Vérification statique seulement ; aucun test, LLM, rendu ou service lancé. Prochaine étape : recharger la page et vérifier la lisibilité dans la colonne de l’atelier.

- **Combat 1.1 implémenté sur autorisation, 2026-09-10** : six recettes H3/REF2V `combat.{prompt,planned,guided}@1.1.0`, version visible 1.1 expérimentale / 1.0 historique. Action Modéré/Dynamique/Intense/Déchaîné et plans 1–6 ou Auto indépendants, défauts Dynamique + 1 ; réglages figés à la création, comparaison via nouvelle exploration. Contrats et compiler `application/combat_sequence.py` propres à 1.1 : vrais 1/2/3 appels, actions reliées sans quotas, caméras/en-têtes/coupes compilés, last frame au dernier plan, révision conservant la structure. REF/H3, T/I/L/FL pris en charge. Version et réglages conservés dans sessions **11** (lecture 1–10), projets H3 **8** (1–7), forks, révisions post-rendu, conversion et continuation. Classic et Combat 1.0 intacts, **542 empreintes** de prompts/profils antérieurs inchangées. Rendu BUNNY/LoRA/MP/seed conservé ; pas de migration de workspace. Cache interface **20260910.2**, nouveau module `combat-controls.js`. Détails et commande tests : `docs/h3-combat-1.1-proposal.md`. Tests préparés, **NON EXÉCUTÉS** ; seules analyses AST/JS/JSON/HTML/empreintes et diff effectuées, aucun import applicatif, appel LLM, rendu ou service lancé. Patch dans `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`, non committé/poussé ; tags pré-BUNNY/pré-masque conservés. Prochaines étapes : tests et calibration sur rendus par l'utilisateur.

- **Proposition de version Combat, 2026-09-10** : sur demande « proposer une nouvelle version / comment versionner », document `docs/h3-combat-1.1-proposal.md`. Proposer **Combat 1.1.0 — Chorégraphie et montage**, expérimental, 1.0 conservé dans Historique et pour ses ateliers. Une seule version créative visible pour H3/REF2V et 1/2/3 appels, avec action et nombre de plans comme réglages indépendants ; plage proposée 1–6 ou Auto pour reprendre les exemples. Ensemble versionné couvrant préparation et échanges après rendu, blocs neutres épinglés, aucun héritage latest ni changement implicite de famille/version en continuation/adaptation. Comparaison via nouvelle exploration, sans migration silencieuse ; rendu BUNNY/LoRA/seed/MP indépendant. Schémas déjà pourvus de `preparation`, mais politiques/enum de révision limités actuellement à 1.0 : extension explicite nécessaire, ainsi que contrats REF multi/plage six. Proposition/documentation seulement, pas d'implémentation autorisée par cette question.

- **Clarification prioritaire utilisateur, 2026-09-10** : conserver **deux réglages indépendants : Quantité d'action et Nombre de plans** (1 = mono, plusieurs = coupures). Aucun remplacement de l'un par l'autre. L'ancienne suggestion de remplacement concernait uniquement le libellé Mouvements additionnels dans Combat ; ne pas en déduire une suppression de contrôles approuvée. Audace, mouvement caméra et nombre d'appels LLM restent distincts. Exemples utilisateur relus directement : duel épée/bouclier et duel hache/épée comportent **trois plans en dix secondes**, chaque plan contenant une combinaison riche attaque/parade/déviation/reprise, déplacement entre trois repères et coupes sur impact/occultation. Guerrière au tachi : **six plans en quinze secondes**, rythmes et échelles variés. Ces exemples doivent calibrer les niveaux d'action élevés et inspirer le découpage ; ne pas réduire chaque plan à un geste ni fixer un quota uniforme de coups toutes les 0,8 s. L'utilisateur donne l'arc global ; le LLM développe une description détaillée et choisit les techniques/transitions. Proposition de plans 1/2/3… ou Auto distinct de l'action, limite technique future à traiter explicitement (pas un plafond créatif déduit de l'ancien 2–4). Discussion/documentation uniquement, aucune implémentation lancée.

- **Action automatique acceptée, discussion mono/multi-plan, 2026-09-10** : l'utilisateur juge le nouvel affrontement bien meilleur et accepte l'approche d'un curseur Combat Modéré / Dynamique / Intense / Déchaîné (remplace l'affichage Mouvements additionnels dans Combat, distinct d'Audace et Caméra ; Classique conservé). Le résultat actuel sert de repère Dynamique à calibrer, sans quota de coups. Nouvelle version Combat envisagée, ancienne disponible ; pas encore implémentée. Dernière demande : analyser le prompt lapin/vampire en 1 étape et expliquer le mono-plan. Double cause explicite : intention « en un seul plan » et recette `minimax.h3.ref2v.combat.prompt@1.0.0` liant `h3-combat/1.0.0/mono.system.txt`, sans coupes. Le guide officiel MiniMax REF décrit bien des [Shot N] et coupes horodatées : capacité du modèle distincte de notre parcours Combat REF actuel. Les 1/2/3 étapes sont des appels de préparation, pas un nombre de plans vidéo. Arc du texte cohérent (lapin prend l'avantage, vampire renverse, contre-offensive finale), action dense ; ambiguïtés de l'intention « princesse » résiduelle et sujets « 1/2 » à remplacer par les noms. Cinq vignettes ne permettent pas de valider tous les gestes ni les coupes. Proposition complémentaire à discuter : choix mono/multi dans Combat REF pour 1/2/3 étapes, réutilisant l'infrastructure existante, avec coupes maintenant la continuité. Aucun code, test, LLM, génération ou runtime modifié ; documentation seule.

- **Combat jugé trop sage, diagnostic en lecture seule, 2026-09-10** : atelier `h3-render-3f6b01cb917e45a8b28d4bfe11752408`, session `prompt-28d27014c74f42eab41ebd2bfe67fd1e`, REF2V Combat **1 étape** 1.0.0, deux références Sujet. Audace/caméra/mouvements/vie déjà **3/3**. Intention issue du test prudent proposé par l'assistant impose caméra fixe, positions relatives conservées et un échange attaque/parade/riposte/recul. Prompt effectif : attaque 1,2 s, parade 2,6 s, esquive 4,9 s, reprise de garde de 6 à 8 s. Cela explique une faible densité demandée ; les vignettes ne suffisent pas à évaluer toute l'animation. Essai 1 Weapon Combat 0,6/0,2 réussi, déclencheur BUNNY absent ; essai 2 Combat V2 en cours au relevé, non touché. Les règles Combat 1.0 autorisent déjà plusieurs échanges en mono, mais leurs permissions prudentes ne garantissent pas une chorégraphie riche. Discussion proposée : déléguer au LLM l'invention à partir d'un arc global et de styles opposés ; rendre l'expansion plus explicite à audace/mouvements élevés dans une future version Combat, indépendante de Classique, sans nouveau curseur nécessaire. REF2V n'est pas intrinsèquement mono (guide MiniMax consulté), seule la famille Combat REF2V actuelle l'est. D'abord essayer une intention plus ouverte avec le même rendu ; multi-plan ensuite pour le montage, pas comme remède démontré. Aucun patch fonctionnel autorisé dans ce tour, tests/LLM/rendu/runtime inchangés.

- **Conseil de premier essai BUNNY Combat, 2026-09-10** : capture avec Weapon Combat V1, forces 0,6/0,2, 0,9 MP initial/final, 8 s et seed conservé. Base d'observation proposée : garder ces valeurs, Turbo 9/4/5 et preview ; vérifier le déclencheur `BUNNY` dans la description des sujets du prompt final (pas ajouté automatiquement par Combat). Si le mouvement manque ensuite, comparer la première force seule à 0,8, seconde toujours 0,2, même seed/prompt. Ces forces sont un point de départ, pas un optimum validé à deux passes. Fiche auteur Hugging Face relue : déclencheur confirmé, empilement avec d'autres LoRA forts de mouvement déconseillé. Aucun réglage/runtime/code modifié, aucun test ou rendu lancé ; prochaine action : observation du rendu par l'utilisateur.

- **Combat 1.0.0 implémenté sur demande, 2026-09-10** : sélecteur Préparation Classique / Combat dans H3 et REF2V ; neuf recettes (H3 mono 1/2/3, H3 multi 1/2/3, REF2V mono 1/2/3), trois profils propres. Chorégraphie causale et permissions/audace Combat distinctes ; blocs neutres à versions exactes, aucune dépendance à un cookbook Classique. Contrats de sortie/compilation existants conservés, sans assouplissement des validateurs. Famille verrouillée à la création, changement par exploration neuve ; pas d'héritage de variante créative entre familles. Détails `docs/h3-combat-preparation.md`.

- **Famille et versions de bout en bout** : `VideoPreparationRef` dans profils/cookbooks/sessions/projets H3, rejet des associations incohérentes. Révision post-rendu Combat 1.0.0 avec prompts propres et caméra/dialogues compilés ; les révisions Classique restent propres aux projets Classique. Conversion H3 vers REF2V conserve famille, frames et réglages ; continuation depuis la dernière frame garde la recette H3 exacte, ou le même nombre d'appels et la version Combat depuis REF2V. Absence de version : erreur explicite et brouillon conservé. Sessions schéma 10 (1–9 compatibles), H3 schéma 7 (1–6 compatibles), profils 6, cookbooks 10. Anciens ateliers Classique par défaut ; aucune migration en masse.

- **Livraison Combat** : aucune sélection automatique de LoRA/déclencheur, aucun changement de recette de rendu, MP, seed ou Turbo. Empreintes statiques des neuf cookbooks et trois profils Classique actuels identiques au snapshot avant patch. Tests simulés de routage, appels, isolation bidirectionnelle, migration, révision, conversion et navigateur préparés, **NON EXÉCUTÉS**. Contrôles limités à AST, syntaxe JS sans invocation, liaisons de fichiers et empreintes ; aucune importation applicative de vérification, aucun appel LLM, rendu, chargement GPU, redémarrage, modification runtime, commit/push. Caches core/H3/REF2V/rendu `20260910.1`. Tags stables conservés. Qualité des chorégraphies et durées à observer par l'utilisateur ; REF2V multi-plan historique non promu, adaptation H3 Combat multi-plan vers REF2V disponible.

- **Blocage H3 résolu, 2026-09-10** : `another H3 Base render is already active` venait de `attempt-2afce7589f3d4d289b853ed8d768f8be`, projet `h3-render-39bf331e2f294e0cbd671c93b5e6474e`, resté running depuis la veille. Exécution `bddc4cf0-85f8-48e9-9a90-12187928d244` absente de la file et de l’historique Bucket. Après relecture historique/file/historique, JSON original sauvegardé sous le projet dans `recovery/project-before-orphan-recovery-20260910.json`, seul essai passé en failed avec explication et conservation des prompts/réglages. GET sur le Lab 7861 confirme ; plus aucun essai H3 actif au relevé. Les cinq essais seulement préparés du nouveau projet `h3-render-1df62d1dc6104b2d8b5b865787ba70b0` restent disponibles, aucune soumission automatique. Rapport `docs/h3-render-recovery-2026-09-10.md`.

- **Correctif préventif H3/REF2V** : réconciliation des running/cancel_pending sans worker local par historique/file/historique ; disparition confirmée → failed, présence distante/panne/réponse invalide → conservation. Fin intervenue entre lectures importée, interrupted reconnu sans completed. Recharger le projet avant sauvegarde de l’admission évite de ressusciter l’état actif récupéré dans le même atelier. Conflit réel explicite en français avec atelier/essai. Client Comfy refuse une réponse de file incomplète. Tests ciblés `test_h3_render_recovery` préparés, **NON EXÉCUTÉS** ; AST et diff contrôlés. Pas de LLM, génération, annulation distante, import applicatif de vérification ou redémarrage. Déblocage runtime déjà effectif ; code préventif chargé au prochain démarrage utilisateur. Architecture Combat/Classique réaffirmée dans Goal, sans patch Combat lancé.

- **Discussion isolation Combat / Classique, 2026-09-10** : l’utilisateur exige qu’une modification Combat n’entraîne pas de changement Classique et demande comment partager les progrès généraux sans divergence. Proposition documentée à la fin de `docs/h3-combat-prompt-audit-2026-09-09.md` : deux familles de préparation indépendantes, blocs communs neutres à versions exactes, promotion explicite des améliorations communes vers les deux familles dans le même patch. Aucun héritage de « Classique latest » ; règles créatives et validations spécifiques séparées. Registre actuel capable des assemblages versionnés, mais gros templates hérités à examiner avant réutilisation. Famille/version/contexte conservés jusqu’à la révision post-rendu ; application/file/DLSS/rendu partagés. **Discussion uniquement, aucune implémentation demandée dans ce tour.** Documentation et continuité actualisées, aucun test, LLM, rendu ou service lancé.

- **Priorités et audit combat, 2026-09-09** : l’utilisateur fixe **prompts de combat P0**, **analyse vidéo/images vers prompt P1**, recherche de seeds oubliée pour le moment. Audit dans `docs/h3-combat-prompt-audit-2026-09-09.md`, backlog réordonné. Neuf fichiers lus, sept prompts distincts (E3 = E2, E8 = E1) ; descriptions et versions Civitai lues par API, fiches de l’auteur sur Hugging Face et guides officiels Base/Reference consultés. Les TXT Director joints aux fiches sont recensés, mais leur téléchargement répond 403 : contenu non lu. Aucun benchmark vidéo effectué.

- **Direction combat à discuter, pas de patch fonctionnel autorisé dans ce tour** : chaînes attaque/réponse/conséquence/reprise, initiatives et espace lisibles, densité adaptée à la durée, bloc partagé aux parcours 1/2/3 sans Plan caché. Garder mono/multi-plan, caméra, dialogue et formats H3/REF2V propres (Base trois rubriques, Full Reference six). Weapon Combat V1 utilise `BUNNY` et son auteur déconseille l’empilement avec Combat Base V2/Motion Repair ; choisir le LoRA créatif à la place de l’existant, pas en plus, lors d’une expérimentation future. Combat V2 : métadonnées `prfight2`/`prfin1`, ne pas recopier les anciens déclencheurs V1 encore présents dans la page. Les forces générales et samplers recommandés ne se transposent pas automatiquement aux deux passes T8. Textes de démonstration jugés utiles pour leurs liens causaux, trop chargés pour devenir des gabarits obligatoires. Aucune recette/réglage/runtime modifié, aucun test, LLM, rendu, téléchargement de poids ou service lancé ; documentation seulement.

- **Discussion outil d’analyse vidéo/images vers H3, 2026-09-09** : demande d’importer une vidéo ou une série d’images pour obtenir un prompt REF2V ou FL2VA (« FL2A » dans le message), et rappel du backlog. **Aucun patch fonctionnel demandé : discuter.** Lecture du code : `CompletionRequest` accepte des images, le feedback H3 les horodate ; `DlssMedia.frames` extrait déjà des images locales, mais aucun moteur général d’analyse temporelle vers prompt H3 n’est identifié. Proposition à discuter : espace séparé, choix d’extrait/frise, observations et transitions corrigibles, rédaction spécialisée REF2V/FL2VA et ouverture dans l’atelier existant. Deux traitements internes, sans imposer une nouvelle succession d’écrans. Images d’analyse distinctes des références/ancres de génération ; ne pas prétendre connaître le son ou une action absente des images. Deux questions facultatives posées : fidélité vs adaptation à ses propres images ; courts extraits vs passage choisi vs découpage d’une vidéo entière. Réponses encore attendues au moment de cette note.

- Backlog récapitulé dans `docs/backlog.md` : prompts de combat, fluidité/lisibilité (correctifs livrés à observer), recherche de seeds explicitement laissée de côté (audit séparé maintenant lié), nouvelle analyse vidéo en discussion ; automatisation/vidéos longues restent une vision ultérieure. Plusieurs anciennes « Next steps » sont des validations de fonctions déjà livrées, pas des fonctions nouvelles à réimplémenter. Lecture et documentation seulement pendant ce tour ; aucun test, LLM, rendu, extraction exécutée ou service modifié.

- **Correction explicite des défauts H3 / REF2V, 2026-09-09** : l’utilisateur réaffirme **Réutiliser seed coché, MP initiaux 0,2 et MP après upscale 0,2, les deux modifiables** pour les rendus courants. H3 0.1.3 satisfait déjà les résolutions ; REF2V passe au rendu courant **0.2.1**, nouveau manifeste avec binding initial et cible finale par défaut 0,2. Adaptateur REF2V et service transmettent effectivement la valeur initiale au graphe, indépendamment de la sortie ; aucun ID de nœud ajouté au code de feature. Ancien 0.2.0 conservé, résolu uniquement dans le catalogue REF2V et libellé Historique, pour reprendre les essais existants. Seed activé par défaut dans le HTML REF2V, les specs des deux modes, le corps HTTP H3 et le fallback JS ; choix de décocher conservé. Libellés explicites « MP initiaux » / « MP après upscale », cache H3-render `20260909.7`. Brouillons/reprises gardent leurs valeurs enregistrées ; les presets BUNNY explicitement convenus à 0,9/0,9 ne sont pas modifiés. Cette correction remplace la décision précédente de laisser le rendu REF2V courant avec première passe désactivée.

- Vérification de ce correctif : `test_ref2v_render_resolution` préparé (bindings distincts, défauts, limites, compilation via service simulé, stockage/reprise/historique), tests navigateur/assemblage mis à jour. **Aucun test exécuté**, aucun appel LLM, rendu ou redémarrage. AST Python, JS et scénarios navigateur compilés sans invocation ; nouveau SHA vérifié et graphes historiques inchangés. Aucun média/runtime, commit ou tag modifié.

- **Audit fluidité Assisted / lisibilité H3, 2026-09-09** : demande de lenteur avant mise en file et clignotement, plus MP, accents et backlog combat. Lecture locale uniquement : 313 ateliers, 5 023 788 octets de JSON ; dernier atelier `krea2-create-0ef1603e4ae64877b6d5a382598211f6`, 22 essais tous réussis, 8 messages. Lecture/décodage JSON brut ≈38 ms, hors objets métier/verrous/réseau : **pas une mesure de latence de l’application**. Causes dans le code : galerie/conversation/arbre reconstruits toutes les secondes, scans checkpoints/LoRA sur SSHFS et inventaire Comfy à chaque admission, attente supplémentaire du GET de file après POST, historique désérialisé entièrement avant limitation. Rapport : `docs/assisted-performance-audit-2026-09-09.md`.

- **Correctifs ciblés de fluidité implémentés** : cartes Assisted conservées par ID, images préservées lors des mises à jour de métadonnées, conversation/arbre inchangés laissés en place ; réponse de polling antérieure au clic invalidée, bouton libéré dès le POST d’ajout. Vérification positive depuis le dernier inventaire chargé lors de l’admission ; sélection inconnue découverte normalement, vérification fraîche conservée dans le worker avant ComfyUI. Le catalogue reste rafraîchissable normalement, pas de cache opaque des projets ni de modification des réglages/FIFO. Historique limité avant désérialisation. La file globale parcourt encore tous les ateliers sous verrou : point restant à mesurer, pas de diagnostic hâtif de cause dominante. POST expose `Server-Timing` prepare/worker/serialize dans les outils réseau du navigateur, sans appel supplémentaire ; pas de réécriture des runs historiques.

- **MP / accents / backlog** : REF2V actuel 0.2.0 utilise bien le champ MP pour la sortie, avec première passe fixée à 0,2 dans son graphe. Les deux champs sont désormais visibles et explicitement nommés, valeur initiale désactivée et expliquée pour cette recette ; H3 actuel/BUNNY gardent les deux valeurs modifiables. Libellé H3 révision 0.3.0 réparé (`?` présents littéralement dans le code). Cache Assisted/H3-render/CSS `20260909.6`. Prompts de combat inspirés de BUNNY notés dans `docs/backlog.md`, aucune nouvelle recette/LoRA activée. Aucune fonction supprimée ; éventuel regroupement des actions secondaires à discuter après observation.

- **Livraison de cette passe** : régressions préparées `test_krea2_assisted_performance`, `test_krea2_assisted_poll_browser`, file/HTTP Assisted, affichage MP BUNNY et assertions de cache actualisées ; **tests NON EXÉCUTÉS**. Contrôles syntaxiques Python AST, JavaScript et scénario navigateur compilés sans invocation, IDs HTML uniques, diff vérifié. Aucun import applicatif de vérification, appel LLM, génération, service redémarré ou donnée runtime modifiée. Pas de commit/push/tag modifié. Patch précédent BUNNY/dialogue/conversion/DLSS conservé dans le worktree.

- **Patch dialogue / adaptation REF2V implémenté, 2026-09-09** : neuf versions de recettes, H3 mono 1.2.0 / H3 multi 1.1.0 / REF2V mono 1.1.0, chacune guided/planned/prompt (3/2/1 appels). Profils 0.6.0 / 0.3.0 / 0.6.0 ; politique vocale partagée 1.0.0. Curseur 0–3, défaut 0, masqué sur les recettes historiques. Répliques utilisateur protégées, ajouts balisés English et bornés en nombre/longueur ; choix du Brief conservés dans les étapes suivantes. Révision post-prompt 0.3.0 avec caméra compilée ; changer le niveau seul ne lance rien. Anciennes recettes et graphes préexistants conservés. Le REF2V multi-plan historique reste inchangé ; H3 multi-plan peut être adapté en REF2V et révisé en 0.3.0. Guide : `docs/dialogue-and-ref2v-conversion-plan.md`.

- **Adaptation H3 → REF2V 1.0.0** : bouton près du prompt de rendu H3, capture du texte édité et des réglages compatibles, first/last reprises dans l’ordre, image ajoutée exigée en T2V sans frame. Un appel multimodal, en-têtes compilés ; caméra/paroles/timestamps/coupes/audio protégés par des jetons. Atelier dérivé distinct sans Brief/Plan fabriqué ni rendu automatique, BUNNY conservé si choisi ; liste « Adaptations depuis H3 », références visibles et lien source. ID idempotent, statut et brouillon persistés, sauvegarde périodique des deltas, aucun retry LLM automatique. Un nouvel appel nécessite une nouvelle adaptation explicite depuis H3. Conversations/rendus/feedback/DLSS utilisent le projet dérivé. La conservation sémantique et la qualité restent à expérimenter.

- **Livraison de ce patch** : sessions schéma 9 (lecture 1–8), compositions 4 (lecture 1–3), H3 6 (lecture 1–5) ; hash historique des intentions à dialogue 0 préservé. Cache UI modifiée `20260909.5`. Tests `test_vocal_policy`, `test_h3_ref2v_conversion` préparés, assertions de stockage/cache mises à jour, **NON EXÉCUTÉS**. Contrôles statiques uniquement : AST Python, imports internes, attributs des corps HTTP, compilation JS sans invocation, IDs HTML uniques et bindings des neuf recettes. Aucun import applicatif pour vérification, test, appel LLM, rendu, installation ou redémarrage de service. Tag `snapshot-avant-bunny-h3-2026-09-09` et point pré-masque conservés ; patch non committé/poussé. Le correctif DLSS ci-dessous fait partie de la livraison.

- **Incident DLSS vidéo pendant le patch vocal, 2026-09-09** : dernier job `dlss-a7f23157fc80efab0bb6bf2457d026bd` échoué à l’import avec `a bytes-like object is required, not 'dict'`. Sortie MP4 présente et conservée : `D:\AI\PanelForge\LocalOutput\dlss\dlss-a7f23157fc80efab0bb6bf2457d026bd_00001_.mp4`, 150891484 octets. Cause : `LocalAssetStore.register_file` envoyait un dict à `_atomic_write` (attend des bytes). Correctif : sérialisation `_json_bytes` avant écriture atomique, comme les autres assets. Tests existants `test_dlss_outputs` couvrent enregistrement/réouverture sans copie, non exécutés. Une fois le Lab rechargé par l’utilisateur, **Reprendre** doit récupérer la même exécution Comfy `01af6556-c9ce-476c-8949-69b65b7b8fde`, sans nouvelle soumission si son historique réussi est conservé. Aucune relance, mutation du job ou copie du média effectuée. Le patch dialogue/conversion reste l’objectif actif.

- **Reprise du patch dialogue / conversion REF2V, 2026-09-09** : après le correctif d’import, l’utilisateur demande « regardons pour l’autre patch ». Périmètre précisé dans `docs/dialogue-and-ref2v-conversion-plan.md`, sans modification applicative. Axe vocal 0–3, défaut 0 ; choix à la première étape décisionnelle, puis conservation, paroles imposées distinctes des ajouts. Proposer aussi le réglage dans les échanges post-prompt, appliqué au prochain appel. Versions de recettes historiques conservées, blocs partagés ; couvrir mono/multi-plan et 1/2/3 étapes. Adaptation depuis le prompt affiché vers un atelier REF2V dérivé en un appel multimodal, rôles first/last repris, en-têtes compilés par l’application, aucun ajout créatif pendant la conversion ni génération automatique ; texte seul exige une référence. Reprendre les réglages compatibles et BUNNY si sélectionné, conserver source/candidat sur erreur et navigation. Aucun test, appel LLM, rendu ou service exécuté pour ce cadrage.

- **Correctif démarrage BUNNY, 2026-09-09** : traceback utilisateur `ImportError: cannot import name derive_h3_render_input_mode from panelforge.domain.h3_render`. L’adaptateur BUNNY importait depuis le domaine une fonction encore définie dans l’application. Fonction pure déplacée dans `domain/h3_render.py`, réexport conservé par l’application et son `__init__`, validation de mode des projets déléguée à cette même fonction. Aucun changement des workflows ou paramètres. Régression préparée dans `tests/test_h3_render.py` : compatibilité des imports public/BUNNY et quatre combinaisons first/last. **Non exécutée** ; contrôle AST et résolution statique des imports internes absolus BUNNY/domaine/application/lanceur OK. Aucun import applicatif exécuté pour vérification, test, appel LLM, génération ou service lancé/redémarré. L’utilisateur relancera sa commande habituelle. Priorité donnée au correctif ; dialogue et conversion REF2V restent pour la suite, selon « ensuite on verra pour implémenter ».

- **Discussion après BUNNY : liberté de dialogue et conversion vers REF2V, 2026-09-09 — non implémentées**. L’utilisateur souhaite autoriser de courtes paroles anglaises spontanées et réactions vocales, puis convertir un prompt H3 image/texte-vers-vidéo en REF2V par un seul appel LLM, en reprenant les images début/fin. Audit : axes actuels scène/caméra/mouvements sans axe dialogue ; certains validateurs multi-plan exigent exactement les paroles de l’intention, donc adapter conjointement politique, prompts et contrats. Proposition à discuter : axe 0–3, défaut 0 (aucun ajout), 1 réactions non verbales, 2 courte réplique anglaise, 3 bref échange ; autorisations et budget lié à la durée, personnages existants, paroles utilisateur conservées, choix stabilisés après la première étape LLM. Conversion proposée depuis le prompt courant vers un atelier REF2V dérivé avec lien source, références et réglages compatibles repris, un appel multimodal de reformulation sans nouveau Brief/Plan ; mapping/en-têtes compilés par l’application, actions/coupes/caméra/audio/paroles préservés. Les rôles first_frame/last_frame existent en REF2V mais restent des références conditionnées par le prompt, sans verrouillage matériel des frames comme FL2VA. Texte seul sans image : demander au moins une référence, pas de génération d’image automatique. Aucune modification applicative, aucun test, appel LLM ou rendu pour cette discussion.

- **BUNNY H3 autorisé et implémenté, 2026-09-09** : sélecteur de recette dans les ateliers H3 Base et REF2VA. **Rendu actuel reste disponible et par défaut**, graphes H3 0.1.3 / REF2V 0.2.0 inchangés. Nouveau `minimax-h3-bunny@0.1.0` depuis le JSON API `(3)` conservé exactement, SHA `8c2f4419f0f121e8cf4aa0e92cac5fd86a6267ca6fba0ad9da3290edf503243b`. FL/I/L/T → modèle FL2VA BF16 ; REF2VA → hybride FL2VA/REF2VA blocs 25–49, branche inutilisée retirée. Bonnes entrées image dans les deux conditionnements avec mode explicite, 1–9 références. Défauts 0,9 MP initial/final (×1), Turbo 0,7 ON, calendrier 9/4/5 ; OFF retire Turbo et propose 30/25/5, ajustements conservés par profil. Un LoRA facultatif sur deux branches indépendantes, Motion Repair importé 0,6/0,2 ; Spectrum et CLIP -2 indisponibles pour BUNNY. MP tous deux modifiables, géométrie T8 alignée et facteur affichés, pas de réduction.

- **Cycle de vie BUNNY** : identité/version/empreinte et paramètres enregistrés par essai, stockage H3 schéma **5**, lecture 1–4. Soumission, récupération après redémarrage, sortie vidéo/keyframes et progression utilisent la recette de l’essai. Recette inconnue ou incompatible refusée, pas de substitution silencieuse. Vérification des classes et fichiers par descriptions Comfy avant soumission ; aucune installation automatique. Preview KJ + taeh3 raccordée aux deux branches, 8 frames / 768 px / 12 FPS, désactivable ; présence de ces interfaces confirmée sur Bucket par GET en lecture seule, fonctionnement réel à expérimenter. Keyframes depuis le décodage final, mêmes max 8 et marge 500 ms. Conversation, dernière frame et DLSS partagés ; provenance génération incluse dans le diagnostic DLSS. Paramètres/brouillons UI séparés par atelier/recette/profil Turbo, prompt conservé, reprise d’un essai restaure la recette. Cache H3 rendu/CSS **20260909.4**.

- **Livraison BUNNY** : guide `docs/bunny-h3-render.md`, proposition historique reliée. Tests `tests.test_h3_bunny` et `tests.test_h3_bunny_browser` préparés, fixtures contrôles H3 et bootstrap/cache ajustées, **NON EXÉCUTÉS**. Contrôles statiques : AST Python, JS et fixtures compilés sans invocation, champs HTTP et IDs DOM cohérents, empreinte/liaisons du manifeste et graphes historiques comparés au snapshot. Aucun appel LLM, génération, import applicatif pour vérification, test, installation, chargement de modèle, annulation ou redémarrage de service. Activer au prochain redémarrage du Lab et rechargement par l’utilisateur une fois ses traitements terminés. Tag `snapshot-avant-bunny-h3-2026-09-09` (`f2a61a5`) et tag pré-masque conservés. Patch non committé/poussé.

- **Point de restauration avant BUNNY publié et vérifié, 2026-09-09** : à la demande de l’utilisateur, commit **`f2a61a5ef47267eef4635a217821e51bf86e3700`**, tag annoté **`snapshot-avant-bunny-h3-2026-09-09`** et branche dédiée `snapshots/avant-bunny-h3-2026-09-09` publiés par push atomique sur `https://github.com/EasyFrag/panelforge`. Vérification `git ls-remote` : branche et tag résolu pointent tous deux sur ce commit ; tag pré-masque toujours `56840b877be4b810ee93f8afe9b2f0c40ee73006`. Périmètre : 200 fichiers, toutes les modifications de code, recettes, tests préparés et documentation depuis le tag pré-masque, notamment Edit/FireRed, H3 et DLSS ; aucune donnée workspace, média ou poids de modèle. **BUNNY restera une recette de rendu supplémentaire**, les recettes H3 Base 0.1.3 et REF2V 0.2.0 et leurs réglages resteront sélectionnables. Aucun test, appel LLM, rendu, installation ou service lancé ; aucun changement applicatif BUNNY dans ce snapshot. Remote `origin` local conservé, publication directement vers l’URL GitHub, branche master distante non modifiée. Cette confirmation de publication est postérieure au snapshot, dont le tag reste immuable.

- **Alignement BUNNY fichier (3), 2026-09-09 — toujours discussion** : nouveau JSON utilisateur au format API, chargeur FL2VA BF16 69 actif ; HybridLoader FL2VA + REF2VA 66 présent mais débranché. Proposition de routage automatique FL/I/L/T → FL2VA, REF2VA → hybride comme notre recette REF2V, avec raccordement des images aux deux conditionnements (actuellement aucune). Défauts demandés **0,9 MP ×1,0 ; Turbo ON à 0,7 ; plan 9/4/5**. Turbo OFF initialise **30/25/5**, profils gardant ensuite leurs réglages. Les deux triplets sont valides selon le code T8, qualité sans Turbo non démontrée ; `base_steps` est un calendrier, nombre exécuté coarse+refine. Un seul LoRA facultatif appliqué séparément à chaque passe ; Motion Repair actif **0,6/0,2** dans ce fichier, jiandou retiré. `comfy kitchen attention` remplace SageAttention, nettoyage Easy-Use retiré. Preview live proposée via notre KJ/taeh3 existant, absent du nouveau graphe et compatibilité T8 à vérifier ; pas de décodage lourd ou génération supplémentaire par défaut. Proposition détaillée actualisée dans `docs/bunny-h3-integration-proposal.md`, aucun code applicatif, test, rendu, installation ou service modifié.

- **Précision BUNNY FL2VA / REF2VA, 2026-09-09** : question utilisateur sur les deux modes du workflow. Lecture du JSON fourni et de `conditioning.py` T8 : checkpoint hybride préassemblé ; AUTO résout le mode selon les entrées (références seules REF2VA, first+last FL2VA, first I2VA, last L2VA, aucune T2VA, références+frames Hybrid), pas selon le texte du prompt. Même pipeline réutilisable avec câblage approprié dans les deux conditionnements ; deux images dans `ref_images` restent des références. Fichier reçu : first/last non connectées et quatre LoadImage en bypass. Proposition précisée, sans intégration, test ou génération ; l’utilisateur expérimente sur Bucket avant le patch.

- **BUNNY repris en discussion, 2026-09-09** : l’utilisateur installe et teste d’abord lui-même le workflow, puis souhaite une intégration fluide avec les ateliers existants. **Bucket confirmé** en réponse à la question du lieu d’installation ; Comfy Windows reste dédié au DLSS. Proposition consignée dans `docs/bunny-h3-integration-proposal.md` : sélecteur de recette de rendu Actuelle / BUNNY expérimental, indépendant des parcours LLM 1/2/3 étapes ; même atelier, galerie, feedback, continuation et DLSS. Garder les deux champs MP modifiables et afficher le facteur/dimensions effectifs, paramètres séparés par recette, LoRA dosables par passe. Figer d’abord le JSON du test réussi. Audit du service : recette aujourd’hui résolue par mode de projet, donc identité/version et réglages doivent être attachés à chaque essai pour soumission/import/récupération. Raccorder entrées aux deux passes et keyframes ; ne pas présumer les modes prêts à partir du JSON aux images en bypass. Fiche v1.0 consultée via API publique : 0,3 MP ×1,5 conseillé pour 12 Go, exemple 0,9 MP ×1,5 sur RunningHub distinct ; aucune promesse de qualité/vitesse sur Bucket. **Documentation seulement**, aucun code applicatif, test, appel LLM, génération, installation ou service modifié.

- **Suppression de la duplication des nouveaux médias DLSS autorisée et implémentée, 2026-09-09** : l’utilisateur juge la copie `workspace/assets` inutile et ne retrouve pas les fichiers. Vérification directe : les quatre PNG/MP4 existent dans `D:\AI\PanelForge\LocalOutput\dlss` (dossiers ordinaires, pas de jonctions), ainsi que quatre copies `assets/<id>/content.bin`. Dernier MP4 `dlss-c3fe5f8d4e2dd70e34c261ed1b3b664f_00001_.mp4` : 151 341 467 octets ; son ancienne copie interne est `asset-60dabeab342a4d3dbfabe282359cd229/content.bin`. Expliquer le nom interne `.bin`, donner un lien direct au MP4. Aucun fichier utilisateur déplacé/supprimé/migré.

- **Nouveau stockage DLSS** : `DlssOutputs` injecté référence le PNG/MP4 Comfy vérifié (nom/dossier bornés, empreinte comparée au téléchargement), sans copie du média final dans les assets. Un redimensionnement ou masque Edit produit un PNG distinct visible `<job>_enhanced.png` / `<job>_result.png`, également référencé. PNG Comfy natif conservé sans réencodage superflu. `LocalAssetStore.register_file` écrit seulement `asset.json` au **schéma 2** : chemin externe, taille/empreinte, identité ; lecture uniquement dans les racines configurées. Assets internes schéma 1 inchangés, mêmes IDs et API de lecture, domaines/projets inchangés. Keyframes de feedback et rapports restent stockés normalement, car ce sont des données dérivées nécessaires. Déplacer/supprimer/remplacer le fichier référencé rend sa lecture indisponible : conserver les résultats visibles. Anciens `content.bin` intacts.

- **Dossier DLSS harmonisé** : nouvelle option `--dlss-output-root D:\AI\PanelForge\LocalOutput`, transmise en `--output-directory` au démarrage automatique, alignée sur le BAT utilisateur sans modifier celui-ci. Repli explicite accepté vers `ComfyUI/output` pour un Comfy déjà ouvert avec l’ancien défaut ; aucune recherche filesystem globale ni copie cachée si destination inconnue. Le chemin exact `local_output_path` est maintenant visible dans le suivi. Export vidéo vers X:/.../Upscale/<date> conservé, lecture via référence locale. Cache DLSS **20260909.3** ; H3/CSS 20260909.2 inchangés. Tests `test_dlss_outputs.py` préparés ; scénarios Assisted/Edit/H3/REF2V, lecture HTTP Range, export serveur, ancien stockage et lancement simulé enrichis. **Tests NON exécutés**. AST 245 fichiers Python, JS DLSS + quatre fixtures navigateur compilés sans invocation, IDs/cache/empreintes des graphes/diff contrôlés. Guide `docs/dlss-local.md` actualisé. Aucun test, appel LLM, génération, lecture de modèle, démarrage/redémarrage/arrêt de service ou donnée runtime modifiée. Activation au prochain redémarrage Lab par l’utilisateur ; pas de commit/push.

- **Emplacement réel des sorties DLSS vérifié, 2026-09-09** : le lanceur utilisateur `D:\AI\ComfyUI_windows_portable\run_dlss.bat` contient `--output-directory "D:\AI\PanelForge\LocalOutput"`, également présent dans les arguments du Comfy actif PID 23228. **Images PNG et vidéos MP4 sont réellement dans `D:\AI\PanelForge\LocalOutput\dlss`** : quatre sorties confirmées correspondant aux journaux, dont `dlss-c3fe5f8d4e2dd70e34c261ed1b3b664f_00001_.mp4` (13:56:21) et `dlss-fd08f4581954bafd33a2740c0b931ea5_00001_.png`. Le dossier standard `ComfyUI\output\dlss` mentionné précédemment n’existe pas pour cette instance. Copies internes dans `D:\Code\panelforge\workspace\assets\<asset-id>\content.bin`. **Distinction à conserver** : le démarrage automatique implémenté par PanelForge ne reprend pas encore cet argument ajouté au BAT ; il utiliserait le dossier standard de Comfy, alors que la réutilisation du processus manuel actuel garde LocalOutput. Aucun alignement de configuration demandé/implémenté à ce stade. Export serveur vidéo du patch distinct et futur, activé au redémarrage Lab ; derniers journaux sans `video_export`. Lecture fichiers/arguments ciblés seulement, aucune génération ou modification runtime ; guide DLSS corrigé.

- **Diagnostic DLSS sans pourcentage, 2026-09-09 à 13:57 locale** : capture utilisateur « Traitement DLSS · 1 min 27 s », ×1,724/60 FPS. Cause identifiée : **backend ancien encore chargé**, pas une absence démontrée de progression du nœud. Processus Lab écoutant 7861 : PID 23060, démarré **12:04:08**, workspace `D:\Code\panelforge\workspace`. Fichiers du suivi modifiés à 12:42:51 (`dlss_progress.py`, bootstrap), service 12:52:16. GET lecture seule `/openapi.json` expose les anciennes routes DLSS et **pas** `/api/dlss/jobs/{job_id}/export`, preuve du backend antérieur ; les nouvelles ressources statiques sont servies depuis le disque, expliquant les nouveaux boutons avec ancien serveur. Dernier journal `dlss-c3fe5f8d4e2dd70e34c261ed1b3b664f` créé à 13:53:30, réussi, sans `progress`, `finished_at`, `video_export`, comme les trois précédents. Code Comfy installé confirme événements progress (value/max/prompt_id/node) et progress_state à destination du client initiateur. Action nécessaire : **relancer uniquement le Lab par l’utilisateur**, une fois ses traitements terminés, puis recharger la page ; Comfy/Unsloth n’ont pas besoin d’être redémarrés pour charger le collecteur PanelForge. La copie serveur du patch sera activée par ce même rechargement backend ; anciens résultats non migrés automatiquement. Aucun test, import applicatif, socket sur client DLSS, appel LLM, rendu, annulation, changement runtime ou redémarrage ; continuité seule actualisée. BUNNY mis de côté à la demande de l’utilisateur.

- **Audit BUNNY H3, 2026-09-09 — discussion, aucune intégration demandée** : fichier `C:\Users\samue\Downloads\BUNNYH3高动态二次放大_FL2VA_REF2VA(1).json`, 95 266 octets. Même principe que H3 Base 0.1.3 et REF2V 0.2.0 : première diffusion, upscale latent H3 3D, seconde diffusion puis décodage audio/vidéo à 24 FPS. Ce pipeline est indépendant du DLSS de post-traitement et des recettes de préparation LLM en 1/2/3 étapes. Aucun remplacement du moteur existant justifié par le seul graphe.

- **Écarts BUNNY réellement câblés** : modèle préassemblé `minimax_h3_hybrid_fl2va_ref2va_zs05_b25-49_int8.safetensors` (égalité des poids avec notre hybride BF16 construit à la volée non vérifiée), Turbo v4 à 0,7, SageAttention, nœuds T8 DualClock/ParityPlan/Reconcile/DetailMixer. Plan nœud 9 : base_steps 9, coarse_steps 4, refine_steps 5 ; les sigmas du sampler proviennent de ce plan, le champ steps 8 du DualClock n’est pas le budget effectif. Nos défauts sont 25 + 3 steps, sampling res_multistep en H3 / Euler en REF2V. Les LoRA de seconde passe sont distincts de la première ; `jiandou.safetensors` actif à 0,85 / 0,5 malgré titres 0,50 / 0,30, Motion_Repair 0,6 / 0,2 en bypass. Notre overlay LoRA partagé affecte les deux passes.

- **Résolution et limites de cet audit** : BUNNY est enregistré à 0,9 MP, facteur spatial ×1,5 soit environ 2 MP finaux après arrondis, durée 10 s (prompt de démonstration mentionne 15 s). Comparer à notre première passe 0,2 MP à défaut ; H3 a désormais 0,2 MP initial ET final par défaut, donc même taille entre passes tant que l’utilisateur ne monte pas la sortie. Le graphe BUNNY sélectionne un upscaler fp16 via T8, le nôtre bf16 via MinimaxH3LatentUpscaler3D : même famille, identité numérique non démontrée. Quatre LoadImage en mode 4, aucune first/last frame connectée ; ne pas annoncer le fichier prêt pour FL2VA/REF2VA tel quel. Lecture du code public T8 `learned_latent_upscale_advanced.py` : le ParityPlan reprend un calendrier publié LBH, coarse 4 + refine 5 effectifs ; le contrôle de hash est désormais diagnostique, contrairement aux notes du fichier qui le disent bloquant. Source https://github.com/T8mars/comfyui-minimax-h3-audio-T8/blob/main/learned_latent_upscale_advanced.py. Aucun test, import applicatif, génération, téléchargement de poids, changement de configuration ou service ; uniquement lecture des graphes/code et actualisation de cette continuité. Piste à discuter : recette de rendu expérimentale séparée pour comparer à résolution finale égale, puis variation de la résolution initiale ; pas de promesse de vitesse/qualité à partir du seul nombre de steps.

- **DLSS vidéo rapide et copie serveur autorisés puis implémentés, 2026-09-09** : H3/REF2V proposent **Upscale DLSS** (lancement direct **×1,724 + 60 FPS**, sans popup) et **Upscale avancé** (panneau existant, fermé après enregistrement de la tâche). Valeurs rapides fixes indépendantes des réglages avancés : HDR OFF, H.264 NVENC, NR/tone/structure/detail 1, skin -1, Default, repli permis. Suivi sous l’essai et indicateur global pendant navigation, sans bloquer les commandes de génération ou de prompt. Fin vidéo sans autosélection ; « Voir le résultat » recharge les essais et sélectionne explicitement la variante, sans remplacer le brouillon ou les réglages. Suivi génération H3 cible le dernier essai non-DLSS. Parcours image conservé.

- **Progression locale réelle** : `infrastructure/dlss_progress.py` observe les événements `progress`, `progress_state`, `executing` du client `panelforge-dlss`, avec filtrage strict de l’exécution. Abonnement avant soumission ; socket optionnelle, historique Comfy toujours autoritaire. Phases Upscale / Fluidification 60 FPS / Enregistrement dans les manifests, progression monotone par phase et horodatée dans le journal, temps écoulé affiché. Sans mesure, statut textuel ; pas de barre indéterminée ou de pourcentage global inventé. Les callbacks installés utilisent ProgressBar(1000) mais ignorent le message détaillé, donc pas de compte précis de frames promis. Statut `receiving` distingue téléchargement et import durable. Graphes et empreintes inchangés.

- **Export vidéo par défaut** : `--dlss-video-export-root X:\data\ComfyUI\output\video\Upscale`, puis dossier **YYYY-MM-DD** à la date locale du résultat prêt, MP4 et diagnostic JSON `dlss-<id>`. Lecture seule du montage confirmée : X: → `\\sshfs.r\malmo@bucket`, dossier demandé présent ; aucun chemin Linux supposé. Comfy conserve sa sortie `D:\AI\ComfyUI_windows_portable\ComfyUI\output\dlss`, puis assets PanelForge locaux. Worker de copie séparé, sans accès au partage pendant le bootstrap ni verrou de rendu/requêtes pendant le transfert ; fichier temporaire puis remplacement, contenu déjà identique conservé. Échec partage ne dégrade pas le candidat réussi ; « Réessayer la copie » / POST `/api/dlss/jobs/{id}/export` reprend seulement la copie avec date/chemin initiaux. Pas de migration des anciennes vidéos terminées ; aucun fichier réellement exporté pendant ce patch.

- **Livraison statique de cet ajustement** : tests simulés `tests/test_dlss_progress_export.py`, scénarios vidéo enrichis dans `tests/test_dlss_browser.py`, abonnement avant POST dans `tests/test_dlss.py`, bootstrap/cache adaptés ; **NON EXÉCUTÉS**. AST 243 Python, DLSS/H3 JS et quatre chaînes de fixture navigateur compilés sans invocation ; liaisons/empreintes/phases des trois manifests contrôlées. Guide `docs/dlss-local.md` actualisé, caches **DLSS/H3 rendu/CSS 20260909.2** ; core/Edit/Assisted restent 20260909.1. Aucun test, LLM, génération, chargement GPU, lancement/redémarrage/arrêt de service ou donnée runtime modifiée. Tag stable pré-masque conservé ; aucun commit/push.

- **Correctif de conversation H3 / REF2V, 2026-09-09** : audit de l’atelier `h3-render-ec42843919e0465bab7231a4fa5df502` et de `workspace/llm_calls.json`. Deux refus après vidéo : à 12:07 locale, `shake.slightly` avec amplitude/vitesse (56,934 s), puis à 12:20 avec cible `keeping the entire row of salamanders and her face in view` (74,432 s). Réparations explicites acceptées à 12:12 et 12:22 ; prompt actuel valide avec léger tremblement. Ce n’est pas un échec de Plan ni de génération vidéo. Contrat conversationnel incomplet sur les champs nuls et consigne « framing prose » ambiguë ; les traces montrent de longues hésitations sur visibilité/mouvement, sans prouver l’origine visuelle du zoom.

- Contrat commun de révision **0.2.0** complété : amplitude/vitesse nulles pour static/shake/POV, cible nulle pour shake/POV, exemple shake valide. Prose de composition explicitement permise (éléments visibles ensemble au moment pertinent), sans imposer static_shot ni réécrire un mouvement inchangé. Validateur conservé, messages de rejet indiquent les champs à corriger et où préserver la visibilité ; pas de suppression silencieuse ni appel automatique. Prompts historiques 0.1.0, recettes de préparation, compilateur et projets enregistrés inchangés. Guide `docs/h3-revision-camera-audit-2026-09-09.md`, tests simulés ajoutés à `H3RenderRevisionVersionTest`, **non exécutés** ; contrôle AST et diff seulement. Aucun LLM/rendu, test, redémarrage ou modification des traces/runtime.

- **DLSS local autorisé puis implémenté le 2026-09-09** : bouton commun dans Edit (KREA2 / FireRed), Assisted, H3 et REF2V, variantes Original / DLSS regroupées par essai, numérotation des générations conservée. Edit remplace son entrée d’amélioration principale et garde ESRGAN / ClearReality sous « Upscaler historique ». Taille source par défaut dans Edit : passe ×2 puis retour aux dimensions source et réapplication du masque/harmonisation enregistrés. Facteur explicite = finition de tout le candidat sélectionné, sortie réellement agrandie ; ancien masque disponible sur son candidat d’origine. Assisted ×2, vidéo ×1,5, cadence/audio conservés, option 60 FPS raccordée avant SaveVideo, HDR désactivé. Relance de variantes depuis l’original sans empiler DLSS ; feedback, continuation et export suivent le candidat exact et les frames de sa propre vidéo. Upgrades latents internes H3/REF2V/KREA2 Batch inchangés.

- **Moteur DLSS partagé** : endpoint local `http://127.0.0.1:8188`, racine `D:\AI\ComfyUI_windows_portable`, options `--dlss-base-url` / `--dlss-root`. Démarrage masqué à la demande, équivalent Python du BAT avec environnement FFmpeg/FFprobe, sans modifier le lanceur. Vérifie les nœuds requis et réutilise l’instance répondante. Aucune commande Unsloth ; Comfy reste ouvert. Panneau « DLSS local » : tâches, nettoyage mémoire, arrêt/redémarrage du seul processus possédé (PID + création + exécutable + endpoint), refus si file active, annulation ciblée. Journal atomique `<workspace>/dlss`, verrou système du worker, IDs persistés avant POST, reprise sans resoumission ambiguë ; échec terminal relançable explicitement. Import idempotent, résultat téléchargeable si étape Edit recommencée/validée pendant le traitement, rapport DLSS/fallback conservé dans les assets et exports.

- **Contrats DLSS** : trois manifests `image.upscale/dlss`, `video.upscale/dlss` et `video.upscale/dlss-smooth`, version `0.1.0`, seuls propriétaires des IDs de nœuds. Images orientées, limites natives et 16 MP de sortie image, dimensions/FPS/durée/audio contrôlés à l’import. Stockage Edit **11** (lecture 1–10), Assisted **8** (lecture 1–7), H3 **4** (lecture 1–3) ; provenance `dlss` distincte, sorties réussies sans exécution dans les files de génération. Caches CSS/core/DLSS/Edit/Assisted/H3 rendu **20260909.1**. Guide `docs/dlss-local.md`, proposition antérieure archivée.

- **Livraison DLSS sans essais runtime** : tests `test_dlss.py` / `test_dlss_browser.py` préparés, assertions schéma/cache/bootstrap adaptées, **NON EXÉCUTÉS**. Contrôles statiques : AST 240 Python, liaisons/empreintes des trois manifests, 913 IDs DOM uniques et 18 scripts présents ; compilation JS sans invocation et diff revérifiés à la livraison. Aucun test, LLM, génération, chargement de modèle, lancement/redémarrage de service, annulation réelle ou mesure VRAM. Tag `stable-avant-masque-2026-09-06` conservé sur `56840b877be4b810ee93f8afe9b2f0c40ee73006` ; pas de commit/push. Qualité, cadence/audio réels et coexistence Unsloth/Comfy à expérimenter par l’utilisateur.

- **Remplacement du collage Assisted autorisé et implémenté le 2026-09-08** : retrait du bouton, dialogue, Canvas et routes de création/reprise du masque **dans Assisted uniquement**. Les compositions déjà enregistrées restent lisibles au schéma Assisted 7, avec feedback/branches/presets/export ; aucun média existant supprimé. Le masque de l’atelier Edit est conservé. Ancien guide réduit à une note de retrait, compatibilité archivée testée par scénarios préparés (non exécutés).

- **Replacer dans un décor** sur un essai Assisted réussi : choix d’un autre essai, référence initiale ou import PNG/JPEG/WebP comme décor, deux aperçus, instruction ciblée éditable. **Ouvrir dans l’atelier Edit** prépare un atelier distinct de façon idempotente, sans LLM ni rendu automatique. Le défaut de la dernière base est mémorisé dans ce navigateur par atelier ; brouillons du dialogue dans l’onglet. Les nouvelles images de départ restent des générations Assisted ; la passe d’intégration et ses candidats sont dans Edit, avec ses outils existants et sans nouveau moteur de file.

- Nouvelle recette **`krea2.identity_edit@0.3.0` · Deux images · décor + sujet**, SHA `63643c41c4585cb9720beb14264e606d56c23c3ecf4c48e18bd736f5371f634e`. Décor sur image/source_latent/source_image, sujet sur image_b/source_latent_b/source_image_b ; positifs et négatifs ancrés dans les deux images, FIT + target_latent conservés. Anciennes 0.1.0/0.2.0 intactes, défaut général 0.2.0. Paire fixe par étape, choix de moteur/recette incompatible bloqué sans ignorer le sujet. Départ Turbo, 10 steps, CFG1, 1 MP modifiable, aucun LoRA de style hérité ; ratio disponible le plus proche du décor orienté. Ref boost sujet 4, force décor 1 fixe dans ce premier workflow et annoncée dans l’UI.

- Stockage Edit **schéma 10**, lecture 1–9. `EditSubjectReference` conserve l’asset et l’origine Assisted ; restart/reprise de version conservent cette référence. LLM et Comfy reçoivent les mêmes PNG orientés, feedback LLM séparé ; sortie mesurée à réception, export de la référence sujet et du candidat exact. Validation prépare ensuite une étape classique à une image, sans la seconde référence ni l’ancien prompt de placement. Pour une autre scène, revenir à Assisted et réutiliser le même décor maître. Pas de garantie de netteté ou de décor identique au pixel.

- Guide **`docs/krea2-restaging.md`** ; tests `test_krea2_restaging.py` et `test_krea2_restaging_browser.py` préparés, fixture navigateur FireRed enrichie et assertions schéma/cache/bootstrap adaptées, **NON EXÉCUTÉS**. Contrôles statiques : AST 230 fichiers Python, quatre JS + deux scénarios navigateur compilés sans invocation, IDs DOM/contrôles présents et anciens éléments masque Assisted absents, liaisons/valeurs/empreintes des trois workflows cohérentes, diff sans erreur. Caches Assisted **20260908.2**, restaging **20260908.1**, Edit **20260908.7**, CSS **20260908.3**. Aucun test, LLM, rendu, téléchargement, redémarrage, annulation ou donnée runtime modifiée ; pas de commit/push, tag stable pré-masque revérifié intact sur `56840b877be4b810ee93f8afe9b2f0c40ee73006`.

- **Retour utilisateur sur le masque Assisted, 2026-09-08 : résultat peu satisfaisant**. Les générations indépendantes s’accordent rarement au décor ; le collage dépend trop de leurs perspectives et positions respectives. L’utilisateur demande une alternative avec deux images dans Identity Edit (décor + nouvelle image Assisted), **discussion uniquement, aucune nouvelle implémentation autorisée dans ce tour**. Ne pas continuer à développer le collage comme solution principale sans nouvel accord.

- Vérification documentation officielle : [fiche du modèle](https://huggingface.co/conradlocke/krea2-identity-edit) et [nœuds](https://github.com/lbouaraba/comfyui-krea2edit). Cas entraîné à deux entrées confirmé : **scène image 1**, **sujet image 2**, ordre important. Fournir les deux images au patch visuel ET à l’encodage Qwen, pas seulement au LLM de prompting. Notre adaptateur `ValidatedKrea2EditWorkflow.build` et manifeste 0.2.0 n’exposent actuellement que `source_image` ; deuxième entrée non branchée. Aucune nécessité de remplacer Assisted pour créer les belles images de départ ; une passe Identity Edit facultative peut ensuite tenter leur intégration dans le décor.

- Piste proposée : action **Replacer dans un décor**, décor maître fixe (idéalement vide pour éviter l’ancien personnage) + image Assisted du personnage/action, instruction ciblée séparant architecture/caméra/lumière fixes et éléments évolutifs (personnage, accessoires, liquide/diamants au sol). Réutiliser le même décor maître pour chaque scène, sans chaîne de générations successivement rééditées. Insertion/relighting documentés ; conservation précise de la pose, des accessoires, du sol et de la netteté Assisted à expérimenter, sans promesse de collage exact ou de qualité identique. Recommander un essai manuel sur une paire avant d’élargir l’interface. Aucun test, LLM, génération ou modification runtime ; continuité uniquement actualisée.

- **Composition par masque dans KREA Assisted autorisée et implémentée le 2026-09-08** : l’utilisateur confirme que les nouvelles images viennent bien d’Assisted, pas d’Identity Edit. Action facultative **Composer avec une autre image** sur les essais réussis ; choix d’un autre essai de l’atelier, référence initiale ou PNG/JPEG/WebP importé comme base. Canvas partagé en pleine largeur, génération à gauche / résultat à droite, source consultable sans perte de masque, harmonisation facultative. Changer de base garde des brouillons séparés par paire dans l’onglet. Pas d’étape imposée, de segmentation ou de recalage automatique ; aucun changement du workflow génératif Assisted.

- **Enregistrer comme essai** crée `Essai N — Composition M`, garde les originaux/masque et revient à la galerie. Schéma Assisted **7**, lecture 1–6, type `generation`/`composition` ; résultat local réussi sans exécution ComfyUI, exclu de la file et du carillon de génération. Réouverture depuis la paire originale, nouvelle sauvegarde sans recomposition cumulative ; numérotation des générations indépendante. Dimensions de la base, orientation EXIF, tolérance de ratio 1 %, pixels décodés protégés hors masque. API import/préparation/sauvegarde idempotente, relecture sous verrou après composition pour préserver les échanges/rendus concurrents.

- La composition ne change pas le prompt, la conversation ou le feedback sélectionné. Feedback/export/preset utilisent son asset exact ; reprise de branche au checkpoint de sa génération d’origine avec la composition en feedback. Réglages/seed/prompt d’origine explicitement hérités ; sidecar local et export séparé de la base/génération/masque. Guide `docs/krea2-assisted-composition.md`. Caches JS Assisted/composition/Canvas **20260908.1**, CSS **20260908.2**, Edit reste **20260908.6**. Proposition précédente ci-dessous désormais réalisée dans ce périmètre ; pièce vide et aide de recalage restent des pistes éventuelles.

- Tests `test_krea2_assisted_composition.py` et `test_krea2_assisted_composition_browser.py` préparés, compatibilité/cache existants actualisés, **NON EXÉCUTÉS**. Contrôles statiques : AST de 229 fichiers Python, quatre JS et scénario navigateur compilés sans invocation, IDs DOM et contrôles Canvas complets, ordre des scripts vérifié, diff sans erreur. Aucun appel LLM, génération, fonction applicative, test, téléchargement, redémarrage ou donnée runtime modifiée. Pas de commit/push ; tag `stable-avant-masque-2026-09-06` revérifié sur `56840b877be4b810ee93f8afe9b2f0c40ee73006`.

- **Discussion décor constant dans Assisted, 2026-09-08 — pas d’implémentation demandée à ce stade** : scénario princesse verse du liquide, l’étale au balai puis ajoute des diamants. L’utilisateur préfère la qualité HD d’Assisted aux moteurs Edit ; souhaite reprendre le décor de l’image à droite (Essai 7, versement) pour les autres (dont Essai 8, coffre/diamants). Inspection : les images d’inspiration Assisted vont au LLM, pas au workflow de génération ; le compositeur Pillow et le Canvas Edit sont réutilisables mais non raccordés à Assisted. Proposition : action facultative « Composer avec une autre image », choix d’une base, même UI Image 2 / Résultat avec masque, source consultable, sauvegarde d’un candidat distinct sans repasse générative. Distinguer décor fixe (architecture) et éléments évolutifs (princesse, outils, sol/liquide/diamants, ombres/reflets). Limites à expliquer : masque sans recalage ne corrige pas une perspective différente ni les portions de mur cachées par l’ancienne princesse ; une version vide validée une seule fois du décor éviterait les restes du personnage d’origine. Éventuelle aide de superposition pour examiner l’alignement, à discuter ; aucune nouvelle étape imposée ou segmentation automatique engagée. Lecture locale et note seulement, aucun test, appel LLM, rendu ou modification de l’interface.

- **FireRed Image Edit 1.1 autorisé et implémenté le 2026-09-08** : sélecteur Moteur dans les paramètres du même atelier Edit. Lightning 8 steps / CFG1 par défaut, Standard 40 / CFG4 ; mode change les valeurs proposées, steps/CFG/MP restent modifiables. **1 MP par défaut confirmé**, ratio source conservé, source originale intacte, redimensionnement Lanczos dans le graphe. Réglages et brouillons indépendants par moteur dans l’onglet ; changement sans LLM ni rendu automatique, prompt/conversation/masque conservés. Ref boost et LoRA KREA2 exclus de FireRed. Reprise d’essai et étape suivante restaurent son moteur et ses paramètres ; anciens parcours KREA2 conservés.

- Recette `firered.image_edit@0.1.0`, graphe fourni copié exactement, SHA `dd1e6ea1668edb64de057e1dc900dfe3fd2951685e2f91dd2d7cbc5fd6456660`, composants et nœuds dans le manifeste dédié. Port de workflow commun, paramètres FireRed explicites ; API transmet ID+version afin d’éviter la collision avec KREA2 `0.1.0`. Pillow normalise l’orientation de l’entrée et lit les dimensions du PNG réussi, aussi en récupération détachée. Schéma Edit **9**, lit 1–8 ; profil LLM `firered.edit.conversation@1.0.0` partage V3 avec une cible adaptée, moteur enregistré dans les révisions. Métadonnées natives du graphe connu et sidecars FireRed récupérables. Masque/upscale/feedback/validation/frise/export raccordés au candidat sélectionné et à la provenance du rendu initial.

- Guide `docs/firered-edit.md`, audit précédent relié au patch. Tests `test_firered_edit.py` et `test_firered_edit_browser.py` préparés, fixtures existantes ajustées au schéma/cache/bootstrap ; **NON EXÉCUTÉS**. Contrôles statiques uniquement, aucune invocation de l’application, LLM, génération, téléchargement, annulation ou redémarrage. Cache Edit JS **20260908.6** ; pas de commit/push ni modification du tag stable pré-masque. Qualité réelle, performances et comparaison des MP restent à expérimenter par l’utilisateur. Les trois points d’audit/alignement ci-dessous décrivent l’état antérieur à cette implémentation.

- Vérification statique FireRed : 225 fichiers Python lisibles par AST, JS Edit et deux scénarios navigateur compilés sans invocation ; IDs DOM sans doublon ni référence manquante, champs HTTP utilisés déclarés, liaisons manifeste présentes, snapshot identique au fichier utilisateur. `git diff --check` sans erreur ; tag stable résolu sur `56840b877be4b810ee93f8afe9b2f0c40ee73006`. Ces vérifications ne constituent pas une exécution des tests ni une validation du rendu réel.

- **Alignement FireRed confirmé le 2026-09-08** : l’utilisateur accepte l’idée d’intégration et la réduction à **1 MP**. Retenir 1 MP comme défaut FireRed dans le champ MP modifiable déjà proposé, ratio source conservé ; garder l’image originale, redimensionner seulement l’entrée du moteur. Reproduire d’abord le workflow dont les résultats lui plaisent, sans upscale automatique ni promesse que 1 MP soit optimal. Choix noté dans l’audit ; intégration toujours non implémentée, aucun test ou appel modèle réalisé pour cette discussion.

- **Audit FireRed Edit du 2026-09-08**, demandé comme analyse, intégration **non implémentée** : `C:\Users\samue\Downloads\image_firered_image_edit1_1.json`, 22 nœuds/17 classes, SHA `dd1e6ea1668edb64de057e1dc900dfe3fd2951685e2f91dd2d7cbc5fd6456660`. FireRed Image Edit 1.1 + Qwen2.5-VL 7B fp8 + VAE Qwen Image ; Lightning 8 steps / CFG1 activé, branche Standard 40 steps / CFG4 sans LoRA, shift3.1, CFGNorm1, Euler/Simple/denoise1. Source redimensionnée Lanczos 1 MP ratio conservé, encodage image+prompt et latent VAE, PNG natif sans upscale. Ref boost et LoRA Identity absents. Les 17 classes et quatre fichiers exacts sont annoncés par les GET de descriptions ComfyUI ; aucun modèle exécuté/téléchargé, service relancé, validation de prompt ou donnée runtime modifiée.

- Guide `docs/firered-edit-audit-2026-09-08.md` : proposition de sélecteur **Moteur KREA2 / FireRed 1.1** dans le même atelier, deux modes FireRed, MP/seed, réglages par moteur, conversation/essais/comparateur/masque/upscale/frise partagés. Writer V3 peut fournir le socle d’un petit profil FireRed ; aucun appel automatique au switch. Adaptateur/manifeste dédiés, identité recette+version (sélection actuelle uniquement par version), paramètres et dimensions propres au moteur à persister, anciens projets à préserver. Ne pas traiter FireRed comme un checkpoint KREA2 ni hériter de ses LoRA/Ref boost. Le réglage 1 MP n’est pas une limite de modèle établie ; flou/détails à comparer, pas de gain de qualité déduit du graphe. Documentation officielle FireRed consultée ; conserver le Lightning exact fourni malgré d’autres versions publiées. Audit/documentation uniquement, aucun test lancé.

- Ref boost Edit **élargi à la demande de l’utilisateur le 2026-09-08** : plage **0–1000** au lieu de 0–10, pas UI 0,1. Borne native 1000 confirmée par un GET en lecture seule de `/object_info/Krea2EditModelPatch` sur Bucket. Constante commune domaine/spec ; validation des réglages **et** des métadonnées de la prochaine étape alignée, champ HTML mis à jour. Workflows, valeurs par défaut, schéma de stockage et JS inchangés (cache Edit reste 20260908.5). Tests existants enrichis pour transmission de 1000 au workflow 0.1.0, 25,5 au workflow 0.2.0, acceptation/persistance HTTP et héritage après validation ; **NON EXÉCUTÉS**. Contrôles statiques seulement, aucun LLM, rendu, redémarrage ou donnée runtime modifié.

- Chargement de **Modifier avec KREA2**, patch du **2026-09-08** : l’utilisateur a précisé que « 3 historiques » concerne uniquement les **ateliers à gauche**, pas les essais de l’étape. Trois familles récentes visibles par défaut ; **Afficher les autres ateliers (N)** charge la suite à la demande, **Afficher seulement les 3 récents** replie sans changer le travail ouvert. API `sources?project_limit=3&project_id=…`, limite par atelier et chaînes complètes ; version ouverte conservée en plus des trois, même historique. Une lecture globale de stockage pour sélection/versions au lieu des relectures de l’ancienne liste ; seules les chaînes retenues sont sérialisées et leurs exécutions détachées rafraîchies. Ancien contrat sans `project_limit` intact. Frise, essais, conversation, mémoire, générations et stockage inchangés. Auto-ouverture du projet le plus récent, au lieu de l’étape de rang maximal tous ateliers confondus. Chargements périmés écartés ; reprise d’étape charge explicitement toute la nouvelle version.

- Inspection locale en lecture seule : 62 sources d’étapes, 267 essais, 82 révisions, environ 1,44 Mo de JSON source au moment de l’audit. Cela ne mesure pas la durée d’ouverture ; catalogue modèles initial inchangé. Cache Edit JS **20260908.5**, guide `docs/krea2-edit-and-presets.md` actualisé. Tests HTTP/versions/navigation étendus et scénario `test_krea2_edit_backlog_browser.py` ajouté, **NON EXÉCUTÉS**. Six fichiers Python analysés par AST, JS Edit et deux scénarios navigateur compilés sans invocation ; diff vérifié. Aucun appel LLM, génération, redémarrage, donnée runtime, commit ou tag modifié ; tag stable pré-masque revérifié intact.

- Diagnostic « Aucun modèle Unsloth » du **2026-09-08** : premier GET du spec Edit Lab 7861 annonce 30 modèles serveur et aucun local ; llama.swap Bucket répond. Unsloth écoute sur 127.0.0.1:8888 et un processus llama-server local existe ; GET `/v1/models` avec la valeur de remplacement du Lab (`panelforge-local-unconfigured`, faute de clé dans l'environnement de l'agent) renvoie **401 authentication_error / Invalid token payload**. Le routeur masque toute erreur d'une source, expliquant le message générique. Aucune clé présente dans l'environnement de l'agent ni dans les variables Windows User/Machine ; cela ne prouve pas son absence dans l'environnement du processus Lab. Ce dernier s'est arrêté pendant le diagnostic : port 7861 ensuite fermé, aucun arrêt/redémarrage effectué par l'agent. Reconfiguration de la clé API au lancement à vérifier par l'utilisateur. Aucun secret lu/affiché, modèle chargé, appel LLM, test, code runtime ou service modifié.

- Upscaler KREA2 Edit **autorisé puis implémenté le 2026-09-08** : bouton **Améliorer les détails** sous le comparateur, panneau facultatif avec modèle replié (ClearReality par défaut si disponible), lancement explicite, progression indéterminée et suivi/carillon existants. Nouveau candidat `upscale`, label parent + « Amélioré N », automatiquement dans Après à la fin, parent dans Avant ; aucune étape ajoutée avant validation. Prompt, réglages de génération et brouillons conservés. Masque/harmonisation enregistrés réappliqués après amélioration de la génération initiale ; reprise du masque utilise l'amélioration avant composition. Changement d'upscaler repart toujours du rendu initial, sans accumulation de passes. Étapes validées immuables.

- Upscale : graphe `image.esrgan.upscale@0.1.0` (LoadImage/UpscaleModelLoader/ImageUpscaleWithModel/ImageScale/SaveImage), cinq nœuds natifs, SHA `3308cc9a46b17065e100bd04dbbf472c9552c658eaf19fd5970aa849a2f8c782`, contrat lié par manifeste ; aucun sampling KREA2/LLM. Entrée à résolution native, sortie exacte aux dimensions orientées de la source, règles de masque/proportions existantes. Catalogue lu par GET à l'ouverture du panneau ; API POST avec demande idempotente. Réutilisation du cycle de rendu Edit (une exécution active), suivi après navigation et récupération des IDs d'exécution conservés. Schéma **8**, lit 1–7 ; paramètres/recette Edit hérités séparés de la provenance d'upscale. Feedback/validation/frise/export utilisent la sortie choisie ; fichiers de provenance préservés à l'export et lors de la reprise d'étape.

- Guide `docs/krea2-edit-upscale.md`, nouveaux tests `test_krea2_upscale.py` et `test_krea2_upscale_browser.py`, fixtures navigateur/cache/schéma existantes ajustées ; **NON EXÉCUTÉS**. Contrôles statiques AST, JS et trois fixtures navigateur compilés sans invocation, IDs HTML/champs HTTP/manifeste contrôlés. Trois GET de descriptions de nœuds ComfyUI ont confirmé les contrats et les modèles annoncés ; aucun appel LLM, génération, test, téléchargement, redémarrage ni donnée runtime modifiée. Cache Edit JS **20260908.4**, CSS **20260908.1**. Aucun commit/push ; tag stable pré-masque conservé. Qualité visuelle à évaluer par l'utilisateur.

- Correctif HTTP 500 KREA2 Edit du **2026-09-08** : l'ajout précédent de `workflow_version` était placé par erreur dans `Krea2AssistedAttemptBody`, alors que la route Edit le lisait sur `Krea2EditAttemptBody`. Champ déplacé dans le contrat Edit (`str | None = None`), champ inutilisé retiré du contrat Assisted. Requête sans version compatible avec le workflow courant ; choix explicite 0.1.0/0.2.0 transmis au service. Test HTTP existant étendu aux deux versions, champ omis/null, persistance, statut created et version inconnue 422 sans nouvel essai ni soumission/LLM ; **NON EXÉCUTÉ**. Deux fichiers analysés par AST et attributs du body lus par la route vérifiés contre ses champs déclarés ; aucune donnée runtime, génération ou service touché. Redémarrage du Lab par l'utilisateur nécessaire pour charger le modèle Pydantic corrigé. Aucun changement frontend/cache ; piste upscaler conservée en réflexion.

- Discussion flou / second passage du **2026-09-08**, aucune implémentation demandée : dimensions relues directement dans quatre images de la chaîne pelouse/Vegeta, sources/retouches 1664×2960 (4.925 MP), générations 1112×1976 (2.197 MP). L'agrandissement à la composition ne restaure pas les détails ; la dérive de texture liée aux éditions reste une autre hypothèse, sans comparaison contrôlée. Derniers essais retrouvés en workflow 0.1.0, Turbo/10/CFG1/Ref boost1/sans LoRA facultatif ; l'étape active change pendant l'inspection (réinitialisation), aucune donnée runtime modifiée. Pas de résultat permettant ici de qualifier 0.2.0. Documentation auteur relue : recommandation ≤2 MP, corrections de géométrie déjà constatées lors de l'audit précédent. GET UpscaleModelLoader seul : modèles annoncés `4x-ClearRealityV1.pth`, `4x_NMKD-Siax_200k.pth`, `remacri_original.safetensors`, `1xSkinContrast-High-SuperUltraCompact.pth`, `RealESRGAN_x4plus_anime_6B.pth` ; présence au catalogue ne prouve pas qualité/chargement. Proposition à discuter : upscaler spécialisé sur la génération sélectionnée, retour aux dimensions source puis harmonisation/masque ; conserver les pixels de source hors masque et l'original. Second passage KREA2 génératif seulement comme expérience distincte, car une nouvelle édition peut réinterpréter la scène. Aucun test, LLM, génération, téléchargement, redémarrage ou réglage modifié.

- Workflow KREA2 Edit **fourni puis autorisé le 2026-09-08** : `C:\Users\samue\Downloads\krea2_identity_edit_new_start.json`, import exact dans `workflows/image.edit/krea2-identity/0.2.0/`, SHA `7f9e066f4ac3bee9b9aa5aa1cb2765d724b8851bc18b11303d5f673912184a19`. Principaux écarts : encodeur Qwen3VL standard bf16 au lieu de Heretic, défaut Turbo bf16/Ref boost 4, SaveImage natif. Géométrie FIT + image/VAE/target_latent, multiple 8, grounding 768, Euler/Simple/CFG1/denoise1 inchangés. Modèles standard disponibles sur Bucket via deux GET de définitions seulement. Graphe fourni sans LoRA facultatif ; manifeste V2 décrit leur insertion uniquement si sélection, jusqu'à dix. Ancienne version 0.1.0 intacte et chargée explicitement avec la nouvelle.

- Rendu Edit : sélecteur **Workflow**, base importée 0.2.0 par défaut pour nouveaux essais ordinaires même dans une ancienne étape active ; valeurs affichées de modèle/Ref boost etc conservées. Bouton **Reprendre les réglages de base** remet checkpoint/Ref boost/steps et retire les LoRA facultatifs ; garde prompt, ratio, MP et seed. Reprendre un essai restaure sa version ; lecture historique affiche sa version exacte. Chaque nouvel essai porte sa référence complète ; anciens essais sans référence résolus depuis la source. File/exécution/récupération détachée, retouche, validation et export utilisent la référence de l'essai. Schéma Edit **7**, lecture 1–6 ; pas de migration runtime globale. Native SaveImage sans `.txt` ComfyUI, provenance locale et export JSON conservés. API catalogue de workflows, défauts issus du manifeste et version par essai. Cache Edit JS **20260908.3** ; prompting V2/V3 inchangé.

- Guide `docs/krea2-edit-workflow-base-2026-09-08.md`. Tests `test_krea2_edit_workflows.py`, HTTP, retouche, navigateur et bootstrap préparés/étendus, **NON EXÉCUTÉS**. Contrôles statiques : 12 fichiers Python AST, JS et fixture navigateur compilés sans invocation, graphes/manifeste lisibles avec empreintes/liaisons correctes, snapshot égal au fichier fourni. Aucun appel LLM, génération, test, mise à jour de nœuds, redémarrage ou donnée runtime modifiée. Qualité à juger par l'utilisateur ; aucun commit/publication.

- Prompting **KREA2 Edit V3 autorisé puis implémenté le 2026-09-08** : module séparé `application/krea2_edit_assistance_v3.py`, opération `krea2.edit.conversation@3.0.0`. Instructions ciblées relatives à la source fixe, maintien de tous les changements encore souhaités de l'étape, remplacement concret pour suppressions, quelques invariants, description de source distinguée d'une cible même lorsque l'UI renvoie les métadonnées comme base. Source et feedback restent distincts ; JSON message français/prompt, six échanges récents, un appel et limites existantes conservés. Instructions courtes admises uniquement en V3 ; V1/V2 et leurs minima inchangés. Ancien module V2 intact, version persistée dans le champ existant, schéma 6 inchangé. Aucun réglage, MP, géométrie, workflow ni upscaling modifié.

- UI Edit : **Version du prompting**, V3 « Modifications ciblées » / V2 « Description complète ». Nouvel atelier par défaut V3 ; étape existante reprend dernière révision, nouvelle étape hérite du dernier échange parent sinon V3. Choix avant envoi gardé en mémoire d'onglet, version enregistrée après réussite ; aucune génération ni réécriture au changement du sélecteur. Version affichée avec chaque prompt dans l'historique ; ancienne V1 affichée seulement pour reprise historique. Échec garde prompt/instruction/choix. Cache Edit JS **20260908.2**. Guide `docs/krea2-edit-prompting.md`, guides de versions/atelier actualisés.

- Tests V3 préparés dans `test_krea2_edit_assistance_v3.py`, HTTP et scénario navigateur existants étendus ; **NON EXÉCUTÉS**. Contrôles statiques : AST de six fichiers Python et compilation sans invocation du JS Edit et de la fixture navigateur. Aucun LLM, rendu, test, redémarrage ou état runtime touché. Comparaison visuelle à faire par l'utilisateur ; ancien prompt V2 et workflow Identity Edit toujours sans diff. Tag stable pré-masque conservé ; pas de commit/publication.

- Précisions Identity Edit du **2026-09-08** : l'utilisateur accepte la direction de prompting, exige de **garder l'ancienne version accessible pour comparaison**, remet les réglages à discussion et demande de conserver les résolutions actuelles ; upscaling en réflexion uniquement. Demande immédiate : point sur le flou/géométrie de l'auteur, documenté dans le complément de `docs/krea2-identity-edit-audit-2026-09-08.md`. Ancienne interpolation des latents susceptible de ramollir l'image ; chemin pixels puis VAE déjà activé chez nous (`source_image` + `vae` + FIT). Fichiers installés contiennent les corrections 1.2.4 de compression/centrage ; `target_latent` sert surtout à éviter le pré-encodage pendant le sampling. Ratios source/rendu récents presque identiques (écart 0.105 %) : pas le cas typique de bande de référence lors d'un grand changement de format. Multiple 8→16 reste une comparaison possible, pas un correctif prouvé ; aucune valeur modifiée. Documentation/continuité seules modifiées, aucun test/rendu/LLM/redémarrage.

- Audit KREA2 Identity Edit du **2026-09-08**, sans implémentation : `docs/krea2-identity-edit-audit-2026-09-08.md`. Version Civitai `3139172` = v1.2 confirmée via API ; recommandations croisées avec les sources de l'auteur. Sur Bucket, fichiers des nœuds **1.2.5**, commit `86f886d` ; workflow récent utilise bien FIT + source image/VAE + target_latent, LoRA v1.2 ×1. Pas de mise à jour évidente à faire. Écart principal : writer Edit V2 exige une description complète, avec 528 mots pour retirer une tache de peinture dans l'atelier pelouse/Vegeta. Turbo/10/CFG1 sans LoRA facultatif conforme aux éditions courantes ; CFG fixe empêche la recette Raw/20/CFG3 recommandée pour suppressions. Grounding 768 fixe ; multiple 8 à comparer à 16, sans prétendre que les anciens témoignages v1.1 prouvent un défaut actuel. Source 1664×2960 (4.925 MP), rendu 1112×1976 (2.197 MP, 2.1 demandé), puis retouche agrandie ×1.5 aux dimensions source : risque de contraste de détails dans la zone peinte. Priorités proposées : prompt d'édition ciblé et cumulatif depuis la source fixe, réglages Turbo/Raw cohérents, lisibilité des dimensions réelles. Sources/runs/images lus uniquement ; aucun test, appel LLM, génération, réglage, nœud ou service modifié.

- H3 multi-plan **autorisé puis implémenté le 2026-09-08** : recettes `minimax.h3.fl2va.direct.multishot.{guided,planned,prompt}@1.0.0`, profil multi-plan `0.2.0` et Direction créative `0.3.0`. Trois parcours 3/2/1 appels, tous en first seule, last seule, first+last ou texte seul. Blocs partagés `h3-multishot/1.0.0`, consignes adaptées au stade de décision, writer identique pour 2/3 étapes. Invariants séparés des changements demandés, état accumulé transmis entre plans, gestes transformateurs visibles, coupes temporelles au même cadrage permises, ellipse possible des préparatifs. Aucun nouvel angle ou gel final systématique imposé.

- Contrat Plan multi-plan V2 réutilise le schéma détaillé V1, ajuste les durées proportionnellement sans ajouter une tenue et retire les avertissements de cadrage répété/absence de tenue. Nouveau `application/h3_multishot_preparation.py` : contrat direct compact avec 2–4 shots (durée, composition initiale, caméra, prose), état final, dialogues et sons ; aucun Plan synthétique/appel intermédiaire. Compilateur partagé : contexte payload V2 `cut_policy: neutral`, coupe sans « new view », lecture/encodage V1 conservés. Révisions protègent découpage, horloges, références, caméras et dialogues ; régénération directe peut changer le nombre de plans, échec garde la révision précédente. Rendu/workflows ComfyUI et stockage des compositions inchangés.

- UI H3 : **Type de séquence Mono-plan / Multi-plan**, puis **Préparation** avec trois recettes courantes par famille. Le changement de famille conserve le nombre d'étapes choisi, les runs existants restent sur leur recette, ancienne multi-plan `0.1.0` dans historique. Défaut initial mono guidée `1.1.0` conservé. La reprise de dernière frame lit désormais la recette du rendu source et la conserve, même si un autre parcours est affiché ; nouvelle first, ancienne last/intention retirées. Lecture échouée/navigation périmée/recette multi manquante ne remplacent pas le travail courant. Caches core/H3 préparation/H3 rendu **20260908.1**.

- Guide `docs/h3-multishot-preparation.md`, guide général actualisé ; tests `test_h3_multishot_preparation.py` / `test_h3_multishot_browser.py` préparés, helper et sélecteur/cache existants actualisés, **NON EXÉCUTÉS**. Contrôles statiques effectués : AST 9 Python, compilation sans invocation de 3 JS et 2 fixtures navigateur, 3 recettes avec dépendances versionnées lisibles, 889 IDs HTML uniques et caches cohérents. Libellés/préambules UTF-8 rétablis après détection d'une conversion ASCII par le pipe PowerShell. Aucun appel LLM, génération, test, son, annulation, redémarrage ni donnée runtime modifiée. Ancienne recette/profil multi-plan intacts ; tag `stable-avant-masque-2026-09-06` toujours sur `56840b877be4b810ee93f8afe9b2f0c40ee73006`. Aucun commit/publication demandé ou effectué. Qualité des transitions/transformations à évaluer par l'utilisateur.

- Précision utilisateur H3 multi-plan du **2026-09-08** : priorité aux entrées first seule / last / first+last, T2V souhaité mais secondaire, pour chacun des parcours 1/2/3 appels. Exemple visuel fourni : femme en robe rose verse une matière rose scintillante, puis l'étale avec un balai/raclette de diamant dans le même cadrage ; reprendre une frame obtenue et poursuivre par ajout/répartition de diamants. Les images suivantes illustrent surtout les états souhaités : le modèle vidéo doit pouvoir les inventer depuis la première image et l'intention, sans imposer une last frame fournie. Reprise successive de clips avec changements d'état forts, pas seulement plusieurs angles d'une action inchangée.

- Ajustement de conception **non implémenté** : autoriser explicitement les coupes temporelles au même cadrage et les changements demandés d'outil/état, distinguer les invariants (femme, robe, pièce, lumière, caméra demandée) des transformations (répartition de matière, outils, diamants). L'ancien compilateur H3 multi-plan ajoute systématiquement `the camera cuts to a new view.` après le premier plan ; à adapter dans une nouvelle version pour ne pas suggérer un nouvel angle lorsqu'on conserve le cadrage. Les warnings de composition répétée doivent tenir compte du changement d'état. Préserver les gestes transformateurs visibles, autoriser les ellipses de préparation quand pertinentes, décrire un état final observable sans hold imposé. Réutiliser la reprise existante depuis la dernière frame en conservant la nouvelle recette multi-plan ; aucun moteur de montage/automatisation supplémentaire demandé. Inspection locale des prompts/compilateur/bouton seulement, aucune génération ou capacité visuelle H3 vérifiée, aucun code runtime modifié.

- Discussion H3 multi-plan du **2026-09-08**, audit du code seulement : les trois parcours récents H3 `1.1.0` sont mono-plan, mais `minimax.h3.fl2va.direct.multishot@0.1.0` existe dans **Autres recettes → Avancées et spécialisées**. Ancien parcours Brief → Plan → Prompt, 2 à 4 plans, durées/caméra/continuité par plan ; compilateur propriétaire des coupes, horloges, références first/last et dialogues, atelier de rendu H3 partagé. First = début du premier plan, Last = fin du dernier ; aucun slot d'image intermédiaire. Anciennes consignes de Brief (deux phrases par section) et avertissements de tenue finale antérieurs aux améliorations causales mono 1.1.0.

- Proposition **à discuter, non implémentée** : décliner le multi-plan en trois nouvelles recettes versionnées, 3 appels Brief/découpage/rédaction, 2 appels découpage direct/rédaction commune, 1 appel avec sortie compacte par plan (durée, caméra, texte) puis compilation locale. Partager les principes de causalité/continuité et le compilateur, adapter les consignes au contexte de chaque étape ; ne pas imposer au parcours direct tout le schéma détaillé de Plan. Séparer dans l'UI type de séquence Mono/Multi et préparation 1/2/3 étapes, sans liste plate supplémentaire. Première cible = un clip avec 2–4 plans, réutilisant le rendu existant ; nombre de plans distinct du nombre d'appels. Une action de travaux peut comporter plusieurs phases dans un seul plan ; une coupe peut aussi masquer une opération, donc conserver les transformations importantes visibles et n'autoriser les ellipses que si souhaitées. Qualité des coupes/continuité non évaluée ici ; aucun test, LLM, génération, service, recette ou code runtime modifié.

- Indicateur sonore de fin des rendus **implémenté le 2026-09-07** à la demande de l'utilisateur : carillon trois notes distinct du bip LLM, moteur Web Audio existant dans `lab-core.js`, déclenché par les états de réussite reçus par l'UI. H3/Ref2V, Assisted, Edit (générations seulement), KREA simple/Batch, Changer de vue, Video Lab et Production V1/V2 raccordés. Une fois par rendu dans l'onglet, historique initial silencieux, états périmés dédoublonnés, nouveaux résultats entre deux polls détectés ; succès simultanés regroupés sur 120 ms. Retouches locales, échecs et annulations sans carillon de succès ; sons LLM/échec existants conservés, ancien bip global de rendu Production/Batch remplacé pour éviter le double signal.

- Audio : aucune dépendance, option, surveillance globale ou requête serveur ajoutée ; respecte le suivi existant et l'autorisation audio souris/clavier. Page ouverte requise. Guide `docs/render-notifications.md`, dix caches JS concernés `20260907.8`. Test `test_render_notifications.py` avec AudioContext simulé préparé, assertions UI/cache actualisées, **NON EXÉCUTÉS**. Dix JS et scénario audio compilés sans invocation ; aucun son joué, appel LLM, génération, annulation, redémarrage ni donnée runtime modifiée. Le tag stable pré-masque reste intact.

- H3 phases causales **implémenté à la demande de l'utilisateur le 2026-09-07** : trois recettes `minimax.h3.fl2va.direct.{guided,planned,prompt}@1.1.0`, défaut UI guidé 3 étapes ; H3 1.0.0 dans historique, anciens runs/recettes/prompts inchangés, Ref2V inchangé. Profil H3 `0.5.0`, Brief standard + Direction créative `0.3.0`, blocs partagés `video-preparation/1.1.0`. Déduire les opérations nécessaires à partir des états visibles, accélérer les gestes sans supprimer les prérequis, conserver éléments existants et gravats finaux ; contexte de décision adapté à 3/2/1 appels, writer commun aux deux parcours avec Plan. Révisions/arbitrages incluent les règles, aucune étape/appel supplémentaire. Guide `docs/video-preparation-recipes.md` actualisé.

- Nouveau contrat H3 `minimax.h3.fl2va.direct_compact_h3_v5` pour les deux parcours avec Plan, même JSON V4, nouveau module `application/h3_phase_plan.py`. La ressemblance locale à la dernière frame avant la coupure donne un avertissement, pas un refus ; blocage limité aux arrêts explicites de toute la scène ou du sujet nommé par le mouvement final à la coupure. Ancien validateur inchangé pour anciennes versions et Ref2V. Contrôles structurels et recoveries V4 conservés ; pas de compréhension physique générale prétendue. Direct conserve le contrat à quatre champs sans Plan. UI sélectionne la variante de Brief selon le profil et verrouille le changement de profil d'un run existant. Caches core/H3 préparation `20260907.3`.

- Tests H3 `test_h3_causal_recipes.py` préparés, helper de parcours versionné et tests sélecteur/cache actualisés, **NON EXÉCUTÉS**. Contrôles statiques seulement : AST de six Python, compilation sans invocation de core/H3 JS et du scénario sélecteur, nouvelles dépendances de templates/profil toutes lisibles, HTML 888 IDs uniques, JSON nouveaux lisibles et diff sans erreur. Arrêts temporaires/avec exception explicite traités en avertissement ; pas de blocage sémantique général. Aucun appel LLM, génération, annulation, redémarrage, projet runtime ou commit ; tag stable pré-masque conservé. Validation de qualité et tests à la main de l'utilisateur.

- Audit H3 travaux du 2026-09-07 demandé par l'utilisateur : direct `prompt-095b6a23c42d404bae50ee0d4a54d14c` et guidé `prompt-43f98cac12d348d8beb2a701d12f414f`, mêmes deux frames inspectées, mur plein → ouverture/parement/gravats. Direct 27,563 s ; guidé Brief 55,729 s, Plan refusé 69,617 s, relance acceptée 72,152 s, prompt 19,248 s. Faux positif lexical du validateur : niche qui « matches the final frame » à 6,2 s alors que l'ouvrier sort ensuite et les nuages continuent ; « identical in form to the last frame » passe à chronologie proche. Le Brief puis le Plan omettent le creusement et choisissent seulement la pose de pierres ; le Plan accepté explicite même un retrait hors champ. Le chemin est déjà partiellement pavé dans les deux anchors. Guide `docs/h3-travaux-audit-2026-09-07.md` : distinguer fin d'un sous-élément et mouvement global, déduire les prérequis matériels au stade de décision des trois recettes, réserver les limites d'ajouts aux embellissements. Diagnostic seulement : aucun code/recette, donnée runtime, test, LLM, génération ou service modifié ; vidéos non visionnées. Le bouton de reprise Edit signalé absent au tour précédent a été retrouvé par l'utilisateur (« c'est bon »), aucun correctif ajouté pour ce point.

- Reprise d'étape KREA2 Edit **implémentée à la demande de l'utilisateur le 2026-09-07** : bouton **Reprendre depuis cette étape** sur une étape validée, copie de travail au même rang avec source, conversation, essais et réglages/prompt exacts du candidat validé. Sélecteur **Version du parcours** au-dessus de la frise ; brouillons de formulaire/masque de l'onglet restent séparés par source. L'ancienne chaîne reste active pendant les essais. À validation, la nouvelle version devient active et la suite repart sur le candidat choisi avec mémoire/essais vides. Anciennes versions consultables, y compris leurs étapes non validées désormais en lecture seule ; aucun effacement ni recalcul automatique.

- Versions Edit : schéma source **6**, lecture 1–5 conservée. `revision` (famille, numéro, origine, clé de reprise), `copied_from_source_id`, `revision_activation` ; chaque version a un `project_id` distinct, préfixe copié en métadonnées avec assets immuables partagés. Racine publiée en dernier : copie partielle invisible et reprise idempotente. Activation persistée sur l'étape corrigée ; dernière validation gagnante même si les brouillons ont été créés dans un autre ordre. Anciennes sources non réécrites pour les archiver. Gardes backend contre modifications d'une version historique et contre bascule pendant un LLM/rendu actif dans la version précédente ; retouches tardives refusées avant création d'assets. Export dans un dossier distinct, chaîne vérifiée par liens parent/image, provenance conservée. Aucun ancien projet runtime modifié pendant l'implémentation.

- API `POST .../sources/{source_id}/resume` avec `request_id`, `GET .../projects/{project_id}` pour une chaîne complète ; listes/lectures exposent les versions. Navigation/polling périmés invalidés, échec de reprise garde la même clé et les brouillons. Guide `docs/krea2-edit-versions.md`, caches Edit JS `20260907.5` / CSS `20260907.6`. Tests backend/HTTP/navigation préparés et contrôles masque existants étendus, **NON EXÉCUTÉS**. Contrôles statiques : AST 14 fichiers Python, HTML équilibré/888 IDs uniques, JS Edit et deux scénarios navigateur compilés sans invocation. Aucun appel LLM, génération, annulation, redémarrage ou commit ; tag `stable-avant-masque-2026-09-06` conservé.

- KREA2 Assisted V3 **implémentée à la demande de l'utilisateur le 2026-09-07** : recette `3.0.0`, label « V3 · corrections visuelles · expérimental », défaut des nouveaux ateliers UI. Nouveau module `application/krea2_assisted_v3.py` réutilisant le contexte compact et la publication V2 ; seule la consigne d'exclusion courte est remplacée par description de l'état visible, retrait de l'élément et des formulations qui continuent à le suggérer, explication française séparée. Pas d'appel supplémentaire, filtrage automatique ni nouveau workflow. V1/V2 inchangées ; anciens ateliers gardent leur version, aucun basculement en cours de conversation ajouté. API sans version conserve V1. Opérations journalisées `krea2.assisted.creation_chat@3.0.0` / `krea2.assisted.recipe_chat@3.0.0`.

- V3 : référence initiale non répétée, feedback/branches/presets et stockage inchangés. Cache Assisted JS `20260907.1`. Guide `docs/assistance-recipe-versions.md` actualisé. Tests de versions, contexte, référence, branches, HTTP/persistance et UI étendus **NON EXÉCUTÉS**. Vérifications statiques : AST 7 fichiers Python, JS compilé sans invocation, HTML équilibré/885 IDs uniques/défaut 3.0.0, empreinte V2 `5255b494ea0908345c472b60ad8efb2b62a6fa2c0b780b19ad06ba1f100d504a` inchangée. Aucun test, appel LLM, génération, donnée runtime ou redémarrage ; gain de qualité à évaluer par l'utilisateur. Aucun commit/tag/publication nouveau.

- Nouvelle discussion Edit : revenir à une étape déjà validée, par exemple pour corriger un rendu 0,8 MP. Actuellement lecture seule après validation ; le bouton Recommencer concerne seulement l'étape pending et efface son travail, ce n'est pas cette reprise. Proposition **non implémentée** : « Reprendre depuis cette étape » ouvre une copie de travail avec source d'origine, conversation et réglages de l'essai validé conservés. Ancienne chaîne inchangée pendant l'essai ; à validation d'un nouveau candidat, conserver l'ancienne suite comme version consultable et reprendre une suite active depuis la nouvelle image. Étapes suivantes à refaire manuellement car liées aux anciens pixels ; aucune suppression ni régénération automatique, pas de report automatique des masques. Frise simple avec accès à l'ancienne version, pas d'arbre supplémentaire imposé. Demande à affiner avec l'utilisateur avant ce patch.

- Audit KREA2 Assisted du 2026-09-07, lecture seule : atelier « interieur d'un arbre » `krea2-create-0f9f74f16c5c4f5c96f559ab14e4a898`, recette 2.0.0, LLM local Qwen3.8-27B, checkpoint CyberRealistic Krea2 v20, aucune LoRA/preset/référence. Images des essais 2–4 inspectées : assemblages et ouvertures persistent ; après « pas de planche », essai 3 avec lambris/plancher/plafond réguliers, puis essai 4 avec charpente marquée. Même seed `229083145364738` et paramètres de calcul ; workflows diffèrent seulement par prompt et métadonnées de sortie. Cela confirme l’échec des reformulations, sans isoler causalement l’effet du mot ni prouver que toute négation renforce un objet.

- Les quatre appels LLM de cet atelier n’ont aucune image jointe ni résultat sélectionné : retours uniquement textuels. Les prompts passent de `no planks or boards` à `no planks, boards, beams, or reworked elements`, mais gardent `photorealistic architectural interior` et une description de murs/plafond/sol en bois. Les exclusions sont dans le prompt positif ; négatif Comfy = `ConditioningZeroOut`, pas de texte négatif distinct. Hypothèse : le concept d’intérieur construit reste insuffisamment remplacé par celui d’une cavité dans une seule masse de bois. Règle V2 actuelle exige déjà une description positive mais autorise une exclusion courte, utilisée ici comme correction principale. Proposition seulement : convertir une suppression en état visuel de remplacement, retirer les formulations associées à la structure refusée, privilégier volume continu/veines irrégulières/fibres brutes ; garder l’explication de l’exclusion dans la conversation. Aucun code, test, appel modèle, rendu, donnée runtime ou service modifié pendant cet audit.

- Patch H3 Base demandé et clarifié le 2026-09-07 : **MP avant upscale** et **MP sortie** sont DEUX champs indépendants, tous deux **modifiables**, défaut **0,2 MP** chacun. **Réutiliser la seed** coché par défaut dans les nouveaux ateliers H3. Les anciens essais conservent leur résolution de sortie ; reprendre prompt/réglages recharge les deux MP et la seed. Ref2V conserve ses contrôles/défauts. Aucun atelier runtime ni rendu existant modifié.

- Workflow de rendu H3 `minimax-h3-latent-speed@0.1.3` créé et sélectionné par `scripts/run_lab.py` ; anciens 0.1.0–0.1.2 conservés. Nouveau binding `initial_megapixels` dans le manifest, défaut de sortie 0,2 ; phases de génération/upscale/finition conservées, aucune nouvelle recette de préparation LLM/menu. SHA256 workflow `3b4566a209275c2c77fdeab7beacd54f144d23569c85c16ace397f951c0ffab5`. Deux MP validés entre 0,1 et 16 par pas de 0,1 ; aucune contrainte entre leurs valeurs. Une sortie inférieure à la première passe reste possible, avec réduction avant finition.

- `initial_megapixels` enregistré par essai, transmis au compilateur H3, exposé dans l’API, l’historique et le contexte de feedback. Lecture des anciens essais = première passe 0,2 ; stockage H3 schéma 3 conservé et lecture 1–3. Ancien workflow explicitement chargé refuse une première passe différente de 0,2. Guide `docs/h3-render-resolution.md`, caches CSS/H3 Render `20260907.5` (Edit/retouche restent `20260907.4`). Tests ciblés et scénario navigateur préparés NON EXÉCUTÉS ; AST 22 fichiers Python en cours, HTML équilibré/885 IDs uniques, JS H3 + scénario compilés sans invocation, hash/assertions/défauts du nouveau JSON cohérents. Aucun test, LLM, génération, annulation ou redémarrage. Tag stable pré-masque conservé, aucun commit/publication demandé.

- Patch demandé puis implémenté le 2026-09-07 : bouton **Recommencer cette étape** près du titre KREA2 Edit, confirmation au clic, retour sur la même source au même rang du même projet. Révisions, prompts générés/erreurs, essais, feedback et brouillons de l’étape retirés de l’atelier ; réglages de rendu réhydratés depuis la source/parent comme au départ. Description initiale de la source conservée ; historique abandonné absent du contexte LLM. Étapes validées immuables ; refus si échange LLM ou rendu queued/running/cancel_pending en cours. Aucun run utilisateur réinitialisé pendant l’implémentation.

- Reprise persistante : `POST .../sources/{source_id}/restart` avec `expected_restart_count`, compteur `restart_count` ajouté avec défaut 0 aux anciens fichiers (schéma 5 conservé). Copie préalable `krea2_edits/<source_id>/restarts/before-N.json`, exclue du backlog/contexte ; assets et traces techniques non supprimés. Une nouvelle tentative avec ancien compteur renvoie l’état actuel sans effacer les échanges entrepris depuis. Verrou Lab, écriture atomique après archive ; résultats tardifs de retouche/LLM protégés par le compteur. Frontend invalide les anciens retours de polling et vide seulement les brouillons de cette étape après succès.

- Retoucher : **Image à gauche** est désormais un sélecteur permanent **Image 2 · génération / Source de l’étape**, remplaçant le bouton temporaire à maintenir. Image 2 par défaut ; masque rouge dessinable sur les deux images, mêmes traits/Annuler/Rétablir, zoom/déplacement, harmonisation et résultat. Changer de vue ne crée pas de modification du masque ni de nouvelle clé de sauvegarde. Choix de vue conservé dans le brouillon de l’onglet.

- Lecture seule du dernier projet runtime « ARbre » : étape 3 pending `krea2-edit-2e54da8a62ce4496a150fe2b23e0512f`, 10 essais/5 révisions autour de la porte ; étapes 1 et 2 advanced. Aucun asset ou état runtime modifié. Tests backend/HTTP/Canvas préparés et étendus pour reprise, mémoire vide, archive, erreurs, idempotence, parents immuables et changement de vue sans perte ; NON EXÉCUTÉS. Contrôles statiques : 16 fichiers Python AST, deux JS et scénario navigateur compilés sans invocation, HTML équilibré/884 IDs uniques. Caches CSS/Edit/retouche `20260907.4`, guide actualisé. Aucun test, LLM, rendu, annulation ou redémarrage ; tag stable pré-masque conservé.

- Extension masque AUTORISÉE puis implémentée le 2026-09-07 : **Image 2 / Résultat** dans Retoucher, masque rouge affichable, bouton **Voir la source (maintenir)** à la souris/tactile/clavier. Harmonisation facultative dans la barre de Retoucher, désactivée initialement, intensité 0–100 % sans étape supplémentaire. **Valider l’image Après et continuer** sous le comparateur utilise exactement son candidat sélectionné et les mêmes gardes/la même opération que l’historique. Sauvegarder sélectionne toujours le nouvel essai dans Après. Les anciennes propositions ci-dessous sont historiques et remplacées par cette extension.

- Harmonisation locale via Pillow/LittleCMS existants, sans nouvelle dépendance ni ComfyUI : transfert des moyennes/écarts-types Lab encodés 8 bits, méthode `reinhard_lab_rgb@1.0.0`. L’image harmonisée à 100 % est préparée à l’ouverture ; le navigateur mélange en RGB selon l’intensité puis applique le masque, sans appel serveur durant les interactions. Serveur : même double interpolation entière à l’enregistrement depuis source + génération d’origine. Adaptation distincte du nœud Comfy ColorTransfer (intensité Lab) et du MKL. Alpha du rendu conservé, source hors masque/transition intacte ; un transfert global peut atténuer des couleurs nouvelles et ne corrige pas les différences de netteté/géométrie.

- Réglages `harmonize`, `harmonize_strength`, `color_method` conservés dans les retouches et l’export ; réouverture restaure masque/réglages sans accumuler les composites. Schéma 5 conservé, anciennes retouches sans champs couleur chargées avec harmonisation désactivée ; schémas 1–4 toujours lisibles. Idempotence compare aussi activation/intensité, brouillon conservé sur erreur, nouvelle clé après changement des réglages. Étapes validées en lecture seule avec leurs paramètres enregistrés, sans substituer le brouillon local.

- Caches CSS/Edit/retouche `20260907.3`, guide `docs/krea2-edit-retouch.md` actualisé. Tests backend/HTTP/Canvas étendus pour couleurs, pixels protégés, reprise, idempotence, ancienne retouche, export et candidat Après exact ; **NON EXÉCUTÉS**. Contrôles statiques uniquement : AST des 16 fichiers Python en cours, compilation sans invocation des deux JS et du scénario navigateur avec les fonctions réelles du comparateur, HTML équilibré avec 883 IDs uniques, diff sans erreur. Aucun test, appel LLM, génération, annulation ou redémarrage de service. Tag `stable-avant-masque-2026-09-06` vérifié intact sur `56840b877be4b810ee93f8afe9b2f0c40ee73006` ; aucun nouveau commit/publication.

- Accord produit du 2026-09-07 sur **image 2 / résultat** et **harmoniser avec la source**. Nouvelle demande : pouvoir valider directement sous le comparateur sans descendre dans l'historique. Précision IHM proposée : harmonisation facultative dans la barre de Retoucher, intensité visible à l'activation, correction sur la génération avant composition ; aucune étape supplémentaire. Bouton principal **Valider l'image Après et continuer** sous le comparateur, lié exactement au candidat Après et aux mêmes conditions de validation que sa carte. Enregistrer la retouche ramène au comparateur avec son nouvel essai sélectionné, puis validation à cet endroit. Principes acceptés, placement expliqué ; ces ajouts ne sont pas encore implémentés.

- Retour utilisateur masque du 2026-09-07 : peindre sur la source rend difficile le repérage des nouveaux éléments ; préférence émergente pour **génération (image 2) à gauche + composite à droite**, plutôt que trois vues. Il propose aussi un fantôme et un color match. Fichier `C:\Users\samue\Downloads\Color Match.json` inspecté : deux branches indépendantes avec même image_ref/image_target, `ColorTransfer`/`reinhard_lab`/per_frame/strength=1 et `ColorMatchV2`/`mkl`/strength=1. Deux GET object_info confirment les nœuds natif ComfyUI et KJNodes disponibles ; documentation officielle ColorTransfer consultée. Proposition à discuter : gauche = génération (harmonisée si activée) avec masque affichable, droite = composite propre, accès momentané à la source ; harmonisation facultative avec intensité 0–100 %, calcul local et appliqué à la génération avant le masque, paramètres persistés pour reprise. Un transfert global peut affecter les couleurs volontairement nouvelles ; commencer avec contrôle d'intensité, puis envisager l'estimation sur zones inchangées si nécessaire. Fantôme optionnel, pas de troisième vue permanente. Aucun changement de code, test, appel LLM, génération ou redémarrage ; attendre décision avant patch.

- Priorité utilisateur du 2026-09-07 : recherche de seeds mise de côté, proposition conservée dans `docs/h3-seed-search-audit-2026-09-07.md`. L'utilisateur teste maintenant Modifier avec KREA2 et son masque ; attendre ses retours sans lancer de test, génération ou nouvelle implémentation à sa place.

- Audit Seed Hunter H3 le 2026-09-07, sans implémentation : fichier utilisateur `C:\Users\samue\Downloads\minimaxSEEDHUNTERWorkflow_v15.json` + description de foxydits lue via API Civitai.red. Graphe = trois premières passes S/S+1/S+2, aperçus vidéo/audio, sélection du latent favori puis upscale/raffinement ; aucune sauvegarde explicite du latent. Réglages tiers affichés 0,4 MP/8 steps différents de nos modèles/sampler. Nos workflows H3 Base `0.1.2` et Ref2V `0.2.0` ont déjà première passe 0,2 MP + upscale/raffinement. Proposition : outil optionnel **Explorer 3 seeds → Finaliser celle-ci** dans le rendu existant, snapshots immuables, file séquentielle, conservation/reprise de l'intermédiaire AV, recettes de préparation LLM inchangées. `queue_attempt` H3 bloque actuellement le deuxième actif ; latents et provenance aperçu/finalisation restent à ajouter. SaveLatent/LoadLatent/SeparateAV/ConcatAV présents via quatre GET object_info ; fidélité du stockage H3 complet non testée. Audit et options : `docs/h3-seed-search-audit-2026-09-07.md`. Aucun code runtime, test, LLM, génération, poids, annulation ou redémarrage ; attendre discussion/autorisation avant patch.

- Rangement H3 Base AUTORISÉ puis appliqué le 2026-09-07 : l'ancienne compacte `minimax.h3.fl2va.direct@0.4.0` est désormais dans **Autres recettes → Versions historiques**, libellée « Mono-plan · compact · historique ». La liste principale contient les trois parcours `1.0.0` ; **Exploration guidée · 3 étapes** devient le défaut pour conserver un parcours à trois étapes. Les runs déjà enregistrés conservent leur recette et la sélection historique reste visible à leur réouverture. Aucun manifest, prompt ou dépendance modifié ; Ref2V conserve son défaut expérimental `0.5.0`. Caches core/H3 `20260907.2`, trois guides et tests existants actualisés. Contrôles statiques : AST des deux tests Python, compilation sans invocation des deux JS et du scénario navigateur, diff sans erreur. Aucun test, appel LLM, génération ou redémarrage exécuté. Recharger la page pour appliquer le rangement.

- Patch V1 masque KREA2 Edit AUTORISÉ et implémenté le 2026-09-07 dans `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`. Plan et guide : `docs/krea2-edit-retouch.md`. Outil facultatif pleine largeur depuis un essai réussi ou Après ; source + masque rouge à gauche et composite en direct à droite, zoom/déplacement communs, pinceau/gomme/taille/douceur/Annuler/Rétablir/ajustement. Aucun appel serveur déclenché par les traits. Brouillons conservés dans l'onglet entre modes/étapes ; sauvegarde explicite puis retour au comparateur avec le nouveau candidat sélectionné.

- Retouches = candidats locaux réussis distincts, libellés `Essai N — Retouche M`, sans execution_id ni workflow compilé, jamais mis en file ComfyUI. Une reprise recharge toujours source + génération d'origine + masque, sans accumulation des composites. Prompt/réglages hérités pour reprise, conversation courante préservée. Schéma Edit 5, lecture 1–4 conservée. Préparation/sauvegarde API, validation images/masque, refus d'une étape devenue immuable, idempotence sous verrou du processus Lab (même clé + même fichier), brouillon conservé sur erreur. Étapes validées : consultation du masque enregistré, sans substitution d'un éventuel brouillon local.

- Choix utilisateur appliqué : dimensions de sortie = source après orientation EXIF. Pillow prépare les deux PNG et compose le résultat ; seule la génération est redimensionnée, écart de ratio accepté jusqu'à 1 %, refus explicite au-delà, aucun recalage automatique. Pixels RGBA décodés hors masque/transition préservés ; V1 normalisée RGBA8, limites colorimétriques/alpha et raccords documentés. Feedback, source suivante, frise et export utilisent l'output_asset_id du candidat choisi. L'export d'une retouche inclut composite, source, rendu initial et masque avec chemins explicites ; métadonnées distinguent composition locale et réglages de génération hérités.

- Pillow `>=12.1.1,<13` ajouté aux dépendances et 12.3.0 installé dans `D:\Code\panelforge\.venv` sans autre mise à niveau ni redémarrage. Chemin checkpoints corrigé `diffusion\_models` → `diffusion_models` dans `scripts/run_lab.py`. Caches CSS/Edit/retouche : `20260907.1`. Tag `stable-avant-masque-2026-09-06` conservé intact, aucun nouveau commit/publication pour ce patch. L'incident de file Assisted abandonné par l'utilisateur reste hors périmètre.

- Vérification du patch masque : tests `test_krea2_retouch.py` et `test_krea2_retouch_browser.py` préparés NON EXÉCUTÉS ; tests existants de cache/chemin actualisés. Contrôles statiques seulement : AST des 15 fichiers Python modifiés/ajoutés, compilation sans invocation des 2 JS et du scénario navigateur, HTML équilibré avec 882 IDs uniques, `git diff --check` sans erreur. Aucun test, appel LLM, génération, annulation de rendu ou redémarrage de service. Les anciennes entrées de conception du masque ci-dessous sont historiques et remplacées par ce patch ; l'utilisateur garde la validation fonctionnelle et visuelle.

- Nouvel inventaire KREA2 du 2026-09-06 après d'autres ajouts : GET ComfyUI UNETLoader = 71 entrées, dont 33 sous `Krea2/` (30 au contrôle précédent). Stat des fichiers via SSH en lecture seule : ajouts récents après Sick Ollie/Sinox = `ultra_v15.safetensors` (14 132 234 864 octets), `kreamania_variant8.safetensors` (12 829 372 648), `intorealismKrea2_v40.safetensors` (13 642 961 416). Tous présents dans `/data/models/ComfyUi/diffusion_models/Krea2` et exposés par ComfyUI. Le Lab `127.0.0.1:7861` ne répond pas et aucun listener 7860–7870 n'est relevé : affichage UI actuel non vérifié, aucun redémarrage effectué. Découverte annexe : le défaut `scripts/run_lab.py` pointe vers `diffusion\_models` (deux dossiers), alors que le dossier serveur réel est `diffusion_models` ; le repli ComfyUI permet la détection, mais le scan local ne peut pas utiliser ce chemin erroné. Aucun poids chargé/lu/haché, aucun test/génération/code modifié. Audit uniquement ; type de précision exact non déduit des seules tailles.

- Sauvegarde avant masque effectivement créée et publication vérifiée au tour précédent : tag annoté `stable-avant-masque-2026-09-06` sur GitHub `EasyFrag/panelforge`, commit `56840b877be4b810ee93f8afe9b2f0c40ee73006`. Ce tour d'inventaire ne modifie pas le tag.

- Point de restauration avant masque demandé le 2026-09-06 : nom de référence `stable-avant-masque-2026-09-06`, depuis le checkout actif `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`. Contenu et limites décrits dans `docs/stable-avant-masque-2026-09-06.md`. Syntaxe vérifiée : 47 fichiers Python analysés par AST, 13 JSON lus, 7 JavaScript compilés sans invocation. Revue complète de l'index : 9 avertissements de lignes vierges finales dans les nouveaux prompts FL2VA, conservées pour figer leur contenu actuel. Aucun test exécuté, aucun appel LLM/rendu/redémarrage ; le terme stable désigne le point de restauration demandé, pas une qualification fonctionnelle nouvelle. Destination de sauvegarde du tag : `https://github.com/EasyFrag/panelforge.git` ; le remote origin de ce checkout pointe vers le dépôt local `D:\Code\panelforge`. Pour retrouver le commit exact, résoudre ce tag et vérifier son équivalent distant.

- Nouveaux checkpoints vérifiés le 2026-09-06 par GET ComfyUI UNETLoader et GET Lab 7861 Assisted spec : 30 modèles sous `Krea2/`, dont `Krea2/sickOllie_krea2.safetensors` et `Krea2/sinoxKrea2Aesthetics_visionV10Uncen.safetensors`, tous deux sélectionnables. Aucun enregistrement manuel nécessaire. Précision inconnue faute d'accès aux fichiers locaux et de métadonnées ; ne pas leur attribuer BF16/INT8 au jugé. Le workflow Assisted partagé `krea2-community@0.2.0` reste ER-SDE/Simple, 8 steps CFG 1.1 puis upscale 1.5 et 2 steps CFG 1/denoise 0.3. La fiche auteur Sick Ollie Krea2 recommande Euler/Beta, 9 steps, CFG 1, 1440×1920 ; ces réglages ne sont pas sélectionnés automatiquement par checkpoint. Variante exacte du fichier et compatibilité de chargement non validées par génération. Aucun changement de catalogue, workflow ou modèle ; voir le document du snapshot pour la source.

- Reprise du sujet masque après le patch de file Assisted : l'utilisateur demande où la conception en était. État vérifié : comparateur/frise Edit présents, aucun pinceau/masque/composite implémenté. Récapitulatif du choix arrêté : composer après génération, pinceau révèle le résultat et gomme restaure la source, aperçu local en direct, masque enregistré par essai et résultat composé utilisé après validation. Différences de netteté et raccords restent à expérimenter. Ce tour est un rappel de conception ; pas une nouvelle autorisation de coder le masque.

- File de rendus Assisted AUTORISÉE puis implémentée le 2026-09-06. Préparation + mise en file atomique via `attempts?enqueue=true`, snapshots prompt/modèle/LoRA/ratio/MP/seed/branche/turn ; ordre global persistant `queue_order`, schéma 6 lit 1–5. Worker unique par service, démarrage lifespan FastAPI ou /start, ordre entre ateliers, exécution synchrone Production via même verrou. Les fichiers existent sans serveur relancé : aucun rendu déclenché par l'agent. Essais legacy created ne démarrent pas automatiquement ; nouvelle action par carte. UI statut français, position globale, annulation par essai, résumé et ouverture de l'autre atelier actif ; polling conserve formulaire et suit les autres essais après une annulation. JS `20260906.1`.

- Reprise de file : IDs ComfyUI conservés, suivi repris après restart sans resoumission ; panne réseau/timeout ne libère pas la suite sans preuve de fin. Échec confirmé ou ressources manquantes → échec puis suivant ; LoRA absente jamais retirée silencieusement. Statut submitting persisté avant POST : envoi interrompu sans ID laisse la file en attente jusqu'au retrait explicite après vérification ComfyUI (aucune interruption globale). Arrêt worker ne cancel pas les calculs distants. Cible = un processus Lab habituel par workspace. Tests fake FIFO/cancel/concurrence/reprise/HTTP préparés NON exécutés ; contrôles statiques seulement, aucun LLM/génération/redémarrage/annulation runtime. Guide `docs/krea2-assisted-render-queue.md`.

- Audit rendus successifs Assisted 2026-09-06 : l'utilisateur signale `another assisted KREA2 render is already active`. Limitation explicite de `queue_attempt` : un seul essai queued/running/cancel_pending parmi tous les projets Assisted, pas de file multi-rendus. UI `renderAttempt` prépare et persiste l'essai avant `/start`, puis rend le bouton cliquable après la requête sans attendre la génération ; un deuxième clic laisse donc un essai created si `/start` est refusé. Lecture des 296 fichiers projets : aucun statut actif au moment de l'audit ; dernier projet `krea2-create-152d0445ef544feeabe04259c656750d` (« Horror décalé »), derniers essais `attempt-89a482df4e6046c3a82424af2e0939ce` et `attempt-7996feb8cf3d4d698aa1d3a38ede96c6` created, sans execution_id, ne seront pas lancés automatiquement. Diagnostic uniquement, aucun changement runtime, test, appel LLM, rendu, annulation ou redémarrage. Proposition pour la suite : vraie file séquentielle, chaque clic capture prompt/modèle/LoRA/seed/branche, statut/position visibles et annulation individuelle ; ne pas supprimer naïvement le verrou sans revoir suivi/reprise/annulation.

- Checkpoint manquant 2026-09-06 : GET ComfyUI `/object_info/UNETLoader` expose 67 modèles, dont 28 sous `Krea2/` et `sickOllie_krea2.safetensors` à la racine. GET Lab 7861 `/api/image-lab/krea2-assisted/spec` expose bien ces 28 modèles, sans Sick Ollie. Cause confirmée : `_krea2_comfy_name` limite l'inventaire aux chemins `Krea2/`, pas un filtre visuel ni un fichier supprimé. Avant toute modification, l'utilisateur interrompt la correction proposée et choisit de déplacer lui-même Sick Ollie dans le bon dossier. Aucun code changé, aucun fichier modèle déplacé par l'agent, aucun test/appel LLM/génération/redémarrage. Attendre son déplacement puis recharger le catalogue ; ne pas élargir le filtre sans nouvelle demande. La complétude de tous les modèles KREA2 aux noms/familles ambigus hors dossier n'est pas démontrée.

- Réserve utilisateur sur le masque : une forte différence de netteté entre source et génération peut rendre le raccord visible même avec un bord adouci. À évaluer lors de ses expérimentations ; ne pas promettre que le fondu corrige une différence de qualité. Conception du masque toujours non implémentée.

- Précision masque utilisateur : il souhaite surtout composer APRÈS la génération et voir le résultat en direct pendant le dessin. Proposition affinée : source et résultat brut conservés séparément ; pinceau révèle le résultat généré, gomme restaure la source, bord adouci réglable, aperçu calculé localement dans le navigateur sans nouvel appel modèle. Masque ajustable par essai ; validation/export produit le PNG composé qui devient la source suivante. Distinguer clairement ce mélange après génération d'un masque guidant le sampler. Le comparateur avant/après existant reste un outil d'inspection indépendant. Aucun code runtime modifié ; conception seulement, implémentation non encore demandée.

- L'utilisateur privilégie désormais le masque local pour limiter la dérive KREA2 Edit et demande la faisabilité d'un dessin sur la source. Proposition : pinceau/gomme, taille et annulation, surimpression colorée, bord adouci réglable ; conserver la génération actuelle puis recomposer uniquement la zone autorisée sur la source, avec masque/réglages enregistrés sur l'essai. Pixels hors zone et transition conservés exactement dans une sortie PNG à dimensions identiques ; cette première version ne signifie pas que le modèle calcule uniquement la zone masquée. Prévoir une marge pour raccords, ombres et extension des objets ; cohérence interne et raccords restent à évaluer. Discussion de conception uniquement, aucune implémentation du masque ni génération autorisée/lancée dans ce tour.

- Audit dérive cartoon 2026-09-05 terminé : six images existantes du projet paroi → trou → porte → pavage inspectées, paramètres et deux workflows compilés lus. Aspect dessiné renforcé notamment sur rochers/nuages/végétation ; pas de baisse de résolution (688×1224 → 1112×1976), sorties PNG. Les deux derniers pavages ont mêmes prompt/source/modèle/seed/Ref boost 0.4/12 steps ; seul réglage différent = slider de détail à 4, avec résultat visuellement plus stylisé. Indice local, pas preuve que toute la dérive vient de cette LoRA ; porte source déjà passée par Detailer à 1. Pavage à Ref boost 4 conserve fortement la scène et manque la transformation ; 0.4 pave mais change le cadrage. Les essais d'une étape repartent de sa même source. Workflow régénère globalement depuis latent vide + références, sans masque protecteur ; ne pas recommander une baisse naïve de denoise. Recommandations à discuter : isoler LoRA optionnelles, stabiliser réglages, prompt de modification plus ciblé, puis masque et recomposition hors zone. Writer des traces historique ; aucun résultat attribuable au nouveau chat. Documentation auteur consultée, détails `docs/krea2-edit-quality-drift-2026-09-05.md`. Aucun test, appel modèle, génération, changement runtime ou redémarrage ; aucune correction de qualité implémentée dans cet audit.

- Patch atelier Edit + presets AUTORISÉ puis implémenté le 2026-09-05, tests NON EXÉCUTÉS. KREA2 Edit : nouveau writer conversationnel `krea2.edit.conversation@2.0.0`, JSON message français + prompt ; frontend demande cette version, API sans version conserve le writer texte historique. Six échanges acceptés récents de l'étape sont transmis, sans recopies des anciens prompts ni historique des autres étapes ; réponse persistée avec version, anciennes révisions affichées honnêtement. Schéma Edit 4 lisible 1/2/3. Source d'étape toujours jointe et toujours entrée réelle du rendu. Promotion conserve désormais Ref boost/steps/modèle LLM en plus des réglages existants ; UI peut retrouver Ref boost/steps d'une ancienne étape via son essai parent chargé. Workflow `krea2.identity_edit@0.1.0` inchangé.

- Interface Edit : comparaison superposée source/essai ou deux essais, séparateur vertical à glisser, curseur clavier/tactile et suivi souris optionnel ; mêmes boîtes d'affichage avec proportions conservées, aucun recalage. Choisir un essai à droite le sélectionne aussi en feedback. Frise base + images réellement validées, clic miniature pour zoom et bouton séparé pour ouvrir l'étape ; étapes validées consultables. Conversation visible, longs prompts/paramètres/images séparées repliables, un atelier actif. Brouillons de formulaire préservés dans la mémoire de l'onglet lors des navigations (pas sauvegardés sur disque). Rafraîchissement tardif ne remplace pas une autre étape ouverte. CSS `20260905.3`, Edit JS `20260905.1`.

- Presets Assisted implémentés : catalogue atomique `workspace/krea2_style_presets.json`, révisions immuables, un nom courant par preset. Sauvegarde depuis un essai réussi (prompt/réglages enregistrés de cet essai, image et provenance), nouveau ou mise à jour avec garde contre version périmée. Sélection initiale préremplit modèle image/LoRA, défauts 9:16/2.1 MP/seed libre ; en atelier modèle/LoRA remplacés, prompt/ratio/MP/seed/historique conservés. Prompt + image d'exemple transmis seulement au prochain échange LLM ; état en attente conservé après échec, consommé après réponse acceptée. A puis B sans échange → B seulement. Aucun appel à la sélection/sauvegarde, aucune branche automatique. Retirer garde les réglages/prompt actuels, Réappliquer recharge le dernier preset et remet l'exemple en attente. Noms transmis visibles sur les échanges ; projets/branches/essais capturent le snapshot et l'état en attente, donc mise à jour catalogue ne réécrit pas les projets. Assisted schéma 5 lit 1/2/3/4. Le prompt édité à la main est maintenant transmis au prochain chat. Câblage dans `scripts/run_lab.py`, Assisted JS `20260905.4`. Recettes Batch indépendantes.

- Vérification de ce patch : AST Python, compilation syntaxique JavaScript V8 sans invocation, HTML équilibré sans ID doublon et IDs JS présents, diff sans erreur. Nouveaux tests `test_krea2_style_presets.py`, `test_krea2_edit_workshop.py`, parcours HTTP et contrats UI actualisés ; aucun test exécuté, aucun appel LLM/image/vidéo, aucun serveur lancé/redémarré ni donnée runtime modifiée. Pas de validation visuelle navigateur. Guide `docs/krea2-edit-and-presets.md`. L'utilisateur signale une dérive progressive cartoon des éditions successives et demande explicitement de la discuter APRÈS le patch : causes non départagées, aucun gain de qualité démontré. Vidéo toujours hors périmètre.

- Dernier affinage KREA2 Edit : utilisateur souhaite cliquer sur l'image d'une étape dans la frise pour zoomer. Proposition : clic miniature ouvre l'agrandissement, action distincte pour sélectionner/consulter l'étape afin de ne pas changer involontairement l'atelier en inspectant une image. Il demande un résumé du patch avant implémentation : chat visible avec contexte récent propre à l'étape, comparateur avant/après, frise/zoom, validation vers nouvelle source et transmission complète des réglages. Vidéo toujours hors périmètre ; presets convenus restent prévus au prochain patch. Aucun début d'implémentation runtime.

- Précision utilisateur sur KREA2 Edit : laisser explicitement la vidéo de côté pour le moment, priorité aux images de références des étapes. Impression de mémoire confirmée comme continuité portée par le prompt courant/images, tandis que les anciens couples instruction/prompt sont cachés sous « Échange de modification » et ne sont pas retransmis au writer. Proposition : conversation visible par étape, contexte récent, ancienne étape consultable, nouvelle base image/prompt validés. Comparateur avant/après demandé : images superposées, séparation verticale qui révèle l'une/l'autre lors du déplacement horizontal. Proposition de base = source de l'étape vs essai sélectionné, choix d'ancien essai possible, proportions/échelle cohérentes sans recalage qui masque les dérives ; poignée contrôlable et suivi au survol facultatif. Conception uniquement, aucun changement de code runtime/test/LLM/rendu/service. Détails ajoutés à `docs/krea2-edit-workshop-audit-2026-09-05.md`.

- Accord presets précisé et reporté au prochain patch : sélection initiale → modèle image/LoRA présélectionnés, prompt d'exemple donné au premier échange LLM. Sélection pendant l'atelier → réglages immédiatement remplacés, prompt courant inchangé, exemple actif au prochain échange seulement, sans appel déclenché par la sélection. Un rendu avant cet échange utilise le prompt courant avec les nouveaux réglages. A puis B sans échange intermédiaire → seul l'exemple B en attente est envoyé. Influence des anciens échanges acceptée, pas de branche automatique. Presets toujours non implémentés.

- Audit demandé de Modifier avec KREA2 avant implémentation : scénario utilisateur mur → trou → ponçage → piquets, chaque résultat validé devient source, puis clips Ref2V avec référence ouvrier et reprise de leur dernière frame. Chaîne d'étapes et `Valider et continuer` déjà présents ; source réelle reste fixe pendant les essais. Writer actuel = nouvelle instruction + prompt courant + source + feedback facultatif, réponse prompt seul ; anciennes révisions affichées mais absentes du contexte LLM. Étapes validées consultables mais non rééditables/branchables dans l'UI. `ref_boost`/steps ne suivent pas la promotion et retombent actuellement aux défauts du nouvel état. Workflow conditionné par la source, sans masque local. Quatre fiches chantier récentes lues : projets distincts étape 1 sans validation, aucune conclusion visuelle. Proposition : conversation courte par étape, frise/comparaison stable, continuité des réglages, puis passerelles Edit/Ref2V. La dernière frame réelle doit être validée avant de poursuivre ; éventuellement rééditer la cible suivante depuis elle pour éviter d'accumuler la dérive. Bouton actuel de reprise vidéo ouvre H3 Base, pas Ref2V. Détails `docs/krea2-edit-workshop-audit-2026-09-05.md` ; guide Ref2V officiel consulté pour les rôles image cible / identité. Discussion uniquement, aucun code runtime, test, appel LLM/rendu, redémarrage ou donnée utilisateur modifié.

- Référence initiale KREA Assisted : changement autorisé puis implémenté pour V1/V2. Les pixels sont joints jusqu'à la première réponse assistant acceptée du projet, puis plus jamais automatiquement ; échec/rejet/interruption avant succès conserve la référence pour la reprise. État déduit des réponses conservées dans toutes les branches (sans transmettre leurs textes au LLM), donc réouverture et retour vers une conversation vide ne réintroduisent pas l'image. Référence conservée comme asset, renvoi volontaire via inspiration inchangé ; feedback reste joint. Statut des images dans les user prompts V1/V2 aligné avec l'envoi réel, systèmes V1 inchangés. Pas d'appel séparé d'analyse/résumé, pas de migration ou nouveau schéma. Tests existants actualisés et cas reprise, réouverture, renvoi volontaire, branche vide ajoutés NON EXÉCUTÉS ; syntaxe AST six fichiers et diff seulement. Aucun test, appel LLM/rendu, service ou donnée runtime touché. Documentation `docs/krea2-conversation-branches.md` actualisée.

- Décision presets KREA : l'utilisateur accepte l'influence cumulative de A puis B dans les prompts/échanges et préfère « continuer avec B ». Recommandation retenue pour la conception : un seul preset de réglages actif, remplacement explicite par B, conversation poursuivie et aucun branchement automatique à chaque sélection. Prompt/image d'exemple restent des références de style, pas une remise à zéro de mémoire ; ne pas promettre de nettoyer A. Garder pour un prochain patch un point de retour avant application du preset, depuis lequel créer volontairement une piste ; distinguer ce point d'une branche créée automatiquement à chaque changement. Preset choisi à la création fait partie de la base du projet. Les presets restent NON implémentés dans ce tour ; seul l'envoi initial de référence a été modifié.

- Blocage au lancement corrigé : la valeur par défaut `Krea2AssistedBranch(...)` du projet était instanciée pendant l'import, avant la définition du validateur `_text`, d'où `NameError`. Passage à `dataclasses.field(default_factory=...)` pour créer la branche lors de l'instanciation du projet. Vérification limitée avec le Python du venv utilisateur : `python -B scripts/run_lab.py --help` termine avec code 0, imports chargés ; aucune création d'application, aucun serveur, test de suite, appel LLM ou rendu lancé. Diff contrôlé. L'utilisateur peut relancer sa commande habituelle. Il approuve l'idée du preset KREA, mais demande de traiter d'abord ce blocage ; presets toujours non implémentés.

- Audit et correctifs Ref2V du 2026-09-05 : une étape `prompt-063ccea6b093492ea4a72ccb55d230b1`, JSON compilé/validé puis rejet `unsupported output contract` (36.160 / 39.099 s) car `_append_revision` oubliait le contrat direct dans son dispatch final ; garde corrigée, contrôles initiaux conservés. Deux étapes `prompt-a5eab5f101894c8f9976e4db2ef3c86e`, Plan accepté 61.761 s puis writers rejetés 45.211 / 36.298 s : `<Picture 2>` réinjecté par l'état final du Plan, compté à tort comme doublon du mapping. Linter limité au paragraphe de déclaration, citations du corps permises si déclarées ; doublons header/labels inconnus/header altéré restent refusés. Révision Ref2V `h3-render-eec5f07ce8cd471989dc22afee2a92e0` : caméra fixe correctement proposée à 0/7 s, faux doublon de phrase statique imbriquée dans sa variante horodatée (67.254 puis 111.997 s) ; tentative intermédiaire (38.051 s) recopiait effectivement token + phrase. Validation par directives complètes/timestamps et suppression uniquement d'une expansion exacte adjacente à son token. Tests de parcours étendus 4/9 refs et ancre finale, régressions mapping/caméra ajoutées, NON exécutés. AST de cinq fichiers et diff seulement ; aucune génération/LLM/redémarrage/donnée runtime modifiée. Détails `docs/ref2v-run-failures-2026-09-05.md`.

- Discussion presets KREA : aucune implémentation demandée à ce stade, utilisateur indécis entre prompt+réglages et réglages seuls. Recettes Batch existantes plus riches (canon/invariants/variables/risques). Proposition : preset rapide nommé checkpoint + LoRA/forces ; conserver prompt/image de l'essai comme exemple, charger le prompt seulement sur option explicite. Préserver les métadonnées de rendu/seed comme provenance sans imposer la seed aux nouveaux sujets. Essais moto 20/21 consultés : même prompt (soft focus/grain/micro-contraste réduit), LoRA/résolution différentes ; pas de conclusion sur le meilleur rendu. Ne pas créer automatiquement des presets depuis ces essais.

- Image Lab : branches conversationnelles et doubles aperçus implémentés à la demande utilisateur, NON TESTÉS. « Résultat à corriger » et « Image d’inspiration » visibles simultanément ; backend cumulait déjà les images. Chaque nouvel essai conserve branche/dernier tour/langue/modèle LLM au moment de sa préparation, plus son prompt/réglages/seed exacts. « Repartir d’ici » crée une piste au préfixe enregistré, garde l'autre suite et sélectionne l'image comme feedback ; « Feedback » reste dans la conversation actuelle. Arbre compact repliable, miniatures/origines/piste active, retour aux branches avec leurs réglages ; sauvegarde des modifications de prompt/réglages avant navigation. Schéma 4 : branches et table de tours partagés, lecture 1/2/3 conservée ; anciens essais affichent explicitement « Nouvelle piste · image + prompt » sans prétendre restaurer la conversation. Recettes V1/V2 inchangées, seul le contexte actif est transmis selon leur fenêtre habituelle, aucun appel supplémentaire. Garde contre changement de branche pendant chat, branche périmée dans les requêtes, rafraîchissement tardif et fin de rendu dans une autre piste. Tests domaine/service/stockage/web/UI ajoutés ou actualisés, non exécutés. Syntaxe AST Python et JavaScript V8 sans invocation + diff seulement ; Node absent du PATH, recours au parseur V8. Aucun appel LLM/rendu ni redémarrage, aucune donnée runtime modifiée. Documentation `docs/krea2-conversation-branches.md`. Caches UI assisted `20260905.3`, CSS `20260905.2`.

- Discussion Image Lab : l'import « ＋ Image d’appoint » est déjà cumulable avec le résultat sélectionné en feedback (et la référence initiale) dans le même appel LLM ; pièce jointe conservée sur le tour, non renvoyée automatiquement aux tours suivants. Ambiguïté UI vérifiée : le grand aperçu affiche l'appoint en priorité et masque l'aperçu du feedback sans retirer ce dernier de la requête. Proposition, non implémentée : afficher deux vignettes nommées « Résultat à corriger » / « Image d’inspiration ». Reprise mémoire : historique actuellement linéaire, sélectionner une ancienne image ne rembobine rien. Proposition optionnelle « Créer une branche depuis ici », conservant l'autre suite et ne transmettant au LLM que l'ascendance choisie selon la fenêtre de contexte habituelle. Enregistrer un point de conversation explicite lors de chaque nouvelle création d'essai, avec prompt/réglages exacts ; plusieurs seeds ne créent pas plusieurs branches. Les anciens essais n'ont pas de lien fiable vers un tour : reprise exacte non reconstructible par simple rapprochement de prompts ; prévoir choix explicite du point ou reprise image/prompt seulement. Aucun changement runtime ni test/LLM/rendu/redémarrage ; conception discutée, arbre non implémenté.

- Discussion style photo moto blindée sur autoroute : objectif KREA2 jugé plausible, fidélité exacte non démontrée. Lecture visuelle : vue frontale légèrement plongeante, effet longue focale, soleil dur, ombres de contact, matières mates et poussière, trafic ordinaire et couleurs sobres. Proposition de prompt documentaire automobile et comparaison Soliloquy V2 / CielBleu sans LoRA, paramètres constants ; leurs performances sur ce sujet restent à mesurer. Catalogue local consulté (description auteur Soliloquy : hiérarchie de détail/tonalité/matières photographiques), présentation officielle Krea open source consultée (exemples automobiles). Pas de génération, test, changement runtime ou nouveau réglage appliqué. Image jointe utilisateur utilisée pour analyse visuelle uniquement.

- Règle spatiale KREA V2 intégrée à la demande utilisateur : échec répété rapporté/visible → changer un choix concret de cadrage/échelle/position dans ses contraintes, sans simple renforcement de synonymes ; réponse décrit le prompt proposé et ne prétend pas que le rendu est corrigé. Libellé JSON + deux paragraphes condensés, système création 3524 → 3358 caractères (511 → 481 mots séparés par espaces). V1, appels, paramètres et publication inchangés. AST seulement, aucun test/LLM/rendu/redémarrage. Sujet suivant discuté : chantier accéléré dans un tronc (captures 161811 / 161833) ; distinguer micro-actions du Plan et vraies images intermédiaires. Protocole proposé `docs/accelerated-work-video-experiment.md` : premier test local B→C entaille 8 s H3 Base, puis 5 états A intact / B tracé / C entamé / D ouvert brut / E poncé en Ref2V 15 s, ou clips FF/LF successifs. Caméra fixe/audace 0 pour isoler causalité outil/matière, décor aligné et références sans UI à préparer. Sources officielles H3 consultées ; aucune capacité de réussite du chantier démontrée, aucun nouvel asset ni recette vidéo implémenté.

- Correctif Ref2V deux étapes sur run moto → avion `prompt-9a179948bd0e4abb93fbcec558a14975`, recette `minimax.h3.ref2v.direct.planned@1.0.0`, profil `0.5.0` : Plan accepté en 72.627 s ; Writer rejeté deux fois en 25.750 / 24.510 s (`llm-3ee6c839da0045bba871b5d4d3d5e1f7`, `llm-6708aeb91dd349198931725927dd7035`). L'application compile les deux keyframes avec « user intention and plan », mais `validate_direct_ref2v_labels` recalculait le header historique « approved Brief and plan ». Le LLM fournissait correctement le corps seul. Le service transmet maintenant au validateur l'en-tête canonique issu de `_preparation_reference_header`, déjà utilisé pour la compilation. Comparaison exacte et contrôles des bindings conservés ; défaut historique de la fonction conservé. Régression hors ligne ajoutée : First + 2 keyframes, parcours deux/trois étapes, streaming, approbation, réouverture/révision, rejet de source/rôle/label/header altérés ; NON exécutée. Helper de fixture rôles/uses corrigé. AST de trois fichiers et diff contrôlés seulement. Aucun test, appel LLM/rendu, redémarrage ou modification du run utilisateur. Après redémarrage utilisateur, reprendre uniquement Prompt H3 ; Plan approuvé intact.

- Audit en lecture du run KREA `lips`, `krea2-create-f315ff2bb9b34272a7c6c1f74c97b3a0` (V2 `2.0.0`, 17 essais, 12 tours) : la demande de séparation est présente dès le tour 6 puis renforcée jusqu'au tour 12, sans changement net de stratégie de cadrage. Prompts des essais 15/16/17 retrouvés intégralement dans CLIPTextEncode des workflows compilés. Ces trois essais : Cielbleu v1bf16, seed `456666006200236`, 2.1 MP, aucune LoRA ; 17 retire seulement la clause bottom strip de 16 (plus double virgule). Dernier appel LLM `llm-355f10fa3a1346f68a0ab054c09a1d5a` : 21.850 s, raisonnement repère correctement l'occlusion, mais réponse réitère une solution proche et affirme abusivement la correction acquise. Feedback encore sélectionné : essai 14 Kroma (image inspectée), pas 16/17 Cielbleu ; référence Instagram en contact aussi attachée. V2 omet bien anciens prompts/catalogues, mais conserve les anciennes affirmations assistant dans la conversation. Hypothèse : cadrage macro serré + composition d'application persiste malgré séparation textuelle ; ce run ne permet pas d'isoler le rôle du checkpoint, encodeur ou seed. Proposition : cadrage nez-menton, espace de peau explicite entre lèvre et pointe, géométrie prioritaire puis textures ; sélectionner le dernier essai comme feedback. Aucun prompt système, réglage ou historique runtime modifié, aucun test/LLM/rendu lancé.

- Vérification statique du dernier ajustement : syntaxe Python lue via AST sur six fichiers et `git diff --check` sans erreur. Aucun test exécuté. Les entrées suivantes conservent l'historique des patchs ; les défauts actuels sont ceux décrits immédiatement ci-dessous.

- À la demande utilisateur, défauts des sélecteurs passés à KREA2 Assisted V2 `2.0.0`, H3 compact expérimental `0.4.0` et Ref2V compact expérimental `0.5.0`. Les trois parcours `1.0.0` restent visibles ; les anciens runs gardent leurs versions. KREA2 accepte une image seule : intention facultative dans le formulaire/API, demande initiale de reproduction visuelle conservée dans le projet puis utilisée au premier échange. Texte + image tous deux absents refusés. Défaut API sans version explicite et anciens schémas restent V1. Cache core/ref2v `.4`, i2v `.5`, assisted `.2` du 20260905. Tests de contrat ajoutés/attentes UI adaptées, NON exécutés ; aucun appel LLM, génération ni redémarrage. Explication V2 : prompt courant + retours récents, suppression des recopies des anciens prompts, priorité au dernier retour, sujet au sens large, catalogues conditionnels ; pas de nouvel arbre mémoire ni changement du moteur image.

- Parcours mono 3/2/1 étapes implémentés pour H3 Base et Ref2V, NON TESTÉS : six cookbooks `minimax.h3.{fl2va,ref2v}.direct.{guided,planned,prompt}@1.0.0`. Guided par défaut ; anciens mono/compacts sous Autres recettes. Schéma cookbook 8 : nombre d'étapes, profil exact et assemblage de templates par dépendances numériques explicites, blocs `video-preparation@1.0.0`, garde cycles/chemins. Plan V4 et writer identiques entre 2/3 étapes, consignes d'interprétation propres au Plan sans Brief. Mode 1 : un seul appel JSON caméra + trois textes, compilation header/durée/caméra vers H3 Base ou Ref2V, aucun Brief ni Plan synthétique ; un mouvement caméra principal, durée explicite sinon 8 s, contrôles paroles/jalons/labels. Nouveau `application/video_preparation.py`, intention séparée immuable dans composition schéma 3 (lecture 1/2 conservée). UI étapes/numéros/Quick mode adaptés ; reprise/fork restaure intention et recette, dernière frame conserve aussi la nouvelle recette mono. IDs recette/version dans opérations Plan/Prompt. Tests hors ligne préparés, NON exécutés ; syntaxe Python via AST et diff uniquement, aucun appel LLM/rendu/redémarrage. Docs `docs/video-preparation-recipes.md`. Caches core/ref2v `20260905.3`, i2v `20260905.4`, quick `20260905.1`.

- Bouton `Repartir de la dernière frame` implemente sous chaque essai reussi du composant partage H3 Base/Ref2V : reutilise uniquement la keyframe correspondant au dernier timestamp attendu, reste desactive si elle manque (pas de fallback silencieux sur echantillon intermediaire). API frontend `PanelForgeH3Base.prefillFirstFrame` charge l'asset en lecture, puis prepare un formulaire H3 Base mono avec first frame seule et intention vide, sans creation serveur ni appel LLM automatique. La recette mono H3 deja selectionnee est conservee, sinon retour au mono standard. Preparation H3 occupee protegee ; erreur de chargement conserve le formulaire courant. Source stockee intacte. Caches i2v `20260905.3`, h3-render/CSS `20260905.1`. Attentes des tests de cache actualisees, aucun test/LLM/rendu/redemarrage execute ; revue statique et diff uniquement.
- Discussion recettes 3/2/1 étapes : règles communes versionnées et consignes propres au parcours, writer partagé avec contrat d'entrée identique. Accord utilisateur puis implémentation décrite ci-dessus ; validation et comparaison réelles restent à sa main.

- Audit/correctif run I2VA fraise `prompt-037d3f9349c448039c10262a523b67c5` : Brief 42.394 s, Plan 55.619 s accepte, Writer 37.207 s puis relance 31.982 s tous deux rejetes pour label interdit. Reponses Writer sans label ; `apply_direct_i2v_timing` reinjecte `<Image 1>` depuis final_state du Plan APRES la normalisation initiale. Correctif `_append_revision` H3 Base mono : normaliser les labels du document assemble selon context.mode avant rehydratation/lint. References inconnues restent rejetees et dialogues preserves par le helper existant. Test integration I2VA/FL2VA ajoute, NON execute ; diff concerne propre, aucun appel/rendu/redemarrage. Plan saisie/plantation/liberation/croissance coherent sur contacts ; lecture bois/verre comme terre reste hypothese discutable. Discussion architecture : trois etapes utiles pour supervision, piste deux appels intention+images vers Plan puis Writer avec Brief facultatif, une etape pour cas simples a comparer sans promesse de qualite.

- Comparaison run experimental `prompt-243cfeaf89e14bf4946e2f2d0d144bd6` (09:20 UTC) vs `prompt-d21dfc3eb5b94b79a6e572b370c5dab5` : profil/cookbook `0.4.0` et nouveaux prompts camera confirmes dans les requetes (y compris Brief, verification lecture UTF-8). Meme intention, modele, temperatures, audace/axes et last-frame ; first-frame SHA different. Durees Brief/Plan/Writer 102.418/77.217/40.230 s vs 48.981/103.508/37.036 ; total 219.865 vs 189.525 s. Thinking 34183/24077/19368 caracteres vs 15165/32560/16399. Plan accepte, 4 beats/4 steps vs 3/6 : choix camera static beaucoup plus direct mais micro-handheld encore cache dans description. Brief boucle sur homme absent selon sa lecture de la nouvelle first-frame, correspondance des invites et choix signature audace 3 (onde radiale + demi-clignement). Writer encore des reprises de prose, respecte cette fois silence (N/A). Signal local encourageant Plan (-25.4 % duree / -26.1 % thinking), pas de gain global demontre, comparaison non controlee a cause de first-frame et decisions creatives differentes. Aucun appel/test/generation ni modification runtime pour audit.

- Audit run `prompt-d21dfc3eb5b94b79a6e572b370c5dab5` du 2026-09-05 09:15 UTC : profil ET cookbook H3 `0.3.3`, nouvelles consignes camera absentes des requetes. Ne pas attribuer ce run au patch `0.4.0`. Brief/Plan/Writer acceptes (Brief revision persistee), durees 48.981/103.508/37.036 s, total appels 189.525 s ; thinking enregistre 15165/32560/16399 caracteres, reponses 2312/7920/1807. Plan 3 beats, 6 steps, 1 push.in. Boucle camera encore tres longue, ambiguite des images et redaction/recontroles repetes ; Brief compte/recrit ses deux phrases par section, Writer hesite plusieurs fois sur timestamp 0 et phrase finale compilee. Pas de pulse ajoute dans les textes finaux de ce run, mais ambiance de conversations reinvente malgre contrainte sans voix. Traces sans timestamps internes ni usage tokens : aucun partage de duree thinking/generation inferable. Aucun test, appel LLM, rendu ou changement runtime pour cet audit.

- Guidage camera implemente dans H3 Base experimental `0.4.0` et Ref2V experimental `0.5.0` : Brief standard et Direction creative `0.2.0`, creation/revision, puis Plan generation/arbitrage. Choix unique du mouvement principal (ou fixe), combinaison simultanee simplifiee et explicitee, succession seulement pour changement de phase utile, respect des axes et du suivi continu. Le Plan ne cache pas un mouvement secondaire dans visible_change/target_clause et consigne une approximation explicite une seule fois dans un risque resolu. Consigne de decision unique et redaction directe sans brouillons JSON repetes. Anciennes recettes et variante historique creative `0.1.0` inchangees. Aucun test, appel LLM, generation ou redemarrage ; gain de latence non mesure.

- Validateur de fin modifie a la demande utilisateur : `_continuing_motion_anchor_issues` associe champs, timestamps et portee etat/action. Matching dans un etat terminal a la coupure accepte sans expression magique ; convergence avant la coupure reste rejetee, convergence ambigue dans action/camera terminale devient avertissement via warnings V4, tenue explicite de pose finale reste bloquante. Messages localisent le champ et, pour convergence anticipee, les temps. Tests de regression adaptes/ajoutes NON executes ; controle diff des fichiers concernes propre. Aucun appel LLM, rendu ou redemarrage. Prompts camera NON modifies : proposition de rendre le Brief compatible avec camera sequentielle, privilegier un mouvement principal et decision unique plutot que reiteration des alternatives.

- Thinking fourni par utilisateur (piece jointe 4a2edd9e) : hesitations repetitives sur dolly+tilt simultanes vs contrat camera sequentiel, redaction repetee du futur JSON, recontroles de schema, ambiguite perspective/pieds et son. Il valide explicitement les formulations finales ensuite rejetees ; aucun timing par passage disponible. Proposition de validateur a discuter : utiliser la portee temporelle des champs, distinguer etat terminal et action sur intervalle, conserver blocage des arrets anticipes explicites, avertir sur convergence ambigue plutot qu'exiger des mots magiques. Validateur NON modifie.
- A la demande utilisateur, journalisation du thinking implementee : `reasoning_text` separe dans `llm_calls.json` schema 3, lecture schemas 1/2 conservee, collecte des evenements streaming meme si affichage UI desactive et champ fournisseur en appels synchrones. Conservation de traces partielles sur erreur/annulation, journal toujours borne aux 20 derniers appels. Aucun changement des parametres de generation fournisseur ni appel supplementaire. Tests de stockage/visibilite/compatibilite ajoutes et NON executes. Activation au prochain redemarrage utilisateur ; anciens thinkings non recuperables automatiquement.

- Second rejet Plan `llm-7a55b345d22b4d4a82dde6474368a00a` 08:59 UTC (110.636 s) : meme erreur lexicale, notamment `composition matches final frame` et `visible state reaches the exact final frame with motion still underway`. Nuance : le validateur ne raisonne pas sur les timestamps et exige une expression de passage instantane dans le meme fragment ; il peut rejeter une description terminale pourtant accompagnee de mouvement. Thinking transmis uniquement au navigateur, explicitement non conserve par `infrastructure/llm/logged.py`; pas de tokens ni ventilation temporelle disponibles. Analyse du cout possible seulement comme hypotheses a partir des prompts/reponses (contradictions Brief/contrat, geometrie des frames, repetition du schema). Aucun test ni appel lance.

- Audit echec Plan 2026-09-05 08:57 UTC, appel `llm-0fc9dcdac4ce4c7e97225fb1b4abb0e7` : reponse complete en 97.786 s, rejet applicatif `invalid H3 Base continuing-motion plan`. Le Brief regenere a 08:56 introduit stabilisation 7-8 s et anneau lumineux de reflets ; le Plan reprend pose finale precoce, oscillation residuelle et progression presque imperceptible malgre `continue_motion`. Validateur `continuing_motion_final_anchor_errors` lexical confirme des formulations de convergence sans passage instantane explicite. Aucun correctif runtime ni appel/test pour cet audit ; corriger la fin du Brief en amont et les ajouts lumineux avant une nouvelle preparation utilisateur.

- Correctif du Brief echoue `prompt-4fed2666c0cd429d88b1cb903267714a` : appel `llm-f440f39f974d483a9cf73418e8b31d96` termine normalement en 92.983 s, neuf titres en gras Markdown non reconnus par `_normalize_brief_document`, aucune revision persistee. Normalisation limitee aux titres exacts encadres de `**`, corps et validation des sections inchanges. Tests de regression ajoutes mais NON executes. Aucun appel LLM, generation, redemarrage ni modification du run utilisateur. Le log conserve la reponse complete ; intention envoyee de 8 s correctement reprise, guirlandes constantes et ombre naturelle conservees.

- Audit nouveau run `prompt-09016578639b4953b582150a21a6c897` (2026-09-05 08:44 UTC) : profil/cookbook H3 `0.4.0` effectivement utilises. Brief/Plan/Writer 60.708/105.037/19.915 s contre 42.842/81.174/42.870 s au run piscine precedent `0.3.3` ; Plan brut 7760 contre 8923 caracteres, toujours 3 beats/6 steps. Meilleur depart explicite du deck, mais contradiction persistante jambes poussees hors de la bouche pendant absorption et phrase finale compilee repetitive. Cinq sorties Brief audace 3 presentes dans le journal borne ajoutent une pulsation lumineuse (deux themes seulement, pas de temoin audace basse) ; ajout des le LLM de preparation, pas preuve d'une initiative du generateur video. Nouveau run : toast + pulse dore des guirlandes, ancien : halo rose buccal. Systeme propose explicitement evolution lumineuse parmi les signatures. Aucun test/appel/generation lance pour cet audit.

- Audit post-video du 2026-09-05 : dernier projet `h3-render-28cfc659d40b4592924f5d7573ecc731`, conversation `h3.base.render.revision@0.2.0`, trois appels 08:31–08:35 UTC. Suppression du glow : les deux premieres revisions accumulent des negations ; la troisieme retire enfin le vocabulaire demande. Les trois appels recoivent les memes cinq keyframes de l'essai 1 et son ancien prompt demandant explicitement un halo rose. Essais 2/3 annules sans keyframes, essai 4 en cours lors de la lecture. Historique retransmis avec tous les anciens prompts (contexte texte 6896 puis 9842 puis 12487 caracteres). Audace 3/3 presente aux deux premiers appels. Pistes : revision ciblee par soustraction, historique conversationnel sans anciens prompts complets, provenance visuelle explicite, derniere demande prioritaire sur audace. La revision post-video est versionnee separement des recettes Brief/Plan ; aucun changement du code runtime ni test/appel/generation pour cet audit.

- Instruction utilisateur du 2026-09-05 : il exécute lui-même les tests. Ne lancer aucun test, appel LLM, rendu image/vidéo ni redémarrage de service pendant le développement sans nouvelle demande explicite ; des générations peuvent être actives en parallèle. Cette règle est aussi inscrite dans `AGENTS.md`.
- Patch expérimental implémenté, NON TESTÉ : KREA2 Assisted V2 `2.0.0` (sujet au sens large, prompt courant + retours verbatim sans recopies des anciens prompts, catalogues conditionnels), H3 Base mono `0.4.0` et Ref2V mono `0.5.0` (Brief/Plan concis, phases causales et projection Writer `camera_clean_compact_v5`). Les trois témoins V1 / `0.3.3` / `0.4.0` restent sélectionnables et par défaut. Les nouveaux profils Brief sont appariés explicitement à leurs cookbooks ; garde serveur contre un mélange témoin/expérimental. Réouverture et forks UI transmettent le profil correspondant.
- Pour les nouvelles recettes vidéo seulement, le compilateur n'injecte plus « Throughout the entire shot » avec le mouvement de fin. La phrase finale reste compilée ; les clauses caméra/dialogue, timings et workflows Hybrid restent inchangés. La projection du Writer supprime uniquement les doublons exacts de même portée temporelle, les champs compilés et l'indentation, sans modifier le Plan approuvé. Aucun appel supplémentaire ni panneau de logs ajouté.
- Tests hors ligne ajoutés/actualisés mais volontairement NON exécutés ; aucun appel aux services LLM/ComfyUI, aucun rendu et aucun redémarrage. Seuls lecture/édition des fichiers et contrôle `git diff --check` ont été effectués. Caches vidéo/core : `20260905.2`. Documentation et procédure de comparaison utilisateur : `docs/experimental-prompts-2026-09-05.md`. Les résultats « 762 tests verts » ci-dessous concernent le patch précédent, pas celui-ci.

- Patch ASTRA 2026-09-05 implémenté : sélecteurs vidéo centrés sur H3 Base `0.3.3` / Ref2V `0.4.0`, volet « Autres recettes » pour avancées/spécialisées et historiques ; une référence sélectionnée reste visible et les manifests sont inchangés. KREA2 Assisted possède désormais V1 `1.0.0`, sélectionnée à la création et persistée par projet/tour. Les schémas 1/2 restent lisibles comme V1 ; nouveaux fichiers en schéma 3. Prompts/contexte V1 extraits sans changement de texte, aucune V2 fictive proposée. Documentation : `docs/assistance-recipe-versions.md`. Cache des quatre scripts modifiés : `20260905.1`.
- Validation finale du patch : 762 tests passent en 81,382 s, dont un test DOM Chromium réel des catégories/versions historiques et de la syntaxe JS. Lecture sans écriture de 291 projets KREA2 Assisted des deux workspaces : tous compatibles V1. `git diff --check` propre. Aucun rendu GPU ni smoke complet de l'application en fonctionnement ; redémarrer le serveur pour charger le nouveau backend puis recharger la page. Prochaine étape : recette V2 expérimentale, sans modifier V1.

- Inventaire versions 2026-09-05 : H3 Base expose 9 recettes et Ref2V 10 choix (dont Super Fast synthétisé par le frontend). Standards actuels et utilisés récemment : H3 Base `0.3.3` (49 compositions du workspace principal), Ref2V `0.4.0` (10). KREA2 Assisted n'a pas de recette de conversation sélectionnable/persistée : système Python global et opération `creation_chat@0.3.0`. Proposition à ce stade, non appliquée : figer le comportement actuel comme KREA Assisted V1 et créer V2 avec référence de recette persistée ; garder les deux standards vidéo, proposer les futures optimisations comme versions expérimentales, déplacer anciennes versions mono-plan et anciennes interviews dans un accès historique, placer les multi-plans récents sous Avancé. Attention : choisir un ancien cookbook vidéo pour un nouveau run utilise encore le profil Brief actuel du frontend ; versionner la paire profil/cookbook pour un témoin complet.

- Priorité actualisée le 2026-09-05 : audit avant nettoyage. Snapshot intégral du code publié sur `EasyFrag/panelforge`, tag `snapshot/avant-astra-2026-09-05`, commit `b63197f5a97c42aa829024adadf66f220cca1397`. Workspace/médias restent locaux. Aucun prompt ni comportement modifié par ASTRA à ce stade.
- Audit détaillé : `docs/audit-astra-2026-09-05.md`. KREA2 Assisted transmet les 13 entrées précédentes, pas une mémoire arborescente ; choisir un ancien feedback ne rembobine pas le dialogue. Production V2 filtre ses notes narratives par rôle/profil, pas par projet/branche. Cinq préparations vidéo récentes coûtent 128–169 s en appels LLM, avec le Plan comme étape dominante ; une incohérence mouvement continu/séquence causale est observée sur la fraise de cristal.
- Validation du snapshot : 755 tests passent en 87,258 s avec `D:\Code\panelforge\.venv\Scripts\python.exe` et `PYTHONPATH=D:\Code\localQ\.panelpatch\src`. Le Python global manque de dépendances. Les entrées historiques ci-dessous décrivent des décisions antérieures et ne remplacent pas cette priorité produit.

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

- **Smoke Suite d’une histoire** : après redémarrage et `Ctrl+F5`, ouvrir « L’Addition », cliquer « Créer l’épisode suivant », vérifier que le mode Suite contient l’ancien brief plus « L’Addition », puis produire une proposition. Contrôler dans la mémoire affichée que la preuve écrite reste acquise, que l’enregistrement audio inexpliqué n’est pas inventé et que la conséquence finale réutilise un élément préparé.

- **Smoke des nouveaux défauts et menus** : redémarrer PanelForge et faire `Ctrl+F5`, puis ouvrir un nouveau run H3 Base et REF2V. Vérifier Qwen local → Gemma local, mode rapide actif, trois modes Image Lab et deux modes Video Lab. Ouvrir ensuite un ancien run sans writer séparé pour confirmer qu'il reste inchangé.
- **Suite narrative à discuter** : si le défaut de causalité se répète, ajouter à Histoires un contrat explicite de continuation (`faits acquis`, `état de fin`, `conflit non résolu`, `objets/preuves disponibles`) et une chaîne par épisode `reprise → obstacle → conséquence`, avec avertissement déterministe sur les preuves, objets ou personnages introduits sans préparation. Ne pas intégrer ce changement sur le seul run « L'Addition ».

- **Smoke de la file globale** : redémarrer PanelForge, faire `Ctrl+F5`, ouvrir **Traitements** depuis le moniteur, puis lancer plusieurs prompts, un rendu distant et un DLSS. Vérifier l'ordre FIFO, l'exclusivité LLM/DLSS, l'indépendance locale/distante, le compteur de repos vidéo à 30 s et la persistance des réglages globaux.

- **Smoke du grand patch Fabrication** : redémarrer depuis `D:\Code\panelforge-krea2-flux`, faire `Ctrl+F5` pour charger `episodes.js/css?v=20260917.3` et `h3-render-lab.js?v=20260917.1`. Vérifier qu’un preset commun pilote les deux profils hérités, qu’une personnalisation Personnages reste intacte après changement de preset, puis ouvrir Scènes, régler le profil vidéo commun avant tout prompt et lancer `Prompts + vidéos`. Tester `Pause après les tâches en cours`, `Reprendre`, les cartes/results et le déverrouillage DLSS final.

- **Vérifier la compression exacte sur le script des chats** : redémarrer le Lab, faire Ctrl+F5 pour charger `stories.js?v=20260917.3`, choisir `Chats de couple · muet`, Script fidèle, 3 micro-scènes de 10 s, puis recoller les sept événements. Attendu : exactement trois scènes regroupées (maladie/offres, billets/câlin, boutique/promenade), aucun dialogue. Si le LLM ignore encore la quantité, le job doit échouer avec le brouillon conservé plutôt qu'appliquer sept scènes.

- **Essai utilisateur Fabrication 1.2** : ouvrir Histoires → Fabrication, vérifier les deux profils et les libellés de workflow, lancer deux ou trois références et confirmer qu’un seul prompt LLM tourne à la fois tandis que KREA2 distant peut rendre en parallèle. Retenir chaque image, observer les états Local/Distant et tester des seuils thermiques prudents avant la chaîne vidéo. L’assemblage final reste hors périmètre.

- **Essai utilisateur voix off / registre** : redémarrer le Lab depuis `D:\Code\panelforge-krea2-flux`, puis faire Ctrl+F5 pour charger `stories.js/css?v=20260917.1`. Créer une histoire à registre 0 puis 2 ou 3 et comparer uniquement le vocabulaire des dialogues ; vérifier que Script fidèle grise le curseur et conserve chaque mot. Dans Fabrication, repréparer une scène avec `VOIX OFF` via Classique 1.0 et vérifier dans le prompt final la forme `(Sx) says in an off-screen voiceover` suivie de la consigne de lèvres fermées ; une réplique `DERRIÈRE LA PORTE` doit rester hors champ. Le futur curseur de densité doit être discuté séparément après ces essais.

- Décider si l'interface de rendu doit rendre la sémantique plus explicite : renommer le choix vide REF2V en « Hybride dynamique FL2VA + REF2VA (25–49) », distinguer visuellement les checkpoints directs des checkpoints préfusionnés, et éventuellement masquer BUNNY 0.1.2 des nouveaux choix tout en le conservant pour la reprise des anciens essais. Aucun patch autorisé à ce stade.

- La scène 1 est prête : actualiser Fabrication et poursuivre avec le projet de rendu déjà créé, sans troisième préparation. Si ce faux positif `tilted` se répète, corriger séparément le validateur caméra pour distinguer une posture de personnage d'une commande caméra, avec régression ciblée et sans assouplir les vraies instructions caméra libres.

- Redémarrer le Lab puis faire `Ctrl+F5`. Dans l'histoire `story-b309aa69d5934b9cb52666b7f480dae2`, utiliser **Réessayer** : les préfixes descriptifs de voix off ne doivent plus provoquer de faux rejet, tandis qu'une vraie paraphrase doit encore être refusée. Vérifier ensuite dans Fabrication que `VOIX OFF` et `DERRIÈRE LA PORTE` sont visibles dans les dialogues et dans l'intention complète.

- Redémarrer le Lab, forcer `Ctrl+F5`, personnaliser le LLM et les réglages image d’un personnage vierge, puis passer au personnage suivant. Vérifier que les sélections sont reprises et qu’une fiche déjà préparée conserve ses propres choix.

- Redémarrer le Lab depuis `D:\Code\panelforge-krea2-flux`, forcer le rechargement du navigateur, puis tester **Cru ++** une fois en mode proposition et une fois en mode script fidèle. Vérifier en particulier la conservation des dialogues, `sexual_state` dans chaque scène et son transfert vers Fabrication. Le choix de la famille vidéo reste manuel et indépendant.

- **Vérifier 1/2/3 et script fidèle dans le Lab réel** : redémarrer le processus depuis `D:\Code\panelforge-krea2-flux`, faire Ctrl+F5 pour charger `stories.js?v=20260916.3`, vérifier une génération à une proposition puis coller le script « Le premier rendez-vous » en mode script. Confirmer qu’un seul appel Rédacteur part, que toutes les répliques apparaissent et que le scénario peut ensuite être validé vers Fabrication. Un script dont le modèle modifie une réplique doit rester en brouillon avec l’erreur de fidélité, sans remplacer le document.

- **Vérifier les correctifs Windows/Fabrication** : redémarrer le Lab, faire Ctrl+F5 pour charger `episodes.js?v=20260916.5`, rouvrir la fabrication de `story-e1f1419c5ac64977b6a129112a2ab409`, puis retenir les sorties déjà terminées de Bruno/Le Serveur sans les regénérer. Pendant une prochaine longue écriture Histoires, confirmer l’absence de `WinError 5`. Suites préparées : `tests.test_local_storage tests.test_episodes_browser tests.test_stories`.

- **Vérifier la trace live Histoires** : redémarrer le Lab sur `feature/krea2-flux-klein`, faire Ctrl+F5 pour charger les assets `20260916.2`, puis lancer concepts ou développement. Le panneau doit montrer le plan si le modèle/fournisseur expose `reasoning`, puis le JSON au fil de l’eau ; un modèle sans canal de raisonnement montrera seulement le JSON. Tester aussi une réponse `reply` supérieure à 12 000 caractères. Suites préparées : `tests.test_stories tests.test_stories_browser`.

- **Validation utilisateur du patch Histoires** : redémarrer le Lab depuis `feature/krea2-flux-klein`, faire Ctrl+F5, créer une histoire Fruits puis une Sensuel light, vérifier les modèles Architecte/Rédacteur, le schéma propre à chaque famille, l’édition manuelle et les diagnostics. Dans Fabrication, choisir `KREA2 + Flux Klein`, enregistrer les réglages communs puis vérifier l’héritage et une personnalisation par fiche. Les prompts et rendus réels restent à évaluer par l’utilisateur ; rendu en lot et assemblage vidéo demeurent un chantier séparé.

- **Valider KREA2 + Flux Klein sur l'instance utilisateur** : depuis `D:\Code\panelforge-krea2-flux`, lancer `python -m unittest tests.test_krea2_assisted_flux_klein tests.test_krea2_assisted_sampling tests.test_krea2_assisted_render_queue tests.test_krea2_assisted_web tests.test_krea2_assisted_ui`, puis redémarrer manuellement le Lab. Vérifier la bascule entre les deux familles, un run Moody 8+4 avec checkpoint/LoRA, la taille finale demandée, les trois seeds, l'image finale et l'image KREA2 pré-Flux. Enchaîner deux rendus pour confirmer l'absence de purge. Aucun commit ni push GitHub n'a été effectué.

- **Après snapshot Histoires/Fabrication 1.1** : utiliser le repère GitHub `snapshot-fabrication-1.1-2026-09-16` pour retrouver cette version. Charger/essayer le patch selon les étapes ci-dessous ; aucune intégration à la branche principale ni nouvelle évolution engagée pendant cette sauvegarde.

- **Charger et essayer Fabrication 1.1** : redémarrage manuel du Lab après les travaux en cours puis refresh navigateur. Dans Histoires → Fabrication, choisir/appliquer un preset de style, essayer une image de style, vérifier checkpoint/favoris/fiches et LoRA, personnaliser une fiche puis revenir aux communs. Vérifier persistance et sliders par scène, dialogues exacts à zéro, provenance/alertes après changement de style. Tests utilisateur : `python -m unittest tests.test_episodes tests.test_episodes_web tests.test_episodes_browser`. Pas de génération de vérification ni publication effectuée. P1 I2V, P2 analyse adaptative et import Video Lab restent séparés.

- **Charger et essayer Fabrication 1.0** : redémarrage manuel du Lab après les traitements en cours, refresh navigateur. Dans Histoires, valider le scénario, générer/importer et choisir les références, puis préparer une scène et lancer son rendu. Vérifier qualité des fiches, correspondance des identités/dialogues, quatre images avec décor, defaults Qwen/Gemma/BUNNY/Motion Repair et durée, reprise des réglages après changement de scène/refresh. Tests utilisateur : `python -m unittest tests.test_episodes tests.test_episodes_browser`. Aucune publication GitHub ni génération de vérification effectuée pour cette livraison.

- **Aligner la fabrication avant développement** : retenir la capacité existante de neuf images REF2V au total par scène, avec personnages et décors, sans repli artificiel à trois. Définir le premier patch autour d'une histoire déjà validée, KREA2 Assisted compact et pilotage REF2V intégré par scène ; éviter l'ancien transfert Video Lab limité à trois. Import vidéo longue explicitement différé. Defaults locaux Qwen/Gemma, Classique deux appels, BUNNY + Motion Repair éditables et versionnés par épisode. Aucun lancement automatique de production sur cette discussion.

- **Charger et vérifier le patch Histoires Local/JSON** : redémarrage du Lab par l'utilisateur pour le nouveau décodeur, puis refresh navigateur pour les assets `20260915.2`. Nouvelle histoire : Local/Gemma Hauhau par défaut ; les histoires existantes reprennent leur modèle enregistré. Vérifier bascule/persistance Local/Serveur et relancer les propositions souhaitées après avoir renseigné le brief si nécessaire. Tests préparés : `tests.test_stories tests.test_stories_browser`. R3 reste active, aucun appel supplémentaire ; les anciens brouillons ne sont pas appliqués automatiquement.

- **Essayer Histoires r3 active** : dans Consignes LLM → Histoires, vérifier r3 et la note « Scènes concrètes : exemples JSON, actes, conséquences et continuité ». Avec le même Gemma et le même brief, demander trois nouvelles pistes puis développer celle retenue ; comparer causalité, actes de l'antagoniste, densité des clips et fin. Essayer ensuite un autre conflit pour vérifier que l'exemple n'est pas recopié. Tests utilisateur : `tests.test_stories`. R2 reste sélectionnable et activable dans l'éditeur. Pas de génération automatique ni troisième appel ; P1/P2 inchangées.

- **Scénario r2 évalué ; prochaine révision à discuter** : conserver le cadre Le Prix du Luxe et les clips de 10 s, rendre sacrifice/mépris visibles, réparer le parcours du collier et la perspective du dialogue de Fraise, condenser la révélation pour une conséquence finale concrète et alléger les répliques. L'utilisateur n'a demandé ni réécriture automatique ni patch dans cet échange ; ne pas lancer de génération ou de rendu. Vérifier aussi les identités fruits avant d'aborder les fiches KREA2.

- **Tester le recadrage Histoires r2 après redémarrage** : demander « 3 nouvelles pistes » avec le brief de tromperie et la correction fruits déjà conservée. Comparer la causalité, les rôles et le ton plutôt que le jargon ; développer seulement la piste retenue. L'ancien scénario reste dans les versions. Le brouillon de correction rejeté n'est pas appliqué automatiquement, car sa logique et son ton restent faibles. Tests utilisateur : `tests.test_stories`. Aucun changement des priorités P1/P2.

- **Vérification utilisateur de Histoires 1.0** : redémarrer le Lab et actualiser, ouvrir Histoires, choisir le modèle, proposer puis sélectionner/développer, vérifier les révisions, exporter une intention, modifier les consignes pour un nouvel échange. Lancer les tests du guide si souhaité. Évaluer le ton narratif avec les LLM locaux : aucun essai réel lancé par l'agent. Suite à aligner ensuite : références KREA2/décors, transferts H3/REF2V et fabrication d'épisode ; P1 I2V/P2 analyse adaptative inchangés.

- **Calibrer le ton dans Histoires livré** : proposer trois concepts contrastés, préciser le degré d'absurde et d'excès des antagonistes par conversation, développer le concept choisi en scénario et dialogues. Deux appels d'écriture concepts/scénario, révisions facultatives. Garder les intentions sans caméra imposée et les dialogues validés exacts. P1/P2 inchangés ; l'autorisation de l'espace d'écriture ne lance pas automatiquement la production de l'épisode.

- **Aligner la suite de l'atelier Épisode après Histoires** : fiches personnages/décors → références et intentions → rendus → DLSS/livraison. Préciser REF2V direct ou image de départ puis I2V, et les étapes de validation. P1/P2 inchangées ; seule la partie d'écriture a été implémentée sur autorisation. Actualiser le navigateur pour retirer les anciennes entrées Production et afficher Histoires.

- **Aligner le point de départ de l'atelier Épisode** : question asynchrone posée (idée courte → épisode, vidéo exemple → adaptation, ou scénario déjà écrit → fabrication). En attendant, présenter les manques communs et une proposition conditionnelle à partir d'une idée, avec validation scénario/casting puis aperçu des clips. P1 amélioration I2V et P2 analyse adaptative restent leurs chantiers distincts ; pas de nouvelle priorité décidée ni de patch autorisé.

- **Valider le correctif REF2V livré** : utilisateur redémarre le Lab, rouvre la session `prompt-b08c5a9d2ca4447abbbe38d61efed33f` depuis REF2V ; le projet `h3-render-22b2bdeb73a94092894086b85365d070` doit reprendre REF2VA et ses deux images sans nouvel appel LLM. Exécuter les suites ciblées indiquées dans `docs/ref2v-classic-render-fix-2026-09-15.md`. P1 I2V, P2 analyse adaptative et EROS/BUNNY inchangés ; H3 demeure la référence figée de ce patch.

- **Contrainte REF2V persistante** : H3 figé (consignes, schéma, compilation, parcours et rendu). Si une future évolution nécessite de spécialiser les consignes/champs de références/assemblage, la livrer dans une version REF2V explicite. Conserver le socle commun existant sans effet de bord H3, deux appels, toutes les références dans leur ordre, grammaire REF2V et isolation des familles. Le patch de raccordement autorisé après cet alignement est livré ; aucune évolution des consignes requise dans ce correctif.

- **Suite de l'audit REF2V** : routage Classique Mise en scène, références, reprise et tests désormais livrés. L'amélioration de lisibilité des versions reprises reste une proposition séparée. Préserver les rôles d'images, les anciens projets et l'isolation Classique/Combat/Sensuel. P1 I2V 1.1 n'est pas encore implémenté sur H3 ; P2 analyse adaptative et presets EROS/BUNNY restent inchangés.

- **Aligner la pièce jointe KREA2 Modif** : proposer le guidage de la rédaction du prompt par une image libre liée à l'échange ; distinguer les rôles source, feedback et référence de changement. Implémenter seulement après demande, conserver P1 I2V/P2 analyse adaptative et le sampling Assisted livré.

- **Valider KREA2 Assisted sampling** : utilisateur redémarre le Lab puis Ctrl+F5. Vérifier Actuel par défaut, Finition 8+4, Moody Beta aux deux passes, Personnalisé après saisie, file de deux rendus à réglages distincts, Reprendre réglages et réouverture/branches, ancien essai à 8+2. Tests préparés et commande dans `docs/krea2-assisted-sampling-1.0.md`. Évaluer qualité sur mêmes checkpoint/prompt/LoRA/seed ; pas de promesse d'amélioration. P1 I2V Mise en scène 1.1, P2 analyse adaptative et sampling EROS/BUNNY restent au backlog ; aucun élargissement autorisé.

- **Prochain patch KREA2, lorsque demandé** : le choix des trois presets est désormais validé ; pas besoin de rediscuter les variantes. Implémenter le sélecteur et les réglages indépendants des deux passes avec sauvegarde/restauration par essai, actuel par défaut. Ne pas lancer ce patch pendant le seul échange d'alignement.

- **Aligner KREA2 sampling avant patch** : garder Actuel 8+2 par défaut, deux presets expérimentaux 8+4 (er_sde/simple et euler_ancestral/beta), paramètres propres à chaque passe sous Avancé. Prévoir instantané complet dans chaque essai et restauration par Reprendre réglages, sans réglage implicite dicté par le checkpoint. Conserver les priorités P1 Mise en scène I2V 1.1, P2 analyse vidéo adaptative et le lot distinct presets EROS/BUNNY. Aucun gain de qualité ni comportement GPU validé ; essais à faire par l'utilisateur après une éventuelle implémentation autorisée.

- **Valider la reprise de durée** : redémarrer le Lab puis Ctrl+F5 ; ouvrir un atelier H3 depuis un nouveau prompt, vérifier que Durée reprend le total prévu. Un atelier possédant déjà un essai reprend volontairement la durée enregistrée de cet essai, toujours modifiable. Tests préparés `test_h3_render.py` et `test_h3_render_controls_browser.py`, à exécuter par l’utilisateur.

- **Essai utilisateur du profil DLSS vidéo léger** : redémarrer le Lab puis Ctrl+F5 ; bouton rapide ou nouveau panneau avancé appliquent le profil demandé. Le bouton Profil vidéo léger remet les effets à ces valeurs après des changements manuels ; ×3 reste sélectionnable dans le menu avancé. Comparer un extrait court avec l’original, sans promesse de verrouillage du teint. Tests préparés : `test_dlss_image_defaults.py` et `test_dlss_browser.py`.

- **Après la snapshot GitHub `2026-09-14.2`** : redémarrer le Lab pour charger les validateurs Python, faire Ctrl+F5 pour le correctif LoRA KREA2, puis valider les deux parcours. La snapshot est une branche/tag de sauvegarde ; aucune fusion automatique vers la branche principale ou modification du remote local n’a été effectuée.

- **Valider le correctif Plan Sensuel** : l’utilisateur redémarre le Lab puis relance le Plan de la même session ou une préparation équivalente. Les formes `<d>English …</d>` correspondant exactement au registre et `from the camera position` ne doivent plus provoquer de retry ; toute parole différente ou vraie commande caméra doit encore être rejetée. Tests ciblés laissés à l’utilisateur : `tests.test_sensual_cinematic.SensualCinematicContractTest.test_plan_canonicalizes_exact_unbracketed_language_and_passive_camera_position` et `tests.test_minimax_h3_protocol.MiniMaxH3ProtocolTest.test_passive_camera_position_is_not_mistaken_for_camera_motion`.

- **Valider le correctif LoRA KREA2 Modif** : faire Ctrl+F5, importer une image puis vérifier immédiatement qu’un LoRA peut être choisi, retiré et que sa force reste modifiable. Aucun redémarrage du Lab n’est requis pour ce JavaScript statique. Test ciblé laissé à l’utilisateur : `tests.test_krea2_edit_web.Krea2EditWebTest.test_ui_is_single_workspace_with_backlog_reasoning_and_ten_loras`.

- **Valider le test Sensuel sans alignement** : l’utilisateur redémarre le Lab pour charger le nouveau schéma Python, puis crée une nouvelle préparation Sensuel plutôt que de reprendre un ancien Plan épinglé sur la révision 1. Comparer durée, raisonnement, rejets et résultat aux traces précédentes ; H3 Base doit indiquer la révision 2. Tests ciblés laissés à l’utilisateur : `tests.test_sensual_cinematic` et `tests.test_prompt_recipes`. Ne pas compacter schéma/exemples, changer le modèle ou propager à KREA2 avant cette mesure.

- **Après la sauvegarde GitHub du 14 septembre** : continuer les essais utilisateur de la version livrée ; P1 prompting I2V, P2 analyse adaptative et presets sampling EROS/BUNNY restent les prochaines évolutions, sans autorisation nouvelle liée à cette publication. Les erreurs H3 de dialogue/références restent diagnostiquées seulement.

- **Validation utilisateur Qwen 0.3.0** : redémarrer le Lab puis Ctrl+F5 ; retrouver 8 steps et dimensionnement automatique en avancé, essayer MP/format et reprise depuis l’historique. Tests ciblés documentés dans `docs/qwen-change-view-settings-0.3.0.md`, non lancés par l’agent. Pour H3, entourer les paroles imposées de guillemets ; le diagnostic est livré, aucune modification des recettes ni de leur contenu n’a été appliquée.

- **Validation du recadrage** : l’utilisateur redémarre le Lab et recharge la page, ouvre une étape KREA2 Modif, clique Recadrer la source, sélectionne/ajuste un rectangle et valide. Vérifier la nouvelle étape, le prompt vide et l’original dans l’historique ; les tests ciblés sont indiqués dans `docs/krea2-crop-1.0.md`. Aucun lancement autonome de tests, modèles ou services. Le patch de téléchargement Qwen précédent reste limité au PNG, sans transfert vers Modifier avec KREA2.

- **Validation du correctif KREA2** : l'utilisateur redémarre le Lab et recharge le navigateur pour prendre le nouveau décodeur et le téléchargement PNG. Tests ciblés préparés : `tests.test_krea2_edit_assistance_v3`, `tests.test_krea2_edit_workshop`, `tests.test_lab_web` (avec le PYTHONPATH du checkout actif). Pas de lancement autonome de tests, LLM, génération ni service. Le transfert vers Modifier avec KREA2 est exclu du patch sur demande explicite, ne pas l'ajouter.

- **Suite après implémentation** : l'utilisateur redémarre le Lab, recharge la page et exécute les tests du guide `docs/video-ux-prompt-editor-1.0.md`, puis essaie sauvegarde/application/retour de consignes et consulte les traces d'un nouveau rendu. Pas de lancement autonome de tests, modèle ou service. P1 I2V / Mise en scène 1.1, P2 analyse adaptative et branchement sampling EROS/BUNNY restent différés.

- **Proposition de premier patch prête** : aligner sur `docs/proposals/video-ux-prompt-editor-patch.md`, puis implémenter sur instruction utilisateur. Petits correctifs préalables séparés, UX validée, éditeur et historique durable dans la même livraison. P1/P2 hors périmètre et adaptation sampling EROS distincte ; snapshot préalable déjà publié.

- **Alignement à poursuivre : petit éditeur Recettes LLM + Échanges LLM durables après rendu**, en complément de l'UX vidéo déjà validée. Révision active persistante pour futurs cycles, retour simple à l'ancienne, conservation des historiques et isolation des familles ; fichiers seuls restent une alternative. Voir la proposition mise à jour. P1 I2V et P2 analyse adaptative inchangées.
- **Avant de retenter les entrées temporelles rejetées** : correctif ciblé proposé dans `docs/diagnostics/media-h3-duration-2026-09-14.md`, libellé « Durée cible » non reconnu et repères confondus avec des totaux. Les essais ont été diagnostiqués, pas patchés. Autre point séparé : contrat spatial caméra Classique insuffisamment explicite dans les consignes/schéma. Conserver les rendus en cours, ne pas relancer un LLM ni un service pour vérifier sans demande.

- **S'aligner sur UX vidéo + consignes LLM accessibles**, puis attendre l'instruction de patch : maquette validée, proposition `docs/proposals/editable-llm-prompts.md`. Dernières recettes H3/REF2V à deux étapes d'abord ; rendre les fichiers actifs réellement éditables, prévisualiser le système complet, préserver versions/archives et cohérence Plan/Writer. Migration à contenu constant, pas de correction silencieuse de la double politique vocale ni de changement I2V dans ce rangement. Le snapshot GitHub préalable existe (`934cd2f`, tag daté du 14 septembre).

- **Maquette validée, détails techniques de rendu à préserver au futur patch** : `docs/proposals/render-presets-v2.html` (aperçus PNG à côté). Aucune comparaison/série BUNNY. Presets EROS exécutables restent conditionnés à l'adaptation vérifiée des samplers et calendriers des deux passes. Respecter les anciennes recettes et paramètres ; les changements visuels n'autorisent pas un changement de génération implicite.
- **P1 en attente : Mise en scène I2V 1.1**, puis **P2 en attente : analyse média adaptative**. Priorités confirmées dans `docs/backlog.md` ; ne pas lancer ces implémentations à partir de la seule demande de maquette/analyse. Leurs périmètres sont documentés séparément, sans héritage automatique de prompting entre familles.

- **Simplifier le rendu avec un seul sélecteur de presets, sans comparaison dédiée** : cadrage actualisé dans `docs/proposals/bunny-sampling-presets.md`, ancienne maquette dépassée. Discussion uniquement pour le moment. Regrouper steps/sampling, replier les détails et conserver le parcours de lancement existant. Avant presets EROS/BUNNY exécutables, établir les vrais samplers et calendriers des deux passes et leur budget ; ne pas transformer les recommandations 4–8 steps en triplets arbitraires. Garder les réglages actuels disponibles et ne pas cumuler essai d'une nouvelle recette de prompt avec changement de sampling ou de LLM. Les presets MiniMax classiques recherchés par l'utilisateur pourront enrichir le catalogue avec leurs compatibilités. Aucun chantier de série comparative à implémenter.

- **Valider le périmètre de Mise en scène 1.1 avant son implémentation** : recette expérimentale distincte, 1.0 disponible longtemps comme référence ; démarrer par réduction des redites statiques sur première frame exacte, sans cumuler nouvelles politiques de dialogue, caméra ou invention d'événements. La présélection actuelle est déjà passée à l'expérimentale 1.0 dans H3/REF2V ; 1.1 n'existe pas encore. Préserver les choix explicites et versions des ateliers existants. Syntaxe seulement contrôlée pour ce changement UI ; pas de demande de tests ou générations de vérification.

- **Discuter l'adoption I2V centrée sur les changements** : éventuelle nouvelle recette Classique expérimentale, ajustement du Plan et de sa projection au prompt final uniquement quand une première frame exacte apporte déjà la scène. Conserver contexte interne pour le Writer, contrôles d'audace/dialogue/musique/plans et héritage exact des autres familles ; comparer ensuite à la version actuelle avec mêmes images, intention et paramètres. Aucun patch fonctionnel demandé dans le tour d'analyse de `I2v.txt`.

- **Essayer le second modèle pour le prompt final** : après les traitements en cours, redémarrer le Lab puis Ctrl+F5. Dans H3 Base/REF2V, choisir Classique Mise en scène 1.0, Combat 1.3 ou Sensuel 1.0, parcours deux étapes ; modèle principal pour le Plan puis cocher l'option pour choisir le Writer, éventuellement local indépendamment du Plan. Vérifier génération, réouverture et duplication ; après un échec du Writer, changer uniquement son modèle et relancer le prompt, Plan validé conservé. Décocher pour même modèle aux deux appels. Tests à lancer par l'utilisateur : `python -m unittest tests.test_prompt_writer_model tests.test_prompt_writer_model_browser tests.test_prompt_composition_storage`. Les réglages du Writer concernent la prochaine rédaction ; attribution des anciens appels dans le journal LLM, pas rétroactivement via le sélecteur.

- **Vérifier la ligne Dialogues et réactions** : Ctrl+F5 puis ouverture H3 et REF2V, sans toucher aux curseurs. La ligne doit être visible dès qu’une recette compatible est chargée, rester masquée avec une ancienne recette sans politique vocale, et conserver la valeur choisie entre changements de recettes. Correction JS seulement, pas de redémarrage serveur requis pour ce changement ; essais fonctionnels à effectuer par l’utilisateur.

- **Valider la comparaison DLSS image** : après ses traitements, l’utilisateur redémarre le Lab puis Ctrl+F5. Assisted/Edit → Upscale DLSS → Comparer des préréglages → choisir les profils et lancer. Vérifier compteur, disponibilité des autres ateliers pendant l’envoi/rendu, Comparer DLSS, cadrage conservé entre variantes et choix du résultat ; tester aussi Taille source masquée. Tests à lancer par l’utilisateur : `python -m unittest tests.test_dlss_image_comparison tests.test_dlss_image_comparison_browser tests.test_dlss_image_defaults tests.test_dlss_browser tests.test_dlss`. Effets visuels des cinq profils encore à évaluer par l’utilisateur ; aucune génération de vérification faite. DLSS vidéo reste au fonctionnement précédent.

- **Gemma local avec image** : appliquer dans les réglages avancés Unsloth propres aux Gemma concernés `--batch-size 2048 --ubatch-size 1120`, puis recharger le modèle après les traitements et réessayer une image côté utilisateur. Le diagnostic de l'assertion est confirmé, l'efficacité locale du réglage reste à valider. Suivre la PR Unsloth 10683 pour le défaut automatique ; ne pas modifier globalement Qwen/les autres modèles et ne pas relancer d'inférence pour vérification sans demande explicite.

- **Vérifier la correction du 13 septembre** : lorsque le Lab est lancé, Ctrl+F5 puis accès aux projets récents en haut à gauche, contenu du projet à droite, catalogue compact dans le panneau. Contrôler changements rapides de projet et reprise de catalogue. Exécuter par l’utilisateur `tests.test_image_catalog_browser` (inclut désormais vrai HTML/CSS/module Assisted) ; tests préparés non lancés. Si le message catalogue persiste, relever son texte complet : le Lab était arrêté pendant l’intervention et le cache présent ne prouve pas la disponibilité actuelle de Bucket/LLM.

- **Valider la fluidité Image Lab** : après ses traitements, l’utilisateur redémarre le Lab puis recharge la page. Ouvrir plusieurs projets Assisted/Edit pendant l’actualisation, vérifier les réglages et le masque conservés, les fiches au clic et la reprise du cache au redémarrage suivant. Tests factices préparés et procédure dans `docs/image-lab-background-catalog.md` ; mesurer le gain dans l’application, aucun benchmark runtime ni test lancé par l’agent.

- **Valider les défauts DLSS image** : après ses traitements, l’utilisateur redémarre le Lab et recharge la page. Ouvrir une image Assisted et Edit : ×1,5, quatre réglages à 1, peau −1, style Default ; lire les « i », vérifier reset explicite et conservation des choix en rouvrant. Taille source reste sélectionnable pour les retouches masquées ; vidéo conserve ×1,724 + 60 FPS. Tests préparés `tests.test_dlss_image_defaults`, `tests.test_dlss`, `tests.test_dlss_browser`, non exécutés par l’agent.

- **Valider le correctif caméra Sensuel** : l'utilisateur exécute `tests.test_sensual_cinematic`, redémarre/recharge le Lab quand ses traitements sont termines, puis relance un Plan proche du smoke. Verifier que le system prompt journalise contient la liste des prefixes et que toute nouvelle clause invalide reste rejetee sans mutation du candidat courant.

- **Valider Sensuel 1.0** après redémarrage du Lab et Ctrl+F5 par l’utilisateur : exécuter `tests.test_sensual_cinematic` et `tests.test_sensual_controls_browser`, puis essayer le même scénario adulte consenti en H3 Base et Ref2V avec Auto puis un nombre imposé. Vérifier les deux appels Plan → Writer, la précision littérale des actions/contacts, la reprise de dernière frame, la conversion Ref2V et l’absence de changement dans Classique/Combat. Calibrer les futurs niveaux Soft/Explicite seulement après ce retour qualitatif.

- **Valider la récupération JSON Analyse média** : l’utilisateur redémarre le Lab après ses traitements, puis peut réessayer une analyse depuis les captures conservées. Exécuter `tests.test_media_analysis` ; aucun nouvel appel automatique ni réécriture des anciens échecs. Guide et version GitHub dans `docs/media-analysis-json-recovery-2026-09-11.md`. Le patch n’implémente pas le choix de priorité à l’action encore en discussion.

- **Valider la correction Writer `phases2`** : après ses traitements, l’utilisateur redémarre le Lab puis peut conserver le Plan déjà approuvé et relancer uniquement la rédaction. Tests préparés `tests.test_classic_cinematic` et `tests.test_prompt_boundary_regressions`, non exécutés par l’agent. Le JSON brut rejeté n’est pas réécrit automatiquement dans l’historique.

- **Valider navigation/aperçus** après Ctrl+F5 : visiter une page puis rafraîchir, notamment H3, REF2V, Edit et Analyse média ; vérifier indépendance des onglets. Rouvrir une fiche LoRA H3 déjà renseignée et lire un aperçu vidéo, fermer pour vérifier son arrêt, contrôler les images KREA2. Tests utilisateur et détails dans `docs/navigation-resource-previews-2026-09-11.md` ; aucune nouvelle récupération des sidecars ni redémarrage du Lab requis pour ce correctif UI.

- **Vérifier EROS Turbo dans H3 et REF2V** après redémarrage du Lab par l’utilisateur et actualisation du sélecteur de modèle : choisir « EROS · Turbo intégré · hybride beta5 », décocher le Turbo supplémentaire BUNNY, garder ses steps d’essai. Test préparé `tests.test_h3_checkpoints.H3CheckpointCatalogTest`, à exécuter par l’utilisateur ; qualité du nouveau checkpoint non évaluée par l’agent.

- **Vérifier Turbo/historique/fiches LoRA/Writer du 11 septembre** : procédure et tests dans `docs/h3-turbo-history-lora-writer-2026-09-11.md`. Après les traitements en cours, l’utilisateur redémarre le Lab pour les nouvelles routes/schémas puis recharge l’interface. Tester EROS intégré avec Turbo BUNNY décoché et steps adaptés au checkpoint ; retrouver les récents ateliers Mise en scène ; ouvrir une fiche LoRA sans toucher aux forces ; relancer la rédaction depuis le Plan déjà validé, sans troisième appel automatique. Tests et validation visuelle par l’utilisateur.

- **Valider les correctifs média/H3 du 11 septembre** : tests/procédure dans `docs/media-h3-boundary-fixes-2026-09-11.md`. Après ses traitements, redémarrage Lab et rechargement par l’utilisateur ; reprendre l’ancienne analyse via Enregistrer/Préparer pour nettoyer les citations. Pour un ancien Plan rejeté sans aucune langue déclarée, corriger ses balises ou refaire le Plan avec le schéma enrichi ; pas de langue devinée ni de relance par l’agent. Vérifier caméra fixe, paroles exactes et séparation Classique/Combat. Aucune modification de la priorité descriptive/action avant retour d’essai.

- **Tester la transcription locale 1.1** : guide `docs/media-analysis-speech-1.1.md`, CPU désormais par défaut. L’utilisateur recharge l’interface et redémarre le Lab quand compatible avec ses traitements ; aucune action de service par l’agent. Vérifier extrait décalé, texte corrigé, inclusion/exclusion des répliques, annulation, réouverture, retour au visuel seul ; exécuter les tests préparés. Puis discuter la priorité action/T2V/I2V/REF2V après son essai, sans changer les consignes prématurément.

- **Tester Analyse média V1**, implémentée sur autorisation : après ses traitements, l’utilisateur redémarre le Lab et ouvre Video Lab → Analyser des médias. Tests et procédure dans `docs/media-analysis-1.0.md`. Vérifier un extrait vidéo décalé, des captures ajoutées/retirées, une série 0/1/3 s réordonnée, intention corrigée/reprise, transfert des références explicites vers H3/REF2V ; évaluer la précision visuelle avec le modèle local. Aucun test, LLM, génération ou redémarrage à sa place.

- **Tester Classique Mise en scène 1.0**, après redémarrage du Lab par l’utilisateur : exécuter les tests préparés, puis comparer ancien/nouveau Classique sur des intentions calmes et actives, mono et multi, à images et réglages constants. Vérifier Auto/priorité manuelle, reprise et conversion. Aucun changement de défaut avant retour qualitatif ; guide `docs/h3-classic-cinematic-1.0.md`. Le snapshot GitHub préalable est publié (entrée Current state).

- **Validation utilisateur des quatre LoRA de rendu** : procédure/tests dans `docs/h3-four-loras.md`. Après ses traitements, l’utilisateur recharge le Lab et choisit H3 **0.1.6**, REF2V **0.2.4** ou BUNNY **0.1.3**. BUNNY garde Combat V2 → Motion Repair à **0,60/0,20 chacun**, puis permet deux ajouts facultatifs. Comparer deux/quatre LoRA, déplacer/désactiver une ligne, reprendre les réglages et vérifier les deux passes. Une reprise historique garde sa recette ; sélectionner la nouvelle recette pour dépasser deux. Aucun test, LLM, rendu ou service à lancer à sa place.

- **Validation utilisateur des checkpoints vidéo** : tests préparés et procédure dans `docs/h3-checkpoint-selection-proposal.md`. Après ses traitements, l'utilisateur recharge le Lab puis choisit une recette actuelle et **Modèle vidéo → EROS** ; comparer à défaut avec mêmes prompt/seed/MP/LoRA/Turbo, vérifier reprise et conversion. Les poids/performances GPU restent non testés ; conserver l'inventaire explicite et ne pas modifier implicitement les réglages selon le checkpoint. Aucun test ou rendu à lancer à la place de l'utilisateur.

- **P0 : validation utilisateur de Combat 1.3 à deux appels**. Après ses traitements, recharger le Lab et choisir Combat → 1.3 → Plan/rédaction dans H3 ou REF2V. Lancer les tests préparés de `docs/h3-combat-1.3.md`, puis comparer Plan/prompt/vidéo et Intense/Déchaîné avec les mêmes références et réglages. Examiner pouvoirs dominants, grands déplacements, caméra/raccords et identité ; une bonne syntaxe ne garantit pas le rendu. Ne lancer aucun test, LLM, génération ou service à la place de l’utilisateur.

- **Combat 1.3 : parcours un/trois appels différés expressément**. Garder seulement deux appels pour la nouvelle direction tant que l’utilisateur ne demande pas d’élargissement. Les anciennes versions continuent à proposer leurs trois parcours. Ajuster les exemples/politiques à partir des résultats observés, sans changer silencieusement la version d’un atelier ou les paramètres de rendu.

- **P0 courant : validation utilisateur de Combat 1.2.0 et du sélecteur corrigé**. Après ses traitements, l'utilisateur redémarre le Lab et recharge la page. Vérifier les trois parcours en H3/REF2V pour 1.1.1 puis 1.2.0, choisir une orientation et comparer à intention/références/seed/LoRA constants. Tester reprises et révisions ; garder action/plans indépendants. Commande des tests préparés dans `docs/h3-combat-1.2.md`, exécution utilisateur uniquement. Ne pas relancer de service, test, appel LLM ou génération à sa place. Les observations 1.1 ci-dessous restent pertinentes pour calibrer action et montage.

- **H3 débloqué** : l’utilisateur peut relancer son rendu actuel ; aucun essai n’a été lancé à sa place. Le correctif préventif et son message de conflit seront chargés lors de son prochain démarrage habituel. Tests `python -m unittest tests.test_h3_render_recovery` à exécuter par lui ; pas de redémarrage/service/test automatique. Ne pas reprendre cet ancien identifiant distant disparu ni restaurer son état running depuis la sauvegarde sans nouvelle preuve.

- **P0 Combat 1.1 : validation utilisateur**. Implémentation livrée ; lancer les tests ciblés du guide `docs/h3-combat-1.1-proposal.md` puis observer Dynamique/Intense à nombre de plans fixe, et 1/3 plans à intensité constante. Calibrer les niveaux par les rendus, sans quotas d'actions. Conserver les ateliers 1.0 et les valeurs BUNNY/LoRA/MP/seed. Aucun test, LLM, rendu ou service à lancer à la place de l'utilisateur.

- **Deux chantiers conservés en backlog sur demande utilisateur** : analyse vidéo/images → prompt (P1, proposition Video Lab dans `docs/backlog.md`) et Sensualité / jeu d’acteur non explicite. Ne pas les démarrer pendant le patch Classique expérimental. Recherche de seeds toujours mise de côté.

- **Défauts de rendu à constater au prochain rechargement utilisateur** : H3 courant 0.1.3 et REF2V courant 0.2.1, seed coché, MP initiaux/après upscale 0,2/0,2 modifiables indépendamment. Un ancien essai repris conserve sa recette/valeurs ; choisir Rendu actuel 0.2.1 pour quitter le REF2V historique. Ne plus revenir aux défauts REF2V 1,2 MP / seed décoché dans de futurs patches d’interface. Tests et générations restent à l’utilisateur.

- **Priorité : observation utilisateur de la fluidité Assisted** après son prochain rechargement du Lab. Enchaîner ses rendus habituels, observer délai de réactivation du bouton et stabilité des images pendant l’attente. Si la lenteur persiste, lire le `Server-Timing` du POST et distinguer attente réseau/catalogue du worker, parcours global de file et coût navigateur. Ne pas lancer soi-même de génération, test ou redémarrage. Exécutions de tests et appréciation réelle des gains laissées à l’utilisateur. Poursuivre ensuite la passe sur les fonctions défaillantes/lisibilité, sans suppression spéculative ; Combat implémenté, en attente d’observation utilisateur.

- **Validation utilisateur du patch dialogue / adaptation** : relancer le Lab et recharger l’interface quand ses traitements sont terminés. Essayer la liberté vocale dans les trois parcours actuels, puis « Adapter en REF2V » depuis le prompt édité ; vérifier références, réglages BUNNY/actuel, réouverture, brouillon d’erreur et navigation sans rendu automatique. Tests préparés dans le guide, à exécuter par l’utilisateur. Ne lancer aucun test, LLM, génération ou service à sa place.

- **Récupérer l’incident DLSS** : après chargement du correctif `LocalAssetStore.register_file`, utiliser Reprendre sur `dlss-a7f23157fc80efab0bb6bf2457d026bd`. Le MP4 natif est déjà présent ; la reprise devrait refaire uniquement l’import si l’historique Comfy réussi est disponible. L’agent n’a pas relancé le job ni modifié ses données.

- **Sauvegarde avant BUNNY terminée** : tag `snapshot-avant-bunny-h3-2026-09-09`, commit `f2a61a5`, publiés et vérifiés sur GitHub. Ne pas refaire ou déplacer ce point de restauration. Pour le patch à venir, conserver explicitement les recettes de génération actuelles H3 / REF2VA dans le sélecteur, comme confirmé par l’utilisateur. Ne pas remplacer le défaut actuel par BUNNY ni modifier les réglages historiques ; pas de test, rendu ou redémarrage à lancer à sa place.

- **Sujet courant : validation BUNNY par l’utilisateur sur Bucket**, patch implémenté, guide `docs/bunny-h3-render.md`. Après son redémarrage habituel du Lab : sélectionner BUNNY, essayer les modes image/first-last et REF2VA, preview puis absence de Turbo, comparer les résolutions réelles et les deux forces du LoRA ; revenir au rendu actuel pour comparaison. Exécuter lui-même les tests préparés (commande dans le guide). Aucun rendu/test/installation ou service à lancer à sa place. Observer qualité, mémoire, audio et comportement réel du profil 30/25/5 avant de conclure ; ne pas remplacer le défaut historique.

- **Validation restante : nouveaux médias DLSS référencés sans copie dans assets**. Chemin direct du dernier fichier confirmé et anciennes copies `.bin` déjà expliqués. Après ses traitements, l’utilisateur relance `run_lab.py` puis recharge la page : vérifier sur son prochain upscale le chemin local affiché, absence de nouveau `content.bin` pour le média final, lecture/feedback/continuation, progression et copie vidéo serveur. Tests préparés `tests.test_dlss_outputs`, `tests.test_dlss`, `tests.test_dlss_progress_export`, `tests.test_dlss_browser`, `tests.test_local_storage`, `tests.test_run_lab_build`, exécution utilisateur uniquement. Ne pas supprimer l’ancien catalogue, ne pas lancer soi-même un rendu/test ni redémarrer un service.

- **Sujet courant : vérifier le patch DLSS vidéo rapide + copie serveur**. Après redémarrage du Lab et rechargement par l’utilisateur : essayer une courte vidéo avec Upscale DLSS ×1,724/60 FPS, préparer un prompt ou générer une autre vidéo pendant ce traitement, contrôler phases/fin sans vol de sélection puis MP4/JSON dans `X:\data\ComfyUI\output\video\Upscale\<date-du-jour>`. Tester le bouton avancé et la reprise de copie séparée si partage indisponible. Tests préparés `tests.test_dlss`, `tests.test_dlss_progress_export`, `tests.test_dlss_browser`, `tests.test_run_lab_build`, **exécution utilisateur seulement**. Ne pas lancer de génération, test ou service pour vérifier. Qualité, audio/cadence réels et coexistence GPU restent à expérimenter.

- **Révision caméra** : au prochain redémarrage du Lab par l’utilisateur, réessayer une demande de maintien des sujets visibles avec `shake.slightly`. Vérifier qu’elle reste dans la prose au moment concerné et que les directives restent valides, sans mouvement fixe imposé. Tests ciblés préparés dans `tests.test_h3_render.H3RenderRevisionVersionTest`, exécution par l’utilisateur uniquement. La réparation du dernier atelier était déjà acceptée ; aucun besoin de reconstruire son plan. Ne pas promettre la disparition du zoom vidéo à partir du seul correctif de contrat.

- **Prochaine validation DLSS par l’utilisateur** : après son prochain redémarrage du Lab et rechargement de la page, commencer par une image puis une courte vidéo avec Unsloth ouvert. Comparer Original / DLSS, taille source contre finition dans Edit, masques, feedback/export et dernière frame vidéo ; essayer ensuite nettoyage/arrêt depuis « DLSS local ». Tests simulés préparés et commande dans `docs/dlss-local.md`, exécution par l’utilisateur uniquement.

- **Après les premiers essais DLSS** : observer qualité, durée et mémoire avant d’envisager arrêt automatique ou exclusion mutuelle avec Unsloth. Ne pas déclencher de rendu, test ou service à la place de l’utilisateur. L’intégration décor/sujet ci-dessous reste disponible indépendamment ; les anciens points de discussion décrivent l’historique, pas des autorisations manquantes pour le patch livré.

- **Priorité : expérimenter l’intégration à deux images** après redémarrage/rechargement par l’utilisateur à son rythme. Assisted → essai → Replacer dans un décor → choisir le décor maître → Ouvrir dans Edit, puis Lancer un rendu explicitement. Comparer d’abord architecture/cadrage, action/accessoires et netteté sur une paire. Les tests préparés et limites du premier essai sont dans `docs/krea2-restaging.md`, exécution par l’utilisateur uniquement. Le collage Assisted est désormais retiré ; les points de discussion/implémentation ci-dessous décrivent les états antérieurs.

- **Priorité après retour négatif sur le collage** : discuter/valider un essai Identity Edit à deux entrées, décor en A et sujet/action Assisted en B. Comparer d’abord la stabilité du décor, la fidélité de l’action et la netteté ; utiliser le même décor maître d’une scène à l’autre. Raccordement et nouvelle UI non implémentés, ne pas lancer de génération à la place de l’utilisateur. Le parcours masque ci-dessous reste disponible comme outil local, pas la piste principale de cohérence entre ces scènes.

- Après redémarrage/rechargement par l’utilisateur à sa convenance, essayer **Composer avec une autre image** sur le candidat Assisted coffre/diamants, avec l’image versement comme base. Peindre les zones évolutives, inspecter les restes éventuels de l’ancien personnage et les différences de perspective ; décider ensuite si une pièce vide commune ou un outil de placement est nécessaire. Tester reprise de masque et choix du candidat au feedback/export. Commande des tests préparés dans `docs/krea2-assisted-composition.md`, exécution par l’utilisateur uniquement ; aucune qualité visuelle validée par l’agent.

- FireRed intégré : l’utilisateur peut redémarrer/recharger le Lab à son rythme puis lancer les tests préparés dans `docs/firered-edit.md`. Vérifier les deux modes depuis la même source, les échanges puis le masque/validation/reprise ; comparer la netteté à 1 MP avant de monter la résolution. Aucun rendu d’évaluation à déclencher par l’agent ; le comportement réel n’a pas été testé pendant le codage.

- Après redémarrage du Lab par l’utilisateur et rechargement de la page, Ref boost peut dépasser 10 jusqu’à 1000. Tests existants préparés dans `test_krea2_edit`, `test_krea2_edit_workflows`, `test_krea2_edit_web` et `test_krea2_edit_workshop`, exécutés par lui uniquement ; aucun résultat visuel évalué pour ces valeurs élevées.

- Au prochain redémarrage du Lab par l’utilisateur, recharger la page et vérifier l’ouverture Edit, les trois ateliers récents et le bouton pour les autres. Ouvrir un ancien atelier, replier puis actualiser : sa frise, ses essais et ses brouillons doivent rester disponibles. Tests à lancer par lui uniquement, commande dans `docs/krea2-edit-and-presets.md`. Si l’ouverture reste lente, distinguer le GET du catalogue modèles (`spec`) et celui des ateliers ; aucun gain temporel chiffré annoncé sans mesure.

- Unsloth : dans le terminal qui relance le Lab, renseigner une clé API Studio valide via `PANELFORGE_LOCAL_LLM_API_KEY`, puis reprendre la commande habituelle et recharger la page. L'URL locale par défaut est `http://127.0.0.1:8888/v1`. Ne pas transmettre la clé dans le chat ou les logs. Distinguer l'erreur d'authentification du catalogue d'une absence réelle de modèles ; l'environnement du processus Lab précédent n'a pas pu être vérifié avant son arrêt.

- L'utilisateur peut redémarrer le Lab, recharger la page, sélectionner un essai réussi dans Après, puis **Améliorer les détails → Lancer**. Comparer ClearReality à l'original, éventuellement choisir un autre modèle dans le panneau replié. Essayer aussi une retouche enregistrée pour juger raccords et netteté avec le masque conservé. Tests à lancer par lui seulement, commande dans `docs/krea2-edit-upscale.md`. Aucun second passage KREA2 génératif ni upscale automatique de toute la chaîne.

- Charger le correctif HTTP 500 en redémarrant le Lab à la convenance de l'utilisateur, puis réessayer la préparation du rendu Edit. Test ciblé préparé : `python -m unittest tests.test_krea2_edit_web.Krea2EditWebTest.test_imported_workflow_defaults_and_selection_are_exposed_without_rendering`, à exécuter par lui uniquement. ComfyUI n'a pas besoin d'être redémarré pour ce correctif de contrat HTTP.

- Upscaling désormais facultatif sur un essai sélectionné : distinguer résolution, texture reconstruite et raccord du masque lors de la comparaison ; les MP d'Identity Edit restent inchangés.

- L'utilisateur peut redémarrer/recharger à sa convenance, ouvrir **Modifier avec KREA2 → Paramètres du rendu → Base importée · Qwen standard (0.2.0)**, puis **Reprendre les réglages de base** s'il souhaite Turbo/Ref boost4/10 steps/sans LoRA ajouté. Ratio/MP/seed/prompt conservés. Comparer avec Historique 0.1.0 ; pour isoler l'encodeur, changer seulement le workflow en conservant les autres contrôles. Tests ciblés et limites de compatibilité dans `docs/krea2-edit-workflow-base-2026-09-08.md`, exécutés par lui seulement. Upscaling facultatif disponible via le bouton du comparateur ; ne pas lancer de rendu de comparaison à sa place.

- L'utilisateur peut redémarrer/recharger à sa convenance puis choisir **Modifier avec KREA2 → Version du prompting → V3 — Modifications ciblées** sur son étape actuelle (elle conserve V2 à la réouverture). Comparer avec V2, mêmes source/intention/réglages/seed, en gardant à l'esprit que changer de writer ne remet pas la mémoire à zéro. Tests ciblés dans `docs/krea2-edit-prompting.md`, à lancer par lui. Réglages Turbo/Raw à discuter séparément ; résolution de génération conservée et upscaling facultatif disponible. Ne pas confondre Edit V3 et Création assistée V3.

- L'utilisateur peut redémarrer/recharger à sa convenance, choisir **Type de séquence → Multi-plan**, puis tester deux plans en préparation à deux étapes avec first seule (versement puis étalement au même cadrage). Inspecter les actions/états dans le Plan et la vidéo, puis reprendre la dernière frame pour demander l'ajout de diamants. Comparer ensuite 1/3 étapes, first+last et last seule ; texte seul secondaire. Guide et tests ciblés dans `docs/h3-multishot-preparation.md`. Tests et générations exécutés par l'utilisateur uniquement, aucune capacité visuelle acquise sur la seule base des contrôles statiques.

- L'utilisateur peut recharger la page et vérifier le carillon sur ses prochains rendus H3/Ref2V et images, y compris une série Assisted, puis consulter l'historique pour vérifier l'absence de bip supplémentaire. Test hors ligne `tests.test_render_notifications` à lancer par lui uniquement. Le navigateur doit avoir reçu une interaction pour activer l'audio ; aucun test audible ou rendu lancé par l'agent.

- L'utilisateur peut tester les trois recettes H3 **1.1.0** après son redémarrage/rechargement : même paire mur plein/ouverture, même intention/durée/modèle/axes/audace, vérifier retrait → dégagement → finition dans les prompts avant de juger la vidéo. Choisir 1.0.0 dans l'historique pour comparer, ou « Repartir de ce run » pour créer un nouveau parcours sans modifier l'ancien. Tests ciblés dans `docs/video-preparation-recipes.md`, à exécuter par lui. Aucune nouvelle campagne LLM/rendu à lancer par l'agent.

- L'utilisateur peut tester **Reprendre depuis cette étape** après son redémarrage/rechargement : choisir une étape validée au milieu d'une chaîne, reprendre ses réglages (dont MP), vérifier ancienne version active pendant le brouillon, puis valider un candidat et consulter l'ancienne suite via le sélecteur. Tests ciblés dans `docs/krea2-edit-versions.md`, à exécuter par lui seulement. Vérifier notamment retouche reprise, essai validé différent du dernier, export distinct et navigation entre versions sans perte de brouillon.

- L'utilisateur peut comparer Assisted V3 dans un nouvel atelier après son redémarrage/rechargement ; anciens projets V1/V2 restent sur leur recette. Lui laisser exécuter les tests préparés et ses rendus, avec essai sélectionné en feedback pour donner au LLM les pixels du défaut.

- L’utilisateur peut vérifier les réglages H3 après son redémarrage/rechargement : nouvel atelier avec les deux MP à 0,2 et seed réutilisée, changement indépendant des deux valeurs, reprise d’un ancien essai puis rendu à sa main. Tests ciblés préparés dans `docs/h3-render-resolution.md`, à exécuter uniquement par lui. Recettes LLM inchangées, recherche de seeds toujours en attente.

- L’utilisateur peut vérifier **Recommencer cette étape** et le sélecteur **Image à gauche** : tests ciblés du guide puis redémarrage/rechargement à sa convenance. Sur une étape en cours, confirmer la reprise et vérifier conversation/essais vides, source inchangée et étapes précédentes intactes ; dans Retoucher, peindre puis alterner source/génération et annuler sans perdre le masque. Continuer l’évaluation couleurs/raccords et validation du candidat Après. Ne lancer aucun test ni service à sa place.

- L'utilisateur exécute les tests ciblés du guide `docs/krea2-edit-retouch.md`, puis redémarre/recharge le Lab lorsque ses générations le permettent pour charger le patch masque. Ne lancer aucun test ni service à sa place. Le tag `stable-avant-masque-2026-09-06` reste le point de restauration.

- Validation manuelle du masque à sa main : dessin et gomme sur un essai existant, fermeture/reprise du brouillon, enregistrement distinct, reprise du masque sauvegardé, choix d'un candidat autre que le dernier pour feedback et validation, inspection frise/export. Recueillir son retour sur les raccords de netteté et le confort des deux vues avant toute extension vidéo ou recalage automatique.

- Recherche de seeds en attente à la demande de l'utilisateur. Conserver `docs/h3-seed-search-audit-2026-09-07.md` pour une reprise ultérieure explicite ; aucune implémentation à lancer pour le moment.

- Au prochain lancement/rechargement du Lab par l'utilisateur, vérifier l'affichage des 33 checkpoints KREA2, dont Ultra v1.5, Kreamania variant 8 et IntoRealism v4.0. Le chemin par défaut est maintenant corrigé ; la disponibilité du montage SSHFS reste indépendante. L'incident de file Assisted qu'il a écarté ne doit pas être rouvert dans ce patch. Les autres pistes ci-dessous restent historiques ou secondaires.

- Sick Ollie et Sinox sont désormais présents et sélectionnables après déplacement/ajout utilisateur. Recharger la page pour retrouver les entrées, groupe précision inconnue si nécessaire. Une éventuelle recette propre à Sick Ollie (Euler/Beta) reste à discuter ; aucun réglage modifié pour cette sauvegarde.

- L'utilisateur lance ses tests puis redémarre/recharge lorsqu'il le souhaite pour l'atelier Edit et les presets implémentés. Vérifier conversation/réouverture, comparaison et zoom frise, validation vers nouvelle étape avec Ref boost/steps conservés ; presets nouveau/mise à jour, sélection initiale et en cours, prochain échange et retour de branche. Ne pas effectuer ces validations à sa place. Audit visuel de la dérive cartoon maintenant disponible dans `docs/krea2-edit-quality-drift-2026-09-05.md` : discuter du compromis fidélité/transformation et d'une éventuelle édition locale avec recomposition ; essais sans LoRA de détail à la main de l'utilisateur, sans modification automatique du workflow. Vidéo hors périmètre.

- Presets désormais implémentés avec « continuer avec B ». Les points de retour spécifiques avant application restent une évolution ultérieure ; les branches existantes et snapshots d'essais conservent déjà le preset sélectionné. Vérification de la référence initiale Assisted par l'utilisateur : premier échange avec référence, échange suivant sans elle, renvoi explicite comme inspiration, réouverture et branche vide ; aucun test à lancer à sa place.

- L'utilisateur relance sa commande `run_lab.py` habituelle après le correctif d'import. Puis reprendre les validations Ref2V et branches à sa main. L'idée du preset KREA (réglages + prompt d'exemple optionnel) lui convient ; son implémentation vient après la résolution du lancement.

- L'utilisateur peut charger le backend corrigé puis reprendre Prompt H3 des parcours Ref2V une/deux étapes et sa révision caméra fixe. Conserver le Plan deux étapes déjà approuvé. Vérifications hors ligne et réelle génération restent à sa main ; aucun résultat réel post-correctif démontré. Recueillir son choix sur le preset KREA rapide avec prompt d'exemple optionnel avant implémentation.

- L'utilisateur peut vérifier les branches Image Lab après ses tests puis son redémarrage/rechargement : nouveau rendu → échanges suivants → « Repartir d’ici » → retour à l'autre piste → réouverture, prompt/réglages/seed conservés et deux aperçus visibles. Vérifier aussi l'action explicite image + prompt sur un ancien essai. Voir `docs/krea2-conversation-branches.md`. Ne pas lancer ces validations à sa place.

- Recueillir le retour utilisateur sur la règle spatiale V2 ; préparer avec lui les états visuels du chantier accéléré selon `docs/accelerated-work-video-experiment.md`, puis le laisser lancer l'essai H3. L'objectif est d'observer la causalité outil/matière, pas seulement l'apparence finale.

- Après son redémarrage, l'utilisateur peut relancer uniquement Prompt H3 du run Ref2V moto → avion en deux étapes ; contrôler aussi les recettes trois étapes et les rôles keyframe lors de ses tests. Correctif de l'en-tête non validé par exécution pendant le développement.

- L'utilisateur exécute les vérifications hors ligne puis redémarre/recharge quand il le souhaite. Comparer 3/2/1 sur les mêmes références/intention/modèle/axes/audace ; vérifier réouverture, fork, rédaction/révision directe et arrivée dans le même espace de rendu. Aucun gain de qualité/latence démontré à ce stade. Ne lancer aucun test, LLM, rendu ni redémarrage sans nouvelle instruction explicite.

1. L'utilisateur lancera les tests puis, quand ses générations sont terminées, redémarrera/rechargera : KREA V2, H3 Base `0.4.0` et Ref2V `0.5.0` seront sélectionnés par défaut. Vérifier création KREA avec image seule et reprise des projets V1. Ne pas exécuter ces validations à sa place.
   Vérifier aussi le bouton de suite depuis H3 Base et Ref2V : dernière frame exacte en première image, intention à remplir, dernier essai source conservé ; bouton indisponible si la frame de fin manque.
2. Comparer avec les témoins sur sujet objet/main, dragon avant/après, séquence causale, mouvement continu et dialogue exact ; relever durée, fidélité et erreurs. Les défauts expérimentaux sont un choix utilisateur, aucun gain n'est encore mesuré.
3. Après ses retours, corriger les écarts puis définir les rôles First/Last réassignables et points de reprise visibles. L'automatisation Ref2V et les vidéos longues restent ultérieures.

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

## Patch 2026-09-17 — famille Histoires « Chats de couple · muet »

### Works
- La vidéo de référence `Download(25).mp4` a été auditée : environ 15 s, format vertical, un couple de chats anthropomorphes réalistes dans une cuisine, gag d’attention insistante puis étreinte tendre, sans narration nécessaire.
- La famille indépendante `story.silent-cats@1.0.0` possède ses propres concepts, scénario et révision. Elle cible deux chats adultes photoréalistes, une situation domestique, une escalade gestuelle et une bascule tendre.
- Le silence est contractuel : `dialogue_policy=forbidden`, exemple de contrat avec `dialogue: []`, registre de dialogue forcé à 0 et rejet backend de toute réplique. Les intentions sans réplique demandent explicitement zéro parole, voix off ou narration.
- L’interface affiche `Chats de couple · muet`, adapte les aides, désactive le curseur de vocabulaire et masque les dialogues dans l’éditeur de scène. Les histoires d’une seule micro-scène de 5 à 15 s sont désormais autorisées pour reproduire le format court de la référence.
- La recette est enregistrée séparément dans le lanceur et reste éditable depuis `Consignes LLM` sans modifier Fruits, Sensuel light ou Cru ++.
- Validation ciblée : compilation Python, `git diff --check` et 55 tests Histoires/Fabrication/API/navigateur passent.

### Broken / missing
- Aucun appel LLM réel, rendu KREA2 ou rendu H3 n’a encore qualifié le photoréalisme, la stabilité des deux chats et l’absence effective de voix sur le moteur vidéo.
- La suite complète du worktree n’est pas verte indépendamment de cette surface : 1 223 tests donnent 36 échecs et 44 erreurs, principalement dans les contrats H3/combat/rendu. Les 55 tests couvrant les fichiers modifiés sont verts.

### Next steps (max 3)
1. Redémarrer PanelForge et générer une proposition `Chats de couple · muet` avec 1 micro-scène de 15 s.
2. Fabriquer les deux fiches chats et le décor avec un checkpoint/réglage KREA2 photoréaliste, puis vérifier que les identités restent nettement distinctes.
3. Rendre la scène en vidéo et vérifier l’absence de parole/voix off ainsi que la lisibilité du gag uniquement par les gestes.

### Risks / open questions
- Le style photoréaliste est imposé éditorialement dans les descriptions, mais le résultat dépend encore du checkpoint, du preset et des LoRA KREA2 choisis dans Fabrication.
- Les vocalisations félines non linguistiques sont autorisées par la recette ; si H3 les transforme en parole ou en chant, il faudra durcir le compilateur vidéo après un smoke réel.

## Patch 2026-09-17 — accueil de KREA2 Création assistée

### Works
- `Nouveau projet` est maintenant le premier bloc de la colonne, avant `Projets récents`, et reste volontairement replié au premier affichage même lorsque l'historique est vide.
- Le nouveau projet sélectionne en priorité la variante locale `unsloth/gemma-4-31b-it-qat-GGUF` lorsqu'elle existe. Une sélection manuelle reste stable pendant les rafraîchissements ; après création, le formulaire suivant revient au défaut.
- Un bouton `Actualiser` voisin du sélecteur relance le catalogue sans recharger la page. Il respecte le rafraîchissement asynchrone du backend, affiche l'état en cours puis le résultat au prochain polling et ne remplace pas les modèles historiques des projets ouverts.
- Les versions de cache CSS/JS ont été relevées. Validation ciblée : `git diff --check` sans erreur et 36 tests KREA2 Assisted UI/domaine/API/sampling/navigation réelle passent.

### Broken / missing
- Aucun smoke dans le Lab réel n'a été fait contre l'instance Unsloth ; si Gemma n'est pas publié dans son inventaire, le sélecteur conserve le premier modèle local disponible.
- Deux tests KREA2 Assisted plus larges restent rouges pour des raisons hors patch : la fixture navigateur DLSS ne déclare pas `jobs`, et un test V2 attend `glass_model` au-delà de la limite actuelle de 12 checkpoints du catalogue de test.

### Next steps (max 3)
1. Redémarrer PanelForge et forcer un rechargement navigateur pour prendre les nouveaux assets.
2. Ouvrir `Nouveau projet`, vérifier Gemma local par défaut, puis tester `Actualiser` pendant que l'inventaire Unsloth est disponible.
3. Créer puis rouvrir un projet utilisant un autre modèle afin de confirmer que son choix historique reste inchangé.

### Risks / open questions
- Le bouton dédié utilise aujourd'hui le rafraîchissement de catalogue commun du backend : les inventaires image et LLM sont rescannés en arrière-plan, même si seul le retour LLM est mis en avant dans ce formulaire.

## Patch 2026-09-17 — nombre exact de micro-scènes Histoires

### Works
- Le nombre choisi dans `Format de l'épisode` est désormais une contrainte exacte pour les développements, Scripts fidèles et révisions qui renvoient un scénario. Une réponse `discussion_only` reste autorisée sans scénario.
- En Script fidèle, le contrat demande explicitement de traiter titres, numéros et rubriques comme des événements source à regrouper. Il autorise la condensation du découpage et des descriptions, mais interdit l'omission d'un événement, la modification de l'ordre/de la fin et la paraphrase des dialogues.
- Le validateur refuse une taille différente avant toute application du document. Il ne lance aucun appel de réparation : la version précédente reste intacte et le brouillon fautif demeure disponible.
- L'interface affiche `Nombre exact de micro-scènes`, explique le regroupement et marque les projets avec `micro-scènes exactes`. Documentation et cache `stories.js?v=20260917.3` sont actualisés.
- Une régression reproduit le brief des sept événements de chats avec une cible de trois : trois scènes sont acceptées, sept sont refusées. Validation : 56 tests Histoires/Fabrication/API/navigateur passent et `git diff --check` ne signale aucune erreur.

### Broken / missing
- Aucun appel au modèle réel n'a encore confirmé que Gemma regroupe spontanément les sept événements en trois dès le premier essai. S'il ignore le contrat, PanelForge refuse proprement la sortie au lieu de relancer automatiquement.
- Le contrôle garantit le nombre de scènes, pas la présence sémantique de chaque événement non dialogué ; cette fidélité reste une instruction au Writer et doit être vérifiée lors du smoke.

### Next steps (max 3)
1. Relancer exactement le brief des chats avec 3 × 10 s et vérifier le regroupement attendu.
2. Contrôler qu'aucun des sept événements n'a disparu et que la troisième scène raccorde naturellement boutique et galerie.
3. Si Gemma échoue souvent malgré le contrat, discuter d'une correction explicite par l'utilisateur ou d'un retry optionnel, sans l'ajouter silencieusement.

### Risks / open questions
- Un script contenant beaucoup de dialogues peut tenir structurellement dans le nombre demandé tout en étant trop dense pour la durée. Le diagnostic de densité reste non bloquant afin que le choix utilisateur continue de faire foi.
- Une ancienne histoire dont le document contient plus de scènes que sa cible reste lisible et modifiable manuellement. Sa prochaine révision structurée devra en revanche revenir au nombre exact enregistré.

## Patch 2026-09-17 — sélecteurs LLM locaux de la fabrication en lot

### Works
- Les profils `Personnages` et `Décors` affichent désormais chacun le sélecteur LLM classique avec une case `Local · Unsloth`, cochée par défaut.
- Le composant partagé filtre le catalogue selon cette case : cochée, il expose les modèles `local::`; décochée, il expose les modèles serveur. Le modèle local mémorisé n'est donc plus marqué indisponible simplement parce que le panneau filtrait implicitement le mauvais catalogue.
- La bascule déclenche aussi la mise à jour des contrôles et du résumé de lot. Les versions de cache `episodes.css` et `episodes.js` passent à `20260917.2`.
- Validation ciblée : 56 tests Histoires/Fabrication/API/navigateur passent, dont une régression navigateur Local → serveur → Local pour les deux profils. `git diff --check` ne signale aucune erreur de contenu.

### Broken / missing
- Aucun smoke n'a encore interrogé l'instance Unsloth réelle. Si le catalogue local est réellement vide après rechargement, le problème restant sera la découverte `/api/stories/models`, distincte du filtrage d'interface corrigé ici.
- Une suite élargie incluant `tests.test_lab_web` conserve quatre échecs hors périmètre sur des attentes H3/Ref2V déjà désynchronisées avec les scripts actuels.

### Next steps (max 3)
1. Redémarrer PanelForge et forcer un rechargement navigateur pour charger `episodes.js/css?v=20260917.2`.
2. Ouvrir `Histoires → Fabrication`, vérifier Unsloth dans les deux profils puis décocher/recocher `Local · Unsloth`.
3. Si aucun modèle local n'apparaît, examiner alors la réponse réelle de `/api/stories/models` et la disponibilité du serveur Unsloth.

### Risks / open questions
- Le choix local est initial au chargement, mais chaque profil conserve ensuite indépendamment son modèle sélectionné dans l'état de l'histoire.

## Patch 2026-09-17 — rafraîchissement unifié de KREA2 Création assistée

### Works
- Une seule commande compacte `Tout actualiser` apparaît dans l'en-tête de Création assistée. Son icône à deux flèches tourne pendant la requête et expose un libellé accessible.
- Elle lance en parallèle le rescan forcé des modèles/LoRA KREA2 et des LLM, le rechargement des presets de style et celui des projets récents. Les trois anciens boutons séparés ont été retirés.
- Le statut compact du catalogue reste visible sans bouton propre. Un échec partiel indique la ressource concernée sans masquer les autres résultats.
- Le rafraîchissement conserve le projet ouvert, le prompt non enregistré, les sélections de modèles et les presets encore disponibles. Les caches passent à `lab.css?v=20260917.2` et `krea2-assisted-lab.js?v=20260917.2`.
- Validation ciblée : les 21 tests statiques KREA2 Assisted plus la régression navigateur réelle du rafraîchissement unifié passent ; les tests API KREA2 Assisted et le contrat principal de la page Lab passent également. `git diff --check` ne relève aucune erreur de contenu.

### Broken / missing
- Aucun smoke n'a encore été fait dans le navigateur utilisateur contre les catalogues et presets réels.
- Le test navigateur indépendant de fermeture d'une fiche de ressource pendant son chargement reste intermittent : Chromium conserve parfois brièvement l'ancien dialogue fermé dans le DOM. Cet échec préexistant ne touche pas le rafraîchissement unifié ; la régression navigateur de Création assistée est verte.
- L'automatisation vidéo Histoires n'est pas commencée dans ce patch.

### Next steps (max 3)
1. Redémarrer PanelForge, faire un rechargement forcé et vérifier le bouton tournant dans l'en-tête avec les quatre familles de données réelles.
2. Concevoir l'écran vidéo Histoires autour d'une liste complète de cartes de scènes, avec profil commun, surcharge par scène, état du prompt, rendu et résultat intermédiaire.
3. Verrouiller les transitions et files : prompts LLM séquentiels, vidéos distantes ordonnancées, validation humaine, puis DLSS manuel par scène sans lancer de nouveau LLM.

### Risks / open questions
- Le rescan des catalogues peut continuer côté serveur après la réponse initiale ; le message compact indique alors l'actualisation en arrière-plan même si l'animation du clic est terminée.
- Pour la vidéo Histoires, il faudra décider si le bouton de génération globale s'arrête après tous les prompts ou peut aussi remplir automatiquement la file vidéo après une validation humaine globale.

## Patch 2026-09-17 — réglages communs lean et chaîne vidéo Histoires

### Works
- Snapshot préalable publié : `44a9b7f`, branche et tag `snapshot-stories-pre-video-2026-09-17`.
- Un seul bloc Direction artistique + KREA2 pilote style, image d’inspiration, workflow, checkpoint, LoRA et sampling. Les profils Personnages/Décors héritent explicitement ou conservent une personnalisation isolée ; format, MP, seed et LLM restent par profil.
- Les anciens profils sans marqueur d’héritage sont traités comme personnalisés. Un changement ou une réapplication de preset ne les écrase donc pas.
- Les réglages vidéo possèdent une révision commune et une copie effective par scène. Durée et seed restent propres à la scène ; la personnalisation coupe l’héritage et le retour aux réglages communs est explicite.
- Le renderer REF2V peut ouvrir ses seuls contrôles de réglage avant qu’un projet/prompt existe. Cette capacité est optionnelle et utilisée seulement dans Fabrication.
- La vue Scènes affiche toutes les micro-scènes, leur état de prompt/rendu, la vidéo produite, l’accès à l’éditeur détaillé et le DLSS manuel lorsqu’il est éligible.
- La chaîne prépare les prompts séquentiellement, laisse le rendu distant précédent progresser pendant le prompt suivant, ne démarre qu’une vidéo à la fois, et persiste erreurs, résultats, pause coopérative et reprise. Aucun écran de queue technique n’est ajouté.
- Validation : 27 tests ciblés verts, compilation Python et `git diff --check` réussis. La suite complète exécute 1 229 tests avec 35 échecs et 44 erreurs hors périmètre déjà présents dans les contrats H3/Combat et fixtures historiques.

### Broken / missing
- Aucun smoke réel n’a encore validé les appels Unsloth, les rendus KREA2/H3, l’attente thermique, la pause pendant une vraie génération ou le lancement DLSS depuis une carte.
- L’assemblage des scènes, les transitions et l’export d’un épisode complet restent hors périmètre.
- Node.js n’est pas installé ; la syntaxe JS est couverte par les tests navigateur ciblés, pas par `node --check`.

### Next steps (max 3)
1. Redémarrer, faire `Ctrl+F5`, puis tester héritage commun et profil personnalisé avec un preset réel.
2. Sur un épisode court de deux ou trois scènes, régler le profil vidéo avant les prompts, lancer la chaîne, demander une pause puis reprendre et vérifier les vidéos sur les cartes.
3. Une fois tous les prompts et rendus terminés, lancer manuellement un DLSS depuis une carte et confirmer qu’aucun nouvel appel LLM ne démarre.

### Risks / open questions
- Une interruption de processus est récupérable par `Reprendre`, mais un rendu ComfyUI distant encore actif au redémarrage doit être réconcilié par le projet H3 avant de relancer afin d’éviter un doublon ; à vérifier au smoke réel.
- La vue globale affiche l’état de production sans exposer la file interne, conformément au choix UX. Les priorités entre une action manuelle hors Histoires et la chaîne restent celles du coordinateur global FIFO.

## Patch 2026-09-17 — faux positif caméra et lisibilité de la chaîne

### Works
- `toward Roux's sly tilted head` est valide : `tilted` peut décrire une pose de sujet. Les mouvements cachés `tilting down` et `tilted down` restent rejetés, de même que les mentions explicites de caméra.
- Le résumé global sépare désormais les compteurs Prompts et Vidéos et qualifie la chaîne active, en pause, interrompue ou terminée.
- Les cartes distinguent prompt prêt, vidéo en attente, rendu en cours, vidéo terminée et erreurs sans répéter le même libellé. Une tâche en cours est animée et porte `aria-busy`; l'animation est coupée si le navigateur demande moins de mouvement.
- Les assets Episodes utilisent la révision de cache `20260917.4`.
- Validation : 45 tests ciblés passent et `git diff --check` ne relève aucune erreur de contenu.

### Broken / missing
- Le processus PanelForge déjà lancé doit être redémarré pour charger le nouveau validateur Python ; un `Ctrl+F5` est ensuite nécessaire pour les nouveaux JS/CSS.
- Le run actuellement enregistré conserve normalement l'ancien échec de scène 1 jusqu'à l'action `Reprendre la chaîne`.

### Next steps (max 3)
1. Laisser finir le rendu H3 déjà actif avant de redémarrer PanelForge.
2. Redémarrer, faire `Ctrl+F5`, puis reprendre la chaîne : les scènes 2 et 3 réussies doivent être ignorées et seule la scène 1 retentée.
3. Vérifier que le résumé affiche simultanément les compteurs prompts et vidéos pendant ce retry.

## Patch 2026-09-18 — transformations visuelles conditionnelles Histoires

### Works
- Le scénario accepte un `visual_transition` strictement optionnel avec quatre étapes : `before`, `trigger`, `visible_change`, `after`. Un objet incomplet est rejeté ; une scène sans transformation conserve exactement son ancien document et son ancien prompt de fabrication.
- Les appels Writer/Révision apprennent à n’utiliser ce champ que pour un changement visuel important et persistant. Script fidèle interdit d’inventer un déclencheur ou un résultat absent de la source.
- Une édition manuelle qui change réellement l’état initial, l’action ou l’état final retire l’ancien marqueur plutôt que de conserver silencieusement une transition devenue incohérente.
- La famille Chats muets exige ce contrat pour une guérison ou un changement important d’état physique, d’objet, de tenue ou de salissure. Le prompt Fabrication rappelle que les quatre temps doivent être compris sans parole, narration ni texte écran.
- La compilation se fait seulement dans l’atelier Histoires et son export ; H3 Direct et REF2V Direct ne passent pas par ce chemin et restent inchangés.
- Validation : 56 tests Histoires/Fabrication/API/navigateur passent, compilation Python et `git diff --check` réussissent.

### Broken / missing
- Les scénarios déjà enregistrés ne sont pas réécrits automatiquement. Pour profiter du nouveau contrat, il faut demander une révision ou générer une nouvelle histoire, puis créer une nouvelle fabrication si le scénario a changé.
- Aucun rendu H3 réel n’a encore vérifié la guérison du chat avec les quatre temps visuels.
- La suite complète reste rouge hors de cette surface : 1 358 tests exécutés, 40 échecs et 33 erreurs dans les contrats/fixtures H3, Combat et historiques déjà désynchronisés ; les tests ciblés modifiés restent verts.

### Next steps (max 3)
1. Redémarrer PanelForge puis générer ou réviser la scène du chat malade.
2. Vérifier dans le prompt résolu de Fabrication la présence du bloc `TRANSITION VISUELLE À MONTRER DANS CE CLIP` uniquement sur la scène de guérison.
3. Rendre quelques seeds et comparer la lisibilité de l’état malade initial, du déclencheur et de l’état final guéri.

### Risks / open questions
- Le champ améliore le contrat narratif mais ne rend pas H3 déterministe ; un état initial très bref peut encore nécessiter un ajustement de l’action ou un autre seed.

## Diagnostic 2026-09-18 — REF2V classique et Spectrum

### Works
- Les données du run montrent trois échecs récents `minimax-h3-ref2v@0.2.4` avec `spectrum_enabled=true`, tous sur `FinalLayer.forward() missing sigma, sample_sigmas, shifts`.
- Le nouvel essai du même projet, même recette et même checkpoint avec `spectrum_enabled=false` démarre normalement ; l’utilisateur confirme que le rendu sans Spectrum fonctionne.
- Le workflow PanelForge transmet correctement le booléen au nœud `SpectrumApplyMiniMaxH3`. La panne se situe dans le wrapper Spectrum chargé par ComfyUI 0.36.0, pas dans le workflow REF2V classique ni dans le prompting Histoires.
- La release officielle Spectrum `v0.2.21` annonce précisément la compatibilité avec le nouveau contrat PDD et la correction de cette exception.

### Broken / missing
- La version réellement chargée du custom node Spectrum sur le serveur n’est pas exposée par PanelForge. Le traceback prouve néanmoins que son ancien chemin à quatre arguments est encore exécuté.
- Aucun correctif applicatif n’a été appliqué. Spectrum reste opt-in et désactivé par défaut.

### Next steps (max 3)
1. Continuer les rendus REF2V classique avec Spectrum désactivé.
2. Mettre à jour `ComfyUI-Spectrum-MiniMax-H3` vers `v0.2.21` ou plus récent, puis redémarrer complètement ComfyUI.
3. Faire un essai court avec Spectrum réactivé ; si l’erreur persiste, vérifier que ComfyUI charge bien les fichiers du nouveau commit et qu’aucune seconde copie du custom node n’existe.

## Patch 2026-09-18 — langue parlée des dialogues Histoires

### Works
- Le formulaire Nouvelle histoire propose `French`, `English`, `Korean`, `Japanese` et `Russian`, avec libellés lisibles et Français sélectionné par défaut. La langue et le registre restent deux axes indépendants.
- Le projet persiste `dialogue_language`. Les histoires historiques sans ce champ sont normalisées sur `French`; la famille Chats muets désactive visuellement le choix et conserve une valeur technique neutre `French`.
- Les appels d’écriture reçoivent la langue cible sans appel supplémentaire. Seul `dialogue.text` change de langue ; descriptions, actions, autres champs narratifs et `reply` restent en français. Les registres 1–3 demandent un oral/argot naturel dans la langue cible plutôt qu’une traduction littérale des exemples français.
- Script fidèle déclare la langue réellement présente, conserve les paroles mot pour mot et interdit traduction, translittération et reformulation. Le registre reste forcé à zéro comme auparavant.
- Les exports d’intentions affichent la langue parlée. Une Fabrication nouvelle la copie dans son snapshot ; la préparation de chaque scène impose ensuite le nom canonique dans `spoken_languages` afin que le compilateur Classique produise la balise H3 correspondante. Les ateliers H3 Direct et REF2V Direct ne sont pas modifiés.
- Le cache `stories.js` passe à `20260918.1`. Des régressions couvrent persistance, validation API, héritage Français, Script fidèle, Chats muets, interface et propagation coréenne vers Fabrication. Vérifications effectuées : parsing AST Python et `git diff --check`; aucune génération, aucun service et aucun test automatisé lancé.

### Broken / missing
- La qualité de prononciation et de synchronisation pour le coréen, le japonais et le russe n’a pas encore été qualifiée sur un rendu H3 réel.
- La V1 est volontairement monolingue par histoire : aucune surcharge par scène ou par réplique et aucune traduction automatique d’un scénario existant.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` afin de charger `stories.js?v=20260918.1`.
2. Créer une courte histoire dans une langue non française et vérifier que les descriptions restent françaises tandis que toutes les répliques utilisent la langue choisie.
3. Ouvrir sa Fabrication et contrôler dans le prompt préparé la balise finale `<d>[Korean|Japanese|Russian|English] …</d>` correspondant au choix avant de lancer un rendu court.

### Risks / open questions
- H3 peut varier en qualité selon la langue et la voix ; le contrat garantit la langue déclarée dans le prompt, pas la qualité acoustique du moteur.
- Un utilisateur qui colle un script français tout en sélectionnant Japonais obtient volontairement un contrat incohérent plutôt qu’une traduction silencieuse. L’aide UI demande de sélectionner la langue réellement écrite ; une future détection pourrait rester un warning non bloquant.

## Audit 2026-09-18 — passe d’upscale H3 et dernier run Histoires

### Works
- Les recettes courantes H3 Base `minimax-h3-latent-speed@0.1.6` et REF2V `minimax-h3-ref2v@0.2.4` suivent toutes deux : diffusion principale, upscale latent 3D, raffinement de trois étapes, puis décodage.
- Le nœud officiel `MinimaxH3LatentUpscaler3D` retourne l’entrée inchangée à une échelle effective de 1,0 ; avec le même ratio et les mêmes dimensions alignées, l’upscale seul est donc bien inutile.
- Le raffinement qui suit reste néanmoins une vraie seconde diffusion. Court-circuiter toute la branche à MP égaux accélérera le rendu mais pourra changer le résultat ; cela mérite un A/B avant d’en faire le défaut.
- Sur la dernière histoire `story-31c126346a544990a5fc781f3cae9d60`, l’appel Ideas Qwen a duré 186,0 s avec 60 167 caractères de raisonnement pour 2 239 caractères de réponse. Le développement Gemma a duré 69,8 s avec 3 419 caractères de raisonnement pour 5 651 caractères de réponse.
- Le long raisonnement Qwen boucle surtout sur le choix de l’antagoniste et de la fin. La sortie est valide, mais une partie de la fin longuement arbitrée est abandonnée par le Writer ; le coût supplémentaire n’est donc pas proportionnel au gain observé.

### Broken / missing
- Les graphes publiés ne possèdent pas encore de chemin de décodage direct depuis la première passe ; aucun bypass n’a été implémenté.
- Le contrôle actuel accepte des MP finaux inférieurs aux MP initiaux hors BUNNY, alors que l’upscaler officiel refuse une échelle effective inférieure à 1,0.
- Le scénario final a trois avertissements de densité de dialogue (29, 27 et 40 mots pour 10 s) et sa dernière scène finit surtout sur un état émotionnel, alors que la recette demande une conséquence accomplie.

### Next steps (max 3)
1. Comparer quelques seeds à MP initial = MP final avec et sans la branche upscale + raffinement pour mesurer qualité, temps et cohérence.
2. Si le bypass est retenu, comparer les dimensions effectives alignées à 32 pixels, décoder directement la première passe à égalité et rejeter une cible réellement inférieure.
3. Tester un profil Ideas plus court sur le même brief (budget de raisonnement ou modèle Architecte plus sobre) avant de modifier les plafonds globaux.

## Alignement 2026-09-18 — bypass upscale et garde thermique vidéo

### Works
- Décision proposée pour A/B : lorsque la résolution cible effective est égale ou inférieure à la résolution initiale, décoder directement la première passe ; lorsque la cible est supérieure, conserver upscale latent + raffinement. Une cible inférieure bypassée sort donc à la résolution initiale et n’effectue pas de downscale.
- Un contrôle temporaire `Forcer l’upscale` doit permettre de rejouer l’ancienne branche à dimensions égales avec le même seed. Sous la résolution initiale, le vrai upscaler ne peut pas être forcé car son contrat interdit une échelle inférieure à 1,0.
- Les vidéos Histoires utilisent bien `H3RenderService.execute_attempt`, qui prend un lease `REMOTE_GPU` auprès du coordinateur commun avant de soumettre le workflow ComfyUI.
- La politique active observée via l’API est `stop=85 °C`, `resume=40 °C`, `cooldown=120 s`, surveillance distante active. Le H3 en cours était à 81 °C : sous 85 °C, son départ immédiat est conforme à la politique actuelle.

### Broken / missing
- Le garde thermique est un seuil d’urgence, pas un refroidissement systématique entre rendus : si le job suivant acquiert la machine à 84 °C, il part immédiatement. Le délai de 120 s ne s’applique qu’après franchissement de 85 °C, une fois la température redescendue à 40 °C.
- La chaîne vidéo Histoires ne possède ni réglages thermiques ni snapshot propre. Elle réutilise la politique globale du coordinateur, actuellement configurée depuis le lot d’images de référence ou initialisée par défaut ; ce couplage est peu visible et surprenant.
- Les décisions thermiques ne sont pas historisées par job. On peut confirmer le chemin de code et la politique live, mais pas reconstruire après coup la température exacte à l’instant où chaque vidéo a démarré.

### Next steps (max 3)
1. Valider la sémantique thermique souhaitée : simple seuil d’urgence, ou refroidissement obligatoire entre deux vidéos distantes.
2. Au prochain patch, persister et afficher la politique thermique propre à la chaîne vidéo, avec un état explicite `Refroidissement` lorsqu’elle attend.
3. Implémenter le bypass et le contrôle A/B dans de nouvelles versions de recettes H3 Base et REF2V, sans modifier les manifests publiés.

## Proposition 2026-09-18 — upscale auto, repos vidéo et monitoring Histoires

### Goal
- Livrer un patch cohérent couvrant : bypass de la branche upscale lorsque la cible effective n’est pas supérieure, pause distante obligatoire de 30 s entre deux vidéos, et monitoring Histoires lisible sans interrompre la lecture des résultats.

### Proposed behavior
- H3 Base courant et REF2V courant : cible effective supérieure => upscale + finition ; cible égale ou inférieure => décodage de la première passe. Une cible inférieure produit la résolution initiale, sans downscale. BUNNY reste hors périmètre.
- Une case temporaire partagée `Forcer l’upscale · test A/B` réactive l’ancienne branche à dimensions égales. Elle est persistée avec l’essai, visible dans son résumé et désactivée sous la résolution initiale.
- La chaîne Histoires stocke `inter_video_cooldown_seconds=30`. Après une vidéo réellement exécutée et avant la suivante, le serveur distant reste réservé mais inactif pendant 30 s ; les appels LLM locaux peuvent continuer.
- Le repos fixe précède le garde thermique existant. Après les 30 s, si le seuil thermique est atteint, l’attente thermique se prolonge selon `stop/resume/stabilisation`.
- Le monitoring expose deux voies distinctes : `LLM local` avec le nom de la scène promptée et `GPU distant` avec la scène rendue, en refroidissement ou en attente. Deux progressions remplacent le compteur global ambigu : prompts prêts et vidéos terminées.
- Les cartes conservent deux états indépendants, Prompt et Vidéo. Une pause demandée nomme les tâches qui terminent et ce qui ne démarrera pas.

### UX / technical findings
- Le polling actuel tourne toutes les deux secondes et `drawVideoOverview()` appelle `replaceChildren()` sur toutes les cartes. Chaque rafraîchissement détruit puis recrée les éléments `<video>`, ce qui interrompt la lecture.
- Le patch proposé réconcilie les cartes par `scene_id`, conserve le même lecteur tant que son `asset_id` ne change pas et met à jour seulement textes, badges, compteurs et nouveaux médias.
- Le compte à rebours repose sur un `cooldown_until` serveur persisté ; l’UI le rafraîchit chaque seconde localement et le recale sur le polling. Pause/reprise et rechargement ne réinitialisent donc pas artificiellement les 30 s.

### Implementation slices
1. Nouvelles versions des manifests H3 Base/REF2V et décision de branche testée sur les dimensions effectives alignées ; propagation/persistance du booléen A/B dans le composant H3 partagé et les essais.
2. Contrat de chaîne vidéo enrichi (`prompt_status`, `video_status`, scène active, cooldown configuré et échéance), réservation distante de 30 s entre rendus et état public avec temps restant.
3. Monitoring DOM stable, deux voies actives, deux barres de progression, badges par scène, pause explicite et tests navigateur prouvant qu’un polling ne remplace pas un lecteur en cours.

### Open points
- Le repos obligatoire ne retarde pas la fin après la dernière vidéo : il s’applique seulement lorsqu’une vidéo suivante existe.
- Une erreur avant toute exécution Comfy ne déclenche pas le repos ; une tentative ayant réellement occupé le GPU le déclenche même si elle termine en échec.

## Patch 2026-09-18 — bypass upscale, repos distant et monitoring Histoires

### Works
- Nouvelles recettes courantes et isolées : H3 Base `minimax-h3-latent-speed@0.1.7` et REF2V `minimax-h3-ref2v@0.2.5`. Les versions `0.1.6` et `0.2.4` restent rouvrables comme historiques.
- La décision compare les dimensions effectives sur la grille 32 px. Une cible supérieure conserve upscale latent + raffinement ; une cible égale ou inférieure reconnecte les décodeurs à la première diffusion et élague réellement les nœuds inutiles du graphe. Une cible inférieure sort à la résolution initiale, sans downscale.
- Le contrôle temporaire `Forcer l’upscale` est commun à H3 et REF2V, persiste avec l’essai et réactive l’ancien chemin uniquement à dimensions égales. Il reste caché pour BUNNY et les recettes historiques.
- La chaîne vidéo Histoires persiste un repos configurable de 1 à 3 600 s, 30 s par défaut. Après un rendu et avant le suivant, le lease `REMOTE_GPU` reste détenu pendant le compte à rebours ; les traitements locaux peuvent continuer. Le garde thermique normal est ensuite évalué à l’acquisition suivante.
- Le statut machine expose l’opération de refroidissement et les secondes restantes. La chaîne persiste aussi `cooldown_until` et la scène concernée afin que l’interface puisse afficher un timer fiable.
- Le monitoring Histoires affiche deux voies et deux progressions distinctes : prompt/LLM local et rendu/GPU distant. Chaque voie nomme la scène active, distingue file/rendu/refroidissement et explique la pause coopérative.
- Les cartes vidéo sont maintenant réconciliées par `scene_id`. Le lecteur n’est remplacé que si son `asset_id` change ; un polling de statut n’interrompt plus la lecture.
- Documentation : `docs/h3-upscale-bypass-and-story-cooldown.md`. Cache frontend H3/Episodes passé à `20260918.1`.
- Validation : compilation Python, `git diff --check` et 82 tests ciblés verts. La suite complète exécute 1 365 tests et reste rouge avec 47 échecs et 33 erreurs sur les contrats/fixtures historiques déjà désynchronisés ; aucun échec n’apparaît dans la surface ciblée de ce patch.

### Broken / missing
- Aucun rendu ComfyUI réel n’a encore comparé visuellement le bypass et la finition forcée avec une même seed.
- Le monitoring conserve volontairement le statut de chaîne compact existant et en dérive les deux voies ; il n’ajoute pas deux machines d’état persistées indépendantes par scène.
- Le contrôle A/B est temporaire et devra être retiré après qualification visuelle.

### Next steps (max 3)
1. Redémarrer PanelForge et faire `Ctrl+F5` pour charger les assets `20260918.1` et les recettes courantes `0.1.7` / `0.2.5`.
2. À MP initiaux = MP cible, comparer deux rendus avec la même seed, bypass par défaut puis `Forcer l’upscale`, et relever temps/qualité.
3. Lancer au moins deux scènes Histoires et vérifier le timer de 30 s, le nom des scènes dans les deux voies et la lecture continue d’une vidéo pendant le polling.

### Risks / open questions
- Le bypass retire aussi les trois étapes de finition ; le gain de temps est certain au niveau du graphe, mais son effet visuel dépendra des contenus et checkpoints.
- Une tentative ayant réellement été soumise déclenche le repos même si ComfyUI finit en échec, choix conservateur pour le matériel.

## Patch 2026-09-18 — suivi global permanent et file KREA2 réservée

### Works
- Le faux `failed` des appels LLM streamés est corrigé à la source : fermer le générateur après un événement terminal `completed` ou `truncated` termine désormais le lease normalement. Une fermeture avant le terminal reste bien un échec/abandon.
- Les vrais échecs de l’ordonnanceur conservent maintenant le type et un message d’erreur borné dans l’historique ; le dialogue détaillé les affiche sous le traitement concerné.
- Le popup est permanent et présente exactement deux lignes, `Local` et `Serveur`, avec un badge `Ready`, `Working`, `Cooldown`, `Unavailable` ou `Paused`, une barre de progression, le traitement courant et un compteur `N en attente`, y compris à zéro.
- La couleur suit le contrat UX : Ready vert, Working orange, Cooldown bleu, Unavailable/Hot rouge et Paused gris. Le dialogue complet conserve les commandes pause/reprise, les prochaines tâches, les réglages et l’historique.
- Les essais KREA2 Assisted réservent leur ticket dans la FIFO distante dès leur mise en file. Les lots suivants sont donc visibles dans le compteur global avant que leur worker commence, gardent leur ordre face aux autres traitements distants et libèrent leur ticket s’ils sont annulés avant admission.
- L’identifiant ComfyUI est attaché aux activités H3/KREA2. Le websocket global normalise les événements H3 avec le profil de progression propre à la recette, alimente le coordinateur puis met à jour la barre compacte sans progression fictive.
- Cache frontend global passé à `20260918.3`. Validation : compilation Python, `git diff --check`, 55 tests ordonnanceur/KREA2/H3/navigateur verts et le test websocket runtime ciblé vert. Une passe élargie a 136 tests verts sur 137 ; le seul échec est le test Retouch historique `test_restart_removes_stage_memory_and_attempts_and_archives_the_old_state`, reproductible seul et sans rapport avec ce patch.

### Broken / missing
- KREA2 conserve pour l’instant ses jalons applicatifs (préparation, envoi, récupération, import) : contrairement à H3 et DLSS, ses manifests n’exposent pas encore un profil de progression ComfyUI suffisamment fiable pour calculer un pourcentage continu.
- Les anciennes lignes `failed` déjà présentes en mémoire ne peuvent pas être réinterprétées ; le redémarrage vide cet historique en mémoire et tous les nouveaux appels utilisent la correction.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger les assets `20260918.3`.
2. Lancer deux images KREA2 Assisted et un H3 : vérifier le compteur distant, l’ordre des libellés puis la progression H3 en direct.
3. Provoquer si possible une vraie erreur contrôlée et confirmer que son message apparaît dans `Derniers traitements`, sans faux `failed` après une réponse LLM réussie.

### Risks / open questions
- Une réservation KREA2 `submitting` ambiguë bloque volontairement la voie distante jusqu’à sa réconciliation ou son annulation ; c’est le comportement sûr pour ne pas doubler une soumission ComfyUI inconnue.
- La progression H3 globale dépend de la connexion websocket du Lab, comme la télémétrie actuelle. Sans navigateur connecté, le statut serveur reste sur les jalons applicatifs mais l’exclusion mutuelle et la FIFO continuent de fonctionner.

## Correctif 2026-09-18 — progression H3 réelle dans le suivi global

### Works
- Cause confirmée sur un rendu BUNNY réel : ComfyUI adresse les événements `executing`/`progress` au `client_id` ayant soumis le prompt. Le moniteur global utilisait le client `panelforge-runtime-*`, alors que H3 soumet avec `panelforge-h3-render-*` ; il recevait donc la télémétrie Crystools, mais jamais les pas du sampler.
- `/api/runtime/events` se connecte désormais au canal H3 lorsqu’il existe, avec repli sur le canal runtime générique. La télémétrie Crystools reste disponible car elle est diffusée à tous les clients.
- Les événements ComfyUI sont normalisés avec le profil versionné de la recette, puis répercutés dans `MachineWorkCoordinator` et dans le popup global. Le libellé indique la phase et le compteur courant, par exemple `Première passe · étape 2/4`, et la barre affiche le pourcentage global de la recette.
- Le websocket de preview H3/REF2V republie également le même événement navigateur vers le suivi global. Cela couvre les écrans directs sans créer une seconde logique de calcul côté frontend.
- Sur BUNNY `0.1.3`, `2/4` dans la première passe correspond à environ `24 %` global (plage 5–42 %), puis les phases upscale, seconde passe, décodage et sauvegarde poursuivent la même barre.
- Cache frontend passé à `work-queue.js?v=20260918.4` et `h3-render-lab.js?v=20260918.2`.
- Validation : compilation Python et 46 tests ciblés verts (websocket runtime, canal H3 prioritaire, normalisation des deux passes, UI du suivi global, H3). Un test H3 UI historique reste rouge sur l’ancien contrat LoRA `video_lora: elements.videoLoraProfile`, sans rapport avec ce correctif ; le module Video Lab retiré de la navigation garde aussi un ancien test d’endpoint en erreur sur `input_mode`.

### Next steps (max 3)
1. Laisser finir le rendu actif, puis redémarrer PanelForge et faire `Ctrl+F5` afin de charger le nouveau backend websocket et les assets frontend.
2. Lancer un H3 ou REF2V et vérifier que la ligne Serveur passe de `Envoi à ComfyUI · 8 %` aux phases et pas réels sans revenir en arrière.
3. Si une recette tierce reste figée, vérifier son `progress_profile` dans le manifest plutôt que d’ajouter des pourcentages spécifiques dans l’interface.

## Correctif 2026-09-18 — reprise des scènes en erreur et refroidissement sans course

### Works
- La chaîne Histoires continue après un échec de prompt isolé et termine en `completed_with_errors`, sans bloquer les scènes suivantes.
- `Relancer les scènes incomplètes` ne rejoue que les scènes en échec. Chaque nouvelle tentative possède un `request_id` distinct, tout en réutilisant une préparation déjà valide et les étapes LLM déjà acceptées.
- Une relance manuelle du prompt ou de la vidéo est désormais réconciliée avec la carte récapitulative : l’ancienne erreur disparaît, l’état réel (`prompting`, `prompt_ready`, `rendering`, `succeeded`) est repris, et une relance concurrente est refusée.
- Le refroidissement distant est enregistré avant de libérer la voie physique. Une vidéo déjà en attente dans la FIFO ne peut donc plus acquérir le GPU dans la courte fenêtre où la fin du rendu précédent n’était pas encore visible.
- Le repos reste volontairement appliqué avant la vidéo suivante. Après la dernière vidéo, l’état redevient `Ready`; si une nouvelle vidéo arrive pendant les 30 secondes restantes, elle attend le reliquat.
- Cache frontend Episodes passé à `20260918.3`.
- Validation : compilation Python, `git diff --check` et 86 tests ciblés verts (`machine_work`, `episodes`, navigateur/web Episodes et H3 render).

### Broken / missing
- Le serveur actuellement lancé doit être redémarré pour réconcilier les anciennes cartes persistées avec les relances manuelles déjà effectuées.
- La variante chinoise H3 est seulement à l’étude : aucune traduction ou modification du compilateur de prompt n’a été ajoutée dans ce correctif.

### Next steps (max 3)
1. Laisser terminer les travaux actifs, redémarrer PanelForge puis faire `Ctrl+F5`.
2. Vérifier que la scène 2 relancée manuellement passe de l’ancienne carte rouge à son état réel, puis tester `Relancer les scènes incomplètes` sur un nouvel échec contrôlé.
3. Valider l’architecture d’une variante chinoise post-compilation, conservant le prompt anglais et le plan comme sources immuables pour un A/B à seed identique.

## Alignement 2026-09-18 — variante chinoise H3 à expérimenter

### Findings
- Les guides MiniMax officiels distinguent le format Base/FL2VA à trois sections et le format Ref2VA à six sections. Ils demandent actuellement que les descriptions structurées soient écrites en anglais, en conservant seulement dialogues, paroles et texte visible dans leur langue d’origine.
- Aucun guide officiel chinois équivalent au guide de prompting H3 n’a été publié. Les retours chinois consultés reprennent majoritairement la structure et les formulations anglaises officielles ; ils ne démontrent pas encore qu’un prompt descriptif chinois surpasse l’anglais.
- Une variante chinoise doit donc rester expérimentale et optionnelle, sans remplacer le prompt anglais canonique.
- Pipeline proposé : plan de la scène + prompt anglais accepté → un appel LLM supplémentaire de transcompilation → validation structurelle → stockage côte à côte → choix Anglais/中文 au rendu. Les dialogues, labels, balises, timecodes, noms de sections et relations de références restent verrouillés.
- Gemma connaît le chinois. Le modèle du prompt final est le meilleur défaut pressenti pour la transcompilation, afin d’éviter un rechargement de modèle et de conserver le même comportement sur les contenus permissifs. Qwen reste une alternative A/B configurable, pas une dépendance de l’architecture.

### Open points
- Ne pas implémenter avant validation du périmètre UI : génération à la demande par scène, sélection de variante au rendu et comparaison à seed/références/réglages identiques.
- Décider si le transcompilateur reçoit le plan de scène complet ou un extrait déterministe compact ; le prompt anglais demeure dans tous les cas la source de forme et le plan une source de contrôle seulement.

## Patch 2026-09-18 — variante chinoise H3 et paroles déterministes

### Works
- H3 Base et REF2V Direct affichent un bloc optionnel `Variante chinoise · expérimental` après le prompt final. La transcompilation est un troisième appel explicite et configurable ; elle reçoit le Plan accepté et le prompt anglais final, sans image.
- Le prompt anglais reste canonique et inchangé. La variante chinoise est persistée à côté de sa révision source, puis choisie explicitement pour le rendu. Anglais et chinois ouvrent deux projets H3 distincts, ce qui permet un A/B sans collision d’historique.
- Le validateur chinois exige de la prose chinoise et conserve exactement sections, plans, timecodes, références, identifiants vocaux, marqueurs techniques et dialogues. Une sortie qui modifie la structure ou les paroles est rejetée sans remplacer l’anglais.
- Le modèle de transcompilation est sélectionnable dans le catalogue LLM normal. Son défaut a depuis été remplacé par Gemma Uncensored local ; une nouvelle révision anglaise remet volontairement la sélection du prompt sur English.
- Les paroles imposées sont remplacées par des jetons opaques avant chaque appel Plan/Writer, révision et arbitrage, puis réinsérées localement avant compilation et validation. Le chemin Super Fast historique applique aussi la restauration. Le rejet observé sur la réplique coréenne est couvert par un test de non-exposition au modèle et de restitution exacte.
- Persistance `prompt_compositions` passée au schéma 7 avec lecture intacte des schémas 1 à 6. La traçabilité des appels de préparation d’un rendu chinois remonte à la révision anglaise source.
- Validation : compilation Python, `git diff --check`, 164 tests ciblés verts, dont transport HTTP et Chromium. Suite complète : 1 394 tests exécutés, 43 échecs et 32 erreurs historiques hors surface (contre 47/33 consignés précédemment) ; aucune régression dans les tests ciblés de ce patch.

### Broken / missing
- La variante chinoise n’est volontairement pas exposée dans Histoires à ce stade.
- Aucun rendu ComfyUI réel n’a encore comparé anglais et chinois à seed, références et réglages identiques.
- Les deltas d’une transcompilation en cours peuvent afficher brièvement les jetons opaques ; le texte final validé et persisté contient toujours les paroles restaurées.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` afin de charger `chinese-prompt-variant.js?v=20260918.1`, les scripts directs `20260918.2`, H3 Render `20260918.3` et le CSS `20260918.4`.
2. Sur une même scène, générer la variante chinoise puis rendre English et 中文 avec la même seed et les mêmes réglages.
3. Vérifier sur un prompt comportant une réplique non anglaise que Plan, prompt final anglais et variante chinoise conservent exactement les caractères originaux.

## Correctif 2026-09-18 — file directe H3/REF2V

### Works
- `queue_attempt` ne rejette plus un rendu uniquement parce qu'un autre H3/REF2V appartenant au processus courant est actif. Il persiste le statut `queued` et réserve immédiatement un ticket FIFO dans `MachineWorkCoordinator`, avant le lancement de la tâche d'arrière-plan.
- Deux ateliers ou onglets peuvent donc lancer leurs rendus successivement : PanelForge conserve l'ordre des clics, même si le thread du second rendu démarre avant celui du premier. ComfyUI ne reçoit toujours qu'un seul rendu vidéo à la fois.
- Les exécutions distantes détachées après redémarrage restent bloquantes tant que leur état ComfyUI n'est pas réconcilié. Un double appel `/start` reste idempotent et une annulation en file retire le ticket non réclamé.
- Histoires transmet le même libellé de scène à la réservation et à l'exécution. L'atelier direct affiche désormais `En attente dans la file…` au lieu de laisser croire que le rendu est déjà en cours.
- Cache H3 Render passé à `20260918.4`.
- Validation : compilation Python, `git diff --check` et 94 tests ciblés verts (`h3_render_global_queue`, `machine_work`, récupération H3, H3, Episodes et contrôle navigateur H3).

### Broken / missing
- Aucun rendu ComfyUI réel n'a été lancé pendant le correctif ; la validation utilise le faux moteur immédiat et vérifie l'ordre exact des soumissions.
- La suite web générale conserve deux attentes de versions d'assets déjà obsolètes avant ce patch (`lab.css` et ancienne version H3) ; elles ne concernent pas la file de rendu.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger H3 Render `20260918.4`.
2. Lancer un FL2V, puis un second depuis un autre onglet : le second doit afficher `En attente dans la file…` et apparaître dans la ligne Serveur du suivi global.
3. Vérifier que le second n'est envoyé à ComfyUI qu'après la fin et le refroidissement éventuel du premier.

## Correctif 2026-09-18 — progression Spectrum et audit réel de la file

### Works
- Le dernier rendu observé utilisait REF2V `0.2.5`, Spectrum actif, 25 steps configurés et un compteur ComfyUI effectif réduit par Spectrum. Le normaliseur rejetait `2/4` parce qu'il exigeait `x/25`, ce qui laissait l'ordonnanceur à `Envoi à ComfyUI · 8 %`.
- Pour un essai Spectrum, le nœud de diffusion suivi accepte désormais son compteur effectif tout en conservant les contrôles stricts des autres phases et des rendus non accélérés.
- La preview H3/REF2V met elle aussi à jour `MachineWorkCoordinator`. Plusieurs onglets peuvent se disputer le canal WebSocket ComfyUI sans que la connexion gagnante prive le suivi global de progression.
- L'audit du workspace confirme que la file du correctif précédent a fonctionné : un second essai a été réservé à 17:11 pendant le premier rendu, puis annulé à 17:12 avant soumission. L'épisode inspecté avait `video_chain: null` : les essais provenaient des boutons manuels des scènes, pas de `Lancer prompts + vidéos`.
- Validation : compilation Python, `git diff --check` et 97 tests ciblés verts, y compris `2/4` Spectrum et la remontée d'une preview vers la file globale. Le module Video Lab complet conserve son erreur historique `input_mode` sur un endpoint retiré de la navigation.

### Broken / missing
- Le processus PanelForge lancé à 17:01 utilise encore le code importé avant ce dernier correctif de progression. La voie distante était redevenue `idle` lors de la vérification finale : le serveur peut maintenant être redémarré sans interrompre ce rendu.
- Aucun changement de stratégie n'a été appliqué à la chaîne Histoires : le bouton global reste le mécanisme qui crée `video_chain`; les lancements manuels par scène utilisent bien la FIFO globale mais ne créent pas de chaîne d'épisode.

### Next steps (max 3)
1. Redémarrer PanelForge. Aucun `Ctrl+F5` n'est nécessaire pour ce correctif backend, même s'il reste utile pour le statut `En attente dans la file…` ajouté précédemment.
2. Relancer un rendu Spectrum et vérifier que `Diffusion principale · étape 1/4`, puis `2/4`, remplace le 8 % figé.
3. Pour tester l'automatisation Histoires, utiliser `Lancer prompts + vidéos`; pour tester uniquement la FIFO manuelle, lancer deux scènes séparément sans annuler la seconde.

## Correctif 2026-09-18 — LLM local pour la variante chinoise

### Works
- H3 Base et REF2V Direct affichent désormais la bascule standard `Local · Unsloth` dans leur bloc de variante chinoise. Elle est cochée par défaut, ce qui évite que le picker commun filtre un catalogue local comme s'il s'agissait du catalogue serveur et laisse la liste vide.
- Le transcompilateur présélectionne exactement `local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP` lorsqu'il est disponible. Le repli reste volontairement local : autre Gemma uncensored, Gemma, Writer local ou premier modèle Unsloth ; il ne décoche jamais implicitement la source locale pour choisir un modèle serveur.
- La bascule reste libre : la décocher affiche les modèles serveur et une sélection explicite de l'utilisateur n'est pas écrasée pendant le run.
- Cache passé à `chinese-prompt-variant.js?v=20260918.2` et `lab.css?v=20260918.5`.
- Validation : `git diff --check` et 26 tests UI/web verts, dont le parcours Chromium de génération chinoise avec le modèle local attendu.

### Broken / missing
- Aucun appel LLM réel n'a été lancé pendant ce correctif ; la disponibilité effective du modèle dépend toujours du catalogue Unsloth au démarrage.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger le nouveau HTML et les assets `20260918.2` / `20260918.5`.
2. Ouvrir un prompt final dans H3 Base ou REF2V et vérifier que `Local · Unsloth` ainsi que Gemma Uncensored sont déjà sélectionnés.
3. Générer une variante chinoise et confirmer dans le suivi Local que l'appel utilise bien le modèle HauhauCS choisi.

## Diagnostic 2026-09-18 — REF2V chinois lance l'ancien projet anglais

### Current state
- La composition `prompt-0ee9a92e3ab64e77b813606598ae950f` contient bien une variante chinoise persistée de 3 728 caractères (`prompt-zh-ce629284263f4820a30cfacfbc101494`).
- Le backend a correctement créé un projet REF2V chinois isolé, `h3-render-6ec70f08ff324aa5b364e86ea6ab186c`, avec la source synthétique `zh:final_prompt-850fc744a2a447d0a67666f89d99aa56:prompt-zh-ce629284263f4820a30cfacfbc101494`. Ce projet n'a aucun essai.
- Un essai anglais a aussi été ajouté au projet `h3-render-e03c9b663fce4edea0a204019523d178`, puis annulé. L'utilisateur indique avoir probablement lancé volontairement chinois puis anglais pour comparer : aucun bug de rattachement UI n'est donc retenu sans nouvelle reproduction.
- Le projet chinois rencontre en plus un second blocage, indépendant : `prepare_attempt()` repasse sa prose dans le validateur cinématique anglais. Les marqueurs `[Shot N]` et les timecodes du prompt inspecté sont corrects, mais les directives telles que `The camera pushes in...` ont été traduites ; `extract_compiled_camera_clauses()` trouve donc zéro phase dans chacun des trois plans et émet `Chaque plan contient une ou deux phases caméra continues.` avant tout envoi à ComfyUI.
- Conserver les clauses caméra en anglais contournerait le rejet mais dégraderait l'expérience A/B recherchée. Le correctif approprié est une validation de rendu consciente de la variante : comparer la structure chinoise à la révision anglaise canonique (sections, plans, coupures, références, dialogues et durée), sans tenter de reparcourir la prose chinoise avec le lexique caméra anglais.

### Next steps (max 3)
1. Ne traiter le rattachement UI que si un nouveau lancement reproduit un projet de langue différente de la sélection visible.
2. Rendre la validation de `prepare_attempt()` consciente du préfixe `zh:`.
3. Couvrir le lancement chinois par un test service.

## Correctif 2026-09-18 — rendu chinois expérimental sans validation anglophone

### Works
- `H3RenderService.prepare_attempt()` détecte les projets dont `source_prompt_revision_id` commence par `zh:` et ne leur applique plus `canonicalize_h3_revision()` ni les linters cinématiques anglophones.
- Le prompt chinois est transmis tel quel au workflow après le seul garde technique générique de taille/type. Les projets anglais, H3 Base comme REF2V, conservent toutes leurs validations actuelles.
- Le test de variante traduit volontairement les clauses `The camera...` en chinois, ouvre son projet isolé puis prépare un essai avec ce texte exact. Validation : 43 tests `h3_chinese_variant` + `h3_render` verts, compilation Python et `git diff --check` sans erreur.

### Next steps (max 3)
1. Redémarrer PanelForge pour charger le correctif backend ; aucun `Ctrl+F5` n'est requis.
2. Relancer le projet chinois existant et vérifier qu'un essai est créé puis envoyé à ComfyUI.
3. Ne concevoir un validateur chinois qu'après les premiers A/B montrant un gain réel.

## Patch 2026-09-19 — axes créatifs, rendu armé et registre vocal Histoires

### Works
- Les sélections de recette, checkpoint, LoRA, ratio, MP, musique et durée restent celles propres à chaque atelier avant ce patch. Aucun réglage vidéo global n'est imposé ; Histoires continue notamment à injecter automatiquement la durée de la scène dans son rendu.
- Les nouvelles préparations utilisent audace/vie/caméra/mouvements `3` et dialogues/réactions `1`. Les modes rapides directs restent présélectionnés.
- Dans Histoires, le panneau de réglages affiche `Générer dès que le prompt est prêt` même sans prompt. Le clic persiste le snapshot visible et crée une chaîne durable d'une seule scène. Elle peut s'attacher au prompt manuel déjà actif, ou lancer prompt puis vidéo ; un échec du prompt marque la carte et annule toute soumission vidéo.
- L'audit du run `La métamorphose de Nour` a isolé le faux rejet de paroles : la pancarte « vilain petit caneton » était prise pour une réplique et placée avant les vrais dialogues. Lorsqu'une intention contient le bloc PanelForge `Répliques exactes...`, le registre vocal est maintenant limité à ce bloc ; l'extraction générique reste inchangée pour les ateliers directs.
- Validation ciblée : contrats dialogue, Episodes/service/UI, H3 Render/BUNNY/LoRA, ateliers directs et web. Les parcours Chromium couvrent le défaut BUNNY et le rendu armé. `git diff --check` est propre. Node.js n'est pas installé ; les parcours Chromium assurent la validation JavaScript exécutée.

### Broken / missing
- La suite complète du worktree très modifié exécute 1 411 tests mais conserve 37 échecs et 31 erreurs hors surface de ce patch, notamment des contrats Combat/H3 Render et des attentes de versions déjà désynchronisées. Les suites ciblées de cette surface sont vertes.
- Aucun rendu ComfyUI ou appel LLM réel n'a été lancé pendant ce patch.

### Next steps (max 3)
1. Redémarrer PanelForge puis faire `Ctrl+F5` pour charger les nouveaux caches H3/REF2V/Episodes.
2. Reprendre la scène en échec de `La métamorphose de Nour` et confirmer que seules les deux vraies répliques entrent dans le Plan.
3. Depuis une scène sans prompt, régler BUNNY puis cliquer `Générer dès que le prompt est prêt` et observer la transition prompt → file serveur.
