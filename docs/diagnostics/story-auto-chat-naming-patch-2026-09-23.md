# Patch histoire — automatique, chat et noms fruités — 23 septembre 2026

## Périmètre
Points 1 et 2 validés par l'utilisateur. Le découpage des dialogues et les erreurs du plan vidéo (point 3) restent hors périmètre.

## Changements
- La correction de séquence reçoit uniquement les remarques bloquantes ; les diagnostics facultatifs sont exclus de sa demande. La correction supplémentaire de l'arc suit aussi cette règle. La première édition de l'arc reste la passe habituelle.
- La relecture suivante retrouve la version effectivement relue grâce à son empreinte et aux révisions existantes. Elle reçoit les remarques précédentes et les scènes jouables changées, avant/après. Aucun stockage supplémentaire de scénario ni nouvel appel.
- Le relecteur distingue un propriétaire nommé d'un personnage visible ; ses anciennes suggestions sont du contexte, pas de nouveaux ordres. La limite d'une correction automatique reste inchangée.
- Une question conserve le mode, le document, les approbations, le motif d'arrêt, la cible en attente et les tentatives déjà utilisées. La réponse ne relance pas le parcours. La reprise ou l'annulation d'une question conserve également ces informations. L'appel de discussion reste comptabilisé.
- Le chat reçoit l'état réel du parcours, ses remarques bloquantes et le résultat de l'étape précédente, y compris une erreur technique. Il doit expliquer cet état et orienter une approbation vers Valider / Continuer.
- Question par défaut dans le formulaire long ; bouton explicite Demander une modification ; validation séparée. Une consigne supplémentaire demande discussion_only pour un simple accord même envoyé comme modification.
- Les nouveaux projets longs portent une politique de nommage : Bananito, Kiwina, Cerisa, Cerisetto, Noisettine sont des exemples. La conception et la première édition existante l'appliquent aux personnages fruités inventés. Les noms fournis par l'auteur ou hérités restent prioritaires. Les anciens projets et les scénarios déjà rédigés reçoivent une consigne de conservation. Aucun renommage local automatique ou nouveau rejet de validation.
- Recette éditoriale révision 5 et cache du script histoires actualisés. Les contrats JSON restent en 2.2.

## Vérification
- Syntaxe Python vérifiée par AST.
- JavaScript de stories.js et des fixtures navigateur compilé sans exécution de l'application.
- Diff relu et contrôle d'espaces effectué.
- Neuf régressions ciblées ajoutées au workflow, test navigateur adapté ; tests non exécutés conformément aux consignes du dépôt. Aucun LLM, rendu, service ou projet runtime lancé/modifié.

Tests à lancer par l'utilisateur depuis le worktree actif :
```powershell
Set-Location D:\Code\panelforge-krea2-flux
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_workflow tests.test_long_stories_browser tests.test_story_visual_continuity
```

## Essais
1. Après les traitements en cours, redémarrer le Lab puis Ctrl+F5.
2. À un arrêt automatique, poser « Quel retour attends-tu ? » : le motif et le mode Automatique restent présents ; aucune réécriture.
3. En Manuel guidé, poser une question puis valider : la validation en attente est conservée. Demander une modification reste une action explicite.
4. Sur une nouvelle histoire de fruits sans noms imposés, vérifier les prénoms proposés. Ouvrir une histoire existante : ses noms sont conservés.
5. Si une correction automatique est nécessaire, regarder la relecture suivante : les remarques précédentes et les changements doivent être disponibles. Une difficulté persistante arrête toujours la boucle.

La qualité des décisions de relecture et des prénoms générés reste à confirmer sur les prochains runs réels.
