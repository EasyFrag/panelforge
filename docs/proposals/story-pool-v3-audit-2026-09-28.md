# Audit v3 — deuxième run : « La piscine des regards »

## Périmètre

Histoire `story-c4abdea16c2c4aac9b39c0d2ab320b72`, épisode `episode-ddad54a04a624bb2abe8cc7066f6d9f8`. Créée le 28 septembre 2026 à 08:16 UTC, écriture terminée à 08:27 UTC. Cinq clips de dix secondes, adaptation en univers Fruits / animation 3D, profil social, dialogues, fin ouverte. La seule réplique formellement protégée est « Abonne-toi pour la suite. ».

Édition v3 effective, même fingerprint que « La présentation » : `babe2b1ef0fc06d50a23eaa86b26af0fc05bd9b80fe4e72ec2c55734416d8e49`. Trois appels acceptés, zéro réparation, durée cumulée 706 422 ms (11 min 46 s). Aucune boucle ou interruption narrative constatée sur ce run.

Scénario, plan, relecture, registre visuel, prompts et six références sélectionnées examinés. Les références ont évolué pendant l’audit : l’utilisateur a sélectionné une nouvelle Mangue, incluse dans la seconde planche. Une septième référence, Cerisetto trempé, n’avait pas encore d’image sélectionnée lors de la dernière lecture. Les cinq scènes ne comportaient aucune préparation vidéo ; aucune voix ni animation n’a donc été évaluée. Pas de génération ni modification du run effectuée pour cet audit.

## Verdict

L’adaptation raconte bien le sujet demandé, avec une progression plus lisible que le premier run. La finition des images est propre, mais le respect des tenues et l’homogénéité de l’univers fruitier sont insuffisants. Les points prioritaires sont le maillot de Banana, la cohérence des personnages et le cadrage final. La densité de la scène 3 est un point de rythme, pas un échec de génération démontré.

Ce run part d’un récit détaillé, tandis que « La présentation » partait d’un brief ouvert. Sa meilleure fidélité ne constitue pas à elle seule une mesure de progrès de la v3 ; aucune correction n’a été appliquée entre les deux audits.

## Écriture : ce qui est réussi

- Les événements sont réellement joués : vantardise, tentative d’échange de numéro, interruption, reproche, prétexte de protection, départ pour les frites, rendez-vous du soir, dépôt des barquettes puis poussée, accusation de jalousie, départ de Banana et appel final.
- Aucun « wesh » dans les dialogues. Le ton reste familier avec « Yo », « gars », « T’as », sans reproduire le tic de la vidéo source.
- « Abonne-toi pour la suite. » est présente exactement, dite par Mangue avec une indication de regard vers le public. L’identifiant de réplique d’auteur est conservé. C’est un succès concret du mécanisme de répliques protégées à ce stade textuel.
- Le rendez-vous est audible : « 8h ce soir, c’est noté ? Je passe te chercher. » Il ne repose pas uniquement sur une intention cachée dans le plan.
- Les barquettes sont déposées avant la poussée, ce qui rend les gestes réalisables.

## Écriture : points à améliorer

### Scène 3 trop bavarde pour son rôle

Elle concentre 40 mots, quatre tours de parole et le départ vers le stand. Le diagnostic estime 10,3 secondes pour dix disponibles. Ce léger dépassement reste indicatif ; surtout, la répétition de la justification ralentit la montée vers la poussée.

« Je te protège, chérie. Des mecs comme ça, ils veulent juste ton numéro » fournit une mauvaise raison de le chasser : il vient précisément de demander ce numéro. Cela peut caractériser une excuse transparente, mais manque de mordant. « Non, t’as besoin d’une gardienne » explicite lourdement le contrôle de Mangue. Un échange plus court peut préserver ce ressort sans nouveau paragraphe de consignes.

Les autres scènes comptent respectivement 24, 26, 17 et 26 mots. La dernière doit aussi laisser le temps au départ, au murmure et au regard caméra : le jeu et les respirations seront à écouter, sans conclure dès maintenant à une surcharge.

### Solitude finale et sortie de l’eau à préciser

La scène 5 conserve Cerisetto dans le bassin, mais annonce Mangue « seule ». La relecture identifie correctement ce point. Il peut rester présent au début de la scène puis sortir du cadre lorsque le plan se resserre sur Mangue et les deux barquettes. Le retirer de toute la scène uniquement parce qu’il ne parle pas serait une mauvaise correction.

Banana commence dans l’eau puis finit par s’éloigner à pied sur les dalles. Sa sortie de l’eau n’est pas explicitement située. La fixer à une transition existante éviterait que chaque clip invente sa position.

### Mélange de langues encore présent dans les données françaises

Le contrat contient « she loses the spotlight » ; le registre visuel contient « Elle joue les stars and wants to remain the centre of attention », « with a phone raised » et « silhouette ronde and souriante ». Les dialogues restent français. Ce problème concerne la propreté et la stabilité des descriptions intermédiaires ; il ne remet pas en cause l’usage de l’anglais dans les prompts image quand ce choix est intentionnel.

## Références visuelles

### Défaut confirmé : maillot de bain devenu maillot de sport

Le brief et le contexte piscine demandent Banana en maillot jaune. Le prompt final de sa référence indique « matching yellow jersey », puis « fabric weave of the jersey ». L’image sélectionnée montre effectivement un haut de sport jaune à bordures sombres et un petit motif de marque. Il ne s’agit pas seulement d’une mauvaise exécution du moteur d’image : le changement de sens est déjà présent dans le prompt.

Correction ciblée à prévoir : conserver le sens « maillot de bain » jusqu’au prompt image, avec une tenue précise conforme à l’intention. Un rappel générique supplémentaire ne suffit pas à expliquer comment cette information sera préservée.

### Univers fruitier visuellement hétérogène

La nouvelle Mangue sélectionnée conserve le maillot bleu et une apparence orange feuillue ; Banana est immédiatement identifiable par sa tête de banane. Kiwito ressemble davantage à un personnage vert aux traits d’oiseau, avec un bec et une crête, qu’à un kiwi-fruit. Cerisetto ressemble surtout à un humain musclé rosé, sans silhouette de cerise lisible.

Ce jugement porte sur la lisibilité de l’espèce et la cohérence du casting, pas sur une obligation de morphologie unique : les silhouettes peuvent varier. Les couleurs, le rendu 3D et les lumières restent globalement compatibles. Les portraits sont donc propres séparément mais moins convaincants comme ensemble « Fruits ».

Banana est également cadrée au buste, contrairement aux références en pied des trois autres personnages. Cela laisse davantage de tenue et de morphologie à inventer lors des scènes de déplacement.

### Description d’action injectée dans une référence d’identité

Le prompt de Kiwito demande de s’approcher d’un autre personnage, Banana, avec un téléphone levé. Un fragment d’un second personnage apparaît au bord gauche de l’image. Cette indication de scène complique une référence qui devrait avant tout stabiliser Kiwito. Retirer l’interaction de ce prompt serait une simplification concrète, pas un ajout de consignes.

### Décor et accessoires

La piscine et le stand de frites sont lisibles ; les deux portions sont présentes dans l’image d’objet. Le décor est cadré assez serré autour d’un angle du bassin : la position de trois personnages et la trajectoire de la poussée restent à établir lors de la mise en scène.

Contrairement au premier run, les barquettes n’ont qu’une seule référence malgré plusieurs états de détenteur. C’est le résultat attendu. Le registre contient encore des états redondants, mais ils n’ont pas produit ici deux images supplémentaires de frites.

La variante Cerisetto « trempé, dans l’eau » peut correspondre à une vraie évolution visuelle, contrairement à un simple déplacement de tasse. Son utilité et sa fidélité restent à examiner quand l’image sera disponible. Distinguer texture mouillée et position dans le bassin évitera de figer tout le décor dans une référence de personnage.

## Présence et qualité de la relecture

- Kiwito est visible en scène 2 puis absent en scène 3. « Kiwito a disparu du bord » mentionne explicitement sa sortie : son absence du casting de la scène 3 est correcte.
- Le diagnostic automatique émet malgré tout un avertissement `visible_cast_check`. Le lecteur comprend que Kiwito n’est plus visible, mais cet avertissement reste dans la liste finale des problèmes. C’est du bruit à réduire ; il ne faut pas ajouter Kiwito aux images pour faire disparaître l’alerte.
- Cerisetto reste dans le casting de la scène 5 sans réplique : présence et parole sont bien séparées. La question restante est celle du cadrage au cours du clip, pas seulement de la liste globale des personnages.
- Le lecteur relève la solitude finale ambiguë et le rythme du clip 3 : deux observations pertinentes. Le même problème de durée apparaît cependant deux fois, comme `speech_estimate` et `clip_load`.
- Le lecteur narratif intervient avant les prompts et rendus de références : il ne pouvait pas voir la transformation ultérieure de « maillot » en « jersey ». Ce contrôle appartient à la préparation visuelle.

## Améliorations cumulées à conserver, sans implémentation

| Priorité | Amélioration | Preuve disponible |
| --- | --- | --- |
| 1 | Vérifier les faits et relations effectivement perceptibles, ainsi que les répliques compréhensibles | « Ma copine » absent et « se fait la miette » dans le premier run ; scène 3 de la piscine perfectible |
| 1 | Préserver les caractéristiques concrètes du brief jusqu’aux images | Maillot de bain traduit en jersey ; Cerisetto peu identifiable comme fruit |
| 1 | Séparer identité visuelle, détenteur, position et action dans les références | Clés/tasse du premier run ; interaction avec Banana dans la référence de Kiwito |
| 1 | Gérer présence silencieuse, sortie de champ et moments du clip séparément | Kiwito absent correctement ; Cerisetto silencieux puis solitude finale ambiguë |
| 2 | Réduire les répétitions et le bruit des diagnostics | Double avertissement de durée ; alerte de casting malgré une disparition explicite |
| 2 | Nettoyer le mélange de langues dans les descriptions narratives et visuelles françaises | Défaut retrouvé dans les deux runs |
| 2 | Contrôler le jeu, le débit et les raccords sur les vidéos effectivement produites | Non évaluables dans ces deux audits |

Avant un futur patch : confronter chaque point aux consignes déjà en place, retirer les doublons et réparer les pertes d’information aux étapes concernées. Ne pas transformer les exemples particuliers (copine, maillot, frites) en longues règles générales ajoutées au prompt.

## Preuves locales

- [Références sélectionnées examinées](../../.agent/diagnostics/pool-v3-audit-2026-09-28/references-selected.jpg).
- `selected-reference-assets.json` dans le même dossier conserve les identifiants et prompts du dernier instantané visuel.
- Première planche `references-in-progress.jpg` : état antérieur, avec la première image de Mangue non retenue au moment de la seconde lecture.
- Traces : `llm-983c2debd6f64bfc810a7966c3fe2d27`, `llm-aa4e44baddfa4232b763aa072c6bfb25`, `llm-5c95834080a24b78bfede636e9d39ae8` sous `workspace/video_llm_traces/calls/`.
- [Audit du premier run](story-girlfriend-v3-audit-2026-09-28.md).

Aucun code, scénario, référence source, validation utilisateur ou état de fabrication modifié. Seuls les documents et instantanés d’audit ont été écrits. Aucun appel LLM, test, génération ni redémarrage déclenché.
