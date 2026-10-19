# Recettes — cuisine dans un monde en laine

L’entrée **Recettes**, après **Histoire**, conserve un projet culinaire autonome. Elle réutilise KREA2 Assisted pour le plat final, H3/MiniMax ou KREA2 + Flux Klein pour les images des plans, et l’usine H3 pour les clips. Les autres parcours et leurs consignes restent distincts.

## Parcours

1. **Univers** : choisir une image existante, importer un fichier ou créer le plat terminé avec un preset KREA2. Le premier preset dont le nom contient wool, laine ou crochet est proposé lorsqu’il existe ; le choix reste modifiable et aucun identifiant de preset local n’est imposé. Le bouton **Créer une recette** sur un essai KREA2 réussi ouvre ce parcours avec l’image choisie.
2. **Découpage** : proposer les plans, les modifier directement ou demander une révision globale. Chaque plan décrit le geste, le rôle préparation/présentation, la scène complète (aliments, récipient, outils et état), le cadrage, les deux états et la durée. Les propositions privilégient **Animation · 1 image** ; les exceptions à deux images demandent une différence visible et une justification. Une proposition sans justification revient à une image. Le mode reste modifiable manuellement ; **Passer tous les plans à une image** prépare la modification, à enregistrer, sans lancer de rendu. Réordonner ou retirer une carte conserve ses essais dans le projet. Valider le découpage déclenche uniquement le lot d’images demandé.
3. **Images** : examiner les images au fil du lot, consulter les instructions, retenir un essai compatible ou régénérer un plan avec une correction. **Généré** et **revu et validé** sont distincts : confirmer la revue, par plan ou en lot, avant l’envoi à l’Usine. Vérifier le plat, le début du geste et la continuité de l’arrivée éventuelle. Un plan **Départ + arrivée · 2 images** prépare son départ, puis son arrivée depuis ce départ avec le plat comme référence secondaire. **Corriger/Générer l’arrivée seule** réutilise exactement le départ affiché, même après un échec ou un abandon de l’arrivée. Une paire partielle n’est jamais envoyée à H3. En mode une image, seule l’image de départ est affichée et envoyée ; une arrivée déjà produite reste consultable dans l’historique.
4. **Clips** : **Envoyer à l’Usine**, en lot ou par plan, crée une fiche en préparation avec les images retenues, le geste, la durée, le cadrage, le format et les consignes visuelles/sonores. L’envoi ne lance ni Plan, ni Prompt, ni vidéo : leur lancement se fait depuis l’Usine. Les cartes montrent les images, le mode, l’état **Envoyé à l’Usine** et un lien direct. Les clips terminés sont ensuite suivis dans Recettes. Sélectionner les essais à garder, puis exporter un ZIP de clips numérotés dans l’ordre des plans, accompagné de `ordre_des_clips.json`. Le montage est externe.

Un plan prêt et revu peut être envoyé pendant que les images d’autres plans sont encore en préparation. Si la sélection contient un plan incomplet, périmé ou non revu, il faut le décocher ou terminer sa préparation. L’ensemble de la sélection est validé avant transmission. Les corrections saisies sur chaque carte sont reprises aussi lors d’un envoi en lot.

## Choisir le moteur des images

Dans **Découpage**, **Valider et générer avec H3** conserve le mode une/deux images de chaque plan. **Valider et générer avec KREA2** passe tous les plans du lot à **Animation · 1 image** et réutilise le preset choisi dans Univers. Il faut choisir un preset s’il manque ; un preset supprimé bloque le lot avant toute modification. La validation, le moteur, la conversion des modes et les tâches sont enregistrés ensemble. Rejouer la même demande ne crée pas de deuxième lot.

Pour KREA2, le prompteur reçoit l’image d’Univers, le preset, le découpage ordonné, le contrat complet du plan et sa correction éventuelle. Il écrit un prompt autonome pour une nouvelle image avant le geste. L’image d’Univers sert à l’analyse visuelle du prompteur ; elle n’est pas transmise comme source à éditer au rendu. Le pipeline est celui d’Univers : KREA2 + finition Flux Klein, 2,1 MP et sampling 8 + 4, avec le checkpoint et les LoRA du preset. Le modèle de prompt est **Découpage et création KREA2** ; H3 utilise **Images des plans · prompt MiniMax**. Aucun gain de vitesse n’est présumé.

Le moteur est conservé par plan et affiché sur les cartes et les essais. Les régénérations, individuelles ou en lot depuis Images, réutilisent ce choix. Le sélecteur du plan permet de changer de moteur ; KREA2 reste à une seule image. Pour revenir à une paire, choisir H3 puis le mode départ/arrivée. Les boutons de validation globaux appliquent leur moteur à tous les plans. L’état de fin reste une intention pour la vidéo, même lorsque seule l’image de départ est générée.

Les essais existants sont conservés. Changer de moteur ou de preset KREA2 demande de nouvelles images ou de revenir aux réglages de l’ancien essai avant de le retenir. Les empreintes H3 historiques restent compatibles. Le contexte KREA2 inclut aussi les titres, gestes et rôles du découpage ordonné : leur modification peut rendre les images KREA2 obsolètes ; durée et réglages H3 seuls ne les invalident pas. La limite du chat KREA2 est respectée en raccourcissant seulement le résumé des autres plans si nécessaire. Un contrat de plan/correction encore trop long est signalé, sans le tronquer ni lancer le rendu.

La dernière scène conserve son fonctionnement actuel : aucune image d’arrivée issue directement d’Univers ni scène finale supplémentaire n’est ajoutée. La revue explicite des images et l’envoi de fiches en préparation dans l’Usine restent nécessaires ; les nouveaux envois gardent le DLSS activé.

## Contrat de scène 2.0.0

Le découpage et chaque prompt d’image reçoivent l’identité du plat, l’action, la scène, les deux états, le rôle du plan et les consignes d’univers. Le départ représente l’instant avant le geste, avec les mains et outils nécessaires déjà visibles. L’arrivée conserve le récipient, la position, le cadrage et les identités alimentaires du départ ; seule la conséquence du geste change. Un morceau de bœuf en crochet reste du bœuf, pas une pelote ou un champignon. Les étapes précédentes excluent les ajouts et le dressage futurs ; la présentation finale montre le plat complet et reconnaissable. Les consignes de matière couvrent aussi les liquides, la vapeur et l’arrière-plan, même si le plat de référence comporte un détail réaliste.

Ces consignes renforcent le contexte fourni aux modèles existants ; elles ne constituent pas une détection automatique des défauts visuels. Aucun appel d’évaluation supplémentaire n’est ajouté. Les anciennes descriptions ne sont pas réécrites automatiquement : pour corriger un mauvais découpage, modifier sa scène/son geste ou demander une révision avant de régénérer explicitement les plans concernés.

## Choix initiaux

- Image de départ du projet = plat terminé, conservé comme référence d’ingrédients, de texture et de palette. Les premiers plans ne doivent pas recopier son état déjà cuit ou dressé.
- Monde textile, y compris eau, huile, vapeur et flammes. Mains et avant-bras humains réalistes.
- Cohérence surtout du style et des couleurs. La cuisine et les accessoires peuvent changer entre les plans.
- Gros plans et cadrages variés, caméra stable au sein de chaque clip.
- Sons des gestes et de cuisine, esprit ASMR, sans voix ni musique. Ce parcours ne prépare ni narration, ni musique, ni titres.
- Durée totale indicative, 45 secondes par défaut ; clips de 5 à 15 secondes selon le contrat H3 actuel. Les durées de rendu sont quantifiées par le moteur. Le format vertical 9:16 est modifiable.
- La création KREA2 applique le checkpoint et les LoRA du preset sélectionné, avec la recette KREA2 + Flux Klein existante. Les plans peuvent suivre ce même chemin en génération directe, ou la composition MiniMax depuis le plat puis une édition locale pour leur arrivée éventuelle. Les vidéos H3 utilisent les réglages de l’usine et un seul plan par clip, première image seule ou première/dernière image. Les nouvelles fiches Recettes ont le DLSS activé par défaut ; son exécution reste liée au lancement depuis l’Usine.

Le suivi et l’export utilisent la vidéo DLSS lorsqu’elle est terminée et activée dans la configuration exécutée. La vidéo brute reste disponible pendant son traitement ou en cas d’échec. Les fiches déjà créées conservent leurs réglages : réenvoyer la même version ne force pas leur DLSS et ne crée pas de doublon.

## Historique et reprises

Les commandes de génération portent une identité persistante et un instantané des paramètres. Le rejeu d’une commande retrouve ses tâches ; il ne double pas le lot. Les liens aux projets enfants sont sauvegardés avant la génération. Les essais conservent les images et les références précises utilisées. Chaque régénération produit un nouvel essai sans effacer le précédent.

L’envoi à l’Usine conserve une réservation durable avant transmission. Réenvoyer les mêmes images, paramètres et correction retrouve la même fiche, y compris après une réponse interrompue. Les modifications faites dans l’Usine ne sont pas écrasées. Une nouvelle version ou correction crée une nouvelle fiche ; si l’ancienne fiche a été supprimée de l’Usine, un nouvel envoi explicite peut la remplacer, en conservant l’historique de Recettes. Les productions déjà lancées avant ce changement restent suivies.

L’identité du plat, le titre, l’action, la scène, le rôle, le départ et les réglages visuels participent à la compatibilité du départ. Modifier seulement l’arrivée ou le mode conserve le départ ; une durée différente ne réclame pas de nouvelles images. L’arrivée et le mode participent à la compatibilité de la paire. La revue porte sur l’essai retenu et le contexte visuel exact : changer d’essai ou de contexte demande une nouvelle revue. Une image reçue pendant la validation provoque un conflit de version ; elle ne peut pas être approuvée sans avoir été affichée. Modifier une action, une durée ou les images signale les anciens clips. L’export refuse les clips sélectionnés qui ne correspondent plus aux plans et images actuels. Réordonner les plans H3 ne rend pas leurs clips obsolètes ; le contexte global KREA2 suit les règles indiquées ci-dessus.

Les essais compatibles et les archives ont des compteurs distincts. Les archives portent le nom du plat et du plan d’origine, restent consultables et ne remplacent pas les images/vidéos actuelles. Les anciennes images sans nouvelle empreinte sont comparées à partir de l’instantané de leur tâche, sans migration du runtime. Elles peuvent être revues et validées si elles correspondent encore au plan. Le changement de politique ne régénère rien, ne modifie pas les modes existants et ne recrée pas les fiches déjà envoyées.

**Pause après l’étape** empêche les tâches suivantes. Les traitements déjà transmis restent suivis. **Abandonner les étapes restantes** retire le travail non encore démarré ; les sorties terminées et les essais restent conservés. Après redémarrage, les lots sont suspendus, les résultats externes déjà soumis sont récupérés et aucun appel de préparation interrompu n’est rejoué silencieusement. Une erreur conserve son diagnostic ; la reprise manuelle du plan crée un essai distinct.

Les routes de consultation n’envoient aucun nouveau travail aux modèles. L’export lit les vidéos existantes et ne les réencode pas. Les fichiers ZIP temporaires sont supprimés après téléchargement.

## Organisation

- Contrats purs : `domain/cooking_recipes.py`.
- Coordination, prompting et adaptateurs : `application/cooking_recipes.py`, `cooking_recipe_prompting.py`, `cooking_recipe_production.py`.
- Index et projets : `workspace/cooking_recipes/`. Références explicites par asset et identifiant de plan ; aucune découverte des médias par chemin.
- Stockage et ZIP : `infrastructure/storage/cooking_recipes.py`, `infrastructure/cooking_recipe_exports.py`.
- HTTP : `/api/recipes`, revue via `POST /projects/{identity}/review-images` (version, ids, approved), arrivée seule via `/generate/image` avec `image_part="end"`, envoi via `POST /projects/{identity}/send`; interface : `recipes.js`, `recipes.css` et section dédiée de `index.html`. L’ancien point d’entrée `/generate/clip` refuse les nouveaux lancements et demande d’actualiser la page. Les tâches historiques déjà enregistrées conservent leur traitement.

Pour les deux boutons Découpage, `/generate/image` reçoit aussi `image_engine="h3"` ou `"krea2"` : choix et validation explicites du lot. Sans ce champ, la génération exige le découpage accepté et réutilise le moteur mémorisé de chaque plan (H3 par défaut pour les anciens projets). Le champ est refusé pour les autres opérations et pour la correction d’arrivée seule.

## Vérification et mise en service

Tests préparés dans `tests/test_cooking_recipes.py`, avec ports de rendu simulés : arrêt après les images, paire de bornes et références, envoi sans lancement, déduplication, reprise après réponse interrompue, refus d’une sélection incomplète/périmée, corrections par plan, suivi des productions historiques, export ordonné, contrats HTTP et stockage. Tests non exécutés conformément à AGENTS.md.

Régressions de la version scène 2 : transmission du contexte complet, choix par défaut du mode, revue explicite et conflit lors d’une nouvelle image, identité de l’essai revu, conservation du départ, correction de l’arrivée seule et rejeu de commande, reprise après échec/redémarrage, passage à une image après abandon, compatibilité historique sans migration et archivage des images/clips d’un ancien plat. Les vérifications de syntaxe n’importent ni ne démarrent l’application.

Régressions préparées pour les deux moteurs : validation atomique/conversion/rejeu, preset absent ou supprimé, reprise KREA2 et régénération, H3 à deux images conservé, historique H3/KREA2 distinct et réutilisable, moteur préservé lors d’une révision, référence Univers et contexte envoyés au prompteur, workflow Flux Klein et reprise d’un essai déjà préparé, échec du prompt sans rendu, longueur de contexte, contrat HTTP et envoi à l’Usine après revue avec DLSS.

Depuis le checkout actif, l’utilisateur peut lancer :

```powershell
python -m unittest discover -s tests -p "test_cooking_recipes*.py"
```

Puis la suite habituelle `python -m unittest discover -s tests`, notamment les régressions des services KREA2 et Qwen/MiniMax partagés. L’implémentation n’a lancé aucun modèle ni rendu, ni redémarré de service. Charger le backend au prochain redémarrage habituel, puis actualiser le navigateur. La fidélité des mailles, des mains et des gestes reste à qualifier sur les générations choisies par l’utilisateur.
