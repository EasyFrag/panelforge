# Audit des échecs Ref2V : une étape, deux étapes et révision

Lecture des appels enregistrés et des projets locaux le 5 septembre 2026.
Aucun appel LLM, rendu, test ou redémarrage lancé. Les corrections ci-dessous
sont écrites ; elles ne sont pas validées par une nouvelle exécution.

## Parcours une étape

Session `prompt-063ccea6b093492ea4a72ccb55d230b1`, recette
`minimax.h3.ref2v.direct.prompt@1.0.0`, quatre références.

Les appels `llm-307a01c7464b4e0dae59f111237fb990` (36,160 s) et
`llm-298cca32008d42a2b7c23bbb0485503a` (39,099 s) sont rejetés avec
`unsupported output contract: minimax.h3.mono.prompt_direct_v1`.
Le JSON reçu contient bien les quatre champs demandés, une caméra statique
et la progression du chantier sur dix secondes.

Cause : `_append_revision` contrôle le contrat direct et son contexte, puis
tombe dans un second dispatch de labels réservé aux anciens contrats. Le
contrat direct manque dans cette seconde sélection. Le rejet arrive donc
après la compilation et la validation initiales.

Correction : ce contrat déjà contrôlé ne tombe plus dans l'erreur des contrats
inconnus. Les contrôles de références, durée, dialogues, champs et caméra
restent appliqués. Le même chemin sert aux recettes H3 Base en une étape.

## Parcours deux étapes

Session `prompt-a5eab5f101894c8f9976e4db2ef3c86e`, recette
`minimax.h3.ref2v.direct.planned@1.0.0`, first frame + trois keyframes.

Plan accepté en 61,761 s (`llm-d83776dd435c41d2a105af4ccb638450`). Les writers
`llm-7fff5e602c8445bca57d0ff8e09bbc46` (45,211 s) et
`llm-ce903b45a33e4a9db5f64fc86cf4bded` (36,298 s) échouent sur
`<Picture 2> doit apparaître exactement une fois dans le mapping.`

Le writer ne recopie pas cette référence. Le Plan approuvé contient
`bright daylight matching <Picture 2>` dans son état final. L'application
réinjecte cet état dans le texte du clip. Le validateur compte ensuite la
déclaration dans l'en-tête **et** cette citation dans l'action comme deux
déclarations concurrentes.

Correction : vérifier l'unicité dans le paragraphe de mapping. Une référence
déjà déclarée peut être citée dans le corps. Les doublons dans le mapping,
labels non contigus, références non déclarées et altérations de l'en-tête
compilé restent refusés. Le correctif antérieur « user intention and plan »
reste en place. Le Plan accepté de ce run n'a pas besoin d'être régénéré.

## Révision après vidéo

Projet `h3-render-eec5f07ce8cd471989dc22afee2a92e0`, issu du parcours trois étapes
`prompt-2fb732355c2e4aad9fc546634d349a49`. Demande : un enregistrement fixe
passé en avance rapide, plutôt qu'un homme donnant simplement l'impression
de courir vite.

- `llm-f4d0bfe6eba446efa74faec1924af695` (67,254 s) : le modèle propose bien
  deux directives statiques, à 0 et 7 secondes. Le validateur compte la phrase
  statique sans timestamp deux fois, car elle est aussi une sous-chaîne de la
  directive horodatée à 7 secondes.
- `llm-0dceeda685084f9590243e6864c58633` (38,051 s) : la tentative de réparation
  recopie réellement les tokens caméra et leurs phrases compilées, ce qui
  crée des doublons. Elle revient aussi aux anciennes directives.
- `llm-ce65adf8cf0642e98a97a772be824892` (111,997 s) : le modèle restitue les
  deux directives statiques et les tokens seuls, mais retrouve le premier
  faux rejet.

Correction : comparer les directives complètes extraites, timestamp compris,
plutôt que compter les sous-chaînes. Le compilateur retire aussi une copie
exacte d'une ancienne/nouvelle phrase caméra placée immédiatement après son
propre token. Il conserve les autres éléments du texte et continue à refuser
les directives manquantes, les timestamps altérés, les tokens inconnus et les
directives supplémentaires. Aucun changement de consigne créative requis.

## Vérification préparée

`tests/test_video_preparation_recipes.py` étendu : génération, approbation,
réouverture et révision du parcours une étape avec quatre et neuf références ;
deux/trois étapes avec quatre références et citation de keyframe dans l'état
final compilé. `tests/test_ref2v_validation_regressions.py` ajouté : mapping et
citations, deux segments statiques, timestamp préservé, doublon adjacent exact
et cas qui doivent rester rejetés, sur Ref2V et H3 Base.

Ces tests sont **non exécutés**, conformément à la consigne utilisateur.
Syntaxe Python contrôlée par AST et `git diff --check` uniquement. Aucun projet
ou résultat utilisateur modifié. Après chargement du nouveau backend,
l'utilisateur peut reprendre les étapes échouées et la révision refusée.

## Discussion presets KREA : proposition uniquement

Le parcours « Préparer la recette » publie déjà une recette Batch complète :
prompt canonique, invariants, variables, risques et réglages. Il est plus lourd
qu'un favori de réglages dans l'exploration Assisted.

Proposition : enregistrer sous un nom le checkpoint, les LoRA et leurs forces,
avec le prompt et une miniature de l'essai comme exemple conservé. Charger
les réglages par défaut ; offrir « Reprendre aussi le prompt » en option.
Conserver le ratio/résolution et la seed d'origine dans la provenance, sans
imposer une seed fixe aux nouveaux sujets. Les éventuels mots déclencheurs de
LoRA doivent rester identifiables si une couche de style est extraite ensuite.

Dans les essais moto 20/21, le prompt est identique et porte déjà le rendu
soft focus, grain et micro-contraste réduit ; les LoRA et la résolution changent.
Ce constat justifie de conserver le prompt d'exemple, sans attribuer à ce seul
audit la réussite d'un réglage ou sa transférabilité à tous les sujets.
Aucune fonction de preset ajoutée pendant cette discussion.
