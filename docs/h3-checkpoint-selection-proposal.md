# H3 / REF2V — Choix du checkpoint de rendu

2026-09-10 : **implémentation autorisée et livrée dans le checkout `D:\Code\localQ\.panelpatch`**, après la proposition ci-dessous. Aucun test exécuté, appel LLM, génération ou redémarrage de service.

**Ajout du 11 septembre 2026 : EROS Turbo intégré.** L’inventaire `GET http://bucket:8188/object_info/UNETLoader`, consulté en lecture seule, contient `10Eros_Max_h3_TURBO-hybrid_beta5.safetensors`. Le fichier était installé mais absent du catalogue explicite PanelForge. Il est désormais enregistré pour H3 et REF2V, sous « EROS · Turbo intégré · hybride beta5 », à côté de l’EROS précédent. Aucun changement de modèle par défaut ou de sampling. Pour BUNNY, sélectionner cette variante et décocher « Ajouter le Turbo BUNNY » ; les steps restent ceux choisis par l’utilisateur. Le catalogue est chargé au démarrage du Lab : redémarrer le Lab après les traitements puis ouvrir le sélecteur / Actualiser la liste. Aucun redémarrage ou rendu effectué par l’agent. Régression d’inventaire préparée dans `tests/test_h3_checkpoints.py`, non exécutée ; syntaxe et catalogue contrôlés statiquement. La qualité de cette variante reste à expérimenter par l’utilisateur.

## Utilisation livrée

Sous **Recette de rendu**, ouvrir **Modèle vidéo · Par défaut** et sélectionner **EROS · hybride beta5**. La ligne reste repliable. Le choix porte sur le prochain rendu, sans réécriture du prompt ni modification du seed, des MP, des LoRA ou du Turbo.

Versions actuelles : H3 Latent Speed **0.1.4**, REF2V **0.2.2**, BUNNY **0.1.1**. Les anciennes versions restent dans le sélecteur de recettes. En reprenant un ancien essai, sa version exacte est restaurée ; pour y tester un checkpoint alternatif, sélectionner d’abord la recette actuelle. Le sélecteur de modèle est masqué sur les recettes historiques, qui gardent leur contrat antérieur. Le VideoLab indépendant reste en 0.2.1.

Le checkpoint et son chargement effectif sont conservés dans chaque essai, la reprise des réglages, les brouillons par recette, l’historique et la conversion H3 → REF2V compatible. Une conversion incompatible demande de choisir un modèle compatible, sans changer le choix en silence. Les variantes DLSS héritent aussi de cette provenance. Un choix sans rendu reste un brouillon de l’onglet ; la réouverture après rechargement reprend les réglages du dernier essai ou de l’adaptation enregistrée.

**Par défaut** conserve les graphes précédents exactement. Un checkpoint explicite remplace uniquement leur source commune de modèle par un chargement UNET direct ; les samplers, LoRA, passes, preview et références restent branchés sur cette source. Les IDs et le modèle de nœud alternatif appartiennent aux nouveaux manifests. Le chargeur hybride REF2V n’est pas réappliqué sur EROS. Le Turbo externe BUNNY reste celui choisi par l’utilisateur : aucune détection ou désactivation automatique.

Le catalogue explicite `src/panelforge/infrastructure/presets/h3_checkpoints.json` associe les noms Comfy aux modes compatibles. L’interface propose leur intersection avec les poids installés, et conserve une sélection devenue indisponible. MiniMaxREDMix n’est pas enregistré, son mode restant à qualifier. Un futur checkpoint nécessite une entrée explicite après identification de son chargement ; un nouveau fichier quelconque n’est pas supposé compatible.

Inventaire via le client Comfy de contrôle à timeout court, cache de 60 secondes, bouton **Actualiser la liste**. Pas de lecture d’inventaire de checkpoints à l’ouverture de l’atelier, au polling ou pour le choix par défaut. Première ouverture du sélecteur et validation d’un choix alternatif peuvent remplir le cache. Une erreur est gardée au plus cinq secondes et bloque le checkpoint explicite ; aucun repli silencieux. La préparation valide hors du verrou de rendu, puis l’exécution revalide avant les uploads, en utilisant le même cache.

Stockage H3 au **schéma 11**, lecture des schémas 1–10 ; pas de migration des projets sur disque pendant le patch. Les anciens essais sans sélection explicite n’acquièrent pas artificiellement un modèle. Caches UI `h3-checkpoints.js`, `h3-render-lab.js` et CSS **20260910.7**.

## Vérification et essais utilisateur

Contrôles statiques effectués : AST Python, syntaxe JS sans invocation, JSON, empreintes des workflows et correspondance des bindings, diff. Les trois nouveaux `workflow_api.json` sont identiques octet par octet à leurs prédécesseurs. Les modifications Combat/Classique et leurs assets de prompts restent hors de ce patch ; seuls des numéros attendus de schéma/cache dans les tests existants changent.

Tests préparés, **non exécutés** : matrice des cinq modes avec/sans LoRA et Turbo BUNNY, source unique des deux passes, defaults inchangés, inventaire filtré/cache/absence/panne, rejet avant upload, stockage/reprise/schéma 10, routes HTTP et conversion enregistrée, brouillons et indisponibilité dans les deux ateliers réels avec HTTP simulé. Les tests ne chargent aucun modèle et utilisent des répertoires temporaires.

Depuis le checkout actif, exécution par l’utilisateur :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_h3_checkpoints tests.test_h3_bunny tests.test_h3_bunny_browser tests.test_h3_ref2v_conversion tests.test_ref2v_render_resolution tests.test_run_lab_build tests.test_lab_web
```

Après ses traitements en cours, l’utilisateur peut redémarrer le Lab et recharger la page, puis comparer défaut/EROS à prompt, seed, MP, LoRA et Turbo constants. La compatibilité et la qualité GPU réelles ne sont pas établies par les vérifications statiques. Aucun commit, push ni tag créé ou modifié par ce patch.

## Constat vérifié avant le patch

Lecture GET de `http://bucket:8188/object_info/UNETLoader` et `object_info/MiniMaxH3HybridLoader` : 78 fichiers exposés. Parmi eux :

- `10Eros_Max_h3_hybrid_beta5.safetensors`
- `MiniMaxREDMix-H3-A2Ab1-pruned_redcraft.safetensors`
- `PinkCherry_fl2va_MiniMax_H3_bf16_beta-0.6.safetensors`
- modèles MiniMax FL2VA/REF2VA d’origine BF16/INT8 et hybrides INT8.

Présence confirmée dans le catalogue Comfy, pas d’ouverture des poids, de vérification de leur empreinte ou d’essai d’inférence. Aucun EROS nommé TURBO n’apparaît dans cet inventaire.

Le [dépôt de l’auteur](https://huggingface.co/TenStrip/10Eros-Max/blob/main/README.md) décrit beta5, sa variante non-Turbo et les fichiers TURBO dont la fusion Turbo est intégrée ; l’hybride repose sur le merge H3 delta1024. Le [fichier exact publié](https://huggingface.co/TenStrip/10Eros-Max/blob/main/10Eros_Max_h3_hybrid_beta5.safetensors) correspond au nom exposé par Bucket. La page Civitai n’a pas été accessible dans cette consultation ; ne pas lui attribuer des informations supplémentaires.

Dans le checkout actif : H3 Latent Speed 0.1.3 charge FL2VA BF16 seul. REF2V actuel 0.2.1 assemble FL2VA BF16 et les projections AdaLN de REF2VA BF16 des blocs 25–49. BUNNY 0.1.0 choisit le chargeur simple en H3 et ce même assemblage en REF2V. Le choix de modèle n’est pas exposé comme réglage par essai. Le client Comfy possède déjà `list_unet_models()` et `describe_node()`.

## UX proposée

Une ligne repliable sous la recette de rendu : **Modèle vidéo · Par défaut**. À l’ouverture, un seul sélecteur **Checkpoint** :

- **Par défaut de la recette** — sélection initiale ; conserve exactement le chargement H3 ou hybride REF2V existant.
- **EROS · Hybrid beta5** — filename complet accessible dans le détail.
- Autres checkpoints H3 installés dont le mode/chargement a été identifié ; ne pas afficher indistinctement les 78 modèles image/vidéo.

Une fois EROS sélectionné, le résumé replié reste **Modèle vidéo · EROS beta5** : choix visible sans formulaire toujours déplié. Revenir à « Par défaut » rétablit le comportement de la recette. Pas de nouveau mode de préparation, de recette de prompt EROS, de branche Combat ou d’écran séparé. Le choix concerne le prochain rendu ; le prompt et les anciens essais restent intacts. Pas d’appel LLM lors d’un changement de checkpoint.

## Branchement proposé

Pour tester le fichier EROS hybride lui-même, le charger directement dans H3 comme dans REF2V. **Ne pas seulement remplacer le `base_model` du chargeur hybride actuel**, ce qui réinjecterait ensuite une partie du REF2VA d’origine. La voie « Par défaut » garde son assemblage actuel. Cette proposition de chargement ne constitue pas une validation de la qualité dans chacun des modes.

Étendre les contrats d’essai et de reprise avec une sélection explicite (défaut ou checkpoint identifié) et les modèles effectivement utilisés. Conserver le choix dans les paramètres repris, les brouillons de recette, la conversion H3→REF2V quand compatible, les métadonnées et l’historique. Chaque essai garde sa propre sélection ; reprendre un essai terminé reprend son modèle, pas le dernier choix global. Une ressource devenue indisponible produit un message sans substitution silencieuse.

Les liaisons du modèle, y compris le chargement direct alternatif de REF2V, appartiennent aux nouveaux manifests de workflow versionnés. Garder les anciens manifests intacts. Vérifier le modèle installé et son mode de chargement avant mise en file, sur un inventaire mis en cache et actualisable à la demande ; ne pas ajouter de scan coûteux au polling ou à chaque clic de rendu.

Aucun changement implicite de seed, MP, durée, LoRA ou calendrier BUNNY lors du choix du checkpoint. Le Turbo externe de BUNNY reste un réglage distinct ; EROS installé est la variante sans TURBO dans le nom. Une éventuelle variante EROS-TURBO devra être reconnue explicitement avant de proposer des réglages adaptés, sans supposer qu’elle équivaut au Turbo externe actuel. Les préconisations de sampling de l’auteur ne sont pas transposées automatiquement au pipeline à deux passes.

L’auteur déconseille cache/Spectrum en référence pour la fidélité. Spectrum est déjà désactivé dans le REF2V inspecté, et BUNNY ne propose pas Spectrum ; conserver ces défauts. La qualité/compatibilité avec les deux passes et les LoRA doit être testée par l’utilisateur, indépendamment du simple chargement de poids.

## Tests à préparer au patch

Défaut identique aux graphes actuels pour H3/REF2V et BUNNY ; checkpoint EROS direct sans surassemblage ; modèle effectif identique dans les deux passes ; compatibilité du mode ; sélection absente/renommée ; réouverture, reprise et conversion ; ancien stockage sans sélection explicite ; brouillons/UI/version des manifests ; inventaire sans rafraîchissement bloquant. Tests exécutés par l’utilisateur selon AGENTS.md. Aucun nouveau backend d’exécution nécessaire.
