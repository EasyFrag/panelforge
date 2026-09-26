# Lèvres : apparition des ornements au contact — analyse du 26 septembre 2026

Statut au moment de l’analyse : proposition à discuter, non implémentée. Le changement a ensuite été validé et implémenté dans le preset ; voir la [note de version](video-factory-lips-contact-release-2026-09-26.md). Aucun appel LLM, rendu, DLSS, test, redémarrage ou changement de fiche/preset. Les images de diagnostic ont été extraites sur CPU des vidéos de base existantes.

## Périmètre et limites

Neuf rendus usine Lèvres terminés entre 12 h 06 et 12 h 53, heure de Paris, le 26 septembre. Lecture des intentions, plans, prompts rédigés et effective_prompt des tentatives H3 correspondantes. Inspection de planches horodatées des neuf bases ; inspection rapprochée toutes les 0,25 s entre 2 et 5,75 s pour les runs 3, 6, 7 et 8. Ce sont des échantillons visuels, pas une mesure exhaustive de tous les pixels ni un essai causal contrôlé. Aucun nouveau rendu comparatif n’a été lancé.

Les neuf intentions sont identiques. Les neuf prompts rédigés correspondent aux effective_prompt, hors espaces de bord : pas de substitution apparente entre rédaction et soumission. Mêmes réglages enregistrés : 10 s, seed 0 verrouillée, 0,9 MP, Bunny 9 steps, coarse 4/refine 5, turbo, Motion Repair 0,6/0,2. Même recette 0.1.3+vae-int8-convrot.1. Preview désactivée dans les tentatives batch. Une image de fin et aucune image de début dans les neuf projets. Les références et les textes finaux varient entre runs ; la série ne permet pas d’isoler leur influence respective.

## Constats les plus utiles

- Cristaux, 5434db2f : de 2 à 3,5 s, le stick glisse sur la lèvre inférieure, qui reste nue sur la portion visible derrière lui. Vers 4,5–5,75 s, il traite la lèvre supérieure tandis que la lèvre inférieure se couvre aussi. L’effet est donc différé et s’étend hors du contact courant.
- Opales, a3b97c35 : vers 3,5–4,75 s, les pierres apparaissent sur la lèvre inférieure pendant le balayage visible de la lèvre supérieure. La bouche est ouverte, ce qui rend l’apparition sur la lèvre opposée particulièrement lisible.
- Moonstone récent, 89bfdbb9 : entre 2,25 et 3 s, une petite zone ornée apparaît derrière le stick sur la lèvre inférieure ; c’est un début plus proche du résultat souhaité. Mais seul un côté est parcouru avant le passage à la lèvre supérieure. Vers 5,25–5,75 s, le bas se complète pendant le geste sur le haut. Ce run est partiellement convaincant, pas un succès strict de la règle locale.
- Jade, 022fb046 : le début laisse une zone ornée localisée, puis l’ornement inférieur s’étend pendant le passage supérieur. Son plan contient littéralement deux règles contradictoires : « leaving green jade-and-diamond material only where it has contacted », puis « The ornamental material spreads from those touched zones until both lips match the finish ».

Le défaut existe déjà avant le DLSS. Le DLSS n’est donc pas nécessaire à son apparition ; cette analyse ne mesure pas ses éventuels effets secondaires.

## Pourquoi le prompt favorise ce résultat

### Une ambiguïté dans notre intention

Le preset dit : « la matière se propage depuis les zones réellement touchées jusqu’à couvrir les deux lèvres ». Cela définit le lieu d’origine, mais autorise une propagation indépendante après le contact. Le besoin réel exige que chaque nouvelle zone ornée ait été directement balayée par le stick.

Le plan reprend cette propagation. La rédaction l’amplifie parfois : pour les cristaux 8a98d45f, le plan garde « spreads from the touched area », mais le prompt final combine les deux lèvres et dit seulement « spreads to fully cover both lips ». Pour Jade, la restriction « only where it has contacted » disparaît de la rédaction, alors que la propagation subsiste. Ajouter une seule phrase à l’intention sans vérifier le plan et le prompt final risque donc de laisser le défaut.

### Le geste ne décrit pas comment couvrir toute la surface

« Glisse sur la lèvre inférieure puis supérieure » ne précise pas un trajet complet d’une commissure à l’autre. Plusieurs vidéos commencent au centre et ne balaient qu’une moitié de la lèvre inférieure. Le texte exige néanmoins une couverture complète et une fin conforme à l’image ornée. Mon hypothèse est que cette combinaison encourage une complétion à distance. La référence finale entièrement décorée et le temps réservé au sourire peuvent renforcer cette tendance, mais la série ne le prouve pas isolément.

### La variation n’est pas une preuve de seed aléatoire

Les réglages enregistrés ont tous seed 0 verrouillée. Les images et les formulations changent : certaines combinaisons donnent un geste initial plus lisible, d’autres une transformation presque simultanée des deux lèvres. On ne peut pas attribuer cette différence au seul prompt ou à la seule référence avec cette série. Aucun élément ici ne démontre que le LoRA ou le nombre de steps serait la cause principale.

## Correction proposée

Préserver l’adaptation des matières, couleurs, ongles et bijoux à l’image finale, l’ASMR, le plan continu et le sourire final. Remplacer la propagation par une règle de dépôt local immédiat, puis décrire deux passages complets, séparés par un bref retrait visible.

Bloc de mécanisme proposé pour l’intention :

> L’ornement apparaît immédiatement et uniquement sur la surface de lèvre réellement balayée par la face du raisin. Il forme une trace nette directement derrière le contact en mouvement ; devant le stick et partout où il n’est pas passé, la lèvre reste nue. La main place le raisin à une commissure de la lèvre inférieure puis balaie lentement toute sa surface jusqu’à l’autre commissure, en gardant un contact visible. La lèvre supérieure reste entièrement nue pendant ce premier passage. Le stick se soulève brièvement : tout nouveau dépôt s’arrête et le décor déjà posé reste fixé. La main pose ensuite le raisin à une extrémité de la lèvre supérieure et effectue un second passage complet, dans l’autre sens. La lèvre inférieure déjà décorée ne change plus. Aucune pierre n’apparaît à distance, avec retard, ou sur la lèvre opposée ; aucun effet de vague ni croissance autonome. La main se retire une fois les deux surfaces parcourues. Le sourire franc s’ouvre ensuite et tient jusqu’à l’image finale.

Le stick conserve son aspect orné ; on ne demande pas simultanément que ses propres pierres se détachent et qu’il reste intégralement intact. Le rendu peut conserver sa fantaisie esthétique, avec une causalité de contact claire.

Proposition de rythme pour 10 s : approche brève, environ 3 s pour la lèvre inférieure, bref changement de lèvre, environ 3 s pour la supérieure, retrait et installation du sourire, environ 2 s de sourire tenu. Le geste doit rester simple. Ce rythme est un guide à tester, pas une garantie de suivi temporel. Éviter le départ au centre suivi d’un seul demi-passage.

Dans la préparation : faire apparaître trois états explicites dans le plan (deux lèvres nues ; bas décoré/haut nu ; deux lèvres décorées). Dans la rédaction : conserver l’ordre, les deux trajets complets et la règle « hors contact, aucun changement ». La description sonore reste liée au frottement/contact, sans nouvelle vague de cristallisation. Le futur patch doit rester limité au preset Lèvres, sans imposer ce scénario à H3 manuel ou aux autres presets.

## Vérification proposée après alignement

1. Premier essai sur une référence humaine déjà testée (Moonstone 89bfdbb9 ou cristaux 5434db2f), avec la même image et les mêmes paramètres enregistrés. Modifier seulement le mécanisme et son déroulé dans le prompt final pour isoler son effet du Plan/Writer.
2. Contrôler : absence de pierre avant contact ; trace immédiate derrière le stick ; haut nu pendant l’application du bas ; aucune progression pendant le changement de lèvre ; absence de transformation après retrait ; sourire final conservé.
3. Si ce premier essai est convaincant, porter la règle dans l’intention automatique et vérifier sa conservation dans Plan puis Prompt sur une autre matière. La réussite d’un seul rendu ne démontre pas sa fiabilité générale.
4. Si le dépôt reste à distance avec un texte non ambigu, étudier une séquence plus simple ou davantage de temps pour l’application. Une image de début nue peut aider à fixer le départ mais ne définit pas le chemin de contact ; ce n’est pas le premier levier ici, puisque les neuf rendus commencent déjà avec des lèvres non ornées.

Aucune migration/régénération des anciens prompts proposée automatiquement. Les réglages existants DLSS et Texte IG restent hors du périmètre de cette analyse.

## Index des sources

Les dossiers de diagnostic contiennent overview.jpg, reference.jpg et les frames extraites. runs.json conserve les identifiants, textes et réglages analysés. Les médias sources ne sont pas déplacés.

| N° | Run | Fin vidéo (Paris) | Nom | Planche |
|---|---|---|---|---|
| 1 | a38c742d | 12:06:32 | levres moonstone | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/01-a38c742d/overview.jpg) |
| 2 | c74f3c27 | 12:12:24 | levres rubis | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/02-c74f3c27/overview.jpg) |
| 3 | 5434db2f | 12:18:41 | Levres diamants et sourrire | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/03-5434db2f/overview.jpg) |
| 4 | 7745fce4 | 12:24:32 | Levres diamants et sourrire | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/04-7745fce4/overview.jpg) |
| 5 | 8a98d45f | 12:30:25 | Levres diamants et sourrire | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/05-8a98d45f/overview.jpg) |
| 6 | a3b97c35 | 12:36:17 | Levres diamants et sourrire | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/06-a3b97c35/overview.jpg) |
| 7 | 89bfdbb9 | 12:42:08 | levres moonstone | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/07-89bfdbb9/overview.jpg) |
| 8 | 022fb046 | 12:47:59 | levres jades | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/08-022fb046/overview.jpg) |
| 9 | 59581654 | 12:53:52 | levres rubis | [Images](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/09-59581654/overview.jpg) |

[Détail du contact — 5434db2f](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/03-5434db2f/contact-detail/contact.jpg)

[Détail du contact — a3b97c35](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/06-a3b97c35/contact-detail/contact.jpg)

[Détail du contact — 89bfdbb9](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/07-89bfdbb9/contact-detail/contact.jpg)

[Détail du contact — 022fb046](D:/Code/panelforge/.agent/diagnostics/lips-contact-2026-09-26/08-022fb046/contact-detail/contact.jpg)

Sources code : src/panelforge/domain/video_factory.py (LIPS_INTENT, lignes 26–44), preparation_text (135–143), application/video_factory_workflows.py (_session, _plan et _prompt). Aucune modification de ces fichiers pendant cette analyse.
