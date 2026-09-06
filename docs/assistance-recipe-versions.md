# Recettes d'assistance et rangement vidéo

## KREA2 Assisted

La recette d'assistance est indépendante du checkpoint KREA2, du workflow ComfyUI et des recettes Batch publiées. `1.0.0`, affichée « V1 · classique », conserve les prompts et la construction du contexte du snapshot `b63197f`. Son implémentation est dans `application/krea2_assisted_v1.py` ; ajouter une implémentation distincte pour V2, sans réécrire V1.

Le choix se fait à la création du projet. `assistance_recipe_version` est enregistré sur le projet et chaque tour utilisateur/assistant, puis exposé par l'API. La recette reste liée au projet ; il n'existe pas encore de changement de recette en cours de conversation. Les schémas de stockage 1 et 2 sont lus comme V1, sans réécriture globale des historiques. Le schéma 3 exige la référence explicite ; une version non implémentée est refusée avant un nouvel échange. L'opération technique V1 reste `creation_chat@0.3.0` ou `recipe_chat@0.3.0` afin de préserver son identité historique dans le journal.

V1 et V2 expérimentale `2.0.0` sont disponibles dans le catalogue du service. V2 est sélectionnée par défaut dans le formulaire de création ; un choix explicite V1 est conservé lors du rafraîchissement du catalogue. Les clients API sans version explicite gardent le défaut historique V1. Les évolutions sont décrites dans `experimental-prompts-2026-09-05.md`. La validation mentionnée plus bas concerne uniquement le premier patch de rangement/versionnement, antérieur à V2.

## Vidéo

Les sélecteurs montrent les options expérimentales H3 Base `0.4.0` et Ref2V `0.5.0`, sélectionnées par défaut, et les nouveaux parcours `1.0.0` à trois, deux ou une étape. Le volet « Autres recettes » permet d'afficher :

- « Avancées et spécialisées » : H3 multi-plan `0.1.0`, interview d'animal `0.2.0`, Ref2V multi-plan structuré `0.2.0` et multi-plan direct `0.2.0`.
- « Versions historiques » : autres versions déjà présentes dans ces sélecteurs.

Une version sélectionnée, notamment celle d'un ancien run verrouillé, reste visible même si sa catégorie est masquée. Revenir au standard remasque les autres versions. La politique d'affichage est commune aux deux sélecteurs, dans `lab-core.js`. Aucun manifeste, prompt vidéo, workflow ni historique n'est supprimé ou modifié.

Le choix d'un ancien cookbook pour un nouveau run conserve le comportement existant : le profil Brief reste celui choisi par le frontend pour cette famille. Ce rangement ne transforme pas les anciens cookbooks en snapshots complets du parcours. Les nouvelles recettes expérimentales fixent et vérifient explicitement le couple profil Brief / cookbook Plan-Writer ; une session ouverte conserve son profil enregistré.

## Validation

Tests de lecture des schémas historiques, persistance projet/tours, rejet d'une version inconnue et empreintes des deux prompts système comparées au snapshot. Le test Chromium vérifie le dévoilement des catégories, le maintien d'une sélection historique verrouillée et l'absence de duplication des contrôles ; il vérifie aussi la syntaxe des scripts modifiés. Il utilise un Chromium local lorsqu'il est installé et est ignoré sinon. Il ne lance ni serveur GPU ni rendu.

Validation du 5 septembre : 762 tests passent en 81,382 s, test Chromium exécuté. Les 291 fichiers `krea2_assisted/*/project.json` des deux workspaces ont été désérialisés en lecture seule sans erreur ; projets et tours reprennent V1. Aucun smoke complet avec rendu GPU n'a été exécuté.
