# Images d’inspiration et branches KREA2 Assisted

## Utilisation

La **référence initiale** est envoyée au premier échange seulement, en V1 comme
en V2. Si cet échange échoue ou est interrompu, elle reste jointe à sa reprise
jusqu’à une première réponse acceptée. Ensuite, le prompt courant et les
échanges disponibles portent les descriptions déjà obtenues ; les pixels ne
sont plus renvoyés. Pour la faire examiner à nouveau, joindre cette image via
**＋ Image d’inspiration**. Un changement de branche, même vers une conversation
vide, ne déclenche pas de nouvel envoi automatique après cette première réponse.
Les projets existants ayant déjà une réponse suivent aussi cette règle, sans
modifier leurs anciens échanges ni ajouter un appel d’analyse ou de résumé.

Le bouton **＋ Image d’inspiration** joint une image au prochain échange. Le
**Résultat à corriger** sélectionné dans la galerie reste joint lui aussi : les
deux aperçus sont visibles ensemble. L’image importée est conservée sur son
message et peut être réutilisée, mais elle n’est pas automatiquement renvoyée
aux échanges suivants. Ces images guident le LLM qui écrit le prompt ; elles
ne deviennent pas des entrées du moteur KREA2 T2I.

Deux actions sur un essai réussi répondent à deux besoins différents :

- **Feedback** continue la conversation actuelle avec cet essai comme résultat
  à examiner. Il ne change pas le point de conversation.
- **Repartir d’ici** crée une branche avec la conversation disponible au moment
  de la création de cet essai, son prompt exact, son checkpoint image, ses LoRA,
  son ratio, sa résolution cible et sa seed. Le modèle LLM et la langue du
  prompt enregistrés à ce point sont également repris. L’image devient le
  feedback de la nouvelle piste.

L’**Arbre des explorations**, replié par défaut au-dessus de la discussion,
affiche les pistes avec leur miniature, leur origine et la piste active.
Cliquer sur une autre piste restaure sa conversation et ses réglages. Les
essais de toutes les pistes restent dans la galerie, avec leur origine.
Un rendu lancé sur une autre branche peut terminer sans déplacer la discussion.

Les modifications du prompt et des réglages encore présentes dans l’éditeur
sont sauvegardées sur la piste quittée lors d’un changement de branche. Le
message non envoyé, l’image d’inspiration en attente et la trace affichée sont
vidés lors du changement, pour ne pas les transporter dans l’autre discussion.

La référence initiale, l’intention initiale et la version d’assistance restent
liées au projet. Les exports et publications restent des résultats du projet.
Le brouillon de recette est conservé en revenant sur une piste ; une nouvelle
branche démarre sans reprendre le brouillon de la direction abandonnée.

## Contexte et compatibilité

Chaque nouvel essai enregistre explicitement sa branche et le dernier ID de
message disponible **avant le rendu**, indépendamment de son délai d’exécution.
Plusieurs seeds au même point partagent ce point ; elles ne créent pas de
branches automatiquement. Un prompt modifié à la main reste celui de l’essai.

Les recettes V1 et V2 reçoivent uniquement la conversation de la piste active.
Leur fenêtre habituelle de contexte reste appliquée ; l’application ne transmet
ni l’arbre complet ni les échanges ultérieurs d’une autre piste. Aucun appel
LLM de résumé ou de branchement n’est ajouté. Cela restaure le contexte
enregistré, sans garantir une réponse identique d’un modèle non déterministe.

Les projets des schémas 1, 2 et 3 restent lisibles. Leurs anciens essais n’ont
pas de point de conversation exact. Ils proposent **Nouvelle piste · image +
prompt**, avec une conversation vide, plutôt qu’un retour historique supposé.
La référence reste conservée au projet, mais n’est pas renvoyée automatiquement
si le projet a déjà une réponse acceptée ; l’intention initiale reste dans le contexte. Les
nouveaux essais de ces projets acquièrent ensuite des points précis.

Le schéma 4 conserve les branches et une table de messages partagés par ID ;
les préfixes communs ne sont pas recopiés pour chaque essai. La version de
recette n’est pas changée par cette évolution de stockage. Aucun historique
existant n’est migré en masse : le nouveau format est écrit à la sauvegarde.

Les changements de branche sont refusés pendant un échange LLM. Les requêtes
de conversation, de rendu et de changement de piste issues d’un onglet resté
sur une ancienne branche sont refusées. Le rafraîchissement d’un rendu ne
réapplique pas une réponse reçue avant une navigation.

## Vérification par l’utilisateur

Tests ajoutés, **non exécutés pendant l’implémentation** :

- `tests/test_krea2_assisted_branches.py` : reprise au préfixe exact, conservation
  de la suite initiale, branches imbriquées, réouverture, seed 0, anciens formats,
  contexte V1/V2 sans la suite abandonnée, deux images jointes, requête périmée,
  interruption d’un flux et fin de rendu sur une autre piste.
- `tests/test_krea2_assisted_web.py` : parcours HTTP de branchement et retour,
  sauvegarde du prompt édité, refus d’un onglet périmé, sans modèle ni renderer.
- Contrats UI et attentes de version du stockage actualisés.

Contrôles effectués : lecture de syntaxe Python par AST, compilation syntaxique
du script JavaScript sans invocation, contrôle du diff. Aucun test, appel LLM,
rendu, lancement du serveur ou redémarrage n’a été effectué.

Après chargement du nouveau backend et rechargement de la page, vérifier :
feedback + inspiration simultanés ; nouvel essai → poursuite de discussion →
repartir de l’essai ; absence de la suite abandonnée ; retour à l’autre piste ;
réouverture du projet avec la bonne branche, son prompt et sa seed.
