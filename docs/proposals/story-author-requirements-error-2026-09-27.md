# Diagnostic — contraintes auteur, Freezer en laine — 27 septembre 2026

## Incident vérifié

Projet story-9ad92b309f8042eaa92f2021f957d8e1 ; appel llm-9a7bd34fedc84223acedef87c9ce6806. Conception sous experimental-2026-09-27, politique 2, recette révision 9. Une séquence, cinq clips, 50 secondes.

Le modèle finit normalement en 214,193 s avec un JSON valide. L’application rejette ensuite le résultat : « Une contrainte d’auteur doit citer un extrait exact du point de départ et une unité existante. » Les sept unit_id valent episode-1, qui existe bien. Six citations sur sept ne figurent pas mot pour mot dans le brief : le modèle les a partiellement traduites en anglais.

Exemples : « EXACTEMENT CINQ SCÈNES DISTINCTES de 10 seconds », « Je vais me pay a pute. », « Freezer, retrieve Mehdi and tabasse-le ! ». Les deux répliques protégées de l’auteur sont correctement enregistrées en français. Certaines formes corrompues se retrouvent aussi dans contract.must_keep et les preuves d’événement ; leur répétition ne doit pas leur donner priorité sur les sources auteur.

## Cause de conception de v2

story_contracts.outline_schema expose author_requirements comme facultatif même avec une seule unité. validate_outline valide strictement toute liste reçue. story_fidelity.validate_requirements exige une sous-chaîne exacte du brief ; ici le contrôle constate à juste titre que ces textes ne sont pas des citations exactes, mais il bloque toute la conception sur un champ inutile.

Pour une seule unité, story_fidelity.author_requirements transmet déjà directement le brief original complet à la relecture. Le modèle ne devrait pas avoir à le recopier ou à le répartir. Les consignes indiquent d’utiliser author_requirements pour plusieurs unités ; le schéma reste trop permissif à la génération, puis le validateur devient bloquant à la réception.

C’est une régression de conception du patch v2, pas un mauvais réglage ni un problème d’identifiant. La simple tolérance d’apostrophes ne corrigerait pas les traductions partielles observées.

## Correction minimale proposée, non implémentée

- Mono-unité : utiliser le brief original directement ; ne plus demander sa recopie dans author_requirements. Pour les réponses déjà reçues, traiter ce champ redondant localement, sans promouvoir de fausses citations, en gardant le brouillon brut.
- Multi-unités : conserver une attribution explicite de sources vérifiables. Ne pas transformer le validateur en acceptation de paraphrases inventées ; une sélection d’extraits par identifiants serait plus robuste que la recopie, à discuter séparément.
- Préserver la priorité des protected_lines originales sur les citations déformées du plan.
- Permettre après correctif la revalidation du brouillon, sous réserve des autres contrôles et sans promettre qu’un ancien brouillon archivé pourra être appliqué directement pendant une relance.
- Garder les archives v1/v2 immuables ; identifier clairement toute nouvelle édition si le contrat de génération change.

## État et périmètre

L’utilisateur a lancé un second compose, requête 6305fdf1-3a85-4375-9fbc-782b4a0ec56f ; en cours pendant le diagnostic. Le premier brouillon est conservé dans draft_history. Aucune interruption, relance ou modification du projet effectuée par l’agent.

Le projet est enregistré en creation_mode=ideas alors que le réglage proposé était adapt (Développer mon récit fourni). Cela n’explique pas l’erreur de citation ; c’est seulement un choix à rectifier pour une future adaptation fidèle.

Diagnostic seul, conformément au contexte « sans code ». Aucun test, LLM, génération, redémarrage, modification applicative ou runtime.

## Correctif implémenté après autorisation

Le schéma ne demande désormais author_requirements que pour plusieurs unités. En mono-unité, la source reste directement le brief original ; un champ redondant reçu sous la politique expérimentale, ou hérité d'un arc enregistré avec ce champ, est écarté avant validation structurelle. Le reste du récit passe dans tous les contrôles existants. Les réponses de référence sans cet héritage restent strictes.

La normalisation est utilisée à l'entrée de parse et dans validate_outline, y compris pour l'édition d'un arc ancien. Elle ne mute pas la réponse reçue. Une application réussie conserve le brouillon brut, enregistre la version normalisée et une note. Aucun événement, dialogue, réplique protégée, personnage ou contenu narratif n'est traduit ou inventé pour contourner le rejet.

Le parcours existant get / revalidate annonce la récupération si le brouillon passe tous les contrôles. Il l'applique sans appel LLM, puis reste en pause pour les étapes suivantes. L'empreinte du document source reste obligatoire : impossible d'appliquer silencieusement un vieux brouillon après modification de l'histoire. Les citations multi-unités restent vérifiées mot pour mot avec une unité existante.

Les trois fichiers du catalogue/archives éditoriaux sont inchangés, SHA-256 comparés avant/après. Ce correctif technique remet le schéma au périmètre déjà prévu par les consignes (attribution uniquement pour plusieurs unités) ; il n'ajoute ni prompt, ni politique d'écriture, ni édition créative. Les sélecteurs v1/v2 et leurs paquets restent inchangés.

Vérification statique : syntaxe AST de quatre modules et du fichier de tests, revue du diff ciblé, contrôle des archives et des espaces. Huit tests ajoutés dans tests/test_story_author_requirements.py, NON exécutés conformément à AGENTS.md. Commande utilisateur :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_author_requirements tests.test_story_editions tests.test_story_quality_policy
```

Sauvegardes et diff : D:/Code/panelforge/.agent/diagnostics/story-author-requirements-fix-2026-09-27/.

## Dernier état observé, distinct du défaut de citation

La relance utilisateur a passé la conception. À la lecture de la version 349, l'arc est enregistré mais develop a échoué avec « model returned an empty text response ». Aucun scénario ni brouillon texte n'a été reçu ; environ 56 000 caractères de trace de raisonnement sont conservés. Ce constat ne permet pas à lui seul de conclure à une limite de tokens, un problème de modèle ou de transport.

Ne pas récupérer l'ancienne conception archivée à la place de ce nouvel état. Pour ce run, reprendre la rédaction après activation du patch ; la récupération locale ne peut pas inventer le scénario absent. Aucun runtime ni service modifié ; aucun test, appel LLM ou rendu lancé par l'agent.
