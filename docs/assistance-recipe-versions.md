# Recettes d'assistance et rangement vidéo

## KREA2 Assisted

La recette d'assistance est indépendante du checkpoint KREA2, du workflow ComfyUI et des recettes Batch publiées. `1.0.0`, affichée « V1 · classique », conserve les prompts et la construction du contexte du snapshot `b63197f`. Les versions sont définies dans des modules distincts `application/krea2_assisted_v1.py`, `krea2_assisted_v2.py` et `krea2_assisted_v3.py` ; V1/V2 restent inchangées.

Le choix se fait à la création du projet. `assistance_recipe_version` est enregistré sur le projet et chaque tour utilisateur/assistant, puis exposé par l'API. La recette reste liée au projet ; il n'existe pas encore de changement de recette en cours de conversation. Les schémas de stockage 1 et 2 sont lus comme V1, sans réécriture globale des historiques. Le schéma 3 exige la référence explicite ; une version non implémentée est refusée avant un nouvel échange. L'opération technique V1 reste `creation_chat@0.3.0` ou `recipe_chat@0.3.0` afin de préserver son identité historique dans le journal.

V1, V2 `2.0.0` et V3 `3.0.0` sont disponibles dans le catalogue du service. **V3 · corrections visuelles · expérimental** est sélectionnée par défaut dans le formulaire de création ; un choix explicite V1/V2 est conservé lors du rafraîchissement du catalogue. Les clients API sans version explicite gardent le défaut historique V1. Les évolutions V2 sont décrites dans `experimental-prompts-2026-09-05.md`. La validation mentionnée plus bas concerne uniquement le premier patch de rangement/versionnement, antérieur à V2.

### V3 : demandes de suppression (7 septembre 2026)

V3 remplace la règle V2 qui autorisait une exclusion courte par une consigne de description du résultat visible : préciser ce qui occupe la zone concernée, retirer l'élément refusé et les formulations qui continuent à le suggérer (structure, action ou traitement visuel), préserver les autres choix de l'utilisateur. L'explication de l'exclusion reste dans la réponse française ; le prompt image décrit la scène souhaitée. Après des échecs répétés, reformuler cette scène plutôt qu'allonger les négations ou les synonymes. Aucun filtrage automatique des mots ni validation lexicale du prompt.

Exemple à évaluer manuellement : après « pas de planches » dans un arbre creux, décrire une cavité au cœur d'un unique tronc, avec des surfaces continues de bois rugueux, plutôt que conserver « architectural interior » et ajouter « no planks, boards, beams ». Les essais observés ne permettent pas d'attribuer l'échec à la seule négation ; aucun gain de qualité n'est encore mesuré.

Le contexte compact et le writer de publication restent ceux de V2. Toujours un seul appel par échange, mêmes limites de sortie, mémoire/branches et presets ; référence initiale analysée au départ seulement, puis renvoyée uniquement sur demande via l'inspiration. Les opérations journalisées sont `krea2.assisted.creation_chat@3.0.0` et `krea2.assisted.recipe_chat@3.0.0`. Aucun workflow, checkpoint, réglage de rendu ou schéma de stockage changé. Un ancien atelier reste en V1/V2 : créer un nouvel atelier V3 pour comparer.

Cache Assisted JS `20260907.1`. Tests préparés dans `test_krea2_assistance_versions.py`, `test_krea2_assisted_v2.py`, `test_krea2_assisted_branches.py`, `test_krea2_assisted_web.py` et `test_krea2_assisted_ui.py` : versions persistées, empreinte V2, contexte compact, référence non répétée, feedback/branches, catalogue et défaut UI. **Non exécutés ; l'utilisateur les lance.** Aucun appel LLM ni génération lancé pour ce patch.

## KREA2 Edit

Depuis le 8 septembre 2026, **Modifier avec KREA2** propose un sélecteur par étape : V3 « Modifications ciblées », défaut d'un nouvel atelier, et V2 « Description complète », conservée pour comparaison. Un échange enregistré garde sa version ; la réouverture restaure la dernière utilisée. Le choix s'applique au prochain échange sans changer le prompt ou les réglages existants. Ce versionnement est indépendant de Création assistée. [Utilisation, contrats et tests](krea2-edit-prompting.md).

## Vidéo

Les sélecteurs montrent les parcours `1.0.0` à trois, deux ou une étape. H3 Base sélectionne **Exploration guidée · 3 étapes** par défaut ; son ancienne compacte `0.4.0` est désormais historique. Ref2V garde sa compacte expérimentale `0.5.0` visible et sélectionnée par défaut. Le volet « Autres recettes » permet d'afficher :

- « Avancées et spécialisées » : H3 multi-plan `0.1.0`, interview d'animal `0.2.0`, Ref2V multi-plan structuré `0.2.0` et multi-plan direct `0.2.0`.
- « Versions historiques » : autres versions déjà présentes dans ces sélecteurs.

Une version sélectionnée, notamment celle d'un ancien run verrouillé, reste visible même si sa catégorie est masquée. Revenir au standard remasque les autres versions. La politique d'affichage est commune aux deux sélecteurs, dans `lab-core.js`. Aucun manifeste, prompt vidéo, workflow ni historique n'est supprimé ou modifié.

Le choix d'un ancien cookbook pour un nouveau run conserve le comportement existant : le profil Brief reste celui choisi par le frontend pour cette famille. Ce rangement ne transforme pas les anciens cookbooks en snapshots complets du parcours. Les nouvelles recettes expérimentales fixent et vérifient explicitement le couple profil Brief / cookbook Plan-Writer ; une session ouverte conserve son profil enregistré.

## Validation

Tests de lecture des schémas historiques, persistance projet/tours, rejet d'une version inconnue et empreintes des deux prompts système comparées au snapshot. Le test Chromium vérifie le dévoilement des catégories, le maintien d'une sélection historique verrouillée et l'absence de duplication des contrôles ; il vérifie aussi la syntaxe des scripts modifiés. Il utilise un Chromium local lorsqu'il est installé et est ignoré sinon. Il ne lance ni serveur GPU ni rendu.

Validation du 5 septembre : 762 tests passent en 81,382 s, test Chromium exécuté. Les 291 fichiers `krea2_assisted/*/project.json` des deux workspaces ont été désérialisés en lecture seule sans erreur ; projets et tours reprennent V1. Aucun smoke complet avec rendu GPU n'a été exécuté.
