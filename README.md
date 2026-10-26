# PanelForge

Version majeure actuelle : **[PanelForge 2.0.0](docs/releases/2.0.0.md)** — 7 octobre 2026.

Le bouton **Instance** dans la barre supérieure indique la version, le commit et
la branche Git, les modifications applicatives locales, les dossiers du code et du
workspace, le PID et l’heure de construction de l’application. Ces informations
sont capturées une fois par `scripts/run_lab.py` et exposées par `/api/instance`
sans cache. L’empreinte SHA-256 porte sur les sources Python/JS/CSS/HTML et
`pyproject.toml` au démarrage, hors données runtime, médias et configuration privée.
Elle n’inclut pas les workflows et ne suit pas les modifications faites après le
démarrage. Git peut être absent : les champs concernés sont alors indisponibles.

Les médias sont lus et vérifiés une seule fois par requête de contenu, y compris
pour une réponse HTTP Range. L’intégrité porte toujours sur le fichier entier ;
ce changement ne constitue pas une lecture partielle sur disque.

Les créations de projets **Recettes** et **Histoire V2** enregistrent une intention
dans `pending-index.json` avant d’écrire le projet puis son index. Après une
interruption du processus, la prochaine liste ou sauvegarde termine l’indexation
du projet déjà écrit, en conservant ses résultats et identifiants de générations.
Un journal invalide reste en place et provoque une erreur explicite. Ce mécanisme
protège les nouvelles écritures ; il ne recherche pas d’anciens fichiers orphelins
et ne coordonne pas plusieurs processus écrivant dans le même workspace.

Le serveur HTTP est organisé par atelier dans `src/panelforge/features/lab/`.
`web.py` assemble les routes, le middleware et le cycle de vie des services.
Les modules `*_web.py` regroupent les routes, modèles de requêtes et réponses de
leur atelier ; les autres ateliers déjà séparés conservent leur organisation.
`media_http.py` porte la lecture des assets et la détection des médias reçus,
`http_support.py` les conversions d’entrée et erreurs communes,
`http_streaming.py` le transport SSE, et `render_events.py` les relais ComfyUI.
Les dépendances de chaque routeur sont injectées explicitement par `create_app`.

Huit réponses principales sont décrites par des `TypedDict` à côté de leurs
sérialisateurs. Ces annotations ne filtrent pas les champs et ne convertissent pas
les valeurs envoyées au navigateur. Les erreurs spécifiques, les champs optionnels
des flux et les formats des historiques sont conservés. Les contrats HTTP d’avant
refactoring sont enregistrés dans `tests/fixtures/lab-http-before-patch2.json`.
Les tests ciblés sont `test_http_contracts.py` et `test_http_transports.py`, à lancer
par l’utilisateur avec `python -m unittest discover -s tests -p "test_http_*.py"`.
Les originaux restent dans `historique/2026-10-22-patch2-http/`.

L’**Usine** charge désormais 50 lignes par page et les réglages complets seulement
à l’ouverture d’une fiche. Les sélections restent conservées entre pages ; la case
globale sélectionne les lignes de la page affichée. Le suivi se rafraîchit toutes
les 5 secondes dans l’Usine, avec des réponses réduites lorsque rien n’a changé.
Dans un autre atelier, seuls les compteurs sont lus toutes les 15 secondes ; aucun
rafraîchissement Usine n’est envoyé depuis un onglet navigateur masqué. Le retour
dans la vue déclenche une actualisation en conservant le brouillon de réglages.
Les routes `/api/video-factory/summary`, `/browse` et `/items/{id}` servent ces
lectures. Un petit inventaire global d’identifiants, révisions et statuts conserve
les actions entre pages et l’ordre de la file. L’API de snapshot complète reste
compatible ; les actions de l’interface demandent `compact=true` pour éviter de
renvoyer tout l’historique après chaque modification.

Au prochain démarrage du Lab, `workspace/system/startup-timings.jsonl` enregistrera
les durées réelles et CPU des phases de construction et des reprises des services,
sans modifier leur ordre. Une ligne est écrite en fin de démarrage ou sur exception,
avec au plus 64 phases ; rotation à 256 Kio vers un unique fichier `.1`. Les imports
Python précédant `build_app` et le chargement du navigateur sont hors mesure ; un
arrêt brutal avant la fin ne produit pas de ligne. Aucun prompt n’est enregistré.
Le statut `ready` signifie que les méthodes de démarrage sont revenues, pas que
tous les travaux de fond sont terminés. Le patch nécessite un redémarrage du Lab,
puis un rechargement des pages, à effectuer lorsque les productions le permettent.
Les tests ciblés, à lancer par l’utilisateur, sont :

```powershell
python -m unittest tests.test_factory_views tests.test_factory_views_browser tests.test_video_factory_web tests.test_startup_timings
```

L’**historique KREA2** se charge indépendamment des ressources indispensables au
formulaire. Sa lenteur ou son indisponibilité n’interrompt plus la chaîne de
création du projet, préparation du prompt et mise en file de l’image. Le bouton
reste occupé jusqu’à l’accusé de mise en file ; les erreurs d’historique restent
dans son panneau, avec nouvelle tentative via Actualiser ou au retour dans la vue.
Les lectures d’historique sont regroupées par onglet, annulées lorsqu’il est masqué
et leurs réponses périmées sont ignorées. Cette suspension ne touche pas une
commande de création/préparation/rendu engagée dans l’onglet.

`/api/image-lab/krea2-assisted/project-summaries?limit=30` fournit les noms,
compteurs, statuts et aperçus sans conversations ni essais complets (limite 100).
Les résumés en mémoire suivent les écritures durables et sont construits pendant
la reprise existante de la file, sans second parcours de la bibliothèque. Après
initialisation, les rafraîchissements ne relisent pas les fichiers de projets et
ne consultent pas ComfyUI. Une utilisation isolée du store charge seulement les
résumés manquants demandés. Les anciens endpoints complets restent compatibles ;
les imports externes demandent toujours une reconstruction explicite de l’index.

Les aperçus utilisent `/api/assets/{id}/thumbnail?v=1` : PNG de 320 pixels maximum,
sans métadonnées du prompt, générés à la demande avec Pillow. Le cache partagé du
serveur est limité à 16 Mio et 256 images ; au plus deux conversions s’exécutent
simultanément. Les demandes en attente ne réservent pas les threads HTTP. La
première lecture vérifie l’asset source ; les suivantes réutilisent la miniature.
Les assets étant immuables, un nouvel ID ou une nouvelle version de conversion
invalide l’aperçu ; les originaux restent inchangés. Ce cache mémoire repart vide
au redémarrage, sans précalcul ; le navigateur peut conserver les miniatures.
Le lot 2 nécessite un redémarrage du Lab puis un rechargement des pages. Il ne
rend pas durable la commande navigateur après fermeture de l’onglet.

Tests du lot 2, à exécuter par l’utilisateur :

```powershell
python -m unittest tests.test_krea2_history tests.test_krea2_history_browser tests.test_image_thumbnails tests.test_krea2_assisted_index tests.test_krea2_assisted_poll_browser tests.test_http_contracts
```

PanelForge est un atelier local pour construire un canon visuel cohérent, qualifier des recettes ComfyUI puis produire des panels narratifs à partir d’assets approuvés.

Le projet reste un monolithe modulaire : ComfyUI sert à découvrir manuellement les workflows, tandis que PanelForge les exécute comme des recettes explicites, versionnées et traçables.

## Tranches utilisables

Les ateliers retirés des menus sont conservés dans [historique](historique/README.md), avec leurs sources d’origine et leur inventaire. Ce dossier ne participe ni au démarrage ni au packaging de l’application.

### Image Lab

Le Lab propose actuellement `character.change_view` :

- import d’une image ou réutilisation d’un candidat précédent ;
- huit azimuts, quatre élévations et trois cadrages ;
- prompt Qwen Multiple Angles déterministe et verrouillé ;
- slider de force pour la LoRA d’angle ;
- seed avancée conservée sans perte de précision ;
- génération via ComfyUI, comparaison et historique local ;
- décisions humaines `kept` ou `rejected` sans remplacement automatique du canon ;
- provenance persistée : recette, workflow compilé, prompt exact, contrôles, hashes et filiation.

La recette active est `qwen-edit-2511-multiple-angles@0.2.0`. Seule la force LoRA `1.0` est actuellement qualifiée ; toute autre valeur permise par le slider est enregistrée comme `experimental_override`.

```text
image source
  → recette versionnée
  → workflow compilé
  → run ComfyUI
  → candidat persistant
  → comparaison et décision humaine
  → asset réutilisable
```

### Video Lab — textes Instagram assistés

Le sous-mode `Texte Instagram` transforme une vidéo MP4 ou WebM en projet éditorial conversationnel :

- quatre images clés sont extraites dans le navigateur à 10, 35, 65 et 90 % ; la vidéo complète n'est pas envoyée au LLM ;
- anglais par défaut ou français, avec trois variantes par défaut contenant angle, hook, légende, hashtags et emojis ;
- `mood`, `vibe`, exemple représentatif et consignes restent libres et peuvent être enregistrés dans un profil de chaîne réutilisable ;
- chaque projet conserve la vidéo, les images clés, toutes les propositions et la conversation complète afin de reprendre les ajustements après un redémarrage ;
- lorsque la vidéo correspond exactement à une sortie H3 ou Video Lab connue, son prompt est ajouté au contexte ; sinon l'analyse reste strictement visuelle et ne prétend pas entendre l'audio ;
- chaque variante dispose d'une action `Tout copier` prête à publier.

### Image Lab — création assistée KREA2

Le mode « Création assistée » organise la conception d’une image comme un projet
conversationnel distinct de KREA2 Edit :

- une intention et, facultativement, une image de référence descriptive sont
  transmises au LLM ; la référence n’entre jamais dans le workflow ComfyUI T2I ;
- chaque réponse conserve des questions d’affinage et un prompt anglais complet,
  immédiatement éditable et exécutable ;
- un résultat réussi peut devenir le feedback visuel du tour suivant, avec son
  prompt exact, son checkpoint, son ratio, ses mégapixels, sa seed et ses LoRA ;
- checkpoint, ratio, mégapixels, seed et quatre LoRA ordonnables restent
  modifiables à chaque essai, tandis que le sampling communautaire reste fixe ;
- les images sont regroupées en bas du projet et une image choisie peut être
  exportée explicitement avec son sidecar sous
  `D:\AI\PanelForge\KREA2 Creations` par défaut ;
- une discussion dédiée peut produire un brouillon de recette (identité,
  invariants, variables, risques et prompt canonique). Seul le bouton de
  publication crée la version immuable `0.1.0`, réutilisable dans
  le catalogue de recettes partagé.

La mémoire du projet contient les échanges, décisions, prompts et essais. La
mémoire globale proposée au LLM reste limitée aux recettes déjà publiées et aux
ressources réellement exposées ; un essai ou une discussion ne l’altère jamais.
La racine d’export peut être remplacée par
`PANELFORGE_KREA2_CREATIONS_ROOT` ou `--krea2-creations-root`.

### Image Lab — création batch

L’onglet **Création batch**, à côté de Création assistée, présente directement
le formulaire de lancement, sans historique ni panneau repliable. Charger un CSV
UTF-8 (BOM accepté), avec une colonne `intention` et une colonne `nom` facultative.
Virgules ou points-virgules sont acceptés ; entourer de guillemets les intentions
contenant des séparateurs ou des retours à la ligne. Les entrées vides sont ignorées,
les doublons conservés. Limites : 500 intentions, 8 Mio et 12 000 caractères par
intention. Un fichier d’exemple est fourni dans `docs/examples/creation-batch.csv`.

V6 est sélectionnée initialement, les inspirations locales sont désactivées et
Gemma 4 local est proposé avec **Local · Unsloth** coché. Le preset est obligatoire.
Langue et direction artistique restent sélectionnables (direction avec V6).
Une image est produite pour chaque intention. Le checkpoint, les LoRA, le format
et la résolution viennent du preset ; le workflow et le sampling proviennent
de son essai source lorsqu’il existe, sinon des défauts Assisted historiques.
Les réglages et la direction sont copiés au lancement et ne suivent pas les
modifications ultérieures du catalogue.

Le suivi à droite sépare prompt LLM et rendu KREA2, avec aperçus de 840 px maximum
au survol et ouverture de l’original dans une fenêtre centrée au clic. Les deux
étapes réussies indiquent **Terminé**. Les barres utilisent la progression disponible,
dont les étapes des deux passes KREA2 ; une progression non mesurable reste animée
sans pourcentage. La position affichée est celle de la file machine partagée,
y compris lorsque DLSS occupe le PC local. Refresh conserve le CSV et les choix en cours. Le suivi
cesse d’interroger le serveur lorsque l’atelier ou l’onglet est masqué.

Les lots sont persistés dans `workspace/creation_batches`. Les prompts sont préparés
dans l’ordre et chaque image rejoint la file KREA2 dès que son prompt est prêt.
Le prompt suivant n’attend pas l’image précédente ; le suivi et la préparation des
rendus fonctionnent indépendamment du LLM, en respectant les réservations de ressources existantes. Fermer
l’onglet n’arrête pas la production. Un identifiant de lancement évite les doubles
soumissions ; une erreur reste limitée à sa ligne. Après redémarrage, les prompts
et essais déjà sauvegardés sont réutilisés. Un appel LLM interrompu sans résultat
durable est marqué en erreur, sans appel automatique supplémentaire. Les envois
ComfyUI ambigus gardent les protections de la file Assisted. Une seule instance
d’écriture par workspace reste requise.

Chaque image terminée propose **8 + 4** pour un nouveau tirage du même prompt avec
le profil **Finition 4 steps · 8 + 4** : l’aperçu s’ajoute sur la même ligne.
**DA** applique une direction artistique au prompt canonique et crée une sous-ligne
**1.1**, **1.2**, etc. **Preset** crée également une sous-ligne, avec un nouveau
prompt préparé à partir de l’intention et du preset choisi. Les originaux et les
réglages de chaque variante sont conservés ; les commandes répétées après perte
de réponse réutilisent leur identifiant. Les fichiers de batch de première version
restent lisibles. Limites : 50 variantes de rendu supplémentaires par ligne et
2 000 lignes en incluant les variantes créatives.

Le **+ blanc sur bouton violet**, à côté de chaque aperçu, envoie cette image en
préparation dans l’Usine. Il devient une **coche verte** après confirmation, avec
l’infobulle « Envoyé à l’usine ». Le reçu est conservé côté serveur et l’envoi ne
lance pas automatiquement la production vidéo.

Tests à lancer par l’utilisateur :
`python -m unittest tests.test_creation_batch tests.test_creation_batch_variants tests.test_creation_batch_web tests.test_creation_batch_browser`.
Ils utilisent des doublures et des fichiers temporaires, sans appel réel LLM/GPU.

### Image Lab — modification KREA2

Le mode de modification de l’Image Lab exécute la recette immuable
`image.edit/krea2.identity_edit@0.1.0`. Il réunit dans un seul écran le backlog,
la reconstruction du prompt et les essais de rendu :

- les anciennes sorties réussies du Batch Lab restent récupérables dans le backlog ;
  une image PNG, JPEG ou WebP externe peut aussi être ajoutée manuellement ;
- un sidecar Batch ou les métadonnées PNG ComfyUI restaurent au mieux prompt,
  checkpoint, ratio, mégapixels, seed et jusqu’à quatre LoRA générales ; les
  informations absentes ou les ressources renommées produisent seulement un
  avertissement et des valeurs par défaut éditables ;
- chaque appel multimodal traite le prompt actuellement édité comme état
  autoritaire et la nouvelle instruction comme le tour suivant de l’échange.
  Sans prompt récupéré, le premier appel reconstruit la scène depuis l’image.
  Un résultat réussi peut être choisi comme feedback visuel : le LLM le compare
  à la cible, tandis que ComfyUI continue de repartir de la source immuable de
  l’étape. La trace séparée reste affichable en option et n’est pas persistée ;
- le prompt final reste éditable, puis les rendus peuvent être répétés sans
  nouvel appel LLM en changeant checkpoint, LoRA, ratio, mégapixels, seed,
  `ref_boost` ou nombre de steps ;
- le workflow conserve la LoRA technique `krea2_identity_edit_v1_2` à force
  `1`, ainsi que CFG, sampler, scheduler, CLIP, VAE et grounding qualifiés ;
- « Valider et continuer » promeut explicitement un essai réussi en source de
  l’étape suivante. Le backlog reste groupé par projet, avec chronologie des
  étapes, révisions de prompt, essais et résultat validé ;
- à chaque validation, l’image originale puis la chaîne des seuls résultats
  acceptés sont recopiées dans un projet lisible hors du workspace technique.
  L’utilisateur nomme le projet et chaque résultat validé ; chaque image reçoit
  un sidecar `.txt` avec prompt et réglages, plus un manifeste `project.json`.
  Les noms visibles sont bornés et ne répètent pas le nom du projet dans chaque
  fichier, afin de rester compatibles avec les limites de chemins Windows ;
- « Traité » retire tout le projet du backlog courant et « Masquer » l’archive
  sans supprimer l’image originale, les étapes ni les essais déjà produits.

La reconstruction accepte une description NSFW lorsque les personnes sont
clairement adultes. Elle ne déduit jamais un âge adulte ambigu et n’ajoute pas
d’acte ou de participant non demandé.

La racine d’export est `D:\AI\PanelForge\KREA2 Projects` par défaut. Elle peut
être remplacée avec `PANELFORGE_KREA2_PROJECTS_ROOT` ou
`--krea2-projects-root`. Une panne de ce stockage produit un avertissement
réessayable dans l’interface sans annuler la validation ni déplacer les fichiers
techniques conservés par ComfyUI et PanelForge.


### H3 Base / FL2VA — texte et frames frontières facultatives

Les parcours H3 Base et Ref2V proposent aussi un `Mode rapide` avant leur création. Cette option orchestre les mêmes opérations que l’interface manuelle — génération puis approbation du Brief, du Plan et du Prompt final — sans créer de recette ni d’appel LLM supplémentaire. Les recommandations et warnings restent visibles mais ne déclenchent aucun arbitrage et ne bloquent pas la chaîne. Une erreur de contrat, une réponse tronquée ou un échec réseau arrête immédiatement le parcours ; les étapes déjà approuvées sont conservées et un bouton permet de reprendre depuis la première étape incomplète. Un rechargement ne relance jamais silencieusement une génération.

Ref2V propose trois familles de recettes dans le même sélecteur : mono-plan standard, multi-plan structuré et multi-plan direct expérimental. Cette dernière correspond à `minimax.h3.ref2v.direct.multishot.superfast@0.2.0` et impose son exécution en un seul appel : elle crée une capsule de Brief sans LLM puis confie directement aux images, à l’intention et à la politique de liberté l’unique rédaction du corps H3. PanelForge ajoute seulement l’en-tête canonique des références, normalise les balises et auto-approuve le Prompt ; aucun Plan JSON ni writer intermédiaire n’est créé. `Supervisé` et `Rapide` restent des choix d’orchestration séparés pour les recettes standard. Les écarts de caméra, de nombre de plans ou de timestamp restent des avertissements, tandis qu’un document vide, sans Shot 1, sans champs audio, avec labels invalides ou placeholders est bloqué. La `0.1.0` Plan-first reste chargeable pour les parcours historiques sans être proposée aux nouveaux runs.

Une option de debug peut afficher en direct la trace séparée transmise par le modèle. Elle n’active aucun raisonnement, ne parse pas de balises `<think>` et ne persiste rien : si le serveur ou le modèle ne fournit pas de canal `reasoning`, l’interface l’indique simplement.

Dans ces deux parcours Direct, la liberté créative est présentée sous cinq modes explicites — Factuel strict, Conservateur, Équilibré, Cinématographique et Exploratoire — alignés sur les politiques déjà appliquées par le backend. Ce choix agit directement sur les propositions du Brief ; le Plan et le prompt final n’en héritent qu’indirectement par le Brief approuvé. Les anciennes valeurs numériques restent relisibles sans arrondi ni invalidation artificielle.

L’onglet principal `H3 Base` utilise le checkpoint MiniMax H3-Base-FL2VA. La présence des deux emplacements facultatifs détermine automatiquement le mode de prompt, sans demander un choix technique supplémentaire :

```text
intention + [première frame] + [dernière frame]
  → T2VA / I2VA / L2VA / FL2VA déduit par les entrées
  → Brief compact éditable et approuvé
  → Plan JSON physique éditable, arbitrable et approuvé
  → prompt MiniMax H3 Base compilé et approuvé
```

Le profil `minimax.h3.fl2va.direct@0.1.0` relit directement zéro, une ou deux images pendant le Brief et ses révisions. La recette `minimax.h3.fl2va.direct@0.1.0` réutilise le Plan V2 mono-plan — beats, contacts, risques, caméra typée et `final_hold_ms` — mais compacte le Brief et le schéma transmis au planner. Le writer reçoit uniquement le mode, la propriété des frames et la projection compacte du Plan ; le Brief complet n’est pas répété.

La recette mono-plan sélectionnée par défaut est désormais `minimax.h3.fl2va.direct@0.3.2`. Elle conserve les contrats de mouvement et la caméra compilée de `0.3.1`, mais traite une last frame comme un échantillon instantané plutôt qu’une destination : un mouvement déclaré continu ne peut plus rejoindre, verrouiller ou stabiliser la composition finale en avance. Pour un tracking avec impression de sur-place, le sujet peut garder une position écran voisine tandis que le Plan doit conserver une preuve de vitesse par parallaxe, défilement, écoulement, projections ou mouvement corporel. Les fins `natural_settle` et `intentional_hold` explicitement demandées restent autorisées.

PanelForge compile ensuite l’enveloppe officielle : aucun header image en T2VA, ancrage de départ en I2VA, ancrage terminal en L2VA, ou double alignement en FL2VA. Il insère aussi les phrases caméra canoniques aux jalons approuvés. Le modèle ne peut donc ni confondre la frame finale avec l’ouverture, ni modifier l’enveloppe, ni réinventer la caméra lors d’une révision.

Les anciennes recettes `minimax.h3.i2v.direct@0.1.0` et `0.2.0` restent immuables et relisibles. L’action « Repartir de ce run » migre leur première frame vers une nouvelle session H3 Base propre, sans copier le Brief, le Plan ni le Prompt historiques.

### Ref2V — brief multimodal sans observation intermédiaire

L’onglet principal `Ref2V` utilise le parcours Direct générique :

```text
1 à 3 images natives + intention simple
  → Brief multimodal éditable et approuvé
  → Plan JSON physique éditable et approuvé
  → prompt MiniMax H3 compilé et approuvé
```

Le profil `minimax.h3.ref2v.direct@0.1.0` ne crée aucune fiche d’observation. Le modèle reçoit directement les images pendant la génération du Brief et à chaque révision de celui-ci. Le planner reçoit à nouveau les mêmes pixels, dans le même ordre, avec le Brief approuvé. Le writer final reste textuel : il ne reçoit que le mapping immuable et le Plan approuvé.

Chaque image porte un rôle fermé — première ou dernière frame, keyframe, sujet, décor, composition, style ou mouvement — et l’ordre affiché fixe le mapping `<Image N> → <Picture N>`. Avant création, l’interface affiche ce mapping et exige sa confirmation ; toute image ajoutée, retirée, déplacée ou requalifiée invalide cette confirmation. Un warning non bloquant signale aussi une intention explicitement multi-plan lorsque la recette mono-plan est active. Le sélecteur propose toutes les versions Direct avant la création du Plan, puis verrouille la recette dans la composition et conserve ce choix après `Nouveau`. `minimax.h3.ref2v.direct@0.3.3` est sélectionnée par défaut ; `0.3.2` reste le témoin mono-plan à placeholders, `0.3.1` son témoin compact précédent, `0.3.0` le témoin verrouillé complet, `0.2.0` le témoin temporel V2 et `0.1.0` le témoin historique.

Le Plan est volontairement générique : personnes, vêtements, accessoires, objets rigides ou articulés utilisent le même contrat de contacts, trajectoires, appuis, relâchement et état observable. Depuis `0.2.0`, le LLM cadence uniquement les actions et choisit `final_hold_ms`; le code place l’état final à la fin du dernier beat et calcule la durée totale, sans retimer ni interpréter les gestes. La `0.3.0` ajoute l’arbitrage supervisé des risques. La `0.3.1` compacte les instructions et le contexte writer. La `0.3.2` réserve les labels `<Picture N>` à l’en-tête compilé. La `0.3.3` retire aussi toute sémantique caméra du contexte du writer : celui-ci ne voit que `camera_landmarks_ms`, tandis que PanelForge insère déterministiquement la clause officielle depuis le Plan approuvé. Cette dernière recette mono-plan est la voie robuste sélectionnée par défaut.

Une tenue finale faible, une durée dérivée supérieure à 15 secondes et les risques non arbitrés restent des avertissements. JSON illisible, intervalles impossibles, mouvement caméra inconnu ou mapping altéré restent bloquants. Dans la `0.3.3`, landmark absent ou dupliqué, placeholder résiduel et prose de mouvement caméra réintroduite par le writer sont rejetés avant compilation ; la casse de la phrase sujet suivant l’insertion est normalisée mécaniquement. Ces contrôles sont propres au nouveau contrat et ne modifient pas les compositions historiques.

`minimax.h3.ref2v.direct.multishot@0.2.0` ajoute à côté la recette expérimentale flexible : une à trois références et deux à six plans reliés par des coupes franches. Elle réutilise le même Brief multimodal, le Plan éditable et l’arbitrage, sans appel LLM supplémentaire. Le planner choisit le nombre minimal de plans, leur durée, leur composition d’ouverture et un raccord structuré — repère spatial, position, direction et phase du mouvement. PanelForge dérive `shot_N`, les timestamps de coupe, la durée totale et `camera_N`. Le writer produit dynamiquement `scene_setup`, `shot_1` à `shot_N` et les deux champs audio, sans voir ni paraphraser les mouvements caméra ; le code compile l’en-tête, les headings et les clauses canoniques. La `0.1.0`, limitée à trois plans et aux placeholders, reste un témoin immuable.

Les risques non arbitrés, une tenue finale faible et une durée dérivée supérieure à 15 secondes restent des avertissements. La V2 verrouille le nombre de plans pendant l’arbitrage et les révisions, mais autorise une nouvelle génération du Plan à en choisir un autre. Elle exclut encore `<scenetrans>`, les dialogues traversant une coupe et les transitions stylisées ; ces syntaxes resteront dans des recettes séparées.

Les trois appels nominaux sont déclenchés séparément dans l’interface. Les corrections manuelles ne consomment aucun appel ; une révision du Brief ou du Prompt en langage naturel ajoute un appel explicite. Les recettes historiques et leurs sessions ne sont pas modifiées.

## Lancer le Lab

L’interface tourne sur le poste PanelForge et appelle ComfyUI à distance. Rien n’est installé dans l’environnement Python du serveur GPU.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python scripts\run_lab.py `
  --base-url http://bucket:8188 `
  --llm-base-url http://bucket:8083/v1
```

Puis ouvrir `http://127.0.0.1:7860`.

Unsloth Studio peut servir de fournisseur LLM local sur le poste PanelForge.
Lancez-le séparément, créez une
clé dans `Settings > API`, puis configurez la connexion avant de démarrer
PanelForge :

```powershell
unsloth studio -p 8888
$env:PANELFORGE_LOCAL_LLM_URL="http://127.0.0.1:8888/v1"
$env:PANELFORGE_LOCAL_LLM_API_KEY="votre-cle-unsloth"
python scripts\run_lab.py `
  --base-url http://bucket:8188 `
  --llm-base-url http://bucket:8083/v1
```

Chaque sélecteur LLM propose alors la case `Local · Unsloth`. La liste locale
est relue dynamiquement depuis `/v1/models` ; les IDs sont
préfixés par leur provenance (`local::`) afin que toutes les étapes
suivantes d'un même parcours restent sur le fournisseur sélectionné. Si un
serveur local est arrêté ou inaccessible, son catalogue est simplement masqué
sans bloquer les autres. Les parcours qui envoient des images exigent un modèle
compatible vision. PanelForge transmet toutes les images choisies au
fournisseur sans appliquer de limite locale ; une éventuelle limite reste donc
celle du serveur appelé.
Le bouton `VRAM LLM` continue de piloter uniquement llama.swap sur le serveur et
ne décharge pas Unsloth Studio.

Les données techniques locales sont écrites sous `workspace/assets`, `workspace/runs`, `workspace/krea2_runs`, `workspace/krea2_batches`, `workspace/krea2_assisted`, `workspace/krea2_edits`, `workspace/video_runs`, `workspace/prompt_sessions` et `workspace/prompt_compositions`, tous ignorés par Git. Les URLs peuvent aussi être définies avec `PANELFORGE_COMFY_URL`, `PANELFORGE_LLM_URL` et `PANELFORGE_LOCAL_LLM_URL`; la clé Unsloth reste dans `PANELFORGE_LOCAL_LLM_API_KEY` et ne doit pas être versionnée. Les projets KREA2 Edit validés utilisent séparément `D:\AI\PanelForge\KREA2 Projects` ou la racine configurée par `PANELFORGE_KREA2_PROJECTS_ROOT`. Les créations assistées explicitement enregistrées utilisent `D:\AI\PanelForge\KREA2 Creations` ou `PANELFORGE_KREA2_CREATIONS_ROOT`.

Le catalogue KREA2 utilise par défaut les chemins UNC stables du montage SSHFS :
`\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion\_models\Krea2` pour
les checkpoints et `\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2`
pour les LoRA. Ils correspondent au lecteur `Y:` sans dépendre de sa visibilité
dans la session qui lance Python. Ces racines peuvent être remplacées par
`PANELFORGE_KREA2_MODELS_ROOT` et `PANELFORGE_KREA2_LORAS_ROOT`. Lorsque le
lecteur local n’est pas visible dans la session de PanelForge, l’inventaire des
ressources `KREA2/` exposées par ComfyUI sert de secours ; taille, précision et
métadonnées locales restent alors indiquées comme inconnues.

Le Lab appelle seulement les API du serveur. llama.swap reste responsable du chargement, du swap et de la mémoire GPU ; aucune bibliothèque d’inférence n’est installée par PanelForge. Le bouton global `Libérer la VRAM` passe par PanelForge puis appelle l’endpoint administratif officiel de llama.swap : tous les modèles LLM actifs sont déchargés et le prochain appel recharge automatiquement le modèle demandé. Cette action peut interrompre une génération LLM en cours.

Le streaming repose sur `stream=true` et des événements SSE internes partagés par H3 Base et Ref2V. Les garde-fous de sortie sont échelonnés à 64 000, 131 072 ou 262 144 tokens selon le type d'appel ; les étapes structurées longues Brief/Plan/Writer H3 utilisent 262 144. Ces valeurs sont volontairement très hautes et servent surtout de protection contre une génération sans fin ; la fenêtre de contexte du fournisseur peut imposer une borne inférieure. Si le serveur termine avec `finish_reason=length`, l’interface indique le budget épuisé, rappelle que le raisonnement interne y est inclus et conserve le texte partiel sans l’enregistrer automatiquement comme une révision complète. Avec `sendLoadingState: true` dans llama.swap, PanelForge reconnaît aussi son message de chargement et l’éventuelle position dans la file. llama.swap ne fournit actuellement pas de pourcentage de chargement fiable : l’interface n’en invente donc pas. Les contenus de raisonnement ordinaires du modèle ne sont jamais affichés comme état système.

Les 20 derniers appels sont conservés dans `workspace/llm_calls.json` : opération, modèle, prompts exacts, réponse, durée, tokens, statut transport, issue applicative, `finish_reason` et erreurs éventuelles. Les images ne sont jamais recopiées dans ce journal ; seules leurs métadonnées et leur SHA-256 sont enregistrées. Ce fichier local peut contenir du texte sensible, reste ignoré par Git et n’est pas exposé par l’API du Lab.

### Diagnostic passif des délais d’images

Les workers KREA2 assisté et Qwen/MiniMax (dont les images H3 des Recettes)
écrivent `workspace/system/image-timings.jsonl`. La collecte est active au
démarrage du Lab ; `PANELFORGE_IMAGE_TIMINGS=0` la désactive au prochain
démarrage. Une modification de code nécessite le redémarrage habituel du Lab,
à effectuer une fois les travaux en cours terminés.

Les lignes `kind=image` correspondent à un passage de suivi d’un essai : IDs projet/essai/
exécution, état observé, durées et tailles. Une reprise conserve l’ID d’essai
mais reçoit un nouveau `trace_id`. Aucun prompt, image, URL, nom de fichier ou
message d’erreur n’est recopié. Le journal tourne sur trois fichiers de 2 Mio
maximum chacun (`.jsonl`, `.jsonl.1`, `.jsonl.2`). Les phases sont bornées en
mémoire, les polls HTTP agrégés, et une seule ligne est écrite après libération
de la réservation GPU. Les sections critiques KREA2 hors worker produisent
aussi une ligne `kind=operation` si elles durent au moins 250 ms ou lèvent une
exception, après libération du verrou. Aucun appel réseau supplémentaire, thread ou dépendance
n’est ajouté ; une erreur d’écriture diagnostique est ignorée.

Pour comparer un essai fluide et un lent, examiner `catalog.*.lock_wait`,
`catalog.*.filesystem`, `catalog.*.http`, `download.response`, `download.body`
(avec le nombre d’octets), puis `asset.content_write_fsync` et
`asset.metadata_write`. `resource.wait` inclut l’admission et la protection
thermique ; `queue_wait_ms` mesure l’attente avant ce passage du worker, depuis
l’horodatage persistant. Une reprise utilise `queue_age_ms` à la place.

Le schéma 2 précise les attentes locales de KREA2. Dans `phases`,
`krea2.service.render.{claim,submitting,running,finish,release}.lock_wait`
mesure l’attente du verrou du service ; `.lock_held` mesure sa détention.
Les opérations lentes portent le nom de leur section critique dans `operation`,
notamment `krea2.service.render_queue` (lecture de la file par l’interface) et
`krea2.service.process_next_render` (sélection du prochain rendu).
`lock_id` identifie le verrou dans le processus ; `process_id`, `thread_id` et
`monotonic_start_ms + start_ms/end_ms` permettent de rapprocher les intervalles
des threads d’un même processus. Le journal est écrit à la fin des opérations :
l’ordre des lignes n’est donc pas celui de leur début.

Dans `aggregates`, `projects.*.lock_wait/lock_held` mesure les verrous du stockage.
`projects.index.enumerate` compte les entrées parcourues et les projets trouvés
lors de l’initialisation ; `projects.index.recover` mesure la récupération de la file.
`projects.list.load` compte les projets effectivement chargés.
`projects.read` sépare la lecture des JSON de `projects.decode` (JSON et objets
du domaine). `projects.serialize/encode`, `projects.write.flush`,
`projects.write.fsync` et `projects.write.replace` détaillent l’enregistrement.
Les lectures répétées sont agrégées (nombre, durée cumulée, maximum), sans ligne
par projet ni lecture supplémentaire. `cpu_ms` mesure le CPU consommé par le
thread dans la phase ; un écart avec la durée écoulée peut aussi venir d’un
verrou, de l’ordonnancement ou du GIL, et ne prouve pas une attente disque.
Les intervalles des agrégats couvrent plusieurs appels ; utiliser les phases
individuelles du verrou de service pour corréler précisément une contention.
Un agrégat `mixed_locks=true` combine plusieurs verrous de projets et ne porte
donc pas de `lock_id` unique.
Les phases utilisent une horloge monotone et peuvent s’imbriquer : leurs durées
ne s’additionnent pas toutes. Les agrégats fournissent nombre, cumul, maximum
et début/fin ; le cumul des polls exclut les pauses entre eux.
`server_execution_ms`, lorsqu’il existe dans l’historique ComfyUI, utilise
uniquement ses horodatages serveur. Une réponse HTTP lente ne suffit pas à
accuser le réseau : elle inclut aussi l’attente côté serveur. Les temps LLM
restent dans `llm_calls.json`.

### File KREA2 et historique des projets

La file KREA2 utilise un index en mémoire des essais actifs, alimenté après
chaque sauvegarde réussie. Les fichiers `krea2_assisted/*/project.json` restent
la référence durable ; leurs formats et les ordres de file sont conservés.
Au démarrage du worker, l’index retrouve une fois les essais à reprendre et
le dernier ordre connu. Les consultations de file, la sélection suivante,
l’attribution d’un ordre et les réveils d’un worker déjà actif ne rescannent
ensuite plus l’historique. La coordination GPU existante reste utilisée.

La liste récente conserve en mémoire les identifiants et dates de modification,
puis ne lit que les projets demandés. Ses lectures ne retiennent pas le verrou
global du service ; les lectures de fichiers sont protégées par projet.
Les récupérations de rendus détachés partagent le verrou d’exécution du worker
pour éviter les doubles imports. Leurs appels ComfyUI et ceux des annulations
s’effectuent hors du verrou global ; l’état courant est revérifié avant de
sauvegarder, pour préserver une annulation ou une modification concurrente.

Cet index suppose un seul Lab écrivant dans le workspace, via le store commun.
Après une importation, restauration ou modification externe des fichiers,
redémarrer le Lab une fois ses travaux terminés pour reconstruire les vues.
Les outils internes peuvent appeler explicitement `rebuild_index()` avant
de reprendre le travail. Un projet illisible bloque la récupération de la
file avec une erreur explicite ; il n’est pas ignoré et le scan n’est pas
répété à chaque poll. Corriger le fichier puis reconstruire ou redémarrer.
La liste récente et l’accès direct aux autres projets restent indépendants
de cette récupération, tant qu’ils ne demandent pas le fichier illisible.

Les traces passives restent disponibles. `projects.index.enumerate` et
`projects.index.recover` mesurent la construction initiale ; elles doivent
disparaître des consultations suivantes. `projects.queue`, `projects.lookup`
et `projects.get.lock_wait` mesurent respectivement l’accès à la file, aux
verrous de projets et au fichier visé. Comparer les attentes du worker avant
et après activation, sans additionner les phases imbriquées ou le calcul GPU
qui se déroule en parallèle. Le coût du démarrage et le gain réel restent à
mesurer sur les générations habituelles.

Tests hors ligne à lancer par l’utilisateur :
`python -m unittest discover -s tests -p "test_krea2_assisted*.py"`, puis
`python -m unittest discover -s tests -p "test_image_timings.py"`.

## Architecture

- `domain` : assets, recettes, runs, sessions et compositions/révisions immuables ;
- `application` : orchestration d’un cas d’usage sans node ID ComfyUI et contrat générique de streaming LLM ;
- `infrastructure/comfy` : transport HTTP minimal ;
- `infrastructure/llm` : adaptateur multimodal OpenAI-compatible, contrôle administratif minimal de llama.swap et décorateur de journalisation bornée ;
- `infrastructure/presets` : validation et compilation des recettes versionnées ;
- `infrastructure/storage` : stockage local vérifié par SHA-256 ;
- `features/lab` : fine interface FastAPI et HTML/CSS/JavaScript natif ;
- `prompt_profiles` : instructions LLM immuables, versionnées et modifiables indépendamment ;
- `prompt_cookbooks` : recettes vidéo versionnées, slots, contrats et templates propres à un cas d’usage ;
- `workflows` : snapshots ComfyUI et manifests explicites.

Les node IDs restent dans les manifests. Le domaine ne dépend ni de FastAPI, ni de ComfyUI, ni d’un fournisseur LLM.

## Feuille de route

### 1. Qualifier les parcours courts I2V et Ref2V

- comparer en A/B le mono-plan robuste `minimax.h3.ref2v.direct@0.3.3` et le multi-plan flexible `minimax.h3.ref2v.direct.multishot@0.2.0` sur les mêmes références et intentions ; qualifier notamment 2, 3, 4 et 6 plans, la distinction des cadrages et les raccords de trajectoire ;
- qualifier `minimax.h3.i2v.direct@0.2.0` sur plusieurs premières frames, intentions et familles de modèles : conformité I2VA, qualité du Brief et du Plan, rythme, continuité, caméra compilée, clipping, tags, voix et synchronisation labiale ;
- versionner une nouvelle recette seulement à partir de défauts reproduits sur plusieurs rendus, en conservant prompts, contexte compilateur et observations de test.

Les transitions stylisées et le dialogue continu à travers les coupes restent hors scope tant que ce premier A/B n’est pas qualifié.

### 2. Vérifier la réutilisabilité du moteur vidéo

- permettre plusieurs compositions/forks sur une même session pour comparer deux versions sans réanalyser les images ;
- ajouter un cookbook de transition comme deuxième cas d’école ;
- introduire explicitement son contrat T2VA/FL2VA au lieu de le forcer dans Ref2VA ;
- conserver les mêmes portes de génération, édition et approbation.

### 3. Qualifier l’Image Lab actuel

- refaire le smoke réel de `character.change_view` ;
- évaluer la matrice visuelle sur plusieurs personnages ;
- ajuster les bornes LoRA uniquement à partir des résultats observés.

### 4. Étendre l’édition d’image

- recettes à un, deux ou trois slots sémantiques (`source`, `identity_reference`, `scene_reference`, `previous_panel`) ;
- opérations dédiées telles que changement d’âge ou édition libre ;
- continuité optionnelle depuis le panel précédent lorsque la scène ne casse pas.

### 5. Construire la Forge narrative

- importer une histoire et proposer personnages, lieux et props ;
- constituer des reference packs approuvés ;
- planifier les panels par `asset_id`, puis les rendre avec les recettes qualifiées.

Les ateliers H3 Base et Ref2V utilisent des workflows strictement versionnés ; les autres workflows vidéo restent à qualifier avant intégration. Limitation V1 : une session de génération ne porte encore qu’une seule composition/cookbook. PanelForge ne cherche pas à devenir un éditeur universel de graphes ComfyUI ni à découvrir automatiquement leurs paramètres.

## Vérification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

La suite couvre le domaine, les manifests, les transports, le stockage, l’orchestration et les API du Lab. Les smokes réels nécessitent llama.swap et/ou ComfyUI joignables avec les modèles attendus.


### Atelier Danse dans Ref2V

`Ref2V → Danse` prépare un transfert de chorégraphie depuis une vidéo, avec le personnage **et le décor de la photo**. Importer une photo en pied, importer la vidéo, choisir son début et un extrait de 5,2 à 15 secondes, puis **Préparer l’essai**. L’extrait est normalisé à 24 FPS et raccourci à la grille H3 `17n+5` sans dépasser la durée choisie. Le son de cet extrait est conservé par défaut et remis dans la vidéo finale, sans utiliser la piste sonore réinventée par le rendu.

Le sélecteur Danse contient seulement les deux recettes présentes : REF2V `0.2.5` et BUNNY `0.1.3`, avec leur VAE INT8/ConvRot actuel. L’extension versionnée `workflows/video.reference/dance/1.0.0/manifest.json` ajoute les entrées vidéo/audio et les liaisons de sauvegarde/reprise des latents. Aucun workflow Reddit/LBH n’est importé et aucun Character Swap LoRA n’est installé ni imposé. Le catalogue de l’atelier Images reste inchangé.

**Générer la danse** lance le rendu habituel de la recette choisie, avec ses valeurs par défaut. Les résolutions égales sont acceptées : BUNNY conserve ses deux passes à ×1 ; REF2V standard saute l’upscale et la finition par défaut. Dans les réglages repliés, **Aperçu rapide uniquement**, décoché par défaut, permet de calculer seulement la première passe aux MP initiaux et de conserver les latents vidéo/audio. **Finaliser cet aperçu**, dans l’historique, recharge ces latents pour la finition sans recalculer la première passe. Seuls les MP finaux peuvent changer ; le prompt, la seed, le ratio, les modèles, les LoRA et le sampling restent ceux de l’aperçu choisi. À résolution égale avec REF2V sans finition forcée, l’aperçu est utilisable directement : aucune finition supplémentaire n’est lancée. Les anciens brouillons restent accessibles et finalisables à une résolution compatible.

Le prompt est prêt sans appel LLM. Il reste modifiable et enregistrable. L’ajustement facultatif propose une nouvelle version en un seul appel, avec Gemma local sélectionné si disponible ; le choix est mémorisé. Le modèle n’observe pas la vidéo et ne doit pas inventer sa chorégraphie. La proposition peut être appliquée ou abandonnée. Les sources, les prompts réellement exécutés et les résultats sont conservés dans les projets H3 ; leur récupération après interruption inclut le son et les latents nécessaires à la finition.

La fidélité du transfert reste à qualifier par des essais utilisateur : ce sont des références guidant le moteur, pas un verrouillage pixel par pixel. Commencer par un seul danseur, un plan fixe continu et une photo au cadrage compatible. Cette livraison concerne l’atelier Danse autonome ; le séquenceur Histoire V3 et l’intégration des travaux avec protagoniste restent des étapes distinctes.

Prérequis : FFmpeg/FFprobe déjà fournis sous `dlss_root/tools`, les deux recettes existantes et les nœuds ComfyUI `LoadVideo`, `GetVideoComponents`, `SaveLatent`, `LoadLatent`, `LTXVSeparateAVLatent`, `LTXVConcatAVLatent`. La vérification des nœuds précède la soumission d’un rendu. Aucun redémarrage, appel LLM ou rendu n’est lancé pendant l’installation.

Régressions préparées, à exécuter par l’utilisateur depuis le checkout actif avec `PYTHONPATH=src` : `python -m unittest discover -s tests -p "test_dance*.py"`, puis les suites H3/REF2V existantes. Elles utilisent des médias, API et transports simulés, sans génération réelle.
