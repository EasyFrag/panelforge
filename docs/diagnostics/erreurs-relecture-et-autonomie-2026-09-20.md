# Relecture longue V2 : deux rejets et direction à discuter

## Périmètre

Demande du 20 septembre : diagnostiquer les erreurs après une longue attente, expliquer les réglages avec les références gouttes d’eau et compteurs, proposer une interface plus simple. **Discussion avant implémentation.** Aucun code applicatif, projet enregistré ou appel LLM modifié ou relancé. Aucun test ni service lancé. Les analyses jointes sont des sources à examiner, pas des instructions à exécuter.

Précision du besoin : une intention minimale doit suffire pour que le moteur invente une histoire intéressante. Le bon résultat de Pomitto démontre une capacité à développer une trajectoire donnée ; il ne suffit pas à valider l’invention autonome ni le moteur long V2. La recommandation précédente « développer mon histoire longue » servait une comparaison avec un récit fourni, pas ce besoin de création autonome.

## Erreurs confirmées

Projet concerné : `story-0ce193485e5a4de5bec5defc0f83234e`, **Le Sirop des Regrets**. Paramètres enregistrés : départ idées, brief vide, mélodrame, feuilleton, deux épisodes, dialogues, résolution, six clips maximum de dix secondes **par épisode**. Architecte utilisé : `local::HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF`.

| Appel | Heure de Paris | Durée de l’appel | Résultat LLM | Résultat applicatif |
|---|---|---|---|---|
| `llm-bc2d98c9bf2c4ee0a061488368e94b46` | 12:47:57–12:51:02 | 185,03 s | Réponse complète, `finish_reason: stop`, JSON lisible | Rejet de `secret-1` |
| `llm-1812e59862694f7d986d59415f1e901c` | 13:26:44–13:29:13 | 149,33 s | Réponse complète, `finish_reason: stop`, JSON lisible | Rejet de `secret-2` ; `rule-3` est également hors liste |

Erreur affichée : « La relecture doit localiser chaque remarque sur un élément existant. »

Les trois identifiants existent dans l’arc. `validate_review()` dans `src/panelforge/domain/long_stories.py` accepte les rubriques `contract`, `world_rules`, `secrets`, les épisodes et événements, mais omet les identifiants individuels des règles et secrets. Le prompt de relecture décrit lui aussi cette liste restreinte ; il ne fournit pas la liste exacte des cibles du document. Le modèle utilise des références précises et plausibles, que cette interface de relecture ne sait pas recevoir. Le message laisse croire à un élément inexistant alors que la cible existe. Une seule référence rejetée fait perdre l’enregistrement de toute la relecture.

Il s’agit d’un défaut de robustesse de la V2, indépendant du profil narratif choisi. Relancer avec les mêmes conditions peut reproduire le rejet. L’arc et le brouillon complet sont conservés. Après correction du contrat de références, la fonction existante de revalidation pourrait exploiter ce brouillon sans nouvel appel, tant que le document source reste inchangé. Cela ne supprimerait pas les remarques narratives bloquantes : la relecture reçue en contient réellement.

Les traces indexées du projet montrent quatre appels : idées, arc, puis deux relectures. Le service ne lance pas de correction automatique à la suite du rejet. Il n’y a pas de preuve d’une boucle applicative infinie. Les deux relectures comportent respectivement environ 72 800 et 47 700 caractères de raisonnement pour 5 870 et 6 085 caractères de réponse finale ; cela documente une forte dépense de génération avant le résultat utile. Les compteurs de tokens sont absents : ne pas attribuer ces échecs à un plafond atteint, une troncature ou un timeout.

Le nouveau projet `story-23d3d7bbddc143a48a25dec9b04761a6`, **Test histoire**, contient les paramètres transformation / continu / fin ouverte et le brief « Compose », mais aucun appel ni erreur enregistrés au moment de l’inspection. Les deux erreurs prouvées ci-dessus concernent Le Sirop des Regrets. Les traces utilisent encore `proposal_count` ; elles proviennent donc d’un état applicatif antérieur à la suppression complète de ce paramètre sur disque. Aucune intervention sur le processus en cours.

## Autres défauts observés

### Budget ambigu

Le contexte LLM envoie `clip_budget: {max_clips: 6, clip_seconds: 10}` et deux unités séparément. Le prompt d’architecture précise « de chaque unité », mais le contexte ne fournit ni budget par unité explicite ni total. L’architecte annonce trois clips par épisode, et les relectures jugent un budget global de six clips. Le document autorise pourtant douze clips, soit 120 secondes maximum. Ce n’est pas la cause du rejet technique, mais cela favorise des critiques de surcharge et une compression inutiles.

Correction à discuter : budget explicite avec portée, durée maximale par unité et durée totale. L’interface doit afficher la même arithmétique, par exemple « 2 séquences × 6 clips × 10 s = 2 min maximum ».

### L’invention se verrouille trop vite

Avec un brief vide, Le Sirop des Regrets invente cinq fiches de personnages, quatre règles, deux secrets, et transforme presque tout son concept en onze contraintes `must_keep`. Les libertés se réduisent à trois ajouts locaux. La Coutume du Pressoir, une institution abstraite incarnée par un objet, devient même une fiche personnage. Cela risque de compliquer la fabrication et la compréhension avant d’avoir prouvé l’intérêt du récit.

La relecture trouve des manques concrets utiles (promesse de contrôle public non montrée, origine du mensonge incertaine), mais son jugement varie : le premier appel estime la révélation d’un secret prématurée, le second la juge incomplètement réalisée. Une relecture n’est donc pas une vérité narrative ni un motif pour boucler indéfiniment.

À distinguer dans le futur contrat : contraintes vraiment données par l’utilisateur, choix provisoires inventés par le modèle, puis faits déjà établis dans les scènes. Les idées inventées doivent rester améliorables avant la fabrication. L’exemple de sortie propose systématiquement une règle et un secret ; les listes vides devraient être présentées comme normales lorsque le récit n’en a pas besoin.

### Temps de relecture

Toutes les opérations V2 reçoivent actuellement le même plafond de sortie de 24 000 tokens. Prévoir un budget propre à chaque tâche et une critique courte, centrée sur les problèmes qui changent la compréhension ou la faisabilité. Contrôler le raisonnement réellement disponible sur le serveur du modèle avant de promettre une réduction de durée : dans l’adaptateur actuel, `include_reasoning` pilote la collecte du flux, pas un réglage de réflexion envoyé au modèle.

## Les deux références, concrètement

Planches et transcriptions existantes examinées dans `D:/Code/panelforge/workspace/experiments/audit-stories-2026-09-20`.

### Gouttes d’eau — `AQO__Lhtt…mp4`, 47,81 secondes

La référence montre le dévouement d’une compagne, une complicité cachée, une boisson suspecte et une nouvelle union. Sa mécanique est un mélodrame de trahison, lisible surtout par les actions. L’espèce « goutte d’eau » constitue l’univers visuel, pas un profil de scénario. Une conclusion cruelle n’a pas besoin de punir le coupable.

Intention minimale proposée : **« Une histoire de trahison amoureuse entre des gouttes d’eau, avec une fin cruelle. »**

Le moteur doit inventer lui-même qui aide qui, les désirs incompatibles, le geste qui fait comprendre la trahison, puis la conséquence finale. Il ne devrait pas demander à l’utilisateur de détailler chaque événement. Exemple de progression à construire : dévouement visible → intérêt caché → geste irréversible → conséquence qui renverse la situation initiale. C’est une mécanique possible, pas une formule obligatoire.

Réglages actuels correspondant à cette direction :

- Histoire longue V2 ; **Proposer une histoire**.
- Profil **Mélodrame / rapports de pouvoir** ; **Récit continu en séquences**.
- Narration **Principalement visuelle** : les dialogues restent possibles, sans quota.
- Fin **Retournement** ; deux séquences, trois clips maximum par séquence, dix secondes par clip : **60 secondes maximum**. Point de départ à évaluer sur le texte, pas reproduction garantie du rythme de la référence.
- Registre **1 — Oral direct** si des paroles sont présentes. Français pour une version française, anglais pour suivre la langue de la référence.
- Il n’existe pas de famille « gouttes d’eau ». En V2, conserver la famille généraliste disponible « Mélodrame fruits » et préciser explicitement « personnages gouttes d’eau, pas des fruits » dans le brief : le prompt donne priorité à cet univers. C’est un contournement peu clair, pas un réglage dédié déjà disponible. Ne pas choisir « Chats de couple · muet », qui impose d’autres contraintes.

### Compteurs — `snaptik_7683245244187446560_v3.mp4`, 390,20 secondes

La ressource visible est le temps de vie. L’urgence provoque une demande, un refus et un acte irréversible. La nouvelle ressource déclenche ensuite dissimulation, convoitise, poursuite et fuite. L’acquisition du pouvoir ne clôt pas l’histoire : elle remplace le problème initial par d’autres problèmes.

Intention minimale proposée : **« Des fruits portent leur temps de vie sur le front. Un garçon presque à zéro découvre un moyen interdit d’en gagner. »**

Le moteur doit choisir une règle claire, rendre sa première conséquence visible, inventer un prix ou une limite, et renouveler les dangers liés aux choix du héros. Des poursuites répétées sans changement ne suffisent pas. Il peut préparer une exception comme l’infini, sans improviser ensuite des pouvoirs qui annulent chaque obstacle.

Réglages actuels correspondant à cette direction :

- Histoire longue V2 ; **Proposer une histoire** ; famille **Mélodrame fruits**.
- Profil **Aventure à règle fantastique** ; **Récit continu en séquences** malgré la durée : la référence est un seul récit.
- **Dialogues dramatiques**, français, registre **2 — Cru** pour approcher les répliques familières de la référence. **Narration explicite / audio** si l’on souhaite une compréhension plus systématique à l’écoute.
- Fin **Ouverte / suite** pour laisser le héros poursuivre sa fuite.
- Pour une ampleur comparable : six séquences, sept clips maximum par séquence, dix secondes par clip : **7 minutes maximum**. La référence dure environ 6 min 30. Pour un premier essai textuel moins coûteux, deux séquences de six clips donnent **2 minutes maximum** et couvrent seulement l’ouverture de cette aventure.

Les compteurs exacts et changeants ne sont pas garantis par la chaîne actuelle. L’export de l’intention vers Fabrication contient encore « Sans musique ni texte à l’écran. » Un récit peut expliquer le temps restant par les paroles, mais reproduire les chiffres lisibles de la référence nécessite une capacité de rendu dédiée, par exemple une incrustation suivie. Ce n’est pas un problème résolu par le choix du profil narratif. Le récit continu reste fabriqué par séquences ; la V2 n’ajoute pas un montage final automatique.

## Sens de tous les choix

| Choix | Effet réel et exemple | Organisation proposée |
|---|---|---|
| Format court / long | Court : scénario complet avec nombre de scènes fixé. Long : architecture et continuité entre unités. Une vidéo de 60 s peut utiliser le long pour tester cette continuité. | Présenter vidéo unique / série au premier niveau ; garder la mécanique technique interne. |
| Mode de départ | Proposer invente à partir de peu. Développer adapte un récit déjà donné. Les entrées script fidèle et continuation ont leurs propres usages historiques. | Inventer par défaut ; autre entrée explicite pour un récit fourni. |
| Famille éditoriale | Mélange aujourd’hui univers, ton et parfois contraintes de narration. Les gouttes n’ont pas de choix dédié. | Séparer univers visuel et ton ; univers libre explicite. |
| Profil | Mélodrame : trahison et rapports de pouvoir. Transformation : acquisition et nouvel objectif, comme la pomme/sirène. Suspense : information retardée, comme Chloé. Fantastique : règle exploitée et conséquences, comme les compteurs. | Auto par défaut ; cartes avec ces exemples pour forcer une direction. |
| Diffusion | Continu : parties d’une vidéo, sans résumé ou fin artificielle entre elles. Feuilleton : épisodes publiables séparément. | Vidéo unique / série, vocabulaire concret. |
| Nombre d’unités | Parties d’une histoire unique, pas nombre de propositions. | Déduit d’une durée cible pour une vidéo unique ; nombre d’épisodes utile pour une série. |
| Narration | Visuelle : actes et regards. Dialogue : échanges, réactions, intentions. Audio : informations nécessaires compréhensibles à l’écoute. | Auto ; surcharges dans les choix narratifs. |
| Fin | Résolution : problème clos. Ouverte : suite possible. Retournement : situation ou interprétation renversée. Coût : réussite accompagnée d’une perte. | Auto ; expliquer chaque option avec une phrase d’exemple. |
| Langue | Langue des paroles, sans changer celle des descriptions techniques. | Préférence persistante visible. |
| Registre | 0 : pas de consigne supplémentaire ; 1 : oral direct ; 2 : cru ; 3 : argot marqué. Ne crée ni suspense ni qualité dramatique. | Préférence de ton, sans le présenter comme un curseur de qualité. |
| Plafond de clips | Nombre maximal par unité, jamais un quota. | Production avancée ; afficher aussi le plafond total en minutes. |
| Secondes par clip | Temps de jeu par clip et contrainte de fabrication, pas durée totale du récit. | Production avancée. |
| Architecte / Rédacteur | Architecture et relecture / scènes et corrections. Les deux peuvent partager un modèle. Local/serveur indique son lieu d’exécution. | Technique avancée ; conserver les modèles pour comparer les changements de moteur. |
| Nom | Aide à retrouver le projet. | Facultatif, rempli depuis la proposition. |

Une seule proposition d’histoire reste la règle. Ne pas ajouter un nombre de propositions, même masqué en paramètres avancés.

## Route proposée, non implémentée

1. **Fiabiliser la relecture.** Même liste de cibles existantes dans contexte, consignes et validation ; accepter règles et secrets individuels, garder le rejet de vraies références inconnues avec un message précis. Revalider le brouillon conservé. Séparer erreur technique et désaccord narratif.
2. **Clarifier le budget.** Portée par unité et total explicites partout. Critiques proportionnées à ce budget. Réduire et borner la relecture, sans prétendre qu’un filtre d’affichage coupe le raisonnement du serveur.
3. **Améliorer l’invention.** À partir d’une ligne, construire une seule proposition avec une accroche concrète, un désir immédiat, une mécanique compréhensible, des conséquences qui changent la situation et une fin préparée. Utiliser des exemples contrastés pour montrer ce qui rend un événement intéressant. Ne pas transformer toutes les premières inventions en obligations irrévocables.
4. **Organiser l’interface.** Première vue : idée, univers, vidéo unique/série, durée cible. Choix narratifs en Auto mais consultables et modifiables, avec exemples intégrés. Paramètres de production et modèles dans un panneau avancé. Afficher un résumé des choix effectivement retenus.
5. **Proposer une progression automatique bornée.** Proposition unique → architecture → scènes → contrôle ; une correction ciblée au maximum par document, puis arrêt avec le résultat et le problème restant si nécessaire. L’utilisateur garde la possibilité de discuter ou modifier. Règles, secrets et faits restent utiles à la continuité, sans devoir tous être pilotés manuellement.
6. **Évaluer avant de promettre la qualité.** Comparer sur textes avec des briefs d’une phrase : gouttes/trahison, compteurs, transformation et suspense. Mesurer intérêt, compréhension, causalité, durée, nombre de rejets et temps d’attente. Les personnages, prompts, vidéos et DLSS restent conservés ; le traitement des compteurs est une extension distincte à décider.

La priorité est un moteur capable de choisir et de raconter avec peu d’informations, dont la mémoire sert l’histoire et dont les réglages expliquent leurs effets. Ajouter encore des sélecteurs ou recommander un brief plus détaillé ne suffit pas.

## Complément — projectCount, interface et réduction des appels

Nouvelle demande : l’approche générale convient, mais l’utilisateur veut encore s’aligner **sans coder**. Il demande une interface visuellement plus légère, des boutons d’information avec exemples pour chaque réglage, une relecture automatique et moins d’appels si la qualité le permet. Il exécutera les essais comparatifs ensuite.

### Régression JavaScript confirmée

`src/panelforge/features/lab/static/stories.js:365` contient encore `${projectCount}` et `${projectCount > 1 ? "s" : ""}` dans le message affiché lorsqu’un projet n’a pas de job. La déclaration a disparu avec le retrait de la quantité de propositions. Recherche dans le dépôt et lecture HTTP de `http://127.0.0.1:7861/static/stories.js` : la référence est présente dans le fichier réellement servi, pas seulement dans une archive.

La création sauvegarde le projet côté serveur, affecte `state.project`, puis appelle `paint()` avant `write()`. L’exception dans `paint()` peut donc empêcher le premier appel LLM, tout en laissant un projet enregistré. Les modes idées et adaptation passent par ce message ; les modes script et continuation ont leurs propres branches. Le projet `story-63a23597c6764a3ea7c650dc5f49943f`, « goute d’eau », est enregistré sans job ni révision, état compatible avec cette séquence. Ne pas attribuer ce défaut à un modèle, au brief ou au cache ; remplacer le message par une formulation singulière lors de la prochaine implémentation autorisée. Aucun correctif appliqué maintenant.

### Valeur et coût observés de la relecture

Nouvelle run consultée en lecture seule : **L’eau qu’on donne**, `story-fcd6917016b04555bf7dd96e367e0d83`. Brief : gouttes anthropomorphes, épouse qui soigne son mari, attirance pour sa médecin, mélodrame visuel cruel. Une séquence, cinq clips de dix secondes maximum. Quatre appels enregistrés : proposition (78,815 s), arc (116,869 s), relecture (88,641 s), correction (88,631 s), soit **372,956 s ≈ 6 min 13** de génération cumulée, hors temps passé par l’utilisateur entre les étapes. Aucune scène rédigée au moment de la lecture.

La relecture relève un vrai maillon manquant : le transfert d’essence vers le mari n’est pas montré avant qu’une extraction ultérieure en dépende. Elle signale aussi une attirance amoureuse insuffisamment visible et une révélation trop chargée pour dix secondes. Cela apporte un exemple concret d’utilité ; cela ne démontre pas que toute relecture séparée ou sa durée actuelle est nécessaire. Le récit garde une mécanique métaphorique complexe, dont la compréhension et l’intérêt devront être jugés sur les scènes.

### Parcours recommandé à discuter

1. **Conception** : regrouper proposition unique et architecture dans un appel. Réponse lisible : promesse, personnages, progression, bascule et fin ; mémoire technique conservée derrière.
2. **Édition de l’architecture** : appel distinct qui examine cette proposition et apporte directement les petites corrections nécessaires, avec un bref relevé. Préserver le brief ; signaler un choix d’auteur important plutôt que le modifier silencieusement. Une passe automatique bornée. Cela reste une proposition à évaluer : la correction du relecteur n’est pas une preuve indépendante de sa propre qualité.
3. **Premier point d’intervention** : présenter l’histoire et le plan, puis « Développer le scénario ». L’utilisateur peut changer la fin, un personnage, le ton ou demander une autre proposition unique. Ne pas lui demander de cliquer sur relire/corriger/relire pour la même étape.
4. **Rédaction** : garder des appels par séquence lorsque la longueur le justifie, avec continuité. Pour une petite histoire, un appel peut produire tout le scénario. Le rédacteur fournit déjà le canon dans sa réponse : ne pas compter cela comme une nouvelle économie.
5. **Contrôle du scénario** : relecture d’ensemble pour un récit compact ; contrôles par blocs cohérents pour une histoire longue. Ne pas supprimer tous les contrôles intermédiaires d’une saga à secrets ou règles persistantes avant évaluation. Une correction supplémentaire éventuelle reste bornée et visible ; si un vrai blocage demeure, rendre le résultat et demander un choix précis.
6. **Second point d’intervention** : scénario lisible, prêt à discuter ou modifier, puis validation explicite pour Fabrication. Les générations de médias restent une étape distincte. Pendant une rédaction automatique, les retours doivent être pris en compte à une frontière d’étape/version cohérente, sans écraser silencieusement un texte en cours.

Compter séparément automatisation des clics et regroupement des appels. Parcours actuel en partant d’une idée, sans correction : **3 + 2N appels** (proposition, arc, relecture d’arc, puis rédaction et relecture par unité). Pour deux séquences : **7 appels**. Proposition ci-dessus pour un récit compact de deux séquences : **5 appels** (conception, édition, deux rédactions, contrôle global), hors corrections supplémentaires. Une séquence : **5 → 4**. Pour les longs récits, le nombre dépend du découpage des contrôles ; ne pas annoncer systématiquement `N + 3`. Moins d’appels n’implique pas proportionnellement moins de temps si les réponses deviennent beaucoup plus longues.

### Interface proposée

- Premier niveau : idée, univers, vidéo unique/série, durée souhaitée ; bouton principal « Imaginer mon histoire ». Nom facultatif issu de la proposition. Les informations nécessaires restent visibles, le reste s’ouvre à la demande.
- Section repliée « Orienter l’histoire » : profil, narration, fin, langue, vocabulaire. Choix Auto pour les directions que le moteur peut inférer ; afficher ensuite les valeurs réellement retenues avec une brève raison. Les choix explicites de l’utilisateur priment.
- Section repliée « Production et modèles » : clips, secondes par clip, modèles. Montrer le budget total et la portée par séquence. Ne pas demander à l’utilisateur de deviner une multiplication cachée.
- Bouton `ⓘ` à côté de chaque réglage, utilisable au clic et au clavier. Une courte explication : ce que cela change, deux exemples contrastés, quand laisser Auto. Exemple pour narration : visuelle = gestes et regards comme les gouttes ; dialogues = réactions et échanges comme les compteurs ; audio = compréhension à l’écoute. Éviter de transformer chaque aide en long paragraphe permanent.
- L’écran de travail présente l’histoire, la conversation et l’avancement. Contrats, IDs, secrets techniques et traces restent dans des détails consultables. Une seule proposition, aucun sélecteur de quantité réintroduit.

### Premier essai après accord et implémentation

Ne pas demander de nouvelles générations pour reproduire les erreurs déjà identifiées. Après les corrections et le parcours proposé : quatre essais textuels, deux briefs minimaux (gouttes/trahison et compteurs) × deux parcours (actuel corrigé et regroupé), mêmes modèles et budgets. L’utilisateur les lance. Comparer intérêt, compréhension des événements, qualité de la fin, cohérence, faisabilité, temps total et nombre de reprises. Cette première comparaison fournit un signal ; répéter les cas ambigus plutôt que conclure sur un seul tirage. Les vidéos viennent après le choix des scénarios.

## Complément — réponse de scénario et deux niveaux de délégation

L’utilisateur propose un mode automatique avec validations automatiques et un mode manuel, mais souligne qu’il ne sait pas où adresser ses retours. L’alignement reste en cours : aucune implémentation demandée dans ce complément.

### Développement de L’eau qu’on donne : cause exacte

Appel `llm-37d913d8bcfa4fe2969ad85c01cb6bc2`, opération `story.long.develop@2.0.0`, rédacteur `local::unsloth/gemma-4-31B-it-qat-GGUF`, le 20 septembre 2026 à 13:52:53–13:53:21, durée 28,036 s. La réponse termine avec `finish_reason=stop` et forme un JSON lisible de 9 987 caractères. Le contrat envoyé demande les clés racines `reply`, `scenario`, `episode_state`.

La réponse contient `reply` et `scenario`, avec **`episode_state` imbriqué dans `scenario`**. Les cinq scènes, affectations d’événements, faits, connaissances et fils narratifs sont présents. La mémoire n’est donc pas omise : elle est à la mauvaise profondeur. Le validateur racine refuse avant les contrôles du scénario avec « Réponse de scénario doit contenir exactement : reply scenario episode_state. »

Correction proposée, non appliquée : reconnaître ce cas précis de structure lorsque la mémoire manque à la racine mais existe à un seul emplacement imbriqué ; la déplacer sans en inventer ni modifier le contenu, puis exécuter les validations normales. Conserver le brut et tracer la normalisation. Si les deux emplacements existent avec un contenu contradictoire, ne pas choisir silencieusement. Si la mémoire est réellement absente, ne pas la fabriquer vide pour contourner la continuité. Une remise en forme réussie ne constitue pas à elle seule une validation narrative.

Le brouillon existant est conservé. Cette réparation structurelle devrait permettre de tenter sa revalidation sans nouvelle génération ; aucune normalisation, modification du projet ou exécution de test n’a été effectuée durant le diagnostic.

### Deux modes, même moteur narratif

- **Automatique** : enchaîne conception, contrôle/correction bornés, rédaction et contrôle final ; avance sur les résultats recevables et livre un scénario prêt pour Fabrication. Un problème narratif restant après la passe de correction ou une erreur technique irrécupérable provoque une pause expliquée. Validation automatique ne signifie pas ignorer les incohérences ou les données manquantes. Le périmètre est la rédaction ; les générations de médias restent dans la chaîne existante.
- **Manuel guidé** : utilise les mêmes appels et contrôles, mais marque les pauses d’auteur sur la direction de l’histoire, puis sur les séquences/scénario. Relecture et petites corrections techniques se font en arrière-plan dans les deux modes. Un bouton principal « Valider et continuer » remplace le pilotage des opérations internes. Les retours utilisateur ajoutent des appels seulement lorsqu’ils demandent une nouvelle rédaction.
- Passage possible d’automatique à manuel via « Reprendre la main » ; pause avant l’étape suivante, brouillons préservés. Un retour pendant une génération est conservé en attente et appliqué à une version clairement identifiée ; ne pas écraser le travail en cours ni prétendre qu’une consigne nouvelle a déjà été intégrée.

### Emplacement et portée des retours

Le défaut actuel est concret : `story-instruction` sert au bouton de conversation (`revise`) et à « Réviser l’arc » (`revise_outline`). Le routage de `revise` dépend implicitement de la présence d’un scénario ; les consignes utilisateur sont ensuite reprises dans `author_feedback` sans cible éditoriale explicitée. C’est difficile à anticiper pour l’utilisateur.

Proposition : un document principal lisible et **un seul espace de retour fixe**, à côté sur écran large et sous le document sur petit écran. En-tête visible « Ton retour sur : Histoire complète / Séquence 2 / Scène 3 ». La cible suit l’élément ouvert ; un bouton « Commenter cette scène » cible directement cet élément sans introduire un autre champ de saisie. L’utilisateur peut élargir la portée à l’histoire complète. Une sélection ou un extrait cité rappelle le passage concerné.

Le champ propose un exemple contextuel, tel que « Garde les personnages, mais rends la trahison plus évidente dans cette scène ». Deux intentions explicites : **Appliquer mon retour** pour demander une modification, **Poser une question** pour discuter sans réécriture. Après modification : nouvelle version affichée, bref relevé des changements, éléments préservés et éventuelles séquences dépendantes à mettre à jour ; possibilité de revenir à la version précédente. « Valider et continuer » reste près du résultat.

Les retours sont attachés à une cible et une version, avec état en attente/appliqué, pour éviter de réappliquer une ancienne consigne locale à toutes les unités. Le vocabulaire visible reste histoire, séquence, scène, progression et fin ; canon, identifiants, JSON et opérations de relecture restent dans les détails.

L’interface de création conserve l’organisation précédente (idée/univers/format/durée, directions narratives et production repliées, boutons d’information). Automatique/Manuel guidé est le choix de délégation ; il ne duplique ni les profils narratifs ni le moteur.
