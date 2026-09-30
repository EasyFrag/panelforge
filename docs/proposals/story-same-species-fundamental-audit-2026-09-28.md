# La même espèce — audit fondamental après les rendus — 28 septembre 2026

## Conclusion et rectification du premier audit

L'échec ne se réduit pas à une mauvaise génération vidéo. Une histoire insuffisamment construite est devenue un plan faisant autorité ; les étapes suivantes en ont préservé les défauts et ajouté une mise en scène trop complexe. La relecture a validé la présence des événements sans suffisamment vérifier leur effet sur le spectateur.

Le premier audit était trop indulgent : constater une présentation et un baiser ne justifiait pas de juger leur enchaînement satisfaisant. Il portait sur l'écriture et les références avant les vidéos ; les constats visuels ci-dessous le complètent et révisent ce jugement. Le brief minimal proposé par l'assistant conservait l'intrigue, mais pas toutes les conditions de fonctionnement de la comédie source. Il ne fallait pas présenter quelques réglages comme une garantie d'adaptation équivalente. Cela ne signifie pas que l'utilisateur devrait dicter chaque réplique ou chaque plan : construire les liaisons manquantes est précisément le travail attendu du moteur d'histoire.

Aucun code, prompt actif, réglage, fichier de projet ou traitement en cours n'a été modifié. Analyse et documentation uniquement.

## Périmètre et niveau de preuve

- Histoire `story-887454eeb15c4481b9db6a83ff708e3a`, deux épisodes exportés : `episode-59a00599e5e3474aba7ad4b9a58f5d35` et `episode-255930cd81084389b0164cf2edd04d99`.
- Sept clips bruts terminés : échantillonnage à deux images par seconde, vingt images inspectées par clip, soit 140 images ; transcription automatique locale des sept pistes audio. Il ne s'agit pas d'une écoute humaine continue ni d'une identification automatique certifiée des locuteurs. Les paroles citées ont été rapprochées du scénario et du prompt.
- Lecture des scénarios, plans, relectures, intentions exportées, sept plans vidéo, sept prompts réellement utilisés, paramètres et traces d'appels. Vérification des références et des projets H3.
- L'ordre des références envoyé au rendu correspond à l'ordre des références préparées, pour les sept clips. Le prompt du projet H3 correspond au prompt final de l'usine. Aucun indice d'un échange systématique de Picture N ou d'un ancien prompt exécuté à la place du nouveau.
- Comparaison avec la transcription déjà archivée de Download(34).mp4, vidéo de référence d'environ 100 secondes. Elle n'a pas été réanalysée intégralement en vidéo pendant ce complément.
- Le défaut du dernier clip est présent dans le brut, avant DLSS. Les sept versions agrandies ne font pas l'objet d'un second audit complet.

Les captures prouvent les défauts visibles ; elles ne permettent pas de prouver le mécanisme interne du modèle vidéo. Les liens entre surcharge du prompt et artefacts restent des hypothèses causales étayées, à confirmer par des essais contrôlés ultérieurs si l'utilisateur le souhaite.

## Les quatre problèmes signalés

| Problème | Ce qui a été retrouvé | Origine principale |
| --- | --- | --- |
| « Je suis pas bizarre, j'espère » | Réplique présente dès l'écriture, acceptée par la relecture, puis conservée exactement jusqu'au rendu. Elle ne répond à aucune inquiétude clairement installée. | Écriture et contrôle éditorial. |
| Clé puis baiser immédiat | Le plan narratif choisit déjà ces gestes comme matérialisation de la liaison. Le scénario n'installe presque aucune attirance réciproque ni décision avant le passage à l'acte. | Architecture narrative ; la vidéo exécute un mauvais raccourci. |
| Grossesse incompréhensible | Ventre très avancé dans le clip d'échographie ; « Je suis enceinte » transcrit dans le clip suivant ; bébé au dernier clip, avec maintien explicite de l'apparence enceinte de Mia. | Ellipses, ordre de révélation et état visuel après la naissance. |
| Bébé donnant l'impression de parler | Dans le dernier brut, vers 3 à 6 secondes, le visage adulte de Léo se mélange à celui du bébé dans le reflet. Le texte attribue pourtant les paroles à Léo et Mia. | Composition des visages/reflets et exécution vidéo ; pas de dialogue écrit pour le bébé. |

### Première scène : exactitude des mots, conversation mal construite

La phrase étrange vient du scénariste, pas d'une improvisation H3. Elle a franchi toutes les validations. Sa conformité au registre oral ne lui donne aucune fonction dans cette rencontre.

Le découpage vidéo aggrave l'entrée en matière : Léo commence sa présentation devant la porte encore fermée, puis Marc ouvre. Le plan respecte la présence de la porte, du geste sur l'épaule et des répliques, mais leur ordre affaiblit la situation de conversation. Préserver les mots ne suffit donc pas à préserver la scène.

### Liaison : le signe visible remplace le développement

Le couple « clé + baiser » permet de cocher une liaison secrète. Il ne construit pas l'intérêt des personnages l'un pour l'autre. La clé ajoute un accessoire et un geste technique sans fonction dramatique assez claire : que propose exactement le père, pourquoi maintenant, et qu'accepte Mia ?

Même une comédie volontairement expéditive et absurde a besoin d'un déclencheur lisible. Quelques échanges peuvent suffire ; il n'est pas question d'exiger une romance réaliste. Dans la source, la réciprocité du flirt et la naïveté du fils remplissaient cette fonction. Le raccourci généré conserve le résultat en supprimant le mécanisme.

### Grossesse : information présente, récit mal ordonné

La grossesse n'est pas totalement absente du rendu. Les images la montrent et la transcription retrouve l'annonce. Mais le spectateur passe du dîner à une grossesse déjà très avancée, puis à son annonce, puis à un bébé. Les changements de temps, de connaissance et de situation ne sont pas suffisamment articulés.

Après la naissance, l'intention exportée conserve « Ventre arrondi » et ordonne de maintenir cet état pendant tout le clip. Le prompt final insiste encore plusieurs fois sur le ventre et la main posée dessus. Le problème n'est pas qu'un ventre doive disparaître immédiatement après un accouchement ; c'est que le système conserve l'état narratif de grossesse avancée sans traiter la transition de naissance.

Correction d'une hypothèse du premier audit : la référence d'échographie était ambiguë entre écran et photo, mais le clip brut examiné matérialise bien une image d'échographie tenue en main. Il ne faut pas continuer à présenter l'apparition d'un moniteur encombrant comme un défaut établi de cette vidéo.

### Dernière scène : confusion visuelle confirmée

Le plan puis le prompt demandent d'aligner le visage de Léo et celui du nouveau-né dans une vitre, puis un gros plan des profils presque superposés. Ils ajoutent une réponse de Mia sur cette composition, un sourire de Léo et un échange complice avec Marc.

Les images montrent effectivement une superposition anormale : les traits adultes contaminent le visage du bébé dans le reflet pendant la partie dialoguée. Cela explique visuellement l'impression rapportée par l'utilisateur. Les données ne prouvent pas que le modèle a intentionnellement attribué une voix au bébé.

Ce dispositif était inutile à la compréhension de la fausse preuve finale. Ajouter seulement « le bébé ne parle pas » laisserait intacte une composition qui rend déjà l'identité du visage ambiguë.

## Pourquoi l'approche produit ces défauts

### 1. Elle transforme trop tôt une idée en preuves obligatoires

Le plan choisit des événements et des objets censés les prouver : clé, baiser, calendrier, échographie, carnet, reflet. L'écriture couvre ces éléments, puis la relecture vérifie une grande partie des mêmes éléments. Une mauvaise décision du plan devient ainsi sa propre référence de qualité.

Ce contrôle détecte des omissions et des incohérences de contrat ; il juge mal les questions décisives : pourquoi le personnage agit-il maintenant, quel changement le spectateur comprend-il, et pourquoi la réaction suivante découle-t-elle de ce changement ?

Il faut distinguer l'événement demandé par l'utilisateur, l'effet recherché sur le public et le moyen inventé pour l'obtenir. Le dernier doit rester révisable.

### 2. La validation arrive après le verrouillage des décisions

Pour cette version du workflow, une composition valide peut conduire directement au développement des unités ; une relecture de bloc intervient ensuite. Il existe donc bien une relecture, mais elle a ici laissé passer les défauts essentiels. Le statut `ready` ne prouve ni le naturel du dialogue ni la compréhension du public.

La préparation vidéo travaille ensuite sur des scènes locales et des dialogues à conserver. Elle n'a plus la mission de reconstruire la liaison, la progression de grossesse ou la blague finale. Le rédacteur final doit encore conserver le plan approuvé, ses cadres, son rythme et ses raccords. On ne peut pas attendre de lui une correction globale qui contredirait son contrat.

### 3. L'adaptation préserve l'intrigue mais perd le fonctionnement comique

Dans la référence, des personnages fruits rendent les catégories d'espèces visibles. Le fils exprime sa confiance, réagit aux alibis, évoque le risque d'un bébé d'une autre espèce et transforme ensuite l'espèce du bébé en preuve absurde de fidélité. Le public comprend à la fois la vérité et l'erreur du personnage.

Dans ce run, l'univers est resté non renseigné et a produit des humains réalistes. Le mélodrame et les silences remplacent une partie des échanges. « Les mêmes yeux » introduit une ressemblance classique ; « Un petit humain comme moi » arrive sans préparation suffisante. Il manque surtout le lien intelligible entre cette constatation et sa conclusion sur la fidélité.

Une transposition humaine pourrait fonctionner, à condition de recréer le raisonnement absurde dans ce nouvel univers. Copier sa phrase finale ne conserve pas automatiquement la blague.

### 4. La précision porte sur la caméra plutôt que sur le sens

Sept clips de dix secondes sont divisés en vingt plans. Les prompts finaux comportent environ 4 300 à 5 900 caractères chacun. Ils répètent des informations entre composition initiale, rythme, déclencheur, action, état final et transition.

Cette longueur n'est pas uniquement une prolixité de Gemma. Le dernier appel rédige des fragments d'actions ; le compilateur assemble aussi les champs déjà décidés par le plan. Sur le dernier clip, la réponse finale du modèle ne fait qu'environ 1 600 caractères, pour un prompt compilé proche de 4 900. Il faut examiner ce qui est demandé et assemblé, pas simplement ajouter au système « sois plus concis », déjà proche de ses consignes.

Les réglages effectifs autorisent une forte audace de caméra, de vie de scène et de mouvement supplémentaire. Ils peuvent amplifier la complexité ; ils n'expliquent pas une liaison mal écrite. Rien ne permet d'attribuer avec certitude leur sélection intentionnelle à l'utilisateur, ni de promettre qu'un cran inférieur résoudrait l'histoire.

### 5. Identité, jeu et état temporaire se contaminent

La description de Léo associe déjà son identité à une mâchoire crispée ; celle de Marc à des mains très précises. Ces détails reviennent comme des obligations de jeu au lieu de varier avec la scène. Le ventre enceinte est, lui, propagé après la naissance.

La distinction à renforcer n'est donc pas seulement présence versus parole, déjà discutée auparavant : il faut aussi séparer identité stable, présence dans la scène, rôle de locuteur, état temporaire et action du moment. Chaque information doit avoir une durée de validité adaptée.

### 6. Le système contrôle davantage le projet que le résultat livré

Les sept tâches ont réussi techniquement et ne signalent pas d'avertissement H3. Cela n'atteste ni la lisibilité des ellipses ni l'intégrité des visages. Le rendu puis l'agrandissement ont donc pu continuer alors que la dernière image contenait une confusion majeure.

Une relecture textuelle ne peut pas certifier seule une scène audiovisuelle. Le contrôle du scénario et une inspection ciblée des moments importants du rendu répondent à deux besoins différents ; aucun ne remplace l'autre.

## Qualité et performance

| Étape | Mesure observée | Lecture correcte |
| --- | --- | --- |
| Écriture de cette série | 17 min 40,5 s sur cinq appels, dont un rejet initial ; chaîne réussie 15 min 16,6 s | Mesures du premier audit, hors préparation vidéo et images. |
| Sept plans vidéo Qwen3.8-27B | 12 min 31,3 s cumulées ; 104 198 tokens d'entrée et 56 050 de complétion déclarés | Sept appels, pas sept boucles de correction. |
| Sept rédactions finales Gemma 4 31B QAT | 4 min 24,4 s cumulées ; 38 315 tokens d'entrée et 10 619 de complétion déclarés | Le modèle intervient après approbation du plan. |
| Préparation vidéo totale | 16 min 55,7 s cumulées | Dépense importante sans réparation du fond narratif. |
| Première préparation → dernier DLSS terminé | Environ 56 min 21 s écoulées | Inclut traitements/attentes ; des étapes se chevauchent. Ne pas additionner arbitrairement les temps des différents moteurs. |

Les traces de préparation contiennent environ 175 700 caractères de raisonnement pour les plans et 22 900 pour le rédacteur final. Ce sont des caractères, pas une mesure directe du temps consacré à penser. Le problème observé est une analyse longue qui privilégie les contraintes et la mise en scène ; il n'y a pas de série démontrée de relances narratives réparant puis cassant l'histoire.

Les deux essais enregistrés par projet H3 correspondent au brut et au DLSS, pas à deux générations brutes concurrentes. Les sept rendus ne fournissent aucune comparaison contrôlée permettant de blâmer le nombre de steps, la quantification ou de déclarer un autre modèle supérieur.

Le gain de performance prioritaire serait de ne pas produire et agrandir une histoire déjà défaillante. Le raccourcissement des prompts et du raisonnement vient ensuite, mesuré par qualité obtenue et temps total, pas seulement par vitesse de sortie.

## Direction corrective proposée, sans implémentation

1. **Juger une histoire lisible avant de figer ses accessoires et ses plans.** Conserver un brief utilisateur court ; faire porter au moteur la responsabilité des transitions, des motivations minimales et de la conclusion. La lecture doit fonctionner sans les métadonnées « liaison établie », « rassuré » ou « convaincu ».
2. **Donner à la relecture un critère indépendant du plan.** Vérifier ce que le spectateur apprend et ce qui justifie les réactions, avec la possibilité de remettre en cause un moyen inventé par l'architecte. Recentrer la passe existante avant d'ajouter de nouveaux rôles ou une succession de validations humaines.
3. **Préserver le mécanisme de l'adaptation.** Identifier ce qui fait fonctionner l'humour ou le retournement, puis le recréer dans l'univers choisi. Ne pas transformer le brief minimal en scénario détaillé imposé à l'utilisateur.
4. **Dériver une mise en scène proportionnée.** Garder seulement les gestes, objets et choix de caméra qui rendent l'information compréhensible. Pour cette fin, une réaction clairement attribuée serait préférable à plusieurs visages superposés dans une vitre. Ce n'est pas une interdiction générale des reflets ou une obligation d'un plan unique.
5. **Régler les transitions d'état à leur cause narrative.** Une naissance doit déclencher une réévaluation de l'état grossesse ; un personnage silencieux reste présent si la scène l'exige. Ne pas traiter la conservation comme une règle absolue supérieure à l'événement.
6. **Réduire les répétitions à leur source.** Examiner le contrat Plan → Prompt et la compilation, afin qu'un fait n'ait pas à être reformulé dans chaque champ. Retirer les contraintes devenues contradictoires avant d'en ajouter.
7. **Qualifier avant de dépenser davantage.** Sur une future demande de mise en œuvre, comparer sur les mêmes scènes le naturel, la compréhension des pivots, la continuité, l'identité des locuteurs et la durée complète. Contrôler les passages rendus à risque avant de généraliser l'agrandissement. Comparer ensuite les modèles par rôle, sans promettre qu'un remplacement global résoudra la conception.

Critère d'acceptation utile pour ce cas : une personne découvrant les scènes doit pouvoir expliquer qui trompe qui, pourquoi le fils ne comprend pas, quand la grossesse puis la naissance surviennent, et pourquoi sa preuve finale est absurde. Elle ne devrait pas avoir besoin de lire le résumé du projet.

## Kiwino et suites

Au dernier relevé de cet audit, les cinq tâches de « La mèche de Kiwino » (`story-0be1a86194434102b0f6e0487ed3f487`, épisode `episode-8192f2184dd14b0894c7bbd3c16b0d3a`) sont encore en file d'attente. Aucune vidéo de cette série n'a donc été qualifiée ici. Les fragilités de scénario et de références déjà documentées restent des points à vérifier ; elles ne justifient pas d'annoncer à l'avance la qualité de ses rendus. Ne pas lancer, annuler ou changer ces tâches au titre de cet audit.

L'utilisateur n'autorise actuellement aucune implémentation. Attendre son retour sur Kiwino et une demande explicite avant de transformer cette direction en correctif. Les améliorations proposées sont conservées pour cette discussion.

## Dossier de preuves

Racine : `D:/Code/panelforge/.agent/diagnostics/story-same-species-fundamental-audit-20260928/`.

- `factory.snapshot.json` : sept tâches et leurs paramètres au relevé.
- `La présentation-scene-*-plan.txt`, `La naissance-scene-*-plan.txt` et les fichiers `*-prompt.txt` : décisions de préparation et prompts finaux.
- `clip-01-contact.jpg` à `clip-07-contact.jpg` : captures des sept bruts ; sous-dossiers correspondants pour images individuelles et audio extrait.
- `media-manifest.json` : correspondance des scènes, assets, durées et repères de concaténation.
- `all-clips.json` et `transcription.log` : transcription locale automatique, sans consigne de réécriture ; aucun appel de génération. Les répétitions très brèves à la fin de la transcription ne sont pas interprétées comme preuve d'une répétition réelle.
- `preparation-call-metrics.json` : quatorze appels de préparation avec modèles, temps et usages déclarés.
- `kiwino-final-status.json` : statut des cinq tâches au dernier relevé.
- Source antérieure : `.agent/diagnostics/download34-story-2026-09-28/audio.json` ; rapport précédent : `story-two-series-quality-performance-audit-2026-09-28.md`.

Traces d'écriture représentatives : `llm-ae731fc4c783434989ab5ce485e6f9f4` (composition acceptée), `llm-2ce1d55cab9245738027c1f161a3ada8` (première unité). Dernière préparation : session `prompt-8775612e2029447e820dec5548c83325`, appel final `llm-426e266d4007468ab247c1e3fdbbd7b1`, projet `h3-render-4fa6869987c449e3a03e6f3f17dc2f38`, brut `asset-e377ab69c8d548f3988dea973310761b`.

Points de code consultés en lecture seule dans le checkout actif `D:/Code/panelforge-krea2-flux` : `application/story_workflow.py`, `domain/story_direction.py`, `application/classic_cinematic.py` et le compilateur commun. Ces références servent à expliquer le comportement observé ; aucun patch n'est inclus dans ce document.
