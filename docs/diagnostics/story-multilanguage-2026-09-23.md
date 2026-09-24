# Fabrication multilangue — 23 septembre 2026

## Correctif : « invalid JSON » lors de la création de la copie

Le fichier `episode-b7e6cc46cf41dc9b5b7acda5a2f3dc2f.json` signalé n’existe pas dans le stockage runtime. La création interroge d’abord l’ID futur pour retrouver une éventuelle copie existante. `LocalEpisodeStore.get()` passait directement par le lecteur JSON, qui enveloppe aussi les erreurs système : le `FileNotFoundError` devenait donc un `StorageCorruptionError`. La branche de création ne pouvait pas continuer.

Le stockage des fabrications vérifie maintenant le fichier avec `_require_regular_file()` avant son décodage, suivant le contrat déjà utilisé par les autres stores. Un épisode absent remonte `FileNotFoundError` ; un fichier existant réellement invalide reste une corruption et n’est jamais remplacé automatiquement. Aucun changement du lecteur JSON partagé ni des documents runtime.

Deux régressions de stockage ajoutées ; la fixture multilangue conserve aussi la nouvelle version renvoyée par la sauvegarde de son histoire source. Contrôles AST et diff uniquement, tests non exécutés. Commande supplémentaire à la main de l’utilisateur : `python -m unittest discover -s tests -p "test_episode_storage.py"`.

## Parcours

Dans Fabrication, ouvrir **3 · Multilangue (optionnel)**. Choisir la langue et le modèle de traduction (Gemma 4 local par défaut), puis les épisodes sources. Une seule version de fabrication par épisode peut être retenue.

Les scènes proposent le dernier essai vidéo réussi par défaut, avec accès aux anciens essais et une prévisualisation. Un prompt préparé sans vidéo est également utilisable lorsqu’aucun essai réussi n’existe dans sa préparation. **Créer la copie** prépare une variante de fabrication indépendante, visible dans le sélecteur de versions et dans Multilangue. La rédaction de l’histoire originale reste commune et inchangée.

- **Traduire pour relire** : un appel par épisode ayant encore des répliques à traduire, puis injection déterministe. La comparaison Original / Traduction permet de corriger les mots et d’enregistrer sans LLM.
- **Tout lancer** : traduction nécessaire, injection, puis vidéos et DLSS dans les files habituelles. Le traitement des autres épisodes continue si l’un d’eux échoue ; l’erreur reste visible.
- **Produire vidéos + DLSS** : disponible quand les traductions sont prêtes. Les étapes réussies sont conservées. Les pauses vidéo restent dans l’onglet Scènes et les traitements utilisent les files existantes.
- **Enregistrer ces répliques** : nouvelle préparation uniquement pour la scène modifiée. Les anciens essais restent consultables ; les scènes inchangées et leurs médias sont réutilisés.

Le parcours Scènes conserve les réglages vidéo habituels et affiche Traduction / Injection, Vidéo et DLSS. Les références et la rédaction sont verrouillées dans la copie. Revenir à une fabrication originale restitue ses commandes habituelles.

## Contrat de conservation

La source est le prompt de l’essai choisi, ses références ordonnées et ses paramètres effectifs : durée, seed (stockée comme chaîne pour éviter un arrondi JavaScript), recette/version, checkpoint, LoRA et options. Chaque scène possède son instantané ; le remplacement ultérieur d’une image dans l’original ne modifie pas la copie. Les sélections périmées sont refusées avant création.

Le LLM ne reçoit aucun droit d’écriture du scénario ou du prompt. Il renvoie uniquement `{translations: [{id, text}]}` pour des identifiants fixes. Chaque ID est obligatoire et unique. Le serveur remplace uniquement les blocs `<d>[Langue] réplique</d>`, sans toucher aux autres caractères : noms, descriptions, caméra, ordre, coupes et intentions restent ceux du prompt source. Les guillemets imbriqués et répliques identiques à plusieurs endroits sont distingués par leur position ; l’extracteur de citations du Plan n’intervient jamais.

Chaque atelier localisé prend le prompt injecté comme référence de validation. Les validateurs des projets originaux restent inchangés. Une tentative de réécriture via le chat H3 ou le rendu direct d’une copie est refusée avant tout appel LLM.

Une scène sans balises de dialogue réutilise sa vidéo source réussie et les variantes DLSS associées dans son propre atelier ; seuls les fichiers immuables sont partagés. Si un rendu/DLSS manque, seule cette étape est mise en file. Si ses paramètres de rendu ont changé, une nouvelle vidéo est nécessaire même pour une scène muette.

## Reprise et traçabilité

Les traductions, préparations, sources et erreurs sont persistées. Un redémarrage signale les traductions interrompues ; **Tout lancer** permet de reprendre. Une traduction déjà injectée ne fait pas de nouvel appel. Les résultats vidéo réussis ne sont pas régénérés à réglages égaux. Les erreurs DLSS peuvent être reprises sans retraduction ni nouvelle vidéo.

Les requêtes de création et de traitement ont une clé d’idempotence ; les répliques utilisent une révision attendue. Une modification est refusée pendant la traduction, la chaîne vidéo ou un rendu/DLSS actif de la scène. Un résultat LLM incomplet conserve son brouillon et son `call_id` dans `localization.job`, sans injection partielle. Les traces utilisent le gateway coordonné existant, avec l’opération `story.dialogue_localization@1.0.0` et l’ID de fabrication.

Stockage H3 : schéma **17**, lecture des schémas 1–16 conservée, provenance `localization_parent_project_id`. Les variantes ne remplacent jamais le résultat de la recherche de l’atelier original par session/révision. Les fabrications restent des documents de schéma 1 avec une extension `localization` versionnée.

## Limites explicites

- Pas de doublage audio sur la même vidéo : les scènes parlées sont régénérées. Une seed identique ne garantit pas des images identiques lorsque les paroles changent.
- Les inscriptions dans les images et la narration visuelle ne sont pas traduites. Seules les voix balisées dans le prompt sont adaptées.
- Un prompt mal balisé ou une scène du scénario contenant des paroles mais aucun bloc `<d>` ne sont pas classés comme muets. Un essai ancien sans recette explicite n’est pas sélectionnable : ses paramètres ne peuvent pas être reproduits fidèlement.
- L’estimation du débit est informative ; ce n’est pas une mesure audio ni une garantie de synchronisation. Une langue plus longue peut nécessiter de raccourcir une réplique à la relecture.
- Les copies sont des variantes de fabrication liées au projet original, pas des duplications de toute l’historique de rédaction.

## Validation de ce patch

Contrôles statiques : AST Python, compilation syntaxique des scripts dans Chromium sans exécution applicative, contrat DOM et `git diff --check`. Aucun test exécuté, appel LLM, rendu, écriture dans le workspace runtime ou redémarrage.

Régressions ajoutées (services entièrement simulés) : conservation byte à byte des sources, citations imbriquées, validation des IDs, copie des résultats muets, traitement multiépisode, reprise sans nouvelle traduction, correction d’une seule scène, concurrence, sources périmées, idempotence, rendu protégé, stockage, changement de durée, DLSS déjà disponible, routes API et parcours navigateur copie/relecture.

Tests ciblés à lancer par l’utilisateur depuis le worktree actif :

```powershell
python -m unittest discover -s tests -p "test_episode_localization*.py"
python -m unittest discover -s tests -p "test_episodes*.py"
python -m unittest discover -s tests -p "test_episode_reference_refresh.py"
```

Essai conseillé après redémarrage du Lab à un moment approprié et Ctrl+F5 : copier un épisode français en English, traduire pour relire, vérifier une scène parlée et une scène muette, corriger une seule réplique, puis produire. L’original et les essais précédents doivent rester accessibles.
