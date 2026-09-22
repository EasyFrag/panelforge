# Histoires longues : correctif des contrats et de la reprise

Implémentation du 22 septembre 2026 dans `D:\Code\panelforge-krea2-flux`, autorisée après l’[audit des erreurs et des traces](audit-contrats-histoires-2026-09-22.md).

Le patch traite la chaîne de rédaction : format demandé au modèle, assemblage des réponses, validation, corrections, reprise et affichage. Il conserve le stockage narratif V2, la fabrication des personnages, les prompts de production, la vidéo, le DLSS et les réglages techniques par scène. Aucun projet runtime n’a été réécrit pendant l’implémentation.

## Ce qui change concrètement

| Problème observé | Comportement ajouté |
| --- | --- |
| Instructions de relecture contradictoires sur les champs à renvoyer | Contrat de réponse 2.1.0 construit une fois, transmis dans le contexte et au transport, puis utilisé pour contrôler la structure reçue. |
| Réécriture complète de l’arc, dépendances oubliées | `edit_outline` renvoie les champs à changer, avec une cible stable et l’empreinte du document de base. Les autres champs et identifiants sont conservés par l’application. |
| Rédacteur obligé de recopier le casting et de synchroniser une seconde liste de clips | Le casting provient de la bible ; chaque scène transporte directement ses métadonnées narratives. L’application reconstruit le format V2 pour le reste de la chaîne. |
| Correction locale qui touche involontairement d’autres scènes | Les corrections éditoriales et retours sur une scène utilisent `scene_edits`. Une empreinte périmée est refusée. Scènes non ciblées, casting et décors restent conservés. |
| Rejet de la réaction finale de Pom | Un clip peut être une progression, une réaction ou une transition. Une réaction sans nouvel événement doit se rattacher à une scène antérieure. Tous les événements requis restent contrôlés. |
| Clé `delivery` répétée, puis correction pourtant fidèle rejetée | Récupération locale bornée de cette faute de ponctuation ; comparaison éventuelle des structures décodées, sans confondre clés et valeurs. Les mots des dialogues restent identiques. |
| Série d’erreurs découvertes une par une | Diagnostics de structure regroupés, puis contrôles de références, causalité, révélations et couverture lorsque la structure permet de les examiner. |
| Réponse correcte syntaxiquement mais injouable en 10 secondes | Estimation locale des paroles et actions ; un excès manifeste bloque l’approbation même si la relecture du modèle affirme que tout va bien. |
| Coûts et brouillons perdus de vue après reprise | Historique des tentatives, durée cumulée et originaux/corrections conservés séparément. Compteurs persistants et téléchargement des brouillons précédents dans l’interface. |

Le moteur de stockage reste `story.long@2.0.0` ; le **contrat d’échange** des nouveaux appels devient `2.1.0`. Les anciens brouillons restent lus selon leur ancien contrat. La version des prompts internes augmente, sans migration du workspace.

## Reprendre « Jus de trahison »

Après tes traitements en cours et ton redémarrage habituel de PanelForge, recharge la page avec Ctrl+F5.

1. Rouvre l’histoire bloquée et consulte le panneau **Brouillon récupérable**. Il présente les scènes lisiblement et regroupe les diagnostics.
2. Choisis **Récupérer le brouillon · sans appel LLM**. Ce bouton applique la réponse déjà reçue uniquement si elle satisfait les contrôles structurels. Il ne lance ni génération ni fabrication.
3. Vérifie le texte récupéré. La dernière scène de Pom possède un ancrage identifiable dans l’état final de l’arc ; ses paroles et actions ne sont pas réécrites par cette récupération.
4. Choisis **Continuer le parcours** quand tu veux poursuivre. Les quatre clips trop chargés restent un problème éditorial : le contrôle local doit demander une correction ciblée avant leur approbation, puis une relecture du résultat.

La récupération locale n’est donc pas une approbation éditoriale. L’arc contient également des passages franglais : ils sont signalés et les nouvelles consignes demandent leur correction. Pour demander une révision de l’arc existant, utilise **L’histoire complète** ; les unités qui en dépendent devront être revérifiées. Une correction d’arc peut rendre les unités suivantes obsolètes selon les règles existantes.

Cette procédure n’a pas été exécutée sur le projet actif pendant le développement.

## Récupération bornée et conservation

- Les fautes de ponctuation reconnues sans ambiguïté sont traitées localement : clé courante répétée avant sa valeur, virgule manquante entre champs, virgule finale. Le remplacement historique de deux chaînes littérales reste borné et n’exécute aucun code.
- Les clés réellement dupliquées, valeurs ambiguës, troncatures, nombres non finis et expressions arbitraires restent refusés. Une réponse encore illisible après cette récupération n’entraîne **pas** de réécriture automatique par un modèle dont la fidélité serait impossible à prouver.
- Pour des erreurs de métadonnées isolées, une seule proposition de correction peut être demandée. L’application fournit la liste exacte des champs accessibles ; ni les dialogues, ni les actions, ni les personnages ne peuvent être modifiés par cette voie. La réponse complète est ensuite revalidée.
- Une réaction ne reçoit pas arbitrairement le dernier événement. Pour les anciennes réponses, la normalisation automatique est limitée à la dernière scène, après couverture de tous les événements, avec une correspondance textuelle forte entre sa preuve et l’état final prévu. Sinon le rattachement doit être précisé.
- Les indices publics (`hints`), confirmations publiques (`reveals`) et apprentissages des personnages (`knowledge`) sont distincts. Les connaissances déjà présentes dans la bible ne sont pas réinscrites comme de nouveaux apprentissages.
- Une erreur source et sa récupération conservent deux résultats d’appels distincts. Une récupération réussie ne transforme pas rétrospectivement la première réponse en réponse valide.
- Avant une nouvelle tentative, l’ancien brouillon est archivé avec son erreur, sa correction éventuelle, ses empreintes et ses identifiants. Les traces complètes de raisonnement restent dans les échanges LLM existants.

Les contrôles de références ne prouvent pas à eux seuls qu’un secret est correctement montré à l’image : la relecture éditoriale reste nécessaire.

## Durée, langue et nombre d’appels

L’estimation locale utilise `nombre de mots / 2,4 + secondes d’actions non simultanées`. Un dépassement est un avertissement. Il devient bloquant si le clip dépasse encore 130 % du budget avec une parole accélérée à 3,5 mots/seconde. Ces seuils évitent de bloquer pour un petit écart incertain ; ce ne sont pas des mesures d’audio produit. Les actions simultanées avec la parole ne doivent pas être comptées dans `action_seconds`.

Le repérage d’anglais résiduel dans les champs français est heuristique : plusieurs marqueurs sont nécessaires, les noms/identifiants sont exclus, et le résultat reste un avertissement. Il ne garantit pas une détection exhaustive.

Le parcours automatique de deux séquences sans défaut garde cinq appels : conception, édition de l’arc, deux rédactions et relecture groupée. Un problème de durée manifeste est détecté avant de payer une relecture pour le découvrir. Il déclenche directement l’unique correction éditoriale prévue pour l’unité, puis exige une relecture actuelle du résultat.

Une correction éditoriale automatique par unité est autorisée ; si le problème persiste, le parcours s’arrête et conserve les textes. « Continuer » ne remet pas cette limite à zéro. Un nouveau retour explicite de l’auteur peut ouvrir une nouvelle correction. La fenêtre de travail conserve le plafond `4 × nombre d’unités + 8` appels, réparations techniques comprises. Une reprise explicite après épuisement ouvre une nouvelle fenêtre ; les compteurs historiques restent conservés.

Les corrections ciblées travaillent dans les scènes existantes. Une restructuration plus large reste une révision explicite de l’auteur. Le budget de sortie demeure **80 000 tokens**. Aucun réglage supplémentaire n’a été ajouté au formulaire de création pour résoudre ces pannes.

Pour les projets antérieurs au patch, les compteurs ne prétendent pas reconstituer les appels déjà oubliés par les anciennes reprises : l’interface indique que le suivi commence avec cette mise à jour. La durée affichée cumule les temps d’attente/appel observés ; ce n’est pas un coût en euros ni une consommation de tokens.

## Sortie JSON contrainte côté serveur

Le lanceur demande désormais `response_format.type=json_schema` pour les nouveaux appels longs qui possèdent un schéma. Le contrat est également présent dans le contexte et contrôlé localement. Les requêtes des autres fonctionnalités, sans schéma, restent inchangées.

La prise en charge effective par les serveurs installés n’a pas été testée : aucun appel LLM de vérification n’était autorisé. L’adaptateur indique que la contrainte a été **demandée**, sans prétendre prouver son exécution par le serveur. Un refus explicite du schéma donne une erreur dédiée et ne déclenche pas de relance silencieuse.

Configuration du lanceur, sans ajouter de réglage au formulaire d’histoire :

| Serveur | Option CLI | Variable d’environnement | Valeurs |
| --- | --- | --- | --- |
| Principal | `--llm-structured-output` | `PANELFORGE_LLM_STRUCTURED_OUTPUT` | `json_schema` par défaut, ou `off` |
| Local | `--local-llm-structured-output` | `PANELFORGE_LOCAL_LLM_STRUCTURED_OUTPUT` | `json_schema` par défaut, ou `off` |

Si un serveur ne prend pas le schéma en charge, `off` conserve les contrats explicites, l’assemblage et tous les contrôles locaux ; seule la contrainte au décodage serveur est désactivée. L’interface de trace indique ce mode. Cela reste un point de compatibilité à vérifier lors du premier essai utilisateur.

## Vérification livrée

Les tests utilisent des passerelles factices, des magasins temporaires et des extraits des réponses enregistrées ; ils ne doivent appeler aucun modèle ni toucher au workspace actif. La fixture dédiée ne contient ni thinking intégral, ni média, ni clé d’accès.

Cas couverts dans les tests ajoutés/adaptés : erreurs réelles JSON et coda, absence de perte de dialogues, rejet des références invalides, diagnostics multiples, séparation indice/révélation/connaissance, charge excessive malgré une relecture positive, empreinte périmée, préservation des scènes non ciblées, récupération en un appel maximum, résultats source/correction distincts, compteurs persistants, reprise sans modèle et transport du schéma.

**Tests fonctionnels non exécutés**, conformément à ton choix de les lancer toi-même et aux instructions du dépôt. Seuls les contrôles statiques Python/JavaScript et `git diff --check` ont été exécutés. Aucun rendu, appel LLM ou redémarrage n’a été lancé. Le patch ne prétend pas garantir l’absence de toute erreur ni la qualité éditoriale d’un nouveau run avant cet essai.

Commande ciblée depuis le worktree actif :

```powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_story_response_recovery tests.test_story_contracts_v21 tests.test_story_schema_transport tests.test_long_story_response_contracts tests.test_long_stories tests.test_story_workflow
```

La suite générale reste disponible avec `python -m unittest discover -s tests` si tu souhaites ensuite l’exécuter.
