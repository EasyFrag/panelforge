# Audit initial ASTRA — 5 septembre 2026

## Point de retour

- Code actif : `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`.
- Snapshot de tous les changements accumulés, avant modification ASTRA : commit `b63197f5a97c42aa829024adadf66f220cca1397`.
- Tag annoté publié et vérifié sur GitHub : `snapshot/avant-astra-2026-09-05`, dépôt `EasyFrag/panelforge`.
- Les médias et historiques ignorés par Git restent locaux ; ce tag est une sauvegarde du code, pas des données de production.
- Validation après snapshot : 755 tests passent en 87,258 s avec `D:\Code\panelforge\.venv\Scripts\python.exe`, `PYTHONPATH=D:\Code\localQ\.panelpatch\src`, et `-m unittest discover -s tests`. Le premier essai avec le Python global a échoué faute de dépendances ; aucun paquet n'a été ajouté.

## Direction produit exprimée aujourd'hui

Priorité à l'atelier humain : partir d'une inspiration, dialoguer avec KREA2 Assisted, comparer les checkpoints, conserver une identité puis préparer librement First/Last Frame dans un décor cohérent. KREA2 Assisted, H3 Base et Ref2V sont les références d'ergonomie positives. Production V1/V2 ne sont pas des parcours à reconduire par défaut.

Les images doivent pouvoir changer de rôle après leur création, notamment inverser First/Last. Le contexte utilisé doit être compréhensible et permettre de repartir avant une bifurcation narrative. Éviter les panneaux qui s'accumulent verticalement et les réglages omniprésents. Un historique de points de reprise avec miniatures paraît une première expérience à comparer à un arbre complet, pas une architecture déjà décidée.

À terme, automatiser d'abord une référence image et une histoire courte via Ref2V, en acceptant éventuellement sa qualité inférieure constatée par l'utilisateur. L'exploration First/Last reste prioritairement humaine. Thèmes initiaux possibles : monstres effrayants et maquillage surnaturel. Les vidéos longues et la continuité voix/style entre clips sont futures.

## Périmètre et limites

Lecture du code, des prompts versionnés, des deux journaux `llm_calls.json` et d'un échange dragon complet. Les données récentes sont dans `D:\Code\panelforge\workspace` ; le journal de `.panelpatch\workspace` s'arrête au 23 août. Les journaux ne conservent chacun que 20 appels. Ce sont des échantillons historiques, pas un benchmark contrôlé. Aucun rendu, navigateur ou appel LLM supplémentaire n'a été lancé pour cet audit. La qualité visuelle des sorties n'a pas été jugée.

## Mémoire : comportement observé

`application/krea2_assisted.py::_completion_request` transmet l'intention originale, le prompt courant, les 13 entrées précédant le message courant (`turns[-14:-1]`, entrées utilisateur et assistant confondues), leurs prompts, le résultat sélectionné et ses réglages. Il joint l'image source, le résultat sélectionné et l'éventuelle image d'appoint du message courant. Les anciennes images d'appoint sont mentionnées dans l'historique mais leurs pixels ne sont pas tous retransmis.

Il ajoute systématiquement jusqu'à 20 recettes publiées, 40 noms de checkpoints et 80 noms de LoRA. Il existe donc une mémoire de contexte effective, même sans interface appelée « mémoire ». Ce n'est pas une mémoire complète illimitée et ce n'est pas un arbre de conversations. `use_feedback` change seulement la tentative sélectionnée ; il ne restaure pas les échanges à la date de cette image.

Dans Production V2, `_memory_context` ajoute les 12 dernières préférences de ressources du profil et les 6 derniers commentaires appréciés/dépréciés du même rôle. Ces derniers ne sont filtrés ni par projet ni par branche : un commentaire narratif d'une autre First Frame peut être réinjecté dans une nouvelle First Frame du même profil. Les liens parent/candidat ne suffisent donc pas à garantir une isolation narrative. C'est un risque confirmé par le code, pas une contamination démontrée sur chaque rendu.

## Exemple KREA2 : dragon

Projet local `krea2-create-0e1817f8e91d4a5ebc5c11cdc0d66979`, mis à jour le 4 septembre : 14 entrées de conversation, 12 essais.

Le dialogue évolue d'un dragon rouge sortant d'un œuf vers un bébé, une interaction avec une main, un dragon sur le bras, puis un retour à la première frame de l'éclosion. Le LLM conserve la grotte, le POV, la palette et les traits du dragon. Cela étaye l'utilité du contexte conversationnel.

Les révisions accumulent cependant des descriptions et des exclusions : absence de flammes, de blessures, de parties du dragon, etc. Lors du retour à un œuf seul, le LLM choisit spontanément une main qui le porte ; l'utilisateur doit préciser ensuite que l'œuf est au sol. Le prompt système demande une réécriture cohérente, mais ne distingue pas explicitement les invariants visuels approuvés des états narratifs temporaires.

Piste : conserver les invariants non concernés par une demande, remplacer complètement l'état narratif concerné, limiter les exclusions aux ambiguïtés utiles et dire dans la réponse française ce qui est conservé/changé. Ne pas promettre qu'un prompt seul compensera une LoRA forte ou garantira un décor identique.

## Mesures vidéo récentes

Journal du workspace principal, cinq triplets consécutifs complets des 4–5 septembre, modèle `local::unsloth/Qwen3.8-27B-GGUF` :

| Étape | Nombre | Durée médiane |
| --- | ---: | ---: |
| Brief | 5 | 30,47 s |
| Plan | 5 | 73,32 s |
| Rédaction finale | 5 | 36,92 s |

Sommes des durées LLM des cinq préparations : 132,652 ; 160,762 ; 137,229 ; 169,021 ; 127,748 secondes. Hors temps de rendu et interactions humaines. Deux appels KREA2 récents durent 31,003 et 24,894 secondes, échantillon trop petit pour généraliser.

Les Plans retournent 8 039 à 10 987 caractères pour des corps finaux de 1 498 à 2 088 caractères. Le modèle répète l'action dans `primary_action`, les `steps`, `continuity_after` et `observable_end_state`. Le writer reçoit encore une projection de plusieurs milliers de caractères. Le premier candidat à l'optimisation est cette redondance de représentation, sans retirer les contraintes caméra/dialogue ni les validateurs.

Les plafonds déclarés dans le journal sont 262 144 tokens pour les trois étapes vidéo et 131 072 pour KREA2. Ils ne prouvent pas une consommation équivalente ni une cause de lenteur. Les compteurs de tokens sont absents sur les appels récents ; on ne peut pas séparer quantitativement préremplissage, raisonnement et génération. `include_reasoning` contrôle le filtrage/affichage de trace dans le transport, pas un budget explicite de raisonnement.

## Exemple vidéo : fraise de cristal

Triplet débutant le 5 septembre à 07:19:24 UTC : appels `llm-4811bc3d03f147429b12a492bc1d9413`, `llm-558c59d670824d658f1b99c6f9c4c9db`, `llm-1468fe81d0a34b44b4d4d0e01693d4d9`.

Demande : saisir une fraise de verre, la planter, puis faire pousser un fraisier de cristal en dix secondes. Le Plan décrit bien une séquence de saisie, plantation, retrait et croissance. Mais son `primary_motion` combine plantation et croissance, tandis que le système impose ce même mouvement dans chaque beat jusqu'à la fin. Le writer explique alors que la même action continue pendant que les doigts relâchent et que la main se retire : incohérence sémantique dans le texte, malgré validation structurelle réussie.

Piste prioritaire qualité : distinguer un plan sans coupe d'une action unique qui ne s'arrête jamais. Une séquence causale peut changer d'action et terminer le contact de la main tout en conservant une croissance active au dernier instant. Traiter cela dans une nouvelle recette expérimentale ; conserver les recettes et le comportement historique de gel L2VA comme témoins.

## Ordre proposé pour les changements suivants

1. Amélioration KREA2 bornée : clarification invariants/état courant et suppression des répétitions exactes du contexte. Dans un appel récent de 12 686 caractères utilisateur, le catalogue prend 4 111 caractères et les recettes 1 639 ; leur sélection conditionnelle peut aider, mais préserver les conseils de ressources explicitement demandés. Versionner l'opération si son contrat de prompt change.
2. Nouvelle recette vidéo expérimentale à Plan plus compact et mouvements par phase. Comparer aux témoins sur dragon First/Last, transformation séquentielle, mouvement continu et dialogue exact. Mesurer latence, erreurs de contrat, fidélité à l'intention et rendu réel ; aucun gain qualitatif n'est encore démontré.
3. Puis améliorer l'atelier autour des outils appréciés : rôles d'images réassignables, contexte visible et points de reprise. Définir si un point restaure une conversation ou crée une branche avant de dessiner un arbre. Automatisation Ref2V après cette qualification.

Ne pas déployer simultanément une réécriture UX, une nouvelle mémoire et de nouveaux prompts : les essais deviendraient difficiles à attribuer. Ce document constitue l'audit initial ; aucun prompt ni comportement applicatif n'a été modifié.
