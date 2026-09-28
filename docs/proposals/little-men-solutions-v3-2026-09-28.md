# Petits hommes expérimental : correction des solutions — 28 septembre 2026

Le preset demandait implicitement deux gestes (trois courts au maximum) et
répétait la sélection de langue dans l’intention, le contexte et les règles.
L’audit des rendus a relevé notamment des collectes d’eau suivies de vidanges
dans la zone à protéger. La v3 demande une solution lisible et durable, avec
les gestes nécessaires et un remerciement minimal.

## Changement

- Intention recentrée sur le détournement d’un objet du quotidien, monumental
  pour les personnages, l’effet utile et le résultat final.
- Aucun nombre de gestes imposé par le preset. Le contrat générique reste
  inchangé : une ou deux phases par plan et jusqu’à six entrées d’actions par
  phase. Une entrée n’est pas un quota de gestes. Durée inchangée : 10 s.
- Une phrase dans continuity_invariants lie problème, mécanisme et bénéfice.
  Pour une inondation ou une vague : origine, zone protégée, trajet et destination hors de cette zone.
  Le contenant peut repartir plein ; un afflux continu doit être contenu ou
  détourné avant les remerciements. Aucun catalogue ou interdit d’objets.
- Les 11 langues, pools, priorité manuelle, provenance, équilibre et tirage
  persistant restent les mêmes. Formules minimales strictes conservées.
- Langue connue : uniquement cette langue et sa formule. Langue encore à
  déduire de l’image : les pools et l’ordre figé restent réservés au Plan.
  Le Prompt utilise la langue du Plan approuvé. La source persistée et ses
  signatures restent identiques entre les deux étapes.
- Notes manuelles et intention image gardées, doublons exacts retirés.
  Description image bornée à un extrait signalé de 1 200 caractères ; le
  style long séparé n’est utilisé qu’en l’absence de description. Les sources
  intégrales restent dans la fiche et servent toujours au repérage du pays.

## Activation et conservation

La politique little_men.localized_thanks.v3 s’applique aux nouvelles
préparations. Un Plan/Prompt déjà commencé en v1/v2 conserve ses règles.
Dupliquer un ancien essai crée une nouvelle préparation : l’intention
standard v2 exacte devient la v3, les réglages de rendu sont conservés.
L’intention source et les résultats d’origine ne sont pas modifiés.
Les intentions personnalisées restent intactes ; pour les remplacer, appliquer
explicitement le preset expérimental. Pour un ancien preset v1, réappliquer
également le preset sur la copie afin de reprendre la nouvelle intention.

Aucun changement des modèles, de la durée, des recettes de rendu, du preset
classique ou des lèvres. Aucun patch de l’anomalie annexe South American :
elle reste à corriger séparément comme prévu dans l’audit.

## Vérification

Tests hors ligne préparés dans tests/test_video_factory_solutions.py ; adaptation
du test de version courante dans tests/test_video_factory_languages.py.
Les anciens tests v1/v2 restent disponibles. Les tests fonctionnels sont à lancer
par l’utilisateur conformément à AGENTS.md. Aucun appel LLM, rendu ou redémarrage
n’a été lancé pendant l’implémentation.

Commande courte après chargement du checkout actif :

    python -m unittest tests.test_video_factory_solutions tests.test_video_factory_languages tests.test_video_factory_experimental tests.test_classic_cinematic tests.test_video_preparation_recipes

Commande complète :

    python -m unittest discover -s tests

## Comparaison manuelle proposée, sans génération lancée

Préparer deux variantes sur les mêmes six images, ancien et nouveau comportement,
avec les mêmes modèles, durée, recette, dimensions, LoRA et seed de rendu.
Fixer la même langue dans chaque paire pour isoler la qualité de la solution.
La génération LLM reste variable : une comparaison unique donne un indice,
pas une preuve causale exhaustive.

| Cas | Point à examiner |
| --- | --- |
| Inondation stagnante | Baisse nette, destination de l’eau lisible, pas de retour dans la rue |
| Inondation alimentée | Traitement de l’arrivée d’eau en plus de la collecte |
| Tsunami | Protection adaptée à la vague, amélioration maintenue après retrait |
| Incendie | Extinction compréhensible et durable |
| Tornade | Mécanisme ludique lisible et disparition durable du danger |
| Sécheresse / réparation | Liberté de solution conservée hors des scènes d’eau |

Avant le rendu, vérifier problème → mécanisme → résultat dans chaque Plan.
Après le rendu, évaluer l’aide sans explication, le lien geste/effet, la baisse
réelle du problème, la persistance après retrait et le remerciement exact.
Noter la variété des objets sur l’ensemble, sans en faire un quota.
Si le Plan est pertinent mais le rendu inverse le transfert d’eau, simplifier
cette mise en scène avant d’ajouter des règles générales.

Contrôles statiques réussis : AST des dix fichiers Python modifiés/ajoutés,
imports de huit modules applicatifs/domaines, compilation V8 du JavaScript
sans exécution de l’interface, git diff --check. Comparaison statique :
l’intention passe de 373 à 107 mots ; les constantes des presets classique,
lèvres et historique v2 sont inchangées. Le classificateur de pays, les pools,
l’équilibrage et le hash des entrées de sélection restent identiques.

Les sauvegardes et le diff isolé se trouvent dans
D:/Code/panelforge/.agent/diagnostics/little-men-solutions-v3-20260928/.
