# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0`; Prompt Lab fournit streaming, carillon de fin renforcé, révisions, approbations et journal borné des appels LLM.
  - Les onglets produits sont désormais `I2V` et `Ref2V`, fondés sur les parcours Direct ; les anciens I2V simple et Ref2V spécialisé sont relégués dans une vue Archives en lecture seule sans supprimer leurs cookbooks ni leurs compositions.
  - Ref2V réalise 1–3 images natives → Brief multimodal → Plan JSON multimodal → prompt H3, sans Observation séparée.
  - `minimax.h3.ref2v.direct@0.3.3` est le mono-plan robuste par défaut. Son writer ne reçoit que `camera_landmarks_ms`; PanelForge insère les clauses caméra depuis le Plan. La `0.3.2` reste le témoin historique à placeholders.
  - `minimax.h3.ref2v.direct.multishot@0.2.0` ajoute séparément 2 à 6 plans et leurs coupes franches, avec le même Brief, Plan et arbitrage ; la `0.1.0` à trois plans reste un témoin immuable.
  - Le sélecteur Ref2V sépare maintenant les recettes `Mono-plan standard`, `Multi-plan structuré` et `Multi-plan direct`. Cette dernière correspond au cookbook interne `minimax.h3.ref2v.direct.multishot.superfast@0.2.0` et impose un seul appel LLM direct : capsule Brief déterministe, images natives, mapping et liberté produisent immédiatement le corps H3. PanelForge ajoute seulement le header canonique, normalise les balises et auto-approuve le Prompt ; aucun Plan JSON n'est créé. La `0.1.0` Plan-first reste chargeable comme recette historique mais n'est pas proposée aux nouveaux runs.
  - Le Plan multi V2 dérive les IDs, coupes, durée et `camera_N` depuis l’ordre du tableau, structure la composition d’ouverture et le raccord spatial/motion de chaque plan, et avertit sur les répétitions exactes entre plans adjacents.
  - Le writer multi V2 reçoit une projection dynamique sans caméra ni placeholder ; PanelForge compile ensuite les champs `shot_1` à `shot_N`, les headings, les timestamps et les phrases caméra canoniques. Arbitrage et révision conservent le nombre de plans approuvé.
  - I2V réalise une première frame native → Brief multimodal → Plan V2 arbitrable → prompt I2VA compilé avec `minimax.h3.i2v.direct@0.2.0`; la `0.1.0` reste le témoin à placeholders.
  - Pour I2V `0.2.0` et Ref2V mono `0.3.3`, le contexte persiste directive et horaire, le writer ne voit aucun mouvement/placeholder, et génération, édition ou révision réinsèrent déterministiquement la phrase canonique au bon jalon.
  - Les recettes restent sélectionnables par `id@version` avant le Plan puis verrouillées dans la composition; le multi-plan dérive headings, coupes, durée et caméra sans horloge redondante du LLM.
  - Ref2V conserve la recette sélectionnée après `Nouveau`, avertit sans bloquer si une intention multi-plan utilise le mono-plan et exige une confirmation explicite du mapping des rôles, invalidée à chaque modification.
  - L’aide `?` des références Ref2V résume dans un tableau compact et accessible le canal contrôlé par chacun des huit rôles d’image.
  - I2V et Ref2V proposent un Mode rapide partagé qui génère puis approuve Brief, Plan et Prompt sans nouvelle recette ni appel LLM ; il ignore les warnings et recommandations, s’arrête sur toute erreur bloquante et reprend sans rejouer les étapes déjà validées. Dans Ref2V, l’orchestration ne propose plus que `Supervisé` et `Rapide` ; la rédaction directe en un appel appartient à la recette multi-plan directe et masque ce contrôle.
  - I2V et Ref2V peuvent afficher en direct, sur option explicite, la trace séparée transmise par le modèle. Cette trace de debug reste éphémère, n’est jamais concaténée au document ni au journal, et n’est pas simulée lorsque le modèle n’en fournit pas.
  - I2V et Ref2V Direct remplacent le curseur de liberté créative par cinq modes discrets alignés sur les politiques backend. Le contrôle précise que son effet direct s’arrête au Brief, restaure exactement toute ancienne valeur numérique hors preset et reste aligné dans les colonnes étroites.
  - Les archives neutralisent création et écritures mais laissent ouvrir et copier tout prompt actif, même non approuvé ou obsolète ; leurs listes chargent jusqu’à 200 sessions avant filtrage.
  - Prompt Lab peut créer une session propre depuis une session existante en réutilisant ses assets validés, avec de nouveaux IDs et sans recopier Brief, approbations ni composition.
  - I2V et Ref2V permettent de préparer ce nouveau parcours depuis un run récent en changeant modèle, recette, intention, liberté ou Mode rapide. Les actions combinées proposent/appliquent puis approuvent sans franchir une erreur, l’étape suivante s’ouvre avec défilement, et le prompt expose les noms complets des images à copier.
  - `Nouveau parcours` est disponible dans la barre supérieure à côté de la libération VRAM ; les ouvertures de runs et les chaînes combinées sont protégées contre les réponses asynchrones obsolètes.
  - Les nouveaux parcours préfèrent automatiquement un modèle dont l’identifiant contient `Qwen3.8-27B`, avec repli sur Qwen 3.6 puis sur le premier modèle exposé.
  - Le transport ComfyUI expose maintenant queue/statut normalisés, annulation ciblée via Jobs API avec fallback legacy prudent, et URL WebSocket client-scoped. La preview Video Lab passe par un relais WebSocket PanelForge same-origin qui transmet les événements texte/binaires et évite le rejet CORS du navigateur.
  - Le Video Lab exécute la recette immuable expérimentale `video.generate.ref2v/minimax-h3-ref2v@0.1.0` avec une à trois références ordonnées, prompt, ratio, mégapixels, durée, steps et seed. Il compile les slots réellement utilisés, conserve un historique séparé et limite l'exécution à un rendu actif.
  - Sa preview live consomme les événements KJ JPEG/WebP/MP4 sur un client WebSocket ComfyUI isolé ; l'interface distingue connexion, disponibilité et erreur du relais sans interrompre le rendu. La vidéo MP4 finale avec audio est importée comme asset. Une annulation cible le job exact et reste en `cancel_pending` si ComfyUI ne confirme pas l'arrêt.
  - Les assets vidéo acceptent les requêtes HTTP Range nécessaires au lecteur natif. La sortie finale conserve uniquement le lecteur vidéo HTML standard, sans bouton, avertissement ni diagnostic audio supplémentaire ; chaque nouvel asset reste chargé via une URL anti-cache stable.
  - Après un redémarrage de PanelForge, la lecture, l'annulation ou la réservation du slot réconcilie un run ComfyUI détaché : une sortie déjà terminée est importée, une erreur devient terminale et un job encore actif reste suivi par le polling UI.
  - Ref2V peut préremplir Video Lab avec ses images ordonnées, le prompt actuellement visible et la durée dérivée du Plan, sans lancer automatiquement le rendu.
  - Storyboard Lab exécute la recette immuable `krea2.storyboard.from_text@0.1.0` : une intention, un modèle et 2, 4, 6 ou 9 panels produisent en exactement un appel LLM des variables narratives strictes, ensuite injectées par code dans le squelette KREA2 fixe. L’interface expose prompt éditable/copiable, variables, warnings, historique, ouverture et relance ; un JSON invalide ou tronqué reste disponible comme brouillon diagnostic sans second appel de réparation.
  - Image Lab exécute désormais la recette immuable `image.generate.t2i/krea2@0.1.0` : prompt, modèle KREA2 installé, ratio, 0,5–4 MP et seed alimentent un workflow T2I nettoyé. Le modèle GPT KREA2 fourni est sélectionné par défaut, tandis que sampler, scheduler, CFG, steps, VAE et CLIP restent verrouillés par la recette.
  - L’inventaire des UNET est découvert dynamiquement via ComfyUI et recoupé avec l’allowlist qualifiée ; la chaîne exacte annoncée par le serveur est conservée. KREA2 fournit PNG final, historique, relance et annulation, sans preview ni LoRA en V1.
  - Storyboard Lab peut préremplir KREA2 avec le prompt actuellement édité et une provenance vérifiée côté serveur, sans lancer automatiquement le rendu. Les runs détachés ou en annulation incertaine sont réconciliés avec ComfyUI avant de réserver le slot, afin d’importer une sortie tardive plutôt que de la perdre.
  - La sortie PNG KREA2 conserve maintenant son ratio naturel dans un cadre plafonné à 760 × 600 px environ, sans étirement à toute la largeur ou hauteur de la zone de résultat.
  - Storyboard affiche désormais en option la trace modèle séparée pendant la génération, via le même composant borné et la même préférence locale que les parcours Direct ; cette trace reste éphémère et absente des runs.
  - Les Plans Direct mono récupèrent uniquement le cas non ambigu où plusieurs steps couvrent exactement tout le même beat : ils sont fusionnés en une tranche simultanée avec provenance et warning. Les chevauchements partiels, trous et intervalles distincts restent bloquants.
  - Validation locale : 607 tests passent.
- Broken / missing:
  - Le dialogue traversant une coupe et les transitions stylisées ne sont pas couverts par la recette multi-plan flexible.
  - Une référence secondaire brute peut encore influencer le décor malgré les frontières textuelles.
  - Le Super rapide direct accepte volontairement les écarts H3 non fatals comme warnings ; qualifier l'obéissance réelle, la structure des coupes et la densité des prompts par modèle avant de l'élargir au mono-plan ou à I2V.
  - Les contrôleurs UI I2V Direct et Ref2V Direct partagent le backend mais gardent encore du code JavaScript dupliqué.
  - KREA2 V1 ne gère ni LoRA, ni preview, ni découpe automatique de la planche en panels indépendants, ni transfert de ces panels vers Ref2V.
  - Les autres formes d'overlap temporel restent volontairement strictes ; la récupération ne couvre que plusieurs steps tous identiques aux bornes exactes de leur beat.
  - Deux arrêts llama.swap `upstream command exited prematurely` sont présents dans les historiques disponibles ; ils sont distincts des rejets contractuels et les relances suivantes réussissent.
  - Audit de poids Ref2V : sur le dernier Plan Qwen, le user prompt fait 18 103 caractères, dont 8 815 de Brief et 8 921 de schéma/tail ; le writer reçoit ensuite 15 329 caractères, dont le même Brief. Les moyennes Qwen observées atteignent environ 21,9 k caractères d’entrée pour le Plan, 21,6 k pour le writer et 32,8 k pour reconcile.

## Decisions

- Les recettes publiées restent immuables et une composition conserve sa version.
- Les variantes partagent leurs contrats et leur orchestration; les différences de contexte writer sont déclarées dans le manifeste.
- Les warnings n’empêchent pas la validation; seules les erreurs structurelles ou contractuelles bloquent.
- I2V et Ref2V restent deux produits et deux contrôleurs séparés ; seuls streaming, stockage, son et protocole H3 sont partagés.
- Les cookbooks legacy publiés restent immuables et chargeables, mais ne sont plus proposés pour créer un parcours depuis l’interface.
- I2V accepte exactement une première frame : I2VA uniquement. FL2VA reste hors périmètre.
- KREA2 est une recette Image Lab dédiée et versionnée ; le modèle, le ratio, les mégapixels et la seed sont variables, tandis que le sampling et les modèles auxiliaires restent immuables dans la V1.

## Next steps

1. Ajouter ensemble une recette I2V mono compacte et une recette FL2V dédiée (première frame requise, dernière frame facultative côté UX), sans modifier I2V `0.2.0`.
2. Prototyper ensuite une recette Ref2V mono `0.4.0` compacte en A/B : Brief projeté, schéma compact et writer sans Brief intégral ; conserver `0.3.3` intacte.
3. Faire un smoke réel KREA2 puis ajouter la télémétrie GPU read-only avant toute bascule automatique de VRAM.

## Risks / open questions

- Le garde-fou rejette exhaustivement les formulations caméra canoniques et garde une détection volontairement étroite des paraphrases libres pour ne pas confondre mouvement du sujet et caméra ; qualifier ses faux positifs/négatifs sur des sorties réelles.
- Un Plan cohérent ne garantit pas à lui seul la fidélité du moteur vidéo aux références brutes.
- FL2VA n’entre pas dans ce parcours : ne pas laisser une seconde image modifier silencieusement le contrat I2VA.
- Les modes de liberté restent une politique globale du Brief ; de vrais axes indépendants « enrichissement visuel » et « caméra/rythme » exigeraient un futur contrat explicite et ne doivent pas être simulés par l’UX seule.
- Les Archives chargent aujourd’hui 200 sessions avant filtrage client ; une pagination ou un filtre serveur sera nécessaire si le volume dépasse ce seuil.
- La durée Video Lab et les timestamps écrits dans le prompt restent deux entrées indépendantes ; l'interface affiche la durée effective quantifiée mais ne réécrit jamais le prompt silencieusement.
- Le workflow H3 conserve en V1 l'historique et l'archive Spectrum en VRAM ; mesurer son coût réel avant d'automatiser la cohabitation avec llama.swap.
- Une coupure de PanelForge entre la soumission ComfyUI et la persistance de son identifiant reste une fenêtre transactionnelle externe non récupérable sans idempotence côté serveur.
- La recette Storyboard exige un JSON strict en un seul essai : la qualité dépendra de la discipline structurelle du modèle. KREA2 peut encore fusionner des cellules ou perdre des détails, surtout sur une grille de neuf panels ; les premiers A/B doivent mesurer ces écarts avant de modifier le squelette fixe.
- La présence d’un modèle dans ComfyUI ne suffit pas à le qualifier : seuls les checkpoints de l’allowlist sont sélectionnables, et les performances/consommations 3–4 MP doivent encore être mesurées sur la RTX 6000.
- Les historiques sont actuellement répartis entre `D:\Code\panelforge\workspace` et `.panelpatch\workspace` selon la copie de code lancée ; cette séparation peut faire croire à deux versions de Python et fragmenter l’audit des runs.
- Le poids dominant des prompts Ref2V vient des données répétées (Brief, schéma, Plan), pas des seules règles système ; supprimer des garde-fous avant de réduire ces duplications risquerait de dégrader la qualité sans gain principal.
