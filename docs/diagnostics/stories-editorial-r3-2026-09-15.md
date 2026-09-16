# Histoires r3 — scènes concrètes et continuité

Implémentation autorisée le 15 septembre 2026 après lecture du scénario
« Le Prix du Luxe ». Recette `story.brainrot@1.0.0`, révision éditoriale r3.

## Constat

Le développement r2 (`llm-88dc9db8e4904d5e950e3bee6c7fe864`) conserve un sacrifice
surtout raconté, étire la révélation sur plusieurs clips et termine sur une
décision encore abstraite. Le collier est récupéré « après le départ » d'Ananas
alors qu'elle est encore observée dans la pièce ; un dialogue attribue à Fraise
une affirmation injustifiée sur ce que sa femme connaît.

R2 contenait déjà des règles de causalité et de dramaturgie. Les exemples
narratifs de `concepts.txt` ne sont pas envoyés au rédacteur du scénario : ce
second appel reçoit `scenario.txt`, auparavant surtout composé de règles générales.
L'hypothèse de cette révision est qu'une démonstration dans le format de sortie
facilitera leur application. Ce gain reste à vérifier avec les modèles locaux.

## Changement

- `editorial-r3/concepts.txt` définit les champs des propositions par leurs actes,
  enjeux et conséquences, avec des exemples d'issues différentes. Les trois pistes
  doivent varier autrement que par l'alibi. Aucune trame unique imposée.
- `editorial-r3/scenario.txt` contient un exemple JSON complet de deux clips liés.
  Une mère garde la même enveloppe, son fils en découvre le contenu au moment où
  elle le lui montre, puis perd l'aide après l'avoir humiliée. Les états initiaux
  et finaux suivent les objets, les présences et les connaissances utiles.
- `editorial-r3/revision.txt` aligne la conversation sur cette écriture, conserve
  le mode discussion seule et répercute les corrections sur les raccords concernés.
- Les répliques restent courtes et jouables avec des gestes dans `clip_seconds`.
  Pas de quota de mots, de nombre d'actions, d'horodatage ou de caméra imposée.
  Les dialogues expressément validés restent préservés sauf demande contraire.

Deux appels : propositions puis développement ; les révisions restent demandées
par l'auteur. Pas de troisième appel de contrôle, de modification du schéma, de
changement d'interface ou de modification H3/REF2V/KREA2.

## Versions et utilisation

Les trois sources r3 sont dans `prompt_sources/story.brainrot/1.0.0/editorial-r3/`.
Les sources et archives r1/r2 restent intactes. `LocalStoryRecipeStore` migre
uniquement une installation d'origine, sans personnalisation ni retour à une
ancienne version : r1 → r2 → r3, ou r2 → r3. Les archives antérieures sont
conservées et une reprise de r1/r2 après migration reste active après redémarrage.

Une recette déjà personnalisée ou restaurée reste active. Les sources r3 peuvent
alors être reprises dans l'éditeur pour une adoption explicite ; aucune fusion
silencieuse des textes de l'auteur n'est effectuée.

Dans **Consignes LLM → Histoires**, la note de r3 est
« Scènes concrètes : exemples JSON, actes, conséquences et continuité ».
Les nouveaux échanges lisent la révision active. Un échange déjà commencé garde
sa copie ; les anciens scénarios et traces ne sont pas réécrits.

Activation dans le workspace utilisateur effectuée le 15 septembre : révision
active 3, historique 3/2/1. Les douze fichiers des archives r1/r2 sont inchangés.
La recette est enregistrée pour les prochains échanges, sans redémarrage lancé
par l'agent. Le service lit la version active au démarrage de chaque demande.

## Vérification et essai utilisateur

Contrôles statiques : AST des fichiers Python modifiés, lecture UTF-8, syntaxe et
références du JSON d'exemple, `git diff --check`. Les régressions de migration
préparées dans `tests.test_stories` couvrent une ancienne r2, la conservation des
archives, les personnalisations et le maintien des retours à r1/r2. Aucun test
applicatif, appel LLM, rendu ou redémarrage de service n'est exécuté par l'agent.

Pour évaluer l'écriture, garder le même modèle et le même brief que pour r2,
demander trois nouvelles pistes puis développer celle retenue. Comparer les
actes des antagonistes, la cohérence, la progression des clips et la fin.
Essayer ensuite un autre conflit, par exemple une injustice au travail, pour
vérifier que le modèle ne recopie pas l'exemple de la mère et du fils.

Commande de régressions, à lancer par l'utilisateur depuis le checkout :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_stories
```
