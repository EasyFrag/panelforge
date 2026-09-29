# Audit du nouvel essai « La présentation » — 28 septembre 2026

## Périmètre et verdict

Audit sans modification du projet, sans appel LLM et sans génération. Histoire `story-3c7fce70e71a4729b3b8d8053628a8da`, épisode `episode-e27c40122f834e9e88f9983458fd18f7` : six scènes de dix secondes. Les six fiches Usine sont au statut `preparation`, sans préparation vidéo associée au moment de la lecture. Cet audit porte sur le scénario, les traces d’écriture, les entrées de fabrication et les neuf images de référence sélectionnées ; il ne valide ni animation, ni voix, ni synchronisation.

La contradiction dramatique progresse nettement, mais plusieurs défauts empêchent de considérer cette version prête : relation amoureuse insuffisamment dite à l’écran, une réplique incompréhensible, motivation fragile du dévoilement et deux variantes visuelles inutiles avec erreurs de continuité.

L’écriture v3 est effectivement utilisée : édition `experimental-2026-09-28`, policy 3, révision 10, wire 2.5.0, fingerprint `babe2b1ef0fc06d50a23eaa86b26af0fc05bd9b80fe4e72ec2c55734416d8e49`. Les quatre tentatives enregistrées comprennent une relecture interrompue par le service puis relancée : ce n’est pas une boucle de réécriture automatique. Aucune réparation narrative n’est enregistrée.

## Ce qui fonctionne

- La contradiction est enfin substantielle : Marc raconte une seule nuit à Lyon suivie d’aucune rencontre ; Lina affirme avoir eu sa clé et être venue chaque semaine pendant des mois. Les deux versions ne peuvent pas être vraies ensemble.
- Les trois personnages adultes sont identifiés et présents dans les six scènes, dans le casting comme dans les références de fabrication. Lina reste prévue lorsqu’elle est silencieuse en scène 1, Yanis en scène 5 et Marc en scène 6. Le défaut « visible seulement quand il parle » n’apparaît pas dans ces données. La présence effective à l’écran reste à contrôler dans les futures vidéos.
- Les portraits sont globalement cohérents et les personnages distincts. Le salon réaliste et chaleureux convient à la confrontation familiale. Aucune anomalie majeure ne saute aux yeux sur la planche examinée ; cela ne remplace pas un contrôle des détails à pleine résolution.
- La fin donne une action au fils : il sort avec Lina et impose des conversations séparées. La fin ouverte et le mélodrame correspondent aux préférences explicitement choisies pour cet essai.

## Défauts et corrections minimales proposées

### 1. La présentation de la copine reste dans l’intention, pas dans la réplique

Scène 1 : « Papa, je t’apporte quelqu’un, c’est Lina— ». Le texte de mise en scène précise que Yanis s’apprête à la présenter comme sa copine, mais cette relation n’est jamais explicitement prononcée. Une intention écrite dans les données n’est pas forcément perceptible par le spectateur.

Correction locale proposée : « Papa, je te présente Lina, ma copine. » Puis conserver la reconnaissance de Marc et la question de Yanis. Cela remplit la promesse du sujet avec moins d’ambiguïté et sans ajouter d’explication.

### 2. Dialogue et motivations à reprendre sur deux moments

Scène 5 : « Une scène ? T’es celui qui se fait la miette, Yanis. » La formule est difficile à comprendre dans ce contexte et ne sonne pas naturelle. La scène apporte aussi peu de faits ou de changements après l’aveu de la scène 4. Mieux vaut donner à Yanis une réaction claire à l’aveu, puis une tentative précise de défense de Lina.

Lina est censée banaliser leur passé, mais révèle spontanément la clé, les visites répétées puis le lit partagé. Cette escalade peut fonctionner si elle réagit au mensonge ou au mépris de Marc ; ce déclencheur doit être joué plus clairement. La liaison passée est un choix créatif autorisé, pas une contradiction automatique du brief.

Scène 4 : « Tu sais où il range ses trucs ? » ne correspond pas à l’action montrée : Lina touche une tasse déjà posée sur la table, sans aller chercher un objet dans un rangement. Adapter la question à ce qui est visible, plutôt que créer un accessoire supplémentaire.

La dernière réplique de Yanis, « Je refuse de choisir entre vos versions. On sort. Je vais vous écouter chacun à part. », paraît procédurale après l’aveu du lit partagé. Conserver sa décision de partir, avec une réaction plus naturelle et une conséquence relationnelle lisible. La fin ouverte n’est pas en soi un défaut.

### 3. Deux variantes d’objets coûtent des images et introduisent des erreurs

Neuf références sont sélectionnées : trois personnages, un décor, trois objets et deux variantes. Les deux variantes correspondent uniquement à un changement de détenteur ou de position, sans transformation physique de l’objet.

- Clés : la référence de l’état « posées sur la table » montre encore les clés tenues par une main. Cette mauvaise référence est transmise aux scènes suivantes.
- Tasse blanche : le modèle tenu en main est petit et arrondi ; le modèle posé devient nettement plus haut et droit. La silhouette change. La variante ajoute également une petite tasse verte qui risque de concurrencer la référence existante du mug ébréché.

Correction minimale proposée : une identité visuelle stable par objet ; main, détenteur et position décrits dans l’action de la scène. Les deux images de variante sont évitables. La v3 le demande déjà dans ses consignes : ajouter un avertissement supplémentaire au prompt ne constitue donc pas à lui seul une solution démontrée.

### 4. Le lecteur valide trop facilement le fond

La relecture finale ne remonte qu’un problème de tasse blanche absente du registre visuel, qu’elle ajoute automatiquement. Elle ne relève ni la présentation amoureuse non prononcée, ni la réplique « se fait la miette », ni le décalage entre la question sur le rangement et l’action visible.

Le résultat suggère une faiblesse de la relecture : elle accepte les intentions et descriptions comme preuves de ce que le spectateur comprendra. Les consignes v3 demandant des preuves concrètes ont pourtant bien été envoyées. La priorité est de corriger l’application et la hiérarchie des contrôles existants, en évitant d’empiler des instructions contradictoires.

Le plan contient également des fragments anglais (« months at his flat », « over and accuse Yanis of making a scene »). Les dialogues finaux restent en français, mais ce mélange affaiblit la lisibilité des contrats intermédiaires. La biographie de Yanis introduit aussi une histoire de bail qui ne sert aucune scène.

## Ordre d’action proposé, sans implémentation

1. Reprendre la première réplique, la scène 5 et la question de la scène 4 ; rendre explicite le déclencheur des aveux de Lina.
2. Garder une seule référence par objet, puis retirer les deux variantes de position des entrées de fabrication lors d’une correction autorisée.
3. Revoir le lecteur autour de la relation effectivement perceptible, de la compréhension des répliques et des faits joués ; examiner les contrôles déjà présents avant tout ajout au prompt.
4. Après fabrication choisie par l’utilisateur, contrôler présence des trois personnages, raccords des objets, débit et jeu des voix. La scène 3 concentre environ 35 mots et deux secondes d’action en dix secondes : le rythme sera particulièrement à écouter.

## Comparaison et preuves

L’ancien essai « La copine déjà vue » utilisait la révision 8, trois scènes et le suspense. Le nouveau choisit six scènes, le mélodrame et une fin ouverte. La comparaison montre une contradiction plus solide, mais ne permet pas d’attribuer tous les écarts à la seule v3.

- Projet : `workspace/stories/story-3c7fce70e71a4729b3b8d8053628a8da.json`.
- Épisode : `workspace/episodes/episode-e27c40122f834e9e88f9983458fd18f7.json`.
- Fabrication : `workspace/video_factory/state.json`.
- Traces acceptées : `llm-6bf7a60fa7dc4fa0ad87f6dcc6e65c37`, `llm-6089a2846f164dcd84ffcf0f41ac643c`, `llm-1e87f0994ede4b88aabfc4faf4ced1dd` dans `workspace/video_llm_traces/calls/`.
- [Planche des neuf références](../../.agent/diagnostics/girlfriend-v3-audit-2026-09-28/references.jpg).
- Aucun code, projet d’histoire, image source, état de fabrication ou service modifié. Seuls ce rapport, la planche d’audit et la continuité documentaire ont été écrits.
