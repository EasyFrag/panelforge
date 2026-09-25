# Miniatures des épisodes

La carte **Miniature de l’épisode** apparaît avant la scène 1 dans Fabrication → Scènes. Les nouveaux modèles produisent un PNG 1080 × 1440 (3:4) indépendant. Elle ne modifie ni les scènes, ni les prompts vidéo, ni le montage, ni les sorties DLSS.

## Parcours

- **Lancer prompts + vidéos** inclut par défaut la miniature si elle manque. Décocher la case permet de lancer uniquement les scènes. Une miniature existante est conservée.
- Sans modèle de série, Qwen compose un modèle à partir de deux personnages distincts et d’un décor disponibles. Le titre public est celui de la série dans la bibliothèque ; le numéro vient de sa numérotation éditoriale. Les états archivés ou dont l’image est obsolète sont exclus.
- Qwen écrit le titre stylisé dans le modèle initial. Le numéro est ajouté en **Outfit** gras par Pillow, sans appel LLM. L’alternative **Police intégrée · titre exact** demande à Qwen un visuel sans texte et dessine aussi le titre avec la police intégrée.
- Les épisodes suivants réutilisent le même visuel, le titre et le gabarit. Seul le numéro change. Les variantes de langue gardent le numéro éditorial.
- **Modifier le modèle** permet de choisir un modèle enregistré, d’importer une image, ou de créer un nouveau modèle Qwen avec jusqu’à **16 références** et une direction visuelle facultative. Chaque image a un rôle : premier plan, arrière-plan, décor, objet important ou style seulement. Un modèle importé doit être sans ancien numéro ; il est recadré au centre au format 3:4. Prévoir des marges autour du titre déjà présent. Le titre peut être conservé dans l’image ou ajouté avec la police intégrée choisie.
- Le modèle choisi devient celui de la série pour les prochaines miniatures. Les images déjà produites restent attachées à leur version. Le numéro peut être corrigé pour cette miniature sans réorganiser la bibliothèque.
- **Télécharger le PNG** exporte l’image seule. Aucun export vidéo n’intègre la miniature.

## Déplacer le bandeau d’une miniature existante

Sur une miniature prête, cliquer **Déplacer le bandeau**. L’aperçu reconstruit le fond et le titre depuis le modèle d’origine, sans le bandeau ajouté par l’application. Glisser le bandeau avec la souris ou au tactile, utiliser les flèches du clavier (Maj pour un pas plus grand), ou les curseurs Horizontal / Vertical. Les boutons **En haut**, **Au centre**, **En bas** et **Position d’origine** donnent des points de départ.

**Enregistrer la position · sans IA** produit uniquement un nouveau PNG local ; aucun appel Qwen, LLM, vidéo ou DLSS. L’ancienne miniature reste dans l’historique. La position est enregistrée par miniature et retrouvée à la réouverture. La case **Garder cette position pour les prochains épisodes de cette série utilisant ce modèle**, cochée par défaut, mémorise aussi le placement pour les nouvelles miniatures de cette série avec ce modèle. Les épisodes déjà produits ne changent pas. Un modèle différent repart de son placement par défaut.

Le titre dessiné par Qwen reste dans l’image et n’est pas déplacé. Pour le cas d’un titre placé en bas, remonter le bandeau libère ce titre. Un bandeau déjà présent dans une image importée ne peut pas être retiré par cette fonction : importer un modèle sans ancien numéro.

## Galerie et corbeille

**Modifier le modèle** ouvre la galerie pour la série actuelle. Le sélecteur conserve les chemins Nouveau modèle Qwen et Importer. La galerie affiche une image, un titre, la date, le format et l’utilisation du modèle : **Actuel pour cette série**, **Utilisé par N épisodes**, **Retenu pour une série** ou **Essai non retenu**. Le modèle actuel est placé en premier ; les autres se trient par date récente, ancienne ou titre. Filtres : Cette série, Essais non retenus de cette série, Toutes les séries, Corbeille ; recherche par titre.

Cliquer une image la sélectionne sans appel de génération. **Appliquer et préparer la miniature** applique explicitement le modèle choisi à cet épisode. **Mettre à la corbeille** retire uniquement un essai non utilisé de la liste normale. **Restaurer** le rend de nouveau sélectionnable. Les modèles liés à un épisode courant, à une série ou à une reprise de traitement sont protégés, avec vérification côté serveur au moment de l’action. Les images d’archives et les assets Qwen restent conservés ; la corbeille désencombre le sélecteur sans libérer l’espace disque.

Les deux éditions contrôlent les révisions : si le modèle ou la miniature a changé ailleurs, actualiser la galerie ou rouvrir le réglage du bandeau. Aucune modification des scènes n’est déclenchée.

## Personnages et typographie

Dans **Modifier le modèle → Nouveau modèle avec Qwen**, sélectionner les références puis affecter leur rôle. Par exemple : Kiwina et le second personnage central au **Premier plan**, les autres personnages à **Arrière-plan**, et le lieu à **Décor**. Les personnages principaux doivent être dominants ; les secondaires restent reconnaissables derrière. La limite technique est 16 images dans ce workflow, pas une garantie de lisibilité avec 16 personnages : le compteur de rôles aide à garder deux ou trois protagonistes principaux.

Deux habillages de titre sont proposés avec aperçu des polices :

- **Pop contrasté** : lettres massives, contour sombre, relief citron vert, face blanc crème. En mode Police intégrée : Outfit Black.
- **Affiche cinéma** : lettres condensées très grasses, ivoire et ombre ambrée. En mode Police intégrée : Barlow Condensed Black.

En mode titre Qwen, l’aperçu est une direction esthétique : la forme des lettres reste interprétée par le modèle. En mode Police intégrée, Qwen dessine un visuel sans texte et le titre exact est composé localement avec la police choisie. Aucun LLM de rédaction ne prépare le prompt ; les rôles et le style sélectionnés sont traduits directement en instructions.

Les nouveaux modèles utilisent `grid-cover-v3`, en **3:4**. Ce cadrage correspond à la capture de grille fournie par l’utilisateur ; il ne prétend pas couvrir tous les affichages des plateformes. Le titre descend dans la zone de 10 à 29 % de la hauteur, les visages restent au centre (33 à 72 %), et le badge est remonté dans la zone de 80 à 91 %. Le PNG conserve 130 pixels sous le badge. Qwen reçoit ces zones réservées ; la composition locale assure le placement exact du texte ajouté avec Police intégrée.

Le titre à dessiner est fourni seul, entre guillemets, à la fin du prompt. L’ancienne formulation plaçait le mot anglais `ONCE` juste après le titre et pouvait provoquer son impression dans l’image ; cette instruction a été retirée. Cela ne retouche pas une image déjà générée. Pour corriger une miniature contenant ce mot ou un titre trop près du bord, choisir **Modifier le modèle → Nouveau modèle avec Qwen**. Une image importée contenant déjà du texte ne permet pas de déplacer ses lettres automatiquement.

Les modèles `outfit-cover-v1` et `poster-cover-v2` restent en 1080 × 1920 (9:16), avec leurs positions d’origine, lors de leur réutilisation. Aucun recadrage silencieux des images existantes. Les rôles, la police, le style, le gabarit et le format de sortie sont associés à la version du modèle ou à la miniature ; l’interface affiche les dimensions correspondantes.

## Traitements et reprise

La composition utilise le service Qwen existant, en 3:4 / 2 MP / 25 steps / CFG 1 pour les nouveaux modèles, avec son workflow et sa file GPU. Le canevas Qwen est de 1248 × 1664 pixels (dimensions arrondies selon le workflow), puis le PNG est exporté en 1080 × 1440. Il n’y a pas de nouvel appel de conversation ou de rédaction. La tâche est réservée avant les vidéos de cette chaîne, sans interrompre un travail déjà en cours. Le premier prompt vidéo peut se préparer pendant le rendu de la miniature.

Un échec de miniature est indiqué dans sa carte et n’empêche pas les vidéos/DLSS. Une pause de la chaîne arrête les prochaines scènes ; la miniature déjà réservée reste un travail Qwen indépendant et peut terminer. La réouverture de l’atelier retrouve le rendu Qwen par ses identifiants et termine la typographie sans nouvelle génération. Une interruption avant la mise en file donne une erreur relançable.

Le registre atomique `workspace/episode-thumbnails/index.json` relie explicitement les séries, versions de modèles, fabrications et assets. Les fichiers images sont dans le stockage d’assets existant. Une nouvelle tentative conserve l’ancienne miniature et son historique ; l’échec d’un nouveau modèle restaure le modèle de série précédent.

Polices : Outfit Black et Barlow Condensed Black, fichiers originaux et licences SIL OFL 1.1 inclus dans `src/panelforge/infrastructure/fonts/`. Source et empreinte dans son README.

## Vérification utilisateur

Aucun appel réel ni test fonctionnel n’a été lancé pendant l’implémentation. Quand les traitements en cours sont terminés, redémarrer le Lab du worktree actif et recharger l’interface avec Ctrl+F5.

1. Sur un épisode avec références prêtes, vérifier la carte avant Scène 1 et son numéro. Ouvrir les réglages pour contrôler le titre et les références, puis préparer la miniature.
2. Sur l’épisode suivant de la même série, préparer la miniature : aucune nouvelle tâche Qwen ; même fond/titre, nouveau numéro.
3. Relancer la chaîne sur un épisode dont la miniature existe : conserver la même image.
4. Importer une image modèle et vérifier le PNG téléchargé. Modifier explicitement le numéro : aucune modification des scènes ni de leurs prompts.
5. Créer un modèle avec plus de quatre images, deux personnages devant et les autres derrière ; vérifier que les rôles restent enregistrés à la réouverture. Comparer Pop et Cinéma, puis le mode Police intégrée pour un titre exact.
6. Vérifier le nouveau PNG 1080 × 1440, les marges au-dessus du titre et sous le numéro, et l’absence de texte parasite. Réutiliser également un ancien modèle pour confirmer le maintien du 9:16.
7. Déplacer le bandeau d’une miniature existante, enregistrer puis rouvrir : position conservée, titre dégagé, aucun nouvel appel Qwen. Vérifier la mémorisation sur une nouvelle miniature de la même série et la conservation des épisodes déjà produits.
8. Dans la galerie, filtrer les essais, mettre un modèle inutilisé à la corbeille puis le restaurer. Un modèle utilisé par un autre épisode doit rester protégé.
9. Vérifier la reprise d’une tâche Qwen et le comportement d’une erreur de miniature : les scènes doivent continuer.

Tests ciblés préparés (services simulés ; le test de typographie dessine une image synthétique locale uniquement) :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_episode_thumbnails*.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_qwen_edit.QwenEditTest.test_workflow_composition_accepts_portrait_grid_dimensions
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_episodes.EpisodeTest.test_thumbnail_is_queued_before_prompt_and_finishes_before_video tests.test_episodes.EpisodeTest.test_thumbnail_failure_does_not_prevent_scenes_or_dlss
```

Le test DOM utilise Chromium local s’il est installé ; sinon il est ignoré. Il contrôle la place de la carte, le choix de modèle, la galerie et sa corbeille, le déplacement du bandeau au clavier et au pointeur, la persistance, le numéro, le double clic et l’absence d’appel aux endpoints de scène.
