# Recettes — cuisine dans un monde en laine

L’entrée **Recettes**, après **Histoire**, conserve un projet culinaire autonome. Elle réutilise KREA2 Assisted pour le plat final, MiniMax pour les images des plans et l’usine H3 pour les clips. Les autres parcours et leurs consignes restent distincts.

## Parcours

1. **Univers** : choisir une image existante, importer un fichier ou créer le plat terminé avec un preset KREA2. Le premier preset dont le nom contient wool, laine ou crochet est proposé lorsqu’il existe ; le choix reste modifiable et aucun identifiant de preset local n’est imposé. Le bouton **Créer une recette** sur un essai KREA2 réussi ouvre ce parcours avec l’image choisie.
2. **Découpage** : proposer les plans, les modifier directement ou demander une révision globale. Chaque plan décrit un geste, un cadrage, l’état de départ, l’arrivée et la durée. Réordonner ou retirer une carte conserve ses essais dans le projet. Valider le découpage déclenche uniquement le lot d’images demandé.
3. **Images** : examiner les images au fil du lot, consulter les instructions, choisir un ancien essai ou régénérer un plan avec une correction. Une image suffit pour une animation libre ; un plan à deux états prépare d’abord son départ, puis son arrivée depuis ce départ avec le plat original comme référence supplémentaire. Une paire partielle n’est jamais envoyée à H3.
4. **Clips** : lancer explicitement les plans sélectionnés. Les clips passent par le Plan, le Prompt et le rendu habituels de l’usine. Le projet montre leur état, leurs vidéos et leurs essais ; un lien ouvre l’unité correspondante dans l’usine. Sélectionner les essais à garder, puis exporter un ZIP de clips numérotés dans l’ordre des plans, accompagné de `ordre_des_clips.json`. Le montage est externe.

## Choix initiaux

- Image de départ du projet = plat terminé, conservé comme référence d’ingrédients, de texture et de palette. Les premiers plans ne doivent pas recopier son état déjà cuit ou dressé.
- Monde textile, y compris eau, huile, vapeur et flammes. Mains et avant-bras humains réalistes.
- Cohérence surtout du style et des couleurs. La cuisine et les accessoires peuvent changer entre les plans.
- Gros plans et cadrages variés, caméra stable au sein de chaque clip.
- Sons des gestes et de cuisine, esprit ASMR, sans voix ni musique. Ce parcours ne prépare ni narration, ni musique, ni titres.
- Durée totale indicative, 45 secondes par défaut ; clips de 5 à 15 secondes selon le contrat H3 actuel. Les durées de rendu sont quantifiées par le moteur. Le format vertical 9:16 est modifiable.
- La création KREA2 applique le checkpoint et les LoRA du preset sélectionné, avec la recette KREA2 + Flux Klein existante. Les plans utilisent la composition MiniMax depuis le plat, puis une édition locale pour leur arrivée éventuelle. H3 utilise les réglages de l’usine et un seul plan par clip, première image seule ou première/dernière image, sans DLSS automatique.

## Historique et reprises

Les commandes de génération portent une identité persistante et un instantané des paramètres. Le rejeu d’une commande retrouve ses tâches ; il ne double pas le lot. Les liens aux projets enfants sont sauvegardés avant la génération. Les essais conservent les images et les références précises utilisées. Chaque régénération produit un nouvel essai sans effacer le précédent.

Les modifications visuelles rendent les images concernées obsolètes ; modifier une action, une durée ou les images signale les anciens clips. L’export refuse les clips sélectionnés qui ne correspondent plus aux plans et images actuels. Réordonner les plans ne rend pas leurs clips obsolètes.

**Pause après l’étape** empêche les tâches suivantes. Les traitements déjà transmis restent suivis. **Abandonner les étapes restantes** retire le travail non encore démarré ; les sorties terminées et les essais restent conservés. Après redémarrage, les lots sont suspendus, les résultats externes déjà soumis sont récupérés et aucun appel de préparation interrompu n’est rejoué silencieusement. Une erreur conserve son diagnostic ; la reprise manuelle du plan crée un essai distinct.

Les routes de consultation n’envoient aucun nouveau travail aux modèles. L’export lit les vidéos existantes et ne les réencode pas. Les fichiers ZIP temporaires sont supprimés après téléchargement.

## Organisation

- Contrats purs : `domain/cooking_recipes.py`.
- Coordination, prompting et adaptateurs : `application/cooking_recipes.py`, `cooking_recipe_prompting.py`, `cooking_recipe_production.py`.
- Index et projets : `workspace/cooking_recipes/`. Références explicites par asset et identifiant de plan ; aucune découverte des médias par chemin.
- Stockage et ZIP : `infrastructure/storage/cooking_recipes.py`, `infrastructure/cooking_recipe_exports.py`.
- HTTP : `/api/recipes`; interface : `recipes.js`, `recipes.css` et section dédiée de `index.html`.

## Vérification et mise en service

Tests préparés dans `tests/test_cooking_recipes.py`, avec ports de rendu simulés : arrêt après les images, paire de bornes et références, idempotence, reprise, obsolescence, conservation des essais, export ordonné, contrats HTTP et stockage. Tests non exécutés conformément à AGENTS.md.

Depuis le checkout actif, l’utilisateur peut lancer :

```powershell
python -m unittest discover -s tests -p "test_cooking_recipes*.py"
```

Puis la suite habituelle `python -m unittest discover -s tests`, notamment les régressions des services KREA2 et Qwen/MiniMax partagés. L’implémentation n’a lancé aucun modèle ni rendu, ni redémarré de service. Charger le backend au prochain redémarrage habituel, puis actualiser le navigateur. La fidélité des mailles, des mains et des gestes reste à qualifier sur les générations choisies par l’utilisateur.
