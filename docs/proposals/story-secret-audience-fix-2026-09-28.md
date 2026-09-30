# Secrets : distinguer public informé et personnages informés

Date : 28 septembre 2026.

## Incident constaté

Projet `story-887454eeb15c4481b9db6a83ff708e3a`, premier brief inspiré de Download(34), édition expérimentale v3. Le premier appel `llm-c85bd97268be4e19bd02d6208c07de62` a produit un arc complet mais invalide :

```json
{"id":"secret-liaison","known_by":["spectateur","char-rene","char-lina"]}
{"id":"secret-paternite","known_by":["spectateur","char-rene","char-lina"]}
```

Le casting déclaré contenait Yanis, Lina et René. Le mot « spectateur » était donc un identifiant inconnu, pas un personnage répété. La formulation générique du validateur masquait cette cause. Le brief « Le spectateur connaît la vérité avant lui » est cohérent et ne demande pas de correction.

## Correctif appliqué au code

Dans le checkout actif `D:/Code/panelforge-krea2-flux` :

- `domain/long_stories.py` : normalisation avant validation référentielle, limitée à la politique v3 du job producteur. Seuls les libellés explicites du public sont reconnus ; un identifiant ou nom déjà déclaré dans le casting garde sa signification de personnage.
- La connaissance du public est conservée dans le texte du secret avec « Le spectateur connaît cette vérité. » ; `known_by` conserve les personnages réellement informés. Le moment de révélation et les autres champs restent identiques.
- Les personnages inconnus, doublons de personnages, valeurs malformées et mentions ambiguës telles que « narrateur » restent rejetés. Aucun secret vide ou trop long n’est tronqué pour passer.
- `application/stories.py` : provenance de la normalisation enregistrée avec brouillon original, brouillon normalisé et note explicite.
- Aucun changement du contrat JSON, des recettes, des réglages, des prompts de consigne, des empreintes éditoriales ou du comportement des anciennes politiques.

## État du projet à la fin de l’inspection

Le projet a évolué indépendamment pendant le diagnostic. À 14:46:24 UTC, il s’appelle « La même espèce », version 299, arc présent et écriture de séquence en cours (`develop`, workflow automatique `running`). L’arc désormais enregistré utilise Léo, Mia et Marc ; les deux secrets ont `known_by: ["marc", "mia"]`.

La récupération envisagée du premier brouillon n’a donc pas été exécutée. Aucun projet runtime, historique, compteur, appel, réglage ou trace n’a été modifié dans cette intervention. Aucun nouvel appel au modèle, rendu ou redémarrage n’a été lancé. Ne pas interrompre le traitement actuel pour ce patch ; il sera disponible au prochain démarrage normal du backend.

## Vérifications et limites

- Syntaxe Python des deux modules modifiés et du nouveau fichier de régression vérifiée par `ast.parse`.
- `git diff --check` ciblé sans erreur ; avertissements Git habituels LF/CRLF seulement.
- Six tests de régression préparés dans `tests/test_story_secret_audience.py` : préservation de l’information et du brouillon, idempotence, alias explicites et refus des erreurs réelles, protection du casting, compatibilité des politiques, absence de troncature.
- Tests non exécutés conformément à AGENTS.md. Aucun essai de génération : ce patch traite la validation et ne prouve pas la qualité narrative d’un prochain rendu.
- L’utilisateur peut exécuter `python -m unittest tests.test_story_secret_audience` depuis le checkout actif.

Sauvegardes avant patch et empreintes : `D:/Code/panelforge/.agent/diagnostics/story-secret-audience-20260928/`.
