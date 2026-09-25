# Écriture des histoires : trois étapes visibles

Implémentation dans `D:\Code\panelforge-krea2-flux`, après le snapshot `9b52feb`. Périmètre : moteur Histoire longue v2, présentation de l’écriture seulement.

## Parcours

1. **Intention** : création existante puis consultation du brief et des réglages enregistrés.
2. **Histoire** : progression et événements lisibles, personnages et fin. Une histoire écrite n’est pas marquée terminée tant que sa vérification ou sa validation manuelle reste attendue.
3. **Scénario** : scènes et dialogues, choix de la séquence déjà écrite, accès direct au retour sur une scène.

Les étapes sont consultables sans appel LLM. La vue choisie est mémorisée par projet ; le bandeau conserve la situation courante et propose de revenir à l’étape active. Les retours non envoyés sont conservés localement par projet et par cible. Une question, une demande de modification et une validation conservent leurs commandes distinctes.

Les états ont un libellé et un symbole : terminé en vert, traitement actif en bleu, planifié en violet, validation/point à examiner en ambre, incident technique en rouge. Le planifié désigne un travail à venir ; aucun pourcentage de temps ni position dans la file du fournisseur n’est inventé.

## Arrêts et reprise

- Validation manuelle : lire puis utiliser le bouton de validation du bandeau.
- Relecture bloquante : remarques bloquantes actuelles visibles, discussion directement ciblée, relecture explicite avec mention de l’appel LLM. Les suggestions facultatives ne deviennent pas des blocages.
- Réponse interrompue : motif exact et conservation du texte ; récupération sans appel LLM proposée en priorité lorsque le contrôle existant l’autorise. Sinon, relance explicitement annoncée comme appel LLM.
- Détails, anciennes versions, brouillons et traces rassemblés dans **Historique et vérifications avancées**.
- Une séquence déjà prête garde son accès à la fabrication même si d’autres restent à écrire.

Le moteur, ses modèles, ses prompts, sa limite de correction et ses validations ne sont pas modifiés. Les écrans Références / Scènes / Multilangue et la préparation d’une suite sont conservés. Les références avant/après transformation restent une évolution séparée.

## Vérifications

Contrôles effectués : analyse syntaxique Python et compilation JavaScript seule (y compris les scripts de fixtures), unicité des IDs HTML, comparaison avec HEAD du balisage de fabrication et de la préparation d’une suite, `git diff --check`.

**Tests fonctionnels préparés mais non exécutés**, conformément à la préférence utilisateur et à AGENTS.md. Aucun appel modèle, génération ou redémarrage. Commandes pour l’utilisateur dans le worktree actif :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_story_writing_browser.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_long_stories_browser.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_stories_browser.py"
```

Essai visuel conseillé après actualisation du navigateur : ouvrir une histoire longue existante, naviguer entre les trois étapes, rédiger un retour sans l’envoyer puis changer de cible et revenir. Sur une histoire bloquée, vérifier la remarque exacte et l’accès direct à la discussion ou à la récupération. À confirmer dans le navigateur réel : disposition sur petit écran et en cours de traitement.


## Complément : correction groupée des blocages du scénario

Le bandeau de scénario propose désormais **Corriger et continuer**. La route dédiée est bornée à une réparation de la séquence bloquée et une relecture immédiate ; aucun développement suivant ne précède ce contrôle. Une relecture favorable approuve cette unité et reprend le mode choisi. Une critique persistante arrête le parcours, sans boucle. Une simple reprise ne réinitialise pas les compteurs ; un nouveau clic explicite est nécessaire pour une autre passe.

Les versions, le périmètre, les dépendances et l’actualité de la relecture sont vérifiés avant mutation. Les suggestions facultatives sont exclues de la réparation. Les observations locales sont repliées, sans compteur zéro qui contredirait un blocage de relecture. Les brouillons manuels restent intacts.

Contrôles : syntaxe Python/JS et HTML seulement. Tests ciblés préparés dans test_story_workflow.py, test_long_stories_browser.py et test_story_writing_browser.py, non exécutés. Aucun appel modèle, rendu ou redémarrage. Charger le backend mis à jour après les traitements puis actualiser la page.
