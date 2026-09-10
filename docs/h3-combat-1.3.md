# Combat 1.3 — Direction cinématographique

Implémenté le 2026-09-10 dans `D:\Code\localQ\.panelpatch`, branche `h3-video-lora`. **Deux appels uniquement pour cette version**, conformément à la dernière demande : Plan puis rédaction. Pas de Brief ni de passe cachée. Les anciennes versions conservent leurs parcours un, deux et trois appels ; Classique garde ses règles.

## Utilisation

Dans H3 ou REF2V, choisir **Combat → 1.3 · Direction cinématographique · 2 appels**. Un nouvel atelier Combat sélectionne cette version. Les ateliers existants restent sur leur version enregistrée.

- **Orientation** : Libre / mixte, Corps à corps, Armes, nouvelle option **Pouvoirs / magie**. Cette dernière fait des pouvoirs les attaques principales, avec origine, trajectoire, cible, conséquence et réponse adverse ; le contact devient facultatif. La morphologie reste distincte des effets émis.
- **Quantité d’action** : les quatre niveaux restent indépendants du nombre de plans. Déchaîné demande davantage de variations de vitesse, d’amplitude, de déplacements et de ripostes simultanées. La fantasy peut exploiter ses pouvoirs à grande échelle ; un duel réaliste conserve ses moyens physiques. Pas d’ajout automatique de mort, magie ou personnages.
- **Nombre de plans** : un à six, ou Auto. Une trajectoire caméra peut comporter deux phases continues sans devenir deux plans. La liberté caméra reste indépendante : caméra fixe et action maximale sont compatibles.
- Décrire l’arc voulu et les moyens de chaque adversaire, puis générer/valider le Plan et rédiger le prompt. Les révisions supplémentaires restent des actions explicites de l’utilisateur.

Les exemples pédagogiques couvrent pouvoirs à distance, armes lourdes, armes rapides, fantasy aérienne et corps à corps. Un exemple complet intention/Plan est choisi localement selon orientation et mots explicites de l’intention ; le rédacteur reçoit également son exemple de sortie. Le maximum montre deux phases et de plus grands déplacements ; l’exemple de contraste montre Intense. Ces exemples enseignent la structure, sans imposer leur durée, deux plans, personnages, décor, pouvoirs ou issue aux contrôles réels. Aucun classificateur LLM.

## Contrat et conservation

Contrat `minimax.h3.combat.cinematic_planned_v1`, exclusivement dans les deux recettes `combat.planned@1.3.0` H3/REF2V. Politiques propres 1.3, adoption explicite du bloc identité 1.1.1, de l’audace 1.1.0 et du protocole caméra neutre 0.1.0 ; aucune référence à « latest ».

Chaque plan contient durée, cadrage initial, une ou deux phases (événement d’action, caméra typée, combinaisons), rythme, état de sortie et raccord. La caméra expose mouvement, vitesse, amplitude et cible, avec les restrictions du domaine : shake/POV sans cible ni modificateurs, statique sans vitesse/amplitude. Minimum 500 ms par phase après normalisation des durées. Maximum six plans et douze clauses caméra, seulement pour Combat 1.3.

Le deuxième appel produit un paragraphe d’action par phase. Le compilateur insère directement cadrages, événements, caméra, rythme, états de sortie et raccords ; il les garde dans leur plan. Les consignes et les descriptions du schéma demandent l’anglais pour tous les champs compilés, y compris ceux du Plan. Il n’y a pas de traduction automatique supplémentaire ni de détecteur linguistique prétendant garantir cette consigne.

Les phases caméra sont conservées dans le contexte enregistré, le projet de rendu, les révisions et l’adaptation vers REF2V. Un changement explicite de caméra conserve les emplacements et les instants de coupe ; les phases sans timestamp restent sans timestamp. Réviser les actions du prompt de préparation conserve la structure du Plan ; pour changer cette structure, réviser le Plan puis relancer la rédaction. Après rendu, les consignes demandent de préserver rythme/raccords et permettent leur changement explicite ; leur fidélité sémantique reste à observer.

Sessions au schéma **13** (lecture 1–12), projets H3/REF2V au schéma **10** (lecture 1–9). Aucune migration des ateliers sur disque. Les réglages et la version suivent réouverture, fork, continuation et conversion. Revenir à une ancienne version recrée ses réglages compatibles ; l’option magie appartient exclusivement à 1.3.

Aucun changement de workflow ComfyUI, modèle, LoRA, force, durée de rendu, seed ou mégapixels. Cache des quatre scripts concernés : **20260910.6**. Le socle UI inchangé reste à 20260910.5.

## Vérification et essais utilisateur

Tests préparés dans `tests/test_combat_cinematic.py` : exemples dans les cinq modes d’entrée, mono/six plans, douze phases, caméra fixe, cibles invalides, coupes cachées, perte de phases/raccords, exactitude du nombre d’appels, révisions, réouverture, conversion, fork et lecture des anciens schémas. Régressions navigateur : sélecteur de version, option magie, parcours unique et continuation. Empreintes des **583 fichiers de prompts/profils antérieurs** conservées dans `tests/fixtures/pre_combat_1_3_assets.json`.

**Tests non exécutés par l’agent.** Vérifications statiques : AST Python, syntaxe JavaScript compilée sans invocation, manifests et chemins de blocs, empreintes historiques, HTML et diff. Aucun import applicatif de vérification, appel LLM, génération ou redémarrage de service. Aucun commit/push/tag demandé ou effectué.

Depuis le checkout actif, tests ciblés à lancer par l’utilisateur :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_combat_cinematic tests.test_combat_orientation tests.test_combat_sequence tests.test_combat_identity tests.test_combat_controls_browser tests.test_recipe_picker_browser tests.test_h3_multishot_browser
```

Après rechargement du Lab par l’utilisateur, comparer une même intention et les mêmes références en 1.2 et 1.3, puis Intense/Déchaîné en 1.3 avec les réglages de rendu constants. Examiner séparément Plan, prompt compilé et vidéo : portée des pouvoirs, amplitude des déplacements, retournement d’initiative, cadrages/raccords et ressemblance. Le patch enrichit ce que Qwen peut exprimer ; la fidélité du rendu H3 reste expérimentale.
