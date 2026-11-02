# Audit des erreurs Plan H3 — Petits hommes, 29 octobre 2026

**Analyse uniquement. Aucun code, réglage, preset, fichier de production ou service modifié. Aucun test, appel modèle ou rendu lancé.** L'utilisateur souhaite privilégier l'intention du preset et préserver le prompter H3 partagé, sauf défaut concret démontré.

## Périmètre et résultat

Audit figé aux appels terminés connus jusqu'au **29 octobre à 20 h 30 min 57 s, heure de Paris** (19:30:57 UTC). Les traitements lancés par l'utilisateur peuvent continuer après cette borne. Les comptes ci-dessous portent sur les appels retrouvés et leur version réellement envoyée, pas sur le preset actuellement affiché après réapplication.

Même modèle dans les trois groupes : `local::unsloth/Qwen3.8-27B-GGUF`. Même recette déclarée : `minimax.h3.fl2va.classic.cinematic.planned@1.0.0`.

| Direction réellement envoyée | Plans examinés | Acceptés | Rejetés | Premier motif affiché |
| --- | ---: | ---: | ---: | --- |
| v4 | 20 | 20 | 0 | — |
| v5 | 9 | 0 | 9 | 8 langue, 1 caméra |
| v7 | 4 | 0 | 4 | 1 langue, 3 caméra |

Les 13 appels rejetés ont terminé normalement côté modèle : réponse complète, statut de transport `succeeded`, arrêt `stop`. Les erreurs interviennent lors de la validation applicative du Plan. Ce ne sont pas des pannes de serveur ou des réponses tronquées.

Les **13 réponses rejetées contiennent toutes une balise de parole incorrecte**, y compris les quatre dont le premier rejet concerne la caméra. Les champs `spoken_languages` et `spoken_lines` sont présents et cohérents. Corriger seulement les caméras laisserait donc le problème de parole.

Le relevé détaillé, sans textes de raisonnement, est dans [calls-audit.json](../../.agent/diagnostics/petit-homme-v7-errors-20261029/calls-audit.json). Les traces originales sont dans `workspace/video_llm_traces/calls/{call_id}.json`.

## 1. Le premier problème est le format de parole

Exemples observés dans les réponses brutes :

```text
<d>Portuguese Obrigado</d>
<d>Portuguese</d>Obrigado</d>
<d>Chinese谢谢</d>
<d>English</d>Thank you
```

Pour la fiche dont la langue et la formule sont déjà `Portuguese` et `Obrigado`, la forme attendue est :

```text
<d>[Portuguese] Obrigado</d>
```

Les crochets autour du nom de langue sont des caractères réels du format. Le modèle les omet ou ferme la balise immédiatement après le nom de langue. Le normaliseur reçoit alors `Portuguese`, `Portuguese Obrigado` ou `Chinese谢谢` comme contenu parlé ; ce contenu ne correspond plus à la réplique déclarée séparément. Le message « Langue manquante ou ambiguë » est donc trompeur dans ces cas : la langue a été choisie, mais sa représentation dans l'action est incorrecte.

La requête envoyée contient bien les crochets : le système indique `<d>[language]words</d>` et le schéma fournit une forme `<d>[English] exact words</d>`. Ils ne disparaissent pas durant la transmission. En revanche, la consigne vocale ajoutée ensuite parle du nom anglais de langue « dans la balise », et fournit séparément une entrée telle que `Portuguese: Obrigado`. Le modèle recompose le balisage au lieu de recopier une ligne complète.

La provenance de l'erreur est établie : `infrastructure/llm/logged.py` archive le contenu retourné par le modèle avant de le rendre au service de composition. Les formes incorrectes sont déjà dans `response_text`, avant restauration des placeholders et compilation.

**Conclusion :** mauvais format généré, sans preuve d'un dysfonctionnement du normaliseur commun. Rendre le format exact immédiatement disponible dans l'intention/préparation est le premier levier à essayer.

## 2. Les rejets caméra correspondent à un contrat mal expliqué par le preset

Trois cas v7 :

| Champ retourné | Pourquoi il est rejeté |
| --- | --- |
| `static_shot`, `target_clause: "over the sloping port street and the looming harbor wave"` | `over` ne fait pas partie des préfixes reconnus par le validateur existant. Une clause vide évite cette ambiguïté pour un cadrage fixe. |
| `push.in`, `target_clause: "the dry pavement beside the minibuses"` | Le champ commence par un groupe nominal, sans amorce spatiale reconnue. |
| `push.in`, `target_clause: "the reinforced log-and-stone barrier at the slope base"` | Même problème de préfixe. |

Le prompter Classique standard donnait des amorces techniques explicites, notamment `toward`, `beside`, `above`. Les consignes spécifiques Petits hommes ont remplacé ces indications par une demande plus abstraite de continuation spatiale. Le validateur de [minimax_h3.py](../../src/panelforge/domain/minimax_h3.py) n'a pas été assoupli et applique toujours son contrat.

Les messages supplémentaires « Tuple should have at least 1 item » sont des conséquences du rejet d'un objet caméra imbriqué. Les réponses examinées contiennent bien des plans et des phases ; ce ne sont pas des scènes vides.

**Conclusion :** perte de guidage technique dans les consignes propres au preset ; aucun défaut général H3 établi. Pour un premier essai limité à l'intention, demander explicitement un cadrage fixe avec `target_clause` vide. Cela ne rend pas les personnages ou le danger immobiles.

## 3. Le preset ne se limite actuellement pas à une intention

Depuis v5, le chemin Petits hommes remplace le système de la recette par `little_men_prompting.system_prompt(...)` dans [prompt_composition.py](../../src/panelforge/application/prompt_composition.py), et écarte la politique Classique habituelle. Il ajoute aussi le contrat d'aide, ses références d'actions et, à partir de v6, les choix de variété. Les autres ateliers conservent leur propre chemin.

Les traces v4 utilisent une recette éditable de révision 2. Les traces v5/v7 ont `recipe_revision: null` et les consignes spécifiques Petits hommes. Le même identifiant de recette H3 ne signifie donc pas que les instructions effectivement reçues sont identiques.

Un cas comparatif particulièrement utile : `llm-2e64ed9f6d0f42528dca96e5fb6052ff`, v4 accepté à 17 h 29 min 42 s heure de Paris, se situe entre deux v5 rejetés à 17 h 28 et 17 h 31. Même modèle et même recette déclarée ; sa réponse contient correctement `<d>[French] Merci</d>`. Les 20 Plans v4 examinés utilisent tous le balisage avec crochets.

Cette comparaison pointe vers le guidage spécifique au preset. Ce n'est pas un essai contrôlé isolant une unique phrase, donc elle ne prouve pas qu'une reformulation suffira à tout corriger.

## 4. La longueur et les priorités narratives

| Version | Médiane caractères système + utilisateur | Médiane temps LLM |
| --- | ---: | ---: |
| v4 | 21 410 | 81,1 s |
| v5 | 17 359 | 66,7 s |
| v7 | 31 310 | 107,2 s |

Les treize rejets représentent environ 17 min 48 s de calcul déjà effectué. Ces durées sont descriptives : la longueur du raisonnement généré et d'autres facteurs varient aussi.

Dans une requête v7 représentative : 10 149 caractères système et 20 694 caractères utilisateur, dont 12 716 pour le schéma. L'intention visible, préfixe inclus, fait 2 186 caractères. La raccourcir rendra les priorités plus faciles à lire, mais ne supprimera qu'une petite partie du paquet complet. La longueur seule n'explique pas les échecs : la v5, plus courte que la v4, échoue aussi dans cet échantillon.

Les Plans v7 rejetés savent déjà identifier une aide, un objet et un mécanisme. Dans le cas des rochers, le Plan propose une intervention et une preuve de protection cohérentes sur le papier. Dans les deux cas de vague, il se concentre sur le déplacement de provisions ou d'un chariot alors que le danger principal reste présent. Cette aide logistique n'est pas automatiquement inutile, mais le Plan ne démontre pas clairement que le bénéfice durera face à la vague. Il faut mieux hiérarchiser **besoin principal, effet durable et merci**. Aucune vidéo issue de ces Plans rejetés n'a été examinée : il s'agit d'une lecture des Plans.

## 5. Proposition limitée à l'intention, non appliquée

### Texte narratif à essayer

> Vidéo de dix secondes, en un seul plan continu. Conserve l'état initial, les personnages, les proportions et les règles de l'univers de l'image. Utilise son intention d'origine pour identifier le besoin principal, le bénéficiaire et les efforts déjà engagés. N'invente pas de crise ; lorsqu'un danger existe, montre son comportement et ses effets réels.
>
> Une même main géante apporte une aide utile, directement ou avec un accessoire. Choisis le mécanisme avant l'objet. Utilise l'assortiment proposé lorsqu'il convient ; sinon, la main seule ou un autre objet restent possibles avec une justification. Aucun parapluie, parasol ou ombrelle comme solution.
>
> Montre seulement les gestes nécessaires, leur action sur la cible et un résultat durable. Traite le besoin principal : un danger persistant ne doit pas annuler immédiatement le bénéfice montré. Laisse le bénéficiaire profiter de l'amélioration, puis les habitants donnent l'unique merci autorisé, brièvement, dans la dernière action. Leur activité peut continuer. Garde un cadrage stable permettant de comprendre l'intervention.

Ce texte conserve l'aide sans urgence obligatoire, le bénéficiaire non humain, les moyens libres, la variété et le résultat avant merci. Les règles structurées existantes restent en place ; on ne prétend pas les supprimer en changeant l'intention visible.

### Deux précisions techniques dans l'entrée du preset

1. **Remerciement :** lorsque langue et formule sont déjà connues, fournir leur balise exacte comme l'unique parole autorisée à copier dans la dernière action. Préciser que `spoken_lines` contient les mots seuls et `spoken_languages` le nom anglais seul. Les caractères `[` et `]` entourant la langue sont obligatoires ; une seule fermeture de balise après les mots. Ne pas mettre dans l'intention une fausse réplique d'exemple ou une seconde langue : elle pourrait être interprétée comme une parole à protéger. Si la langue reste à choisir visuellement, décrire la grammaire sans introduire de parole alternative.
2. **Caméra pour l'essai initial :** demander `static_shot`, `amplitude: null`, `speed: null`, `target_clause: ""`. C'est une restriction de mise en scène dans l'intention, compatible avec les validateurs actuels. Si les mouvements sont conservés ensuite, rappeler les amorces techniques autorisées dans l'entrée du preset.

Les formes de balises et de champs caméra sont des indications syntaxiques, pas des scénarios ni des associations objet-problème. Aucun exemple de solution issu du batch n'est à ajouter.

### Ce que cet essai ne doit pas changer

- Pas de modification du prompter H3 partagé, de son validateur caméra ou de son normaliseur de parole.
- Pas de réparation silencieuse des réponses, de suppression du merci ou d'assouplissement général pour accepter un Plan incorrect.
- Pas de nouveau modèle ou d'appel de critique pour masquer une erreur de format.
- Pas de promesse de réussite avant un essai réel : les validations peuvent révéler d'autres erreurs après correction des premiers blocages.

Après accord, essayer la nouvelle intention sur quelques fiches représentatives avant de relancer un grand lot. Comparer les requêtes effectives, l'acceptation du Plan, le balisage, la pertinence de l'aide et le bénéfice précédant la gratitude. Aucun de ces essais n'a été lancé dans cet audit.

## 6. Tension annexe : un parasol existe déjà dans certaines images

L'image `asset-6696b56c937d41feb911a02290de58d9`, inspectée directement, contient un parasol sur son bord gauche. Le Plan `llm-f9e699987fc044abace4da15cb28e643` décrit un cadrage excluant ce bord. Le système demande à la fois de conserver la première image et de ne pas conserver de parapluie/parasol. Ces exigences peuvent entrer en conflit lorsque l'objet est déjà dans le décor.

Ce n'est pas la cause des rejets comptés. Une formulation interdisant cet objet **comme solution apportée par la main** serait plus précise, mais l'intention seule ne peut garantir d'annuler une interdiction système plus prioritaire. Un éventuel ajustement de cette règle devrait rester propre au preset ; aucun changement n'est proposé au H3 partagé pour ce point. L'interdiction actuelle n'a pas été modifiée.

## Traces principales

| Appel | Version | Observation |
| --- | --- | --- |
| `llm-2e64ed9f6d0f42528dca96e5fb6052ff` | v4 | Plan accepté entre deux échecs v5, balise française correcte. |
| `llm-c4f9a06e371e4cee8767edf5a85de82a` | v7 | Rochers : champs de langue corrects, balise mal formée. |
| `llm-cf39ae0c0e82410197df877cfa280bdb` | v7 | Vague : caméra rejetée, parole également incorrecte. |
| `llm-f9e699987fc044abace4da15cb28e643` | v7 | Vague : caméra rejetée, parole incorrecte, priorité donnée aux provisions. |
| `llm-f894e3b0b1904c558a079de1b88c8726` | v7 | Caméra rejetée, balise anglaise incorrecte. |

## Clarification après question de l'utilisateur : périmètre et retour à la base standard

Vérification complémentaire en lecture seule : la condition exacte est `source.speech_policy in CAUSAL_HELP_POLICIES`, dont les seules valeurs sont les politiques Petits hommes v5/v6/v7. Elle remplace les consignes du **Plan et du Writer**, désactive la recette éditable et substitue les permissions créatives spécifiques. Les autres politiques suivent les branches habituelles. Une fiche personnalisée issue de Petits hommes conserve son origine et cette politique ; appliquer un autre preset nommé réinitialise l'origine/version. Cette confirmation porte sur le routage des consignes, sans prétendre qu'aucun fichier technique partagé n'a été modifié.

Historique : v5 introduit le système distinct, le contrat causal et le transport des actions approuvées au Writer ; v6 ajoute l'assortiment et la variété des mécanismes ; v7 ajoute le contexte de l'image, l'aide sans danger obligatoire, le bénéficiaire non humain et la branche de contexte insuffisant. Ces versions changent donc davantage que l'intention visible. La séparation avait notamment pour but d'éviter les exemples de solutions et les contraintes narratives génériques ; elle a aussi supprimé du guidage technique utile.

La proposition précédente était bien un essai **intention seule**, en y insérant les précisions de format. L'utilisateur questionne maintenant l'intérêt de repartir d'une version qui fonctionne. Recommandation de fond précisée : reprendre la base technique H3 standard utilisée par les v4 acceptées et exprimer les règles éditoriales Petits hommes dans son intention/contexte dédié. Conserver dix secondes, aide adaptée, variété, contexte image, bannissement du parapluie et bénéfice avant merci, sans rétablir les anciennes associations de solutions.

Cette voie implique de changer le raccordement propre à Petits hommes, **sans modifier les consignes du H3 partagé**. Ce n'est pas un simple échange de texte : les schémas `help_contract`/`variety_choice`, leurs validations et le transport protégé des actions au Writer doivent être réalignés avec le chemin retenu. Définir ce périmètre dans un futur patch ; ne pas promettre que les instructions standard seules satisferont tous les contrats spécifiques. Les vingt Plans v4 acceptés constituent une base comparative favorable, pas une garantie de qualité des vidéos ni de réussite de la future combinaison.

**Aucun changement applicatif autorisé ou réalisé par cette clarification.** L'utilisateur pose des questions ; cette recommandation ne vaut pas accord d'implémentation.
