# BUNNY dans les ateliers H3 / REF2VA

Intégration du 2026-09-09, recette expérimentale `minimax-h3-bunny@0.1.0`.
Point de restauration publié avant le patch : [`snapshot-avant-bunny-h3-2026-09-09`](https://github.com/EasyFrag/panelforge/tree/snapshot-avant-bunny-h3-2026-09-09), commit `f2a61a5ef47267eef4635a217821e51bf86e3700`.

## Utilisation

Après son redémarrage habituel du Lab et un rechargement de la page, l’utilisateur trouve **Recette de rendu** dans les ateliers H3 Base et REF2VA. **Rendu actuel reste le défaut** : H3 Base 0.1.3 et, depuis la correction des résolutions, REF2V **0.2.1**. Tous deux proposent **MP initiaux 0,2 / MP après upscale 0,2**, modifiables indépendamment, et **Réutiliser le seed coché**. REF2V 0.2.0 reste disponible dans Historique avec sa première passe fixe. BUNNY conserve son preset propre 0,9/0,9 comme sélection supplémentaire. La préparation LLM en 1, 2 ou 3 étapes et la conversation restent communes.

Les brouillons de réglages sont conservés par atelier et recette dans l’onglet. Le changement conserve le prompt, et lors d’un premier passage vers une recette conserve ratio, durée et seed. Revenir à une recette déjà utilisée retrouve son brouillon. Un essai enregistré conserve durablement sa recette et ses paramètres ; **Reprendre prompt + réglages** restaure cet essai, y compris le mode Turbo et les forces du LoRA.

| Contrôle BUNNY | Défaut et comportement |
| --- | --- |
| Modèle | Automatique : FL2VA BF16 pour texte/first/last ; chargeur hybride FL2VA + REF2VA, blocs 25–49, pour REF2VA. Nom affiché. |
| MP avant upscale | **0,9**, modifiable. |
| MP sortie | **0,9**, modifiable. Dimensions et facteur réels affichés après arrondis. |
| Turbo | **Activé**, LoRA technique à 0,7. Décocher le retire du graphe. |
| Calendrier / passe 1 / passe 2 | **9 / 4 / 5** avec Turbo. Premier passage sans Turbo : **30 / 25 / 5**. Chaque mode garde ensuite les ajustements saisis. |
| LoRA vidéo | Un fichier facultatif, deux forces séparées. Exemple importé : Motion Repair **0,6 / 0,2**. Choisir Standard pour ne pas appliquer ce LoRA. |
| Preview | Activée, désactivable ; aperçu léger pendant les deux passes via KJ + `taeh3.safetensors`. |

Le champ calendrier définit les sigmas de départ ; le nombre exécuté est **passe 1 + passe 2**, donc 9 ou 30 avec les profils proposés. La première passe doit rester inférieure au calendrier ; la seconde accepte 3, 4 ou 5 steps. Les contrôles Spectrum et CLIP Last Layer du rendu actuel sont masqués pour BUNNY et refusés côté serveur.

À **×1**, les deux passes restent présentes, mais la taille ne grandit pas. Le moteur accepte uniquement une géométrie sans réduction, de ×1 à ×4 par axe. La cible du contrôle T8 ne dépasse pas 4096 pixels par côté. La même convention que ResolutionSelector est utilisée pour nos champs MP (1024² pixels/MP) ; des dimensions explicites sont transmises à T8, qui conserve les proportions de la première passe sur la grille H3 de 32 pixels. L’affichage des dimensions est plus précis que le seul nombre de MP demandé.

La preview est indicative, limitée à 8 frames, côté maximal 768 pixels, 12 FPS. Elle ne lance aucune diffusion supplémentaire ni décodage complet séparé de la première passe. Sa désactivation conserve le suivi de progression. Le fonctionnement et le coût réels avec les deux passes T8 restent à valider par l’utilisateur.

## Contrats techniques

- Le fichier API utilisateur `(3)` est conservé à l’identique dans `workflows/video.generate.h3-base/minimax-h3-bunny/0.1.0/workflow_api.json`, SHA-256 `8c2f4419f0f121e8cf4aa0e92cac5fd86a6267ca6fba0ad9da3290edf503243b`. Le manifeste porte les liaisons, modèles, entrées, templates de preview/keyframes et phases de progression. Les workflows existants n’ont pas été modifiés.
- L’adaptateur ne garde que le chargeur utile et les branches actives. Le même LoRA est appliqué à deux branches issues du modèle commun ; la seconde force ne s’ajoute pas cumulativement à la première. Attention `comfy kitchen attention`, upscaler fp16, audio natif et paramètres avancés désactivés restent ceux du fichier fourni. Pas de nettoyage GPU automatique ajouté.
- Le mode est explicite dans **les deux conditionnements** : first/last sur leurs entrées dédiées, ou références ordonnées sur les entrées Ref2VA (1 à 9). Aucun changement sémantique silencieux entre références et frames. Le prompt fourni par l’atelier est transmis sans nouvelle réécriture LLM ; l’option musique continue d’utiliser le comportement existant.
- Avant soumission, seuls les contrats `/object_info/<classe>` sont consultés pour les nœuds et modèles du graphe effectivement utilisé. Un nœud, fichier ou tiny VAE manquant produit une erreur explicite ; pas de téléchargement, changement de moteur ou appel modèle automatique. L’essai et son prompt restent disponibles.
- Stockage H3 **schéma 5**, lecture des schémas 1–4. Les nouveaux essais conservent une `RecipeRef` (identité, version, empreinte) et les réglages BUNNY. Les anciens essais sans identité explicite utilisent la recette historique de leur mode. La soumission, les sorties, la récupération après redémarrage, les keyframes et la progression sont résolues à partir de l’essai, indépendamment du sélecteur actuellement affiché.
- Keyframes prélevées dans le décodage final existant, maximum 8, marge 500 ms autour des coupures comme les recettes actuelles. La vidéo, son audio et ses frames rejoignent le même historique. Feedback, reprise, dernière frame et DLSS utilisent les assets de l’essai sélectionné. Les variantes DLSS conservent la recette de génération ; le diagnostic DLSS inclut également sa provenance BUNNY. Le DLSS reste sur Comfy Windows, la génération sur Bucket.
- Cache H3 rendu et CSS : **20260909.4**. Pas de changement du cache DLSS ni de la préparation LLM.

## Vérification préparée

**Tests non exécutés par l’agent.** Contrôles effectués uniquement sur le texte : AST Python, compilation JavaScript sans invocation, champs du contrat HTTP, IDs DOM, liaisons/empreinte du manifeste et comparaison des graphes historiques avec le snapshot.

Commandes à lancer par l’utilisateur dans son environnement habituel :

```powershell
python -m unittest tests.test_h3_bunny tests.test_h3_bunny_browser tests.test_h3_render tests.test_h3_render_controls_browser tests.test_run_lab_build tests.test_dlss
```

Ces scénarios utilisent des ports Comfy/LLM simulés. Le scénario navigateur utilise le DOM et le JS réels, avec HTTP simulé et GPU désactivé. Ils couvrent les cinq modes, l’ordre des références, les branches de modèles et LoRA, Turbo, dimensions, contrats invalides, dépendance manquante, persistance/anciens schémas, import après redémarrage, reprise des réglages, sélection et provenance DLSS.

L’essai réel sur Bucket reste nécessaire pour apprécier les mouvements, la netteté, l’audio, la mémoire et la preview. Le profil sans Turbo 30/25/5 est un point de départ, pas un optimum démontré. Aucun test, appel LLM, génération, installation de dépendance, chargement de modèle ou redémarrage de service effectué pendant ce patch.
