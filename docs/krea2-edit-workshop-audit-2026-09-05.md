# KREA2 Edit : atelier d’états successifs pour des travaux

Audit du code et lecture des métadonnées locales le 2026-09-05. Discussion de
conception, aucune implémentation du mode, aucun test, appel LLM/rendu ou
redémarrage. Aucun jugement de qualité des images sans comparaison visuelle.

## Ce qui existe

- Un projet contient une chaîne d’étapes avec parents explicites. Chaque étape
  conserve sa source, ses révisions de prompt et ses essais.
- Le writer reçoit la source réelle `STAGE SOURCE`, le prompt courant éditable,
  la nouvelle instruction et éventuellement un essai `GENERATED FEEDBACK`.
  Les anciennes révisions sont enregistrées et affichables, mais ne sont pas
  transmises comme conversation. Sa réponse est uniquement le prompt final.
- Chaque essai édite la source de l’étape, même si un autre résultat sert de
  feedback. `Valider et continuer` adopte exactement le PNG choisi comme source
  de l’étape suivante, avec son prompt, modèle, LoRA, ratio, résolution et seed.
- Les étapes validées sont consultables mais ne permettent pas de repartir
  dans une autre direction depuis l’interface. L’export conserve la chaîne.
- Le workflow `krea2.identity_edit@0.1.0` conditionne réellement le rendu par
  l’image et une LoRA technique fixe ; aucun masque local n’est exposé ni utilisé
  dans le graphe. Une zone inchangée n’est donc pas préservée pixel par pixel
  par un masque ou une recomposition déterministe.

Sources principales : `application/krea2_edit.py` (writer, promotion, rendu),
`domain/krea2_edit.py`, `features/lab/static/krea2-edit-lab.js`, manifeste et
graphe `workflows/image.edit/krea2-identity/0.1.0/`.

Les quatre fiches chantier les plus récemment modifiées lors de la lecture
(spray, chemin/piquets, retrait de marteaux) sont des projets distincts en
étape 1, sans résultat accepté. Cela décrit le stockage actuel, sans permettre
de conclure pourquoi l’utilisateur n’a pas utilisé la promotion.

## Points concrets à améliorer

- Échange conversationnel court en français plus prompt autonome, dans un même
  appel. Conserver les retours récents de l’étape ; en avançant, prendre l’image
  validée et les contraintes utiles comme base, sans réactiver les essais rejetés.
- Rendre visibles les états validés et les variantes de l’étape actuelle dans
  une frise, avec comparaison avant/après et espace de travail stable.
- Garder une validation volontaire, et permettre ultérieurement de créer une
  piste depuis un état validé sans modifier sa suite existante.
- Corriger la transmission des réglages : actuellement `ref_boost` et `steps`
  sont absents des métadonnées du nouvel état. Sans essai dans cette étape,
  `openSource` retombe sur les défauts (2.5 et 10), même si le résultat accepté
  avait d’autres valeurs. Ne pas attribuer cet écart au modèle.
- Décrire dans l’image le résultat visible d’une modification localisée, et
  dans la vidéo les gestes qui la produisent. Conserver cadrage, repères du
  décor et acquis des étapes antérieures. Une consigne de préservation n’est
  pas une garantie technique ; évaluer la dérive sur quelques étapes d’abord.

## Enchaînement vidéo proposé

Images : mur intact → trou brut → trou poncé → piquets posés. Préparer les
états souhaités ; chacun reste révisable au fil des vidéos.

Un clip représente une transformation. Entrées envisagées : état de départ,
état cible, référence d’identité de l’ouvrier. Ces rôles correspondent à la
distinction entre image cible et sujet de référence du
[guide officiel Ref2V](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md).
Ce contrat de prompt ne démontre pas la fidélité réelle du rendu sur ces travaux.

Après chaque clip, comparer sa dernière frame au résultat attendu avant de
l’adopter comme départ du suivant. Si le trou reste incomplet, ne pas passer
automatiquement au ponçage. Si le décor a un peu changé, l’état cible suivant
peut être réédité depuis cette frame réelle ; une dérive inacceptable justifie
de reprendre le clip au lieu de l’accumuler.

Le bouton existant `Repartir de la dernière frame`, commun aux essais H3/Ref2V,
ouvre actuellement **H3 Base** avec une première image, pas une continuation
Ref2V conservant ouvrier et prochain état. Les passerelles Edit → Ref2V et
dernière frame vidéo → étape Edit restent à concevoir.

Premier essai proposé à l’utilisateur : une transformation localisée, puis un
deuxième clip depuis la fin réelle du premier. Observer décor, état du matériau,
identité de l’ouvrier et causalité outil/matière avant d’étendre la chaîne.

## Périmètre affiné après discussion

L’utilisateur met explicitement la vidéo de côté : le prochain travail doit
d’abord permettre de préparer confortablement les images des étapes.

Son impression de mémoire correspond bien à une continuité via le prompt
courant et les images. L’historique instruction/prompt est actuellement caché
dans le panneau replié « Échange de modification » ; ce n’est pas une conversation
transmise au writer. Proposition : rendre les messages visibles, garder le
prompt détaillé repliable et conserver un contexte récent propre à l’étape.
Les étapes antérieures restent consultables ; la nouvelle étape part de l’image
et du prompt validés, sans réinjecter automatiquement les anciennes corrections.

Comparateur demandé : deux images superposées, séparation verticale déplaçable
horizontalement pour révéler l’avant/l’après. Proposition : source de l’étape
à gauche et essai sélectionné à droite par défaut ; possibilité de choisir un
ancien essai pour comparer deux variantes. Même échelle, proportions conservées,
pas de déformation ou recalage automatique qui masquerait la dérive du décor.
Poignée manipulable à la souris, au toucher et au clavier ; le suivi au survol
peut rester une option, pour ne pas déplacer la comparaison involontairement.
Un seul état actif et sa conversation, la frise pour consulter les états validés.
Discussion uniquement, ni comparateur ni nouveau chat implémentés.

Précision utilisateur : les images de la frise doivent être cliquables pour
zoomer. Proposition de distinguer le clic miniature (agrandissement) de l'action
qui ouvre l'étape, afin de pouvoir comparer sans changer l'atelier actif.
