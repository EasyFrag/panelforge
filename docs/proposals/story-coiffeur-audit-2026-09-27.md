# Audit comparé — La Coupe Demandée et Le Colis — 27 septembre 2026

Périmètre : scénario et appels enregistrés, sans évaluation des vidéos finales. Nouveau projet story-d279def1674c444dbb645f75d6899ea2 ; fabrication episode-04ec1e7b956a4de289a592c4c9a746f4. Aucun code, réglage ou runtime modifié.

## Comparaison factuelle

| Point | Le Colis | La Coupe Demandée |
| --- | --- | --- |
| Intention | Deux colocataires opposés sur un colis reçu par erreur | Coiffeur qui rate complètement une coupe et la fait passer pour recherchée |
| Fin au premier appel | Automatique, résolue par le modèle en ouverte | Résolution explicitement fournie dès le premier appel |
| Durée cible / scénario | 50 / 40 s | 50 / 50 s |
| Clips | 4 | 5 |
| Mots de dialogue, même comptage lexical | 119 | 103 |
| Appels | 3, aucun repair | 3, aucun repair |
| Durée cumulée LLM | 402,344 s | 383,712 s |
| Langue des dialogues | Française, quelques maladresses | Deux répliques sur dix avec des phrases hybrides français/anglais |

Même profil comédie noire/argot cru v1, street, registre 3, rythme rapide, français, humains adultes réalistes/live action. Aucun lexique ni phrase imposée. Même Qwen3.8-27B HauhauCS Uncensored Aggressive MTP dans les trois rôles. Révision éditoriale 8 effectivement chargée. Ces deux essais ne suffisent pas à attribuer un défaut à la famille Qwen ou à cette variante seule.

## Ce que raconte le nouveau scénario

Yanis découvre sa nuque asymétrique. Malik refuse la notion de raté, nomme la coupe Le Décalé, flatte le client et applique un produit. Yanis finit par payer, satisfait, puis remercie le coiffeur d’avoir sauvé sa soirée.

La progression et la fin sont plus nettes que dans Le Colis. Cependant, le ressort de tromperie est atténué : le résumé explique que Malik transforme la coupe pour aider Yanis. Le raté reste asymétrique mais devient objectivement plus stylé dans les descriptions. L’ironie d’un client convaincu par un mensonge pourrait fonctionner, mais le scénario ne maintient pas assez clairement le décalage entre sa croyance et ce que voit le public. Peu de montée dans la mauvaise foi ; le récit ressemble progressivement à une remise en confiance.

Le monde visuellement réaliste est bien respecté. En revanche, un aspect photoréaliste n’exige pas une intrigue prudente ni une atténuation de l’exagération comique. L’instruction initiale « rate complètement » perd de sa force au fil de la conception.

## Langue : défaut établi et laissé passer

La réponse brute de develop contient déjà :
- « Je peux sort as such or t’rends me ridiculous? » ;
- « Le Décalé. Rarely a client oses it. Et t’as the face that carries it. »

Les mêmes fragments sont enregistrés dans dialogue.text. Ce n’est pas une traduction effectuée par PanelForge. L’arc comportait déjà quelques fragments anglais, puis le rédacteur les multiplie dans les descriptions et deux répliques. Sa trace alterne français et anglais dans ses brouillons de phrases, malgré plusieurs rappels explicites de produire du français. La cause technique précise de cette non-conformité n’est pas déterminable à partir de ces traces seules.

La relecture détecte explicitement ces deux répliques et propose de les corriger. Elle les classe pourtant warning/clarity, au motif que l’intrigue reste compréhensible. Ce n’est pas le code qui rétrograde ce diagnostic : la réponse brute du lecteur dit déjà warning. L’automate suit donc la politique existante et termine avec le scénario prêt sans correction. La détection locale repose sur des marqueurs lexicaux et ne signale ici que trois descriptions ; ce contrôle heuristique ne suffit pas à garantir la langue parlée.

## Pourquoi la relecture valide la dérive

Le lecteur reçoit les scènes réellement jouées, les états visuels et unit_requirements.required_on_screen. Ces exigences sont les preuves d’événements choisies par la conception. Il ne reçoit ni le brief initial ni une projection distincte de ses contraintes d’auteur.

L’événement 4 demande déjà que le client voie la coupe comme une déclaration et l’événement 5 qu’il parte confiant. La relecture vérifie correctement cette version, mais possède peu de prise pour détecter que l’intention de tromperie a été adoucie en amont. La protection contre les secrets futurs est utile ; elle ne devrait pas faire disparaître les contraintes d’auteur pertinentes pour la séquence courante.

## Coût et hésitations

| Étape | Durée | Tokens de sortie déclarés, raisonnement compris |
| --- | --- | --- |
| Conception | 95,351 s | 6 574 |
| Rédaction | 165,026 s | 17 310 |
| Relecture | 123,335 s | 4 217 |

Total 6 min 24, sans boucle d’appels ni troncature. Le raisonnement enregistré contient environ 3 202 / 8 070 / 2 333 mots respectivement ; ce sont des mots comptés, pas des tokens mesurés.

Le rédacteur produit cinq scènes de deux répliques, en suivant cinq événements. Il revient longuement sur les clés, tailles de listes, IDs, états et formats, et remet plusieurs fois ses dialogues en chantier sans éliminer le mélange de langues. Les preuves d’événements sont identiques dans selected_unit et unit_requirements, soit environ 1 032 caractères de contexte répétés. La structure response_schema représente ~6 770 caractères côté rédaction. Elle sert une validation utile : ne pas la supprimer sans préserver ce contrat.

Côté relecture, visual_state_review (~5 545 caractères) dépasse reader_units (~4 630). Cette projection sert la continuité, mais donne une piste concrète de simplification adaptée aux changements réels. Réduire ces redondances n’a pas encore de gain de latence démontré.

## États visuels

Base de Yanis correctement définie dès sa première apparition avec la coupe ratée ; une variante coiffée est prévue après scène 4. Pas de prolifération comme dans l’ancien essai Fraisette. Son intérêt reste à discuter : si seuls un léger brillant et la confiance changent, une deuxième référence n’est pas forcément nécessaire. Si une forme réellement différente doit être visible, elle se justifie. L’évolution d’opinion d’un personnage n’est pas, à elle seule, un état physique.

## Proposition à discuter, non implémentée

1. Traiter la mauvaise langue dans une phrase parlée comme un défaut de livraison avéré, distinct d’un choix stylistique. Conserver les emprunts usuels, noms et citations autorisées. Réutiliser la correction ciblée bornée ; ne pas transformer tous les warnings en blocages ni ajouter une passe universelle.
2. Donner au lecteur une courte projection des contraintes originales applicables à l’unité, séparée des décisions de conception, sans révéler les secrets des unités suivantes. Il pourra comparer l’intention, l’arc et ce que voit réellement le public.
3. Clarifier la responsabilité créative : inventer un aboutissement et préserver le ressort comique du brief, sans trame, vocabulaire ou punition obligatoire. Une résolution ne signifie pas obligatoirement réparation, réconciliation ou amélioration objective.
4. Alléger d’abord les répétitions mesurées et les instructions techniques redondantes. Garder les trois fonctions tant qu’elles sont utiles ; ne pas réduire brutalement le budget de sortie et risquer de réintroduire des troncatures.
5. Après ces corrections, comparer Qwen seul et Qwen conception/relecture + Gemma rédaction sur une même intention et des réglages identiques. Cela permettrait de distinguer le routage, les consignes et le modèle, sans attribuer à Qwen entier les défauts d’un run.

Aucun test, appel LLM, rendu, redémarrage ou modification du scénario n’a été lancé pendant cet audit.
