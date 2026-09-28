# Petits hommes : retours, mécanismes et intention courte — 28 septembre 2026

Analyse seulement, à la demande de l’utilisateur. Aucun correctif appliqué.

## Conclusion

La précision manquante concerne le besoin à satisfaire et le comportement du
phénomène. La liberté de choisir un objet peut rester large. Une feuille
plastique qui intercepte une vague répond au danger continu ; une collecte
locale suivie d’un versement dans la ville rend l’aide incohérente. Pour la
sécheresse, l’objectif doit être l’apport d’eau même lorsque l’image met en
avant une fissure.

Les deux exports nommés par l’utilisateur sont des tsunamis malgré leur
préfixe incendie. Ils datent du 27 septembre et utilisent la politique v2,
avant le correctif v3 livré. Dans l’état lu, 72 vidéos Petits hommes terminées :
21 v2 et 51 anciennes sans version de sélection ; aucune v3 terminée.
Ces retours précisent la direction, sans mesurer encore les résultats du v3.

## Ce qui a été vérifié

Dix Plans lus : les deux tsunamis, trois incendies textiles, cinq sécheresses.
Sept planches comparées visuellement : les deux tsunamis et trois incendies
DLSS, plus deux sécheresses en rendu de base (exports DLSS de celles-ci
absents à leurs chemins enregistrés). Captures extraites à 2 images/s, puis
sélectionnées sur les planches ; pas de lecture audio ni de jugement sur
la fluidité fine à la fréquence native.

| Cas | Plan et captures | Conséquence |
| --- | --- | --- |
| [b1b89c22 / feuille plastique](../../.agent/diagnostics/little-men-feedback-20260928/b1b89c22/contact.jpg) | La feuille devient une paroi entre la vague et les habitants, puis une raclette nettoie. La barrière reste visible. De la mousse déborde, mais le mécanisme de protection reste immédiatement lisible. | Garder l’idée : intervenir à l’échelle et sur le trajet du danger. La feuille reste un exemple, pas un objet obligatoire. |
| [5ca8a38e / bol](../../.agent/diagnostics/little-men-feedback-20260928/5ca8a38e/contact.jpg) | Le Plan demande de capter puis reverser vers un canal de fond. Le bol arrive visiblement plein, puis le versement se fait parmi les constructions. La protection contre toute la vague est peu établie. | Problème à la fois de mécanisme dans le Plan et de restitution. Ne pas interdire tous les récipients ; distinguer eau stagnante et arrivée continue. |
| [fea47e26 / sécheresse Corée](../../.agent/diagnostics/little-men-feedback-20260928/fea47e26/contact.jpg) | Image dominée par une route fissurée ; le Plan et le rendu posent un pansement. | Le besoin de boire/arroser n’est pas traité. L’image autorise une lecture de route endommagée. |
| [2f73e2d8 / sécheresse France](../../.agent/diagnostics/little-men-feedback-20260928/2f73e2d8/contact.jpg) | Une fissure au premier plan devient le sujet du sauvetage ; un bâton de colle la colmate. | Même dérive que la recouture signalée par l’utilisateur, sans couture littérale retrouvée dans les cinq Plans lus. |
| [ad7cccd7 / feu en ville](../../.agent/diagnostics/little-men-feedback-20260928/ad7cccd7/contact.jpg) | Forme de flamme très dessinée et rigide ; sous le bocal, elle rétrécit et conserve une lueur résiduelle. | Extinction et mouvement vivant insuffisamment lisibles. |
| [13b5f86f / vaporisateur](../../.agent/diagnostics/little-men-feedback-20260928/13b5f86f/contact.jpg) | La forme de flamme initiale reste très sculptée, mais le vaporisateur laisse ensuite la fenêtre sombre. | Une aide utile peut réussir malgré un feu peu vivant. Distinguer pertinence de la solution et animation du phénomène. |
| [15f72d44 / feu rural](../../.agent/diagnostics/little-men-feedback-20260928/15f72d44/contact.jpg) | Le foyer ressemble à des éclats translucides ; sous le bocal, ces formes s’assombrissent et restent présentes. | La source et les mots employés invitent à animer un objet figurant le feu. |

Parmi les cinq sécheresses, trois Plans proposent déjà de l’eau ; deux
proposent colle/pansement. Les tornades et réparations sont conservées comme
réussites signalées par l’utilisateur et examinées lors des audits précédents ;
elles n’appellent pas de nouvelle contrainte dans ce complément.

## Incendies : source et prompt vidéo se renforcent

Les descriptions KREA des trois incendies parlent explicitement de résine
orange/rouge et de fumée en coton. Le cas rural décrit des éclats de résine
lumineux. Le Plan va jusqu’à demander aux personnages de pousser ces éclats.
Les prompts vidéo répètent les flammes en résine et les éclats rigides.

L’hypothèse de l’utilisateur est donc fortement étayée : le départ est déjà
sculptural, et la préparation entretient cette interprétation. Ce n’est pas
une preuve expérimentale isolant la cause, car aucun A/B n’a été généré.

Pour les futures images KREA, proposer une consigne brève :
« Décor et personnages en laine ; feu incandescent aux contours souples et
irréguliers, fumée légère. »
Dans la préparation vidéo, demander le mouvement des flammes jusqu’à
l’extinction. Préserver le style miniature sans recopier une matière rigide
comme définition obligatoire du feu.

## Proposition de texte, non appliquée

Base commune : **87 mots**.

> Les petits hommes affrontent le problème de l’image. Une main géante descend du ciel avec un objet du quotidien, monumental pour eux, et le détourne pour apporter une aide ingénieuse et immédiatement compréhensible. Chaque geste fait progresser la même solution et laisse un bénéfice durable. Garder les personnages et le décor reconnaissables, avec des phénomènes vivants qui réagissent à l’intervention. Une fois l’aide accomplie, la main remonte ; les petits hommes lèvent les bras et prononcent ensemble, une seule fois, le remerciement fourni. Laisser voir le résultat.

Ajouter une seule phrase liée au problème, puis éviter de la redoubler dans
les consignes du Plan :

| Problème identifié | Phrase ciblée | Total avec la base |
| --- | --- | --- |
| Sécheresse | Apporter de l’eau pour soulager la sécheresse et rendre son bénéfice visible. | 99 mots |
| Tsunami / vague | Intercepter ou détourner la vague avant les habitants, avec une protection qui reste efficace. | 101 mots |
| Inondation | Évacuer l’eau hors de la zone protégée et montrer une baisse durable du niveau. | 101 mots |
| Incendie | Les flammes vacillent et la fumée monte, puis le feu s’éteint sous l’effet de l’aide. | 102 mots |

La langue et sa formule restent gérées par le mécanisme v3 déjà en place.
La durée reste transmise par le réglage de rendu. Le nombre de gestes reste
dicté par l’aide utile et le temps disponible.

Le problème vient de l’intention KREA/contexte explicite confronté à l’image.
Le nom de fichier n’est pas une source fiable : les deux tsunamis sont nommés
incendie. Si une ancienne image n’a plus ce contexte, préciser simplement
« sécheresse, manque d’eau » dans le champ de scène existant. Pas de besoin
établi d’un appel LLM supplémentaire ou d’un nouveau catalogue d’objets.

## Marche à suivre proposée

1. Valider ce principe : résultat attendu précis, accessoire et gestes libres.
2. Au futur correctif, remplacer les formulations génériques/redondantes par
   la base et la seule consigne pertinente ; conserver les mots exacts de
   remerciement et les règles de langue actuelles.
3. Pour les images de sécheresse ambiguës, rendre le manque d’eau explicite
   dans la source. Pour les nouveaux incendies, corriger aussi la description
   de l’image KREA afin d’obtenir un feu moins sculptural.
4. Comparer quelques cas ciblés à réglages constants : tsunami feuille/bol,
   sécheresse ayant reçu un pansement, feu en laine. Garder une tornade et une
   réparation témoins afin de vérifier que leur inventivité est préservée.

Les images en résine rigide risquent de rester contraignantes même avec un
meilleur texte vidéo ; ce point sera à juger sur un futur essai, sans ajouter
de longues règles préventives.

Preuves : selected.json, media.json, proposed-intention.json et captures dans
.agent/diagnostics/little-men-feedback-20260928/.
Aucun code, preset, intention enregistrée, média source, réglage ou service
modifié ; aucun appel LLM, rendu, test ni redémarrage.
