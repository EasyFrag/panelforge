# Quatre LoRA de rendu — H3 et REF2V

Implémenté le 10 septembre 2026 dans le checkout `D:\Code\localQ\.panelpatch`.

Les nouvelles recettes H3 **0.1.6**, REF2V **0.2.4** et BUNNY **0.1.3** acceptent jusqu’à quatre LoRA distincts. Dans le bloc LoRA existant, **Ajouter un LoRA** révèle une ligne à la demande. Les flèches ↑/↓ déplacent le fichier avec ses forces et son activation ; × retire la ligne. Le compteur indique le nombre de lignes configurées. Les lignes désactivées restent enregistrées et comptent dans les quatre emplacements.

Le basique garde le profil Standard par défaut, ses MP initiaux/après upscale à 0,2/0,2 modifiables et la réutilisation du seed. Chaque LoRA possède une force et le réglage CLIP reste commun. BUNNY garde **Combat V2 puis Motion Repair**, chacun à **0,60 en passe 1 et 0,20 en passe 2** ; les deux emplacements supplémentaires sont facultatifs. Chaque passe applique les fichiers actifs dans le même ordre, avec ses propres forces. Les branches MODEL repartent de la source checkpoint/Turbo commune ; aucune accumulation des LoRA de passe 1 dans le MODEL de passe 2. Turbo, preview, checkpoints et paramètres de sampling conservent leur comportement.

Les recettes précédentes restent disponibles avec leur limite de deux LoRA. Une reprise historique garde sa recette ; choisir la nouvelle version de recette de rendu pour ajouter un troisième ou quatrième fichier. Le brouillon de l’éditeur adopte alors le contrat actuel, sans modifier l’essai d’origine. Aucune ligne n’est supprimée silencieusement si une configuration trop grande est restaurée dans une ancienne recette : une erreur invite à changer de recette ou retirer des lignes.

## Contrats et compatibilité

- `H3VideoLoraStack@0.2.0` : maximum quatre entrées. Le contrat `0.1.0` reste lisible et limité à deux ; les anciennes sélections uniques restent prises en charge.
- La capacité et les identifiants des nœuds additionnels BUNNY appartiennent aux manifests versionnés. Les graphes API de base sont identiques aux recettes précédentes. Le basique utilise les entrées dynamiques du chargeur rgthree existant.
- Validation API, applicative et compilation : cinquième ligne refusée, fichiers distincts, forces contrôlées, ressources actives vérifiées avant création puis avant upload. La limite de la recette s’applique aussi aux requêtes directes.
- Structure de stockage inchangée : schéma H3/REF2V **13**, aucune migration de projet. Ordre, forces, activation et version sont conservés dans les essais, leur reprise, le feedback, les conversions et les candidats DLSS.
- Module partagé H3/REF2V `h3-loras.js`, cache **20260910.10**. Le polling ne reconstruit pas les lignes. Aucun changement des recettes de prompt Classique/Combat.

## Validation à effectuer par l’utilisateur

Après ses traitements, redémarrer le Lab et recharger la page. Choisir une recette actuelle, ajouter deux lignes BUNNY ou quatre lignes basiques, modifier les forces, déplacer/désactiver une ligne, puis vérifier la reprise des réglages. Comparer à deux LoRA avec les mêmes seed, prompt et paramètres.

Tests préparés, **non exécutés pendant l’implémentation** :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_h3_four_loras tests.test_h3_four_loras_browser tests.test_h3_multiple_loras tests.test_h3_bunny_browser tests.test_h3_checkpoints
```

Les tests utilisent des transports simulés et des dossiers temporaires. Le test navigateur utilise Chromium local s’il est installé. Contrôles d’implémentation limités à l’analyse syntaxique Python/JavaScript, aux manifests, aux empreintes des graphes et au diff ; aucun import applicatif de vérification, appel LLM, rendu ou redémarrage. La qualité et le coût GPU de quatre LoRA restent à observer avec les fichiers choisis.
