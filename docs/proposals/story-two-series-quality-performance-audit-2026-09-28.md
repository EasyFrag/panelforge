# Audit des deux séries — qualité et performance — 28 septembre 2026

> Complément après les rendus : [audit fondamental de La même espèce](story-same-species-fundamental-audit-2026-09-28.md). Le premier jugement narratif était trop indulgent ; le complément distingue les défauts réellement observés des hypothèses de cet état des lieux antérieur.

## Périmètre et conclusion

Demande explicite : auditer et conserver les améliorations possibles, sans coder. Lecture des scénarios, arcs, relectures et huit traces d’écriture ; inspection de douze références sélectionnées de la première série et de dix références candidates de la seconde, disponibles à 15:53:30 UTC (17:53:30 Paris). Les deux workflows d’écriture sont `ready`. Les scènes exportées ne comportent aucune préparation vidéo au relevé : animation, voix et synchronisation ne sont pas évaluées.

Les bases narratives sont reconnaissables et les références ont une finition propre. La fidélité reste toutefois trop souvent validée par des signes approximatifs : une valise devient une rupture, une notification devient une liaison établie, une phrase de ressemblance concurrence la fausse preuve finale. Les images de photographies ne conservent pas les identités des personnages. La longueur du raisonnement ne se traduit donc pas par une vérification narrative assez fiable.

## 1. La même espèce

Projet `story-887454eeb15c4481b9db6a83ff708e3a`. Deux unités, sept clips de 10 s effectivement écrits, pour un plafond configuré de dix clips / 100 s. Univers non renseigné, personnages humains réalistes, adaptation, mélodrame, langage naturel cru et débit rapide. Le moteur n’a pas reçu de demande explicite de fruits ou de rendu 3D dans ce run.

### Réussites

- La présentation est cette fois audible : Marc dit « ta copine ». Le défaut de relation seulement présente dans les métadonnées du précédent audit n’est pas reproduit.
- Le baiser et le transfert de clé rendent la liaison perceptible au public. Le secret ne dépend pas d’un simple résumé.
- Marc et Mia restent dans le casting lorsqu’ils sont silencieux ; l’absence de Léo pendant l’échographie est explicite. Pas de confusion systématique entre visibilité et dialogue dans le découpage.
- Léo et Marc réutilisent exactement leurs références entre unités. La variante enceinte de Mia conserve bien son visage et sa robe. Les décors réalistes ont une lumière compatible.

### Défauts à conserver pour correction

1. **La fausse preuve finale est affaiblie.** Léo dit d’abord « il a les mêmes yeux que moi », puis « Un petit humain comme moi ». La première réplique ajoute un indice conventionnel de ressemblance qui concurrence le raisonnement absurde demandé : même espèce donc fidélité. Garder la conclusion absurde comme cause intelligible de son soulagement, sans ajouter une preuve parallèle plus plausible. Il n’est pas nécessaire de dicter tous les dialogues.
2. **Raccord émotionnel contradictoire.** Après les excuses, l’état final dit que Léo regarde le carnet « sans conviction », tandis que la mémoire le classe comme rassuré et la fin le dit convaincu. Une acceptation résignée et un soulagement réel ne sont pas équivalents. La relecture ne signale pas ce décalage.
3. **Échographie : confusion concrète entre photo, écran et scène.** Le scénario fait sortir une échographie, montrer un écran avec les silhouettes du couple, puis ranger une photo dans un sac. La description devient « Image d’échographie reflétant deux silhouettes ». Le prompt image demande effectivement ces silhouettes dans le scan. L’image sélectionnée montre un appareil/moniteur d’échographie, pas une photo portable. L’image n’affiche pas clairement les deux silhouettes erronées : le défaut confirmé est la chaîne de description et la nature de l’objet, pas une hallucination visuelle supposée. Choisir un objet cohérent avec le geste, puis maintenir ce choix jusqu’au rendu.
4. **Grossesse conservée après la naissance.** Un seul état enceinte est posé au début de l’unité et persiste jusqu’à la scène finale. Aucune évolution après naissance n’est indiquée alors que Mia est présente. Ne pas exiger un ventre plat immédiatement ; prévoir simplement un état cohérent avec la scène après accouchement, sans reconduire automatiquement l’état de grossesse.
5. **Dramaturgie comprimée et accessoires surchargés.** Trois scènes suffisent à présenter, embrasser et dissimuler ; quatre autres concentrent grossesse, doute, excuses et naissance. Photos multiples, calendrier, carnet de lit et étiquette de pharmacie compliquent la lisibilité sans développer beaucoup les rapports. Les 70 s effectives respectent un plafond, mais ne constituent pas une vidéo de 100 s. Utiliser éventuellement un clip disponible pour une réaction qui change la situation ; ne pas remplir pour atteindre un quota.
6. **Qualité du dialogue inégale.** « Bonjour. Je suis pas bizarre, j’espère », « Les dates sont là » et le carnet de réglages du lit semblent dictés par le besoin de cocher une preuve plutôt que par une intention naturelle. L’absurde peut rester, mais l’excuse doit être compréhensible et produire une réaction crédible dans cet univers.

Les portraits sont propres. L’écart de génération entre Léo et Marc est visuellement peu marqué, au regard du père décrit comme quinquagénaire ; c’est un jugement de lisibilité du casting, pas une estimation d’âge certaine. La référence bébé inclut des bras et une pose liés à la scène : distinguer à l’avenir identité du bébé et manipulation par Léo.

## 2. La mèche de Kiwino

Projet `story-0be1a86194434102b0f6e0487ed3f487`. Une unité, cinq clips de 10 s pour un plafond de six / 60 s. Mode idées, profil/fin automatiques résolus en suspense/coût, ambiance comédie noire street, vocabulaire 3, rendu 3D. Ce choix explique le ton plus cru : ce run n’est pas une comparaison contrôlée de modèles avec le précédent, ni la reproduction des réglages de départ du guide Download(35).

### Réussites

- Progression globale lisible : dissimulation, test positif, enthousiasme du compagnon, peur de la mère, ressemblance, effondrement.
- La mèche et la marque sur la joue donnent un motif visuel concret à la révélation. La fiche de Kiwino et celle du bébé présentent bien une ressemblance de famille à ce niveau général.
- Le bébé est explicitement dans le casting de la scène où il est tenu ; Kiwino peut légitimement exister seulement sur photo. Il n’est pas nécessaire de le faire entrer physiquement dans les scènes pour faire disparaître un avertissement.

### Défauts narratifs

1. **Rupture insuffisamment jouée.** Le plan demande à Bananito de quitter l’appartement tout en le laissant seul dans ce même appartement devant la chambre. Le rédacteur repère cette contradiction dans sa trace, y revient plusieurs fois, puis choisit de fermer une valise, claquer la porte de la chambre et rester immobile. Aucune confrontation ni décision de rupture claire n’est dite à Cerisa. Les symboles expriment la peine et une intention de partir, sans établir nettement l’action demandée. Le relecteur relève lui aussi l’absence de départ explicite, mais l’accepte comme symbolique. Le brief dit « la quitte », pas nécessairement « quitte l’appartement » : il faut surtout une rupture perceptible et une géographie cohérente, sans ajouter une obligation absente de la source.
2. **Cerisa disparaît avant la conséquence.** Elle n’est présente ni à la découverte ni à la fin ; aucune transition n’explicite sa position. C’est un choix de cadrage possible, mais il évite la réaction et l’échange qui donneraient du poids à la séparation. Ne pas l’ajouter partout automatiquement : décider où la rupture doit être perceptible.
3. **Secret d’abord suggéré.** La notification au nom de Kiwino démontre une communication cachée, pas encore la nature de la relation. La pensée sur la mèche à la troisième scène rend ensuite le secret beaucoup plus clair. L’intention générale est respectée, mais le public n’a pas dès l’ouverture la certitude que le plan prétend lui donner.
4. **Émotion très brève.** Le compagnon exprime sa joie dans une seule réplique, puis sa perte en quelques mots. Cinq clips et 66 mots environ laissent une marge : la répétition verbale n’est pas le problème principal, c’est le manque de réactions et de décisions jouées. Un sixième clip utile pourrait établir la rupture ; aucune nécessité de remplir mécaniquement.
5. **Finition linguistique.** « On fêt ça » est une faute dans une parole libre ; « tâche claire » revient pour une tache sur la joue. Aucun passage involontaire en anglais dans les dialogues examinés ; aucun « wesh ». La voix intérieure est explicite (`thought`) mais mérite d’être assumée lorsque le mode choisi est dialogue.

### Références candidates examinées à 17:53:30 Paris

Dix images prêtes à valider, aucune sélectionnée à cet instant ; une onzième fiche est la variante de photo déplacée.

- **Défaut majeur : la photo de Kiwino représente un autre personnage.** La fiche montre un personnage vert à mèche sombre ; la photo montre un personnage à peau humaine et cheveux vert vif. Le prompt de photo a conservé la mèche et la tache, mais perdu l’espèce, la morphologie et les autres traits. Un nom propre seul ne porte pas une identité visuelle.
- **La photo du couple montre deux humains.** Elle ne reprend ni Bananito banane ni l’apparence de Cerisa. Son prompt dit seulement « a stylized couple, Cerisa and Bananito ». Le problème existe donc avant l’exécution image. Les portraits déjà établis devraient servir de sources à la photo, au lieu de la réinventer indépendamment.
- **Univers hétérogène.** Bananito est immédiatement une banane ; Cerisa ressemble surtout à une femme stylisée rosée ; Kiwino et le bébé à des personnages verts. Les fiches sont jolies séparément mais insuffisamment coordonnées. Même observation que dans l’audit piscine. Kiwino a en outre une silhouette assez enfantine pour le rôle d’amant adulte prévu.
- **Le bébé paraît déjà assez grand et se tient debout.** Sa ressemblance est utile, mais sa présentation sert mal une révélation à la naissance. Le prompt a réduit « nouveau-né » à un bébé générique avec vêtements simples.
- **Variante de photo inutile.** « Posée sur la table du salon » devient « posée près du lit » et crée une nouvelle référence. L’objet ne change pas d’apparence ; seul son emplacement change. C’est un coût évitable, contrairement à une valise réellement ouverte puis fermée.
- Le téléphone affiche lisiblement Kiwino ; le test ne donne pas une lecture nette de deux traits dans une fenêtre de résultat. Ce dernier détail doit être confirmé à taille utile avant de servir de preuve centrale.

La fiche de Kiwino reste utile pour construire sa photographie, même s’il n’apparaît jamais en personne. Ne pas supprimer sa référence sur la seule base de `unused_characters`.

## 3. Relecture : longue, mais trop indulgente sur les effets dramatiques

Les prompts contiennent déjà la bonne instruction : relire ce que le public voit et entend et ne pas confondre une preuve demandée avec une preuve jouée. `reader_units.characters` ne contient que les IDs et noms : il ne faut pas expliquer le défaut par une fuite supposée de toutes les descriptions de rôle. La projection du lecteur est déjà allégée.

Le problème observé est l’arbitrage : le lecteur accepte une valise comme une rupture accomplie et le rédacteur sacrifie une conséquence pour satisfaire un plan contradictoire. Ajouter encore le même paragraphe de fidélité aurait peu de valeur. Remplacer les formulations répétées par un contrôle court, centré sur la conséquence source et le geste/la parole qui la démontre ; accepter explicitement « preuve insuffisante » sans inventer une nouvelle intrigue.

La première relecture produit un correctif visuel utile pour l’état initial du bébé, mais aucune issue narrative. La seconde répond `issues=[]` ; l’application réintroduit ensuite deux warnings de casting que le résumé annonce levés. C’est un bruit déjà observé avec Kiwito à la piscine. Une photographie ou une notification ne justifie pas la présence physique de Kiwino.

Le bloc visuel de la relecture Kiwino compte environ 8 692 caractères contre 4 114 pour les scènes lues. Le contrôle d’apparence est nécessaire, mais prend ici plus de place que le récit. Privilégier les changements et incohérences pertinents, plutôt qu’ajouter une nouvelle passe LLM systématique.

## 4. Performance mesurée

Toutes les étapes d’écriture et relecture utilisent `local::unsloth/Qwen3.8-27B-GGUF` (alias enregistré, pas une vérification de quantification). Température 0,6 en composition/rédaction, 0,3 en relecture. Plafond demandé : 80 000 tokens ; toutes les réponses se terminent normalement, aucune troncature observée.

| Mesure | La même espèce | La mèche de Kiwino |
| --- | ---: | ---: |
| Appels d’écriture enregistrés | 5 | 3 |
| Durée cumulée des tentatives applicatives | 17 min 40,5 s | 8 min 57,3 s |
| Décomposition | plan rejeté 2:24 ; nouveau plan 2:15 ; écriture 3:56 + 5:02 ; relecture 4:02 | plan 2:01 ; écriture 3:58 ; relecture 2:59 |
| Tokens d’entrée cumulés | 30 178 | 18 065 |
| Tokens de sortie rapportés par le serveur | 79 071 | 43 524 |
| Caractères de raisonnement enregistrés | 269 469 | 142 437 |
| Caractères de réponse JSON | 46 957 | 27 368 |
| Part du raisonnement en caractères | 85,2 % | 83,9 % |
| Réécritures narratives automatiques | 0 | 0 |
| Clips effectifs | 7 × 10 s | 5 × 10 s |

La première chaîne réussie prend 15 min 16,6 s hors essai rejeté. Son temps calendrier depuis la création jusqu’à la relecture est d’environ 28 min 39 s, incluant près de 11 minutes entre échec et reprise : ne pas attribuer cette pause au débit du modèle. La seconde réutilise le plan d’abord rejeté après normalisation du spectateur ; aucune deuxième composition n’est enregistrée. L’issue historique `rejected` reste dans la trace initiale, sans signifier que le plan est encore bloqué.

**Ces durées concernent l’écriture seulement, pas les rendus image/vidéo.** Ce sont des durées enveloppes des appels, pas du temps GPU pur. Les traces ne séparent pas assez précisément attente, chargement, préremplissage, raisonnement et décodage ; impossible d’attribuer leurs variations au seul modèle. Les pourcentages ci-dessus portent sur les caractères, pas sur les tokens de raisonnement ni sur un pourcentage exact du temps.

### Où le modèle tourne en rond

- Rédaction de « La naissance » : 72 966 caractères de raisonnement pour 13 234 de JSON ; calculs répétés de mots, hésitations sur les états de l’échographie, le bébé et les transitions.
- Rédaction Kiwino : 76 483 caractères de raisonnement pour 18 179 de JSON ; contradiction « partir/rester », inventaire répété de `reference`, détenteurs, scènes et champs requis. La contradiction est identifiée, puis rationalisée au lieu d’être résolue proprement.
- Relecture première série : 59 496 caractères de raisonnement pour 2 845 de réponse, soit environ 21 fois plus ; 4 min 02 pour deux validations et un petit patch.
- Relecture Kiwino : 36 952 pour 1 249, soit environ 30 fois plus ; 2 min 59, aucune issue émise par le modèle malgré le départ ambigu.

Ce ne sont pas des boucles de corrections automatiques répétées. Il s’agit de suranalyse à l’intérieur de chaque appel, surtout autour des contrats et de la continuité. Réduire arbitrairement le plafond global peut couper le JSON sans améliorer le jugement.

## 5. Plan d’amélioration conservé, non implémenté

| Priorité | Modification à préparer | Bénéfice attendu / critère |
| --- | --- | --- |
| P0 | Contrôler la conséquence voulue à partir du geste ou de la parole effectivement joués, séparément du plan inventé | Détecter la rupture non établie et la fausse preuve affaiblie ; éviter de valider des résumés flatteurs |
| P0 | Préserver l’identité dans les images contenant d’autres personnages : photos, écrans, portraits | Photo de Kiwino et photo du couple reconnaissables par comparaison avec leurs fiches |
| P0 | Résoudre les contradictions du plan avant de leur consacrer plusieurs minutes de rédaction | Départ/position finale cohérents ; photo/écran de l’échographie cohérents |
| P1 | Séparer durablement apparence, emplacement, détenteur, pose et présence silencieuse | Plus de variante pour une photo déplacée ; grossesse traitée après naissance ; absence justifiée non signalée comme erreur |
| P1 | Réduire et différencier l’effort de raisonnement selon le rôle | Relecture plus courte, avec au moins la même détection des défauts prouvés ; zéro troncature |
| P1 | Fusionner les doublons de consignes et limiter les inventaires visuels au besoin de l’étape | Moins d’hésitations de format ; éviter d’ajouter partout les règles de chaque bug |
| P1 | Corriger localement langue et mots pivots, sans réécriture globale | « on fête », « tache », nouveau-né conservé ; mêmes intentions et même registre |
| P2 | Comparer les modèles sur ces cas gelés, après contrôle des entrées et budgets | Choisir le meilleur rapport défauts détectés / temps total, pas le plus gros raisonnement |

### Prompts : simplifier plutôt qu’empiler

Les mêmes notions de fidélité, état/transformation et budget de parole reviennent dans plusieurs blocs du système et du contexte. Garder une définition par notion. Clarifier notamment le terme « transformation physique » face au transfert de clé : la trace montre que le modèle hésite longuement sur cette distinction, malgré une règle de référence déjà présente. Le cas spécifique du spectateur possède désormais une normalisation : ne pas le compenser par une longue nouvelle consigne dans chaque rôle.

La relation entre schéma complet dans le texte et schéma de sortie contraint peut être comparée ensuite ; ne pas retirer aveuglément les contraintes utiles. Les champs d’état qui répètent une conclusion devraient rester dérivés d’une scène effectivement jouée. Le moteur n’a pas besoin d’un nouveau résumé complet à chaque contrôle.

Fixer explicitement l’univers au départ si son identité compte : avec `visual_universe` vide, un brief a produit des humains et l’autre des fruits. Le rendu 3D est distinct de l’espèce des personnages. Aucune modification des réglages utilisateur n’a été faite.

### Modèles et protocole de comparaison

Conserver Qwen comme point de comparaison pour la composition. Tester d’abord une relecture au raisonnement plus court, sur les scénarios figés et les défauts connus, sans relancer toute une série. Une variante sans raisonnement ou Gemma déjà disponible peut être un candidat de lecteur ; aucune supériorité de vitesse ou de fidélité n’est établie ici. Gemma sert actuellement aux prompts de références : les erreurs de photo montrent que changer le modèle seul ne corrige pas une entrée privée de l’identité visuelle.

La documentation actuelle de llama.cpp propose un budget de raisonnement distinct et un réglage d’effort. Leur compatibilité avec le binaire local, le modèle et son template reste à vérifier avant tout essai ; aucun paramètre n’a été appliqué. [Documentation officielle du serveur llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

Pour une comparaison future : mêmes scènes/briefs, même univers, paramètres enregistrés, une variable à la fois. Mesurer JSON valide, faits perceptibles, contradictions ratées, fausses alertes, cohérence des identités, temps total à froid/à chaud et taille du raisonnement. Tenir compte du coût de changement de modèle et de chargement : un lecteur plus rapide isolément peut ne pas accélérer le parcours complet.

Les appels à s’abonner ne figurent pas dans les briefs actuels et `protected_lines` est vide : leur absence n’est pas un échec du mécanisme de répliques imposées. Si souhaité sur ces histoires, en faire une demande explicite courte au prochain essai.

## Preuves et continuité

Instantanés, métriques par appel et quatre planches dans `D:/Code/panelforge/.agent/diagnostics/story-two-series-audit-20260928/` : `story-call-metrics.json`, `references.json`, `references-1.jpg`, `references-2.jpg`, `kiwino-candidates-1.jpg`, `kiwino-candidates-2.jpg`. Les photos candidates ne sont pas présentées comme des choix validés par l’utilisateur.

Cet audit prolonge [l’audit copine v3](story-girlfriend-v3-audit-2026-09-28.md) et [l’audit piscine v3](story-pool-v3-audit-2026-09-28.md) : preuves réellement jouées, identité séparée de l’action, univers cohérent, présence/parole distinctes et bruit de relecture réduit.

Aucun code applicatif, prompt actif, modèle, réglage, scénario, référence ou état de production modifié. Aucun test, appel LLM, rendu, installation ou redémarrage déclenché. Seuls des documents et artefacts d’audit ont été écrits.
