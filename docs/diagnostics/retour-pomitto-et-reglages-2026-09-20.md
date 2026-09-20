# Retour sur la dernière histoire fabriquée et réglages de test

## Cas examiné

Le dernier scénario effectivement passé en Fabrication au moment de l’inspection est **La vengeance salée de Pomitto**, histoire `story-14f83b366fa64020916a12b0dcf80780`, fabrication `episode-e41513c02bdc41d480292089d3cbed10`. Le projet plus récent **Le Sirop des Regrets** (`story-0ce193485e5a4de5bec5defc0f83234e`) utilise la V2 longue, mais ne possède pas encore de scénario enregistré à cet instant. Il ne faut pas confondre les deux observations.

Sources locales lues : brief, proposition, scénario, échanges, intentions de fabrication et sorties des six scènes. Trois images par clip existant ont été extraites à 1, 5 et 9 secondes. La [planche](D:/Code/panelforge/workspace/experiments/analyse-pomitto-2026-09-20/storyboard.jpg) et les IDs des assets sont conservés dans `workspace/experiments/analyse-pomitto-2026-09-20`. Ce relevé ne constitue pas un visionnage continu ni une évaluation de la bande sonore. Aucun nouveau rendu ni appel LLM n’a été lancé.

Réglages observés : **mode court**, départ par proposition unique, famille Fruit, six clips de dix secondes, français, registre 3. Architecte : `local::HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF`. Rédacteur : `local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP`. Deux appels d’écriture réussis, proposition puis scénario, sans correction intermédiaire enregistrée.

## Ce qui fonctionne et ce que cela change dans l’audit

L’intention fournit déjà une trajectoire : détresse → immersion → rencontre d’une personne à secourir → aide → récompense → acquisition de pouvoir → départ vers un nouvel objectif. Le protagoniste passe d’une situation subie à une action utile, puis retrouve une capacité d’agir. La récompense suit son geste ; ce lien suffit à donner une direction au récit, sans exiger un conflit stratégique supplémentaire dans chaque clip.

Le rédacteur en conserve l’essentiel. Sauvetage et don occupent deux scènes distinctes. Les informations passent par des actions visuelles simples : cage, libération, contact de la main, énergie, lévitation. Les images échantillonnées conservent des personnages reconnaissables et rendent visibles immersion, sirène libérée, transformation et retour. Cela soutient l’appréciation positive de l’utilisateur, à la portée de cet échantillonnage.

**Ce résultat montre que le moteur existant sait déjà développer une bonne intention.** Il ne mesure ni la fiabilité sur tous les briefs, ni la continuité entre plusieurs épisodes : ce projet est court. La V2 doit conserver cette capacité et mieux protéger la trajectoire de l’auteur. Ajouter systématiquement des sous-intrigues, des épreuves ou des paramètres ne serait pas un progrès démontré.

| Moment | Respect de l’intention | Écart observé |
|---|---|---|
| Rupture / détresse | Le motif et la chute émotionnelle sont conservés. | La proposition ajoute confiscation de propriété, expulsion et humiliation publique. Le scénario consacre un clip entier à l’expulsion. |
| Rencontre et sauvetage | Le héros retrouve une possibilité d’agir en aidant la sirène. | La proposition ajoute une origine au piège impliquant le rival, qui n’est pas ensuite établie dans les scènes. |
| Récompense | Le don suit le sauvetage ; la transformation est visuellement identifiable. | Le don écrit sous l’eau est représenté au bord de l’eau dans les images du cinquième clip. Ce raccord relève aussi de la fabrication. |
| Fin | Le héros est devenu puissant et tourné vers la suite. | Le brief s’arrêtait au départ dans le ciel. Dès la proposition, le récit ajoute retour au palais et attaque ; le rédacteur reprend cette extension. |
| Conséquence | Le palais est fissuré dans les images échantillonnées. | L’état final affirme que le rival est « détrôné », alors que le scénario décrit surtout un choc et une couronne qui tombe. |

L’écart sur la fin apparaît donc **avant le Rédacteur**, au stade de la proposition. Le Rédacteur suit assez bien une proposition qui a déjà élargi le brief. La priorité est de vérifier tôt les étapes incontournables, les ajouts autorisés et le point d’arrêt, puis de préserver ce contrat. Il ne s’agit pas de refaire cette histoire ni de modifier ses fichiers enregistrés.

## Configuration conseillée pour le premier essai V2

Conserver les deux modèles de ce résultat pour éviter de changer simultanément moteur et modèles. Pour une nouvelle histoire dont la mécanique principale est une transformation suivie d’un objectif encore ouvert :

| Réglage | Valeur de départ | Effet |
|---|---|---|
| Format narratif | **Histoire longue V2** | Active contrat, arc, canon et relectures. Le mode court reste une référence utile pour les récits simples. |
| Famille | **Mélodrame fruits** | Donne l’univers et les conventions de personnages. En V2, elle n’impose pas le profil narratif ni un quota de paroles. |
| Mode de départ | **Développer mon histoire longue** | Utilise directement l’intention fournie pour construire l’arc. **Proposer une histoire** sert plutôt à chercher une direction quand elle manque. |
| Profil | **Transformation / quête** | Met l’accent sur découverte, acquisition, changement de capacité/statut et nouvel objectif. |
| Diffusion | **Récit continu en séquences** | Les unités composent un seul récit ; pas de résumé ou de cliffhanger obligé à chaque frontière. La fabrication reste séparée par unité. |
| Nombre de séquences | **2** | Deux parties de la même histoire, pas deux propositions. Permet de vérifier la continuité sur deux écritures consécutives. |
| Narration | **Dialogues dramatiques** | Les paroles expriment désirs, réactions et conflit ; les actions portent aussi l’histoire. |
| Fin globale | **Ouverte / suite** | L’arc peut finir sur une transformation ou un départ. Le brief doit préciser exactement l’action finale à ne pas dépasser. |
| Plafond de clips par unité | **3** | De un à trois clips utiles par séquence. Avec deux séquences de dix secondes par clip : au maximum soixante secondes, comme le cas de référence. |
| Durée d’un clip | **10 secondes** | Temps disponible pour actions, paroles et réactions ; le même réglage est utilisé par la fabrication. |
| Langue parlée | **Français** | Change la langue des répliques. Les descriptions restent en français. |
| Registre | **3 pour la comparaison** | Conserve le vocabulaire cru/argotique du cas observé. Ce réglage n’améliore pas la structure ; choisir **1 — Oral direct** pour un ton moins vulgaire. |
| Architecte / Rédacteur | **Qwen3.8-27B / Gemma4-31B déjà utilisés** | Le premier construit et relit en V2 ; le second écrit et corrige les scènes. Le réglage Local/serveur choisit où est exécuté le modèle, pas un degré de créativité. |

Ce budget est un point de départ comparable, pas une promesse que chaque intention tient en soixante secondes. Si la relecture relève une vraie surcharge, alléger le récit ou créer un nouvel essai avec un plafond supérieur : le budget V2 actuel est fixé à la création. Pour qualifier spécifiquement la V2 sans générer de vidéo, ce parcours de deux séquences nécessite six appels d’écriture/relecture, hors corrections.

Les autres choix ont les effets suivants :

- **Mélodrame** : rapports de pouvoir, trahisons et conséquences relationnelles. **Suspense / révélation** : indices, croyances et moment où le public apprend la vérité. **Aventure à règle fantastique** : exploitation cohérente d’une règle et de ses limites. Un pouvoir ponctuel ne suffit pas à rendre ce dernier profil préférable à Transformation.
- **Feuilleton** : épisodes conçus pour être publiés séparément, avec une progression locale et une attente vers la suite. Le nombre indique des épisodes d’une seule histoire.
- **Narration explicite / audio** : rend les faits nécessaires accessibles à l’écoute, par les paroles et canaux vocaux existants ; ce n’est pas un nouveau moteur de voix. **Principalement visuelle** : gestes, objets et réactions portent le récit ; les paroles ne sont pas obligatoires. La famille muette impose l’absence de paroles.
- **Résolution** ferme le conflit principal ; **Retournement** change l’interprétation ou le rapport de force à la fin ; **Victoire avec coût** associe réussite et perte. Ce sont des directions éditoriales, pas des garanties automatiques de fidélité à la dernière phrase du brief.
- **Registre 0** n’ajoute aucune consigne de vocabulaire ; **1** favorise l’oral quotidien ; **2** autorise un vocabulaire cru ; **3** accentue l’argot lorsque pertinent. **Nom** sert à retrouver le projet ; l’intention narrative doit être dans le champ de texte.
- En mode court, **Continuer une histoire** exploite le passé fourni ; **Suivre fidèlement un script complet** conserve les dialogues au mot près. L’adaptation longue autorise la réécriture : ces deux usages sont différents.

Pour un brief efficace, cinq indications suffisent : **situation initiale**, **progression et découvertes obligatoires**, **changement attendu**, **action exacte de fin**, **libertés autorisées**. L’orthographe parfaite n’est pas nécessaire : la trajectoire concrète du brief de Pomitto est déjà exploitable malgré ses fautes.

## Simplification implémentée

Une seule proposition par demande, sur tous les parcours qui proposent une histoire. Le sélecteur et `proposal_count` ont été supprimés du formulaire, de l’API de création, des nouveaux documents et des contextes LLM. Le validateur refuse plusieurs propositions ; l’unique histoire est sélectionnée automatiquement. Son bouton de sélection redondant disparaît et sa carte utilise toute la largeur disponible.

Les documents historiques comportant plusieurs propositions restent lisibles et sélectionnables. Leur ancienne métadonnée de quantité est ignorée pour les nouveaux appels. Les recettes archivées ne sont pas réécrites sur disque ; l’adaptation des anciennes consignes au contrat d’une proposition est conservée. Les anciens clients envoyant `proposal_count` doivent être rechargés après mise à jour du serveur.

Tests contractuels et navigateur mis à jour, vérifications statiques effectuées. Tests non exécutés conformément au `AGENTS.md` du worktree ; aucun service redémarré. Les vidéos et projets utilisateur n’ont pas été modifiés.
