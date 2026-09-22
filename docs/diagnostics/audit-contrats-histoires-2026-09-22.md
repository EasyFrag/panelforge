# Audit des erreurs en chaîne du moteur d’histoires longues

22 septembre 2026 — diagnostic et proposition, sans modification du moteur.

## Verdict

Les échecs viennent de plusieurs couches qui ne partagent pas un contrat suffisamment cohérent : consignes assemblées, réponse du modèle, validation du domaine, récupération des erreurs et relecture éditoriale. Les modèles commettent des omissions, mais l’application les transforme trop facilement en arrêt complet. Inversement, elle accepte certains défauts de langue et laisse la surcharge temporelle au niveau d’un avertissement.

Le correctif JSON précédent comporte aussi un défaut confirmé : son contrôle « format seulement » rejette une réparation qui conserve exactement l’histoire. Il faut remplacer ce contrôle, pas demander à l’utilisateur de changer ses réglages.

Recommandation : refondre la frontière entre écriture et données structurées, les corrections et la validation. Conserver l’architecture narrative utile, la création des personnages et la chaîne industrielle de fabrication. Une augmentation du budget, une consigne supplémentaire ou la suppression générale des validateurs ne traiteraient pas l’ensemble.

## Périmètre et preuves

- Code actif : `D:\Code\panelforge-krea2-flux`, base `2673c24e65eafd13b3797125b2ae2425b3db2100`.
- Projet : `story-9ddd34b57dc549d2bc959d9c735ac0ec`, **Jus de trahison**, version 413, enregistré le 22 septembre à 10:33:53, heure de Paris. Dernière vérification en lecture seule : même version et même échec.
- Sept appels enregistrés, leurs prompts réellement envoyés, réponses, traces de raisonnement et résultats applicatifs ; lecture du code de construction des requêtes, validation, récupération, relecture et orchestration.
- Copie des preuves dans `D:\Code\panelforge\workspace\experiments\audit-story-contracts-2026-09-22` : `project-snapshot.json`, `calls-summary.json`, sept fichiers d’appel au format JSON et exports séparés des réponses et raisonnements.
- Calculs sur ces fichiers : décodage JSON, comparaison textuelle avant/après réparation, comptage des mots et durées des appels. Aucun test applicatif, appel LLM, rendu ou redémarrage exécuté. Aucun projet ou réglage modifié.
- Limite : cet audit porte sur l’écriture et son exécution, pas sur une nouvelle vidéo rendue. Les estimations de parole ne sont pas des mesures audio.

L’intention enregistrée est maintenant une amorce libre : un fils pomme naïf présente sa compagne à son père charmeur ; ils se rapprochent dans son dos. L’utilisateur avait volontairement abandonné l’adaptation détaillée pour observer l’invention du modèle. L’absence de grossesse ou de révélation de paternité n’est donc pas ici une faute de fidélité.

## Ce qui s’est réellement passé

Heures de début à Paris ; durées arrondies. Les préfixes identifient les fichiers complets des preuves.

| Début | Appel | Rôle / modèle enregistré | Durée | Résultat applicatif |
|---|---|---|---:|---|
| 10:13:44 | `2a406771…` | Conception / Qwen Hauhau | 180 s | Arc accepté |
| 10:16:44 | `dd37021b…` | Relecture et réécriture / Qwen Hauhau | 100 s | `depends_on` absent sur six événements |
| 10:19:02 | `32da5d47…` | Nouvelle relecture / Qwen Hauhau | 114 s | Même omission sur six événements |
| 10:28:50 | `53a943b4…` | Relecture après correctif / Qwen Hauhau | 92 s | Arc accepté |
| 10:30:22 | `2f0624d4…` | Développement / Gemma Hauhau | 92 s | JSON mal formé |
| 10:31:54 | `41fd96e6…` | Réparation JSON / Gemma Hauhau | 25 s | JSON corrigé, rejeté à tort par le garde-fou |
| 10:33:00 | `3767f7e0…` | Nouveau développement / Gemma Unsloth | 53 s | Cinquième clip sans rattachement d’événement |

Identifiants de modèles enregistrés : `local::HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF`, `local::HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP`, puis `local::unsloth/gemma-4-31B-it-qat-GGUF`.

Les sept appels terminent avec `finish_reason=stop`, un plafond demandé de **80 000 tokens**, et un succès côté transport. L’application en accepte deux et en rejette cinq, réparation comprise. Cela représente **655,037 secondes cumulées**, dont **382,714 secondes pour les appels rejetés**. La durée écoulée entre le premier départ et le dernier échec est d’environ vingt minutes, avec des intervalles : ce n’est pas vingt minutes de calcul mesuré.

Les compteurs de tokens ne sont pas renseignés dans les traces. Aucun des deux nouveaux blocages ne correspond à une troncature signalée. Augmenter encore le plafond ne cible pas leur cause. À la capture, l’arc est enregistré et relu, mais aucune séquence développée n’est acceptée ; le dernier brouillon de 9 206 caractères existe toujours.

## 1. Le JSON : erreur du modèle, puis erreur de notre récupération

Dans le premier développement, ligne 85, colonne 35, la deuxième réplique du deuxième clip contient :

```text
"delivery": "delivery": "spoken"
```

La réponse du réparateur remplace uniquement cette ligne par :

```json
"delivery": "spoken"
```

La comparaison des fichiers établit exactement ceci : supprimer cette répétition dans l’original donne la totalité du texte corrigé, caractère pour caractère. Aucun dialogue, personnage, événement, nombre ou autre champ n’a changé. Cela prouve une réparation syntaxique fidèle ; cela ne certifie pas la qualité narrative ou la durée du scénario.

`assert_format_only` extrait par expression régulière une suite de chaînes, nombres et littéraux, puis exige une égalité parfaite entre original et correction. Les **clés** sont comptées comme les **valeurs**. Enlever la clé répétée change cette suite : le garde-fou conclut faussement à une modification de contenu.

Cette protection est également insuffisante en principe : conserver l’ordre des chaînes et nombres ne prouve pas qu’ils occupent les mêmes chemins dans l’objet. Il faut protéger le contenu et les rattachements structuraux, pas seulement une suite de tokens.

Autre défaut : après l’échec de la récupération, le bilan applicatif de l’appel initial est réécrit avec l’erreur de récupération. Le JSON brut permet de retrouver la cause, mais la télémétrie ne conserve plus deux résultats clairement distincts.

**Correction proposée :** réparation locale par transformations structurelles explicitement autorisées, hors des chaînes, avec positions avant/après et une interprétation non ambiguë. Pour les cas restants, correction limitée à des segments identifiés, conservation des textes et identifiants, puis validation complète. Une réponse ambiguë reste un brouillon à examiner. Ne pas retirer simplement le garde-fou ni exécuter du code émis par le modèle.

## 2. Le clip sans événement : une vraie utilité dramatique non reconnue

Le dernier développement est un JSON valide. Les rattachements sont :

| Clip | Contenu | Événements |
|---|---|---|
| 1 | Présentation et première attraction | `event-1` |
| 2 | Flirt au dîner | `event-2` |
| 3 | Faux diagnostic médical | `event-3` |
| 4 | Départ du père avec la compagne | `event-3` |
| 5 | Le fils range seul, heureux et dupé | Liste vide |

Tous les événements de l’unité sont déjà couverts. Le cinquième clip, **La solitude heureuse**, montre précisément l’état final demandé par l’arc : le fils reste seul à ranger, satisfait, après le départ des deux adultes. Cette réaction renforce l’ironie dramatique. Elle n’ajoute pas une péripétie, mais elle sert l’histoire.

Le validateur exige pourtant au moins un événement pour chaque clip et rejette toute la séquence. Le prompt exige une entrée par clip, des IDs servis et la couverture de tous les événements, sans dire aussi explicitement que le tableau doit toujours contenir au moins un ID. Le modèle distingue l’événement de sa retombée, alors que le validateur les traite de la même manière.

Le champ vide est donc non conforme au contrat actuel. La valeur narrative du clip reste réelle. Dire que « le modèle n’a pas suivi l’histoire » serait faux.

**Correction proposée :** autoriser explicitement les fonctions progression, réaction et transition. Une réaction ou transition reste rattachée à un événement ou à une scène antérieure par un lien justifié ; elle n’a pas à inventer un nouvel événement. La couverture et l’ordre sont contrôlés à l’échelle de la séquence. Pour ce brouillon, le départ sous prétexte médical fournit le rattachement naturel de la réaction finale. Ne pas généraliser en remplissant automatiquement toute liste vide avec le dernier événement.

## 3. Les contrats sont éparpillés et les prompts se recouvrent

### Plusieurs demandes de sortie dans un même appel

Pour `edit_outline`, le prompt de relecture générique dit de renvoyer `reply` et `review`. Un suffixe demande ensuite `reply`, l’intégralité de `series_outline` corrigé, et `review`. La relecture groupée présente une superposition comparable entre `review` et `reviews`.

Le modèle a choisi les bonnes clés racines dans les appels examinés : ces contradictions ne prouvent donc pas la cause de chaque erreur. Elles augmentent toutefois le risque, alors que ce problème de racine a déjà été rencontré dans l’historique.

La relecture dite indépendante est exécutée avec le même modèle architecte, dans un appel qui corrige puis évalue sa propre correction. Ce n’est pas une vérification indépendante du résultat finalement sérialisé. Il ne faut pas considérer un bilan `issues: []` comme une garantie générale.

L’application réinjecte aussi des champs dérivés, par exemple `beats`, tout en demandant au modèle de les supprimer en sortie. Ce comportement est explicable par le format interne, mais le contexte d’écriture devrait présenter uniquement les données utiles et éditables.

### Un exemple JSON ne contraint pas le décodeur

`response_contract` est un exemple inclus dans le texte envoyé. `CompletionRequest` ne contient pas de schéma de sortie et la passerelle locale n’envoie ni `response_format`, ni schéma JSON, ni grammaire. La syntaxe et les champs obligatoires reposent donc sur l’obéissance textuelle du modèle.

La documentation actuelle de llama.cpp décrit les sorties JSON contraintes via `response_format`. Elle précise que seule une partie de JSON Schema est prise en charge et que le schéma ne remplace pas les explications dans le prompt. Il faut vérifier la capacité de la version locale et sa transmission par le proxy avant activation ; aucune compatibilité locale n’a été testée pendant cet audit. Sources : [serveur llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), [grammaires et limites](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md).

### Le modèle recopie des données qui pourraient rester dans l’application

Une révision redonne tout l’arc, ses identifiants et son graphe. L’écriture redonne le casting puis un tableau de scènes et un tableau parallèle d’affectations indexées. Cette redondance augmente les possibilités d’omission et de désynchronisation.

Les descriptions narratives, changements, répliques et justifications doivent venir du modèle. Les positions, données inchangées, identités déjà connues, références de révision et champs dérivés peuvent rester sous responsabilité de l’application. Celle-ci ne doit toutefois pas déduire arbitrairement la causalité ou le savoir d’un personnage.

## 4. Ce que montrent les raisonnements enregistrés

Les sept traces représentent **167 290 caractères**. C’est un volume de texte, pas un nombre de tokens ni une mesure directe du temps de raisonnement. Ce sont les traces fournies par les modèles locaux, à comparer aux réponses effectives ; elles ne prouvent pas exhaustivement leur processus interne.

| Appel | Observation utile du raisonnement | Vérification dans la réponse |
|---|---|---|
| Conception Qwen | Explore la naïveté, les alibis et plusieurs fins ; retient l’infidélité familiale et le médecin complice | Mécanique principale présente ; univers respecté dans le casting final |
| Deux relectures Qwen rejetées | Mentionnent explicitement `depends_on`, jusqu’à énumérer les six dépendances à conserver | Champ omis malgré cette préparation |
| Relecture Qwen acceptée | Cherche à franciser les passages, contrôler les indices, préparer la chute et supprimer les champs dérivés | Nombreuses descriptions encore mixtes français/anglais ; pas de remarques résiduelles |
| Premier rédacteur Gemma | Découpe trois événements sur cinq clips, avec rattachements cohérents | Erreur de sérialisation sur une seule clé ; paroles trop abondantes |
| Réparateur Gemma | Identifie précisément la duplication de `delivery` et veut préserver le reste | Réparation fidèle, refusée par notre code |
| Dernier rédacteur Gemma | Prévoit explicitement une retombée finale avec le fils heureux et ignorant | Bonne fonction dramatique, mais métadonnée `event_ids` vide ; surcharge sur les clips parlés |

Les quatre appels Qwen produisent chacun environ 30 000 à 54 000 caractères de raisonnement pour environ 9 000 caractères de réponse. Une partie du raisonnement répète des vérifications de champs et de langue qui ne se matérialisent pas dans le résultat. Il faut externaliser ces contrôles dans le logiciel. Demander « réfléchis plus » ne fournit pas cette garantie.

Le raisonnement majoritairement anglophone n’est pas en soi un défaut. La non-conformité se situe dans les champs français de la réponse, pas dans la langue de la trace interne. Changer uniquement de modèle n’est pas une conclusion justifiée : deux variantes de Gemma ont échoué différemment et le réparateur a réussi sa tâche.

Enfin, `include_reasoning=False` sur la réparation ne désactive pas le raisonnement du serveur : ce paramètre agit sur la collecte/transmission locale des traces ; la couche de journalisation demande même leur collecte. La réparation contient 3 117 caractères de raisonnement. Un contrôle du calcul exigerait un paramètre serveur réellement pris en charge, distinct de la visibilité des traces. Garder le plafond 80 000 demandé par l’utilisateur ; ne pas confondre plafond de sortie et allocation utile du raisonnement.

## 5. La qualité que les erreurs techniques masquent

### Le cœur de l’histoire fonctionne

La séduction parallèle à la joie du fils, les excuses absurdes et la réaction finale portent une ironie dramatique compréhensible. Le dernier brouillon utilise un silence utile. Il suit bien davantage l’intention de tromperie que ne le laisse croire son message d’échec.

Cela ne rend pas toutes ses inventions fortes : le médecin complice fournit une solution très commode, les variations autour du jus se répètent, et le « pacte de charme » de l’arc final reste abstrait. Ce sont des sujets de relecture éditoriale, pas des défauts de JSON. Les répliques devraient davantage différencier les voix et faire agir les personnages, plutôt que commenter plusieurs fois leur complicité.

### Durée : quatre clips manifestement chargés

Le dernier brouillon prévoit cinq clips de dix secondes. Le calcul déjà utilisé dans l’application est `mots / 2,4 + secondes d’actions non simultanées` :

| Clip | Mots prononcés | Parole estimée | Actions successives déclarées | Total estimé |
|---|---:|---:|---:|---:|
| 1 | 35 | 14,6 s | 4 s | 18,6 s |
| 2 | 41 | 17,1 s | 6 s | 23,1 s |
| 3 | 40 | 16,7 s | 5 s | 21,7 s |
| 4 | 35 | 14,6 s | 4 s | 18,6 s |
| 5 | 0 | 0 s | 8 s | 8 s |

Ce sont des estimations, sensibles au débit et au jeu. Elles signalent néanmoins un problème majeur : la parole seule dépasse déjà dix secondes dans les quatre premiers clips. Le premier développement corrigé a le même problème dans ses cinq clips. Il ne faut donc pas récupérer ce dernier et le déclarer immédiatement prêt à fabriquer.

Le contrôle de charge existe, mais en avertissement après validation ; l’affectation vide bloque avant qu’il soit utilement exposé sur le brouillon. Les consignes parlent de faisabilité sans donner au rédacteur ce budget de parole chiffré.

Correction : fournir un budget de parole indicatif tenant compte des gestes et réactions, produire le diagnostic sur le brouillon, puis demander de raccourcir ou redistribuer les seules scènes réellement surchargées. Une estimation proche de la limite reste un avertissement ; une surcharge manifeste doit empêcher l’autovalidation pour fabrication tant qu’elle n’est pas traitée. Ne pas remplir mécaniquement tous les clips, ni supprimer les réactions pour faire rentrer les dialogues.

### Langue : le résultat accepté reste mélangé

Exemple dans l’arc accepté : « Il invente un diagnostic absurde qui justifies qu'ils leave together. » Le secret est formulé en anglais ; plusieurs états de la deuxième unité sont également mixtes. Les instructions de français sont pourtant présentes.

La relecture affirme avoir nettoyé les dialogues et ne liste aucun problème. Les dialogues sont effectivement plus français que les descriptions ; ce bilan ne doit pas être élargi à une certification de tous les champs. La vérification manque pour les descriptions, contrats et états transmis ensuite au rédacteur.

Correction : vérifier les champs narratifs concernés, intégrer leurs problèmes à la relecture existante, et cibler les corrections. Ne pas rejeter automatiquement un nom propre ou un emprunt familier isolé tel que « bad ».

### Secrets : suspicion du public et découverte du fils sont trop regroupées

`secret-1` contient à la fois l’usage des excuses médicales et la préparation de la liaison ; sa révélation publique est réservée à la deuxième unité. Or la première montre déjà des regards complices, le diagnostic arrangé et le départ des deux adultes. Les `reveals` restent vides.

Le raisonnement Qwen justifie cela par une différence entre soupçon et confirmation finale. Cette distinction est pertinente, mais le contrat ne la représente pas explicitement : une seule vérité et une seule date de révélation couvrent plusieurs niveaux d’information. Ce n’est pas la preuve d’une révélation prématurée bloquante ; c’est une ambiguïté qui pourra provoquer soit un refus abusif, soit une fuite non détectée.

Correction : distinguer l’information montrée au public, son degré de confirmation et les personnages qui l’apprennent. Pour une tromperie, le public doit pouvoir comprendre avant la victime. La relecture doit vérifier les gestes et paroles effectifs, pas seulement les tableaux déclaratifs. Les entrées `knowledge` du brouillon répètent par ailleurs des personnages déjà informés dans l’arc : éviter ces faux changements de connaissance.

### Réglages : influences réelles, mais pas cause des pannes

Le projet est toujours en `creation_mode=adapt`, alors que le brief actuel est une amorce d’invention. L’univers contient encore explicitement « médecin ananas » : sa présence ne vient pas d’une invention incontrôlée du modèle. Le modèle lui cherche un rôle causal et en fait le fournisseur d’alibis.

Le format est deux unités de cinq clips maximum, dix secondes chacun, pour une cible de cent secondes. Ce découpage administratif ne garantit pas l’équilibre dramatique. Représenter plus clairement ce qui est hérité d’un réglage ou décidé par le modèle aiderait l’utilisateur. Il n’a toutefois pas à modifier ces choix pour résoudre une clé JSON répétée ou une affectation manquante.

## 6. Pourquoi une nouvelle erreur apparaît après chaque correction

1. Les modèles doivent inventer et recopier beaucoup de données techniques en même temps.
2. Le contrat existe sous plusieurs formes : exemples, paragraphes, suffixes et conditions Python, sans définition commune suffisamment explicite.
3. La validation s’arrête à la première exception. Le défaut suivant existe souvent déjà, mais n’est pas montré.
4. La récupération automatique couvre quelques cas isolés ; celle du JSON introduit elle-même un faux rejet.
5. La relance réécrit une réponse entière : elle peut réparer un champ et en abîmer un autre.
6. La relecture génère une nouvelle version complète et l’approuve dans le même appel, sans preuve que toutes les exigences ont été respectées dans le résultat sérialisé.
7. Les erreurs de format arrêtent le parcours avant l’exposition des défauts éditoriaux ou temporels.

Le compteur `workflow.calls` vaut zéro dans le projet capturé malgré sept appels durables. Il est remis à zéro à certaines reprises ; les quotas de corrections éditoriales ont, eux, une persistance distincte. Il ne s’agit donc pas d’une preuve de boucle infinie automatique, mais le compteur courant ne permet pas de comprendre le coût total. Les traces montrent ici des reprises et une réparation automatique, pas une infinité d’appels autonomes.

## Correctif de fond proposé

### A. Un contrat par opération, défini une seule fois

Définir des contrats versionnés pour conception, relecture d’arc, écriture, correction et relecture de bloc. En dériver les exemples et les validations de structure ; produire un schéma compatible avec le serveur lorsque disponible. Générer les listes d’IDs autorisés depuis le projet. Garder les invariants narratifs et références croisées dans le domaine.

Assembler un prompt propre par opération : mission, contexte minimal, règles pertinentes et unique contrat de sortie. Supprimer les consignes de sortie concurrentes et les champs internes dérivés. La capacité serveur doit être explicite ; pas de repli silencieux qui ferait croire qu’une sortie est contrainte alors qu’elle ne l’est pas.

Activer ce contrat pour les opérations d’histoire concernées, pas globalement pour les autres usages de la passerelle. Vérifier également son articulation avec le template de raisonnement et le streaming : la contrainte porte sur le JSON final, la fin effective de génération reste requise avant acceptation.

Le schéma doit contraindre les clés, types et identifiants, tout en laissant libres l’écriture, les répliques et la mécanique narrative. Un JSON conforme ne prouve ni la causalité ni la qualité de l’histoire.

### B. Réduire les données que le modèle doit recopier

Pour une révision, demander des modifications ciblées sur IDs stables, liées à la révision de base, plutôt que l’arc complet. L’application conserve ce qui n’est pas touché et applique les changements atomiquement. Une modification d’événement invalide les contrôles des unités dépendantes ; préserver le même ID ne prouve pas que la causalité est inchangée.

Dans une nouvelle version du contrat d’écriture, rapprocher les scènes et leurs métadonnées pour éviter les tableaux parallèles. Le modèle choisit les références narratives et la fonction du clip ; l’application construit les index et réinjecte les identités connues. Un adaptateur conserve le format de fabrication actuel.

### C. Validation complète et récupération bornée

Parcours proposé : réception immuable → récupération locale autorisée → décodage → collecte des problèmes structurels et référentiels → diagnostics éditoriaux et de durée → correction ciblée si nécessaire → nouvelle validation → acceptation pour la suite.

Collecter les erreurs indépendantes avec `code`, chemin, portée et gravité, au lieu d’exposer une succession de messages génériques. Si le JSON n’est pas décodable, préciser que l’analyse du contenu n’a pas encore été possible ; ne pas inventer les diagnostics manquants.

Séparer trois niveaux :

- **Récupérable techniquement** : ponctuation ou répétition structurelle non ambiguë ; correction tracée, texte protégé.
- **Problème ciblé à résoudre** : référence manquante ou incohérente, texte incomplet, omission d’un événement obligatoire, charge manifestement excessive ; brouillon lisible et conservé, fabrication bloquée tant que nécessaire.
- **Avertissement** : préférence éditoriale, estimation incertaine, raccord mineur ; ne détruit pas le travail et ne relance pas toute l’histoire.

Une tentative automatique de réparation technique au maximum par étape et révision ; un cycle éditorial ciblé au maximum avant retour explicite à l’utilisateur si un blocage persiste. Compteurs persistants par révision, budget global et cause d’arrêt lisible. Une action volontaire de l’utilisateur peut ouvrir une nouvelle tentative, enregistrée comme telle.

### D. Relecture qui vérifie le texte effectivement produit

La relecture reçoit les diagnostics déterministes et s’occupe de fidélité, causalité, compréhension, révélations, voix, langue et faisabilité. Elle retourne des problèmes prouvés et, lorsque localement possible, des changements bornés. Elle ne doit pas inventer une réécriture pour justifier son rôle.

Lier les résultats à la version du texte. Après une correction substantielle, contrôler les passages modifiés et leurs conséquences ; ne pas recycler l’approbation d’une version antérieure. Ne pas présenter l’autoévaluation d’une correction comme une expertise indépendante. Le choix d’un autre modèle pour la relecture reste une option à évaluer, pas une condition suffisante de qualité.

Pour les deux séquences actuelles, conserver un parcours normal d’environ cinq appels éditoriaux : conception, contrôle de l’arc, deux développements, relecture groupée. Les contrôles de structure, calculs de durée et sauvegardes n’ajoutent aucun appel. Les réparations doivent devenir exceptionnelles et ciblées. Aucune promesse de gain de latence chiffré avant mesure.

### E. Une reprise exploitable et compréhensible

Conserver séparément le brouillon initial, les candidats corrigés, les diagnostics et leur provenance. Ne plus écraser l’erreur source avec celle d’une tentative de récupération. Afficher les problèmes pertinents ensemble : par exemple « scène 5 : réaction sans rattachement ; scènes 1 à 4 : charge élevée ».

Séparer « texte reçu », « structure validée », « relecture effectuée » et « prêt à fabriquer ». Rendre disponible la revalidation locale du candidat approprié et indiquer si l’action appelle ou non un modèle. Afficher le nombre total d’appels, leur rôle, le temps cumulé et les réparations, indépendamment des reprises.

L’utilisateur intervient sur l’intention ou le contenu, dans un champ de retour attaché à l’histoire ou à une scène. Il ne devrait pas avoir à fournir des IDs ou à diagnostiquer le JSON. Mode automatique : poursuite après corrections sûres et contrôles suffisants. Mode manuel : mêmes garanties, avec pauses éditoriales explicites.

## Livraison et critères d’acceptation

Livrer cet ensemble en lots cohérents, sous le même objectif de fiabilité :

1. **Récupération et diagnostic** : supprimer le faux rejet prouvé, préserver tous les candidats, identifier les clips et remonter tous les problèmes accessibles. Ajouter le contrat explicite des réactions et les diagnostics de charge sur les brouillons.
2. **Contrats et prompts** : définition commune, consignes par opération, transport du schéma selon les capacités, révisions ciblées et compatibilité avec les documents existants.
3. **Qualité et orchestration** : distinction public/personnages, relecture liée à la version, budgets de correction persistants, états de reprise et explications dans l’interface.

Conserver le format existant au stockage ou fournir une migration explicite et réversible. La chaîne personnages → prompts → vidéos → DLSS reçoit toujours le contrat de fabrication attendu. Aucun changement automatique des réglages techniques par scène ni des prompts déjà fabriqués.

Avant de considérer le problème traité, couvrir ensemble les cas suivants avec des fixtures minimales issues des traces, sans envoyer les données au modèle :

| Cas | Résultat attendu |
|---|---|
| Duplication de `delivery` observée | Réparation exacte acceptée ; aucune réplique modifiée |
| Réparateur changeant un mot, nombre, locuteur ou rattachement | Modification détectée ; pas d’acceptation comme simple réparation de forme |
| JSON ambigu, tronqué ou expression exécutable | Pas d’invention de fin ni d’exécution ; brouillon conservé et cause lisible |
| Omission de dépendances lors d’une révision sans changement causal | Liens existants conservés par application du changement ciblé |
| Révision modifiant la causalité | Références et conséquences recontrôlées ; pas de conservation aveugle du graphe |
| Réaction finale liée au départ | Acceptée sans inventer de nouvel événement |
| Événement obligatoire manquant ou ID inconnu | Blocage précis et globalement regroupé avec les autres défauts |
| Quatre clips trop parlés pour dix secondes | Diagnostic disponible avant fabrication ; correction ciblée proposée |
| Public informé avant le héros | Ironie dramatique permise ; pas d’apprentissage fictif du héros |
| Secret réellement dévoilé trop tôt ou fait non joué | Défaut sémantique signalé sur le passage concerné |
| Scénario français comportant des passages anglais | Relecture localisée ; noms propres et argot isolé préservés |
| Reprise, pause, erreur puis nouvelle tentative | Historique intact, budgets explicites, pas de boucle automatique cachée |
| Ancien document valide et sortie vers fabrication | Compatibilité conservée |

Prévoir également un test de contrat de transport avec passerelle simulée, puis un essai réel contrôlé de la prise en charge du schéma lorsque l’utilisateur le lance. Les seuls tests du parseur ne peuvent pas valider les capacités du serveur ni la qualité créative. Les tests et générations restent à la main de l’utilisateur conformément aux instructions acquises.

## Reprise du projet actuel après correction

Ne pas régénérer la conception. Conserver l’arc et les deux candidats développés. Reprendre de préférence le dernier brouillon : sa réaction finale est pertinente. Résoudre son rattachement, traiter la surcharge des quatre clips parlés et la langue du contexte, puis revalider et poursuivre la deuxième séquence. Cela doit passer par le parcours applicatif avec provenance, pas par une modification silencieuse des fichiers du projet.

La correction de l’interface entre modèle et application est nécessaire même si l’on choisit un meilleur modèle ensuite. L’objectif vérifiable est une réponse récupérable, des erreurs regroupées et des textes réellement évalués avant fabrication ; aucune architecture ne peut promettre que toute invention du modèle sera bonne du premier coup.

## Repères du code audité

- `src/panelforge/domain/story_response_recovery.py` : `decode_response`, `assert_format_only`.
- `src/panelforge/domain/long_stories.py` : `normalize_event_dependencies`, `validate_outline`, `episode_example`, `validate_episode`, `validate_review`.
- `src/panelforge/application/long_stories.py` : projection des contextes et assemblage des consignes par opération.
- `src/panelforge/application/stories.py` : diagnostics de durée, `_parse_draft`, `_repair_json_once`, `_run`, persistance des résultats.
- `src/panelforge/application/story_workflow.py` : `advance`, `_call`, `tick`, budgets et reprises.
- `src/panelforge/application/prompt_lab.py` : `CompletionRequest`.
- `src/panelforge/infrastructure/llm/openai_compatible.py` et `logged.py` : paramètres réellement envoyés et gestion des traces de raisonnement.
- `prompt_sources/story.long/2.0.0/` : consignes communes, écriture, relecture et arc.
