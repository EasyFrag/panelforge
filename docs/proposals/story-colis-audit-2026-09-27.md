# Petit audit — Le Colis — 27 septembre 2026

Projet : story-0c1422ce9a55463c8529e254a4bc273d. Fabrication : episode-1bbc0a1095a748a69297bfd742388435. Audit du scénario et des trois appels enregistrés, pas des vidéos finales.

## Verdict

Essai techniquement réussi, intention minimale respectée et ton plus franc inventé sans répliques imposées. Le récit reste toutefois une installation de conflit, avec peu de comédie et sans véritable aboutissement local. Le problème dominant est désormais éditorial, pas une erreur de JSON ou une boucle automatique.

## Réglages réellement reçus

Comédie noire / argot cru v1 ; style street ; vocabulaire 3 ; débit rapide ; langue française ; humains adultes réalistes ; rendu live action. Lexique et paroles exactes vides. Qwen3.8-27B Uncensored HauhauCS Aggressive MTP pour les trois rôles. Cible 50 s, plafond 5 clips de 10 s. La fin et le profil étaient auto au premier appel ; le concepteur a choisi social et open. L’utilisateur n’a donc pas imposé une fin ouverte.

## Résultat

Quatre scènes de 10 s, soit 40 s préparées. Environ 119 mots de dialogue selon un comptage lexical conservant les contractions, contre 121 dans le diagnostic applicatif.

1. Découverte du colis et de l’erreur de livraison.
2. Nino veut rendre le carton ; Sacha conteste.
3. Sacha ouvre, découvre la montre et décide de la garder.
4. Nino emporte le carton presque vide ; elle garde la montre et tous deux restent au seuil.

Les objectifs sont lisibles et les deux voix distinctes. Les expressions familières viennent du modèle, pas d’un lexique injecté. « Ton cerveau dit on rend ça » et « comme si j’avais volé ta mère » cherchent une couleur propre. Mais le récit répète surtout rendre/garder, sans changement de tactique très marqué, gag visuel fort ou conséquence comique jouée. Le départ de Nino avec le carton vidé affaiblit son objectif initial : pourquoi lui reste-t-il utile ?

Une formulation est fautive : « C’est vrai or » au lieu de « C’est du vrai or ». L’arc contient de nombreux mélanges français/anglais ; les dialogues finaux restent français. La relecture ne relève ni cette maladresse ni la faiblesse de l’aboutissement.

## Appels et raisonnement observé

| Étape | Durée | Tokens de sortie déclarés, raisonnement inclus |
| --- | --- | --- |
| Conception | 100,732 s | 7 357 |
| Rédaction | 152,541 s | 15 532 |
| Relecture | 149,071 s | 6 738 |

Total : 402,344 s, soit 6 min 42 ; trois appels acceptés, aucune récupération, correction ou troncature. Les 29 627 tokens ne sont pas les seuls tokens de scénario. Les débits moyens sortie/durée sont environ 73, 102 et 45 tokens/s, préremplissage compris : ils ne démontrent pas ici un chargement RAM ou une anomalie GPU.

Le concepteur hésite plusieurs fois entre une conséquence et une fin ouverte. Il préfère la seconde comme choix prudent afin d’éviter d’ajouter une punition ou un retournement. Il traite ainsi l’idée de départ comme une situation à préserver plutôt que comme le début d’une histoire à développer. Les consignes de liberté semblent ici interprétées comme une raison de ne pas engager une issue ; c’est une inférence appuyée sur les traces, pas une mesure causale contrôlée.

Le rédacteur décide de quatre scènes pour quatre événements, laissant le cinquième clip disponible. Son raisonnement consacre beaucoup de place au schéma, aux champs et aux états visuels. La relecture prend presque autant de temps que la rédaction et hésite surtout sur la durée estimée et la granularité des états. Elle accepte le récit et conserve une remarque indicative de débit. Aucun blocage automatique n’en résulte.

## Continuité et fabrication

Deux personnages, un décor, le colis et la montre sont justifiés. Une sixième référence « montre posée sur la paume de Sacha » a aussi été créée : elle représente une position de l’objet plutôt qu’une nouvelle apparence durable. C’est une variante probablement superflue, à distinguer des deux véritables références d’objets utiles.

## Orientation pour la discussion

Conserver le ton, la simplicité et les trois fonctions. Clarifier que l’absence de chute imposée laisse au concepteur la responsabilité d’inventer un aboutissement, même pour une fin ouverte. Demander une différence perceptible entre début et fin, sans imposer de punition ou de scénario-type. Orienter la relecture sur la compréhension et l’effet narratif avant les estimations de durée. Un seul essai ne suffit pas à conclure à un biais systématique.

Aucun code, réglage, scénario ni donnée runtime modifié. Aucun test, appel LLM, rendu ou redémarrage lancé.
